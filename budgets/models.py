from django.db import models
from api.models import User
from transactions.models import Category
import uuid

class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets')
    
    month = models.IntegerField(help_text="Mês de referência (1-12)")
    year = models.IntegerField(help_text="Ano de referência")
    
    amount_limit = models.DecimalField(max_digits=15, decimal_places=2, help_text="Teto de gastos para o período")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'month', 'year'], name='unique_budget_per_category_month')
        ]
        ordering = ['year', 'month', 'category__name']

    def __str__(self):
        return f"{self.category.name} - {self.month}/{self.year}: {self.amount_limit}"
