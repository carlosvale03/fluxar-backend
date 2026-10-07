"""
Interpretação de cada linha: tipo, sinal, descrição do OFX, status, conta,
transferência e limites de texto (IMPORT-16 a IMPORT-22, IMPORT-24,
IMPORT-26). Nada é gravado nessa etapa.
"""
from datetime import date, datetime
from decimal import Decimal

from accounts.models import Account
from data_exchange.importacao.interpretacao import (
    Interpretador, LinhaImportada, Rejeicao, interpretar_ofx,
)
from data_exchange.importacao.leitura import LinhaBruta, TransacaoOfx
from transactions.models import Transaction

from .base import MAPEAMENTO, ImportacaoTestCase

COM_TIPO = {**MAPEAMENTO, 'type_column': 'Tipo'}
COMPLETO = {
    **COM_TIPO, 'status_column': 'Situação', 'category_column': 'Categoria',
    'subcategory_column': 'Subcategoria', 'tags_column': 'Tags', 'account_column': 'Conta',
}
TRANSFERENCIA = {
    'date_column': 'Data', 'amount_column': 'Valor', 'description_column': 'Descrição',
    'source_account_column': 'Origem', 'dest_account_column': 'Destino',
}


class InterpretacaoTestCase(ImportacaoTestCase):

    def interpretador(self, mapeamento=COMPLETO, import_type='INCOME_EXPENSE', conta_padrao=None,
                      mapa_de_contas=None, usar_padrao=True):
        if usar_padrao and conta_padrao is None:
            conta_padrao = self.a.conta
        return Interpretador(self.a.usuario, mapeamento, import_type, conta_padrao, mapa_de_contas or {})

    def linha(self, numero=2, **valores):
        base = {'Data': '10/09/2026', 'Descrição': 'Padaria', 'Valor': '-45,00'}
        base.update(valores)
        return LinhaBruta(numero, base)

    def assert_rejeitada(self, resultado, numero, motivo):
        self.assertEqual(resultado, Rejeicao(numero, motivo))


class TipoTests(InterpretacaoTestCase):

    def test_palavras_de_receita_sem_diferenciar_maiusculas_nem_acentos(self):
        """IMPORT-16: "Crédito", "CREDITO", "Entrada", "C" e "receita" viram receita sem sinal."""
        interpretador = self.interpretador()
        for tipo in ('Crédito', 'CREDITO', 'Entrada', 'C', 'receita', ' c '):
            with self.subTest(tipo=tipo):
                resultado = interpretador.planilha(self.linha(Tipo=tipo, Valor='-100,00'))
                self.assertIsInstance(resultado, LinhaImportada)
                self.assertEqual((resultado.tipo, resultado.valor), ('INCOME', Decimal('100.00')))

    def test_palavras_de_despesa_sem_diferenciar_maiusculas_nem_acentos(self):
        """IMPORT-16: "Débito", "saída", "D" e "DESPESA" viram despesa sem sinal."""
        interpretador = self.interpretador()
        for tipo in ('Débito', 'saída', 'D', 'DESPESA', 'Saida'):
            with self.subTest(tipo=tipo):
                resultado = interpretador.planilha(self.linha(Tipo=tipo, Valor='45,00'))
                self.assertEqual((resultado.tipo, resultado.valor), ('EXPENSE', Decimal('45.00')))

    def test_tipo_desconhecido_rejeita_com_o_valor_original(self):
        """IMPORT-17: "Transferido" rejeita com "Tipo desconhecido: Transferido"."""
        resultado = self.interpretador().planilha(self.linha(numero=7, Tipo='Transferido'))
        self.assert_rejeitada(resultado, 7, 'Tipo desconhecido: Transferido')

    def test_sem_coluna_de_tipo_o_sinal_decide(self):
        """IMPORT-18: sem coluna de tipo, -45,00 é despesa de 45.00 e 100 é receita."""
        interpretador = self.interpretador(MAPEAMENTO)
        despesa = interpretador.planilha(self.linha(Valor='-45,00'))
        receita = interpretador.planilha(self.linha(Valor='100'))
        self.assertEqual((despesa.tipo, despesa.valor), ('EXPENSE', Decimal('45.00')))
        self.assertEqual((receita.tipo, receita.valor), ('INCOME', Decimal('100.00')))

        # Coluna de tipo mapeada, mas vazia na linha: também pelo sinal
        vazia = self.interpretador(COM_TIPO).planilha(self.linha(Tipo='', Valor='-45,00'))
        self.assertEqual((vazia.tipo, vazia.valor), ('EXPENSE', Decimal('45.00')))


