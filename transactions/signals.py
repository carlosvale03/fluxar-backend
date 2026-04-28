from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Sum, F
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
        Transaction.objects.filter(
            transfer_id=instance.transfer_id
        ).exclude(
            id=instance.id
        ).delete()

# --- BALANCE SYNC SIGNALS ---

def get_transaction_impact(transaction):
    """
    Calcula o impacto financeiro de uma transação no saldo da conta.
    Retorna o valor assinado (positivo para entradas, negativo para saídas).
    Retorna 0 se a transação não for COMPLETED ou não tiver conta.
    """
    if not getattr(transaction, 'account_id', None) or transaction.status != 'COMPLETED':
        return 0
    
    # Entradas
    if transaction.type in ['INCOME', 'TRANSFER_IN']:
        return transaction.amount
    
    # Saídas
    if transaction.type in ['EXPENSE', 'TRANSFER_OUT', 'INVOICE_PAYMENT', 'CREDIT_CARD']:
        return -transaction.amount
        
    return 0

@receiver(pre_save, sender=Transaction)
def capture_old_transaction_state(sender, instance, **kwargs):
    """
    Captura o estado anterior da transação antes de salvar, para calcular o diff do saldo.
    """
    if instance.pk:
        try:
            old_instance = Transaction.objects.get(pk=instance.pk)
            instance._old_impact = get_transaction_impact(old_instance)
            instance._old_account_id = old_instance.account_id
        except Transaction.DoesNotExist:
            instance._old_impact = 0
            instance._old_account_id = None
    else:
        instance._old_impact = 0
        instance._old_account_id = None

@receiver(post_save, sender=Transaction)
def update_account_balance_on_save(sender, instance, created, **kwargs):
    """
    Atualiza o saldo da conta quando uma transação é criada ou editada.
    """
    new_impact = get_transaction_impact(instance)
    old_impact = getattr(instance, '_old_impact', 0)
    old_account_id = getattr(instance, '_old_account_id', None)
    new_account_id = getattr(instance, 'account_id', None)

    # 1. Se a conta mudou, remove o impacto da conta antiga e adiciona na nova
    if old_account_id and old_account_id != new_account_id:
        Account.objects.filter(id=old_account_id).update(balance=F('balance') - old_impact)
        if new_account_id:
            Account.objects.filter(id=new_account_id).update(balance=F('balance') + new_impact)
    else:
        # 2. Mesma conta (ou nova transação), aplica apenas a diferença
        if new_account_id:
            diff = new_impact - old_impact
            if diff != 0:
                Account.objects.filter(id=new_account_id).update(balance=F('balance') + diff)

@receiver(post_delete, sender=Transaction)
def update_account_balance_on_delete(sender, instance, **kwargs):
    """
    Atualiza o saldo da conta quando uma transação é excluída.
    """
    impact = get_transaction_impact(instance)
    account_id = getattr(instance, 'account_id', None)
    if impact != 0 and account_id:
        # Usamos filter().update() em vez de instance.account para evitar 
        # exceptions de DoesNotExist durante deleção em cascata
        Account.objects.filter(id=account_id).update(balance=F('balance') - impact)
