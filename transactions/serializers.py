from rest_framework import serializers
from rest_framework import serializers
from .models import Transaction, Category, Tag
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

    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'status', 'description', 'amount', 'signed_amount', 'date',
            'account', 'account_detail', 'credit_card', 'invoice', 
            'category', 'category_detail',
            'tags', 'tags_detail',
            'is_installment', 'installment_number', 'installment_total',
            'transfer_id', 'related_transaction', 'target_account_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice', 'is_installment', 'installment_number', 'installment_total',
            'transfer_id', 'related_transaction', 'signed_amount',
            'created_at', 'updated_at'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            self.fields['target_account_id'].queryset = Account.objects.filter(user=request.user, is_active=True)

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

    def create(self, validated_data):
        # Criação simples (Receita/Despesa padrão)
        # Para logicas complexas use as actions da ViewSet
        user = self.context['request'].user
        validated_data['user'] = user
        tags = validated_data.pop('tags', [])
        # Remove campos puramente virtuais se sobrarem
        validated_data.pop('target_account_id', None) # source='_target...' might fail if popped manually above?
        # Actually without 'source', validated_data has 'target_account_id'. We pop it.
        
        t = super().create(validated_data)
        
        if tags:
            t.tags.set(tags)
        return t

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        target_account = validated_data.pop('target_account_id', None)
        
        # 1. Update Partner Account if requested
        if target_account and instance.transfer_id:
            partner = Transaction.objects.filter(
                transfer_id=instance.transfer_id
            ).exclude(id=instance.id).first()
            
            if partner:
                partner.account = target_account
                partner.save() # Dispara signal, mas sync_transfer_update ignora account change.
        
        # 2. Normal Update
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
