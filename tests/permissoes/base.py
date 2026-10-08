"""
Base dos testes de permissões e planos.

`criar_usuario` cria contas verificadas com a mesma senha; `criar_admin` cria
um administrador pelo papel, sem `is_staff` (AD-016). `PermissoesTestCase`
descarta o cache das travas antes e depois de cada teste, e `fechar` e
`liberacao_de_testes` gravam a configuração direto no banco.
"""
from django.core.cache import cache
from rest_framework.test import APITestCase

from api.models import GlobalSetting, TravaDePlano, User
from core import travas

SENHA = 'Cofre-Azul-2026'

RECURSOS = [
    'relatorios_avancados', 'comparacao_mensal', 'analise_por_tag', 'monitor_de_foco',
    'calendario', 'orcamentos', 'metas', 'cartoes', 'compras_parceladas',
    'transacoes_recorrentes', 'tags', 'importacao_ofx', 'importacao_planilha',
    'exportacao_pdf', 'exportacao_xlsx', 'personalizar_dashboard', 'gestao_do_salario',
    'vinculos',
]
LIMITES = [
    'limite_contas', 'limite_cartoes', 'limite_categorias', 'limite_subcategorias',
    'limite_tags', 'limite_metas',
]


def criar_usuario(apelido, **extra):
    campos = {'email_verified': True}
    campos.update(extra)
    return User.objects.create_user(
        email=f'{apelido}@permissoes.fluxar', password=SENHA, name=apelido.capitalize(), **campos,
    )


def criar_admin(apelido='admin', **extra):
    campos = {'role': 'ADMIN'}
    campos.update(extra)
    return criar_usuario(apelido, **campos)


def liberacao_de_testes(ligada):
    GlobalSetting.objects.update_or_create(
        key='testing_unlock', defaults={'value': 'true' if ligada else 'false'},
    )
    travas.invalidar()


def fechar(chave, plano='COMMON', limite=None):
    """Fecha um recurso, ou define um limite, direto no banco."""
    if chave in LIMITES:
        valores = {'limite': limite, 'liberado': None}
    else:
        valores = {'liberado': False, 'limite': None}
    TravaDePlano.objects.update_or_create(chave=chave, plano=plano, defaults=valores)
    travas.invalidar()


class PermissoesTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        travas.invalidar()
        self.addCleanup(travas.invalidar)
