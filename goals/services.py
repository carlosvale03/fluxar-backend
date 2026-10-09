from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from accounts.saldo import travar
from core.datas import hoje
from core.valores import reais
from transactions.models import Transaction
from transactions.services import TransactionService
from .models import Goal, GoalDeposit
from .valores import recalcular, saldo_livre

SEM_COFRINHO = 'Esta meta não possui um cofrinho vinculado.'
META_ARQUIVADA = 'Metas arquivadas não recebem aportes.'
SALDO_LIVRE_INSUFICIENTE = 'O saldo livre do cofrinho é de {valor}.'
VALOR_DA_META_INSUFICIENTE = 'A meta tem {valor} para resgatar.'
COFRINHO_INSUFICIENTE = 'O cofrinho tem só {valor}.'


def _travar(meta, conta):
    """
    Trava as contas envolvidas em ordem de id e, só depois, a meta (META-22),
    na mesma ordem da edição de uma transferência ligada à meta. Devolve a
    meta e o cofrinho lidos de novo, já travados.
    """
    cofrinho_id = Goal.objects.values_list('account_id', flat=True).get(pk=meta.pk)
    contas = travar(cofrinho_id, conta.pk if conta is not None else None)
    meta = Goal.objects.select_for_update().get(pk=meta.pk)
    if not meta.account_id:
        raise ValidationError(SEM_COFRINHO)
    if meta.account_id not in contas:
        # O cofrinho mudou entre a leitura e a trava da meta
        contas.update(travar(meta.account_id))
    return meta, contas[meta.account_id]


def _registrar(meta, tipo, conta, valor, data, descricao, transfer_id=None):
    """
    Grava o registro do aporte ou do resgate; com transferência, ligado às
    duas pernas (AD-045). Depois recalcula a meta.
    """
    pernas = {}
    if transfer_id is not None:
        for perna in Transaction.objects.filter(transfer_id=transfer_id, user_id=meta.user_id):
            pernas['transacao_saida' if perna.type == 'TRANSFER_OUT' else 'transacao_entrada'] = perna
    GoalDeposit.objects.create(
        goal=meta, account=conta, amount=valor, type=tipo, description=descricao, date=data,
        transaction_id=transfer_id, **pernas,
    )
    recalcular(meta.pk)


class GoalService:
    @staticmethod
    @db_transaction.atomic
    def aportar(goal, amount, date_deposit=None, account=None, description=None):
        """
        Aporte na meta (META-12 a META-14, META-21):
        - com `account`, cria a transferência dessa conta para o cofrinho pelas
          regras da spec `saldo`; o próprio cofrinho como origem cai na
          SALDO-17;
        - sem `account`, usa o saldo livre do cofrinho, sem transferência, até
          o valor dele.
        Meta arquivada não recebe aporte; meta concluída recebe (META-23).
        """
        amount = Decimal(str(amount))
        meta, cofrinho = _travar(goal, account)
        if not meta.is_active:
            raise ValidationError(META_ARQUIVADA)
        date_deposit = date_deposit or hoje()
        description = description or f"Aporte na Meta: {meta.name}"

        if account is None:
            livre = saldo_livre(cofrinho)
            if amount > livre:
                raise ValidationError(SALDO_LIVRE_INSUFICIENTE.format(valor=reais(livre)))
            _registrar(meta, 'DEPOSIT', cofrinho, amount, date_deposit, description)
            return meta

        transfer_id = TransactionService.create_transfer(
            user=meta.user, account_from=account, account_to=cofrinho,
            amount=amount, date=date_deposit, description=description,
        )
        _registrar(meta, 'DEPOSIT', account, amount, date_deposit, description, transfer_id)
        return meta

    @staticmethod
    @db_transaction.atomic
    def resgatar(goal, amount, date_withdrawal=None, account=None, description=None):
        """
        Resgate da meta (META-15 a META-18), também de meta arquivada:
        - até o valor da meta;
        - com `account`, até o saldo do cofrinho, com a transferência do
          cofrinho para essa conta;
        - sem `account`, para o saldo livre do cofrinho, sem transferência.
        A trava da meta faz o segundo de dois resgates simultâneos ler o valor
        já recalculado (META-22).
        """
        amount = Decimal(str(amount))
        meta, cofrinho = _travar(goal, account)
        if amount > meta.current_amount:
            raise ValidationError(VALOR_DA_META_INSUFICIENTE.format(valor=reais(max(meta.current_amount, 0))))
        date_withdrawal = date_withdrawal or hoje()
        description = description or f"Resgate da Meta: {meta.name}"

        if account is None:
            _registrar(meta, 'WITHDRAWAL', cofrinho, amount, date_withdrawal, description)
            return meta

        saldo_do_cofrinho = cofrinho.balance
        # As regras da transferência (SALDO-17, SALDO-35) respondem primeiro;
        # a recusa pelo saldo do cofrinho desfaz a transferência no `atomic`
        transfer_id = TransactionService.create_transfer(
            user=meta.user, account_from=cofrinho, account_to=account,
            amount=amount, date=date_withdrawal, description=description,
        )
        if amount > saldo_do_cofrinho:
            raise ValidationError(COFRINHO_INSUFICIENTE.format(valor=reais(max(saldo_do_cofrinho, 0))))
        _registrar(meta, 'WITHDRAWAL', account, amount, date_withdrawal, description, transfer_id)
        return meta

    @staticmethod
    def get_progress(goal):
        """
        Retorna dicionário com dados de progresso.
        No sistema de Ledger Estrito, confiamos no current_amount salvo na meta,
        que é atualizado permanentemente por cada aporte ou resgate (manual ou automático).
        """
        # Garante que seja Decimal para evitar erro 'int object has no attribute quantize'
        val = Decimal(str(goal.current_amount))
        current_amount = val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        progress_pct = Decimal('0')
        if goal.target_amount > 0:
            progress_pct = (current_amount / goal.target_amount) * Decimal('100')
        
        remaining = goal.target_amount - current_amount
        if remaining < 0: remaining = Decimal('0')
        
        suggestion = Decimal('0')
        months = 0
        if goal.target_date:
            # Meses a partir de hoje em Brasília, com mínimo de 1 (META-24, AD-008)
            today = hoje()
            months = (goal.target_date.year - today.year) * 12 + (goal.target_date.month - today.month)
            if months <= 0: months = 1
            if remaining > 0:
                suggestion = remaining / Decimal(months)
            
        return {
            'percentage': min(round(progress_pct, 1), Decimal('100.0')),
            'current_amount': current_amount,
            'remaining': remaining,
            'monthly_suggestion': round(suggestion, 2),
            'months_remaining': months
        }
