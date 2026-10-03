from decimal import Decimal
from datetime import date
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
    def unpay_invoice(user, invoice: CreditCardInvoice):
        """
        Estorna o pagamento da fatura pela regra de `accounts/faturas.py`
        (`estornar`): desfaz exatamente o que o pagamento registrou
        (FATURA-34 a FATURA-38, SALDO-24 a SALDO-27).
        """
        from .faturas import estornar

        estornar(user, invoice)
