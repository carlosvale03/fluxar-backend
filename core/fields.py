"""
Relações que só aceitam objetos do usuário da requisição (AD-010, AD-032).

Qualquer ID que não seja do usuário (de outro usuário, inexistente,
categoria-modelo sem dono, UUID malformado ou tipo errado) recebe a mesma
mensagem, para que a resposta não revele se o ID existe em outra conta.
"""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from rest_framework import serializers

CONTA_NAO_ENCONTRADA = 'Conta não encontrada.'
CARTAO_NAO_ENCONTRADO = 'Cartão não encontrado.'
CATEGORIA_NAO_ENCONTRADA = 'Categoria não encontrada.'
TAG_NAO_ENCONTRADA = 'Tag não encontrada.'


def _buscar(queryset, pk):
    """Devolve o objeto `pk` do queryset ou None, qualquer que seja a falha."""
    try:
        if isinstance(pk, bool):
            raise TypeError
        return queryset.get(pk=pk)
    except (ObjectDoesNotExist, TypeError, ValueError, DjangoValidationError):
        return None


class OwnedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """
    `PrimaryKeyRelatedField` que filtra o queryset pelo dono
    (`owner_field`, por padrão `user`) igual a `request.user`. Sem `request`
    no contexto, nenhum objeto é aceito. Funciona com `many=True`.
    """

    def __init__(self, *, not_found_message, owner_field='user', **kwargs):
        self.not_found_message = not_found_message
        self.owner_field = owner_field
        super().__init__(**kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = getattr(self.context.get('request'), 'user', None)
        if user is None or not user.is_authenticated:
            return queryset.none()
        return queryset.filter(**{self.owner_field: user})

    def to_internal_value(self, data):
        obj = _buscar(self.get_queryset(), data)
        if obj is None:
            raise serializers.ValidationError(self.not_found_message)
        return obj


def get_owned_or_400(queryset, user, pk, field_name, message, owner_field='user'):
    """
    Para views que leem IDs direto de `request.data`: devolve o objeto `pk`
    do `user` ou levanta `ValidationError({field_name: [message]})` (HTTP 400).
    """
    obj = _buscar(queryset.filter(**{owner_field: user}), pk)
    if obj is None:
        raise serializers.ValidationError({field_name: [message]})
    return obj
