"""
Corrige as faturas gravadas antes da feature `faturas` (FATURA-39 a
FATURA-41).

1. Compra no cartão sem fatura: `purchase_date` recebe o `date` gravado
   (quando ainda não tem), e a compra vai para a fatura da data da compra;
   pendente numa fatura paga vai para a primeira não paga seguinte
   (FATURA-39, FATURA-15).
2. Compra com duas ou mais parcelas pendentes na mesma fatura (FIN-06): as
   parcelas, em ordem de número, são realocadas. A primeira fica onde está,
   as pagas ficam onde estão e servem de referência, e cada pendente
   seguinte vai para a primeira fatura não paga depois da fatura da parcela
   anterior (FATURA-40, FATURA-12). O `date` acompanha o vencimento da
   fatura nova (AD-039). O restante de um pagamento parcial antigo tem o
   mesmo número da parcela dividida: só a primeira parte de cada número
   entra na realocação, e as outras ficam onde estão.
3. O total de todas as faturas é recalculado como a soma das compras do dono
   do cartão ligadas a ela (FATURA-41, ISOL-14).

Roda uma vez, no `migrate` do deploy; em banco vazio não encontra nada. Usa
os modelos históricos e as funções de data de `accounts/faturas.py`, que não
importam modelos nem acessam o banco. Faturas criadas aqui usam os dias
atuais do cartão.
"""
from decimal import Decimal

from django.db import migrations
from django.db.models import F, Q, Sum

from accounts.faturas import datas_da_fatura, mes_da_fatura, mes_seguinte


def _obter_fatura(CreditCardInvoice, cartao, mes, ano):
    fechamento, vencimento = datas_da_fatura(cartao.closing_day, cartao.due_day, mes, ano)
    fatura, _ = CreditCardInvoice.objects.get_or_create(
        card_id=cartao.pk, month=mes, year=ano,
        defaults={'closing_date': fechamento, 'due_date': vencimento, 'status': 'OPEN'},
    )
    return fatura


def _primeira_nao_paga(CreditCardInvoice, cartao, mes, ano):
    fatura = _obter_fatura(CreditCardInvoice, cartao, mes, ano)
    while fatura.status == 'PAID':
        fatura = _obter_fatura(CreditCardInvoice, cartao, *mes_seguinte(fatura.month, fatura.year))
    return fatura


def _colocar(Transaction, compra, fatura):
    Transaction.objects.filter(pk=compra.pk).update(invoice_id=fatura.pk, date=fatura.due_date)
    compra.invoice_id, compra.date = fatura.pk, fatura.due_date


def _ligar_compras_sem_fatura(apps):
    Transaction = apps.get_model('transactions', 'Transaction')
    CreditCardInvoice = apps.get_model('accounts', 'CreditCardInvoice')
    sem_fatura = Transaction.objects.filter(
        type='CREDIT_CARD', invoice__isnull=True, credit_card__isnull=False,
    ).select_related('credit_card')
    for compra in sem_fatura:
        cartao = compra.credit_card
        data_compra = compra.purchase_date or compra.date
        fatura = _obter_fatura(
            CreditCardInvoice, cartao, *mes_da_fatura(cartao.closing_day, cartao.due_day, data_compra),
        )
        if compra.status == 'PENDING' and fatura.status == 'PAID':
            fatura = _primeira_nao_paga(CreditCardInvoice, cartao, fatura.month, fatura.year)
        Transaction.objects.filter(pk=compra.pk).update(purchase_date=data_compra)
        _colocar(Transaction, compra, fatura)


def _realocar_parcelas_repetidas(apps):
    Transaction = apps.get_model('transactions', 'Transaction')
    CreditCardInvoice = apps.get_model('accounts', 'CreditCardInvoice')
    raizes = Transaction.objects.filter(
        type='CREDIT_CARD', parent_transaction__isnull=True, is_installment=True,
    )
    for raiz in raizes:
        partes = Transaction.objects.filter(
            Q(pk=raiz.pk) | Q(parent_transaction_id=raiz.pk),
            user_id=raiz.user_id, type='CREDIT_CARD', invoice__isnull=False,
        ).select_related('invoice__card').order_by(
            F('installment_number').asc(nulls_first=True), 'created_at', 'pk',
        )
        parcelas, numeros = [], set()
        for parte in partes:
            # O restante antigo repete o número da parcela dividida
            if parte.installment_number in numeros:
                continue
            numeros.add(parte.installment_number)
            parcelas.append(parte)

        faturas_pendentes = [p.invoice_id for p in parcelas if p.status == 'PENDING']
        if len(faturas_pendentes) == len(set(faturas_pendentes)):
            continue

        anterior = parcelas[0].invoice
        for parcela in parcelas[1:]:
            if parcela.status == 'PENDING':
                fatura = _primeira_nao_paga(
                    CreditCardInvoice, anterior.card, *mes_seguinte(anterior.month, anterior.year),
                )
                if fatura.pk != parcela.invoice_id:
                    _colocar(Transaction, parcela, fatura)
                anterior = fatura
            else:
                anterior = parcela.invoice


def _recalcular_todos_os_totais(apps):
    Transaction = apps.get_model('transactions', 'Transaction')
    CreditCardInvoice = apps.get_model('accounts', 'CreditCardInvoice')
    for fatura in CreditCardInvoice.objects.select_related('card'):
        total = Transaction.objects.filter(
            invoice_id=fatura.pk, type='CREDIT_CARD', user_id=fatura.card.user_id,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if fatura.total_amount != total:
            CreditCardInvoice.objects.filter(pk=fatura.pk).update(total_amount=total)


def corrigir(apps, schema_editor):
    _ligar_compras_sem_fatura(apps)
    _realocar_parcelas_repetidas(apps)
    _recalcular_todos_os_totais(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_pagamentodefatura_itemdepagamento'),
        ('transactions', '0009_transaction_purchase_date'),
    ]

    operations = [
        migrations.RunPython(corrigir, migrations.RunPython.noop),
    ]
