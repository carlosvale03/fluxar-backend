import uuid
from datetime import date
from django.db import transaction
from django.db.models import F, Q
from rest_framework.exceptions import ValidationError

from .models import Transaction, Category
from accounts.faturas import alocar_parcelas, colocar, dividir_valor, obter_fatura
from accounts.models import Account, CreditCard
from core.fields import CONTA_NAO_ENCONTRADA

MESMA_CONTA = 'A conta de origem e a de destino devem ser diferentes.'
COMPRA_EM_FATURA_PAGA = 'Estorne o pagamento da fatura antes de alterar esta compra.'


def grupo_da_compra(parcela):
    """
    A compra inteira de uma parcela: a parcela raiz (`parent_transaction`
    nulo) e as que apontam para ela, só do dono da parcela (ISOL-14), em
    ordem de parcela.
    """
    raiz = parcela.parent_transaction_id or parcela.pk
    return Transaction.objects.filter(
        Q(pk=raiz) | Q(parent_transaction_id=raiz), user_id=parcela.user_id,
    ).select_related('invoice').order_by(F('installment_number').asc(nulls_first=True), 'created_at')


def em_fatura_paga(parcelas):
    """Se alguma das parcelas está numa fatura paga."""
    return any(p.invoice_id and p.invoice.status == 'PAID' for p in parcelas)

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
    def editar_compra(parcela, dados, escopo='SINGLE'):
        """
        Edita uma parcela de compra no cartão.
        - Parcela em fatura paga não muda (FATURA-19).
        - O `date` enviado é ignorado: ele vem da fatura (AD-039).
        - Data da compra ou cartão diferente vale para a compra inteira: todas
          as parcelas recebem a data e o cartão novos e são realocadas
          (FATURA-17); recusado se alguma parte está em fatura paga. A data
          atual é `purchase_date or date`, para que uma compra antiga salva
          com a data carregada não mude.
        - Valor e categoria seguem o escopo (`SINGLE` ou `ALL_FUTURE`); os
          demais campos valem só para a parcela editada.
        """
        dados = dict(dados)
        dados.pop('date', None)
        dados.pop('type', None)
        nova_data = dados.pop('purchase_date', None)
        novo_cartao = dados.pop('credit_card', None)

        grupo = list(grupo_da_compra(parcela))
        if em_fatura_paga([p for p in grupo if p.pk == parcela.pk]):
            raise ValidationError({'detail': COMPRA_EM_FATURA_PAGA})

        data_atual = parcela.purchase_date or parcela.date
        muda_data = nova_data is not None and nova_data != data_atual
        muda_cartao = novo_cartao is not None and novo_cartao.pk != parcela.credit_card_id
        if muda_data or muda_cartao:
            if em_fatura_paga(grupo):
                raise ValidationError({'detail': COMPRA_EM_FATURA_PAGA})
            cartao = novo_cartao if muda_cartao else parcela.credit_card
            data = nova_data if muda_data else (grupo[0].purchase_date or grupo[0].date)
            for p, fatura in zip(grupo, alocar_parcelas(cartao, data, len(grupo))):
                alvo = parcela if p.pk == parcela.pk else p
                alvo.purchase_date = data
                if muda_cartao:
                    alvo.credit_card = cartao
                    alvo.account = cartao.account
                colocar(alvo, fatura)

        if escopo == 'ALL_FUTURE' and parcela.is_installment:
            futuras = [
                p for p in grupo
                if p.pk != parcela.pk and p.installment_number is not None
                and p.installment_number > parcela.installment_number
            ]
            if em_fatura_paga(futuras):
                raise ValidationError({'detail': COMPRA_EM_FATURA_PAGA})
            for p in futuras:
                # Descrição não propaga, para manter o n/total
                for campo in ('amount', 'category'):
                    if campo in dados:
                        setattr(p, campo, dados[campo])
                p.save()

        for campo, valor in dados.items():
            setattr(parcela, campo, valor)
        parcela.save()
        return parcela

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

        # Uma parcela por fatura não paga, a partir da fatura da data da
        # compra (FATURA-12, FATURA-15); a diferença do arredondamento fica na
        # primeira (FATURA-13). Cada parcela guarda a data real da compra, e o
        # `date` é o vencimento da fatura, gravado junto com ela como no
        # `colocar` (FATURA-16, AD-039).
        faturas = alocar_parcelas(card, date, installments)
        valores = dividir_valor(amount, installments)
        parcelado = installments > 1

        transactions = []
        parent_txn = None
        for i, (fatura, val) in enumerate(zip(faturas, valores)):
            desc = f"{description} ({i+1}/{installments})" if parcelado else description
            t = Transaction.objects.create(
                user=user,
                type='CREDIT_CARD',
                status='PENDING', # Pendente até o pagamento da fatura
                account=card.account, # Conta de pagamento do cartão
                credit_card=card,
                invoice=fatura,
                date=fatura.due_date,
                amount=val,
                purchase_date=date,
                description=desc,
                category=category,
                is_installment=parcelado,
                installment_number=(i + 1) if parcelado else None,
                installment_total=installments if parcelado else None,
                parent_transaction=parent_txn,
            )

            if tags:
                t.tags.set(tags)
            if i == 0 and parcelado:
                parent_txn = t
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
