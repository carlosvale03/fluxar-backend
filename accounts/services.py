from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Account, CreditCard, CreditCardInvoice

FATURA_JA_PAGA = 'Fatura já está paga.'
FATURA_NAO_PAGA = 'Esta fatura não está paga.'

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
        from django.db.models import Sum
        from transactions.models import Transaction

        # 1. Limite Utilizado (Total pendente no cartão), só compras do dono do cartão (ISOL-14)
        total_pending = Transaction.objects.filter(
            credit_card=card,
            user_id=card.user_id,
            type='CREDIT_CARD',
            status='PENDING'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        available_limit = card.limit - total_pending

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
    def get_next_due_date(card: CreditCard) -> date:
        """
        Calcula próxima data de vencimento baseada no dia atual e dia de fechamento.
        """
        today = timezone.localtime().date()
        # Se hoje for antes do fechamento, vence neste mês (se due_day > closing_day) ou no próximo?
        # Lógica simplificada:
        # Se hoje <= closing_day, a fatura desse mês está aberta.
        # Vencimento geralmente é X dias após fechamento. 
        # Aqui, vamos usar apenas o due_day do mês atual ou próximo.
        
        try:
            return date(today.year, today.month, card.due_day)
        except ValueError: # Ex: dia 31 em mês de 30 dias
             return date(today.year, today.month, 28) # Fallback simples

    @staticmethod
    def calculate_due_date(card: CreditCard, purchase_date: date) -> date:
        """
        Calcula a data de vencimento da fatura onde a compra cairá.
        Regra:
        1. Se a compra foi feita no dia de fechamento ou depois, vai para a próxima fatura.
        2. O vencimento é relativo ao mês de fechamento.
        """
        # 1. Determina o Ciclo (Mês de Referência do Fechamento)
        if purchase_date.day >= card.closing_day:
            # Comprou no "Melhor Dia" ou depois: vai para o fechamento do próximo mês
            closing_month_date = purchase_date + relativedelta(months=1)
        else:
            # Comprou antes do fechamento: fecha neste mês
            closing_month_date = purchase_date
            
        closing_month = closing_month_date.month
        closing_year = closing_month_date.year
        
        # 2. Determina a data de vencimento
        # Se o dia de vencimento <= dia de fechamento (ex: 4 <= 28), vence no mês seguinte ao fechamento.
        # Se o dia de vencimento > dia de fechamento (ex: 15 > 5), vence no mesmo mês do fechamento.
        if card.due_day <= card.closing_day:
            due_date = date(closing_year, closing_month, 1) + relativedelta(months=1, day=card.due_day)
        else:
            due_date = date(closing_year, closing_month, card.due_day)
            
        return due_date

    @staticmethod
    @transaction.atomic
    def pay_invoice(user, invoice: CreditCardInvoice, account: Account, amount: Decimal, date: date):
        """
        Processa pagamento de fatura atualizando as transações originais.
        Refatoração:
        - Não cria mais 'INVOICE_PAYMENT'.
        - Despesas pagas viram saídas da `account` na data do pagamento.
        - Despesas não pagas (parcial) são movidas para a próxima fatura (Rollover).
        """
        from transactions.services import TransactionService

        # Relê a fatura sob trava: de duas tentativas simultâneas, a segunda
        # espera a primeira e encontra a fatura já paga (SALDO-26)
        invoice = CreditCardInvoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status == 'PAID':
            raise ValidationError({'detail': FATURA_JA_PAGA})

        # 1. Buscar transações pendentes desta fatura
        # Apenas despesas de cartão, ignorando eventuais ajustes manuais por enquanto
        pending_txs = invoice.transactions.filter(
            type='CREDIT_CARD', 
            status='PENDING',
            user_id=invoice.card.user_id, # Só compras do dono do cartão (ISOL-14)
        ).order_by('date', 'amount')
        
        remaining_payment = amount
        paid_transactions = []
        
        # Próxima fatura (para rollover)
        next_month = invoice.month + 1
        next_year = invoice.year
        if next_month > 12:
            next_month = 1
            next_year += 1
            
        next_invoice = None # Lazy load
        
        # 2. Processar pagamentos
        for tx in pending_txs:
            if remaining_payment <= 0:
                # Acabou o dinheiro do pagamento. O resto é rollover.
                if not next_invoice:
                    next_invoice = TransactionService._get_or_create_invoice(invoice.card, next_month, next_year)
                
                # Move para próxima fatura
                tx.invoice = next_invoice
                tx.save()
                continue
            
            if tx.amount <= remaining_payment:
                # Paga a transação inteira
                tx.status = 'COMPLETED'
                tx.account = account 
                tx.payment_date = date # Data do pagamento efetivo (não altera data de competência)
                tx.save()
                
                remaining_payment -= tx.amount
                
            else:
                # Paga PARTE da transação (Split)
                pay_amount = remaining_payment
                leftover_amount = tx.amount - pay_amount
                
                # 1. Atualizar a original (parte PAGA)
                # Precisamos clonar dados antes de salvar
                original_desc = tx.description
                original_category = tx.category
                original_tags = list(tx.tags.all())
                
                tx.amount = pay_amount
                tx.status = 'COMPLETED'
                tx.account = account
                tx.payment_date = date # Data do pagamento
                tx.description = f"{original_desc} (Parcial)"
                tx.save()
                
                # 2. Criar a parte RESTANTE (Rollover)
                if not next_invoice:
                    next_invoice = TransactionService._get_or_create_invoice(invoice.card, next_month, next_year)
                    
                from transactions.models import Transaction
                # Criar nova transação para o resto
                new_tx = Transaction.objects.create(
                    user=user,
                    type='CREDIT_CARD',
                    status='PENDING',
                    account=invoice.card.account, # Volker à conta do cartão (padrão)
                    credit_card=invoice.card,
                    invoice=next_invoice,
                    amount=leftover_amount,
                    date=tx.date, # Mantém data original de competência? Ou vira divida nova?
                                  # Melhor manter original para saberem a origem.
                    description=f"{original_desc} (Restante)",
                    category=original_category,
                    is_installment=tx.is_installment,
                    installment_number=tx.installment_number,
                    installment_total=tx.installment_total,
                    parent_transaction=tx.parent_transaction
                )
                new_tx.tags.set(original_tags)
                
                remaining_payment = Decimal('0.00')

        # 3. Finalizar Fatura
        # Como todas as txs foram tratadas (pagas ou movidas), a fatura deve ficar zerada de pendencias?
        # Sim, mas o registro dela fica PAID.
        # Importante: O signal que criamos (update_invoice_total) vai rodar a cada save acima!
        # Isso vai atualizar o invoice.total_amount em tempo real.
        # Ao final, o total_amount da invoice deve refletir O QUE FOI PAGO nela?
        # Não, o total_amount reflete o que está vinculado a ela.
        # Se movemos as não pagas para a próxima, o total_amount desta vai diminuir para apenas o valor pago.
        # Correto. Contabilidade bate.
        
        invoice.status = 'PAID'
        invoice.save()

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
