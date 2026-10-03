import uuid
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Transaction, Category
from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCard, CreditCardInvoice
from accounts.services import CreditCardService
from core.fields import CONTA_NAO_ENCONTRADA

MESMA_CONTA = 'A conta de origem e a de destino devem ser diferentes.'

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
        Cria a transferência: a saída na origem e a entrada no destino, no
        mesmo `atomic`, com o mesmo status e a descrição enviada (SALDO-11,
        SALDO-12). Origem igual ao destino recebe 400 (SALDO-17), e conta
        excluída de qualquer lado também (SALDO-35): o aporte e o resgate de
        meta passam por aqui com o cofrinho, que não vem da requisição.
        Devolve o `transfer_id` que liga as duas pernas.
        """
        if account_from.pk == account_to.pk:
            raise ValidationError({'detail': MESMA_CONTA})
        if Account.objects.filter(pk__in=[account_from.pk, account_to.pk], is_active=False).exists():
            raise ValidationError({'detail': CONTA_NAO_ENCONTRADA})

        transfer_uid = uuid.uuid4()
        for tipo, conta in (('TRANSFER_OUT', account_from), ('TRANSFER_IN', account_to)):
            Transaction.objects.create(
                user=user, type=tipo, status='COMPLETED', account=conta,
                amount=amount, date=date, description=description,
                transfer_id=transfer_uid,
            )
        return transfer_uid

    @staticmethod
    @transaction.atomic
    def editar_transferencia(perna, dados, user):
        """
        Edita uma perna de transferência e mantém a outra igual (SALDO-13 a
        SALDO-15). Valor, data e status valem para as duas pernas; a
        descrição é de cada uma. `account` é a conta da perna editada e
        `target_account_id`, a da outra perna. O tipo não muda. As contas
        antigas e as novas são recalculadas (AD-038).
        """
        from accounts.saldo import recalcular
        from .serializers import TIPO_NAO_ALTERAVEL

        dados = dict(dados)
        tipo = dados.pop('type', perna.type)
        if tipo != perna.type:
            raise ValidationError({'type': [TIPO_NAO_ALTERAVEL]})

        parceira = Transaction.objects.select_for_update().filter(
            transfer_id=perna.transfer_id, user_id=user.pk,
        ).exclude(pk=perna.pk).first()
        contas_antigas = [perna.account_id, parceira.account_id if parceira else None]

        conta_da_outra = dados.pop('target_account_id', None)
        conta = dados.get('account', perna.account)
        if conta is None:
            raise ValidationError({'account': [CONTA_NAO_ENCONTRADA]})
        if parceira is not None:
            conta_da_outra = conta_da_outra or parceira.account
            if conta_da_outra is not None and conta_da_outra.pk == conta.pk:
                raise ValidationError({'detail': MESMA_CONTA})

        for campo, valor in dados.items():
            setattr(perna, campo, valor)
        perna.save()

        if parceira is not None:
            for campo in ('amount', 'date', 'status'):
                if campo in dados:
                    setattr(parceira, campo, dados[campo])
            parceira.account = conta_da_outra
            parceira.save()

        recalcular(*contas_antigas, perna.account_id, parceira.account_id if parceira else None)
        return perna

    @staticmethod
    @transaction.atomic
    def create_credit_card_expense(user, card, amount, date, description, category, tags=None, installments=1):
        """
        Cria despesa de Cartão de Crédito.
        Suporta parcelamento (Installments).
        """
        if installments < 1:
            raise ValidationError("Número de parcelas deve ser pelo menos 1.")
        # A compra fica na conta de pagamento do cartão; conta excluída não
        # recebe movimentação nova (SALDO-35, AD-003)
        if card.account_id is not None and not Account.objects.filter(
            pk=card.account_id, is_active=True,
        ).exists():
            raise ValidationError({'detail': CONTA_NAO_ENCONTRADA})

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
        """
        A fatura do cartão que vence em `month`/`year`, pela regra única de
        `accounts/faturas.py` (FATURA-01 a FATURA-04, FATURA-07).
        """
        return obter_fatura(card, month, year)

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
