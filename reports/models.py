from django.db import models
from api.models import User
from transactions.models import Category, Tag
import uuid

class FocusedMonitorItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='focused_monitors')
    
    # Pode monitorar uma categoria OU uma tag
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Evitar duplicatas do mesmo item para o mesmo usuário
        unique_together = ['user', 'category', 'tag']
        ordering = ['created_at']

    def __str__(self):
        item = self.category.name if self.category else self.tag.name
        return f"{self.user.email} - Monitor: {item}"
