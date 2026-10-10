"""
Gestão do salário (AD-026, AD-053).

- `GestaoDoSalario`: uma por usuário, com as categorias de salário e o plano.
- `ParteDoPlano`: cada parte do plano, na ordem de prioridade, com a regra e
  o destino.
- `DivisaoDoSalario`: uma por recebimento dividido, com a chave da tentativa
  (AD-007) e a marca de desfeita.
- `ItemDaDivisao`: o que cada parte gerou na divisão.

As transações geradas levam o id da divisão em
`Transaction.divisao_do_salario`, um UUID sem FK, para não criar dependência
circular entre os apps `transactions` e `salario`.
"""
import uuid

from django.conf import settings
from django.db import models

# Regras das partes
FIXO = 'FIXED'
PERCENTUAL = 'PERCENT'
REGRAS = [(FIXO, 'Valor fixo'), (PERCENTUAL, 'Percentual do salário')]

# Destinos das partes; sem destino, o tipo fica nulo
CONTA = 'ACCOUNT'
META = 'GOAL'
CONTA_DO_SALARIO = 'SALARY_ACCOUNT'
DESTINOS = [(CONTA, 'Conta'), (META, 'Meta'), (CONTA_DO_SALARIO, 'Fica na conta do salário')]

# Classe de despesa a que a parte corresponde no histórico (SALARIO-54)
ESSENCIAL = 'ESSENCIAL'
DISPENSAVEL = 'DISPENSAVEL'
REFERENCIAS = [(ESSENCIAL, 'Essencial'), (DISPENSAVEL, 'Dispensável')]


class GestaoDoSalario(models.Model):
    """
    A configuração da gestão do salário do usuário. Sem `categorias_configuradas`,
    as categorias de salário são a "Salário" e as subcategorias dela
    (SALARIO-14). `plano_salvo` marca que o usuário já salvou um plano, mesmo
    sem partes (Personalizado).
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gestao_do_salario')
    categorias = models.ManyToManyField('transactions.Category', blank=True, related_name='+')
    categorias_configuradas = models.BooleanField(default=False)
    plano_salvo = models.BooleanField(default=False)
    atualizada_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Gestão do salário {self.pk}'


class ParteDoPlano(models.Model):
    gestao = models.ForeignKey(GestaoDoSalario, on_delete=models.CASCADE, related_name='partes')
    ordem = models.PositiveIntegerField()
    nome = models.CharField(max_length=60)
    tipo_de_regra = models.CharField(max_length=10, choices=REGRAS)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_de_destino = models.CharField(max_length=20, choices=DESTINOS, null=True, blank=True)
    conta = models.ForeignKey('accounts.Account', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    meta = models.ForeignKey('goals.Goal', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    referencia = models.CharField(max_length=20, choices=REFERENCIAS, blank=True, default='')

    class Meta:
        ordering = ['ordem', 'pk']

    def __str__(self):
        return f'Parte {self.pk}'


class DivisaoDoSalario(models.Model):
    """
    Uma divisão de um recebimento (AD-053). `recebimento_ref` guarda o id do
    recebimento mesmo depois de ele ser excluído; a restrição única parcial
    deixa só uma divisão ativa por recebimento (SALARIO-38, SALARIO-39).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='divisoes_do_salario')
    recebimento = models.ForeignKey('transactions.Transaction', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    recebimento_ref = models.UUIDField(db_index=True)
    conta_de_origem = models.ForeignKey('accounts.Account', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # idempotency_key enviado pela interface (AD-007); sem chave, cada pedido é uma tentativa nova
    chave = models.UUIDField(null=True, blank=True)
    valor_recebido = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    livre = models.DecimalField(max_digits=12, decimal_places=2)
    criada_em = models.DateTimeField(auto_now_add=True)
    desfeita_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # A mesma chave não se repete para o mesmo usuário (SALARIO-37)
            models.UniqueConstraint(
                fields=['user', 'chave'], condition=models.Q(chave__isnull=False),
                name='divisao_chave_unica_por_usuario',
            ),
            # Um recebimento tem no máximo uma divisão ativa (SALARIO-38, SALARIO-39)
            models.UniqueConstraint(
                fields=['recebimento_ref'], condition=models.Q(desfeita_em__isnull=True),
                name='divisao_ativa_unica_por_recebimento',
            ),
        ]

    def __str__(self):
        return f'Divisão {self.pk}'


class ItemDaDivisao(models.Model):
    """
    O que uma parte gerou na divisão: o valor e, quando gerou transação, as
    duas pernas da transferência ou do aporte (SALARIO-32, SALARIO-35).
    """
    divisao = models.ForeignKey(DivisaoDoSalario, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveIntegerField()
    nome_da_parte = models.CharField(max_length=60)
    # Vazio só na parte sem destino que ficou com valor zero
    tipo_de_destino = models.CharField(max_length=20, choices=DESTINOS, blank=True, default='')
    conta = models.ForeignKey('accounts.Account', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    meta = models.ForeignKey('goals.Goal', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    reduzida = models.BooleanField(default=False)
    transacao_saida = models.ForeignKey('transactions.Transaction', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    transacao_entrada = models.ForeignKey('transactions.Transaction', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    transfer_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ['ordem', 'pk']

    def __str__(self):
        return f'Item {self.pk}'
