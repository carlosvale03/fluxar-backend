from rest_framework import serializers
from .models import Budget
from .services import BudgetService
from transactions.models import Category
from transactions.serializers import CategorySerializer
from core.fields import OwnedPrimaryKeyRelatedField, CATEGORIA_NAO_ENCONTRADA

class BudgetSerializer(serializers.ModelSerializer):
    # Só categorias do usuário da requisição (AD-032)
    category = OwnedPrimaryKeyRelatedField(
        queryset=Category.objects.all(), not_found_message=CATEGORIA_NAO_ENCONTRADA,
    )
    category_detail = CategorySerializer(source='category', read_only=True)
    total_spent = serializers.SerializerMethodField()
    percentage_used = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            'id', 'category', 'category_detail', 'month', 'year', 'amount_limit',
            'total_spent', 'percentage_used', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_spent', 'percentage_used', 'status']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Categoria de outro usuário, ou categoria-modelo, não aparece (ISOL-15)
        if instance.category.user_id != instance.user_id:
            ret['category'] = None
            ret['category_detail'] = None
        return ret

    def get_usage_data(self, obj):
        if not hasattr(obj, '_usage_data'):
            obj._usage_data = BudgetService.get_budget_usage(obj)
        return obj._usage_data

    def get_total_spent(self, obj):
        return self.get_usage_data(obj)['total_spent']

    def get_percentage_used(self, obj):
        return self.get_usage_data(obj)['percentage_used']

    def get_status(self, obj):
        return self.get_usage_data(obj)['status']

    def validate_category(self, value):
        # Validar se categoria é de despesa
        if value.type != 'EXPENSE':
            raise serializers.ValidationError("Orçamentos apenas para categorias de DESPESA.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        # Validação de unicidade já feita pelo Model/UniqueConstraint? 
        # DRF normalmente lida com unique_together, mas UniqueConstraint as vezes precisa de validador explicito no serializer.
        # Vamos deixar o DB estourar erro ou o DRF pegar (Validators.UniqueTogetherValidator não pega constraint nova do Django 2.2+ as vezes).
        # Mas como definimos no Meta, o ModelSerializer tenta validar.
        return super().create(validated_data)
