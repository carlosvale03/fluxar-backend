"""
Gravação das linhas e resumo da importação (IMPORT-23, IMPORT-25, IMPORT-27
a IMPORT-31, IMPORT-39, IMPORT-40, IMPORT-43, IMPORT-44, IMPORT-47, AD-043).

Roda dentro da transação da requisição (`ATOMIC_REQUESTS`). Trava as contas
envolvidas em ordem de id antes de procurar os repetidos, grava cada linha
num savepoint próprio e recalcula os saldos uma vez no fim. Uma falha de
banco rejeita só a linha; o texto da exceção vai para o log, não para a
resposta (CONTRATO-29).
"""
import logging
import uuid

from django.db import transaction

from accounts.models import Account
from accounts.saldo import recalculo_adiado
from transactions.models import Category, CorrecaoDeCategoria, Tag, Transaction
from transactions.services import TransactionService

from .interpretacao import LinhaImportada, Rejeicao
from .repetidos import Repetidos
from .texto import normalizar, normalizar_descricao

logger = logging.getLogger(__name__)

ERRO_AO_GRAVAR = 'Erro ao gravar a linha'


def linha_rejeitada(rejeicao):
    """`{line, reason}` da rejeição, com `sheet` na importação completa (IMPORT-30, IMPCOMP-21)."""
    item = {'line': rejeicao.linha, 'reason': rejeicao.motivo}
    if rejeicao.aba is not None:
        item['sheet'] = rejeicao.aba
    return item


