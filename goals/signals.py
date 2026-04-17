import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from decimal import Decimal, ROUND_HALF_UP
from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_save, post_delete, pre_save
import cloudinary.uploader

@receiver(post_save, sender='transactions.Transaction')
def handle_transaction_for_goals(sender, instance, created, **kwargs):
    """
    Sinal que captura qualquer transação financeira em um cofrinho e reflete
    proporcionalmente no histórico de cada meta vinculada.
    """
    if not created: 
        return

    # Coletamos os dados necessários da instância para usar no closure (on_commit)
    # Isso evita problemas de thread/transação com o objeto 'instance'
    txn_ref = instance.transfer_id or instance.id
    account_id = instance.account_id
    txn_amount = abs(instance.amount)
    txn_type_raw = instance.type
    txn_description = instance.description
    txn_date = instance.date

    def process_on_commit():
        Account = apps.get_model('accounts', 'Account')
        Goal = apps.get_model('goals', 'Goal')
        GoalDeposit = apps.get_model('goals', 'GoalDeposit')

        account = Account.objects.filter(id=account_id).first()
        if not account: return

        goals = Goal.objects.filter(account=account, is_active=True)
        if not goals.exists(): return

        # Prevenção de duplicidade: ignore se esta transação já foi vinculada a alguma meta
        if GoalDeposit.objects.filter(transaction_id=txn_ref).exists():
            return

        # 1. Calcular o saldo total atual das metas vinculadas a este cofrinho
        from django.db.models import Sum
        total_goals_balance = goals.aggregate(total=Sum('current_amount'))['total'] or Decimal('0.00')
        
        # 2. Determinação do Tipo na Meta
        # Se saiu dinheiro do cofrinho físico (despesa), é um Resgate na meta.
        is_negative = txn_type_raw in ['EXPENSE', 'TRANSFER_OUT', 'CREDIT_CARD']
        txn_type = 'WITHDRAWAL' if is_negative else 'DEPOSIT'

        num_goals = goals.count()

        for goal in goals:
            # 3. Cálculo da Proporção
            if total_goals_balance > 0:
                # Proporção baseada no saldo ATUAL da meta em relação ao total das metas
                proportion = goal.current_amount / total_goals_balance
                parcel_amount = (txn_amount * proportion).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                # Se todas as metas estão zeradas, distribui igualmente
                parcel_amount = (txn_amount / Decimal(num_goals)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if parcel_amount == 0:
                continue

            # 4. Atualização PERMANENTE do saldo da meta (Ledger Estrito)
            if txn_type == 'DEPOSIT':
                goal.current_amount += parcel_amount
            else:
                # No resgate automático (despesa no cofrinho), reduzimos o saldo.
                # Não permitimos que o automático deixe a meta negativa (opcional, mas seguro)
                new_amount = goal.current_amount - parcel_amount
                goal.current_amount = max(Decimal('0.00'), new_amount)
            
            goal.save(update_fields=['current_amount'])

            # 5. Criar registro no Histórico (Shadow Ledger)
            GoalDeposit.objects.create(
                goal=goal,
                account=account,
                amount=parcel_amount,
                type=txn_type,
                description=f"Automático: {txn_description}",
                transaction_id=txn_ref,
                date=txn_date
            )

    transaction.on_commit(process_on_commit)

@receiver(post_delete, sender='transactions.Transaction')
def handle_transaction_deletion(sender, instance, **kwargs):
    """
    Remove todos os registros (Shadow Ledger) no histórico das metas vinculados
    a uma transação deletada. Mantém a integridade do saldo real x meta.
    """
    GoalDeposit = apps.get_model('goals', 'GoalDeposit')
    txn_ref = instance.transfer_id or instance.id
    
    # Ao deletar, removemos tanto o registro manual quanto o automático
    GoalDeposit.objects.filter(transaction_id=txn_ref).delete()

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
