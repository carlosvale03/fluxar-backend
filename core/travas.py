"""
Travas dos planos: catálogo, configuração e decisão de acesso (AD-044).

O `CATALOGO` tem as chaves que um plano pode travar: recursos, ligados ou
desligados por plano, e limites, com um número por plano ou sem limite. Os
recursos essenciais da spec não entram no catálogo e, por isso, nunca travam
(PERM-14).

A configuração fica na tabela `TravaDePlano` e na `GlobalSetting`
`testing_unlock`. Cada processo lê as duas no máximo uma vez a cada 30
segundos, no mesmo padrão de `core/manutencao.py` (PERM-11, PERM-24);
`invalidar()` descarta o valor guardado. Linha ausente vale liberado e sem
limite, e a liberação sem a chave vale ligada (PERM-28).

`acesso(usuario)` é a única decisão: o administrador e a liberação para
testes liberam tudo; senão vale a configuração do plano atual do usuário,
lido do banco a cada requisição (PERM-04, PERM-09, PERM-23, PERM-26).
"""
import time
from dataclasses import dataclass
from typing import Callable, Optional

from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission

from accounts.models import Account, CreditCard
from api.models import GlobalSetting, TravaDePlano
from goals.models import Goal
from transactions.models import Category, Tag

PLANOS = ('COMMON', 'PREMIUM', 'PREMIUM_PLUS')
RECURSO = 'recurso'
LIMITE = 'limite'
TTL = 30


# Contagem do uso de cada limite --------------------------------------------

def _contar_contas(usuario, **contexto):
    """Contas ativas, sem os cofrinhos criados por metas."""
    cofrinhos_de_metas = Goal.objects.filter(user=usuario).values('account_id')
    return (
        Account.objects.filter(user=usuario, is_active=True)
        .exclude(Q(type='PIGGY_BANK') & Q(pk__in=cofrinhos_de_metas))
        .count()
    )


def _contar_cartoes(usuario, **contexto):
    return CreditCard.objects.filter(user=usuario, is_active=True).count()


def _contar_categorias(usuario, **contexto):
    return Category.objects.filter(user=usuario, is_active=True, parent__isnull=True).count()


def _contar_subcategorias(usuario, parent=None, **contexto):
    """Subcategorias ativas da categoria-pai informada."""
    return Category.objects.filter(user=usuario, is_active=True, parent=parent).count()


def _contar_tags(usuario, **contexto):
    return Tag.objects.filter(user=usuario).count()


def _contar_metas(usuario, **contexto):
    return Goal.objects.filter(user=usuario, is_active=True).count()


# Catálogo ------------------------------------------------------------------

@dataclass(frozen=True)
class Trava:
    chave: str
    tipo: str
    nome: str
    descricao: str
    contar: Optional[Callable] = None


def _recurso(chave, nome, descricao):
    return Trava(chave, RECURSO, nome, descricao)


def _limite(chave, nome, descricao, contar):
    return Trava(chave, LIMITE, nome, descricao, contar)


