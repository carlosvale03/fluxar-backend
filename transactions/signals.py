from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from .models import Transaction

@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def update_invoice_total(sender, instance, **kwargs):
    """
    Atualiza o total_amount da Invoice sempre que uma transação vinculada é alterada.
    """
    if instance.invoice:
        # Recalcula o total somando todas as transações de despesa vinculadas
        # Nota: Filtrar apenas tipos relevantes de despesa se necessário.
        # Atualmente: 'CREDIT_CARD' é o tipo de despesa. 'INVOICE_PAYMENT' pode estar vinculado?
        # Geralmente INVOICE_PAYMENT não tem FK invoice preenchido (é pagamento DA fatura, não item DA fatura).
        # Mas vamos garantir filtrando por type='CREDIT_CARD' para evitar somar pagamentos se algo mudar.
        
        total = instance.invoice.transactions.filter(
            type='CREDIT_CARD'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Atualiza a invoice sem disparar signals da invoice (loop?) - Invoice não tem signals ainda.
        # Usar update_fields para ser mais eficiente e evitar efeitos colaterais.
        instance.invoice.total_amount = total
        instance.invoice.save(update_fields=['total_amount'])

@receiver(post_save, sender=Transaction)
def sync_transfer_update(sender, instance, created, **kwargs):
    """
    Sincroniza atualizações entre transações de transferência parcerias.
    """
    if not created and instance.transfer_id:
        # Atualiza a transação parceira com dados comuns.
        # NÃO atualiza account aqui (isso é especifico de cada perna).
        # Usa update() para não disparar signals recursivamente.
        Transaction.objects.filter(
            transfer_id=instance.transfer_id
        ).exclude(
            id=instance.id
        ).update(
            date=instance.date,
            amount=instance.amount,
            # description removido para permitir personalização independente
        )

@receiver(post_delete, sender=Transaction)
def sync_transfer_delete(sender, instance, **kwargs):
    """
    Cascade delete para transações de transferência.
    """
    if instance.transfer_id:
        # Deleta a parceira
        # O exclude é importante para não tentar deletar a que acabou de disparar o signal (embora ja não exista)
        # O queryset.delete() dispara signals, então haverá uma chamada recursiva para a parceira.
        # A parceira deletada disparará o signal novamente, mas não encontrará 'instance' no banco, então o loop para.
        Transaction.objects.filter(
            transfer_id=instance.transfer_id
        ).exclude(
            id=instance.id
        ).delete()
