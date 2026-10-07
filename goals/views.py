from rest_framework import viewsets, permissions, status, decorators
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Goal
from .serializers import GoalSerializer, GoalDepositSerializer
from .services import GoalService
from core.permissions import IsPremiumPlus
from accounts.models import Account
from core.filtros import ParametrosConhecidosMixin
from core.mixins import UserQuerySetMixin
from core.fields import get_owned_or_400, CONTA_NAO_ENCONTRADA
from core.datas import hoje, ler_data
from core.valores import ler_valor

CAMPO_OBRIGATORIO = 'Este campo é obrigatório.'
META_COM_SALDO = 'Não é possível excluir uma meta com saldo pendente. Resgate o dinheiro primeiro para zerar a meta.'


def _data_do_movimento(texto):
    """
    Data do aporte ou do resgate: `AAAA-MM-DD`, sem hora (CONTRATO-25); sem
    data, hoje em Brasília. Outro formato recebe 400 no campo `date`.
    """
    if texto in (None, ''):
        return hoje()
    return ler_data(texto, 'date')


def _exigir(campos):
    """Erro de campo obrigatório em cada campo vazio (CONTRATO-30)."""
    erros = {campo: [CAMPO_OBRIGATORIO] for campo, valor in campos.items() if valor in (None, '')}
    if erros:
        raise ValidationError(erros)


def _mover(operacao, *args):
    """
    Recusas do service viram 400 com `detail` em português; erro inesperado
    sobe e vira 500, sem o texto da exceção (CONTRATO-29).
    """
    try:
        operacao(*args)
    except DjangoValidationError as erro:
        raise ValidationError({'detail': erro.messages[0]})


class GoalViewSet(ParametrosConhecidosMixin, UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer
    # Permissão: IsAuthenticated E IsPremiumPlus
    permission_classes = [permissions.IsAuthenticated, IsPremiumPlus]
    
    def destroy(self, request, *args, **kwargs):
        """Bloqueia a exclusão se a meta ainda tiver saldo."""
        goal = self.get_object()
        if goal.current_amount != 0:
            raise ValidationError({'detail': META_COM_SALDO})
        return super().destroy(request, *args, **kwargs)
    
    def get_queryset(self):
        # UserQuerySetMixin já filtra user=self.request.user
        return super().get_queryset()

    @decorators.action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        goal = self.get_object()
        
        # Validar dados de entrada manualmente ou usar serializer simples
        amount = request.data.get('amount')
        account_id = request.data.get('account_id') or request.data.get('account_from')
        
        _exigir({'amount': amount, 'account_id': account_id})
        # Valor maior que zero, com até duas casas, com o erro no campo (SALDO-09)
        amount = ler_valor(amount)
        date_deposit = _data_do_movimento(request.data.get('date'))
            
        # Erro no campo que a requisição usou (AD-010); só contas ativas (SALDO-35)
        account_field = 'account_id' if request.data.get('account_id') else 'account_from'
        account = get_owned_or_400(
            Account.objects.filter(is_active=True), request.user, account_id, account_field, CONTA_NAO_ENCONTRADA,
        )
        
        _mover(GoalService.deposit, goal, account, amount, date_deposit, request.data.get('description'))
        # Retornar a meta atualizada
        return Response(self.get_serializer(goal).data, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        goal = self.get_object()
        
        amount = request.data.get('amount')
        # account_to é para onde o dinheiro sai do cofrinho
        account_id = request.data.get('account_to') or request.data.get('account_id')
        
        _exigir({'amount': amount, 'account_to': account_id})
        # Valor maior que zero, com até duas casas, com o erro no campo (SALDO-09)
        amount = ler_valor(amount)
        date_withdrawal = _data_do_movimento(request.data.get('date'))
            
        # Erro no campo que a requisição usou (AD-010); só contas ativas (SALDO-35)
        account_field = 'account_to' if request.data.get('account_to') else 'account_id'
        account_to = get_owned_or_400(
            Account.objects.filter(is_active=True), request.user, account_id, account_field, CONTA_NAO_ENCONTRADA,
        )
        
        _mover(GoalService.withdraw, goal, account_to, amount, date_withdrawal, request.data.get('description'))
        return Response(self.get_serializer(goal).data, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        goal = self.get_object()
        # Só movimentos em contas do dono da meta, como em GoalSerializer.deposits (ISOL-15)
        deposits = goal.deposits.filter(account__user_id=goal.user_id).order_by('-created_at')
        serializer = GoalDepositSerializer(deposits, many=True)
        return Response(serializer.data)