CATALOGO = {trava.chave: trava for trava in (
    _recurso('relatorios_avancados', 'Relatórios avançados', 'Aba "Avançados" da tela Relatórios.'),
    _recurso('comparacao_mensal', 'Comparação mensal', 'Gráfico de comparação mensal no dashboard e nos relatórios.'),
    _recurso('analise_por_tag', 'Análise por tag', 'Análise e distribuição por tag nos relatórios.'),
    _recurso('monitor_de_foco', 'Monitor de foco', 'Monitor de foco nos relatórios.'),
    _recurso('calendario', 'Calendário', 'Tela Calendário.'),
    _recurso('orcamentos', 'Orçamentos', 'Tela Orçamentos, inclusive a importação de orçamentos de outro mês.'),
    _recurso('metas', 'Metas', 'Tela Metas: metas, aportes, resgates, histórico e cofrinho de arredondamento.'),
    _recurso(
        'cartoes', 'Cartões',
        'Telas Cartões e detalhe do cartão, e compras no cartão. Pagar e estornar faturas existentes continua liberado.',
    ),
    _recurso('compras_parceladas', 'Compras parceladas', 'Parcelamento acima de 1x na compra no cartão.'),
    _recurso(
        'transacoes_recorrentes', 'Transações recorrentes',
        'Opção "recorrente" ao lançar, e edição e exclusão de séries inteiras.',
    ),
    _recurso('tags', 'Tags', 'Tela Tags e campo de tags nos lançamentos.'),
    _recurso('importacao_ofx', 'Importação de OFX', 'Importação de extratos em OFX.'),
    _recurso('importacao_planilha', 'Importação de planilha', 'Importação de CSV e XLSX, inclusive de transferências.'),
    _recurso('exportacao_pdf', 'Exportação em PDF', 'Exportação de transações em PDF.'),
    _recurso('exportacao_xlsx', 'Exportação em XLSX', 'Exportação de transações em XLSX.'),
    _recurso('personalizar_dashboard', 'Personalizar o dashboard', 'Personalização do layout do dashboard.'),
    _recurso(
        'gestao_do_salario', 'Gestão do salário',
        'Tela Gestão do salário: plano de divisão, simulação, divisão, desfazer e o aviso ao lançar o salário.',
    ),
    _recurso(
        'vinculos', 'Vínculos entre transações',
        'Criar e trocar vínculos entre transações, filtro de vinculadas e relatório de gastos puxados.',
    ),
    _limite('limite_contas', 'Contas', 'Contas ativas, sem contar os cofrinhos criados por metas.', _contar_contas),
    _limite('limite_cartoes', 'Cartões', 'Cartões ativos.', _contar_cartoes),
    _limite('limite_categorias', 'Categorias', 'Categorias principais ativas.', _contar_categorias),
    _limite(
        'limite_subcategorias', 'Subcategorias', 'Subcategorias ativas de uma mesma categoria.', _contar_subcategorias,
    ),
    _limite('limite_tags', 'Tags', 'Tags.', _contar_tags),
    _limite('limite_metas', 'Metas', 'Metas ativas.', _contar_metas),
)}


# Configuração em cache -----------------------------------------------------

@dataclass(frozen=True)
class Configuracao:
    testing_unlock: bool
    # (chave, plano) -> TravaDePlano.liberado ou TravaDePlano.limite
    valores: dict


_configuracao = None
_lido_em = None


def liberacao_ligada(valor):
    """O texto da `GlobalSetting`; sem a chave, a liberação vale ligada, como antes da feature (PERM-28)."""
    return valor is None or valor.lower() == 'true'


def ler_configuracao():
    """A configuração atual do banco, sem o cache."""
    liberacao = GlobalSetting.objects.filter(key='testing_unlock').values_list('value', flat=True).first()
    valores = {}
    for chave, plano, liberado, limite in TravaDePlano.objects.values_list('chave', 'plano', 'liberado', 'limite'):
        trava = CATALOGO.get(chave)
        if trava is not None:
            valores[(chave, plano)] = limite if trava.tipo == LIMITE else liberado
    return Configuracao(testing_unlock=liberacao_ligada(liberacao), valores=valores)


def configuracao():
    """A configuração das travas, lida do banco no máximo uma vez a cada 30 s."""
    global _configuracao, _lido_em
    agora = time.monotonic()
    if _lido_em is None or agora - _lido_em >= TTL:
        _configuracao = ler_configuracao()
        _lido_em = agora
    return _configuracao


def invalidar():
    """Faz a próxima chamada ler o banco de novo."""
    global _lido_em
    _lido_em = None


def valor_configurado(config, chave, plano):
    """
    O valor da trava no plano: `True`/`False` para recurso e o número ou
    `None` (sem limite) para limite. Sem a linha, liberado e sem limite.
    """
    valor = config.valores.get((chave, plano))
    if CATALOGO[chave].tipo == RECURSO:
        return valor is not False
    return valor


TIPOS_NA_API = {RECURSO: 'feature', LIMITE: 'limit'}


def valor_na_api(chave, valor):
    """`true`/`false` para recurso e `{limit: int | null}` para limite."""
    return valor if CATALOGO[chave].tipo == RECURSO else {'limit': valor}


def catalogo_com_valores(config):
    """
    Cada trava do catálogo, na ordem da spec, com o valor dos três planos
    (PERM-10, PERM-27).
    """
    return [
        {
            'key': trava.chave,
            'type': TIPOS_NA_API[trava.tipo],
            'name': trava.nome,
            'description': trava.descricao,
            'values': {
                plano: valor_na_api(trava.chave, valor_configurado(config, trava.chave, plano))
                for plano in PLANOS
            },
        }
        for trava in CATALOGO.values()
    ]


# Decisão por usuário -------------------------------------------------------

