"""
Rotas da gestão do salário, todas travadas pelo recurso `gestao_do_salario`
(SALARIO-16, PERM-15).
"""
import uuid
from types import SimpleNamespace

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.filtros import ParametrosConhecidosMixin
from core.travas import RecursoLiberado
from core.valores import dinheiro

from . import divisao, plano
from .calculo import dividir
from .models import DivisaoDoSalario
from .modelos import MODELOS, REGRA_DOS_MODELOS
from .referencias import referencias
from .serializers import (
    DivisionCreateSerializer, DivisionPreviewSerializer, PlanSerializer, SimulateSerializer, conferir_soma,
)

PERMISSOES = [permissions.IsAuthenticated, RecursoLiberado('gestao_do_salario')]
SO_DESFAZIVEIS = 'Use undoable=true: só as divisões que ainda podem ser desfeitas são listadas.'


def validar(classe, request):
    """
    Valida `request.data` com o serializer e devolve os dados validados. Os
    erros das partes vêm na posição de cada parte, com `{}` nas partes sem
    erro: `{"parts": [{}, {"value": [...]}]}`.
    """
    serializer = classe(data=request.data, context={'request': request})
    if serializer.is_valid():
        return serializer.validated_data
    erros = dict(serializer.errors)
    partes = erros.get('parts')
    if isinstance(partes, dict):
        enviadas = request.data.get('parts') if hasattr(request.data, 'get') else None
        tamanho = len(enviadas) if isinstance(enviadas, list) else max(partes) + 1
        erros['parts'] = [partes.get(posicao, {}) for posicao in range(tamanho)]
    raise ValidationError(erros)


def parte_da_requisicao(dados):
    """Uma parte validada pelo `PlanPartSerializer`, no formato que `dividir` lê."""
    conta, meta = dados.get('account'), dados.get('goal')
    return SimpleNamespace(
        id=None, nome=dados['name'], tipo_de_regra=dados['rule_type'], valor=dados['value'],
        tipo_de_destino=dados.get('destination_type'), conta=conta, meta=meta,
        conta_id=conta.pk if conta is not None else None, meta_id=meta.pk if meta is not None else None,
    )


class SalaryModelsView(APIView):
    """`GET /salary/models/`: os modelos com a obra de origem e as partes (SALARIO-01, SALARIO-02)."""
    permission_classes = PERMISSOES

    def get(self, request):
        return Response([
            {
                'code': modelo.codigo,
                'name': modelo.nome,
                'author': modelo.autor,
                'book': modelo.obra,
                'parts': [
                    {
                        'name': parte.nome,
                        'rule_type': REGRA_DOS_MODELOS,
                        'value': dinheiro(parte.percentual),
                        'destination_type': parte.tipo_de_destino,
                        'reference': parte.referencia,
                    }
                    for parte in modelo.partes
                ],
            }
            for modelo in MODELOS
        ])


class SalaryPlanView(APIView):
    """`GET` e `PUT /salary/plan/`: o plano único do usuário (SALARIO-04 a SALARIO-12, SALARIO-14)."""
    permission_classes = PERMISSOES

    def get(self, request):
        return Response(plano.plano_em_json(request.user))

    def put(self, request):
        dados = validar(PlanSerializer, request)
        conferir_soma(dados['parts'])
        plano.salvar_plano(request.user, dados['parts'], dados.get('salary_categories'))
        return Response(plano.plano_em_json(request.user))


class SalarySimulateView(APIView):
    """
    `POST /salary/simulate/`: a divisão de um valor pelas partes enviadas ou
    pelo plano salvo, sem gravar nada (SALARIO-13).
    """
    permission_classes = PERMISSOES

    def post(self, request):
        dados = validar(SimulateSerializer, request)
        valor = dados['amount']
        if 'parts' in dados:
            conferir_soma(dados['parts'])
            partes = [parte_da_requisicao(p) for p in dados['parts']]
        else:
            partes = plano.partes_do_plano(request.user)
        resultado = dividir(valor, partes)
        return Response({
            'amount': dinheiro(valor),
            'items': [plano.item_em_json(item) for item in resultado.itens],
            'total': dinheiro(resultado.total),
            'free': dinheiro(resultado.livre),
        })


