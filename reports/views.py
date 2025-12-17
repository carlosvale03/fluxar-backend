from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date
from .services import ReportService
from .permissions import IsPremium

class ReportViewSet(viewsets.ViewSet):
    """
    ViewSet para relatórios e dashboards. Não possui model associado.
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        data = ReportService.get_dashboard_summary(request.user)
        return Response(data)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        try:
            month = int(request.query_params.get('month', date.today().month))
            year = int(request.query_params.get('year', date.today().year))
        except ValueError:
            return Response({"error": "Mês/Ano inválidos"}, status=status.HTTP_400_BAD_REQUEST)
            
        data = ReportService.get_calendar_data(request.user, month, year)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/simple')
    def charts_simple(self, request):
        try:
            month = int(request.query_params.get('month', date.today().month))
            year = int(request.query_params.get('year', date.today().year))
        except ValueError:
            return Response({"error": "Mês/Ano inválidos"}, status=status.HTTP_400_BAD_REQUEST)
            
        data = ReportService.get_simple_charts(request.user, month, year)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/advanced', permission_classes=[permissions.IsAuthenticated, IsPremium])
    def charts_advanced(self, request):
        # Premium Only
        days = int(request.query_params.get('days', 90))
        data = ReportService.get_advanced_charts(request.user, period_days=days)
        return Response(data)
