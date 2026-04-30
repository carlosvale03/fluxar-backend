from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date
from .services import ReportService
from .permissions import IsPremium
from .models import FocusedMonitorItem
from .serializers import FocusedMonitorItemSerializer

class ReportViewSet(viewsets.ViewSet):
    """
    ViewSet para relatórios e dashboards. Não possui model associado.
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        try:
            month = request.query_params.get('month')
            year = request.query_params.get('year')
            days = request.query_params.get('days') # Novo parâmetro para range fixo
            
            month = int(month) if month else date.today().month
            year = int(year) if year else date.today().year
        except ValueError:
            return Response({"error": "Mês/Ano inválidos"}, status=status.HTTP_400_BAD_REQUEST)
            
        data = ReportService.get_dashboard_summary(request.user, month, year, period_days=days)
        return Response(data)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        period = request.query_params.get('period') or request.query_params.get('days')
        
        data = ReportService.get_calendar_data(request.user, month, year, period_days=period)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/simple')
    def charts_simple(self, request):
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        period = request.query_params.get('period') or request.query_params.get('days')
            
        data = ReportService.get_simple_charts(request.user, month, year, period_days=period)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/advanced', permission_classes=[permissions.IsAuthenticated, IsPremium])
    def charts_advanced(self, request):
        # Premium Only
        period = request.query_params.get('period') or request.query_params.get('days')
        data = ReportService.get_advanced_charts(request.user, period_days=period)
        return Response(data)
    @action(detail=False, methods=['get'], url_path='charts/monthly-comparison')
    def monthly_comparison(self, request):
        months = int(request.query_params.get('months', 6))
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        data = ReportService.get_monthly_comparison(request.user, months=months, month=month, year=year)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/tag-insights')
    def tag_insights(self, request):
        tag_id = request.query_params.get('tag_id')
        months = int(request.query_params.get('months', 6))
        
        if not tag_id:
            return Response({"error": "tag_id é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)
            
        data = ReportService.get_tag_insights(request.user, tag_id, months=months)
        if data is None:
            return Response({"error": "Tag não encontrada"}, status=status.HTTP_404_NOT_FOUND)
            
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/tag-distribution')
    def tag_distribution(self, request):
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        period = request.query_params.get('period') or request.query_params.get('days')
        
        data = ReportService.get_tag_distribution(request.user, month, year, period_days=period)
        return Response(data)



class FocusedMonitorViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsPremium]
    serializer_class = FocusedMonitorItemSerializer

    def get_queryset(self):
        return FocusedMonitorItem.objects.filter(user=self.request.user)
