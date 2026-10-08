"""
Interpretação de cada linha (IMPORT-16 a IMPORT-22, IMPORT-24, IMPORT-26).

Transforma uma linha bruta da leitura numa `LinhaImportada` (data, valor sem
sinal, tipo, descrição, status, conta ou contas, categoria, tags e FITID) ou
numa `Rejeicao` com o número da linha e o motivo. Nada é gravado aqui; o
único acesso ao banco é o mapa de contas do usuário, carregado uma vez.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from accounts.models import Account
from core.valores import CENTAVO, VALOR_INVALIDO, ler_valor_em_texto

from .leitura import tipo_da_importacao, vazio
from .texto import DATA_INVALIDA, ler_data_em_texto, normalizar

TIPOS_DE_RECEITA = {'receita', 'entrada', 'credito', 'c'}
TIPOS_DE_DESPESA = {'despesa', 'saida', 'debito', 'd'}
STATUS_PENDENTE = {'pendente', 'pending'}

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


@dataclass(frozen=True)
class Rejeicao:
    linha: int
    motivo: str


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


class Interpretador:
    """
    Interpreta as linhas de uma planilha com o mapeamento de colunas, o tipo
    de importação, a conta padrão (ou `None`) e o mapeamento de contas da
    tela (`{nome na planilha: id da conta}`).
    """

    def __init__(self, usuario, mapeamento, import_type, conta_padrao, mapa_de_contas):
        self.mapeamento = mapeamento
        self.transferencia = tipo_da_importacao(import_type) == 'TRANSFER'
        self.conta_padrao = conta_padrao
        # Só as contas do usuário (isolamento): id de outra conta não é encontrado
        contas = list(Account.objects.filter(user=usuario))
        self.contas_por_id = {str(c.pk): c for c in contas}
        self.contas_por_nome = {}
        for conta in sorted(contas, key=lambda c: c.is_active):
            # A ativa prevalece sobre uma excluída de mesmo nome
            self.contas_por_nome[normalizar(conta.name)] = conta
        self.mapa_de_contas = {normalizar(nome): str(i) for nome, i in (mapa_de_contas or {}).items()}

    def celula(self, linha, campo):
        coluna = self.mapeamento.get(campo)
        if not coluna:
            return None
        valor = linha.valores.get(coluna)
        return None if vazio(valor) else valor

    def texto(self, linha, campo):
        valor = self.celula(linha, campo)
        return None if valor is None else str(valor).strip()

    def planilha(self, linha):
        try:
            if self.transferencia:
                return self.transferencia_da_linha(linha)
            return self.receita_ou_despesa(linha)
        except LinhaRejeitada as rejeicao:
            return Rejeicao(linha.numero, str(rejeicao))

    def receita_ou_despesa(self, linha):
        data = ler_data(self.celula(linha, 'date_column'))
        valor = ler_valor(self.celula(linha, 'amount_column'))

        tipo_na_linha = self.texto(linha, 'type_column')
        if tipo_na_linha is None:
            tipo = tipo_pelo_sinal(valor)
        elif normalizar(tipo_na_linha) in TIPOS_DE_RECEITA:
            tipo = 'INCOME'
        elif normalizar(tipo_na_linha) in TIPOS_DE_DESPESA:
            tipo = 'EXPENSE'
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

        situacao = self.texto(linha, 'status_column')
        status = 'PENDING' if normalizar(situacao) in STATUS_PENDENTE else 'COMPLETED'

        return LinhaImportada(
            numero=linha.numero, data=data, valor=abs(valor), tipo=tipo, descricao=descricao,
            status=status, conta=self.conta(self.texto(linha, 'account_column')),
            categoria=categoria, subcategoria=subcategoria, tags=tags,
        )

    def transferencia_da_linha(self, linha):
        data = ler_data(self.celula(linha, 'date_column'))
        valor = ler_valor(self.celula(linha, 'amount_column'))
        descricao = self.texto(linha, 'description_column') or DESCRICAO_DA_TRANSFERENCIA
        tags = self.tags(linha)
        conferir_tamanho(descricao, LIMITE_DA_DESCRICAO, 'descrição')
        for tag in tags:
            conferir_tamanho(tag, LIMITE_DO_NOME, 'tag')

        origem = self.conta(self.texto(linha, 'source_account_column'))
        destino = self.conta(self.texto(linha, 'dest_account_column'))
        if origem.pk == destino.pk:
            raise LinhaRejeitada(ORIGEM_E_DESTINO_IGUAIS)
        return LinhaImportada(
            numero=linha.numero, data=data, valor=abs(valor), tipo='TRANSFER',
            descricao=descricao, conta=origem, destino=destino, tags=tags,
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
        padrão (IMPORT-22). Nunca cai na conta padrão quando há um nome.
        """
        if nome is None:
            if self.conta_padrao is None:
                raise LinhaRejeitada(CONTA_NAO_INFORMADA)
            return conferir_conta_ativa(self.conta_padrao, self.conta_padrao.name)

        chave = normalizar(nome)
        if chave in self.mapa_de_contas:
            conta = self.contas_por_id.get(self.mapa_de_contas[chave])
        else:
            conta = self.contas_por_nome.get(chave)
        if conta is None:
            raise LinhaRejeitada(CONTA_NAO_MAPEADA.format(nome=nome))
        return conferir_conta_ativa(conta, nome)
