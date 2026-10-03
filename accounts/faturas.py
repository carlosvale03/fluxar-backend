"""
Regras da fatura do cartão (spec `faturas`).

Primeira camada, sem banco: as datas de fechamento e de vencimento e o mês
da fatura em que cai uma compra. A migração de correção usa as mesmas
funções, por isso esta camada não importa modelos.

`mes` e `ano` de uma fatura são sempre os do vencimento, como
`CreditCardInvoice.month` e `year`.
"""
import calendar
from datetime import date
from decimal import Decimal


def dia_no_mes(ano, mes, dia):
    """
    O `dia` do mês, ou o último dia do mês quando ele não existe (FATURA-01,
    AD-006). O ajuste não se acumula: cada mês parte do dia cadastrado
    (FATURA-02).
    """
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def mes_seguinte(mes, ano):
    """O mês seguinte, como `(mes, ano)`."""
    return (1, ano + 1) if mes == 12 else (mes + 1, ano)


def mes_anterior(mes, ano):
    """O mês anterior, como `(mes, ano)`."""
    return (12, ano - 1) if mes == 1 else (mes - 1, ano)


def datas_da_fatura(dia_fechamento, dia_vencimento, mes, ano):
    """
    `(fechamento, vencimento)` da fatura que vence em `mes`/`ano`. O
    fechamento fica no mesmo mês do vencimento quando o dia de vencimento é
    maior que o de fechamento (FATURA-03) e no mês anterior quando é menor
    ou igual (FATURA-04).
    """
    vencimento = dia_no_mes(ano, mes, dia_vencimento)
    if dia_vencimento > dia_fechamento:
        mes_fechamento, ano_fechamento = mes, ano
    else:
        mes_fechamento, ano_fechamento = mes_anterior(mes, ano)
    fechamento = dia_no_mes(ano_fechamento, mes_fechamento, dia_fechamento)
    return fechamento, vencimento


def mes_da_fatura(dia_fechamento, dia_vencimento, data_compra):
    """
    `(mes, ano)` do vencimento da fatura em que cai uma compra. Antes do
    fechamento do mês, já ajustado por AD-006, ela fica na fatura que fecha
    nesse mês (FATURA-10); no dia do fechamento ou depois, na que fecha no
    mês seguinte (FATURA-11).
    """
    mes, ano = data_compra.month, data_compra.year
    if data_compra >= dia_no_mes(ano, mes, dia_fechamento):
        mes, ano = mes_seguinte(mes, ano)
    if dia_vencimento <= dia_fechamento:
        mes, ano = mes_seguinte(mes, ano)
    return mes, ano


# --- Faturas e compras (com banco) ---
# Os modelos são importados dentro das funções, para que a camada de datas
# continue importável pela migração sem carregar os apps.


def obter_fatura(cartao, mes, ano):
    """
    A fatura do cartão que vence em `mes`/`ano`, criada com as datas de
    `datas_da_fatura` e os dias atuais do cartão quando falta (FATURA-25).
    Fatura existente mantém as datas gravadas, mesmo que os dias do cartão
    tenham mudado (FATURA-07).
    """
    from .models import CreditCardInvoice

    fechamento, vencimento = datas_da_fatura(cartao.closing_day, cartao.due_day, mes, ano)
    fatura, _ = CreditCardInvoice.objects.get_or_create(
        card=cartao, month=mes, year=ano,
        defaults={'closing_date': fechamento, 'due_date': vencimento, 'status': 'OPEN'},
    )
    return fatura


def fatura_da_compra(cartao, data_compra):
    """
    `(mes, ano)` da fatura em que cai uma compra, sem criar fatura. Se a
    fatura desse mês já existe e fecha na data da compra ou antes (os dias
    do cartão mudaram depois que ela foi criada), a compra vai para a
    seguinte (FATURA-07, FATURA-10, FATURA-11).
    """
    from .models import CreditCardInvoice

    mes, ano = mes_da_fatura(cartao.closing_day, cartao.due_day, data_compra)
    while CreditCardInvoice.objects.filter(
        card=cartao, month=mes, year=ano, closing_date__lte=data_compra,
    ).exists():
        mes, ano = mes_seguinte(mes, ano)
    return mes, ano


