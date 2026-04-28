from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Account
from decimal import Decimal

@receiver(pre_save, sender=Account)
def capture_old_initial_balance(sender, instance, **kwargs):
    """
    Captura o saldo inicial antigo antes de salvar para calcular a diferença.
    """
    if instance.pk:
        try:
            old_instance = Account.objects.get(pk=instance.pk)
            instance._old_initial_balance = old_instance.initial_balance
            # Se o balance atual for 0 e existirem transações, talvez precisemos de um recálculo total,
            # mas para edições simples de saldo inicial, a lógica de diff é suficiente.
        except Account.DoesNotExist:
            instance._old_initial_balance = Decimal('0.00')
    else:
        instance._old_initial_balance = Decimal('0.00')

@receiver(post_save, sender=Account)
def update_balance_on_initial_balance_change(sender, instance, created, **kwargs):
    """
    Atualiza o saldo calculado (balance) quando o saldo inicial é alterado.
    """
    if created:
        # Se a conta acabou de ser criada, o balance é igual ao initial_balance
        if instance.balance != instance.initial_balance:
            Account.objects.filter(pk=instance.pk).update(balance=instance.initial_balance)
    else:
        old_initial = getattr(instance, '_old_initial_balance', Decimal('0.00'))
        if instance.initial_balance != old_initial:
            diff = instance.initial_balance - old_initial
            # Atualiza o balance somando a diferença do saldo inicial
            from django.db.models import F
            Account.objects.filter(pk=instance.pk).update(balance=F('balance') + diff)
