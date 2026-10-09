"""
Exclusão definitiva de uma conta (LGPD-10 a LGPD-14, AD-018, AD-030).

`excluir_definitivamente` é o único caminho: a rotina diária e o painel admin
chamam a mesma função. Primeiro remove as imagens do Cloudinary; se alguma
remoção falhar, levanta `ExclusaoFalhou` e nada é apagado, e a conta continua
como estava (desativada e marcada, no caso da rotina). Depois, num `atomic`,
apaga tudo que pende do usuário e grava o `RegistroDeExclusao`.
"""
import logging

import cloudinary.uploader
from django.apps import apps
from django.db import transaction
from django.utils import timezone

from .models import RegistroDeExclusao, SystemLog, User

logger = logging.getLogger(__name__)

# Os registros que pendem do usuário e saem com ele, como `(modelo, campo)`.
# A ordem importa: `PagamentoDeFatura.conta` é PROTECT, então os pagamentos
# saem antes das contas. Os demais saem na cascata do usuário.
MODELOS_DO_USUARIO = (
    ('accounts.PagamentoDeFatura', 'user'),
    ('accounts.Account', 'user'),
    ('accounts.CreditCard', 'user'),
    ('transactions.Transaction', 'user'),
    ('transactions.RecurringTransaction', 'user'),
    ('transactions.Category', 'user'),
    ('transactions.Tag', 'user'),
    ('transactions.CorrecaoDeCategoria', 'user'),
    ('budgets.Budget', 'user'),
    ('reports.FocusedMonitorItem', 'user'),
    ('goals.Goal', 'user'),
    ('goals.ConfiguracaoDeTrocos', 'user'),
    ('goals.Troco', 'user'),
    ('api.Sessao', 'user'),
    ('api.EmailVerificationToken', 'user'),
    ('api.PasswordResetToken', 'user'),
    ('admin.LogEntry', 'user'),
)

# Referências ao usuário que não saem na cascata: o log de auditoria é
# tratado à parte (AD-030), e a trava de plano só guarda quem a mudou por
# último, solta com SET_NULL.
EXCECOES = (
    ('api.SystemLog', 'user'),
    ('api.TravaDePlano', 'atualizada_por'),
)

# `admin_name` dos registros que não são ações de administrador
SISTEMA = 'Sistema'


class ExclusaoFalhou(Exception):
    """Uma etapa da exclusão definitiva falhou; nada foi apagado (LGPD-12)."""


def _public_ids(usuario):
    """O avatar e as imagens das metas do usuário no Cloudinary."""
    from goals.models import Goal

    ids = []
    if usuario.avatar:
        ids.append(usuario.avatar.public_id)
    for meta in Goal.objects.filter(user=usuario):
        if meta.image:
            ids.append(meta.image.public_id)
    return [public_id for public_id in ids if public_id]


def _remover_do_cloudinary(usuario):
    for public_id in _public_ids(usuario):
        try:
            resultado = cloudinary.uploader.destroy(public_id)
        except Exception as erro:
            # Só a classe do erro e o id interno (LGPD-21)
            logger.error("Falha ao remover imagem do Cloudinary usuario=%s (%s).", usuario.pk, type(erro).__name__)
            raise ExclusaoFalhou('cloudinary') from erro
        # "not found" vale: a imagem já saiu numa tentativa anterior
        if not isinstance(resultado, dict) or resultado.get('result') not in ('ok', 'not found'):
            logger.error("Cloudinary recusou a remoção de imagem usuario=%s.", usuario.pk)
            raise ExclusaoFalhou('cloudinary')


def excluir_definitivamente(usuario, executor):
    """
    Apaga a conta e todos os dados dela e guarda só o registro da exclusão
    (LGPD-10, LGPD-11). `executor` é `RegistroDeExclusao.ROTINA`, `ADMIN` ou
    `USUARIO`. Levanta `ExclusaoFalhou` sem apagar nada se o Cloudinary falhar
    (LGPD-12). Depois dela, o e-mail fica livre para um novo cadastro (LGPD-14).
    """
    from accounts.models import PagamentoDeFatura
    from goals.models import Goal

    _remover_do_cloudinary(usuario)

    usuario_id = usuario.pk
    pedida_em = usuario.exclusao_pedida_em
    with transaction.atomic():
        # As imagens já saíram: o signal da meta não tenta de novo
        Goal.objects.filter(user_id=usuario_id).update(image=None)
        PagamentoDeFatura.objects.filter(user_id=usuario_id).delete()
        logs = SystemLog.objects.filter(user_id=usuario_id)
        # Os registros de ações de administrador ficam só com o id interno (AD-030)
        logs.exclude(admin_name=SISTEMA).update(user=None, usuario_ref=usuario_id)
        logs.filter(admin_name=SISTEMA).delete()
        SystemLog.objects.filter(usuario_ref=usuario_id, user__isnull=True, admin_name=SISTEMA).delete()
        User.objects.get(pk=usuario_id).delete()
        RegistroDeExclusao.objects.get_or_create(
            usuario_id=usuario_id,
            defaults={'pedida_em': pedida_em, 'excluida_em': timezone.now(), 'executada_por': executor},
        )


def excluir_contas_vencidas():
    """
    A rotina diária (AD-048): apaga, uma a uma, as contas desativadas com a
    exclusão marcada para agora ou antes (LGPD-10). Cada conta é
    independente: a que falhar fica desativada e marcada para a próxima
    execução, e as outras seguem (LGPD-12). Devolve `(excluidas, falhas)`.
    """
    vencidas = list(
        User.objects.filter(is_active=False, exclusao_agendada_para__lte=timezone.now())
        .order_by('exclusao_agendada_para')
        .values_list('pk', flat=True)
    )
    excluidas = falhas = 0
    for usuario_id in vencidas:
        usuario = User.objects.filter(pk=usuario_id).first()
        if usuario is None:
            continue
        try:
            excluir_definitivamente(usuario, RegistroDeExclusao.ROTINA)
        except Exception as erro:
            # Só a classe do erro e o id interno (LGPD-21)
            logger.error("Exclusão definitiva adiada usuario=%s (%s).", usuario_id, type(erro).__name__)
            falhas += 1
        else:
            excluidas += 1
    return excluidas, falhas


def modelos_do_usuario():
    """Os modelos de `MODELOS_DO_USUARIO`, resolvidos."""
    return [(apps.get_model(rotulo), campo) for rotulo, campo in MODELOS_DO_USUARIO]
