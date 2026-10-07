"""
Paginação das listas grandes: transações e as listas do admin (AD-021).

As coleções pequenas vêm completas, porque `DEFAULT_PAGINATION_CLASS` é
`None`; esta classe é ligada só onde a lista é paginada.
"""
from django.core.paginator import InvalidPage, Page
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class _PaginaVazia(Page):
    """Página fora da lista: sem itens e sem vizinhas (CONTRATO-04)."""

    def has_next(self):
        return False

    def has_previous(self):
        return False


class PaginacaoPadrao(PageNumberPagination):
    """
    20 itens por padrão e até 100 com `page_size` (CONTRATO-03), no formato
    `count`, `total_pages`, `current_page`, `next`, `previous` e `results`
    (CONTRATO-02).
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        paginator = self.django_paginator_class(queryset, self.get_page_size(request))
        numero = request.query_params.get(self.page_query_param) or 1
        if numero in self.last_page_strings:
            numero = paginator.num_pages
        try:
            self.page = paginator.page(numero)
        except InvalidPage:
            # Página além da última, ou que não é número: 200 com a lista
            # vazia e os totais corretos, sem o 404 do DRF (CONTRATO-04)
            self.page = _PaginaVazia([], self._numero_pedido(numero), paginator)
        return list(self.page)

    @staticmethod
    def _numero_pedido(numero):
        """O número pedido, se for um inteiro positivo; senão, 1."""
        try:
            numero = int(numero)
        except (TypeError, ValueError):
            return 1
        return numero if numero >= 1 else 1

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })
