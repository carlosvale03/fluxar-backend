from django.db import models
from api.models import User
import uuid

class Account(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('CHECKING', 'Conta Corrente'),
        ('SAVINGS', 'Poupança'),
        ('WALLET', 'Carteira'),
        ('INVESTMENT', 'Investimento'),
        ('PIGGY_BANK', 'Cofrinho'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='CHECKING')
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Saldo atual calculado (inicial + receitas - despesas)")
    
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
    
    # Vínculo com Conta de Pagamento (FE-002)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_cards', help_text="Conta usada para pagar a fatura deste cartão")
    
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


class PagamentoDeFatura(models.Model):
    """
    Registro de um pagamento de fatura (AD-040): a chave de idempotência, o
    que foi pago e a fatura que recebeu o restante ou as compras movidas.
    O estorno desfaz os itens dele, e a repetição da mesma chave responde a
    partir dele (FATURA-27, FATURA-30). Nunca é apagado.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pagamentos_de_fatura')
    fatura = models.ForeignKey(CreditCardInvoice, on_delete=models.CASCADE, related_name='pagamentos')
    conta = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='+')
    valor = models.DecimalField(max_digits=15, decimal_places=2)
    data = models.DateField()
    # idempotency_key enviado pela interface; sem chave, cada pedido é uma tentativa nova
    chave = models.UUIDField(null=True, blank=True)
    fatura_seguinte = models.ForeignKey(
        CreditCardInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    estornado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # A mesma chave não se repete para o mesmo usuário (FATURA-30, FATURA-32)
            models.UniqueConstraint(
                fields=['user', 'chave'], condition=models.Q(chave__isnull=False),
                name='pagamento_chave_unica_por_usuario',
            ),
        ]

    def __str__(self):
        return f"Pagamento de {self.valor} - {self.fatura}"


class ItemDePagamento(models.Model):
    """
    O que um pagamento fez com cada compra: pagou inteira, dividiu (a parte
    paga fica em `compra` e o restante em `restante`) ou moveu para a fatura
    seguinte.
    """
    PAGA = 'PAGA'
    DIVIDIDA = 'DIVIDIDA'
    MOVIDA = 'MOVIDA'
    TIPOS = [
        (PAGA, 'Paga'),
        (DIVIDIDA, 'Dividida'),
        (MOVIDA, 'Movida'),
    ]

    pagamento = models.ForeignKey(PagamentoDeFatura, on_delete=models.CASCADE, related_name='itens')
    tipo = models.CharField(max_length=10, choices=TIPOS)
    compra = models.ForeignKey('transactions.Transaction', on_delete=models.SET_NULL, null=True, related_name='+')
    # Só DIVIDIDA
    restante = models.ForeignKey('transactions.Transaction', on_delete=models.SET_NULL, null=True, related_name='+')
    valor_original = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    descricao_original = models.CharField(max_length=255, blank=True)
