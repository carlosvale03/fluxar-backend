from django.db import models
from cloudinary.models import CloudinaryField
from django.conf import settings
from accounts.models import Account

class Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals')
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='goals')
    target_date = models.DateField(null=True, blank=True)
    image = CloudinaryField('image', folder='goals', resource_type='image', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.user.email})"

class GoalDeposit(models.Model):
    """
    Registra uma movimentação em uma meta (Aporte ou Resgate).
    """
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Aporte'),
        ('WITHDRAWAL', 'Resgate'),
    ]

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='deposits')
    account = models.ForeignKey(Account, on_delete=models.CASCADE) # Conta de origem/destino
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    type = models.CharField(max_length=15, choices=TRANSACTION_TYPES, default='DEPOSIT')
    description = models.CharField(max_length=255, blank=True, null=True)
    transaction_id = models.UUIDField(null=True, blank=True, db_index=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_display()} de {self.amount} para {self.goal.name} em {self.date}"
