from rest_framework import serializers
from .models import Account, CreditCard, CreditCardInvoice
from .services import AccountService, CreditCardService
from core.services.plan_limits import PlanLimitsService

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            'id', 'name', 'type', 'initial_balance', 'balance', 
            'institution', 'color', 'is_manual', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_manual', 'balance']

    def validate(self, data):
        # Validar limite APENAS na criação
        if not self.instance:
            user = self.context['request'].user
            if not PlanLimitsService.can_add_account(user):
                raise serializers.ValidationError("Limite de contas excedido para o seu plano.")
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class CreditCardInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditCardInvoice
        fields = ['id', 'month', 'year', 'status', 'total_amount', 'closing_date', 'due_date']

class InvoicePaymentSerializer(serializers.Serializer):

    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    account_id = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none(), required=True)
    date = serializers.DateField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
             self.fields['account_id'].queryset = Account.objects.filter(user=request.user, is_active=True)


class CreditCardSerializer(serializers.ModelSerializer):
    available_limit = serializers.SerializerMethodField()
    current_invoice_total = serializers.SerializerMethodField()
    next_due_date = serializers.SerializerMethodField()
    
    # Campos para vínculo com conta (FE-002)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none(), # Placeholder, populado no __init__
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra contas apenas do usuário logado
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
             self.fields['account_id'].queryset = Account.objects.filter(user=request.user, is_active=True)

    def validate(self, data):
        if 'closing_day' in data:
            self.validate_closing_day(data['closing_day'])
        if 'due_day' in data:
            self.validate_due_day(data['due_day'])
            
        if not self.instance:
            user = self.context['request'].user
            if not PlanLimitsService.can_add_card(user):
                raise serializers.ValidationError("Limite de cartões excedido para o seu plano.")
        return data

    def get_invoice_data(self, obj):
        if not hasattr(obj, '_invoice_data'):
            obj._invoice_data = CreditCardService.get_invoice_data(obj)
        return obj._invoice_data

    def get_available_limit(self, obj):
        data = self.get_invoice_data(obj)
        return data['available_limit']

    def get_current_invoice_total(self, obj):
        data = self.get_invoice_data(obj)
        return data['current_invoice_total']
    
    def get_next_due_date(self, obj):
        return CreditCardService.get_next_due_date(obj)

    def create(self, validated_data):
        user = self.context['request'].user
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
