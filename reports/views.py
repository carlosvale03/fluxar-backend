import re

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from core.datas import hoje
from core.filtros import ParametrosConhecidosMixin
from .services import ReportService
from core.travas import RecursoLiberado
from .models import FocusedMonitorItem
from .serializers import FocusedMonitorItemSerializer

MESES_FORA_DO_LIMITE = 'O parâmetro months aceita de 1 a 24.'


def ler_meses(request, padrao=6):
    """
    O parâmetro `months`: inteiro de 1 a 24, ou `padrao` quando não vem;
    qualquer outro valor recebe 400 (REL-12, PERF-05).
    """
    texto = request.query_params.get('months')
    if texto is None:
        return padrao
    if not re.fullmatch(r'[0-9]+', texto) or not 1 <= int(texto) <= 24:
        raise ValidationError({'detail': MESES_FORA_DO_LIMITE})
    return int(texto)

class ReportViewSet(ParametrosConhecidosMixin, viewsets.ViewSet):
    """
    ViewSet para relatórios e dashboards. Não possui model associado.

    O dashboard e os gráficos simples são essenciais (PERM-14); as outras
    ações exigem a trava do plano delas (PERM-15).
    """
    permission_classes = [permissions.IsAuthenticated]
    # Parâmetros conhecidos de cada relatório (CONTRATO-14)
    parametros_por_acao = {
        'dashboard': frozenset({'month', 'year', 'days'}),
        'calendar': frozenset({'month', 'year', 'period', 'days'}),
        'charts_simple': frozenset({'month', 'year', 'period', 'days'}),
        'tag_distribution': frozenset({'month', 'year', 'period', 'days'}),
        'charts_advanced': frozenset({'period', 'days'}),
        'monthly_comparison': frozenset({'months', 'month', 'year'}),
        'tag_insights': frozenset({'tag_id', 'months'}),
        'linked_expenses': frozenset({'month', 'year', 'period', 'days'}),
    }

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        try:
            month = request.query_params.get('month')
            year = request.query_params.get('year')
            days = request.query_params.get('days') # Novo parâmetro para range fixo
            
            # Mês atual de Brasília quando não vem (REL-08)
            month = int(month) if month else hoje().month
            year = int(year) if year else hoje().year
        except ValueError:
            # Erros no formato do DRF, em português (CONTRATO-29)
            raise ValidationError({'detail': 'Mês/Ano inválidos.'})
            
        data = ReportService.get_dashboard_summary(request.user, month, year, period_days=days)
        return Response(data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated, RecursoLiberado('calendario')])
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

    @action(detail=False, methods=['get'], url_path='charts/advanced', permission_classes=[permissions.IsAuthenticated, RecursoLiberado('relatorios_avancados')])
    def charts_advanced(self, request):
        period = request.query_params.get('period') or request.query_params.get('days')
        data = ReportService.get_advanced_charts(request.user, period_days=period)
        return Response(data)
    @action(detail=False, methods=['get'], url_path='charts/monthly-comparison', permission_classes=[permissions.IsAuthenticated, RecursoLiberado('comparacao_mensal')])
    def monthly_comparison(self, request):
        months = ler_meses(request)
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        data = ReportService.get_monthly_comparison(request.user, months=months, month=month, year=year)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/tag-insights', permission_classes=[permissions.IsAuthenticated, RecursoLiberado('analise_por_tag')])
    def tag_insights(self, request):
        tag_id = request.query_params.get('tag_id')
        months = ler_meses(request)
        
        if not tag_id:
            raise ValidationError({'tag_id': ['Este campo é obrigatório.']})
            
        data = ReportService.get_tag_insights(request.user, tag_id, months=months)
        if data is None:
            raise NotFound('Tag não encontrada.')
            
        return Response(data)

    @action(detail=False, methods=['get'], url_path='charts/tag-distribution', permission_classes=[permissions.IsAuthenticated, RecursoLiberado('analise_por_tag')])
    def tag_distribution(self, request):
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        period = request.query_params.get('period') or request.query_params.get('days')
        
        data = ReportService.get_tag_distribution(request.user, month, year, period_days=period)
        return Response(data)

    @action(
        detail=False, methods=['get'], url_path='linked-expenses',
        permission_classes=[permissions.IsAuthenticated, RecursoLiberado('vinculos')],
    )
    def linked_expenses(self, request):
        """Gastos puxados por categoria (VINCULO-34, VINCULO-35), travado pelo plano (VINCULO-20)."""
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        period = request.query_params.get('period') or request.query_params.get('days')
        return Response(ReportService.get_linked_expenses(request.user, month, year, period_days=period))



class FocusedMonitorViewSet(ParametrosConhecidosMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('monitor_de_foco')]
    serializer_class = FocusedMonitorItemSerializer

    def get_queryset(self):
        return FocusedMonitorItem.objects.filter(user=self.request.user)
