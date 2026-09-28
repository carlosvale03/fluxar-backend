import math

from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """
    Ajusta duas respostas do DRF.

    O 404 fica sempre com a mensagem única "Não encontrado.". A partir do DRF
    3.15, o Http404 leva a mensagem do Django, que muda conforme o modelo e o
    formato do ID, e um ID de outro usuário e um ID inexistente precisam
    receber a mesma resposta (ISOL-12).

    O 429 diz em quantos minutos tentar de novo (AUTH-36). O cabeçalho
    Retry-After, em segundos, continua vindo do DRF.
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    response = drf_exception_handler(exc, context)
    if isinstance(exc, exceptions.Throttled) and response is not None:
        minutos = max(1, math.ceil((exc.wait or 0) / 60))
        response.data = {"detail": f"Muitas tentativas. Tente novamente em {minutos} minutos."}
    return response
