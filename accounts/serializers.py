from rest_framework import serializers
from .models import Account, CreditCard, CreditCardInvoice
from .services import AccountService, CreditCardService
from core.services.plan_limits import PlanLimitsService

class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    
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

    def get_balance(self, obj):
        return AccountService.get_balance(obj)

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class CreditCardInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditCardInvoice
        fields = ['id', 'month', 'year', 'status', 'total_amount', 'closing_date', 'due_date']


class CreditCardSerializer(serializers.ModelSerializer):
    available_limit = serializers.SerializerMethodField()
    current_invoice_total = serializers.SerializerMethodField()
    next_due_date = serializers.SerializerMethodField()
    
    class Meta:
        model = CreditCard
        fields = [
            'id', 'name', 'limit', 'closing_day', 'due_day',
            'institution', 'color',
            'available_limit', 'current_invoice_total', 'next_due_date',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'available_limit', 'current_invoice_total']

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
