from rest_framework import serializers
from django.db import transaction
from dateutil.relativedelta import relativedelta
from .models import Transaction, Category, Tag, RecurringTransaction
from accounts.models import Account, CreditCard
from .services import TransactionService, CategoryService
from core.fields import (
    OwnedPrimaryKeyRelatedField, CONTA_NAO_ENCONTRADA, CARTAO_NAO_ENCONTRADO,
    CATEGORIA_NAO_ENCONTRADA, TAG_NAO_ENCONTRADA,
)
from core.valores import validar_valor_positivo

# Tipos que o endpoint genérico cria e entre os quais troca (SALDO-18, SALDO-19).
# Transferência, compra no cartão e pagamento de fatura nascem só das
# operações próprias (AD-005).
TIPOS_DO_ENDPOINT = ('INCOME', 'EXPENSE')
TIPO_NAO_CRIAVEL = 'Por aqui só é possível criar receitas e despesas.'
TIPO_NAO_ALTERAVEL = 'O tipo só pode ser trocado entre receita e despesa.'
COMPRA_SO_PELA_FATURA = 'Compras no cartão são efetivadas pelo pagamento da fatura.'

class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    parent_name = serializers.ReadOnlyField(source='parent.name')
    parent = OwnedPrimaryKeyRelatedField(
        queryset=Category.objects.all(), not_found_message=CATEGORIA_NAO_ENCONTRADA,
        required=False, allow_null=True,
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'icon', 'color', 'type', 'parent', 'parent_name', 'subcategories', 'is_active']
        read_only_fields = ['id', 'subcategories', 'parent_name']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Categoria-pai de outro usuário não aparece (ISOL-15)
        if instance.parent_id and instance.parent.user_id != instance.user_id:
            ret['parent'] = None
            ret['parent_name'] = None
        return ret

    def get_subcategories(self, obj):
        # Retorna subcategorias de 1º nível, só as do dono da categoria (ISOL-14)
        subs = obj.subcategories.filter(is_active=True, user_id=obj.user_id)
        return CategorySerializer(subs, many=True).data

    def create(self, validated_data):
        user = self.context['request'].user
        parent = validated_data.get('parent')
        
        # Check Limits
        CategoryService.check_limits(user, parent)
        
        validated_data['user'] = user
        return super().create(validated_data)

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']
        read_only_fields = ['id']

