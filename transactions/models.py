from django.db import models
from api.models import User
import uuid


class ClasseDeDespesa(models.Model):
    """
    Classe de despesa do usuário (AD-025, AD-052): Essencial e Dispensável
    são padrão; o usuário cria outras até o total de 5. O nome é único por
    usuário sem diferença de maiúsculas e acentos, pela `nome_normalizado`.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='classes_de_despesa')
    nome = models.CharField(max_length=30)
    nome_normalizado = models.CharField(max_length=30)
    cor = models.CharField(max_length=7)
    padrao = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'nome_normalizado'], name='classe_nome_unico_por_usuario'),
        ]

    def __str__(self):
        return f'Classe {self.pk}'


class Category(models.Model):
    TYPE_CHOICES = [
        ('INCOME', 'Receita'),
        ('EXPENSE', 'Despesa'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories', null=True, blank=True)
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Identificador do ícone (ex: 'mdi-food')")
    color = models.CharField(max_length=7, blank=True, null=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='EXPENSE')
    
    # Hierarquia e Templates
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories', help_text="Categoria pai (opcional, para subcategorias)")
    is_template = models.BooleanField(default=False, help_text="Se True, serve apenas como molde para novos usuários")
    # Classe própria da categoria de despesa; sem ela, vale a da mãe (CLASSE-16)
    classe = models.ForeignKey(
        ClasseDeDespesa, on_delete=models.SET_NULL, null=True, blank=True, related_name='categorias',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=['user', 'type']),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return f"{self.name} ({self.get_type_display()})"


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'name']

    def __str__(self):
        return self.name





class Transaction(models.Model):
    TYPE_CHOICES = [
        ('INCOME', 'Receita'),
        ('EXPENSE', 'Despesa'),
        ('TRANSFER_OUT', 'Transferência (Saída)'),
        ('TRANSFER_IN', 'Transferência (Entrada)'),
        ('CREDIT_CARD', 'Despesa Cartão'),
        ('INVOICE_PAYMENT', 'Pagamento Fatura'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    
    # Vinculações
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    credit_card = models.ForeignKey('accounts.CreditCard', on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    invoice = models.ForeignKey('accounts.CreditCardInvoice', on_delete=models.SET_NULL, related_name='transactions', null=True, blank=True)
    
    # Classificação
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    
    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('COMPLETED', 'Concluída'),
    ]

    # Dados da transação
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='COMPLETED')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField() # Data de competência (para filtro)
    
    # Transferência
    transfer_id = models.UUIDField(null=True, blank=True, db_index=True, help_text="ID agrupador de transferências (origem/destino)")

    # Parcelamento (Installments)
    is_installment = models.BooleanField(default=False)
    installment_number = models.IntegerField(null=True, blank=True, help_text="Número da parcela (ex: 1)")
    installment_total = models.IntegerField(null=True, blank=True, help_text="Total de parcelas (ex: 12)")
    parent_transaction = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='installments', help_text="Transação pai que originou o parcelamento")

    # Recorrência (Link para template original, se houver)
    recurring_source = models.ForeignKey('RecurringTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_transactions')

    # Data de pagamento (efetiva saída/entrada no caixa)
    payment_date = models.DateField(null=True, blank=True)

    # Data real da compra no cartão; o `date` dela é o vencimento da fatura (AD-039, FATURA-16)
    purchase_date = models.DateField(null=True, blank=True)

    # Data em que a transação conta nos relatórios, recalculada no `save()`
    # (AD-046, REL-01, REL-02); veja `data_no_relatorio`
    report_date = models.DateField(db_index=True)
    # Lançamento criado pelo ajuste de saldo: fica fora de receitas e
    # despesas (REL-03, REL-05)
    is_balance_adjustment = models.BooleanField(default=False)

    # Importação: o lote de cada importação, o identificador da transação no
    # OFX e se a categoria veio das correções do usuário (IMPORT-34, IMPORT-44)
    import_batch = models.UUIDField(null=True, blank=True, db_index=True)
    fitid = models.CharField(max_length=255, null=True, blank=True)
    categoria_sugerida = models.BooleanField(default=False)

    # Divisão do salário que gerou a transação (SALARIO-35, AD-053); um UUID
    # sem FK, como o `transfer_id`, para não ligar os apps em círculo
    divisao_do_salario = models.UUIDField(null=True, blank=True, db_index=True)

    # Vínculo (AD-027, AD-054): a transação principal da qual esta é
    # dependente, gravada na raiz da compra parcelada. Excluir a principal
    # desfaz o vínculo e mantém a dependente (VINCULO-14). As regras ficam em
    # `transactions/vinculos.py`.
    principal = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='dependentes',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Segunda barreira contra o mesmo OFX importado duas vezes (IMPORT-34, IMPORT-39)
            models.UniqueConstraint(
                fields=['account', 'fitid'], condition=models.Q(fitid__isnull=False),
                name='fitid_unico_por_conta',
            ),
            # Uma transação não é principal de si mesma (VINCULO-08)
            models.CheckConstraint(
                condition=~models.Q(principal=models.F('id')),
                name='transacao_nao_e_principal_de_si_mesma',
            ),
        ]

    def save(self, *args, **kwargs):
        # A `report_date` acompanha sempre o tipo, as datas e a parcela (AD-046)
        self.report_date = data_no_relatorio(
            self.type, self.date, self.purchase_date, self.installment_number,
        )
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = {*update_fields, 'report_date'}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} - {self.description} ({self.amount})"


def data_no_relatorio(tipo, data, data_da_compra, numero_da_parcela):
    """
    A data em que a transação conta nos relatórios (AD-046):
    - compra no cartão com `purchase_date`: a data da compra mais N-1 meses na
      parcela N, no mesmo dia, ou no último dia do mês quando ele não existe
      (REL-01, REL-02, AD-006);
    - compra no cartão antiga, sem `purchase_date`: a `date`, porque cada
      parcela antiga já tem o próprio vencimento;
    - demais tipos: a `date`.
    A migração `0011_relatorios` repete esta regra.
    """
    from accounts.faturas import dia_no_mes

    if tipo != 'CREDIT_CARD' or data_da_compra is None:
        return data
    meses = data_da_compra.month - 1 + (numero_da_parcela or 1) - 1
    return dia_no_mes(data_da_compra.year + meses // 12, meses % 12 + 1, data_da_compra.day)


class CorrecaoDeCategoria(models.Model):
    """
    Categoria definida ou trocada pelo usuário numa transação importada
    (IMPORT-42). Sugere a categoria nas próximas importações do mesmo usuário
    (IMPORT-43) e é apagada junto com ele (IMPORT-48).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='correcoes_de_categoria')
    transacao = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    descricao = models.CharField(max_length=255)
    descricao_normalizada = models.CharField(max_length=255, db_index=True)
    conta = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    categoria_antes = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    categoria_depois = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'descricao_normalizada', '-criada_em']),
        ]

    def __str__(self):
        return f"{self.descricao} → {self.categoria_depois_id}"


class RecurringTransaction(models.Model):
    FREQUENCY_CHOICES = [
        ('DAILY', 'Diária'),
        ('WEEKLY', 'Semanal'),
        ('MONTHLY', 'Mensal'),
        ('YEARLY', 'Anual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_transactions')
    
    # Template dos dados
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    type = models.CharField(max_length=20, choices=Transaction.TYPE_CHOICES)
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, null=True, blank=True)
    credit_card = models.ForeignKey('accounts.CreditCard', on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Controle de Recorrência
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    last_processed = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} ({self.get_frequency_display()})"
