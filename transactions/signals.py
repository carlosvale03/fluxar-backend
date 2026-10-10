from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from api.models import User
from accounts.faturas import recalcular_totais
from accounts.models import Account, CreditCard
from accounts.saldo import recalcular
from .models import Transaction
from .padrao import criar_padrao_do_cadastro

@receiver(post_save, sender=User)
def initialize_user_data(sender, instance, created, **kwargs):
    """O cadastro novo recebe o padrão de `criar_padrao_do_cadastro` (AD-050)."""
    if created:
        criar_padrao_do_cadastro(instance)

@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def update_invoice_total(sender, instance, **kwargs):
    """
    Recalcula o total da fatura antiga e da nova sempre que uma compra é
    criada, editada, movida ou excluída (FATURA-18). A fatura antiga vem do
    `capture_old_transaction_state`.
    """
    recalcular_totais(getattr(instance, '_old_invoice_id', None), instance.invoice_id)

@receiver(post_delete, sender=Transaction)
def sync_transfer_delete(sender, instance, **kwargs):
    """
    Cascade delete para transações de transferência.
    """
    if instance.transfer_id:
        # Só a parceira do dono da transação (ISOL-14)
        Transaction.objects.filter(
            transfer_id=instance.transfer_id, user_id=instance.user_id
        ).exclude(
            id=instance.id
        ).delete()

# --- BALANCE SYNC SIGNALS ---
# O saldo vem sempre de accounts/saldo.py (AD-038): os signals só dizem quais
# contas recalcular, a antiga e a nova.

@receiver(pre_save, sender=Transaction)
def capture_old_transaction_state(sender, instance, **kwargs):
    """
    Captura a conta e a fatura anteriores da transação antes de salvar, para
    recalcular também a conta de onde ela saiu (SALDO-07) e o total da
    fatura de onde ela saiu (FATURA-18).
    """
    instance._old_account_id = None
    instance._old_invoice_id = None
    # Uma transação nova não tem estado anterior: sem consulta (IMPORT-40)
    if instance.pk and not instance._state.adding:
        anterior = (
            Transaction.objects.filter(pk=instance.pk).values_list('account_id', 'invoice_id').first()
        )
        if anterior:
            instance._old_account_id, instance._old_invoice_id = anterior

@receiver(post_save, sender=Transaction)
def update_account_balance_on_save(sender, instance, created, **kwargs):
    """
    Recalcula o saldo da conta antiga e da nova quando uma transação é criada
    ou editada.
    """
    recalcular(getattr(instance, '_old_account_id', None), instance.account_id)

@receiver(post_delete, sender=Transaction)
def update_account_balance_on_delete(sender, instance, **kwargs):
    """
    Recalcula o saldo da conta quando uma transação é excluída.
    """
    recalcular(instance.account_id)
