"""
Linhas já importadas (IMPORT-34 a IMPORT-38): FITID no OFX, chave de data,
valor, tipo e descrição nos demais casos, e contagem das repetições
consumida na ordem do arquivo.
"""
import uuid
from datetime import date
from decimal import Decimal

from data_exchange.importacao.interpretacao import LinhaImportada
from data_exchange.importacao.repetidos import Repetidos, transacoes_existentes
from transactions.models import Transaction

from .base import ImportacaoTestCase


class RepetidosTests(ImportacaoTestCase):

    def lancar(self, conta=None, tipo='EXPENSE', valor='5.00', dia=10, descricao='Café', **extra):
        conta = conta or self.a.conta
        return Transaction.objects.create(
            user=conta.user, account=conta, type=tipo, description=descricao,
            amount=Decimal(valor), date=date(2026, 9, dia), **extra,
        )

    def linha(self, numero=2, conta=None, tipo='EXPENSE', valor='5.00', dia=10, descricao='Café', **extra):
        return LinhaImportada(
            numero=numero, data=date(2026, 9, dia), valor=Decimal(valor), tipo=tipo,
            descricao=descricao, conta=conta or self.a.conta, **extra,
        )

    def ignoradas(self, linhas):
        """Os números das linhas ignoradas, consumindo na ordem do arquivo."""
        repetidos = Repetidos(self.a.usuario, linhas)
        return [linha.numero for linha in linhas if repetidos.ignorar(linha)]

    def test_ofx_com_fitid_ja_gravado_e_ignorado_mesmo_com_descricao_editada(self):
        """IMPORT-34: o FITID na mesma conta basta; descrição e valor não importam."""
        self.lancar(descricao='Padaria do João (editada)', fitid='F1')
        linhas = [
            self.linha(1, descricao='PADARIA JOAO', fitid='F1', ofx=True),
            self.linha(2, descricao='PADARIA JOAO', fitid='F2', ofx=True),
            self.linha(3, conta=self.a.poupanca, descricao='PADARIA JOAO', fitid='F1', ofx=True),
        ]
        self.assertEqual(self.ignoradas(linhas), [1])

    def test_ofx_antigo_sem_fitid_e_reconhecido_pela_chave(self):
        """IMPORT-35: transação gravada sem FITID é comparada por data, valor, tipo e descrição."""
        self.lancar(descricao='Padaria')                 # importação antiga, sem FITID
        self.lancar(descricao='Mercado', fitid='OUTRO')  # com FITID: só o FITID vale
        linhas = [
            self.linha(1, descricao='Padaria', fitid='N1', ofx=True),
            self.linha(2, descricao='Mercado', fitid='N2', ofx=True),
            self.linha(3, descricao='Padaria', fitid=None, ofx=True),
        ]
        self.assertEqual(self.ignoradas(linhas), [1])

    def test_planilha_compara_data_valor_tipo_e_descricao_na_conta(self):
        """IMPORT-36: só a linha com a mesma chave na mesma conta é repetida."""
        self.lancar(fitid='F9')
        linhas = [
            self.linha(2),
            self.linha(3, conta=self.a.poupanca),
            self.linha(4, tipo='INCOME'),
            self.linha(5, valor='5.01'),
            self.linha(6, dia=11),
            self.linha(7, descricao='Cafe'),
        ]
        self.assertEqual(self.ignoradas(linhas), [2])

    def test_compras_iguais_no_mesmo_arquivo_contam_as_repeticoes(self):
        """IMPORT-38: N linhas iguais contra M existentes gravam N − M."""
        duas = [self.linha(2), self.linha(3)]
        self.assertEqual(self.ignoradas(duas), [])

        self.lancar()
        self.assertEqual(self.ignoradas(duas), [2])

        tres = [self.linha(2), self.linha(3), self.linha(4)]
        self.lancar()
        self.assertEqual(self.ignoradas(tres), [2, 3])
        self.lancar()
        self.lancar()
        self.assertEqual(self.ignoradas(tres), [2, 3, 4])

    def test_transferencia_igual_e_ignorada(self):
        """IMPORT-37: mesma origem, destino, data e valor."""
        transferencia = uuid.uuid4()
        self.lancar(tipo='TRANSFER_OUT', valor='200.00', descricao='Antiga', transfer_id=transferencia)
        self.lancar(conta=self.a.poupanca, tipo='TRANSFER_IN', valor='200.00', descricao='Antiga',
                    transfer_id=transferencia)
        linhas = [
            self.linha(2, tipo='TRANSFER', valor='200.00', descricao='Reserva', destino=self.a.poupanca),
            self.linha(3, tipo='TRANSFER', valor='200.00', descricao='Reserva', destino=self.a.poupanca),
            self.linha(4, conta=self.a.poupanca, tipo='TRANSFER', valor='200.00', destino=self.a.conta),
            self.linha(5, tipo='TRANSFER', valor='200.00', dia=11, destino=self.a.poupanca),
        ]
        self.assertEqual(self.ignoradas(linhas), [2])

    def test_consulta_limitada_as_contas_e_ao_periodo_do_arquivo(self):
        """A consulta carrega só as transações das contas e do período das linhas."""
        dentro = [self.lancar(dia=10), self.lancar(dia=15), self.lancar(dia=20)]
        self.lancar(dia=9)
        self.lancar(dia=21)
        self.lancar(conta=self.a.poupanca, dia=15)
        self.lancar(conta=self.b.conta, dia=15)

        linhas = [self.linha(2, dia=20), self.linha(3, dia=10)]
        self.assertEqual(
            set(transacoes_existentes(self.a.usuario, linhas).values_list('pk', flat=True)),
            {t.pk for t in dentro},
        )
