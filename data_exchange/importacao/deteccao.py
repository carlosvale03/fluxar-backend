"""
Detecção do plano de importação (IMPCOMP-04 a IMPCOMP-14).

A partir das abas lidas, liga cada cabeçalho a um campo pelos sinônimos, dá
um papel a cada aba (receitas e despesas, transferências ou ignorada),
reconhece o modelo do Mobills, ignora as abas contidas em outra e lista as
contas do arquivo com a sugestão de vincular a uma conta ativa ou de criar.
O que vier num plano editado prevalece sobre o detectado. Nada é gravado.
"""
from collections import Counter
from datetime import date

from rest_framework.exceptions import ValidationError

from accounts.models import Account
from core.valores import dinheiro

from .interpretacao import LinhaRejeitada, ler_data, ler_valor
from .leitura import linha_de_resumo, vazio
from .texto import normalizar

RECEITAS_DESPESAS = 'RECEITAS_DESPESAS'
TRANSFERENCIAS = 'TRANSFERENCIAS'
IGNORAR = 'IGNORAR'
PAPEIS = (RECEITAS_DESPESAS, TRANSFERENCIAS, IGNORAR)

COLUNAS_NAO_RECONHECIDAS = 'Colunas não reconhecidas'
CONTIDA_NA_ABA = 'Contida na aba {nome}'
ABA_INEXISTENTE = 'Aba inexistente no arquivo: {nome}.'

MOBILLS = 'MOBILLS'

VINCULAR = 'vincular'
CRIAR = 'criar'


def nome_comparavel(texto):
    """`normalizar` com os espaços internos juntados: sem maiúsculas, acentos e espaços extras."""
    return ' '.join(normalizar(texto).split())


# Campo do plano → nomes de cabeçalho reconhecidos (IMPCOMP-04), já comparáveis
SINONIMOS = {
    'date_column': ('data', 'date', 'dt', 'data da transacao'),
    'description_column': ('descricao', 'historico', 'memo', 'titulo', 'lancamento'),
    'amount_column': ('valor', 'quantia', 'amount'),
    'account_column': ('conta', 'banco', 'carteira'),
    'source_account_column': ('conta origem', 'origem', 'de'),
    'dest_account_column': ('conta destino', 'destino', 'para'),
    'type_column': ('tipo',),
    'status_column': ('situacao', 'status'),
    'category_column': ('categoria',),
    'subcategory_column': ('subcategoria',),
    'tags_column': ('tags', 'etiquetas'),
    'income_column': ('entrada', 'credito'),
    'expense_column': ('saida', 'debito'),
}
CAMPOS = tuple(SINONIMOS)

# Nomes das abas e cabeçalhos exatos da exportação do Mobills (IMPCOMP-08)
CABECALHO_MOBILLS = ('Data', 'Descrição', 'Valor', 'Conta', 'Situação', 'Categoria', 'Subcategoria', 'Tags')
MODELO_MOBILLS = {
    'Receitas e Despesas': CABECALHO_MOBILLS,
    'Despesas': CABECALHO_MOBILLS,
    'Receitas': CABECALHO_MOBILLS,
    'Transferências': ('Data', 'Conta origem', 'Conta destino', 'Valor', 'Tags'),
}
ABA_PRINCIPAL_DO_MOBILLS = 'Receitas e Despesas'
ABAS_REPETIDAS_DO_MOBILLS = ('Despesas', 'Receitas')

# Tipo sugerido para a conta nova pelas palavras do nome, na ordem (IMPCOMP-12)
TIPOS_PELO_NOME = (
    (('carteira',), 'WALLET'),
    (('poupanca', 'reserva'), 'SAVINGS'),
    (('investimento', 'cdb'), 'INVESTMENT'),
    (('cofrinho',), 'PIGGY_BANK'),
)


def colunas_da_aba(aba):
    """Liga cada cabeçalho ao primeiro campo cujo sinônimo bate; um campo fica com o primeiro cabeçalho."""
    colunas = {}
    for cabecalho in aba.cabecalho:
        comparavel = nome_comparavel(cabecalho)
        for campo, nomes in SINONIMOS.items():
            if comparavel in nomes:
                colunas.setdefault(campo, cabecalho)
                break
    return colunas


def papel_da_aba(colunas):
    """O papel e o motivo da aba pelas colunas reconhecidas (IMPCOMP-05 a IMPCOMP-07)."""
    if colunas.get('source_account_column') and colunas.get('dest_account_column'):
        return TRANSFERENCIAS, None
    if colunas.get('date_column') and (
        colunas.get('amount_column') or (colunas.get('income_column') and colunas.get('expense_column'))
    ):
        return RECEITAS_DESPESAS, None
    return IGNORAR, COLUNAS_NAO_RECONHECIDAS


def cabecalho_preenchido(aba):
    return tuple(c.strip() for c in aba.cabecalho if c and c.strip())


