import logging
from django.db.models.signals import post_save, post_delete, pre_delete, pre_save
from django.dispatch import receiver
import cloudinary.uploader

from . import vinculo

@receiver(pre_delete, sender='transactions.Transaction')
def remover_registros_da_transacao_excluida(sender, instance, origin=None, **kwargs):
    """
    A transação excluída leva junto os registros de meta ligados a ela, na
    mesma operação (META-06, META-09).
    """
    vinculo.ao_excluir(instance, origin)


@receiver(post_save, sender='transactions.Transaction')
def acompanhar_transacao_alterada(sender, instance, created, **kwargs):
    """
    A transação alterada leva valor, data e status aos registros de meta
    ligados a ela (META-07 a META-09). Uma transação nova ainda não tem
    registro ligado; e o rateio automático entre as metas do cofrinho saiu
    (META-03, AD-028).
    """
    if created:
        return
    vinculo.ao_salvar(instance)

# --- Cloudinary Image Cleanup ---

@receiver(post_delete, sender='goals.Goal')
def delete_image_on_goal_delete(sender, instance, **kwargs):
    """
    Remove a imagem do Cloudinary quando a meta é excluída.
    """
    if instance.image:
        try:
            # O CloudinaryField retorna um objeto que tem o public_id
            cloudinary.uploader.destroy(instance.image.public_id)
        except Exception as e:
            logging.error(f"Erro ao deletar imagem do Cloudinary (Goal Delete): {e}")

@receiver(pre_save, sender='goals.Goal')
def delete_old_image_on_goal_update(sender, instance, **kwargs):
    """
    Remove a imagem antiga do Cloudinary quando uma nova imagem é enviada.
    """
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.image:
        old_id = getattr(old_instance.image, 'public_id', str(old_instance.image))
        new_id = getattr(instance.image, 'public_id', str(instance.image)) if instance.image else None
        
        if old_id and old_id != new_id:
            try:
                cloudinary.uploader.destroy(old_id)
            except Exception as e:
                logging.error(f"Erro ao deletar imagem antiga do Cloudinary (Goal Update): {e}")
