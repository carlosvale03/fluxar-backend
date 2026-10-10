"""
Análise e importação da planilha completa (IMPCOMP-13, IMPCOMP-23,
IMPCOMP-31, IMPCOMP-37, IMPCOMP-45 a IMPCOMP-48, IMPCOMP-52, AD-055).

O fluxo é sem estado: a análise e a importação recebem o arquivo e o plano.
A análise lê as abas, completa o plano, interpreta as linhas com contas
provisórias no lugar das contas a criar e marca as repetidas, sem gravar
nada. A importação cria as contas novas, grava as linhas válidas pelo
`Gravacao.importar` e acerta o saldo das contas criadas, tudo numa
transação. Os logs levam só contagens e ids (AD-019).
"""
import logging
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction

from core.valores import dinheiro

from .contas import acertar_saldos, contas_a_criar, contas_provisorias, contas_vinculadas, criar_contas
from .deteccao import IGNORAR, detectar_plano
from .gravacao import Gravacao
from .interpretacao import LinhaImportada, Rejeicao, ResolvedorDeContas, conferir_chaves, interpretar_aba
from .leitura import conferir_colunas, ler_abas, vazio
from .repetidos import Repetidos

logger = logging.getLogger(__name__)

VALIDA = 'VALIDA'
REJEITADA = 'REJEITADA'
REPETIDA = 'REPETIDA'
EXCLUIDA = 'EXCLUIDA'


def preparar(usuario, arquivo, plano, tags_liberadas):
    """
    Lê as abas, confere as chaves de linha do plano (IMPCOMP-35), completa o
    plano e confere que as colunas das abas usadas existem (IMPORT-06,
    IMPCOMP-22). Com `tags` travado, a coluna de tags sai do plano (IMPCOMP-51).
    """
    abas = ler_abas(arquivo)
    conferir_chaves(abas, plano.get('linhas'))
    final = detectar_plano(abas, usuario, plano)
    for aba, plano_da_aba in zip(abas, final['abas']):
        if not tags_liberadas:
            plano_da_aba['colunas'].pop('tags_column', None)
        if plano_da_aba['papel'] != IGNORAR:
            conferir_colunas(aba.cabecalho, list(dict.fromkeys(plano_da_aba['colunas'].values())))
    return abas, final


def interpretar(abas, final, contas, tags_liberadas):
    """As `LinhaDoArquivo` das abas usadas e a quantidade de rodapés pulados."""
    resolvedor = ResolvedorDeContas(contas)
    linhas, resumos = [], 0
    for aba, plano_da_aba in zip(abas, final['abas']):
        if plano_da_aba['papel'] == IGNORAR:
            continue
        da_aba, pulados = interpretar_aba(aba, plano_da_aba, resolvedor, final['linhas'], tags_liberadas)
        linhas += da_aba
        resumos += pulados
    return linhas, resumos


