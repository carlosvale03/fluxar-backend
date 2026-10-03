from decimal import Decimal
from datetime import date
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import Account, CreditCard, CreditCardInvoice

from .faturas import FATURA_JA_PAGA, FATURA_NAO_PAGA

class AccountService:
    @staticmethod
    def get_balance(account: Account) -> Decimal:
        """
        Saldo da conta pela regra SALDO-01 (accounts/saldo.py).
        """
        from .saldo import calcular

        return calcular(account)

class CreditCardService:
    @staticmethod
    def get_invoice_data(card: CreditCard):
        """
        Retorna dados da fatura atual e limite disponível.
        Refatoração (UX):
        - Fatura Atual: A primeira fatura não paga (OPEN ou CLOSED) em ordem cronológica.
        - Limite Utilizado: Soma de TODAS as transações 'CREDIT_CARD' pendentes do cartão.
        """
        from .faturas import limite_disponivel

        # 1. Limite disponível pela fórmula única (FATURA-42)
        available_limit = limite_disponivel(card)

        # 2. Fatura Atual (Próxima fatura a ser paga)
        # Busca a fatura mais antiga que não esteja PAGA
        current_invoice = card.invoices.exclude(status='PAID').order_by('year', 'month').first()
        
        current_invoice_total = Decimal('0.00')
        if current_invoice:
            current_invoice_total = current_invoice.total_amount

        return {
            'current_invoice_total': current_invoice_total,
            'available_limit': available_limit
        }

    @staticmethod
    def pay_invoice(user, invoice: CreditCardInvoice, account: Account, amount: Decimal, date: date, chave=None):
        """
        Paga a fatura pela regra de `accounts/faturas.py` (`pagar`): atômico,
        sob trava, com a divisão e a rolagem registradas (FATURA-21 a
        FATURA-28, AD-040) e idempotente pela `chave` (FATURA-30 a FATURA-33).
        Devolve o `PagamentoDeFatura`.
        """
        from .faturas import pagar

        return pagar(user, invoice, account, amount, date, chave)

    @staticmethod
    @transaction.atomic
    def unpay_invoice(user, invoice: CreditCardInvoice):
        """
        Reverte o pagamento de uma fatura (SALDO-24, SALDO-25, SALDO-27).
        - Só a fatura paga pode ser estornada; a releitura sob trava recusa
          o estorno que chega depois de outro.
        - As compras pagas voltam ao estado de antes do pagamento: pendentes,
          na conta do cartão (como `create_credit_card_expense` as cria) e
          sem data de pagamento. O recálculo devolve à conta de pagamento
          exatamente o valor pago (AD-038).
        - Num pagamento parcial, a parte "(Parcial)" volta a pendente e a
          "(Restante)" continua na fatura seguinte; juntar as duas fica com a
          feature `faturas`.
        - Invoice volta para OPEN.
        """
        from .saldo import recalcular

        invoice = CreditCardInvoice.objects.select_for_update().select_related('card').get(pk=invoice.pk)
        if invoice.status != 'PAID':
            raise ValidationError({'detail': FATURA_NAO_PAGA})

        # 1. Buscar transações pagas
        paid_txs = invoice.transactions.filter(
            type='CREDIT_CARD',
            status='COMPLETED',
            user_id=invoice.card.user_id, # Só compras do dono do cartão (ISOL-14)
        )
        contas_pagadoras = set(paid_txs.values_list('account_id', flat=True))

        # 2. Reverter Status, conta e data de pagamento
        paid_txs.update(status='PENDING', account=invoice.card.account_id, payment_date=None)
        recalcular(*contas_pagadoras, invoice.card.account_id)

        # 3. Reabrir Fatura
        invoice.status = 'OPEN'
        invoice.save()
