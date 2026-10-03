"""
Parâmetros conhecidos de cada rota GET (CONTRATO-14, AD-022).

Um parâmetro que a rota não conhece recebe HTTP 400, em vez de ser ignorado
em silêncio e devolver dados errados à tela.
"""
from rest_framework.exceptions import ValidationError

FILTRO_DESCONHECIDO = 'Filtro desconhecido: {nome}.'

# Parâmetros das listas paginadas (core/pagination.py)
PAGINACAO = frozenset({'page', 'page_size'})


def conferir_parametros(request, permitidos):
    """
    Recusa com 400 o primeiro parâmetro fora de `permitidos`, em ordem
    alfabética, para a mensagem ser sempre a mesma.
    """
    desconhecidos = sorted(set(request.query_params) - set(permitidos))
    if desconhecidos:
        raise ValidationError({'detail': FILTRO_DESCONHECIDO.format(nome=desconhecidos[0])})


class ParametrosConhecidosMixin:
    """
    Confere os parâmetros das requisições GET, depois da autenticação e das
    permissões.

    `parametros_permitidos` vale para a lista de um ViewSet ou para a rota
    inteira de uma APIView; `parametros_por_acao` vale para as ações GET de um
    ViewSet. O detalhe e as ações que não estão no dicionário não aceitam
    nenhum parâmetro.
    """
    parametros_permitidos = frozenset()
    parametros_por_acao = {}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method == 'GET':
            conferir_parametros(request, self.parametros_da_rota())

    def parametros_da_rota(self):
        acao = getattr(self, 'action', None)
        if acao is None or acao == 'list':
            return self.parametros_permitidos
        return self.parametros_por_acao.get(acao, frozenset())
