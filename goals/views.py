from rest_framework import viewsets, permissions, status, decorators
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Goal
from .serializers import GoalSerializer, GoalDepositSerializer
from .services import GoalService
from core.travas import RecursoLiberado, conferir_limite
from accounts.models import Account
from core.filtros import PAGINACAO, ParametrosConhecidosMixin
from core.pagination import PaginacaoPadrao
from core.mixins import UserQuerySetMixin
from core.fields import get_owned_or_400, CONTA_NAO_ENCONTRADA
from core.datas import hoje, ler_data
from core.valores import dinheiro, ler_valor
from .valores import saldo_livre

CAMPO_OBRIGATORIO = 'Este campo é obrigatório.'
META_COM_VALOR = 'Resgate o valor da meta antes de excluí-la.'
TROCA_COM_VALOR = 'Resgate o valor da meta antes de trocar o cofrinho.'


def _data_do_movimento(texto):
    """
    Data do aporte ou do resgate: `AAAA-MM-DD`, sem hora (CONTRATO-25); sem
    data, hoje em Brasília. Outro formato recebe 400 no campo `date`.
    """
    if texto in (None, ''):
        return hoje()
    return ler_data(texto, 'date')


def _verdadeiro(valor):
    """Booleano do corpo: `true` em JSON ou "true" em formulário."""
    return valor is True or (isinstance(valor, str) and valor.lower() == 'true')


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
    # Metas, aportes, resgates e histórico (PERM-15). O cofrinho é uma conta
    # comum: transferências e ajuste de saldo seguem liberados (PERM-22)
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('metas')]
    # Só o histórico é paginado (META-32, CONTRATO-14)
    parametros_por_acao = {'history': PAGINACAO}
    
    def perform_create(self, serializer):
        # O cofrinho criado com a meta não conta no limite de contas (PERM-16)
        conferir_limite(self.request.user, 'limite_metas')
        serializer.save()

    def perform_update(self, serializer):
        """Trocar o cofrinho só com a meta zerada (META-28)."""
        meta = serializer.instance
        novo = serializer.validated_data.get('account', meta.account)
        if novo != meta.account and meta.current_amount > 0:
            raise ValidationError({'detail': TROCA_COM_VALOR})
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """
        Exclui só a meta zerada (META-29). A resposta diz se o cofrinho ficou
        sem metas e com saldo zero, para a interface perguntar se exclui o
        cofrinho também (META-30).
        """
        goal = self.get_object()
        if goal.current_amount > 0:
            raise ValidationError({'detail': META_COM_VALOR})
        cofrinho = goal.account
        goal.delete()
        cofrinho_vazio = (
            cofrinho is not None and cofrinho.user_id == request.user.pk and cofrinho.is_active
            and not Goal.objects.filter(account=cofrinho).exists()
            and Account.objects.get(pk=cofrinho.pk).balance == 0
        )
        return Response({'piggy_bank_empty': cofrinho_vazio}, status=status.HTTP_200_OK)

    def get_queryset(self):
        # UserQuerySetMixin já filtra user=self.request.user
        return super().get_queryset()

    def _conta_do_movimento(self, request, campos, saldo_livre):
        """
        A conta de origem do aporte ou de destino do resgate, lida do primeiro
        campo preenchido de `campos`. Com o saldo livre (`saldo_livre`
        verdadeiro), não há conta (META-13, META-16). Erro no campo que a
        requisição usou, com a mensagem de ID inexistente (META-20, AD-010);
        só contas ativas (SALDO-35).
        """
        if saldo_livre:
            return None
        campo = next((c for c in campos if request.data.get(c)), campos[0])
        return get_owned_or_400(
            Account.objects.filter(is_active=True), request.user, request.data.get(campo), campo,
            CONTA_NAO_ENCONTRADA,
        )

    def _movimentar(self, request, operacao, campos, campo_do_saldo_livre):
        goal = self.get_object()
        amount = request.data.get('amount')
        saldo_livre = _verdadeiro(request.data.get(campo_do_saldo_livre))
        obrigatorios = {'amount': amount}
        if not saldo_livre:
            campo = next((c for c in campos if request.data.get(c)), campos[0])
            obrigatorios[campo] = request.data.get(campo)
        _exigir(obrigatorios)
        # Valor maior que zero, com até duas casas, com o erro no campo (META-19, SALDO-09)
        amount = ler_valor(amount)
        data = _data_do_movimento(request.data.get('date'))
        conta = self._conta_do_movimento(request, campos, saldo_livre)

        _mover(operacao, goal, amount, data, conta, request.data.get('description'))
        goal.refresh_from_db()
        return Response(self.get_serializer(goal).data, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        """Aporte de outra conta (`account_id` ou `account_from`) ou do saldo livre (`from_free_balance`)."""
        return self._movimentar(request, GoalService.aportar, ('account_id', 'account_from'), 'from_free_balance')

    @decorators.action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """Resgate para outra conta (`account_to` ou `account_id`) ou para o saldo livre (`to_free_balance`)."""
        return self._movimentar(request, GoalService.resgatar, ('account_to', 'account_id'), 'to_free_balance')

    @decorators.action(detail=False, methods=['get'], url_path='piggy-banks')
    def piggy_banks(self, request):
        """
        Um item por cofrinho com metas do usuário: saldo, soma das metas,
        inclusive as arquivadas, e saldo livre, que pode ser negativo
        (META-02, META-04).
        """
        cofrinhos = Account.objects.filter(
            user=request.user, type='PIGGY_BANK', goals__user=request.user,
        ).distinct().order_by('name', 'pk')
        itens = []
        for cofrinho in cofrinhos:
            livre = saldo_livre(cofrinho)
            itens.append({
                'account_id': cofrinho.pk,
                'name': cofrinho.name,
                'balance': dinheiro(cofrinho.balance),
                'goals_total': dinheiro(cofrinho.balance - livre),
                'free_balance': dinheiro(livre),
            })
        return Response(itens)

    @decorators.action(detail=True, methods=['post'], url_path='dismiss-correction')
    def dismiss_correction(self, request, pk=None):
        """O usuário viu o aviso da correção, que não aparece mais (META-11)."""
        goal = self.get_object()
        Goal.objects.filter(pk=goal.pk).update(valor_antes_da_correcao=None)
        goal.refresh_from_db()
        return Response(self.get_serializer(goal).data, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Histórico de aportes e resgates, paginado no formato de CONTRATO-02, do
        mais recente para o mais antigo (META-32). Só movimentos em contas do
        dono da meta (ISOL-15).
        """
        goal = self.get_object()
        deposits = (
            goal.deposits.filter(account__user_id=goal.user_id)
            .select_related('account').order_by('-date', '-created_at', '-pk')
        )
        paginacao = PaginacaoPadrao()
        pagina = paginacao.paginate_queryset(deposits, request, view=self)
        return paginacao.get_paginated_response(GoalDepositSerializer(pagina, many=True).data)
