from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from .models import Account, CreditCard, CreditCardInvoice

class AccountService:
    @staticmethod
    def get_balance(account: Account) -> Decimal:
        """
        Calcula o saldo atual da conta.
        Por enquanto considera apenas o saldo inicial.
        Futuramente irá somar receitas e subtrair despesas/transferências.
        """
        from django.db.models import Sum
        from transactions.models import Transaction

        balance = account.initial_balance

        # Receitas e Transferências Recebidas (Entradas)
        incomes = Transaction.objects.filter(
            account=account, 
            status='COMPLETED', # Apenas efetivadas
            type__in=['INCOME', 'TRANSFER_IN']
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # Despesas, Transferências Enviadas e Pagamento de Fatura (Saídas)
        # Nota: CREDIT_CARD "PAGO" (COMPLETED) impacta o saldo da conta vinculada.
        expenses = Transaction.objects.filter(
            account=account,
            status='COMPLETED', # Apenas efetivadas
            type__in=['EXPENSE', 'TRANSFER_OUT', 'INVOICE_PAYMENT', 'CREDIT_CARD']
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        return balance + incomes - expenses

class CreditCardService:
    @staticmethod
    def get_invoice_data(card: CreditCard):
        """
        Retorna dados da fatura atual e limite disponível.
        """
        # 1. Identificar fatura aberta atual
        # Simulação simples da fatura atual baseada na data de hoje
        # TODO: Implementar lógica real de busca/criação de fatura
        
        current_invoice_total = Decimal('0.00')
        
        # Tenta pegar a fatura aberta atual
        today = timezone.localtime().date()
        current_invoice = card.invoices.filter(
            status='OPEN', 
            month=today.month, 
            year=today.year
        ).first()

        if current_invoice:
            current_invoice_total = current_invoice.total_amount

        available_limit = card.limit - current_invoice_total

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
        - Se purchase_date.day < closing_day: Fatura do mês corrente.
        - Se purchase_date.day >= closing_day: Fatura do mês seguinte.
        """
        if purchase_date.day < card.closing_day:
            due_month = purchase_date.month
            due_year = purchase_date.year
        else:
            due_month = purchase_date.month + 1
            due_year = purchase_date.year
            if due_month > 12:
                due_month = 1
                due_year += 1
        
        # Define o dia com base no due_day do cartão
        try:
            return date(due_year, due_month, card.due_day)
        except ValueError:
            import calendar
            last_day = calendar.monthrange(due_year, due_month)[1]
            return date(due_year, due_month, last_day)

    @staticmethod
    def pay_invoice(user, invoice: CreditCardInvoice, account: Account, amount: Decimal, date: date):
        """
        Processa pagamento de fatura atualizando as transações originais.
        Refatoração:
        - Não cria mais 'INVOICE_PAYMENT'.
        - Despesas pagas viram saídas da `account` na data do pagamento.
        - Despesas não pagas (parcial) são movidas para a próxima fatura (Rollover).
        """
        from transactions.services import TransactionService
        
        # 1. Buscar transações pendentes desta fatura
        # Apenas despesas de cartão, ignorando eventuais ajustes manuais por enquanto
        pending_txs = invoice.transactions.filter(
            type='CREDIT_CARD', 
            status='PENDING'
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
    def unpay_invoice(user, invoice: CreditCardInvoice):
        """
        Reverte o pagamento de uma fatura.
        - Transações COMPLETED voltam para PENDING.
        - Invoice volta para OPEN.
        """
        # 1. Buscar transações pagas
        paid_txs = invoice.transactions.filter(
            type='CREDIT_CARD',
            status='COMPLETED'
        )
        
        # 2. Reverter Status
        paid_txs.update(status='PENDING')
        
        # 3. Reabrir Fatura
        invoice.status = 'OPEN'
        invoice.save()