class Gravacao:
    """Grava as linhas de uma importação para o usuário e monta o resumo."""

    def __init__(self, usuario):
        self.usuario = usuario
        self.lote = uuid.uuid4()
        # Categorias e tags do usuário pelo nome sem acentos nem maiúsculas (IMPORT-23)
        self.categorias = {
            (normalizar(c.name), c.type, c.parent_id): c
            for c in Category.objects.filter(user=usuario, is_active=True)
        }
        self.tags = {normalizar(t.name): t for t in Tag.objects.filter(user=usuario)}
        # Só as correções do próprio usuário, a mais recente de cada
        # descrição, carregadas uma vez por importação (IMPORT-43, IMPORT-49)
        self.correcoes = {
            c.descricao_normalizada: c.categoria_depois
            for c in CorrecaoDeCategoria.objects.filter(user=usuario)
            .select_related('categoria_depois')
            .order_by('descricao_normalizada', '-criada_em')
            .distinct('descricao_normalizada')
        }

    def importar(self, resultados):
        """
        Grava as `LinhaImportada` de `resultados` e devolve o resumo
        `{total, imported, ignored, rejected, suggested, batch_id,
        rejected_rows}` (IMPORT-29, IMPORT-30).
        """
        validas = [r for r in resultados if isinstance(r, LinhaImportada)]
        rejeitadas = [r for r in resultados if isinstance(r, Rejeicao)]
        gravadas = ignoradas = sugeridas = 0
        por_aba = []  # (aba, 'imported' | 'ignored') de cada linha válida

        with transaction.atomic():
            self.travar_contas(validas)
            repetidos = Repetidos(self.usuario, validas)
            with recalculo_adiado():
                for linha in validas:
                    if repetidos.ignorar(linha):
                        ignoradas += 1
                        por_aba.append((linha.aba, 'ignored'))
                        continue
                    try:
                        novas = {'categorias': {}, 'tags': {}}
                        with transaction.atomic():
                            sugerida = self.gravar(linha, novas)
                    except Exception as erro:  # noqa: BLE001 - qualquer falha rejeita só a linha (IMPORT-28)
                        # Só a classe do erro: a mensagem e o traceback podem
                        # trazer descrição e valor da linha (LGPD-21)
                        logger.error(
                            'Falha ao gravar a linha %s da importação %s (%s).',
                            linha.numero, self.lote, type(erro).__name__,
                        )
                        rejeitadas.append(Rejeicao(linha.numero, ERRO_AO_GRAVAR, linha.aba))
                        continue
                    # O cache só recebe as categorias e tags novas depois que o savepoint confirma
                    self.categorias.update(novas['categorias'])
                    self.tags.update(novas['tags'])
                    gravadas += 1
                    sugeridas += sugerida
                    por_aba.append((linha.aba, 'imported'))

        # Na ordem das abas e, dentro de cada uma, pelo número da linha
        ordem_das_abas = {}
        for resultado in resultados:
            ordem_das_abas.setdefault(resultado.aba, len(ordem_das_abas))
        rejeitadas.sort(key=lambda r: (ordem_das_abas.get(r.aba, 0), r.linha))
        # Totais por aba da importação completa (IMPCOMP-47)
        self.por_aba = {}
        for aba, chave in [(r.aba, 'rejected') for r in rejeitadas] + por_aba:
            if aba is not None:
                totais = self.por_aba.setdefault(aba, {'imported': 0, 'ignored': 0, 'rejected': 0})
                totais[chave] += 1
        return {
            'total': len(resultados),
            'imported': gravadas,
            'ignored': ignoradas,
            'rejected': len(rejeitadas),
            'suggested': sugeridas,
            'batch_id': str(self.lote),
            'rejected_rows': [linha_rejeitada(r) for r in rejeitadas],
        }

    def travar_contas(self, linhas):
        """
        Trava as contas do arquivo em ordem de id: uma segunda importação para
        as mesmas contas espera esta terminar e, ao procurar os repetidos,
        encontra as linhas já gravadas (IMPORT-39).
        """
        ids = {linha.conta.pk for linha in linhas} | {linha.destino.pk for linha in linhas if linha.destino}
        list(Account.objects.select_for_update().filter(pk__in=ids).order_by('pk'))

    def gravar(self, linha, novas):
        """Grava a linha e diz se ela recebeu categoria sugerida (IMPORT-44)."""
        sugerida = None
        if linha.tipo == 'TRANSFER':
            # Mesmas regras e mensagens da spec saldo (IMPORT-25)
            transfer_id = TransactionService.create_transfer(
                user=self.usuario, account_from=linha.conta, account_to=linha.destino,
                amount=linha.valor, date=linha.data, description=linha.descricao,
            )
            pernas = list(Transaction.objects.filter(transfer_id=transfer_id, user=self.usuario))
            Transaction.objects.filter(pk__in=[p.pk for p in pernas]).update(import_batch=self.lote)
        else:
            categoria = self.categoria(linha, novas)
            if categoria is None:
                sugerida = self.sugestao(linha)
            pernas = [Transaction.objects.create(
                user=self.usuario, account=linha.conta, type=linha.tipo, status=linha.status,
                amount=linha.valor, date=linha.data, description=linha.descricao,
                category=categoria or sugerida, categoria_sugerida=sugerida is not None,
                import_batch=self.lote, fitid=linha.fitid,
            )]
        # Transação nova não tem tags: grava as ligações numa consulta só (IMPORT-40)
        tags = {self.tag(nome, novas).pk for nome in linha.tags}
        Transaction.tags.through.objects.bulk_create([
            Transaction.tags.through(transaction_id=perna.pk, tag_id=tag) for perna in pernas for tag in tags
        ])
        return sugerida is not None

    def sugestao(self, linha):
        """
        A categoria da correção mais recente para a descrição da linha, se ela
        ainda existe, está ativa e tem o tipo da linha; senão, `None`
        (IMPORT-43, IMPORT-47).
        """
        categoria = self.correcoes.get(normalizar_descricao(linha.descricao))
        if categoria is None or not categoria.is_active or categoria.type != linha.tipo:
            return None
        return categoria

    def categoria(self, linha, novas):
        """A categoria e a subcategoria da linha, criadas quando o usuário ainda não as tem (IMPORT-23)."""
        if not linha.categoria:
            return None
        principal = self.obter_categoria(linha.categoria, linha.tipo, None, novas)
        if not linha.subcategoria:
            return principal
        return self.obter_categoria(linha.subcategoria, linha.tipo, principal, novas)

    def obter_categoria(self, nome, tipo, pai, novas):
        chave = (normalizar(nome), tipo, pai.pk if pai else None)
        existente = self.categorias.get(chave) or novas['categorias'].get(chave)
        if existente:
            return existente
        criada = Category.objects.create(user=self.usuario, name=nome, type=tipo, parent=pai)
        novas['categorias'][chave] = criada
        return criada

    def tag(self, nome, novas):
        chave = normalizar(nome)
        existente = self.tags.get(chave) or novas['tags'].get(chave)
        if existente:
            return existente
        criada = Tag.objects.create(user=self.usuario, name=nome)
        novas['tags'][chave] = criada
        return criada