def primeira_nao_paga(cartao, mes, ano):
    """
    A partir de `mes`/`ano`, a primeira fatura do cartão que não está paga,
    criada se faltar (FATURA-15, FATURA-25).
    """
    fatura = obter_fatura(cartao, mes, ano)
    while fatura.status == 'PAID':
        fatura = obter_fatura(cartao, *mes_seguinte(fatura.month, fatura.year))
    return fatura


def alocar_parcelas(cartao, data_compra, quantidade):
    """
    As faturas das `quantidade` parcelas de uma compra: a primeira na fatura
    da data da compra e cada seguinte na fatura do mês seguinte ao da
    anterior, uma parcela por fatura, pulando as faturas pagas (FATURA-12,
    FATURA-15).
    """
    faturas = [primeira_nao_paga(cartao, *fatura_da_compra(cartao, data_compra))]
    while len(faturas) < quantidade:
        anterior = faturas[-1]
        faturas.append(primeira_nao_paga(cartao, *mes_seguinte(anterior.month, anterior.year)))
    return faturas


def dividir_valor(valor, quantidade):
    """
    O valor de cada parcela: arredondado a centavos, com a diferença somada à
    primeira, para que a soma seja o valor da compra (FATURA-13).
    """
    parcela = round(valor / Decimal(quantidade), 2)
    valores = [parcela] * quantidade
    valores[0] += valor - parcela * quantidade
    return valores


def colocar(compra, fatura):
    """
    Liga a compra à fatura e grava o vencimento dela como `date`, sempre
    juntos (AD-039). Salva a compra, o que também a cria se for nova.
    """
    compra.invoice = fatura
    compra.date = fatura.due_date
    compra.save()
    return compra


def status_exibido(fatura):
    """
    O status mostrado da fatura: `PAID` se paga; senão `OPEN` enquanto hoje
    (em Brasília, AD-008) é anterior ao fechamento e `CLOSED` a partir dele
    (FATURA-08, FATURA-09). O banco grava só `OPEN` e `PAID`.
    """
    from core.datas import hoje

    if fatura.status == 'PAID':
        return 'PAID'
    return 'OPEN' if hoje() < fatura.closing_date else 'CLOSED'


def proximo_vencimento(cartao):
    """
    O primeiro vencimento igual ou posterior a hoje, pelos dias atuais do
    cartão (FATURA-06): o deste mês, se ainda não passou, ou o do seguinte.
    """
    from core.datas import hoje

    dia = hoje()
    vencimento = dia_no_mes(dia.year, dia.month, cartao.due_day)
    if vencimento < dia:
        mes, ano = mes_seguinte(dia.month, dia.year)
        vencimento = dia_no_mes(ano, mes, cartao.due_day)
    return vencimento


