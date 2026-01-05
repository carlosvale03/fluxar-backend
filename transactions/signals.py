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
