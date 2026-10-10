"""
Vínculo entre transações (AD-027, AD-054, spec `vinculo-entre-transacoes`).

Uma despesa ou compra no cartão pode ser dependente de uma transação
principal, num nível só: a dependente tem uma principal só, e a principal não
é dependente de outra. O vínculo fica no campo `Transaction.principal`, sempre
na raiz da compra parcelada (VINCULO-12), e é só informação: nenhum cálculo de
saldo, fatura, orçamento ou total lê o campo (VINCULO-17, VINCULO-28).

Todas as rotas passam por aqui. `vincular` trava as duas raízes em ordem de id
antes de conferir as regras, para que pedidos simultâneos não montem um ciclo
nem um segundo nível (VINCULO-19). Os logs levam só ids (VINCULO-23).
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.fields import TRANSACAO_NAO_ENCONTRADA
from core.valores import dinheiro

from .models import Transaction

logger = logging.getLogger(__name__)

ZERO = Decimal('0.00')

# Só despesas e compras no cartão se vinculam (VINCULO-05)
TIPOS_VINCULAVEIS = ('EXPENSE', 'CREDIT_CARD')

TIPO_NAO_VINCULAVEL = 'Só despesas e compras no cartão podem ser vinculadas.'
DEPENDENTE_COMO_PRINCIPAL = 'Uma transação dependente não pode ser principal.'
PRINCIPAL_COMO_DEPENDENTE = 'Uma transação principal não pode virar dependente.'
VINCULO_A_SI_MESMA = 'Uma transação não pode ser vinculada a ela mesma.'


def raiz_da_compra(transacao):
    """
    O id da compra inteira de uma parcela: a parcela raiz, que é a própria
    transação quando ela não é parcela (como em `services.grupo_da_compra`).
    """
    return transacao.parent_transaction_id or transacao.pk


def _recusar(mensagem):
    raise ValidationError({'detail': mensagem})


@transaction.atomic
def vincular(dependente, principal):
    """
    Grava `dependente` como dependente de `principal`, as duas pelas raízes
    das compras. Recusa com 400 os tipos que não se vinculam (VINCULO-05), a
    própria transação (VINCULO-08), a principal que já é dependente
    (VINCULO-06) e a dependente que já tem dependentes (VINCULO-07). A
    dependente de outra principal troca de principal (VINCULO-09), e a que já
    tem essa principal fica como está (VINCULO-10). Devolve a raiz da
    dependente.
    """
    id_da_dependente = raiz_da_compra(dependente)
    id_da_principal = raiz_da_compra(principal)
    # As duas raízes, do dono da dependente, travadas em ordem de id
    travadas = {
        t.pk: t for t in Transaction.objects.select_for_update()
        .filter(pk__in={id_da_dependente, id_da_principal}, user_id=dependente.user_id)
        .order_by('pk')
    }
    raiz = travadas.get(id_da_dependente)
    alvo = travadas.get(id_da_principal)
    if raiz is None or alvo is None:
        raise ValidationError({'principal': [TRANSACAO_NAO_ENCONTRADA]})

    if raiz.type not in TIPOS_VINCULAVEIS or alvo.type not in TIPOS_VINCULAVEIS:
        _recusar(TIPO_NAO_VINCULAVEL)
    if raiz.pk == alvo.pk:
        _recusar(VINCULO_A_SI_MESMA)
    if alvo.principal_id is not None:
        _recusar(DEPENDENTE_COMO_PRINCIPAL)
    if Transaction.objects.filter(principal_id=raiz.pk).exists():
        _recusar(PRINCIPAL_COMO_DEPENDENTE)

    if raiz.principal_id == alvo.pk:
        return raiz
    # `update()` grava só o vínculo, sem os signals de saldo e fatura (VINCULO-17)
    Transaction.objects.filter(pk=raiz.pk).update(principal=alvo)
    raiz.principal = alvo
    logger.info('Vínculo gravado: dependente=%s principal=%s.', raiz.pk, alvo.pk)
    return raiz


@transaction.atomic
def desvincular(dependente):
    """
    Remove só o vínculo da compra da dependente, sem alterar nem excluir as
    transações (VINCULO-04). Uma transação sem principal fica como está.
    """
    raiz = raiz_da_compra(dependente)
    alteradas = Transaction.objects.filter(
        pk=raiz, user_id=dependente.user_id, principal__isnull=False,
    ).update(principal=None)
    if alteradas:
        logger.info('Vínculo desfeito: dependente=%s.', raiz)


def dados_dos_vinculos(transacoes):
    """
    Os campos do vínculo de cada compra das `transacoes`, por id da raiz
    (VINCULO-26, VINCULO-27): `principal`, `principal_detail` (`{id,
    description, date}`, com a data da compra no cartão), `dependents_count` e
    `total_cost`, a soma de todas as parcelas da compra principal e das
    compras dependentes, nulo sem dependentes. Faz o mesmo número de consultas
    para qualquer quantidade de transações, para a lista não fazer uma
    consulta por linha. Só lê transações do dono de cada uma (ISOL-14).
    """
    donos = {raiz_da_compra(t): t.user_id for t in transacoes}
    if not donos:
        return {}
    raizes, usuarios = set(donos), set(donos.values())
    do_dono = Transaction.objects.filter(user_id__in=usuarios)

    principal_da_raiz = dict(do_dono.filter(pk__in=raizes).values_list('pk', 'principal_id'))
    dependentes = {}
    for principal_id, pk in do_dono.filter(principal_id__in=raizes).values_list('principal_id', 'pk'):
        dependentes.setdefault(principal_id, []).append(pk)

    detalhes = {
        linha['pk']: {
            'id': str(linha['pk']),
            'description': linha['description'],
            'date': (linha['purchase_date'] or linha['date']).isoformat(),
        }
        for linha in do_dono.filter(pk__in={p for p in principal_da_raiz.values() if p}).values(
            'pk', 'description', 'date', 'purchase_date',
        )
    }

    compras = set(dependentes) | {pk for pks in dependentes.values() for pk in pks}
    valores = {}
    if compras:
        valores = dict(
            do_dono.filter(Q(pk__in=compras) | Q(parent_transaction_id__in=compras))
            .annotate(compra=Coalesce('parent_transaction_id', 'pk'))
            .order_by().values('compra').annotate(total=Sum('amount'))
            .values_list('compra', 'total')
        )

    dados = {}
    for raiz in raizes:
        principal = principal_da_raiz.get(raiz)
        suas = dependentes.get(raiz, [])
        custo = None
        if suas:
            custo = dinheiro(sum((valores.get(pk, ZERO) for pk in [raiz, *suas]), ZERO))
        dados[raiz] = {
            'principal': str(principal) if principal else None,
            'principal_detail': detalhes.get(principal),
            'dependents_count': len(suas),
            'total_cost': custo,
        }
    return dados


class ListaComVinculos(serializers.ListSerializer):
    """
    Lista de transações do `TransactionSerializer`: os campos do vínculo de
    todas as linhas saem de `dados_dos_vinculos` de uma vez, sem uma consulta
    por linha (VINCULO-26).
    """

    def to_representation(self, data):
        itens = list(data.all() if hasattr(data, 'all') else data)
        self.context.setdefault('_vinculos', {}).update(dados_dos_vinculos(itens))
        return super().to_representation(itens)


def desfazer_vinculos(ids, user_id):
    """
    Desfaz todos os vínculos das transações `ids`, como dependentes e como
    principais, sem excluir nenhuma: a despesa que vira receita perde os
    vínculos (VINCULO-16).
    """
    ids = list(ids)
    if not ids:
        return
    como_dependente = Transaction.objects.filter(
        pk__in=ids, user_id=user_id, principal__isnull=False,
    ).update(principal=None)
    como_principal = Transaction.objects.filter(
        principal_id__in=ids, user_id=user_id,
    ).update(principal=None)
    if como_dependente or como_principal:
        logger.info('Vínculos desfeitos pela troca para receita: transacoes=%s.', len(ids))