class SalaryPendingView(APIView):
    """`GET /salary/pending/`: os salários do mês atual e do anterior ainda não divididos (SALARIO-24)."""
    permission_classes = PERMISSOES

    def get(self, request):
        return Response([divisao.recebimento_em_json(t) for t in divisao.pendentes(request.user)])


class SalaryDivisionPreviewView(APIView):
    """`POST /salary/divisions/preview/`: a revisão da divisão, sem gravar nada (SALARIO-29, SALARIO-30)."""
    permission_classes = PERMISSOES

    def post(self, request):
        dados = validar(DivisionPreviewSerializer, request)
        return Response(divisao.revisar(request.user, dados['receipt'], dados['adjustments']))


class SalaryDivisionsView(ParametrosConhecidosMixin, APIView):
    """
    `GET /salary/divisions/?undoable=true`: as divisões que ainda podem ser
    desfeitas, da mais recente para a mais antiga, para a tela oferecer o
    desfazer depois de fechado o resultado (SALARIO-45, SALARIO-49). O
    parâmetro é obrigatório: a rota não lista as demais divisões.

    `POST /salary/divisions/`: gera as transações da divisão de uma vez
    (SALARIO-32 a SALARIO-43). A repetição da mesma `idempotency_key`
    devolve a divisão já gravada, também com 201 (SALARIO-37).
    """
    permission_classes = PERMISSOES
    parametros_permitidos = frozenset({'undoable'})

    def get(self, request):
        if request.query_params.get('undoable') != 'true':
            raise ValidationError({'undoable': [SO_DESFAZIVEIS]})
        return Response([divisao.divisao_em_json(registro) for registro in divisao.desfaziveis(request.user)])

    def post(self, request):
        # A repetição responde antes da validação: o recebimento pode ter
        # sido excluído depois da primeira resposta
        chave = request.data.get('idempotency_key') if hasattr(request.data, 'get') else None
        try:
            chave = uuid.UUID(str(chave)) if chave not in (None, '') else None
        except ValueError:
            chave = None
        if chave is not None:
            anterior = DivisaoDoSalario.objects.filter(user=request.user, chave=chave).first()
            if anterior is not None and str(anterior.recebimento_ref) == str(request.data.get('receipt')):
                return Response(divisao.divisao_em_json(anterior), status=status.HTTP_201_CREATED)

        dados = validar(DivisionCreateSerializer, request)
        registro, _ = divisao.gerar(
            request.user, dados['receipt'].pk, dados['idempotency_key'], dados['adjustments'],
        )
        return Response(divisao.divisao_em_json(registro), status=status.HTTP_201_CREATED)


class SalaryDivisionDetailView(APIView):
    """`GET /salary/divisions/<id>/`: a divisão com as transações geradas (SALARIO-44, SALARIO-45)."""
    permission_classes = PERMISSOES

    def get(self, request, pk):
        registro = get_object_or_404(DivisaoDoSalario, pk=pk, user=request.user)
        return Response(divisao.divisao_em_json(registro))


class SalaryReferencesView(APIView):
    """`GET /salary/references/`: o comprometido no mês e as médias do histórico (SALARIO-52, SALARIO-53, SALARIO-56)."""
    permission_classes = PERMISSOES

    def get(self, request):
        return Response(referencias(request.user))


class SalaryDivisionUndoView(APIView):
    """`POST /salary/divisions/<id>/undo/`: desfaz a divisão inteira em até 7 dias (SALARIO-46 a SALARIO-51)."""
    permission_classes = PERMISSOES

    def post(self, request, pk):
        registro = divisao.desfazer(request.user, pk)
        return Response(divisao.divisao_em_json(registro))
