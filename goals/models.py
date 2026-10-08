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
    # Valor antes da correção da META-11; mostrado uma vez, até o usuário confirmar
    valor_antes_da_correcao = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
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
    # `transfer_id` da transferência; nos registros antigos, o `transfer_id`
    # ou o `id` da transação (META-01, META-10)
    transaction_id = models.UUIDField(null=True, blank=True, db_index=True)
    # As duas pernas da transferência do aporte ou do resgate (AD-045). Sem
    # elas e sem `transaction_id`, o registro não tem transação: saldo livre
    # ou correção (META-13, META-16, META-11)
    transacao_saida = models.ForeignKey(
        'transactions.Transaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    transacao_entrada = models.ForeignKey(
        'transactions.Transaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # Registro de correção do recálculo da implantação (META-11)
    eh_correcao = models.BooleanField(default=False)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_display()} de {self.amount} para {self.goal.name} em {self.date}"


class ConfiguracaoDeTrocos(models.Model):
    """
    Cofrinho de trocos do usuário (META-35, META-44, META-45): a meta que
    recebe os trocos e a hora da ativação, a partir da qual as despesas
    efetivadas geram troco.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='configuracao_de_trocos')
    ativo = models.BooleanField(default=False)
    # Meta arquivada ou excluída pausa os trocos até o usuário escolher outra (META-44)
    meta = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    ativado_em = models.DateTimeField(null=True, blank=True)


class Troco(models.Model):
    """
    O troco de uma despesa até o próximo real (META-36). Pendente até o
    depósito; depois, depositado e ligado ao aporte, ou descartado quando a
    conta foi excluída (META-38, META-43).
    """
    PENDENTE = 'PENDENTE'
    DEPOSITADO = 'DEPOSITADO'
    DESCARTADO = 'DESCARTADO'
    STATUS = [(PENDENTE, 'Pendente'), (DEPOSITADO, 'Depositado'), (DESCARTADO, 'Descartado')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trocos')
    despesa = models.ForeignKey('transactions.Transaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    conta = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    valor = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default=PENDENTE)
    aporte = models.ForeignKey(GoalDeposit, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    criado_em = models.DateTimeField(auto_now_add=True)
