"""
Rotas da gestão do salário, todas travadas pelo recurso `gestao_do_salario`
(SALARIO-16, PERM-15).
"""
from types import SimpleNamespace

from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.travas import RecursoLiberado
from core.valores import dinheiro

from . import plano
from .calculo import dividir
from .modelos import MODELOS, REGRA_DOS_MODELOS
from .serializers import PlanSerializer, SimulateSerializer, conferir_soma

PERMISSOES = [permissions.IsAuthenticated, RecursoLiberado('gestao_do_salario')]


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
        divisao = dividir(valor, partes)
        return Response({
            'amount': dinheiro(valor),
            'items': [plano.item_em_json(item) for item in divisao.itens],
            'total': dinheiro(divisao.total),
            'free': dinheiro(divisao.livre),
        })
