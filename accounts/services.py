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
            type__in=['INCOME', 'TRANSFER_IN']
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # Despesas, Transferências Enviadas e Pagamento de Fatura (Saídas)
        # Nota: CREDIT_CARD não sai da conta (sai do limite do cartão). Só INVOICE_PAYMENT sai da conta.
        expenses = Transaction.objects.filter(
            account=account,
            type__in=['EXPENSE', 'TRANSFER_OUT', 'INVOICE_PAYMENT']
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
        Processa o pagamento de uma fatura.
        - Cria despesa na conta bancária.
        - Atualiza status da fatura e das transações.
        - Gera rotativo se pagamento parcial.
        """
        from transactions.services import TransactionService
        from transactions.models import Transaction

        # 1. Validar se a fatura tem valor a pagar
        # Recalcular total amount pelas transactions para garantir?
        # Por enquanto confiar no invoice.total_amount ou somar transactions 'OPEN'?
        # Vamos somar transactions vinculadas.
        pending_transactions = invoice.transactions.exclude(type='INVOICE_PAYMENT') 
        # Cuidado: invoice.transactions related manager.
        # As transações de despesa são CREDIT_CARD.
        # INVOICE_PAYMENT não deve estar vinculado a invoice dessa forma (geralmente nao tem FK pra invoice, ou tem?)
        # Transaction model tem `invoice = models.ForeignKey(...)`.
        
        real_total = Decimal('0.00')
        for t in pending_transactions:
            real_total += t.amount # TODO: Filtrar apenas não estornadas/pagas?
            
        if real_total <= 0:
             # Se for 0, marca como paga direto
             invoice.status = 'PAID'
             invoice.save()
             return

        # 2. Criar saída da conta (Pagamento de Fatura)
        # Usar TransactionService para criar a despesa na conta
        # Tipo deve ser INVOICE_PAYMENT para não bagunçar relatórios de categorias
        payment_txn = Transaction.objects.create(
            user=user,
            type='INVOICE_PAYMENT',
            account=account,
            amount=amount,
            date=date,
            description=f"Pagamento Fatura {invoice.card.name} ({invoice.month}/{invoice.year})",
            category=None # Ou categoria específica "Pagamento de Fatura"?
        )
        
        # 3. Atualizar Fatura e Transações
        # Cenário 1: Pagamento Total (ou maior)
        if amount >= real_total:
            invoice.status = 'PAID'
            invoice.total_amount = real_total # Atualiza com o real
            invoice.save()
            
            # Opcional: Marcar transações como pagas? 
            # Como o modelo Transaction não tem status booleano 'paid', assumimos que se invoice está PAID, elas estão pagas.
            
        # Cenário 2: Pagamento Parcial (Rotativo)
        else:
            remaining = real_total - amount
            
            # Marca a fatura atual como FECHADA/PAGA pois foi "resolvida" com o pagamento parcial + rolagem
            invoice.status = 'PAID' 
            invoice.total_amount = real_total
            invoice.save()
            
            # Criar Transação de Rotativo na PRÓXIMA fatura
            # Data da nova despesa: Hoje ou vencimento da próxima?
            # Vencimento da próxima.
            
            # Achar próxima fatura
            next_month = invoice.month + 1
            next_year = invoice.year
            if next_month > 12:
                next_month = 1
                next_year += 1
                
            # Usar create_credit_card_expense para gerar o rotativo
            TransactionService.create_credit_card_expense(
                user=user,
                card=invoice.card,
                amount=remaining,
                date=date, # Data hoje
                description=f"Rotativo Fatura {invoice.month}/{invoice.year} (Restante)",
                category=None, # Categoria "Juros/Rotativo"?
                installments=1
            )
            
            # TODO: Adicionar juros se necessário (User pediu "Restante + Juros" no prompt, mas não deu taxa. Faremos só o restante por enquanto).