class ValorEDataTests(InterpretacaoTestCase):

    def test_celulas_tipadas_e_textos_brasileiros(self):
        """IMPORT-09 a IMPORT-11, IMPORT-13 e IMPORT-14: célula e texto dão o mesmo valor e data."""
        interpretador = self.interpretador(MAPEAMENTO)
        casos = [
            ({'Valor': 1500, 'Data': datetime(2026, 3, 4)}, Decimal('1500.00'), date(2026, 3, 4)),
            ({'Valor': '1.500', 'Data': '04/03/26'}, Decimal('1500.00'), date(2026, 3, 4)),
            ({'Valor': -45.5, 'Data': date(2026, 3, 4)}, Decimal('45.50'), date(2026, 3, 4)),
            ({'Valor': 'R$ -45,00', 'Data': '2026-03-04'}, Decimal('45.00'), date(2026, 3, 4)),
        ]
        for valores, valor, data in casos:
            with self.subTest(valores=valores):
                resultado = interpretador.planilha(self.linha(**valores))
                self.assertEqual((resultado.valor, resultado.data), (valor, data))

    def test_valor_e_data_invalidos_rejeitam_a_linha(self):
        """IMPORT-12 e IMPORT-15: os motivos "Valor inválido" e "Data inválida"."""
        interpretador = self.interpretador(MAPEAMENTO)
        for numero, valores, motivo in [
            (3, {'Valor': 'abc'}, 'Valor inválido'),
            (4, {'Valor': '0,00'}, 'Valor inválido'),
            (5, {'Valor': 0}, 'Valor inválido'),
            (6, {'Valor': 45.555}, 'Valor inválido'),
            (7, {'Valor': ''}, 'Valor inválido'),
            (8, {'Data': '29/02/2025'}, 'Data inválida'),
            (9, {'Data': ''}, 'Data inválida'),
        ]:
            with self.subTest(valores=valores):
                self.assert_rejeitada(interpretador.planilha(self.linha(numero, **valores)), numero, motivo)


class OfxTests(InterpretacaoTestCase):

    def ofx(self, valor='-45.00', memo='', favorecido='', fitid='F1'):
        return TransacaoOfx(3, date(2026, 9, 10), Decimal(valor), memo, favorecido, fitid)

    def test_descricao_pelo_memo_pelo_favorecido_ou_sem_descricao(self):
        """IMPORT-19: memo, senão favorecido, senão "Sem descrição"."""
        self.assertEqual(interpretar_ofx(self.ofx(memo='Padaria', favorecido='Loja'), self.a.conta).descricao, 'Padaria')
        self.assertEqual(interpretar_ofx(self.ofx(favorecido='Loja'), self.a.conta).descricao, 'Loja')
        self.assertEqual(interpretar_ofx(self.ofx(), self.a.conta).descricao, 'Sem descrição')

    def test_sinal_decide_o_tipo_e_o_fitid_vai_junto(self):
        """IMPORT-18 e IMPORT-34: negativo é despesa, positivo é receita; o FITID segue a linha."""
        despesa = interpretar_ofx(self.ofx('-45.00', memo='Padaria'), self.a.conta)
        receita = interpretar_ofx(self.ofx('100.50', memo='Pix', fitid='F2'), self.a.conta)

        self.assertEqual(despesa, LinhaImportada(
            numero=3, data=date(2026, 9, 10), valor=Decimal('45.00'), tipo='EXPENSE',
            descricao='Padaria', status='COMPLETED', conta=self.a.conta, fitid='F1', ofx=True,
        ))
        self.assertEqual((receita.tipo, receita.valor, receita.fitid), ('INCOME', Decimal('100.50'), 'F2'))

    def test_conta_excluida_rejeita_a_transacao(self):
        """IMPORT-21: conta excluída não recebe movimentação (AD-003)."""
        antiga = Account.objects.create(user=self.a.usuario, name='Antiga', type='CHECKING', is_active=False)
        self.assert_rejeitada(interpretar_ofx(self.ofx(memo='Padaria'), antiga), 3, 'Conta excluída: Antiga')


