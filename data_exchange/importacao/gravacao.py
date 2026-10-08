"""
Gravação das linhas e resumo da importação (IMPORT-23, IMPORT-25, IMPORT-27
a IMPORT-31, IMPORT-39, IMPORT-40, AD-043).

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
from transactions.models import Category, Tag, Transaction
from transactions.services import TransactionService

from .interpretacao import LinhaImportada, Rejeicao
from .repetidos import Repetidos
from .texto import normalizar

logger = logging.getLogger(__name__)

ERRO_AO_GRAVAR = 'Erro ao gravar a linha'


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

    def importar(self, resultados):
        """
        Grava as `LinhaImportada` de `resultados` e devolve o resumo
        `{total, imported, ignored, rejected, suggested, batch_id,
        rejected_rows}` (IMPORT-29, IMPORT-30).
        """
        validas = [r for r in resultados if isinstance(r, LinhaImportada)]
        rejeitadas = [r for r in resultados if isinstance(r, Rejeicao)]
        gravadas = ignoradas = 0

        with transaction.atomic():
            self.travar_contas(validas)
            repetidos = Repetidos(self.usuario, validas)
            with recalculo_adiado():
                for linha in validas:
                    if repetidos.ignorar(linha):
                        ignoradas += 1
                        continue
                    try:
                        novas = {'categorias': {}, 'tags': {}}
                        with transaction.atomic():
                            self.gravar(linha, novas)
                    except Exception:  # noqa: BLE001 - qualquer falha rejeita só a linha (IMPORT-28)
                        logger.exception('Falha ao gravar a linha %s da importação %s', linha.numero, self.lote)
                        rejeitadas.append(Rejeicao(linha.numero, ERRO_AO_GRAVAR))
                        continue
                    # O cache só recebe as categorias e tags novas depois que o savepoint confirma
                    self.categorias.update(novas['categorias'])
                    self.tags.update(novas['tags'])
                    gravadas += 1

        rejeitadas.sort(key=lambda r: r.linha)
        return {
            'total': len(resultados),
            'imported': gravadas,
            'ignored': ignoradas,
            'rejected': len(rejeitadas),
            'suggested': 0,
            'batch_id': str(self.lote),
            'rejected_rows': [{'line': r.linha, 'reason': r.motivo} for r in rejeitadas],
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
        if linha.tipo == 'TRANSFER':
            # Mesmas regras e mensagens da spec saldo (IMPORT-25)
            transfer_id = TransactionService.create_transfer(
                user=self.usuario, account_from=linha.conta, account_to=linha.destino,
                amount=linha.valor, date=linha.data, description=linha.descricao,
            )
            pernas = list(Transaction.objects.filter(transfer_id=transfer_id, user=self.usuario))
            Transaction.objects.filter(pk__in=[p.pk for p in pernas]).update(import_batch=self.lote)
        else:
            pernas = [Transaction.objects.create(
                user=self.usuario, account=linha.conta, type=linha.tipo, status=linha.status,
                amount=linha.valor, date=linha.data, description=linha.descricao,
                category=self.categoria(linha, novas), import_batch=self.lote, fitid=linha.fitid,
            )]
        # Transação nova não tem tags: grava as ligações numa consulta só (IMPORT-40)
        tags = {self.tag(nome, novas).pk for nome in linha.tags}
        Transaction.tags.through.objects.bulk_create([
            Transaction.tags.through(transaction_id=perna.pk, tag_id=tag) for perna in pernas for tag in tags
        ])

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
