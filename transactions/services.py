import uuid
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Transaction, Category
from accounts.models import Account, CreditCard, CreditCardInvoice
from accounts.services import CreditCardService

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
        Gera 2 transações ligadas pelo mesmo transfer_id.
        """
        transfer_uid = uuid.uuid4()
        
        # Saída
        t_out = Transaction.objects.create(
            user=user, type='TRANSFER_OUT', account=account_from,
            amount=amount, date=date, description=f"TR - Para: {account_to.name}",
            transfer_id=transfer_uid
        )
        
        # Entrada
        t_in = Transaction.objects.create(
            user=user, type='TRANSFER_IN', account=account_to,
            amount=amount, date=date, description=f"TR - De: {account_from.name}",
            transfer_id=transfer_uid
        )
        # Retorna o ID de agrupamento
        return transfer_uid

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
        installment_amount = round(installment_amount, 2)
        diff = amount - (installment_amount * installments)
        
        parent_txn = None
        
        for i in range(installments):
            # 1. Data de Compra Virtual da Parcela
            # Simula que a compra foi feita i meses depois, para cair na fatura correta
            purchase_date_virtual = date + relativedelta(months=i)
            
            # 2. Vencimento da Fatura (Competência)
            due_date = CreditCardService.calculate_due_date(card, purchase_date_virtual)
            
            val = installment_amount
            if i == 0:
                val += diff
            
            # Buscar ou Criar Fatura
            invoice = TransactionService._get_or_create_invoice(card, due_date.month, due_date.year)
            
            # Descrição
            desc = description
            if installments > 1:
                desc = f"{description} ({i+1}/{installments})"
            
            t = Transaction.objects.create(
                user=user,
                type='CREDIT_CARD',
                status='PENDING', # Refatoração: Status PENDING até pagar fatura
                account=card.account, # Refatoração: Vincula à conta do cartão (Contábil)
                credit_card=card,
                invoice=invoice,
                amount=val,
                date=due_date, # Data efetiva da despesa na fatura
                description=desc,
                category=category,
                is_installment=(installments > 1),
                installment_number=(i + 1) if installments > 1 else None,
                installment_total=installments if installments > 1 else None,
                parent_transaction=parent_txn
            )
            
            if tags:
                t.tags.set(tags)
            
            if i == 0 and installments > 1:
                parent_txn = t
                t.parent_transaction = None 
                t.save()
                
            transactions.append(t)
            
        return transactions

    @staticmethod
    def _get_or_create_invoice(card, month, year):
        # O 'month' e 'year' aqui referem-se à competência do VENCIMENTO da fatura.
        
        # Calcula a data de vencimento real
        try:
            d_date = date(year, month, card.due_day)
        except ValueError:
            # Fallback para o último dia do mês se o dia não existir (ex: 31 de fevereiro)
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            d_date = date(year, month, last_day)

        # O fechamento ocorre no mês anterior ao vencimento se due_day <= closing_day
        if card.due_day <= card.closing_day:
            closing_ref = d_date - relativedelta(months=1)
        else:
            closing_ref = d_date
            
        try:
            c_date = date(closing_ref.year, closing_ref.month, card.closing_day)
        except ValueError:
            import calendar
            last_day = calendar.monthrange(closing_ref.year, closing_ref.month)[1]
            c_date = date(closing_ref.year, closing_ref.month, last_day)

        # Log para depuração (pode ser removido após validação)
        print(f"[INVOICE] Card: {card.name}, Target: {month}/{year} -> Closes: {c_date}, Due: {d_date}")

        invoice, created = CreditCardInvoice.objects.get_or_create(
            card=card, month=month, year=year,
            defaults={
                'closing_date': c_date,
                'due_date': d_date,
                'status': 'OPEN'
            }
        )
        return invoice

class CategoryService:
    # Definição simples de limites (em futuro mover para tabela de Planos)
    PLAN_LIMITS = {
        'FREE': {'max_roots': 20, 'max_subs_per_root': 5},
        'PREMIUM': {'max_roots': 9999, 'max_subs_per_root': 9999},
        'PREMIUM_PLUS': {'max_roots': 9999, 'max_subs_per_root': 9999},
        'COMMON': {'max_roots': 9999, 'max_subs_per_root': 9999}
    }

    @staticmethod
    def check_limits(user, parent_category=None):
        """
        Verifica se o usuário pode criar nova categoria/subcategoria de acordo com o plano.
        """
        # Se usuário não tem profile/plano ainda, assume FREE
        plan_type = 'FREE'
        if hasattr(user, 'plan'):
             plan_type = str(user.plan).upper()
        
        limits = CategoryService.PLAN_LIMITS.get(plan_type, CategoryService.PLAN_LIMITS['FREE'])

        if parent_category:
            # Validando Subcategoria
            # Filtramos apenas is_active=True para garantir que deletadas não contem.
            qs = Category.objects.filter(user=user, parent=parent_category, is_active=True)
            count = qs.count()
            
            if count >= limits['max_subs_per_root']:
                raise ValidationError(
                    f"Você atingiu o limite de {limits['max_subs_per_root']} subcategorias para esta categoria no plano Grátis."
                )
        else:
            # Validando Categoria Raiz
            count = Category.objects.filter(user=user, parent__isnull=True, is_active=True).count()
            if count >= limits['max_roots']:
                raise ValidationError(
                    f"Você atingiu o limite de {limits['max_roots']} categorias principais no plano Grátis."
                )

    @staticmethod
    def clone_templates_to_user(user):
        """
        Copia todas as categorias marcadas como (is_template=True, parent=None) para o novo usuário.
        Também copia suas subcategorias recursivamente (suportando 1 nível).
        """
        templates = Category.objects.filter(is_template=True, parent__isnull=True)
        
        for template in templates:
            # Copiar Raiz
            new_cat = Category.objects.create(
                user=user,
                name=template.name,
                type=template.type,
                icon=template.icon,
                color=template.color,
                is_template=False, # Agora é instância real do user
                parent=None
            )
            
            # Copiar Subcategorias (Nível 1)
            sub_templates = template.subcategories.all()
            for sub in sub_templates:
                Category.objects.create(
                    user=user,
                    name=sub.name,
                    type=sub.type,
                    icon=sub.icon,
                    color=sub.color,
                    is_template=False,
                    parent=new_cat # Vincula à nova raiz do usuário
                )
