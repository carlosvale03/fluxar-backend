"""
Plano da importação completa (IMPCOMP-14, IMPCOMP-24, IMPCOMP-28,
IMPCOMP-36, AD-055).

O plano chega como texto JSON no multipart, no campo `plano`:

    {
      "abas": [{"nome", "papel", "colunas": {campo: cabeçalho}}],
      "contas": {nome no arquivo: {"acao": "vincular", "id"}
                                 | {"acao": "criar", "nome", "tipo", "saldo_atual", "institution", "color"}},
      "linhas": {"<aba>:<número>": {"excluir": true} | {campo corrigido: valor}}
    }

Tudo é opcional: o que faltar vem da detecção. Os erros voltam no campo
`plano`, com o caminho dos campos aninhados.
"""
import json

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from accounts.models import Account
from core.fields import CONTA_NAO_ENCONTRADA, get_owned_or_400

from .importacao.deteccao import CAMPOS, CRIAR, PAPEIS, VINCULAR

PLANO_MALFORMADO = 'Plano inválido: JSON malformado.'
CAMPO_DESCONHECIDO = 'Campo desconhecido: {campo}.'
TAGS_INVALIDAS = 'Informe as tags como texto ou lista de textos.'


class AbaDoPlanoSerializer(serializers.Serializer):
    nome = serializers.CharField(trim_whitespace=False)
    papel = serializers.ChoiceField(choices=PAPEIS)
    colunas = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True, trim_whitespace=False), required=False,
    )

    def validate_colunas(self, colunas):
        for campo in colunas:
            if campo not in CAMPOS:
                raise serializers.ValidationError(CAMPO_DESCONHECIDO.format(campo=campo))
        return colunas


class ContaDoPlanoSerializer(serializers.Serializer):
    acao = serializers.ChoiceField(choices=(VINCULAR, CRIAR))
    id = serializers.CharField(required=False, allow_null=True)
    nome = serializers.CharField(max_length=100, required=False)
    tipo = serializers.ChoiceField(choices=Account.ACCOUNT_TYPE_CHOICES, required=False)
    # Qualquer valor com até duas casas, inclusive zero e negativo (como `ler_saldo`)
    saldo_atual = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    institution = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    color = serializers.CharField(max_length=7, required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if attrs['acao'] == VINCULAR:
            # Conta de outro usuário, inexistente ou excluída: a mesma mensagem (AD-010, IMPCOMP-24)
            attrs['conta'] = get_owned_or_400(
                Account.objects.filter(is_active=True), self.context['request'].user,
                attrs.get('id'), 'id', CONTA_NAO_ENCONTRADA,
            )
            return attrs
        faltando = {
            campo: [self.fields[campo].error_messages['required']]
            for campo in ('nome', 'tipo', 'saldo_atual') if campo not in attrs
        }
        if faltando:
            raise serializers.ValidationError(faltando)
        return attrs


class TagsDaCorrecaoField(serializers.Field):
    """As tags corrigidas, como texto separado por vírgulas ou lista de textos."""
    default_error_messages = {'invalid': TAGS_INVALIDAS}

    def to_internal_value(self, data):
        if isinstance(data, str) or (isinstance(data, list) and all(isinstance(t, str) for t in data)):
            return data
        self.fail('invalid')

    def to_representation(self, value):
        return value


def texto_corrigido():
    return serializers.CharField(required=False, allow_blank=True, allow_null=True)


class LinhaDoPlanoSerializer(serializers.Serializer):
    excluir = serializers.BooleanField(required=False)
    data = texto_corrigido()
    valor = texto_corrigido()
    descricao = texto_corrigido()
    conta = texto_corrigido()
    destino = texto_corrigido()
    tipo = texto_corrigido()
    situacao = texto_corrigido()
    categoria = texto_corrigido()
    subcategoria = texto_corrigido()
    tags = TagsDaCorrecaoField(required=False, allow_null=True)


class PlanoSerializer(serializers.Serializer):
    modelo = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    abas = serializers.ListField(child=AbaDoPlanoSerializer(), required=False)
    contas = serializers.DictField(child=ContaDoPlanoSerializer(), required=False)
    linhas = serializers.DictField(child=LinhaDoPlanoSerializer(), required=False)


def ler_plano(request):
    """
    O plano validado do campo `plano` do multipart, ou `{}` sem ele. JSON
    malformado ou formato errado recebem 400 no campo `plano` (IMPCOMP-36).
    """
    bruto = request.data.get('plano')
    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        return {}
    try:
        dados = json.loads(bruto)
    except (TypeError, ValueError):
        raise ValidationError({'plano': [PLANO_MALFORMADO]}) from None
    serializer = PlanoSerializer(data=dados, context={'request': request})
    if not serializer.is_valid():
        raise ValidationError({'plano': serializer.errors})
    return serializer.validated_data