def texto_da_celula(valor):
    if vazio(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return str(Decimal(str(valor)))
    return str(valor).strip()


def celula(item, campo):
    coluna = item.colunas.get(campo)
    return texto_da_celula(item.linha.valores.get(coluna)) if coluna else None


def linha_na_resposta(item, estado):
    """
    A linha da revisão: os valores interpretados quando a linha é válida,
    repetida ou excluída e legível; o texto das células quando rejeitada.
    """
    resultado = item.resultado
    transferencia = item.colunas.get('source_account_column')
    linha = {
        'chave': item.chave, 'aba': item.aba, 'numero': item.linha.numero, 'estado': estado,
        'motivo': resultado.motivo if isinstance(resultado, Rejeicao) else None,
        'conta': celula(item, 'source_account_column' if transferencia else 'account_column'),
        'destino': celula(item, 'dest_account_column'),
    }
    if isinstance(resultado, LinhaImportada):
        linha.update({
            'data': resultado.data.isoformat(), 'descricao': resultado.descricao, 'tipo': resultado.tipo,
            'categoria': resultado.categoria, 'subcategoria': resultado.subcategoria,
            'valor': dinheiro(resultado.valor), 'situacao': resultado.status, 'tags': list(resultado.tags),
        })
        return linha
    valor = celula(item, 'amount_column') or celula(item, 'income_column')
    if valor is None and celula(item, 'expense_column'):
        valor = f"-{celula(item, 'expense_column')}"
    tags = celula(item, 'tags_column')
    linha.update({
        'data': celula(item, 'date_column'), 'descricao': celula(item, 'description_column'),
        'tipo': celula(item, 'type_column'), 'categoria': celula(item, 'category_column'),
        'subcategoria': celula(item, 'subcategory_column'), 'valor': valor,
        'situacao': celula(item, 'status_column'),
        'tags': [t.strip() for t in tags.split(',') if t.strip()] if tags else [],
    })
    return linha


def analisar(usuario, arquivo, plano, tags_liberadas=True):
    """
    `{plano, linhas, resumo}` sem gravar nada (IMPCOMP-13, IMPCOMP-31): cada
    linha das abas usadas com o estado VALIDA, REJEITADA, REPETIDA ou
    EXCLUIDA, e o resumo da revisão (IMPCOMP-37).
    """
    abas, final = preparar(usuario, arquivo, plano, tags_liberadas)
    contas = {**contas_vinculadas(usuario, final['contas']), **contas_provisorias(usuario, final['contas'])}
    linhas, resumos = interpretar(abas, final, contas, tags_liberadas)

    validas = [l.resultado for l in linhas if not l.excluida and isinstance(l.resultado, LinhaImportada)]
    marcadas = Repetidos(usuario, validas).marcar(validas)
    repetidas = {id(r) for r, repetida in zip(validas, marcadas) if repetida}

    resposta = []
    totais = {tipo: {'quantidade': 0, 'valor': Decimal('0.00')} for tipo in ('INCOME', 'EXPENSE', 'TRANSFER')}
    contagem = {VALIDA: 0, REJEITADA: 0, REPETIDA: 0, EXCLUIDA: 0}
    for item in linhas:
        if item.excluida:
            estado = EXCLUIDA
        elif isinstance(item.resultado, Rejeicao):
            estado = REJEITADA
        elif id(item.resultado) in repetidas:
            estado = REPETIDA
        else:
            estado = VALIDA
            totais[item.resultado.tipo]['quantidade'] += 1
            totais[item.resultado.tipo]['valor'] += item.resultado.valor
        contagem[estado] += 1
        resposta.append(linha_na_resposta(item, estado))

    def total(tipo):
        return {'quantidade': totais[tipo]['quantidade'], 'valor': dinheiro(totais[tipo]['valor'])}

    resumo = {
        'validas': contagem[VALIDA], 'rejeitadas': contagem[REJEITADA],
        'repetidas': contagem[REPETIDA], 'excluidas': contagem[EXCLUIDA],
        'contas_novas': len(contas_a_criar(final['contas'])),
        'receitas': total('INCOME'), 'despesas': total('EXPENSE'), 'transferencias': total('TRANSFER'),
        'summary_rows': resumos,
    }
    logger.info(
        'Análise de importação do usuário %s: %s abas, %s linhas (%s válidas, %s rejeitadas, '
        '%s repetidas, %s excluídas), %s rodapés.',
        usuario.pk, len(abas), len(linhas), contagem[VALIDA], contagem[REJEITADA],
        contagem[REPETIDA], contagem[EXCLUIDA], resumos,
    )
    return {'plano': final, 'linhas': resposta, 'resumo': resumo}


def importar(usuario, arquivo, plano, tags_liberadas=True):
    """
    Cria as contas novas, grava as linhas não excluídas de todas as abas
    usadas e acerta o saldo das contas criadas, numa transação (IMPCOMP-45,
    IMPCOMP-29). Responde com os totais de IMPORT-29, `excluded`,
    `accounts_created`, `by_sheet` e `summary_rows` (IMPCOMP-47).
    """
    with transaction.atomic():
        abas, final = preparar(usuario, arquivo, plano, tags_liberadas)
        criadas = criar_contas(usuario, final['contas'])
        contas = {**contas_vinculadas(usuario, final['contas']), **criadas}
        linhas, resumos = interpretar(abas, final, contas, tags_liberadas)

        gravacao = Gravacao(usuario)
        resumo = gravacao.importar([l.resultado for l in linhas if not l.excluida])
        acertar_saldos(criadas, {nome: Decimal(final['contas'][nome]['saldo_atual']) for nome in criadas})

    por_aba = {
        plano_da_aba['nome']: {'imported': 0, 'ignored': 0, 'rejected': 0}
        for plano_da_aba in final['abas'] if plano_da_aba['papel'] != IGNORAR
    }
    for aba, totais in gravacao.por_aba.items():
        por_aba[aba].update(totais)
    resposta = {
        **resumo,
        'excluded': sum(1 for l in linhas if l.excluida),
        'accounts_created': [{'id': str(conta.pk), 'name': conta.name} for conta in criadas.values()],
        'by_sheet': por_aba,
        'summary_rows': resumos,
    }
    logger.info(
        'Importação completa %s do usuário %s: %s gravadas, %s ignoradas, %s rejeitadas, '
        '%s excluídas, %s contas criadas.',
        resumo['batch_id'], usuario.pk, resumo['imported'], resumo['ignored'], resumo['rejected'],
        resposta['excluded'], len(criadas),
    )
    return resposta
