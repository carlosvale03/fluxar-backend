from rest_framework import serializers
from .models import Account, CreditCard, CreditCardInvoice
from .faturas import proximo_vencimento, status_exibido
from .services import AccountService, CreditCardService
from core.fields import OwnedPrimaryKeyRelatedField, CONTA_NAO_ENCONTRADA
from core.travas import conferir_limite
from core.valores import dinheiro, validar_valor_positivo

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            'id', 'name', 'type', 'initial_balance', 'balance', 
            'institution', 'color', 'is_manual', 
            'is_active', 'created_at', 'updated_at'
        ]
        # is_active só muda pela exclusão, que confere saldo e pendentes (SALDO-34)
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_manual', 'balance', 'is_active']

    def create(self, validated_data):
        user = self.context['request'].user
        # Só a criação confere o limite; o cofrinho de uma meta nasce fora
        # daqui e não conta (PERM-16)
        conferir_limite(user, 'limite_contas')
        validated_data['user'] = user
        return super().create(validated_data)


class CreditCardInvoiceSerializer(serializers.ModelSerializer):
    # Aberta ou fechada pela data de hoje; paga quando recebe pagamento (FATURA-08, FATURA-09)
    status = serializers.SerializerMethodField()
    credit_card_id = serializers.UUIDField(source='card_id', read_only=True)
    # Valor, conta e data do pagamento ativo, ou null (FATURA-27)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = CreditCardInvoice
        fields = [
            'id', 'month', 'year', 'status', 'total_amount', 'closing_date', 'due_date',
            'credit_card_id', 'payment',
        ]

    def get_status(self, obj):
        return status_exibido(obj)

    def get_payment(self, obj):
        if obj.status != 'PAID':
            return None
        pagamento = (
            obj.pagamentos.filter(estornado_em__isnull=True).select_related('conta').order_by('-criado_em').first()
        )
        if pagamento is None:
            return None
        return {
            'amount': f'{pagamento.valor:.2f}',
            'account_id': str(pagamento.conta_id),
            'account_name': pagamento.conta.name,
            'date': pagamento.data.isoformat(),
        }

class InvoicePaymentSerializer(serializers.Serializer):

    amount = serializers.DecimalField(max_digits=15, decimal_places=2, validators=[validar_valor_positivo])
    # Só contas ativas do usuário da requisição (AD-032)
    account_id = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True), not_found_message=CONTA_NAO_ENCONTRADA,
        required=True,
    )
    date = serializers.DateField(required=True)
    # Identificador da tentativa (FATURA-29, FATURA-30); sem ele, é uma tentativa nova
    idempotency_key = serializers.UUIDField(required=False, allow_null=True)


class CreditCardSerializer(serializers.ModelSerializer):
    available_limit = serializers.SerializerMethodField()
    current_invoice_total = serializers.SerializerMethodField()
    next_due_date = serializers.SerializerMethodField()
    
    # Campos para vínculo com conta (FE-002); só contas ativas do usuário da requisição (AD-032)
    account_id = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True),
        not_found_message=CONTA_NAO_ENCONTRADA,
        source='account',
        required=False,
        allow_null=True
    )
    account = AccountSerializer(read_only=True)

    class Meta:
        model = CreditCard
        fields = [
            'id', 'name', 'limit', 'closing_day', 'due_day',
            'institution', 'color',
            'account', 'account_id', # Novos campos
            'available_limit', 'current_invoice_total', 'next_due_date',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'available_limit', 'current_invoice_total']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Conta de outro usuário não aparece no cartão (ISOL-15)
        if instance.account_id and instance.account.user_id != instance.user_id:
            ret['account'] = None
            ret['account_id'] = None
        return ret

    def validate(self, data):
        if 'closing_day' in data:
            self.validate_closing_day(data['closing_day'])
        if 'due_day' in data:
            self.validate_due_day(data['due_day'])
        return data

    def get_invoice_data(self, obj):
        if not hasattr(obj, '_invoice_data'):
            obj._invoice_data = CreditCardService.get_invoice_data(obj)
        return obj._invoice_data

    def get_available_limit(self, obj):
        data = self.get_invoice_data(obj)
        # Dinheiro como texto (CONTRATO-16)
        return dinheiro(data['available_limit'])

    def get_current_invoice_total(self, obj):
        data = self.get_invoice_data(obj)
        return dinheiro(data['current_invoice_total'])
    
    def get_next_due_date(self, obj):
        return proximo_vencimento(obj)

    def create(self, validated_data):
        user = self.context['request'].user
        conferir_limite(user, 'limite_cartoes')
        validated_data['user'] = user
        return super().create(validated_data)

    def validate_closing_day(self, value):
        if not (1 <= value <= 31):
            raise serializers.ValidationError("O dia de fechamento deve estar entre 1 e 31.")
        return value

    def validate_due_day(self, value):
        if not (1 <= value <= 31):
            raise serializers.ValidationError("O dia de vencimento deve estar entre 1 e 31.")
        return value
