"""
Campos de importação na transação e correções de categoria (IMPORT-34,
IMPORT-42, IMPORT-48).
"""
import uuid
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction

from api.models import User
from transactions.models import CorrecaoDeCategoria, Transaction

from .base import ImportacaoTestCase


class CamposDeImportacaoTests(ImportacaoTestCase):

    def lancar(self, conta, fitid, **extra):
        return Transaction.objects.create(
            user=conta.user, account=conta, type='EXPENSE', description='Padaria',
            amount=Decimal('45.00'), date=date(2026, 9, 10), fitid=fitid, **extra,
        )

    def test_fitid_unico_por_conta(self):
        """IMPORT-34: o mesmo FITID não se repete na conta; em contas diferentes, pode."""
        lote = uuid.uuid4()
        primeira = self.lancar(self.a.conta, 'F1', import_batch=lote)
        self.lancar(self.a.poupanca, 'F1')

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.lancar(self.a.conta, 'F1')

        # Sem FITID (planilha ou importação antiga), a restrição não vale
        self.lancar(self.a.conta, None)
        self.lancar(self.a.conta, None)
        self.assertEqual(Transaction.objects.filter(account=self.a.conta).count(), 3)
        primeira.refresh_from_db()
        self.assertEqual((primeira.import_batch, primeira.categoria_sugerida), (lote, False))

    def test_correcoes_somem_com_o_usuario(self):
        """IMPORT-48 e IMPORT-42: a correção guarda os dados e é apagada com o usuário."""
        usuario = User.objects.create_user(email='correcoes@teste.fluxar', password='senha-de-teste-123')
        transacao = self.lancar(self.a.conta, None)
        correcao = CorrecaoDeCategoria.objects.create(
            user=usuario, transacao=transacao, descricao='UBER *TRIP 1234',
            descricao_normalizada='uber *trip', conta=self.a.conta,
            categoria_antes=None, categoria_depois=self.a.despesa,
        )
        CorrecaoDeCategoria.objects.create(
            user=self.a.usuario, descricao='Padaria', descricao_normalizada='padaria',
            categoria_depois=self.a.despesa,
        )
        correcao.refresh_from_db()
        self.assertIsNotNone(correcao.criada_em)

        usuario.delete()

        self.assertFalse(CorrecaoDeCategoria.objects.filter(pk=correcao.pk).exists())
        self.assertEqual(CorrecaoDeCategoria.objects.filter(user=self.a.usuario).count(), 1)
