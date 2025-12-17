from django.db import models
from api.models import User
import uuid

class Category(models.Model):
    TYPE_CHOICES = [
        ('INCOME', 'Receita'),
        ('EXPENSE', 'Despesa'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories', null=True, blank=True)
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Identificador do ícone (ex: 'mdi-food')")
    color = models.CharField(max_length=7, blank=True, null=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='EXPENSE')
    
    # Hierarquia e Templates
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories', help_text="Categoria pai (opcional, para subcategorias)")
    is_template = models.BooleanField(default=False, help_text="Se True, serve apenas como molde para novos usuários")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=['user', 'type']),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return f"{self.name} ({self.get_type_display()})"


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'name']

    def __str__(self):
        return self.name


class TransferGroup(models.Model):
    """
    Agrupa duas transações (saída e entrada) de uma transferência.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('INCOME', 'Receita'),
        ('EXPENSE', 'Despesa'),
        ('TRANSFER_OUT', 'Transferência (Saída)'),
        ('TRANSFER_IN', 'Transferência (Entrada)'),
        ('CREDIT_CARD', 'Despesa Cartão'),
        ('INVOICE_PAYMENT', 'Pagamento Fatura'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    
    # Vinculações
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    credit_card = models.ForeignKey('accounts.CreditCard', on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    invoice = models.ForeignKey('accounts.CreditCardInvoice', on_delete=models.SET_NULL, related_name='transactions', null=True, blank=True)
    
    # Classificação
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    
    # Dados da transação
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField() # Data de competência (para filtro)
    
    # Transferência
    transfer_group = models.ForeignKey(TransferGroup, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions')

    # Parcelamento (Installments)
    is_installment = models.BooleanField(default=False)
    installment_number = models.IntegerField(null=True, blank=True, help_text="Número da parcela (ex: 1)")
    installment_total = models.IntegerField(null=True, blank=True, help_text="Total de parcelas (ex: 12)")
    parent_transaction = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='installments', help_text="Transação pai que originou o parcelamento")

    # Recorrência (Link para template original, se houver)
    # recurring_source = models.ForeignKey('RecurringTransaction', ...)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.description} ({self.amount})"


class RecurringTransaction(models.Model):
    FREQUENCY_CHOICES = [
        ('DAILY', 'Diária'),
        ('WEEKLY', 'Semanal'),
        ('MONTHLY', 'Mensal'),
        ('YEARLY', 'Anual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_transactions')
    
    # Template dos dados
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    type = models.CharField(max_length=20, choices=Transaction.TYPE_CHOICES)
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, null=True, blank=True)
    credit_card = models.ForeignKey('accounts.CreditCard', on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Controle de Recorrência
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    last_processed = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} ({self.get_frequency_display()})"
