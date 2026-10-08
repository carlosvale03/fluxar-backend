from rest_framework import serializers
from .models import Goal, GoalDeposit
from .services import GoalService
from accounts.models import Account
from core.fields import OwnedPrimaryKeyRelatedField, CONTA_NAO_ENCONTRADA
from core.valores import dinheiro, validar_valor_positivo

class GoalDepositSerializer(serializers.ModelSerializer):
    account_name = serializers.ReadOnlyField(source='account.name')
    datetime = serializers.ReadOnlyField(source='date')
    
    # O `transfer_id` da transferência, ou nulo sem transferência (META-32)
    transaction = serializers.ReadOnlyField(source='transaction_id')
    is_correction = serializers.ReadOnlyField(source='eh_correcao')

    class Meta:
        model = GoalDeposit
        fields = [
            'id', 'amount', 'type', 'description', 'date', 'datetime', 'account', 'account_name',
            'transaction', 'is_correction', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

class GoalSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()
    current_amount = serializers.SerializerMethodField()
    amount_remaining = serializers.SerializerMethodField()
    suggested_monthly_saving = serializers.SerializerMethodField()
    months_remaining = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    correction = serializers.SerializerMethodField()

    # Só cofrinhos ativos do usuário da requisição (META-26, AD-032); sem
    # cofrinho, a meta ganha um novo (META-25)
    account = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(type='PIGGY_BANK', is_active=True), not_found_message=CONTA_NAO_ENCONTRADA,
        required=False, allow_null=True,
    )
    
    # Campos auxiliares para criação de cofrinho customizado
    cofrinho_name = serializers.CharField(write_only=True, required=False)
    institution = serializers.CharField(write_only=True, required=False)
    color = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Goal
        fields = [
            'id', 'name', 'description', 'target_amount', 'current_amount', 
            'account', 'target_date', 'image', 'is_active', 'status',
            'progress_percentage', 'amount_remaining', 
            'suggested_monthly_saving', 'months_remaining',
            'correction', 'created_at', 'updated_at',
            'cofrinho_name', 'institution', 'color'
        ]
        read_only_fields = ['id', 'current_amount', 'created_at', 'updated_at']
        # Alvo de pelo menos R$ 0,01 (META-27)
        extra_kwargs = {'target_amount': {'validators': [validar_valor_positivo]}}

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Conta de outro usuário não aparece na meta (ISOL-15)
        if instance.account_id and instance.account.user_id != instance.user_id:
            ret['account'] = None
        # Força o campo image a retornar a URL absoluta da CDN
        if instance.image:
            request = self.context.get('request')
            if request:
                ret['image'] = request.build_absolute_uri(instance.image.url)
            else:
                ret['image'] = instance.image.url
        return ret

    def get_correction(self, obj):
        """
        Aviso único da correção do recálculo (META-11): o valor de antes e o de
        depois, até o usuário confirmar em `dismiss-correction`.
        """
        if obj.valor_antes_da_correcao is None:
            return None
        return {'before': dinheiro(obj.valor_antes_da_correcao), 'after': dinheiro(0)}

    def _get_prog(self, obj):
        if not hasattr(self, '_prog_cache'):
            self._prog_cache = {}
        if obj.id not in self._prog_cache:
            self._prog_cache[obj.id] = GoalService.get_progress(obj)
        return self._prog_cache[obj.id]

    def get_progress_percentage(self, obj):
        return self._get_prog(obj)['percentage']

    def get_current_amount(self, obj):
        # Sobrescreve o campo current_amount do model com o valor real do cofrinho,
        # como texto (CONTRATO-16)
        return dinheiro(self._get_prog(obj)['current_amount'])

    def get_amount_remaining(self, obj):
        return dinheiro(self._get_prog(obj)['remaining'])

    def get_suggested_monthly_saving(self, obj):
        return dinheiro(self._get_prog(obj)['monthly_suggestion'])

    def get_months_remaining(self, obj):
        return self._get_prog(obj)['months_remaining']

    def get_status(self, obj):
        prog = self._get_prog(obj)
        if prog['current_amount'] >= obj.target_amount:
            return 'COMPLETED'
        if not obj.is_active:
            return 'ARCHIVED'
        return 'IN_PROGRESS'
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        validated_data['user'] = user

        # Se não houver conta vinculada, cria um Cofrinho automático
        if 'account' not in validated_data or not validated_data['account']:
            from accounts.models import Account
            from decimal import Decimal
            
            c_name = validated_data.pop('cofrinho_name', f"Cofrinho: {validated_data['name']}")
            c_inst = validated_data.pop('institution', 'fluxar')
            c_color = validated_data.pop('color', '#10b981')

            piggy_bank = Account.objects.create(
                user=user,
                name=c_name,
                type='PIGGY_BANK',
                institution=c_inst,
                color=c_color,
                initial_balance=Decimal('0.00')
            )
            validated_data['account'] = piggy_bank
        else:
            # Limpa campos extras se uma conta existente foi passada
            validated_data.pop('cofrinho_name', None)
            validated_data.pop('institution', None)
            validated_data.pop('color', None)

        return super().create(validated_data)
