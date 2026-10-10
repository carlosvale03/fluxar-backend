"""
Interpretação de cada linha (IMPORT-16 a IMPORT-22, IMPORT-24, IMPORT-26).

Transforma uma linha bruta da leitura numa `LinhaImportada` (data, valor sem
sinal, tipo, descrição, status, conta ou contas, categoria, tags e FITID) ou
numa `Rejeicao` com o número da linha e o motivo. Nada é gravado aqui; o
único acesso ao banco é o mapa de contas do usuário, carregado uma vez.

Na importação completa (IMPCOMP-15 a IMPCOMP-22, IMPCOMP-32 a IMPCOMP-34),
cada aba usada é interpretada com o papel e as colunas do plano, as contas
vêm do plano, os rodapés de resumo são pulados e as correções e exclusões
de linha do plano são aplicadas antes de interpretar.
"""
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from accounts.models import Account
from core.valores import CENTAVO, VALOR_INVALIDO, ler_valor_em_texto

from .leitura import conferir_colunas, linha_de_resumo, tipo_da_importacao, vazio
from .texto import DATA_INVALIDA, ler_data_em_texto, normalizar

TIPOS_DE_RECEITA = {'receita', 'entrada', 'credito', 'c'}
TIPOS_DE_DESPESA = {'despesa', 'saida', 'debito', 'd'}
TIPOS_DE_TRANSFERENCIA = {'transferencia'}
# Situações pendentes do Fluxar, do Mobills e de outros apps (IMPORT-20, IMPCOMP-16)
STATUS_PENDENTE = {'nao paga', 'a pagar', 'a receber', 'agendada', 'pendente', 'pending'}

SEM_DESCRICAO = 'Sem descrição'
DESCRICAO_DA_TRANSFERENCIA = 'Transferência via Importação'

TIPO_DESCONHECIDO = 'Tipo desconhecido: {valor}'
CONTA_NAO_MAPEADA = 'Conta não mapeada: {nome}'
CONTA_EXCLUIDA = 'Conta excluída: {nome}'
CONTA_NAO_INFORMADA = 'Conta não informada'
ORIGEM_E_DESTINO_IGUAIS = 'Origem e destino iguais'
TEXTO_LONGO = 'Texto longo demais: {coluna}'

LIMITE_DA_DESCRICAO = 255
LIMITE_DO_NOME = 50


@dataclass
class LinhaImportada:
    """
    Uma linha pronta para a gravação. `tipo` é INCOME, EXPENSE ou TRANSFER;
    na transferência, `conta` é a origem e `destino`, o destino. `valor` é
    sempre sem sinal; `ofx` diz se a linha veio de um OFX.
    """
    numero: int
    data: date
    valor: Decimal
    tipo: str
    descricao: str
    status: str = 'COMPLETED'
    conta: Account | None = None
    destino: Account | None = None
    categoria: str | None = None
    subcategoria: str | None = None
    tags: list = field(default_factory=list)
    fitid: str | None = None
    ofx: bool = False
    aba: str | None = None


@dataclass(frozen=True)
class Rejeicao:
    """A linha rejeitada: o número, o motivo e a aba, na importação completa (IMPCOMP-21)."""
    linha: int
    motivo: str
    aba: str | None = None


class LinhaRejeitada(Exception):
    """Interrompe a interpretação de uma linha com o motivo da rejeição."""


def ler_valor(celula):
    """
    Célula numérica (IMPORT-11) ou texto no formato brasileiro (IMPORT-09,
    IMPORT-10). Zero, mais de duas casas ou ilegível: "Valor inválido"
    (IMPORT-12).
    """
    if isinstance(celula, (int, float, Decimal)) and not isinstance(celula, bool):
        valor = Decimal(str(celula))
        if valor == 0 or valor != valor.quantize(CENTAVO):
            raise LinhaRejeitada(VALOR_INVALIDO)
        return valor.quantize(CENTAVO)
    if vazio(celula):
        raise LinhaRejeitada(VALOR_INVALIDO)
    try:
        return ler_valor_em_texto(celula)
    except ValueError:
        raise LinhaRejeitada(VALOR_INVALIDO) from None


def ler_data(celula):
    """Célula de data (IMPORT-14) ou texto (IMPORT-13); senão "Data inválida" (IMPORT-15)."""
    if isinstance(celula, datetime):
        return celula.date()
    if isinstance(celula, date):
        return celula
    if vazio(celula):
        raise LinhaRejeitada(DATA_INVALIDA)
    try:
        return ler_data_em_texto(celula)
    except ValueError:
        raise LinhaRejeitada(DATA_INVALIDA) from None


def conferir_tamanho(texto, limite, coluna):
    if texto is not None and len(texto) > limite:
        raise LinhaRejeitada(TEXTO_LONGO.format(coluna=coluna))


