from rest_framework import serializers
from .models import FocusedMonitorItem
from transactions.models import Category, Tag
from core.fields import OwnedPrimaryKeyRelatedField, CATEGORIA_NAO_ENCONTRADA, TAG_NAO_ENCONTRADA

class FocusedMonitorItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True)

    # Só categorias e tags do usuário da requisição (AD-032)
    category = OwnedPrimaryKeyRelatedField(
        queryset=Category.objects.all(), not_found_message=CATEGORIA_NAO_ENCONTRADA,
        required=False, allow_null=True,
    )
    tag = OwnedPrimaryKeyRelatedField(
        queryset=Tag.objects.all(), not_found_message=TAG_NAO_ENCONTRADA,
        required=False, allow_null=True,
    )
    
    class Meta:
        model = FocusedMonitorItem
        fields = ['id', 'category', 'tag', 'category_name', 'tag_name', 'created_at']
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Categoria ou tag de outro usuário não aparece no monitor (ISOL-15)
        if instance.category_id and instance.category.user_id != instance.user_id:
            ret['category'] = None
            ret['category_name'] = None
        if instance.tag_id and instance.tag.user_id != instance.user_id:
            ret['tag'] = None
            ret['tag_name'] = None
        return ret

    def validate(self, data):
        category = data.get('category')
        tag = data.get('tag')
        
        if not category and not tag:
            raise serializers.ValidationError("É necessário selecionar uma Categoria ou uma Tag.")
            
        if category and tag:
            raise serializers.ValidationError("Selecione apenas um: Categoria OU Tag.")
            
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
