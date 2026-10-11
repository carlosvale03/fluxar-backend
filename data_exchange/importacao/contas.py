"""
Contas da importação completa (IMPCOMP-23, IMPCOMP-25 a IMPCOMP-27,
IMPCOMP-29, AD-055).

O plano liga cada nome de conta do arquivo a uma conta ativa do usuário
(vincular) ou a uma conta nova (criar). Na análise, a conta nova é uma conta
provisória, nunca gravada. Na importação, as contas novas são criadas com
saldo inicial zero antes da gravação das linhas e, depois dela, o saldo
inicial é acertado para que o saldo seja o saldo atual informado no plano.
Tudo roda na transação da importação: uma falha que sobe desfaz as contas.
"""
import uuid
from decimal import Decimal

from accounts.models import Account
from accounts.saldo import calcular, recalcular
from core.travas import conferir_limite

from .deteccao import CRIAR, VINCULAR


def contas_a_criar(contas_do_plano):
    """As contas do plano marcadas para criar, `{nome no arquivo: conta do plano}`."""
    return {nome: conta for nome, conta in contas_do_plano.items() if conta['acao'] == CRIAR}


def contas_vinculadas(usuario, contas_do_plano):
    """
    `{nome no arquivo: Account}` das contas vinculadas, só entre as contas
    ativas do usuário (AD-010; o plano já foi validado).
    """
    ids = {conta['id'] for conta in contas_do_plano.values() if conta['acao'] == VINCULAR}
    ativas = {str(c.pk): c for c in Account.objects.filter(user=usuario, is_active=True, pk__in=ids)}
    return {
        nome: ativas[conta['id']]
        for nome, conta in contas_do_plano.items()
        if conta['acao'] == VINCULAR and conta['id'] in ativas
    }


def contas_provisorias(usuario, contas_do_plano):
    """Na análise, uma conta não gravada para cada conta a criar, com um id só dela."""
    return {
        nome: Account(pk=uuid.uuid4(), user=usuario, name=conta['nome'], type=conta['tipo'])
        for nome, conta in contas_a_criar(contas_do_plano).items()
    }


def criar_contas(usuario, contas_do_plano):
    """
    Cria as contas marcadas para criar, com o nome, o tipo, a instituição e
    a cor do plano e saldo inicial zero (IMPCOMP-25), depois de conferir o
    limite de contas para todas de uma vez (IMPCOMP-27). Devolve
    `{nome no arquivo: Account}`.
    """
    novas = contas_a_criar(contas_do_plano)
    conferir_limite(usuario, 'limite_contas', quantidade=len(novas))
    return {
        nome: Account.objects.create(
            user=usuario, name=conta['nome'], type=conta['tipo'], initial_balance=Decimal('0.00'),
            institution=conta.get('institution') or None, color=conta.get('color') or None,
        )
        for nome, conta in novas.items()
    }


def acertar_saldos(contas_criadas, saldos_atuais):
    """
    Depois da gravação, fora do `recalculo_adiado`: o saldo inicial de cada
    conta criada passa a ser o saldo atual informado menos o efeito das
    transações efetivadas dela, e o saldo é recalculado (IMPCOMP-26).
    `saldos_atuais` é `{nome no arquivo: Decimal}`.
    """
    for nome, conta in contas_criadas.items():
        conta.refresh_from_db()
        efeito = calcular(conta) - conta.initial_balance
        inicial = Decimal(saldos_atuais[nome]) - efeito
        Account.objects.filter(pk=conta.pk).update(initial_balance=inicial)
        recalcular(conta.pk)
        conta.refresh_from_db()
