"""
Limpeza dos dados de um usuário pelo administrador (ADMIN-21 a ADMIN-26, AD-050).

`limpar_dados` deixa o usuário como um cadastro novo, tudo ou nada:

1. Remove do Cloudinary as imagens das metas; se uma remoção falhar, levanta
   `LimpezaFalhou` e nada é apagado (ADMIN-24), como na exclusão (LGPD-12).
2. Num `atomic`, trava a linha do usuário, de modo que uma segunda limpeza
   simultânea espera a primeira terminar (ADMIN-26).
3. Apaga cada modelo de `MODELOS_DO_USUARIO` que não está em
   `MANTIDOS_NA_LIMPEZA`, na ordem da lista (ADMIN-21).
4. Recria o padrão de um cadastro novo (ADMIN-22).
5. Grava o `CLEAR_DATA` no log de auditoria, na mesma transação: sem o
   registro, nada é apagado (ADMIN-08).

Uma exceção no meio desfaz a transação inteira (ADMIN-25). O `User`, com
login, senha, perfil, plano e papel, não está na lista e fica (ADMIN-23).
"""
from django.apps import apps
from django.db import transaction

from transactions.padrao import criar_padrao_do_cadastro

from .auditoria import Acoes, registrar
from .exclusao import MODELOS_DO_USUARIO, ExclusaoFalhou, _remover_do_cloudinary
from .models import User

# O que a limpeza mantém: as sessões, os tokens, o histórico dos termos e do
# consentimento e o log do admin do Django
MANTIDOS_NA_LIMPEZA = frozenset({
    'api.Sessao',
    'api.EmailVerificationToken',
    'api.PasswordResetToken',
    'api.AceiteDosTermos',
    'api.DecisaoDeConsentimento',
    'admin.LogEntry',
})


class LimpezaFalhou(Exception):
    """A remoção das imagens das metas falhou; nada foi apagado (ADMIN-24)."""


def modelos_da_limpeza():
    """Os modelos que a limpeza apaga, como `(modelo, campo)`, na ordem da lista."""
    return [
        (apps.get_model(rotulo), campo)
        for rotulo, campo in MODELOS_DO_USUARIO
        if rotulo not in MANTIDOS_NA_LIMPEZA
    ]


def limpar_dados(usuario, admin):
    """
    Apaga os dados do usuário, recria o padrão do cadastro e registra a
    limpeza feita por `admin`, tudo ou nada.
    """
    from goals.models import Goal

    try:
        _remover_do_cloudinary(usuario, incluir_avatar=False)
    except ExclusaoFalhou as erro:
        raise LimpezaFalhou('cloudinary') from erro

    with transaction.atomic():
        usuario = User.objects.select_for_update().get(pk=usuario.pk)
        # As imagens já saíram: o signal da meta não tenta de novo
        Goal.objects.filter(user_id=usuario.pk).update(image=None)
        for modelo, campo in modelos_da_limpeza():
            modelo.objects.filter(**{f'{campo}_id': usuario.pk}).delete()
        criar_padrao_do_cadastro(usuario)
        registrar(
            admin, Acoes.CLEAR_DATA, usuario,
            descricao='Todos os dados financeiros e configurações foram limpos pelo administrador.',
        )
