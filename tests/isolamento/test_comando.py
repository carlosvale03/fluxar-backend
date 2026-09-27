import re
from decimal import Decimal
from io import StringIO

from django.apps import apps
from django.core.management import call_command

from accounts.models import Account
from core.isolation import find_cross_links
from tests.isolamento.base import DoisUsuariosTestCase
from tests.isolamento.ligacoes import gravar_ligacoes_cruzadas

# Linha de uma ligação: tipo, ID do registro, relação e ID do objeto alheio
LINHA_DE_LIGACAO = re.compile(r'[A-Za-z]+ [0-9a-f-]+ [a-z_]+ [0-9a-f-]+')


def rodar(*args):
    saida = StringIO()
    call_command('check_isolation', *args, stdout=saida)
    return saida.getvalue().splitlines()


class ComandoCheckIsolationTests(DoisUsuariosTestCase):

    def test_base_sem_ligacoes_imprime_so_o_total_zero(self):
        self.assertEqual(rodar(), ['Ligações cruzadas: 0'])

    def test_lista_uma_linha_por_ligacao_e_o_total_sem_corrigir(self):
        registros = gravar_ligacoes_cruzadas(self.a, self.b, self.categoria_modelo)

        linhas = rodar()

        esperadas = [f'{tipo} {registro_id} {relacao} {alheio_id}'
                     for tipo, registro_id, relacao, alheio_id in registros.esperadas]
        self.assertEqual(sorted(linhas[:-1]), sorted(esperadas))
        self.assertEqual(linhas[-1], 'Ligações cruzadas: 18')
        # Sem --fix, nada é corrigido
        self.assertEqual(len(find_cross_links(apps)), 18)

    def test_saida_traz_so_tipos_e_ids_sem_nomes_valores_nem_emails(self):
        gravar_ligacoes_cruzadas(self.a, self.b, self.categoria_modelo)

        linhas = rodar('--fix')
        saida = '\n'.join(linhas)

        for linha in linhas[:-2]:
            self.assertRegex(linha, f'^{LINHA_DE_LIGACAO.pattern}$')
        for dado in ('@', 'Usuário', 'Conta', 'Cartão', 'Cofrinho', 'Meta ', 'Mercado', 'Viagem',
                     'Pendurada', 'Série', 'Lançamento', '.00', 'R$'):
            self.assertNotIn(dado, saida)

    def test_fix_corrige_e_imprime_o_resumo(self):
        gravar_ligacoes_cruzadas(self.a, self.b, self.categoria_modelo)

        linhas = rodar('--fix')

        self.assertEqual(linhas[-2], 'Ligações cruzadas: 18')
        self.assertEqual(linhas[-1], 'Ligações desfeitas: 18. Recalculados: contas 1, faturas 1, metas 1.')
        self.assertEqual(find_cross_links(apps), [])
        # A conta de B deixa de contar a receita de A (SALDO-01)
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1000.00'))
        self.assertEqual(rodar(), ['Ligações cruzadas: 0'])
