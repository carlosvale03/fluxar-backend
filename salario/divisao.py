"""
Recebimentos a dividir e revisão da divisão (SALARIO-24, SALARIO-29,
SALARIO-30, SALARIO-40).
"""
from django.db.models import Exists, OuterRef
from rest_framework.exceptions import ValidationError

from accounts.faturas import mes_anterior
from core.datas import hoje
from core.fields import RECEBIMENTO_NAO_ENCONTRADO
from core.valores import dinheiro
from reports.regras import limites_do_mes, mes_atual
from transactions.models import Transaction

from . import plano
from .calculo import AjustesAcimaDoRecebido, dividir
from .models import DivisaoDoSalario

JA_DIVIDIDO = 'Este salário já foi dividido.'
AJUSTES_ACIMA_DO_RECEBIDO = 'Os valores passam do salário recebido.'
AJUSTE_DE_OUTRA_PARTE = 'Ajuste de uma parte que não está no plano.'


def recebimento_valido(usuario, transacao, categorias=None):
    """
    Receita efetivada, com conta, numa categoria de salário do usuário e que
    não é ajuste de saldo (SALARIO-40). A importada também vale (SALARIO-24).
    """
    if categorias is None:
        categorias = plano.categorias_de_salario(usuario)
    return (
        transacao is not None and transacao.user_id == usuario.pk and transacao.type == 'INCOME'
        and transacao.status == 'COMPLETED' and transacao.account_id is not None
        and not transacao.is_balance_adjustment and transacao.category_id in categorias
    )


def conferir_recebimento(usuario, transacao):
    """Levanta 400 no campo `receipt` se a transação não é um salário recebido (SALARIO-40)."""
    if not recebimento_valido(usuario, transacao):
        raise ValidationError({'receipt': [RECEBIMENTO_NAO_ENCONTRADO]})


def divisao_ativa(recebimento_id):
    return DivisaoDoSalario.objects.filter(recebimento_ref=recebimento_id, desfeita_em__isnull=True)


def conferir_nao_dividido(recebimento_id):
    """Levanta 400 se o recebimento já tem uma divisão ativa (SALARIO-38)."""
    if divisao_ativa(recebimento_id).exists():
        raise ValidationError({'detail': JA_DIVIDIDO})


def pendentes(usuario):
    """
    Os salários efetivados do mês atual e do anterior, no calendário de
    Brasília, sem divisão ativa, do mais recente para o mais antigo
    (SALARIO-24).
    """
    ano, mes = mes_atual()
    mes_ant, ano_ant = mes_anterior(mes, ano)
    inicio, _ = limites_do_mes(ano_ant, mes_ant)
    _, fim = limites_do_mes(ano, mes)
    dividido = DivisaoDoSalario.objects.filter(recebimento_ref=OuterRef('pk'), desfeita_em__isnull=True)
    return (
        Transaction.objects.filter(
            user=usuario, type='INCOME', status='COMPLETED', account__isnull=False,
            is_balance_adjustment=False, category_id__in=plano.categorias_de_salario(usuario),
            date__gte=inicio, date__lte=fim,
        )
        .exclude(Exists(dividido))
        .select_related('account', 'category')
        .order_by('-date', '-created_at')
    )


def recebimento_em_json(transacao):
    return {
        'id': str(transacao.pk),
        'description': transacao.description,
        'amount': dinheiro(transacao.amount),
        'date': transacao.date.isoformat(),
        'account': str(transacao.account_id),
        'account_name': transacao.account.name,
        'category': str(transacao.category_id) if transacao.category_id else None,
        'category_name': transacao.category.name if transacao.category_id else None,
        'imported': transacao.import_batch is not None,
    }


def calcular(usuario, recebimento, ajustes=None):
    """
    A divisão do recebimento pelo plano salvo, com os ajustes da revisão
    (SALARIO-26 a SALARIO-30). Ajuste de uma parte fora do plano ou acima do
    recebido recebe 400 no campo `adjustments`.
    """
    partes = plano.partes_do_plano(usuario)
    ajustes = {str(chave): valor for chave, valor in (ajustes or {}).items()}
    if set(ajustes) - {str(parte.pk) for parte in partes}:
        raise ValidationError({'adjustments': [AJUSTE_DE_OUTRA_PARTE]})
    try:
        return dividir(recebimento.amount, partes, ajustes, conta_do_recebimento=recebimento.account_id)
    except AjustesAcimaDoRecebido:
        raise ValidationError({'adjustments': [AJUSTES_ACIMA_DO_RECEBIDO]})


def revisao_em_json(recebimento, divisao, data):
    """O corpo de `POST /salary/divisions/preview/` (SALARIO-29)."""
    origem = {'id': str(recebimento.account_id), 'name': recebimento.account.name}
    return {
        'receipt': recebimento_em_json(recebimento),
        'items': [{**plano.item_em_json(item), 'origin_account': origem} for item in divisao.itens],
        'total': dinheiro(divisao.total),
        'free': dinheiro(divisao.livre),
        'date': data.isoformat(),
    }


def revisar(usuario, recebimento, ajustes=None):
    """A revisão da divisão de um recebimento, sem gravar nada."""
    conferir_recebimento(usuario, recebimento)
    conferir_nao_dividido(recebimento.pk)
    divisao = calcular(usuario, recebimento, ajustes)
    return revisao_em_json(recebimento, divisao, hoje())