@dataclass(frozen=True)
class Acesso:
    plano: str
    is_admin: bool
    testing_unlock: bool
    _config: Configuracao

    @property
    def livre(self):
        """Administrador e liberação para testes: tudo liberado, sem limite (PERM-09, PERM-23)."""
        return self.is_admin or self.testing_unlock

    def recurso_liberado(self, chave):
        assert CATALOGO[chave].tipo == RECURSO, chave
        return self.livre or valor_configurado(self._config, chave, self.plano)

    def limite(self, chave):
        """O limite da trava para o usuário; `None` é sem limite."""
        assert CATALOGO[chave].tipo == LIMITE, chave
        if self.livre:
            return None
        return valor_configurado(self._config, chave, self.plano)


def acesso(usuario):
    config = configuracao()
    return Acesso(
        plano=usuario.plan,
        is_admin=bool(usuario.is_active and usuario.role == 'ADMIN'),
        testing_unlock=config.testing_unlock,
        _config=config,
    )


def uso(usuario, chave, **contexto):
    """Quantos itens o usuário já tem para o limite `chave`."""
    return CATALOGO[chave].contar(usuario, **contexto)


# Bloqueio nas rotas --------------------------------------------------------

class PlanoBloqueado(APIException):
    """
    HTTP 403 `{detail, code: "plan_locked", feature}` para um recurso
    bloqueado no plano do usuário (PERM-15). O handler de
    `core/exceptions.py` acrescenta os `extras` ao corpo.
    """
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Este recurso não está disponível no seu plano.'
    default_code = 'plan_locked'

    def __init__(self, chave):
        super().__init__()
        self.extras = {'feature': chave}


def exigir_recurso(usuario, chave):
    """Levanta `PlanoBloqueado` se o recurso `chave` está bloqueado para o usuário."""
    if not acesso(usuario).recurso_liberado(chave):
        raise PlanoBloqueado(chave)


def RecursoLiberado(chave, acoes=None):
    """
    Permissão do DRF que exige o recurso `chave` do catálogo. Com `acoes`,
    vale só para essas ações do ViewSet; as outras seguem liberadas.
    Depois de `IsAuthenticated`, para o anônimo receber 401.
    """
    class _RecursoLiberado(BasePermission):
        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            if acoes is None or getattr(view, 'action', None) in acoes:
                exigir_recurso(request.user, chave)
            return True

    _RecursoLiberado.__name__ = f'RecursoLiberado_{chave}'
    return _RecursoLiberado


class LimiteDoPlano(APIException):
    """
    HTTP 403 `{detail, code: "plan_limit_reached", feature, limit}` para a
    criação além do limite do plano (PERM-16).
    """
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Você atingiu o limite do seu plano.'
    default_code = 'plan_limit_reached'

    def __init__(self, chave, limite):
        super().__init__()
        self.extras = {'feature': chave, 'limit': limite}


def conferir_limite(usuario, chave, **contexto):
    """
    Chamada na criação de um item: recusa quando o uso atual já é maior ou
    igual ao limite do plano. Os itens existentes nunca são apagados nem
    bloqueados por limite (PERM-16, PERM-21). `contexto` leva o que a contagem
    precisa, como o `parent` das subcategorias.
    """
    limite = acesso(usuario).limite(chave)
    if limite is None:
        return
    # Trava o usuário até o fim da requisição, para duas criações simultâneas
    # não passarem juntas do limite
    type(usuario).objects.select_for_update().filter(pk=usuario.pk).exists()
    if uso(usuario, chave, **contexto) >= limite:
        raise LimiteDoPlano(chave, limite)


# Acesso informado ao frontend ----------------------------------------------

# Limites cujo uso depende de um contexto; o /auth/me informa só o limite
LIMITES_POR_CONTEXTO = frozenset({'limite_subcategorias'})


def acesso_na_api(usuario):
    """
    O `access` do `/auth/me` (PERM-17): `{is_admin, testing_unlock, plan,
    features: {chave: bool}, limits: {chave: {limit, used}}}`. O frontend
    decide só por ele (PERM-18).
    """
    decisao = acesso(usuario)
    limites = {}
    for trava in CATALOGO.values():
        if trava.tipo != LIMITE:
            continue
        item = {'limit': decisao.limite(trava.chave)}
        if trava.chave not in LIMITES_POR_CONTEXTO:
            item['used'] = uso(usuario, trava.chave)
        limites[trava.chave] = item
    return {
        'is_admin': decisao.is_admin,
        'testing_unlock': decisao.testing_unlock,
        'plan': decisao.plano,
        'features': {
            trava.chave: decisao.recurso_liberado(trava.chave)
            for trava in CATALOGO.values() if trava.tipo == RECURSO
        },
        'limits': limites,
    }
