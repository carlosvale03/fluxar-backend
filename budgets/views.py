from rest_framework import viewsets, permissions
from .models import Budget
from .serializers import BudgetSerializer
from transactions.models import Category

class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Budget.objects.filter(user=self.request.user)
        
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        category = self.request.query_params.get('category')
        
        if month: qs = qs.filter(month=month)
        if year: qs = qs.filter(year=year)
        if category: qs = qs.filter(category_id=category)
        
        return qs.order_by('year', 'month', 'category__name')
