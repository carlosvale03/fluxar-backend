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
    category_detail = CategorySerializer(source='category', read_only=True)
    tags_detail = TagSerializer(source='tags', many=True, read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'description', 'amount', 'date',
            'account', 'credit_card', 'invoice', 
            'category', 'category_detail',
            'tags', 'tags_detail',
            'is_installment', 'installment_number', 'installment_total',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice', 'is_installment', 'installment_number', 'installment_total',
            'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        # Criação simples (Receita/Despesa padrão)
        # Para logicas complexas use as actions da ViewSet
        user = self.context['request'].user
        validated_data['user'] = user
        tags = validated_data.pop('tags', [])
        
        t = super().create(validated_data)
        
        if tags:
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
