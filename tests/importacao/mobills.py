"""
Arquivo de exemplo com o layout da exportação do Mobills (importacao-completa).

Quatro abas, com os nomes e os cabeçalhos da exportação:

- "Receitas e Despesas": 57 linhas em 11 contas, valor com sinal e situação "Paga";
- "Despesas" e "Receitas": exatamente as linhas negativas e as positivas da primeira;
- "Transferências": 9 transferências entre as contas.

Toda aba termina numa linha vazia e numa linha "Total (...)", com o total na
coluna Valor. As datas vêm como texto dd/mm/aaaa e os valores como números,
como no arquivo real. Os dados são inventados.
"""
from datetime import date
from decimal import Decimal

from .base import arquivo_xlsx

CABECALHO = ['Data', 'Descrição', 'Valor', 'Conta', 'Situação', 'Categoria', 'Subcategoria', 'Tags']
CABECALHO_TRANSFERENCIAS = ['Data', 'Conta origem', 'Conta destino', 'Valor', 'Tags']

# As 11 contas e o tipo sugerido pelo nome (IMPCOMP-12)
CONTAS = {
    'Nubank': 'CHECKING',
    'Itaú': 'CHECKING',
    'Carteira': 'WALLET',
    'Poupança Caixa': 'SAVINGS',
    'XMeta - Reserva de emergência': 'SAVINGS',
    'XC - Investimentos CDB': 'INVESTMENT',
    'Cofrinho viagem': 'PIGGY_BANK',
    'Inter': 'CHECKING',
    'Bradesco': 'CHECKING',
    'C6 Bank': 'CHECKING',
    'Santander': 'CHECKING',
}
NOMES = list(CONTAS)

TOTAL_DE_LINHAS = 57
TOTAL_DE_TRANSFERENCIAS = 9


def lancamentos():
    """As 57 linhas de "Receitas e Despesas": uma receita a cada quatro linhas."""
    linhas = []
    for i in range(TOTAL_DE_LINHAS):
        receita = i % 4 == 0
        dia = date(2026, 8 + i // 30, 1 + i % 28)
        valor = 1000 + i if receita else -(10.5 + i)
        linhas.append([
            dia.strftime('%d/%m/%Y'), f'Lançamento {i + 1}', valor, NOMES[i % len(NOMES)], 'Paga',
            'Salário' if receita else 'Mercado', None, None,
        ])
    return linhas


def transferencias():
    """As 9 transferências, cada uma de uma conta para a seguinte."""
    return [
        [date(2026, 9, 1 + i).strftime('%d/%m/%Y'), NOMES[i], NOMES[i + 1], 50.25 + i, None]
        for i in range(TOTAL_DE_TRANSFERENCIAS)
    ]


def com_rodape(cabecalho, linhas, coluna_do_valor):
    """O cabeçalho, as linhas, uma linha vazia e a linha "Total (n)" com a soma na coluna Valor."""
    total = [None] * len(cabecalho)
    total[0] = f'Total ({len(linhas)})'
    total[coluna_do_valor] = sum(linha[coluna_do_valor] for linha in linhas)
    return [cabecalho] + linhas + [[None] * len(cabecalho), total]


def abas_do_mobills():
    linhas = lancamentos()
    return [
        ('Receitas e Despesas', com_rodape(CABECALHO, linhas, 2)),
        ('Despesas', com_rodape(CABECALHO, [linha for linha in linhas if linha[2] < 0], 2)),
        ('Receitas', com_rodape(CABECALHO, [linha for linha in linhas if linha[2] > 0], 2)),
        ('Transferências', com_rodape(CABECALHO_TRANSFERENCIAS, transferencias(), 3)),
    ]


def arquivo_mobills(nome='RELATORIO_TRANSACOES_teste.xlsx'):
    return arquivo_xlsx(nome=nome, abas=abas_do_mobills())


def efeito_por_conta():
    """
    O efeito de cada conta no saldo, calculado direto dos dados do arquivo:
    receitas e despesas com sinal, a transferência sai da origem e entra no destino.
    """
    efeito = {nome: Decimal('0.00') for nome in NOMES}
    for linha in lancamentos():
        efeito[linha[3]] += Decimal(str(linha[2]))
    for linha in transferencias():
        efeito[linha[1]] -= Decimal(str(linha[3]))
        efeito[linha[2]] += Decimal(str(linha[3]))
    return efeito
