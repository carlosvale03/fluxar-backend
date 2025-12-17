from django.db import models
from api.models import User
import uuid

class Account(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('CHECKING', 'Conta Corrente'),
        ('SAVINGS', 'Poupança'),
        ('WALLET', 'Carteira'),
        ('INVESTMENT', 'Investimento'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='CHECKING')
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Identidade Visual e Open Finance
    institution = models.CharField(max_length=50, blank=True, null=True, help_text="Código ou nome da instituição para ícone (ex: 'nubank', 'itaú')")
    color = models.CharField(max_length=7, blank=True, null=True, help_text="Cor hexadecimal para exibição (ex: #7F22E2)")
    is_manual = models.BooleanField(default=True, help_text="Se True, movimentação é manual. Se False, virá de integração externa.")
    external_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID da conta na API externa de Open Finance")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.user.email})"


class CreditCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_cards')
    name = models.CharField(max_length=100)
    limit = models.DecimalField(max_digits=15, decimal_places=2)
    closing_day = models.IntegerField(help_text="Dia de fechamento da fatura (1-31)")
    due_day = models.IntegerField(help_text="Dia de vencimento da fatura (1-31)")
    
    # Identidade Visual
    institution = models.CharField(max_length=50, blank=True, null=True, help_text="Código ou nome da instituição para ícone")
    color = models.CharField(max_length=7, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.user.email}"


class CreditCardInvoice(models.Model):
    INVOICE_STATUS = [
        ('OPEN', 'Aberta'),
        ('CLOSED', 'Fechada'),
        ('PAID', 'Paga'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(CreditCard, on_delete=models.CASCADE, related_name='invoices')
    month = models.IntegerField()
    year = models.IntegerField()
    status = models.CharField(max_length=10, choices=INVOICE_STATUS, default='OPEN')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    closing_date = models.DateField()
    due_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['card', 'month', 'year']

    def __str__(self):
        return f"Fatura {self.month}/{self.year} - {self.card.name}"
