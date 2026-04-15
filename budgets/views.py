from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import IntegrityError
from django.db.models import F
from .models import Budget
from .serializers import BudgetSerializer
from transactions.models import Category
from core.mixins import UserQuerySetMixin

class BudgetViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Budget.objects.all()
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Mixin já filtra por user. 
        # Precisamos filtrar os parametros adicionais sobre o resultado do mixin.
        qs = super().get_queryset()
        
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        category = self.request.query_params.get('category')
        
        start_month = self.request.query_params.get('start_month')
        start_year = self.request.query_params.get('start_year')
        end_month = self.request.query_params.get('end_month')
        end_year = self.request.query_params.get('end_year')

        if start_month and start_year and end_month and end_year:
            try:
                start_val = int(start_year) * 12 + int(start_month)
                end_val = int(end_year) * 12 + int(end_month)
                # Annotate and filter by period value (year*12 + month)
                qs = qs.annotate(p_val=F('year') * 12 + F('month')).filter(p_val__gte=start_val, p_val__lte=end_val)
            except ValueError:
                pass
        elif month: 
            qs = qs.filter(month=month)
            if year: qs = qs.filter(year=year)
        elif year: 
            qs = qs.filter(year=year)
        
        if category: qs = qs.filter(category_id=category)
        
        return qs.order_by('year', 'month', 'category__name')


    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """
        Importa orçamentos selecionados para o mês/ano especificado.
        Esperado no body: { "source_ids": ["uuid", ...], "month": 2, "year": 2026 }
        """
        source_ids = request.data.get('source_ids', [])
        month = request.data.get('month')
        year = request.data.get('year')

        if not source_ids or not month or not year:
            return Response(
                {"error": "Parâmetros source_ids, month e year são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            month = int(month)
            year = int(year)
        except ValueError:
            return Response(
                {"error": "Mês e ano devem ser números inteiros."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar orçamentos de origem
        source_budgets = Budget.objects.filter(
            user=request.user,
            id__in=source_ids
        )

        if not source_budgets.exists():
            return Response(
                {"error": "Nenhum orçamento de origem encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Identificar quais categorias já têm orçamento no mês atual para evitar duplicatas
        existing_categories = Budget.objects.filter(
            user=request.user,
            month=month,
            year=year
        ).values_list('category_id', flat=True)

        new_budgets = []
        skipped_count = 0
        for budget in source_budgets:
            if budget.category_id not in existing_categories:
                new_budgets.append(
                    Budget(
                        user=request.user,
                        category=budget.category,
                        month=month,
                        year=year,
                        amount_limit=budget.amount_limit
                    )
                )
            else:
                skipped_count += 1

        if not new_budgets:
            return Response(
                {"message": "Todos os orçamentos selecionados já existem no mês de destino.", "skipped": skipped_count},
                status=status.HTTP_200_OK
            )

        try:
            Budget.objects.bulk_create(new_budgets)
            return Response(
                {
                    "message": f"{len(new_budgets)} orçamentos importados com sucesso!", 
                    "imported_count": len(new_budgets),
                    "skipped_count": skipped_count
                },
                status=status.HTTP_201_CREATED
            )
        except IntegrityError:
            return Response(
                {"error": "Erro de integridade ao criar orçamentos. Verifique se já existem orçamentos para estas categorias."},
                status=status.HTTP_400_BAD_REQUEST
            )


