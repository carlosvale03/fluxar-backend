"""
Sessões de login (AD-037).

Cada login cria uma linha em `Sessao`, e os dois tokens levam o `id` dela no
claim `sid`. A renovação é rotativa: a sessão guarda o `jti` do único token de
renovação que ainda vale, e um token já usado é recusado (SESSAO-08, SESSAO-09).
"""
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Sessao


class SessaoInvalida(Exception):
    """Token de renovação recusado: vencido, já usado, sem sessão aberta ou de conta inativa."""


def adicionar_claims(token, user):
    """Dados do usuário no token, para o front não precisar consultar /me logo de cara."""
    token['name'] = user.name
    token['email'] = user.email
    token['plan'] = user.plan
    token['role'] = user.role
    return token


def _emitir(user, sessao):
    """Token de renovação novo, com validade e jti novos, para a sessão."""
    refresh = adicionar_claims(RefreshToken.for_user(user), user)
    refresh['sid'] = str(sessao.id)
    return refresh


def _uuid(valor):
    try:
        return uuid.UUID(str(valor))
    except (TypeError, ValueError):
        return None


def criar_sessao(user):
    """Abre uma sessão e devolve (access, refresh)."""
    sessao = Sessao(
        user=user,
        expira_em=timezone.now() + jwt_settings.REFRESH_TOKEN_LIFETIME,
    )
    refresh = _emitir(user, sessao)
    sessao.refresh_jti = refresh[jwt_settings.JTI_CLAIM]
    sessao.save()
    return str(refresh.access_token), str(refresh)


def renovar(refresh_str):
    """
    Troca o token de renovação por um novo e devolve (access, refresh).
    Levanta `SessaoInvalida` em qualquer recusa.
    """
    try:
        antigo = RefreshToken(refresh_str)
    except TokenError as erro:
        raise SessaoInvalida() from erro

    sid = _uuid(antigo.get('sid'))
    if sid is None:
        raise SessaoInvalida()

    with transaction.atomic():
        sessao = Sessao.objects.select_for_update().filter(pk=sid).first()
        agora = timezone.now()
        if (
            sessao is None
            or sessao.encerrada_em is not None
            or sessao.expira_em <= agora
            or sessao.refresh_jti != antigo.get(jwt_settings.JTI_CLAIM)
            or str(sessao.user_id) != str(antigo.get(jwt_settings.USER_ID_CLAIM))
        ):
            raise SessaoInvalida()
        user = sessao.user
        if not user.is_active:
            raise SessaoInvalida()

        novo = _emitir(user, sessao)
        sessao.refresh_jti = novo[jwt_settings.JTI_CLAIM]
        sessao.ultimo_uso = agora
        sessao.expira_em = agora + jwt_settings.REFRESH_TOKEN_LIFETIME
        sessao.save(update_fields=['refresh_jti', 'ultimo_uso', 'expira_em'])

    return str(novo.access_token), str(novo)


def _abertas():
    return Sessao.objects.filter(encerrada_em__isnull=True)


def encerrar(sid):
    """Encerra uma sessão (logout)."""
    sid = _uuid(sid)
    if sid is not None:
        _abertas().filter(pk=sid).update(encerrada_em=timezone.now())


def encerrar_outras(user, sid_atual):
    """Encerra as sessões do usuário, menos a atual (troca de senha, SESSAO-15)."""
    _abertas().filter(user=user).exclude(pk=_uuid(sid_atual)).update(encerrada_em=timezone.now())


def encerrar_todas(user):
    """Encerra todas as sessões do usuário (redefinição e desativação, SESSAO-16 e SESSAO-17)."""
    _abertas().filter(user=user).update(encerrada_em=timezone.now())


def sessao_aberta(sid, user_id):
    """A sessão existe, é do usuário, não foi encerrada e não venceu."""
    sid = _uuid(sid)
    if sid is None:
        return False
    return _abertas().filter(pk=sid, user_id=user_id, expira_em__gt=timezone.now()).exists()
