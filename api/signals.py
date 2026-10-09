import logging
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
import cloudinary.uploader

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(pre_save, sender=User)
def delete_old_avatar_on_update(sender, instance, **kwargs):
    """
    Remove o avatar antigo do Cloudinary quando um novo é enviado.
    """
    if not instance.pk:
        return

    try:
        old_instance = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return

    if old_instance.avatar:
        old_id = getattr(old_instance.avatar, 'public_id', str(old_instance.avatar))
        new_id = getattr(instance.avatar, 'public_id', str(instance.avatar)) if instance.avatar else None
        
        if old_id and old_id != new_id:
            try:
                cloudinary.uploader.destroy(old_id)
            except Exception as erro:
                # Só a classe do erro e o id: a mensagem pode trazer dados (LGPD-21)
                logger.error(
                    "Erro ao remover o avatar antigo do Cloudinary usuario=%s (%s).",
                    instance.pk, type(erro).__name__,
                )
