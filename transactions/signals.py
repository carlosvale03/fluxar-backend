from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from api.models import User
from accounts.models import Account, CreditCard
from .models import Transaction, Category

DEFAULT_CATEGORIES = [
    { "name": "Salário", "type": "INCOME", "icon": "DollarSign", "color": "#14b8a6" },
    { "name": "Investimento", "type": "INCOME", "icon": "TrendingUp", "color": "#06b6d4" },
    { "name": "Pagamentos", "type": "INCOME", "icon": "Banknote", "color": "#10b981" },
    { "name": "Prêmio", "type": "INCOME", "icon": "Trophy", "color": "#f59e0b" },
    { "name": "Presente", "type": "INCOME", "icon": "Gift", "color": "#fb7185" },
    { "name": "Outros", "type": "INCOME", "icon": "Sparkles", "color": "#64748b" },
    {
        "name": "Casa",
        "type": "EXPENSE",
        "icon": "Home",
        "color": "#6366f1",
        "subcategories": [
            { "name": "Aluguel", "icon": "Key" },
            { "name": "Energia", "icon": "Zap" }
        ]
    },
    { "name": "Comida", "type": "EXPENSE", "icon": "Utensils", "color": "#f97316" },
    { "name": "Transporte", "type": "EXPENSE", "icon": "Car", "color": "#3b82f6" },
    { "name": "Lazer", "type": "EXPENSE", "icon": "Gamepad2", "color": "#8b5cf6" },
    { "name": "Educação", "type": "EXPENSE", "icon": "GraduationCap", "color": "#c084fc" },
    { "name": "Eletrônicos", "type": "EXPENSE", "icon": "Smartphone", "color": "#64748b" },
    { "name": "Doces", "type": "EXPENSE", "icon": "IceCream", "color": "#ec4899" },
    { "name": "Doação", "type": "EXPENSE", "icon": "Heart", "color": "#f43f5e" },
    { "name": "Presente", "type": "EXPENSE", "icon": "Gift", "color": "#fb7185" }
]

@receiver(post_save, sender=User)
def initialize_user_data(sender, instance, created, **kwargs):
    """
    Cria categorias e conta padrão sempre que um novo usuário é registrado.
    """
    if created:
        # 1. Cria as categorias padrão
        for cat_data in DEFAULT_CATEGORIES:
            # Cria a categoria pai
            parent_category = Category.objects.create(
                user=instance,
                name=cat_data["name"],
                type=cat_data["type"],
                icon=cat_data["icon"],
                color=cat_data["color"],
                is_active=True
            )
            
            # Se existirem subcategorias, cria vinculadas ao pai
            if "subcategories" in cat_data:
                for sub_data in cat_data["subcategories"]:
                    Category.objects.create(
                        user=instance,
                        name=sub_data["name"],
                        icon=sub_data["icon"],
                        type=cat_data["type"], # Herda o tipo
                        color=cat_data["color"], # Herda a cor
                        parent=parent_category,
                        is_active=True
                    )
        
        # 2. Cria a conta padrão "Carteira"
        Account.objects.create(
            user=instance,
            name="Carteira",
            type="WALLET",
            initial_balance=0,
            color="#475569",
            is_active=True
        )

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
