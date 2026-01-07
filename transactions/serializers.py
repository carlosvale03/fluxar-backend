from rest_framework import serializers
from django.db import transaction
from dateutil.relativedelta import relativedelta
from .models import Transaction, Category, Tag, RecurringTransaction
from accounts.models import Account, CreditCard
from .services import TransactionService, CategoryService

class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'icon', 'color', 'type', 'parent', 'subcategories', 'is_active']
        read_only_fields = ['id', 'subcategories']

    def get_subcategories(self, obj):
        # Retorna subcategorias de 1º nível
        subs = obj.subcategories.filter(is_active=True)
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
    
    # Transfer details
    related_transaction = serializers.SerializerMethodField()
    target_account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none(), 
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


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            self.fields['target_account_id'].queryset = Account.objects.filter(user=request.user, is_active=True)

    def to_representation(self, instance):
        """
        Injeta is_recurring e frequency no output baseado no recurring_source.
        """
        representation = super().to_representation(instance)
        
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
            qs = Transaction.objects.filter(transfer_id=obj.transfer_id).exclude(id=obj.id)
            partner = qs.first()
            if partner:
                 return {
                     'id': partner.id,
                     'account_name': partner.account.name if partner.account else 'Desconhecida',
                     'amount': partner.amount,
                     'type': partner.type
                 }
        return None

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
        target_account = validated_data.pop('target_account_id', None)
        scope = validated_data.pop('update_scope', 'SINGLE')
        
        # 1. Update Partner Account if requested
        if target_account and instance.transfer_id:
            partner = Transaction.objects.filter(
                transfer_id=instance.transfer_id
            ).exclude(id=instance.id).first()
            
            if partner:
                partner.account = target_account
                partner.save() # Dispara signal, mas sync_transfer_update ignora account change.
        
        # 2. Batch Installment Update (ALL_FUTURE)
        if scope == 'ALL_FUTURE' and instance.is_installment:
            from django.db.models import Q
            root_id = instance.parent_transaction_id or instance.id
            
            # Busca parcelas futuras (excluindo a atual, que será atualizada pelo super().update)
            futures = Transaction.objects.filter(
                Q(id=root_id) | Q(parent_transaction_id=root_id)
            ).filter(
                installment_number__gt=instance.installment_number
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
    account_from = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    account_to = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    date = serializers.DateField()
    description = serializers.CharField(max_length=255, required=False, default="Transferência")

    def __init__(self, *args, **kwargs):
        # Filtra querysets pelo usuario
        request = kwargs.get('context', {}).get('request')
        super().__init__(*args, **kwargs)
        if request and request.user:
            self.fields['account_from'].queryset = Account.objects.filter(user=request.user)
            self.fields['account_to'].queryset = Account.objects.filter(user=request.user)


class CreditCardExpenseSerializer(serializers.Serializer):
    credit_card = serializers.PrimaryKeyRelatedField(queryset=CreditCard.objects.none())
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    date = serializers.DateField()
    description = serializers.CharField(max_length=255)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none())
    installments = serializers.IntegerField(default=1, min_value=1)
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.none(), many=True, required=False)

    def __init__(self, *args, **kwargs):
        request = kwargs.get('context', {}).get('request')
        super().__init__(*args, **kwargs)
        if request and request.user:
            self.fields['credit_card'].queryset = CreditCard.objects.filter(user=request.user)
            self.fields['category'].queryset = Category.objects.filter(user=request.user)
            self.fields['tags'].queryset = Tag.objects.filter(user=request.user)
