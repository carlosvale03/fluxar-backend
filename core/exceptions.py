import math

from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """
    Ajusta duas respostas do DRF e acrescenta `code` às que têm `detail`.

    O 404 fica sempre com a mensagem única "Não encontrado.". A partir do DRF
    3.15, o Http404 leva a mensagem do Django, que muda conforme o modelo e o
    formato do ID, e um ID de outro usuário e um ID inexistente precisam
    receber a mesma resposta (ISOL-12).

    O 429 diz em quantos minutos tentar de novo (AUTH-36). O cabeçalho
    Retry-After, em segundos, continua vindo do DRF.

    As travas dos planos respondem `{detail, code, feature[, limit]}`, com os
    `extras` da exceção (PERM-15, PERM-16).
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    response = drf_exception_handler(exc, context)
    if isinstance(exc, exceptions.Throttled) and response is not None:
        minutos = max(1, math.ceil((exc.wait or 0) / 60))
        unidade = "minuto" if minutos == 1 else "minutos"
        response.data = {"detail": f"Muitas tentativas. Tente novamente em {minutos} {unidade}."}
    if response is not None:
        _acrescentar_codigo(exc, response)
        # As travas dos planos levam a chave e, no limite, o valor (PERM-15, PERM-16)
        extras = getattr(exc, 'extras', None)
        if extras and isinstance(response.data, dict):
            response.data.update(extras)
    return response


def _acrescentar_codigo(exc, response):
    """
    Um erro que não é de campo leva `detail` e `code`, com o código do DRF,
    como `not_found` ou `invalid` (CONTRATO-29, CONTRATO-31).
    """
    if not isinstance(response.data, dict) or 'detail' not in response.data or 'code' in response.data:
        return
    codigos = exc.get_codes() if isinstance(exc, exceptions.APIException) else None
    if isinstance(codigos, dict):
        codigos = codigos.get('detail')
    if isinstance(codigos, list):
        codigos = codigos[0] if codigos else None
    if isinstance(codigos, str):
        response.data['code'] = codigos
