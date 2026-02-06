from rest_framework import serializers
from .models import FocusedMonitorItem
from transactions.models import Category, Tag

class FocusedMonitorItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True)
    
    class Meta:
        model = FocusedMonitorItem
        fields = ['id', 'category', 'tag', 'category_name', 'tag_name', 'created_at']
        read_only_fields = ['id', 'created_at']

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