def limite_disponivel(cartao):
    """
    O limite do cartão menos as compras pendentes dele, de todas as faturas,
    só as do dono do cartão (FATURA-42, ISOL-14). É a única fórmula, usada
    na tela do cartão e no dashboard.
    """
    from django.db.models import Sum

    from transactions.models import Transaction

    pendente = Transaction.objects.filter(
        credit_card=cartao, user_id=cartao.user_id, type='CREDIT_CARD', status='PENDING',
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return cartao.limit - pendente


def recalcular_totais(*fatura_ids):
    """
    Grava em cada fatura o total igual à soma das compras no cartão ligadas a
    ela, só as do dono do cartão (FATURA-18, ISOL-14). Ignora `None`. Quem
    muda compras por `QuerySet.update()` chama esta função.
    """
    from django.db.models import Sum

    from transactions.models import Transaction

    from .models import CreditCardInvoice

    ids = {fatura_id for fatura_id in fatura_ids if fatura_id is not None}
    for fatura in CreditCardInvoice.objects.filter(pk__in=ids).select_related('card'):
        total = Transaction.objects.filter(
            invoice_id=fatura.pk, type='CREDIT_CARD', user_id=fatura.card.user_id,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if fatura.total_amount != total:
            CreditCardInvoice.objects.filter(pk=fatura.pk).update(total_amount=total)


# --- Pagamento e estorno ---

FATURA_JA_PAGA = 'Fatura já está paga.'
FATURA_NAO_PAGA = 'Esta fatura não está paga.'
VALOR_MAIOR_QUE_O_TOTAL = 'O valor pago não pode ser maior que o total da fatura.'
CHAVE_COM_OUTROS_DADOS = 'Este identificador de pagamento já foi usado com outros dados.'
ESTORNE_A_SEGUINTE = 'Estorne primeiro o pagamento da fatura seguinte.'


def _dividir(compra, pago, conta, data, seguinte):
    """
    Divide a compra no pagamento parcial (FATURA-23): ela fica com a parte
    paga e "(Parcial)", e o restante, pendente, vai para a fatura `seguinte`
    com a data da compra, na conta do cartão e no grupo da compra (a mesma
    raiz), para que a exclusão e a FATURA-19 o tratem como parte dela.
    Devolve o restante.
    """
    from transactions.models import Transaction

    descricao, tags = compra.description, list(compra.tags.all())
    restante = Transaction(
        user_id=compra.user_id, type='CREDIT_CARD', status='PENDING',
        account_id=compra.credit_card.account_id, credit_card_id=compra.credit_card_id,
        amount=compra.amount - pago, purchase_date=compra.purchase_date,
        description=f'{descricao} (Restante)', category_id=compra.category_id,
        is_installment=compra.is_installment, installment_number=compra.installment_number,
        installment_total=compra.installment_total,
        parent_transaction_id=compra.parent_transaction_id or compra.pk,
    )

    compra.amount = pago
    compra.status = 'COMPLETED'
    compra.account = conta
    compra.payment_date = data
    compra.description = f'{descricao} (Parcial)'
    compra.save()

    colocar(restante, seguinte)
    restante.tags.set(tags)
    return restante


def pagar(usuario, fatura, conta, valor, data, chave=None):
    """
    Paga a fatura com `valor` saído de `conta` em `data`, tudo num `atomic`:
    qualquer falha desfaz a operação inteira (FATURA-28).
    - `chave` é o identificador da tentativa (AD-007). Se o usuário já tem
      um pagamento com ela, devolve esse pagamento sem pagar de novo, mesmo
      depois de um estorno (FATURA-30); com outra fatura, valor, conta ou
      data, recusa com 400 (FATURA-32). Sem chave, é uma tentativa nova.
    - Relê a fatura sob trava: fatura paga recebe 400 (FATURA-33, SALDO-26),
      e valor maior que o total, também (FATURA-26).
    - As compras pendentes, em ordem de data da compra, valor e criação
      (FATURA-22), são pagas inteiras enquanto o valor dá (FATURA-21); a
      compra em que o valor acaba é dividida (FATURA-23), e as que não
      cabem vão para a primeira fatura seguinte não paga, criada se faltar
      (FATURA-24, FATURA-25).
    - Grava o `PagamentoDeFatura` com um item por compra (AD-040).
    Devolve o pagamento.
    """
    from django.db import IntegrityError, transaction
    from django.db.models.functions import Coalesce
    from rest_framework.exceptions import ValidationError

    from transactions.models import Transaction

    from .models import CreditCardInvoice, ItemDePagamento, PagamentoDeFatura
    from .saldo import recalcular

    with transaction.atomic():
        fatura = CreditCardInvoice.objects.select_for_update().select_related('card').get(pk=fatura.pk)
        if chave is not None:
            anterior = PagamentoDeFatura.objects.filter(user=usuario, chave=chave).first()
            if anterior is not None:
                if (anterior.fatura_id, anterior.valor, anterior.conta_id, anterior.data) != (
                    fatura.pk, valor, conta.pk, data,
                ):
                    raise ValidationError({'detail': CHAVE_COM_OUTROS_DADOS})
                return anterior
        if fatura.status == 'PAID':
            raise ValidationError({'detail': FATURA_JA_PAGA})
        recalcular_totais(fatura.pk)
        fatura.refresh_from_db(fields=['total_amount'])
        if valor > fatura.total_amount:
            raise ValidationError({'detail': VALOR_MAIOR_QUE_O_TOTAL})

        cartao = fatura.card
        try:
            # Savepoint: com ATOMIC_REQUESTS, o erro de restrição sem ele
            # inutilizaria a transação da requisição
            with transaction.atomic():
                pagamento = PagamentoDeFatura.objects.create(
                    user=usuario, fatura=fatura, conta=conta, valor=valor, data=data, chave=chave,
                )
        except IntegrityError:
            # A mesma chave gravada ao mesmo tempo por um pedido de outra
            # fatura, que tem outra trava (FATURA-32)
            raise ValidationError({'detail': CHAVE_COM_OUTROS_DADOS})
        pendentes = Transaction.objects.filter(
            invoice=fatura, type='CREDIT_CARD', status='PENDING',
            user_id=cartao.user_id,  # Só compras do dono do cartão (ISOL-14)
        ).select_related('credit_card').order_by(Coalesce('purchase_date', 'date'), 'amount', 'created_at')

        resta = valor
        seguinte = None
        for compra in pendentes:
            if resta > 0 and compra.amount <= resta:
                compra.status = 'COMPLETED'
                compra.account = conta
                compra.payment_date = data
                compra.save()
                resta -= compra.amount
                ItemDePagamento.objects.create(pagamento=pagamento, tipo=ItemDePagamento.PAGA, compra=compra)
                continue

            if seguinte is None:
                seguinte = primeira_nao_paga(cartao, *mes_seguinte(fatura.month, fatura.year))
            if resta > 0:
                valor_original, descricao_original = compra.amount, compra.description
                restante = _dividir(compra, resta, conta, data, seguinte)
                resta = Decimal('0.00')
                ItemDePagamento.objects.create(
                    pagamento=pagamento, tipo=ItemDePagamento.DIVIDIDA, compra=compra,
                    restante=restante, valor_original=valor_original,
                    descricao_original=descricao_original,
                )
            else:
                colocar(compra, seguinte)
                ItemDePagamento.objects.create(pagamento=pagamento, tipo=ItemDePagamento.MOVIDA, compra=compra)

        fatura.status = 'PAID'
        fatura.save()
        if seguinte is not None:
            pagamento.fatura_seguinte = seguinte
            pagamento.save(update_fields=['fatura_seguinte'])
        recalcular_totais(fatura.pk, seguinte.pk if seguinte else None)
        recalcular(conta.pk, cartao.account_id)
    return pagamento


def _estornar_sem_registro(fatura):
    """
    Estorno de um pagamento feito antes desta feature, sem registro: as
    compras pagas da fatura voltam a pendentes, na conta do cartão e sem
    data de pagamento (SALDO-24, SALDO-25). As divisões antigas não são
    juntadas. Devolve as contas a recalcular.
    """
    from transactions.models import Transaction

    pagas = Transaction.objects.filter(
        invoice=fatura, type='CREDIT_CARD', status='COMPLETED',
        user_id=fatura.card.user_id,  # Só compras do dono do cartão (ISOL-14)
    )
    contas = set(pagas.values_list('account_id', flat=True))
    pagas.update(status='PENDING', account=fatura.card.account_id, payment_date=None)
    return contas


def _voltar_a_pendente(compra, conta_do_cartao):
    compra.status = 'PENDING'
    compra.account_id = conta_do_cartao
    compra.payment_date = None


def estornar(usuario, fatura):
    """
    Estorna o pagamento ativo da fatura, tudo num `atomic` (FATURA-28).
    - Relê a fatura sob trava; fatura não paga recebe 400 (SALDO-27).
    - Sem registro (pagamento anterior a esta feature), segue o caminho
      antigo.
    - Se a fatura que recebeu o restante ou as compras movidas já está
      paga, recusa com 400 (FATURA-38).
    - PAGA volta a pendente, na conta do cartão e sem data de pagamento
      (FATURA-34). DIVIDIDA volta a pendente com a descrição original e o
      valor pago mais o valor atual do restante, que é excluído; restante
      excluído pelo usuário não volta (FATURA-35). MOVIDA volta para a
      fatura original se ainda existe, está pendente e está na seguinte
      (FATURA-36).
    - A fatura volta a `OPEN`, exibida como aberta ou fechada pela data de
      hoje (FATURA-37), e o pagamento recebe `estornado_em`; o registro
      nunca é apagado (FATURA-30).
    """
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError

    from .models import CreditCardInvoice, ItemDePagamento
    from .saldo import recalcular

    with transaction.atomic():
        fatura = CreditCardInvoice.objects.select_for_update().select_related('card').get(pk=fatura.pk)
        if fatura.status != 'PAID':
            raise ValidationError({'detail': FATURA_NAO_PAGA})
        conta_do_cartao = fatura.card.account_id
        pagamento = fatura.pagamentos.filter(estornado_em__isnull=True).order_by('-criado_em').first()

        seguinte_id = None
        if pagamento is None:
            contas = _estornar_sem_registro(fatura)
        else:
            seguinte_id = pagamento.fatura_seguinte_id
            if seguinte_id and CreditCardInvoice.objects.filter(pk=seguinte_id, status='PAID').exists():
                raise ValidationError({'detail': ESTORNE_A_SEGUINTE})
            contas = {pagamento.conta_id}
            for item in pagamento.itens.select_related('compra', 'restante'):
                compra = item.compra
                if compra is None:
                    continue
                if item.tipo == ItemDePagamento.PAGA:
                    contas.add(compra.account_id)
                    _voltar_a_pendente(compra, conta_do_cartao)
                    compra.save()
                elif item.tipo == ItemDePagamento.DIVIDIDA:
                    contas.add(compra.account_id)
                    restante = item.restante
                    if restante is not None:
                        compra.amount += restante.amount
                        restante.delete()
                    compra.description = item.descricao_original
                    _voltar_a_pendente(compra, conta_do_cartao)
                    compra.save()
                elif compra.status == 'PENDING' and compra.invoice_id == seguinte_id:
                    colocar(compra, fatura)

            pagamento.estornado_em = timezone.now()
            pagamento.save(update_fields=['estornado_em'])

        fatura.status = 'OPEN'
        fatura.save()
        recalcular_totais(fatura.pk, seguinte_id)
        recalcular(*contas, conta_do_cartao)

def resposta_do_pagamento(pagamento):
    """
    O corpo da resposta do pagamento, montado só a partir do registro: a
    repetição da mesma chave recebe exatamente o mesmo corpo, inclusive
    depois de um estorno (FATURA-30).
    """
    return {
        'status': 'Pagamento processado com sucesso.',
        'payment': {
            'id': str(pagamento.pk),
            'invoice_id': str(pagamento.fatura_id),
            'amount': f'{pagamento.valor:.2f}',
            'account_id': str(pagamento.conta_id),
            'date': pagamento.data.isoformat(),
            'idempotency_key': str(pagamento.chave) if pagamento.chave else None,
        },
    }