def tipo_pelo_sinal(valor):
    """Negativo é despesa e positivo é receita (IMPORT-18)."""
    return 'EXPENSE' if valor < 0 else 'INCOME'


def conferir_conta_ativa(conta, nome):
    """Conta excluída não recebe movimentação (IMPORT-21, AD-003)."""
    if not conta.is_active:
        raise LinhaRejeitada(CONTA_EXCLUIDA.format(nome=nome))
    return conta


def interpretar_ofx(transacao, conta):
    """Uma transação de OFX na conta escolhida (IMPORT-18, IMPORT-19, IMPORT-34)."""
    try:
        valor = ler_valor(transacao.valor)
        descricao = transacao.memo or transacao.favorecido or SEM_DESCRICAO
        conferir_tamanho(descricao, LIMITE_DA_DESCRICAO, 'descrição')
        conferir_conta_ativa(conta, conta.name)
    except LinhaRejeitada as rejeicao:
        return Rejeicao(transacao.numero, str(rejeicao))
    return LinhaImportada(
        numero=transacao.numero, data=transacao.data, valor=abs(valor), tipo=tipo_pelo_sinal(valor),
        descricao=descricao, conta=conta, fitid=transacao.fitid, ofx=True,
    )


def comparavel(texto):
    """O `nome_comparavel` da detecção: sem maiúsculas, acentos e espaços extras."""
    from .deteccao import nome_comparavel  # a detecção importa este módulo
    return nome_comparavel(texto)


