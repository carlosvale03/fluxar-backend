from django.db import models
from django.conf import settings
from accounts.models import Account

class Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals')
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.user.email})"

class GoalDeposit(models.Model):
    """
    Registra um aporte em uma meta, vindo de uma conta.
    """
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='deposits')
    account = models.ForeignKey(Account, on_delete=models.CASCADE) # Conta de origem
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} para {self.goal.name} em {self.date}"
