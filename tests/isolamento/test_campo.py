from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from rest_framework import serializers

from accounts.models import Account, CreditCardInvoice
from core.fields import (
    CATEGORIA_NAO_ENCONTRADA, CONTA_NAO_ENCONTRADA, TAG_NAO_ENCONTRADA,
    CARTAO_NAO_ENCONTRADO, OwnedPrimaryKeyRelatedField, get_owned_or_400,
)
from transactions.models import Category, Tag
from tests.isolamento.base import DoisUsuariosTestCase


class RelacoesDeTesteSerializer(serializers.Serializer):
    account = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True),
        not_found_message=CONTA_NAO_ENCONTRADA, required=False,
    )
    category = OwnedPrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        not_found_message=CATEGORIA_NAO_ENCONTRADA, required=False,
    )
    tags = OwnedPrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        not_found_message=TAG_NAO_ENCONTRADA, many=True, required=False,
    )
    invoice = OwnedPrimaryKeyRelatedField(
        queryset=CreditCardInvoice.objects.all(),
        not_found_message=CARTAO_NAO_ENCONTRADO, owner_field='card__user',
        required=False,
    )


class CampoDoDonoTests(DoisUsuariosTestCase):

    def validar(self, dados, usuario=None, com_request=True):
        contexto = {'request': SimpleNamespace(user=usuario or self.a.usuario)} if com_request else {}
        serializer = RelacoesDeTesteSerializer(data=dados, context=contexto)
        valido = serializer.is_valid()
        return valido, serializer

    def assert_recusa(self, dados, campo, mensagem):
        valido, serializer = self.validar(dados)
        self.assertFalse(valido)
        self.assertEqual(serializer.errors, {campo: [mensagem]})

    def test_objeto_proprio_e_aceito(self):
        valido, serializer = self.validar({
            'account': str(self.a.conta.id),
            'category': str(self.a.subcategoria.id),
            'invoice': str(self.a.fatura.id),
        })

        self.assertTrue(valido, serializer.errors)
        self.assertEqual(serializer.validated_data['account'], self.a.conta)
        self.assertEqual(serializer.validated_data['category'], self.a.subcategoria)
        self.assertEqual(serializer.validated_data['invoice'], self.a.fatura)

    def test_objeto_de_outro_usuario_e_recusado(self):
        self.assert_recusa({'account': str(self.b.conta.id)}, 'account', 'Conta não encontrada.')
        self.assert_recusa({'category': str(self.b.categoria.id)}, 'category', 'Categoria não encontrada.')
        self.assert_recusa({'tags': [str(self.b.tag.id)]}, 'tags', 'Tag não encontrada.')

    def test_id_inexistente_e_recusado_com_a_mesma_mensagem(self):
        self.assert_recusa({'account': self.ID_INEXISTENTE}, 'account', 'Conta não encontrada.')
        self.assert_recusa({'category': self.ID_INEXISTENTE}, 'category', 'Categoria não encontrada.')
        self.assert_recusa({'tags': [self.ID_INEXISTENTE]}, 'tags', 'Tag não encontrada.')

    def test_categoria_modelo_sem_dono_e_recusada(self):
        self.assert_recusa(
            {'category': str(self.categoria_modelo.id)}, 'category', 'Categoria não encontrada.',
        )

    def test_uuid_malformado_e_recusado_com_a_mesma_mensagem(self):
        for valor in ('nao-e-um-uuid', '1234', '00000000-0000-4000-8000-00000000000Z'):
            with self.subTest(valor=valor):
                self.assert_recusa({'account': valor}, 'account', 'Conta não encontrada.')

    def test_tipo_errado_e_recusado_com_a_mesma_mensagem(self):
        for valor in (123, 12.5, True, {'id': str(self.a.conta.id)}, [str(self.a.conta.id)]):
            with self.subTest(valor=valor):
                self.assert_recusa({'account': valor}, 'account', 'Conta não encontrada.')

    def test_many_com_uma_tag_alheia_no_meio_recusa_o_campo_inteiro(self):
        tag_a2 = Tag.objects.create(user=self.a.usuario, name='Outra A')

        self.assert_recusa(
            {'tags': [str(self.a.tag.id), str(self.b.tag.id), str(tag_a2.id)]},
            'tags', 'Tag não encontrada.',
        )

        valido, serializer = self.validar({'tags': [str(self.a.tag.id), str(tag_a2.id)]})
        self.assertTrue(valido, serializer.errors)
        self.assertEqual(serializer.validated_data['tags'], [self.a.tag, tag_a2])

    def test_sem_request_nenhum_objeto_e_aceito(self):
        valido, serializer = self.validar({'account': str(self.a.conta.id)}, com_request=False)

        self.assertFalse(valido)
        self.assertEqual(serializer.errors, {'account': ['Conta não encontrada.']})

    def test_sem_usuario_autenticado_recusa_categoria_modelo_e_objetos_de_qualquer_usuario(self):
        """
        Sem `request`, ou com usuário anônimo, o campo não pode cair num filtro
        por dono nulo, que aceitaria a categoria-modelo (ISOL-10).
        """
        casos = [
            ({'category': str(self.categoria_modelo.id)}, 'category', 'Categoria não encontrada.'),
            ({'category': str(self.b.categoria.id)}, 'category', 'Categoria não encontrada.'),
            ({'category': str(self.a.categoria.id)}, 'category', 'Categoria não encontrada.'),
            ({'account': str(self.b.conta.id)}, 'account', 'Conta não encontrada.'),
            ({'tags': [str(self.a.tag.id)]}, 'tags', 'Tag não encontrada.'),
        ]
        contextos = {
            'sem request': {},
            'usuario anonimo': {'request': SimpleNamespace(user=AnonymousUser())},
        }
        for nome, contexto in contextos.items():
            for dados, campo, mensagem in casos:
                with self.subTest(contexto=nome, dados=dados):
                    serializer = RelacoesDeTesteSerializer(data=dados, context=contexto)

                    self.assertFalse(serializer.is_valid())
                    self.assertEqual(serializer.errors, {campo: [mensagem]})

    def test_mantem_o_filtro_extra_do_queryset(self):
        self.a.conta.is_active = False
        self.a.conta.save()

        self.assert_recusa({'account': str(self.a.conta.id)}, 'account', 'Conta não encontrada.')

    def test_owner_field_filtra_pelo_dono_indicado(self):
        self.assert_recusa({'invoice': str(self.b.fatura.id)}, 'invoice', 'Cartão não encontrado.')