def modelo_do_arquivo(abas):
    """`MOBILLS` quando todas as abas têm os nomes e os cabeçalhos da exportação do Mobills (IMPCOMP-08)."""
    if abas and all(MODELO_MOBILLS.get(aba.nome) == cabecalho_preenchido(aba) for aba in abas):
        return MOBILLS
    return None


def tentar(funcao, celula):
    try:
        return funcao(celula)
    except LinhaRejeitada:
        return None


def texto_da_celula(linha, coluna):
    if not coluna:
        return None
    valor = linha.valores.get(coluna)
    return None if vazio(valor) else str(valor).strip()


def valor_com_sinal(linha, colunas):
    """O valor da linha com sinal: a coluna de valor, ou a entrada positiva e a saída negativa."""
    if colunas.get('amount_column'):
        return tentar(ler_valor, linha.valores.get(colunas['amount_column']))
    entrada = linha.valores.get(colunas.get('income_column')) if colunas.get('income_column') else None
    saida = linha.valores.get(colunas.get('expense_column')) if colunas.get('expense_column') else None
    if vazio(entrada) == vazio(saida):
        return None
    if not vazio(entrada):
        valor = tentar(ler_valor, entrada)
        return abs(valor) if valor is not None else None
    valor = tentar(ler_valor, saida)
    return -abs(valor) if valor is not None else None


def linhas_de_dados(aba, colunas):
    """As linhas da aba sem o rodapé de resumo (IMPCOMP-15)."""
    return [linha for linha in aba.linhas if not linha_de_resumo(linha, colunas)]


def assinatura(linha, colunas):
    """Data, valor, conta e descrição da linha, para comparar abas (IMPCOMP-09)."""
    data = linha.valores.get(colunas.get('date_column')) if colunas.get('date_column') else None
    valor = valor_com_sinal(linha, colunas)
    return (
        tentar(ler_data, data) or texto_da_celula(linha, colunas.get('date_column')),
        valor if valor is not None else texto_da_celula(linha, colunas.get('amount_column')),
        nome_comparavel(texto_da_celula(linha, colunas.get('account_column'))),
        texto_da_celula(linha, colunas.get('description_column')),
    )


def abas_contidas(abas, detectadas):
    """
    Ignora a aba de receitas e despesas cujas linhas (data, valor, conta e
    descrição, contando as repetições) estão todas dentro de outra aba usada
    (IMPCOMP-09). Entre duas abas iguais, a primeira fica e a segunda é a
    contida. Aba sem linhas não é contida em nenhuma.
    """
    multiconjuntos = {}
    for indice, (aba, plano) in enumerate(zip(abas, detectadas)):
        if plano['papel'] == RECEITAS_DESPESAS:
            multiconjuntos[indice] = Counter(
                assinatura(linha, plano['colunas']) for linha in linhas_de_dados(aba, plano['colunas'])
            )
    for indice, linhas in multiconjuntos.items():
        if not linhas:
            continue
        for outro, linhas_da_outra in multiconjuntos.items():
            if outro == indice or detectadas[outro]['papel'] != RECEITAS_DESPESAS:
                continue
            maior = sum(linhas_da_outra.values()) > sum(linhas.values()) or outro < indice
            if maior and all(linhas_da_outra[k] >= n for k, n in linhas.items()):
                detectadas[indice]['papel'] = IGNORAR
                detectadas[indice]['motivo'] = CONTIDA_NA_ABA.format(nome=abas[outro].nome)
                break


def detectar_abas(abas, modelo):
    """O papel, as colunas e o motivo detectados de cada aba."""
    detectadas = []
    for aba in abas:
        colunas = colunas_da_aba(aba)
        papel, motivo = papel_da_aba(colunas)
        detectadas.append({
            'nome': aba.nome, 'papel': papel, 'colunas': colunas, 'motivo': motivo,
            'cabecalho': list(aba.cabecalho),
        })
    nomes = [aba.nome for aba in abas]
    if modelo == MOBILLS and ABA_PRINCIPAL_DO_MOBILLS in nomes:
        for plano in detectadas:
            if plano['nome'] in ABAS_REPETIDAS_DO_MOBILLS:
                plano['papel'] = IGNORAR
                plano['motivo'] = CONTIDA_NA_ABA.format(nome=ABA_PRINCIPAL_DO_MOBILLS)
    else:
        abas_contidas(abas, detectadas)
    return detectadas


def tipo_sugerido(nome):
    """O tipo da conta nova pelas palavras óbvias do nome, sem interpretar prefixos (IMPCOMP-12)."""
    comparavel = nome_comparavel(nome)
    for palavras, tipo in TIPOS_PELO_NOME:
        if any(palavra in comparavel for palavra in palavras):
            return tipo
    return 'CHECKING'


