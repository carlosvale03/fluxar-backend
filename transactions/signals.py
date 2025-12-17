from django.db.models.signals import post_save
from django.dispatch import receiver
from api.models import User
from .services import CategoryService

@receiver(post_save, sender=User)
def clone_categories_on_signup(sender, instance, created, **kwargs):
    """
    Quando um usuário é criado, copia os templates de categoria para ele.
    """
    if created:
        CategoryService.clone_templates_to_user(instance)