class Interpretador:
    """
    Interpreta as linhas de uma planilha com o mapeamento de colunas, o tipo
    de importação, a conta padrão (ou `None`) e o mapeamento de contas da
    tela (`{nome na planilha: id da conta}`).

    Na importação completa, cada aba tem o seu interpretador, com o nome da
    aba (que vai nas rejeições, IMPCOMP-21) e um `resolvedor` que devolve a
    conta de um nome do arquivo pelo plano; aí não há conta padrão.
    """

    def __init__(self, usuario, mapeamento, import_type, conta_padrao, mapa_de_contas, aba=None, resolvedor=None):
        self.mapeamento = mapeamento
        self.transferencia = tipo_da_importacao(import_type) == 'TRANSFER'
        self.conta_padrao = conta_padrao
        self.aba = aba
        self.resolvedor = resolvedor
        self.contas_por_id = {}
        self.contas_por_nome = {}
        self.mapa_de_contas = {}
        if resolvedor is not None:
            return
        # Só as contas do usuário (isolamento): id de outra conta não é encontrado
        contas = list(Account.objects.filter(user=usuario))
        self.contas_por_id = {str(c.pk): c for c in contas}
        for conta in sorted(contas, key=lambda c: c.is_active):
            # A ativa prevalece sobre uma excluída de mesmo nome
            self.contas_por_nome[normalizar(conta.name)] = conta
        self.mapa_de_contas = {normalizar(nome): str(i) for nome, i in (mapa_de_contas or {}).items()}

    def celula(self, linha, campo):
        coluna = self.colunas.get(campo)
        if not coluna:
            return None
        valor = linha.valores.get(coluna)
        return None if vazio(valor) else valor

    def texto(self, linha, campo):
        valor = self.celula(linha, campo)
        return None if valor is None else str(valor).strip()

    def planilha(self, linha, mapeamento=None):
        """
        A `LinhaImportada` ou a `Rejeicao` da linha. `mapeamento` substitui o
        da aba só nesta linha, para as correções do plano (IMPCOMP-32).
        """
        self.colunas = self.mapeamento if mapeamento is None else mapeamento
        try:
            if self.transferencia:
                return self.transferencia_da_linha(linha)
            return self.receita_ou_despesa(linha)
        except LinhaRejeitada as rejeicao:
            return Rejeicao(linha.numero, str(rejeicao), self.aba)

    def valor_e_tipo(self, linha):
        """
        O valor sem sinal e o tipo pela coluna de valor (o sinal decide,
        IMPORT-18) ou pelas colunas de entrada e de saída: a preenchida define
        o tipo, e as duas ou nenhuma rejeitam (IMPCOMP-18, IMPCOMP-19).
        """
        if self.colunas.get('amount_column') or not (
            self.colunas.get('income_column') or self.colunas.get('expense_column')
        ):
            valor = ler_valor(self.celula(linha, 'amount_column'))
            return abs(valor), tipo_pelo_sinal(valor)
        entrada = self.celula(linha, 'income_column')
        saida = self.celula(linha, 'expense_column')
        if (entrada is None) == (saida is None):
            raise LinhaRejeitada(VALOR_INVALIDO)
        if entrada is not None:
            return abs(ler_valor(entrada)), 'INCOME'
        return abs(ler_valor(saida)), 'EXPENSE'

    def receita_ou_despesa(self, linha):
        data = ler_data(self.celula(linha, 'date_column'))
        valor, tipo = self.valor_e_tipo(linha)

        tipo_na_linha = self.texto(linha, 'type_column')
        if tipo_na_linha is None:
            pass
        elif normalizar(tipo_na_linha) in TIPOS_DE_RECEITA:
            tipo = 'INCOME'
        elif normalizar(tipo_na_linha) in TIPOS_DE_DESPESA:
            tipo = 'EXPENSE'
        elif comparavel(tipo_na_linha) in TIPOS_DE_TRANSFERENCIA and self.colunas.get('dest_account_column'):
            # Transferência numa aba de receitas e despesas (IMPCOMP-20)
            return self.transferencia_da_linha(linha, origem='account_column', valor=valor)
        else:
            raise LinhaRejeitada(TIPO_DESCONHECIDO.format(valor=tipo_na_linha))

        descricao = self.texto(linha, 'description_column') or SEM_DESCRICAO
        categoria = self.texto(linha, 'category_column')
        subcategoria = self.texto(linha, 'subcategory_column') if categoria else None
        tags = self.tags(linha)
        conferir_tamanho(descricao, LIMITE_DA_DESCRICAO, 'descrição')
        conferir_tamanho(categoria, LIMITE_DO_NOME, 'categoria')
        conferir_tamanho(subcategoria, LIMITE_DO_NOME, 'subcategoria')
        for tag in tags:
            conferir_tamanho(tag, LIMITE_DO_NOME, 'tag')

        # Situações pendentes (IMPORT-20, IMPCOMP-16); as demais são efetivadas (IMPCOMP-17)
        situacao = self.texto(linha, 'status_column')
        status = 'PENDING' if comparavel(situacao) in STATUS_PENDENTE else 'COMPLETED'

        return LinhaImportada(
            numero=linha.numero, data=data, valor=valor, tipo=tipo, descricao=descricao,
            status=status, conta=self.conta(self.texto(linha, 'account_column')),
            categoria=categoria, subcategoria=subcategoria, tags=tags, aba=self.aba,
        )

    def transferencia_da_linha(self, linha, origem='source_account_column', valor=None):
        data = ler_data(self.celula(linha, 'date_column'))
        if valor is None:
            valor = ler_valor(self.celula(linha, 'amount_column'))
        descricao = self.texto(linha, 'description_column') or DESCRICAO_DA_TRANSFERENCIA
        tags = self.tags(linha)
        conferir_tamanho(descricao, LIMITE_DA_DESCRICAO, 'descrição')
        for tag in tags:
            conferir_tamanho(tag, LIMITE_DO_NOME, 'tag')

        conta_de_origem = self.conta(self.texto(linha, origem))
        destino = self.conta(self.texto(linha, 'dest_account_column'))
        if conta_de_origem.pk == destino.pk:
            raise LinhaRejeitada(ORIGEM_E_DESTINO_IGUAIS)
        return LinhaImportada(
            numero=linha.numero, data=data, valor=abs(valor), tipo='TRANSFER',
            descricao=descricao, conta=conta_de_origem, destino=destino, tags=tags, aba=self.aba,
        )

    def tags(self, linha):
        texto = self.texto(linha, 'tags_column')
        if texto is None:
            return []
        return [tag.strip() for tag in texto.split(',') if tag.strip()]

    def conta(self, nome):
        """
        A conta da linha: o mapeamento da tela, senão a conta do usuário com o
        mesmo nome sem acentos nem maiúsculas (IMPORT-21); sem nome, a conta
        padrão (IMPORT-22). Nunca cai na conta padrão quando há um nome. Com
        um `resolvedor`, a conta vem do plano da importação completa.
        """
        if nome is None:
            if self.conta_padrao is None:
                raise LinhaRejeitada(CONTA_NAO_INFORMADA)
            return conferir_conta_ativa(self.conta_padrao, self.conta_padrao.name)
        if self.resolvedor is not None:
            return self.resolvedor(nome)

        chave = normalizar(nome)
        if chave in self.mapa_de_contas:
            conta = self.contas_por_id.get(self.mapa_de_contas[chave])
        else:
            conta = self.contas_por_nome.get(chave)
        if conta is None:
            raise LinhaRejeitada(CONTA_NAO_MAPEADA.format(nome=nome))
        return conferir_conta_ativa(conta, nome)


