from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Account
from .saldo import recalcular

@receiver(post_save, sender=Account)
def update_balance_on_initial_balance_change(sender, instance, created, **kwargs):
    """
    Recalcula o saldo (accounts/saldo.py) quando a conta é criada ou salva,
    o que cobre a mudança do saldo inicial (SALDO-43). O saldo gravado volta
    para a instância, para que a resposta da API traga o valor certo.
    """
    recalcular(instance.pk)
    instance.balance = Account.objects.filter(pk=instance.pk).values_list('balance', flat=True).get()