class GetOwnedOr400Tests(DoisUsuariosTestCase):

    def test_devolve_o_objeto_proprio(self):
        conta = get_owned_or_400(
            Account.objects.all(), self.a.usuario, str(self.a.conta.id),
            'account_id', CONTA_NAO_ENCONTRADA,
        )

        self.assertEqual(conta, self.a.conta)

    def test_levanta_erro_no_campo_nos_demais_casos(self):
        casos = [
            (Account.objects.all(), str(self.b.conta.id), 'Conta não encontrada.'),
            (Account.objects.all(), self.ID_INEXISTENTE, 'Conta não encontrada.'),
            (Account.objects.all(), 'nao-e-um-uuid', 'Conta não encontrada.'),
            (Account.objects.all(), 123, 'Conta não encontrada.'),
            (Account.objects.all(), None, 'Conta não encontrada.'),
            (Category.objects.all(), str(self.categoria_modelo.id), 'Categoria não encontrada.'),
        ]
        for queryset, pk, mensagem in casos:
            with self.subTest(pk=pk):
                with self.assertRaises(serializers.ValidationError) as ctx:
                    get_owned_or_400(queryset, self.a.usuario, pk, 'campo_x', mensagem)
                self.assertEqual(ctx.exception.detail, {'campo_x': [mensagem]})

    def test_owner_field_filtra_pelo_dono_indicado(self):
        fatura = get_owned_or_400(
            CreditCardInvoice.objects.all(), self.a.usuario, str(self.a.fatura.id),
            'invoice', CARTAO_NAO_ENCONTRADO, owner_field='card__user',
        )
        self.assertEqual(fatura, self.a.fatura)

        with self.assertRaises(serializers.ValidationError) as ctx:
            get_owned_or_400(
                CreditCardInvoice.objects.all(), self.a.usuario, str(self.b.fatura.id),
                'invoice', CARTAO_NAO_ENCONTRADO, owner_field='card__user',
            )
        self.assertEqual(ctx.exception.detail, {'invoice': ['Cartão não encontrado.']})
