"""
Referências do mês e histórico da gestão do salário (SALARIO-52, SALARIO-53,
SALARIO-56).

- Comprometido no mês: as despesas recorrentes pendentes do mês atual e o
  valor em aberto das faturas que vencem nele (`regras.faturas_do_mes`).
- Histórico: as médias mensais, nos 3 últimos meses completos, das receitas
  de salário efetivadas, das despesas por classe efetiva (`regras.despesas` e
  `mapa_de_classes`, AD-052) e da diferença entre as duas. Quem tem menos
  histórico usa os meses que existem desde o mês da primeira transação, e
  `months_used` diz quantos entraram.

Os meses são os do calendário de Brasília (AD-008).
"""
from decimal import Decimal

from django.db.models import Min, Sum

from accounts.faturas import dia_no_mes, mes_anterior
from core.texto import normalizar
from core.valores import dinheiro
from reports import regras
from transactions.classes import mapa_de_classes
from transactions.models import ClasseDeDespesa, Transaction

from . import plano
from .models import DISPENSAVEL, ESSENCIAL

MESES_DO_HISTORICO = 3
SEM_CLASSE = 'Sem classe'
# As classes padrão que correspondem às partes dos modelos (SALARIO-54)
REFERENCIA_DAS_CLASSES = {'essencial': ESSENCIAL, 'dispensavel': DISPENSAVEL}
ZERO = Decimal('0.00')


def referencia_da_classe(classe):
    """`ESSENCIAL` ou `DISPENSAVEL` para as classes padrão; vazio nas demais."""
    if classe is None or not classe.padrao:
        return ''
    return REFERENCIA_DAS_CLASSES.get(normalizar(classe.nome_normalizado), '')


def comprometido(usuario):
    """O que já está comprometido no mês atual (SALARIO-52)."""
    inicio, fim = regras.limites_do_mes(*regras.mes_atual())
    recorrentes = regras.total(Transaction.objects.filter(
        user=usuario, type='EXPENSE', status='PENDING', recurring_source__isnull=False,
        date__gte=inicio, date__lte=fim, is_balance_adjustment=False,
    ))
    faturas = regras.faturas_do_mes(usuario)
    return {
        'recurring_pending': dinheiro(recorrentes),
        'invoices_due': dinheiro(faturas),
        'total': dinheiro(recorrentes + faturas),
    }


def meses_do_historico(usuario):
    """
    Os meses completos do histórico, do mais antigo ao mais recente: os 3
    anteriores ao mês atual, a partir do mês da primeira transação (SALARIO-56).
    """
    ano, mes = regras.mes_atual()
    mes_ant, ano_ant = mes_anterior(mes, ano)
    meses = regras.meses_do_calendario(dia_no_mes(ano_ant, mes_ant, 1), MESES_DO_HISTORICO)
    primeira = Transaction.objects.filter(
        user=usuario, is_balance_adjustment=False,
    ).aggregate(primeira=Min('report_date'))['primeira']
    if primeira is None:
        return []
    return [(a, m) for a, m in meses if (a, m) >= (primeira.year, primeira.month)]


def historico(usuario):
    """As médias mensais do histórico (SALARIO-53, SALARIO-56)."""
    meses = meses_do_historico(usuario)
    classes = list(ClasseDeDespesa.objects.filter(user=usuario).order_by('-padrao', 'criada_em', 'nome'))
    por_classe = {classe.pk: ZERO for classe in classes}
    sem_classe = ZERO
    salario = ZERO
    if meses:
        inicio = regras.limites_do_mes(*meses[0])[0]
        fim = regras.limites_do_mes(*meses[-1])[1]
        salario = regras.total(
            regras.receitas(usuario, inicio, fim).filter(category_id__in=plano.categorias_de_salario(usuario)),
        )
        mapa = mapa_de_classes(usuario)
        somas = regras.despesas(usuario, inicio, fim).order_by().values('category_id').annotate(total=Sum('amount'))
        for soma in somas:
            classe = mapa.get(soma['category_id'])
            if classe is not None and classe.pk in por_classe:
                por_classe[classe.pk] += soma['total']
            else:
                sem_classe += soma['total']
    quantidade = len(meses)

    def media(valor):
        return dinheiro(valor / quantidade if quantidade else ZERO)

    despesas = sum(por_classe.values(), ZERO) + sem_classe
    linhas = [
        {
            'class_id': str(classe.pk), 'class_name': classe.nome,
            'reference': referencia_da_classe(classe), 'average': media(por_classe[classe.pk]),
        }
        for classe in classes
    ]
    if sem_classe:
        linhas.append({'class_id': None, 'class_name': SEM_CLASSE, 'reference': '', 'average': media(sem_classe)})
    return {
        'months_used': quantidade,
        'salary_average': media(salario),
        'expense_average': media(despesas),
        'difference_average': media(salario - despesas),
        'by_class': linhas,
    }


def referencias(usuario):
    """O corpo de `GET /salary/references/`."""
    return {'committed': comprometido(usuario), 'history': historico(usuario)}
