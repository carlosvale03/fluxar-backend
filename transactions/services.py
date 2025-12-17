from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Transaction, TransferGroup, Category
from accounts.models import Account, CreditCard, CreditCardInvoice

class TransactionService:
    @staticmethod
    def create_income(user, account, amount, date, description, category, tags=None):
        """
        Cria uma RECEITA e atualiza o saldo da conta (futuro).
        """
        t = Transaction.objects.create(
            user=user,
            type='INCOME',
            account=account,
            amount=amount,
            date=date,
            description=description,
            category=category
        )
        if tags:
            t.tags.set(tags)
        return t

    @staticmethod
    def create_expense(user, account, amount, date, description, category, tags=None):
        """
        Cria uma DESPESA.
        """
        t = Transaction.objects.create(
            user=user,
            type='EXPENSE',
            account=account,
            amount=amount,
            date=date,
            description=description,
            category=category
        )
        if tags:
            t.tags.set(tags)
        return t

    @staticmethod
    @transaction.atomic
    def create_transfer(user, account_from, account_to, amount, date, description="Transferência"):
        """
        Cria transferencia entre contas (Atomic).
        Gera 2 transações ligadas por um TransferGroup.
        """
        group = TransferGroup.objects.create()
        
        # Saída
        t_out = Transaction.objects.create(
            user=user, type='TRANSFER_OUT', account=account_from,
            amount=amount, date=date, description=f"TR - Para: {account_to.name}",
            transfer_group=group
        )
        
        # Entrada
        t_in = Transaction.objects.create(
            user=user, type='TRANSFER_IN', account=account_to,
            amount=amount, date=date, description=f"TR - De: {account_from.name}",
            transfer_group=group
        )
        return group

    @staticmethod
    def create_credit_card_expense(user, card, amount, date, description, category, tags=None, installments=1):
        """
        Cria despesa de Cartão de Crédito.
        Suporta parcelamento (Installments).
        """
        if installments < 1:
            raise ValidationError("Número de parcelas deve ser pelo menos 1.")

        transactions = []
        installment_amount = amount / Decimal(installments)
        # Ajuste de centavos na primeira ou ultima parcela? 
        # Simples: arredondar todas e jogar diferença na primeira.
        installment_amount = round(installment_amount, 2)
        diff = amount - (installment_amount * installments)
        
        # Lógica de faturas
        # Precisamos achar a fatura baseada na data da compra E NO DIA DE FECHAMENTO.
        # Se date.day > closing_day, vai para a fatura do mês seguinte.
        
        # Data base para cálculo
        current_date_base = date
        
        # Se compra feita após fechamento, "pula" um mês para a primeira parcela
        if current_date_base.day > card.closing_day:
            # Ex: fechamento dia 10. Compra dia 11/Jan. Fatura é Fev.
            current_date_base = current_date_base + relativedelta(months=1)
        
        # Definir dia de vencimento da fatura
        # A fatura vence no due_day do mês target.
        
        # Loop de parcelas
        parent = None
        
        for i in range(installments):
            num = i + 1
            
            # Valor da parcela
            val = installment_amount
            if i == 0:
                val += diff # Ajuste na primeira
            
            # Calcular mês/ano da fatura desta parcela
            # A data base já está ajustada para a primeira parcela.
            # Parcelas seguintes apenas somam meses.
            target_date = current_date_base + relativedelta(months=i)
            
            # Buscar ou Criar Fatura (Invoice)
            # A fatura é identificada por Month/Year.
            # O vencimento (due_date) é calculado.
            invoice = TransactionService._get_or_create_invoice(card, target_date.month, target_date.year)
            
            # Criar transação
            t = Transaction.objects.create(
                user=user,
                type='CREDIT_CARD',
                credit_card=card,
                invoice=invoice,
                amount=val,
                date=date, # Data da compra se mantém a original para histórico? Ou data da parcela? 
                           # Geralmente mantém data da compra, mas o vinculo com Invoice define quando paga.
                description=f"{description} ({num}/{installments})" if installments > 1 else description,
                category=category,
                is_installment=(installments > 1),
                installment_number=num if installments > 1 else None,
                installment_total=installments if installments > 1 else None,
                parent_transaction=parent 
            )
            
            if tags:
                t.tags.set(tags)
            
            if i == 0 and installments > 1:
                parent = t # A primeira vira pai das outras
                t.parent_transaction = None # Ela é orfã ou pai de si mesma? Melhor None.
                t.save()
            
            transactions.append(t)
            
        return transactions

    @staticmethod
    def _get_or_create_invoice(card, month, year):
        invoice, created = CreditCardInvoice.objects.get_or_create(
            card=card, month=month, year=year,
            defaults={
                'closing_date': date(year, month, card.closing_day) if card.closing_day <= 28 else date(year, month, 28), # Simplificação
                'due_date': date(year, month, card.due_day) if card.due_day <= 28 else date(year, month, 28)
                # TODO: Melhorar calculo de datas fim de mês (29/30/31)
            }
        )
        return invoice