class TransactionSerializer(serializers.ModelSerializer):
    account_detail = serializers.SerializerMethodField()
    category_detail = CategorySerializer(source='category', read_only=True)
    tags_detail = TagSerializer(source='tags', many=True, read_only=True)

    # Relações graváveis: só objetos do usuário da requisição (AD-032), e
    # conta excluída não recebe movimentação nova (SALDO-35)
    account = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True), not_found_message=CONTA_NAO_ENCONTRADA,
        required=False, allow_null=True,
    )
    credit_card = OwnedPrimaryKeyRelatedField(
        queryset=CreditCard.objects.all(), not_found_message=CARTAO_NAO_ENCONTRADO,
        required=False, allow_null=True,
    )
    category = OwnedPrimaryKeyRelatedField(
        queryset=Category.objects.all(), not_found_message=CATEGORIA_NAO_ENCONTRADA,
        required=False, allow_null=True,
    )
    tags = OwnedPrimaryKeyRelatedField(
        queryset=Tag.objects.all(), not_found_message=TAG_NAO_ENCONTRADA,
        many=True, required=False,
    )
    
    # Transfer details
    related_transaction = serializers.SerializerMethodField()
    target_account_id = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True),
        not_found_message=CONTA_NAO_ENCONTRADA,
        write_only=True, 
        required=False, 
    )
    signed_amount = serializers.SerializerMethodField()
    update_scope = serializers.ChoiceField(
        choices=['SINGLE', 'ALL_FUTURE'], 
        default='SINGLE', 
        write_only=True
    )
    is_recurring = serializers.BooleanField(write_only=True, default=False)
    frequency = serializers.ChoiceField(
        choices=RecurringTransaction.FREQUENCY_CHOICES, 
        required=False, 
        write_only=True
    )
    recurring_source = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'status', 'description', 'amount', 'signed_amount', 'date',
            'account', 'account_detail', 'credit_card', 'invoice', 
            'category', 'category_detail',
            'tags', 'tags_detail',
            'is_installment', 'installment_number', 'installment_total',
            'transfer_id', 'related_transaction', 'target_account_id', 'update_scope',
            'is_recurring', 'frequency', 'recurring_source',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice', 'is_installment', 'installment_number', 'installment_total',
            'transfer_id', 'related_transaction', 'signed_amount', 'recurring_source',
            'created_at', 'updated_at'
        ]
        # Valor maior que zero, com até duas casas (SALDO-09)
        extra_kwargs = {'amount': {'validators': [validar_valor_positivo]}}

    def to_representation(self, instance):
        """
        Injeta is_recurring e frequency no output baseado no recurring_source.
        """
        representation = super().to_representation(instance)

        # Conta, categoria e tags de outro usuário não aparecem (ISOL-15)
        dono = instance.user_id
        if instance.account_id and instance.account.user_id != dono:
            representation['account'] = None
            representation['account_detail'] = None
        if instance.category_id and instance.category.user_id != dono:
            representation['category'] = None
            representation['category_detail'] = None
        tags_alheias = {str(tag.id) for tag in instance.tags.all() if tag.user_id != dono}
        if tags_alheias:
            representation['tags'] = [i for i in representation['tags'] if str(i) not in tags_alheias]
            representation['tags_detail'] = [
                tag for tag in representation['tags_detail'] if tag['id'] not in tags_alheias
            ]
        
        # Se tem recurring_source, é recorrente
        has_recurrence = instance.recurring_source is not None
        representation['is_recurring'] = has_recurrence
        
        if has_recurrence:
            representation['frequency'] = instance.recurring_source.frequency
        else:
            representation['frequency'] = None
            
        return representation

    def get_signed_amount(self, obj):
        # Retorna negativo para saídas e positivo para entradas
        if obj.type in ['EXPENSE', 'TRANSFER_OUT', 'INVOICE_PAYMENT', 'CREDIT_CARD']:
            return -abs(obj.amount)
        return abs(obj.amount)

    def get_account_detail(self, obj):
        if obj.account:
            return {'id': obj.account.id, 'name': obj.account.name}
        return None

    def get_related_transaction(self, obj):
        if obj.transfer_id:
            # Tenta achar a parceira
            # Cachear isso seria bom, mas para detail view ok.
            # Só a parceira do dono da transação, com a conta dele (ISOL-14, ISOL-15)
            qs = Transaction.objects.filter(
                transfer_id=obj.transfer_id, user_id=obj.user_id
            ).exclude(id=obj.id)
            partner = qs.first()
            if partner:
                 conta_do_dono = partner.account if partner.account and partner.account.user_id == obj.user_id else None
                 return {
                     'id': partner.id,
                     'account_name': conta_do_dono.name if conta_do_dono else 'Desconhecida',
                     'amount': partner.amount,
                     'type': partner.type
                 }
        return None

    def validate(self, attrs):
        # Edição de transação ainda ligada a objeto de outro usuário, ou a
        # categoria-modelo, é recusada até o corpo desfazer a ligação (ISOL-02)
        if self.instance is not None:
            dono = self.instance.user_id
            erros = {}
            for campo, mensagem in (
                ('account', CONTA_NAO_ENCONTRADA),
                ('credit_card', CARTAO_NAO_ENCONTRADO),
                ('category', CATEGORIA_NAO_ENCONTRADA),
            ):
                atual = getattr(self.instance, campo)
                if campo not in attrs and atual is not None and atual.user_id != dono:
                    erros[campo] = [mensagem]
            if 'tags' not in attrs and self.instance.tags.exclude(user_id=dono).exists():
                erros['tags'] = [TAG_NAO_ENCONTRADA]
            if erros:
                raise serializers.ValidationError(erros)
        self._validar_tipo_e_status(attrs)
        return attrs

    def _validar_tipo_e_status(self, attrs):
        tipo = attrs.get('type')
        if self.instance is None:
            if tipo not in TIPOS_DO_ENDPOINT:
                raise serializers.ValidationError({'type': [TIPO_NAO_CRIAVEL]})
            return
        atual = self.instance.type
        if tipo is not None and tipo != atual and not (tipo in TIPOS_DO_ENDPOINT and atual in TIPOS_DO_ENDPOINT):
            raise serializers.ValidationError({'type': [TIPO_NAO_ALTERAVEL]})
        # Compra no cartão só é efetivada pelo pagamento da fatura (SALDO-46)
        if atual == 'CREDIT_CARD' and attrs.get('status') == 'COMPLETED' and self.instance.status != 'COMPLETED':
            raise serializers.ValidationError({'status': [COMPRA_SO_PELA_FATURA]})

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Extrair dados de recorrência
        is_recurring = validated_data.pop('is_recurring', False)
        frequency = validated_data.pop('frequency', None)
        
        # Extrair tags
        tags = validated_data.pop('tags', [])
        
        # Limpar campos virtuais
        validated_data.pop('target_account_id', None)
        validated_data.pop('update_scope', None)
        
        # 1. Criar a Transação base
        validated_data['user'] = user
        transaction = super().create(validated_data)
        
        if tags:
            transaction.tags.set(tags)
            
        # 2. Lógica de Recorrência
        if is_recurring and frequency:
            recur = RecurringTransaction.objects.create(
                user=user,
                description=transaction.description,
                amount=transaction.amount,
                type=transaction.type,
                account=transaction.account,
                credit_card=transaction.credit_card,
                category=transaction.category,
                frequency=frequency,
                start_date=transaction.date
            )
            
            # Vincular a transação original ao template
            transaction.recurring_source = recur
            transaction.save(update_fields=['recurring_source'])

            # 3. Gerar ocorrências futuras (LIMIT de 12 meses/ciclos no total)
            current_date = transaction.date
            
            # Já criamos a primeira. Gerar mais 11 futuras.
            for _ in range(11):
                if frequency == 'DAILY': delta = relativedelta(days=1)
                elif frequency == 'WEEKLY': delta = relativedelta(weeks=1)
                elif frequency == 'MONTHLY': delta = relativedelta(months=1)
                elif frequency == 'YEARLY': delta = relativedelta(years=1)
                else: break
                
                current_date += delta
                
                # Criar transação futura
                future_txn = Transaction.objects.create(
                    user=user,
                    description=transaction.description,
                    amount=transaction.amount,
                    type=transaction.type,
                    account=transaction.account,
                    credit_card=transaction.credit_card,
                    category=transaction.category,
                    date=current_date,
                    status='PENDING' if transaction.type in ['EXPENSE', 'CREDIT_CARD'] else 'COMPLETED',
                    recurring_source=recur
                )
                if tags:
                    future_txn.tags.set(tags)
            
        return transaction

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        scope = validated_data.pop('update_scope', 'SINGLE')
        for campo in ('is_recurring', 'frequency'):
            validated_data.pop(campo, None)

        # 1. Perna de transferência: as duas pernas mudam juntas (SALDO-13 a SALDO-15)
        if instance.transfer_id:
            t = TransactionService.editar_transferencia(
                instance, validated_data, self.context['request'].user,
            )
            if tags is not None:
                t.tags.set(tags)
            return t
        validated_data.pop('target_account_id', None)

        # 2. Batch Installment Update (ALL_FUTURE)
        if scope == 'ALL_FUTURE' and instance.is_installment:
            from django.db.models import Q
            root_id = instance.parent_transaction_id or instance.id
            
            # Busca parcelas futuras (excluindo a atual, que será atualizada pelo super().update)
            # Só parcelas do dono da transação editada (ISOL-14)
            futures = Transaction.objects.filter(
                Q(id=root_id) | Q(parent_transaction_id=root_id)
            ).filter(
                installment_number__gt=instance.installment_number,
                user_id=instance.user_id,
            )
            
            for txn in futures:
                # Descrição NÃO propaga (para manter n/total)
                if 'amount' in validated_data:
                    txn.amount = validated_data['amount']
                if 'category' in validated_data:
                    txn.category = validated_data['category']
                
                txn.save()

        # 3. Normal Update
        t = super().update(instance, validated_data)
        
        if tags is not None:
            t.tags.set(tags)
            
        return t

# Serializers Específicos para Ações
class TransferSerializer(serializers.Serializer):
    # Só contas ativas do usuário da requisição (AD-032, SALDO-35)
    account_from = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True), not_found_message=CONTA_NAO_ENCONTRADA,
    )
    account_to = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True), not_found_message=CONTA_NAO_ENCONTRADA,
    )
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, validators=[validar_valor_positivo])
    date = serializers.DateField()
    description = serializers.CharField(max_length=255, required=False, default="Transferência")


class CreditCardExpenseSerializer(serializers.Serializer):
    credit_card = OwnedPrimaryKeyRelatedField(
        queryset=CreditCard.objects.all(), not_found_message=CARTAO_NAO_ENCONTRADO,
    )
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, validators=[validar_valor_positivo])
    date = serializers.DateField()
    description = serializers.CharField(max_length=255)
    category = OwnedPrimaryKeyRelatedField(
        queryset=Category.objects.all(), not_found_message=CATEGORIA_NAO_ENCONTRADA,
    )
    installments = serializers.IntegerField(default=1, min_value=1)
    tags = OwnedPrimaryKeyRelatedField(
        queryset=Tag.objects.all(), not_found_message=TAG_NAO_ENCONTRADA,
        many=True, required=False,
    )
