"""
Conjunto anonimizado para melhorar o produto e treinar modelos de previsão e
de categorização (LGPD-36 a LGPD-38, AD-031).

Só entram os usuários com o consentimento ligado no momento da geração: quem
retira o consentimento sai dos conjuntos seguintes, e o que já foi gerado não
é refeito (LGPD-37, art. 16, IV). Cada linha traz só o tipo, o valor, o mês e
o ano, a categoria normalizada e a descrição normalizada, sem dígitos, sem
e-mails e sem os nomes das contas e cartões do usuário. Ficam de fora os ids
de usuário, conta e transação, os nomes de conta e de cartão e o dia. As
linhas saem embaralhadas, para a ordem não agrupar as linhas de uma pessoa.
"""
import random
import re

from data_exchange.importacao.texto import normalizar_descricao

COLUNAS = ('tipo', 'valor', 'mes', 'ano', 'categoria', 'descricao')

# Só os lançamentos que dizem algo sobre gastos e receitas; transferências e
# pagamentos de fatura levam nomes de contas e cartões nas descrições
TIPOS = ('INCOME', 'EXPENSE', 'CREDIT_CARD')

EMAIL = re.compile(r'\S+@\S+')


def _sem_identificadores(texto, nomes):
    """Descrição normalizada, sem e-mails, dígitos e os nomes de contas e cartões."""
    limpo = normalizar_descricao(EMAIL.sub(' ', texto or ''))
    for nome in nomes:
        if nome:
            limpo = limpo.replace(nome, ' ')
    return ' '.join(limpo.split())


def _nomes_do_usuario(usuario_id):
    from accounts.models import Account, CreditCard

    nomes = list(Account.objects.filter(user_id=usuario_id).values_list('name', flat=True))
    nomes += list(CreditCard.objects.filter(user_id=usuario_id).values_list('name', flat=True))
    # Os mais longos primeiro, para "nubank ultravioleta" sair antes de "nubank"
    return sorted({normalizar_descricao(nome) for nome in nomes}, key=len, reverse=True)


def dados_para_melhoria(embaralhar=random.shuffle):
    """As linhas do conjunto, como dicionários com as `COLUNAS`."""
    from api.models import User
    from transactions.models import Transaction

    linhas = []
    consentiram = User.objects.filter(consentimento_melhoria=True, is_active=True).values_list('pk', flat=True)
    for usuario_id in consentiram:
        nomes = _nomes_do_usuario(usuario_id)
        transacoes = (
            Transaction.objects
            .filter(user_id=usuario_id, type__in=TIPOS, is_balance_adjustment=False)
            .values_list('type', 'amount', 'report_date', 'category__name', 'description')
        )
        for tipo, valor, data, categoria, descricao in transacoes:
            linhas.append({
                'tipo': tipo,
                'valor': str(valor),
                'mes': data.month,
                'ano': data.year,
                'categoria': _sem_identificadores(categoria, nomes),
                'descricao': _sem_identificadores(descricao, nomes),
            })
    embaralhar(linhas)
    return linhas