class StatusTests(InterpretacaoTestCase):

    def test_pendente_ou_pending_importam_pendentes_e_o_resto_efetivada(self):
        """IMPORT-20: "Pendente" e "pending" são pendentes; "Pago", vazio e sem coluna, efetivadas."""
        interpretador = self.interpretador()
        for situacao, status in [('Pendente', 'PENDING'), ('pending', 'PENDING'), ('PENDENTE', 'PENDING'),
                                 ('Pago', 'COMPLETED'), ('', 'COMPLETED')]:
            with self.subTest(situacao=situacao):
                self.assertEqual(interpretador.planilha(self.linha(**{'Situação': situacao})).status, status)
        self.assertEqual(self.interpretador(MAPEAMENTO).planilha(self.linha()).status, 'COMPLETED')


class ContaTests(InterpretacaoTestCase):

    def test_conta_pelo_mapeamento_ou_pelo_nome(self):
        """IMPORT-21: o mapeamento da tela vale primeiro; depois, o nome sem acento nem maiúsculas."""
        interpretador = self.interpretador(mapa_de_contas={'Nubank': str(self.a.poupanca.id)})
        self.assertEqual(interpretador.planilha(self.linha(Conta='Nubank')).conta, self.a.poupanca)
        self.assertEqual(interpretador.planilha(self.linha(Conta='POUPANCA A')).conta, self.a.poupanca)
        self.assertEqual(interpretador.planilha(self.linha(Conta=' corrente a ')).conta, self.a.conta)

    def test_conta_nao_mapeada_rejeita_sem_cair_na_conta_padrao(self):
        """IMPORT-21: "Conta não mapeada: <nome>", inclusive mapeada para a conta de outro usuário."""
        interpretador = self.interpretador(mapa_de_contas={'Banco B': str(self.b.conta.id)})
        self.assert_rejeitada(interpretador.planilha(self.linha(Conta='Banco X')), 2, 'Conta não mapeada: Banco X')
        self.assert_rejeitada(interpretador.planilha(self.linha(Conta='Banco B')), 2, 'Conta não mapeada: Banco B')

    def test_conta_excluida_rejeita(self):
        """IMPORT-21: conta mapeada ou de mesmo nome que está excluída rejeita com "Conta excluída: <nome>"."""
        antiga = Account.objects.create(user=self.a.usuario, name='Antiga', type='CHECKING', is_active=False)
        interpretador = self.interpretador(mapa_de_contas={'Velha': str(antiga.id)})
        self.assert_rejeitada(interpretador.planilha(self.linha(Conta='Velha')), 2, 'Conta excluída: Velha')
        self.assert_rejeitada(interpretador.planilha(self.linha(Conta='antiga')), 2, 'Conta excluída: antiga')

        # A conta padrão excluída também não recebe a linha
        sem_coluna = self.interpretador(MAPEAMENTO, conta_padrao=antiga)
        self.assert_rejeitada(sem_coluna.planilha(self.linha()), 2, 'Conta excluída: Antiga')

    def test_sem_conta_na_linha_usa_a_padrao_ou_rejeita(self):
        """IMPORT-22: sem conta na linha e sem conta padrão, "Conta não informada"."""
        com_padrao = self.interpretador()
        self.assertEqual(com_padrao.planilha(self.linha(Conta='')).conta, self.a.conta)

        sem_padrao = self.interpretador(usar_padrao=False)
        self.assert_rejeitada(sem_padrao.planilha(self.linha(Conta='')), 2, 'Conta não informada')
        self.assert_rejeitada(
            self.interpretador(MAPEAMENTO, usar_padrao=False).planilha(self.linha()), 2, 'Conta não informada',
        )


