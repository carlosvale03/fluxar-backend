from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """
    Mantém o 404 com a mensagem padrão do DRF ("Not found.").

    A partir do DRF 3.15, o Http404 leva a mensagem do Django, que muda
    conforme o modelo e o formato do ID. Um ID de outro usuário e um ID
    inexistente precisam receber a mesma resposta (ISOL-12).
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    return drf_exception_handler(exc, context)