def nomes_de_conta(linha, plano):
    """Os nomes de conta da linha com o efeito de cada um, conforme o papel da aba."""
    colunas = plano['colunas']
    valor = valor_com_sinal(linha, colunas)
    if plano['papel'] == TRANSFERENCIAS:
        absoluto = abs(valor) if valor is not None else None
        return [
            (texto_da_celula(linha, colunas.get('source_account_column')), -absoluto if absoluto else None),
            (texto_da_celula(linha, colunas.get('dest_account_column')), absoluto),
        ]
    nomes = [(texto_da_celula(linha, colunas.get('account_column')), valor)]
    if colunas.get('dest_account_column'):
        absoluto = abs(valor) if valor is not None else None
        nomes.append((texto_da_celula(linha, colunas['dest_account_column']), absoluto))
    return nomes


def contas_do_arquivo(abas, planos, usuario):
    """
    Cada nome de conta das abas usadas uma vez, agrupado sem diferença de
    maiúsculas, acentos e espaços extras, com a quantidade de linhas, a soma
    dos valores e a primeira e a última data (IMPCOMP-10), e a sugestão:
    vincular à conta ativa de mesmo nome (IMPCOMP-11) ou criar com o tipo
    pelo nome (IMPCOMP-12).
    """
    resumos = {}
    for aba, plano in zip(abas, planos):
        if plano['papel'] == IGNORAR:
            continue
        coluna_da_data = plano['colunas'].get('date_column')
        for linha in linhas_de_dados(aba, plano['colunas']):
            data = tentar(ler_data, linha.valores.get(coluna_da_data)) if coluna_da_data else None
            for nome, valor in nomes_de_conta(linha, plano):
                if nome is None:
                    continue
                resumo = resumos.setdefault(nome_comparavel(nome), {
                    'nome': nome, 'quantidade': 0, 'soma': 0, 'datas': [],
                })
                resumo['quantidade'] += 1
                if valor is not None:
                    resumo['soma'] += valor
                if isinstance(data, date):
                    resumo['datas'].append(data)

    ativas = {nome_comparavel(c.name): c for c in Account.objects.filter(user=usuario, is_active=True)}
    contas = {}
    for chave, resumo in resumos.items():
        nome = resumo['nome']
        existente = ativas.get(chave)
        if existente is not None:
            sugestao = {'acao': VINCULAR, 'id': str(existente.pk)}
        else:
            sugestao = {
                'acao': CRIAR, 'nome': nome[:100], 'tipo': tipo_sugerido(nome), 'saldo_atual': '0.00',
                'institution': None, 'color': None,
            }
        datas = resumo['datas']
        sugestao['arquivo'] = {
            'quantidade': resumo['quantidade'],
            'soma': dinheiro(resumo['soma']),
            'primeira_data': min(datas).isoformat() if datas else None,
            'ultima_data': max(datas).isoformat() if datas else None,
        }
        contas[nome] = sugestao
    return contas


def conta_do_plano(conta):
    """A conta de um plano editado (já validado) no formato da resposta."""
    if conta['acao'] == VINCULAR:
        return {'acao': VINCULAR, 'id': str(conta['conta'].pk)}
    return {
        'acao': CRIAR, 'nome': conta['nome'], 'tipo': conta['tipo'],
        'saldo_atual': dinheiro(conta['saldo_atual']),
        'institution': conta.get('institution') or None, 'color': conta.get('color') or None,
    }


def detectar_plano(abas, usuario, plano=None):
    """
    O plano completo: `{modelo, abas: [{nome, papel, colunas, motivo,
    cabecalho}], contas: {nome no arquivo: sugestão}, linhas}`. O papel e as
    colunas das abas e as contas de um plano editado prevalecem sobre os
    detectados (IMPCOMP-13, IMPCOMP-14).
    """
    plano = plano or {}
    modelo = modelo_do_arquivo(abas)
    detectadas = detectar_abas(abas, modelo)

    editadas = {aba['nome']: aba for aba in plano.get('abas') or []}
    nomes = {aba.nome for aba in abas}
    for nome in editadas:
        if nome not in nomes:
            raise ValidationError({'plano': [ABA_INEXISTENTE.format(nome=nome)]})
    for detectada in detectadas:
        editada = editadas.get(detectada['nome'])
        if editada is None:
            continue
        if editada['papel'] != detectada['papel']:
            detectada['motivo'] = None
        detectada['papel'] = editada['papel']
        if editada.get('colunas') is not None:
            detectada['colunas'] = {campo: coluna for campo, coluna in editada['colunas'].items() if coluna}

    contas = contas_do_arquivo(abas, detectadas, usuario)
    editadas_por_nome = {nome_comparavel(nome): conta for nome, conta in (plano.get('contas') or {}).items()}
    for nome, sugestao in contas.items():
        editada = editadas_por_nome.get(nome_comparavel(nome))
        if editada is not None:
            contas[nome] = {**conta_do_plano(editada), 'arquivo': sugestao['arquivo']}

    return {'modelo': modelo, 'abas': detectadas, 'contas': contas, 'linhas': dict(plano.get('linhas') or {})}