class TransferenciaTests(InterpretacaoTestCase):

    def transferencia(self, **valores):
        base = {'Data': '10/09/2026', 'Descrição': 'Reserva', 'Valor': '200,00',
                'Origem': 'Corrente A', 'Destino': 'Poupança A'}
        base.update(valores)
        return LinhaBruta(4, base)

    def test_transferencia_entre_as_contas_mapeadas(self):
        """IMPORT-25: a linha vira transferência da origem para o destino."""
        resultado = self.interpretador(TRANSFERENCIA, 'TRANSFER').planilha(self.transferencia())
        self.assertEqual(
            (resultado.tipo, resultado.conta, resultado.destino, resultado.valor, resultado.descricao),
            ('TRANSFER', self.a.conta, self.a.poupanca, Decimal('200.00'), 'Reserva'),
        )

    def test_origem_igual_ao_destino_ou_conta_nao_mapeada_rejeitam(self):
        """IMPORT-26: "Origem e destino iguais" e "Conta não mapeada: <nome>"."""
        antiga = Account.objects.create(user=self.a.usuario, name='Antiga', type='CHECKING', is_active=False)
        interpretador = self.interpretador(TRANSFERENCIA, 'TRANSFER')
        self.assert_rejeitada(
            interpretador.planilha(self.transferencia(Destino='corrente a')), 4, 'Origem e destino iguais',
        )
        self.assert_rejeitada(
            interpretador.planilha(self.transferencia(Destino='Banco X')), 4, 'Conta não mapeada: Banco X',
        )
        self.assert_rejeitada(
            interpretador.planilha(self.transferencia(Origem=antiga.name)), 4, 'Conta excluída: Antiga',
        )


class TextoLongoTests(InterpretacaoTestCase):

    def test_textos_acima_do_limite_rejeitam_com_a_coluna(self):
        """IMPORT-24: descrição acima de 255; categoria, subcategoria ou tag acima de 50."""
        interpretador = self.interpretador()
        for valores, coluna in [
            ({'Descrição': 'x' * 300}, 'descrição'),
            ({'Categoria': 'c' * 51}, 'categoria'),
            ({'Categoria': 'Casa', 'Subcategoria': 's' * 51}, 'subcategoria'),
            ({'Tags': f'viagem, {"t" * 60}'}, 'tag'),
        ]:
            with self.subTest(coluna=coluna):
                self.assert_rejeitada(interpretador.planilha(self.linha(**valores)), 2, f'Texto longo demais: {coluna}')

    def test_textos_no_limite_passam_com_categoria_e_tags(self):
        """IMPORT-24: 255 e 50 caracteres ainda cabem; as tags vêm separadas por vírgula."""
        resultado = self.interpretador().planilha(self.linha(**{
            'Descrição': 'd' * 255, 'Categoria': 'c' * 50, 'Subcategoria': 'Feira', 'Tags': ' viagem, ,trabalho ',
        }))
        self.assertEqual(
            (len(resultado.descricao), resultado.categoria, resultado.subcategoria, resultado.tags),
            (255, 'c' * 50, 'Feira', ['viagem', 'trabalho']),
        )

    def test_nada_e_gravado(self):
        """A interpretação não grava nada."""
        antes = Transaction.objects.count()
        self.interpretador().planilha(self.linha())
        interpretar_ofx(TransacaoOfx(1, date(2026, 9, 10), Decimal('-1.00'), 'X', '', 'F'), self.a.conta)
        self.assertEqual(Transaction.objects.count(), antes)
