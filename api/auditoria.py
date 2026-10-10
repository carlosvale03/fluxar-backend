"""
Log de auditoria das ações de administrador (ADMIN-08 a ADMIN-11, AD-030, AD-049).

`registrar` é o único caminho para gravar uma ação de administrador: guarda
quem fez e sobre quem pelo id interno e pelo e-mail mascarado (AD-019), a
ação numa constante de `Acoes` e os valores de antes e de depois em JSON.
A descrição é um texto curto, sem nome nem e-mail.
"""
from .models import SystemLog
from .utils.email_service import _mask_email

# `admin_name` dos registros que não são ações de administrador
SISTEMA = 'Sistema'


class Acoes:
    CHANGE_PLAN = 'CHANGE_PLAN'
    CHANGE_ROLE = 'CHANGE_ROLE'
    CHANGE_STATUS = 'CHANGE_STATUS'
    RESET_PASSWORD = 'RESET_PASSWORD'
    CLEAR_DATA = 'CLEAR_DATA'
    DELETE_ACCOUNT = 'DELETE_ACCOUNT'
    UPDATE_MAINTENANCE = 'UPDATE_MAINTENANCE'
    UPDATE_TESTING_UNLOCK = 'UPDATE_TESTING_UNLOCK'
    UPDATE_PLAN_LOCK = 'UPDATE_PLAN_LOCK'
    UPDATE_PLAN_LIMIT = 'UPDATE_PLAN_LIMIT'
    # Configuração global fora das conhecidas
    UPDATE_SETTING = 'UPDATE_SETTING'

    TODAS = (
        CHANGE_PLAN, CHANGE_ROLE, CHANGE_STATUS, RESET_PASSWORD, CLEAR_DATA, DELETE_ACCOUNT,
        UPDATE_MAINTENANCE, UPDATE_TESTING_UNLOCK, UPDATE_PLAN_LOCK, UPDATE_PLAN_LIMIT, UPDATE_SETTING,
    )


def registrar(admin, acao, usuario=None, antes=None, depois=None, descricao=''):
    """
    Grava uma ação de administrador. `admin` é quem fez (None para o sistema),
    `usuario` é o afetado, quando houver. Devolve o registro.
    """
    return SystemLog.objects.create(
        user=usuario,
        usuario_ref=usuario.pk if usuario is not None else None,
        usuario_email=_mask_email(usuario.email) if usuario is not None else '',
        admin_ref=admin.pk if admin is not None else None,
        admin_name=_mask_email(admin.email) if admin is not None else SISTEMA,
        action=acao,
        antes=antes,
        depois=depois,
        description=descricao,
    )
