from rest_framework import serializers
from .models import Goal, GoalDeposit
from .services import GoalService

class GoalDepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalDeposit
        fields = ['id', 'amount', 'date', 'account', 'created_at']
        read_only_fields = ['id', 'created_at']

class GoalSerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()
    deposits = GoalDepositSerializer(many=True, read_only=True)
    
    class Meta:
        model = Goal
        fields = [
            'id', 'name', 'target_amount', 'current_amount', 
            'target_date', 'is_active', 'progress', 'deposits',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_amount', 'created_at', 'updated_at', 'deposits']

    def get_progress(self, obj):
        return GoalService.get_progress(obj)
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