class ResolvedorDeContas:
    """
    A conta de cada nome do arquivo pelo plano (`{nome no arquivo: conta}`),
    comparando os nomes sem maiúsculas, acentos e espaços extras. Na análise,
    a conta a criar é uma conta provisória, não gravada.
    """

    def __init__(self, contas):
        self.contas = {comparavel(nome): conta for nome, conta in contas.items()}

    def __call__(self, nome):
        conta = self.contas.get(comparavel(nome))
        if conta is None:
            raise LinhaRejeitada(CONTA_NAO_MAPEADA.format(nome=nome))
        return conferir_conta_ativa(conta, nome)


# Importação completa: correções, exclusões e rodapés do plano -------------

# Campo da correção de linha → campo do mapeamento (IMPCOMP-32)
CAMPOS_DA_CORRECAO = {
    'data': 'date_column', 'valor': 'amount_column', 'descricao': 'description_column',
    'conta': 'account_column', 'destino': 'dest_account_column', 'tipo': 'type_column',
    'situacao': 'status_column', 'categoria': 'category_column', 'subcategoria': 'subcategory_column',
    'tags': 'tags_column',
}
LINHA_INEXISTENTE = 'Linha inexistente no arquivo: {chave}.'


def chave_da_linha(aba, numero):
    """A chave da linha no plano: `"<aba>:<número>"`, com o número de IMPORT-30."""
    return f'{aba}:{numero}'


def conferir_chaves(abas, linhas_do_plano):
    """Recusa o plano com uma chave de linha que não existe no arquivo (IMPCOMP-35)."""
    existentes = {chave_da_linha(aba.nome, linha.numero) for aba in abas for linha in aba.linhas}
    for chave in linhas_do_plano or {}:
        if chave not in existentes:
            raise ValidationError({'plano': [LINHA_INEXISTENTE.format(chave=chave)]})


def corrigir(linha, colunas, correcao, transferencia):
    """
    A linha com os campos corrigidos no lugar das células, e o mapeamento da
    linha: um campo sem coluna na aba ganha uma coluna só desta linha. Um
    valor corrigido numa aba de entrada e saída passa a valer com sinal.
    """
    valores = dict(linha.valores)
    colunas = dict(colunas)
    for campo, valor in correcao.items():
        if campo not in CAMPOS_DA_CORRECAO:
            continue
        destino = CAMPOS_DA_CORRECAO[campo]
        if campo == 'conta' and transferencia:
            destino = 'source_account_column'
        if campo == 'valor':
            colunas.pop('income_column', None)
            colunas.pop('expense_column', None)
        coluna = colunas.get(destino) or f'__correcao_{campo}'
        colunas[destino] = coluna
        valores[coluna] = ', '.join(valor) if isinstance(valor, list) else valor
    return replace(linha, valores=valores), colunas


@dataclass
class LinhaDoArquivo:
    """
    Uma linha de uma aba usada na importação completa: a chave, a aba, a
    linha já corrigida, o mapeamento dela, o resultado da interpretação e se
    o plano a exclui (IMPCOMP-34).
    """
    chave: str
    aba: str
    linha: object
    colunas: dict
    resultado: object
    excluida: bool = False


def interpretar_aba(aba, plano_da_aba, resolvedor, correcoes, tags_liberadas=True):
    """
    Interpreta as linhas de uma aba usada com o papel e as colunas do plano:
    pula os rodapés de resumo (IMPCOMP-15), aplica as correções (IMPCOMP-32,
    IMPCOMP-33) e marca as excluídas (IMPCOMP-34). Com `tags` travado, as
    tags ficam de fora, também as das correções (IMPCOMP-51). Devolve as
    `LinhaDoArquivo` e a quantidade de rodapés pulados.
    """
    colunas = dict(plano_da_aba['colunas'])
    if not tags_liberadas:
        colunas.pop('tags_column', None)
    transferencia = plano_da_aba['papel'] == 'TRANSFERENCIAS'
    conferir_colunas(aba.cabecalho, list(dict.fromkeys(colunas.values())))
    interpretador = Interpretador(
        None, colunas, 'TRANSFER' if transferencia else 'INCOME_EXPENSE', None, None,
        aba=aba.nome, resolvedor=resolvedor,
    )

    linhas = []
    resumos = 0
    for linha in aba.linhas:
        if linha_de_resumo(linha, colunas):
            resumos += 1
            continue
        chave = chave_da_linha(aba.nome, linha.numero)
        correcao = dict(correcoes.get(chave) or {})
        excluida = bool(correcao.pop('excluir', False))
        if not tags_liberadas:
            correcao.pop('tags', None)
        linha_corrigida, colunas_da_linha = corrigir(linha, colunas, correcao, transferencia)
        resultado = interpretador.planilha(linha_corrigida, colunas_da_linha)
        linhas.append(LinhaDoArquivo(chave, aba.nome, linha_corrigida, colunas_da_linha, resultado, excluida))
    return linhas, resumos
