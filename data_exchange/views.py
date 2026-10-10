import json
from rest_framework import views, status, permissions, parsers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.http import HttpResponse
from accounts.models import Account
from transactions.classes import mapa_de_classes
from transactions.filtros import filtrar_transacoes
from transactions.models import Transaction
from .importacao.gravacao import Gravacao
from .importacao.interpretacao import Interpretador, interpretar_ofx
from .importacao.leitura import contas_da_planilha, ler_ofx, ler_planilha
from .services import ExportService
from core.fields import get_owned_or_400, CONTA_NAO_ENCONTRADA
from core.filtros import ParametrosConhecidosMixin
from core.travas import RecursoLiberado, acesso

# Erros no formato do DRF, em português e sem o texto da exceção (CONTRATO-29)
ARQUIVO_NAO_ENVIADO = 'Arquivo não enviado.'


class ImportOFXView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('importacao_ofx')]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    
    def post(self, request):
        file_obj = request.FILES.get('file')
        account_id = request.data.get('account_id')
        
        if not file_obj:
            raise ValidationError({'file': [ARQUIVO_NAO_ENVIADO]})
        
        account = get_owned_or_400(
            Account.objects.all(), request.user, account_id, 'account_id', CONTA_NAO_ENCONTRADA,
        )
        
        # Sempre 200 com o resumo quando o arquivo é aceito, inclusive com zero
        # gravadas (IMPORT-29, IMPORT-31)
        resultados = [interpretar_ofx(tx, account) for tx in ler_ofx(file_obj)]
        return Response(Gravacao(request.user).importar(resultados), status=status.HTTP_200_OK)

class ImportSpreadsheetPreflightView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('importacao_planilha')]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        import_type = request.data.get('import_type', 'INCOME_EXPENSE')
        mapping_raw = request.data.get('mapping')
        
        try:
            mapping = json.loads(mapping_raw) if mapping_raw else {}
        except:
            mapping = {}

        if not file_obj:
            raise ValidationError({'file': [ARQUIVO_NAO_ENVIADO]})

        # Mesmos formatos e limites da importação (IMPORT-02, IMPORT-04 a IMPORT-06)
        linhas = ler_planilha(file_obj, mapping, import_type)
        return Response({'accounts': contas_da_planilha(linhas, mapping, import_type)}, status=200)

class ImportSpreadsheetView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('importacao_planilha')]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        account_id = request.data.get('account_id')
        import_type = request.data.get('import_type', 'INCOME_EXPENSE')
        
        # O frontend envia mapping e account_mapping como string JSON
        mapping_raw = request.data.get('mapping')
        account_mapping_raw = request.data.get('account_mapping')
        
        try:
            mapping = json.loads(mapping_raw) if mapping_raw else {}
        except:
            mapping = {}

        try:
            account_mapping = json.loads(account_mapping_raw) if account_mapping_raw else {}
        except:
            account_mapping = {}
        
        if not file_obj:
            raise ValidationError({'file': [ARQUIVO_NAO_ENVIADO]})
            
        account = get_owned_or_400(
            Account.objects.all(), request.user, account_id, 'account_id', CONTA_NAO_ENCONTRADA,
        ) if account_id else None
        
        # Com `tags` travado, a coluna de tags é ignorada e a linha é gravada:
        # um recurso acessório não recusa uma linha válida (PERM-15)
        if not acesso(request.user).recurso_liberado('tags'):
            mapping.pop('tags_column', None)

        linhas = ler_planilha(file_obj, mapping, import_type)
        interpretador = Interpretador(request.user, mapping, import_type, account, account_mapping)
        resultados = [interpretador.planilha(linha) for linha in linhas]
        # Sempre 200 com o resumo quando o arquivo é aceito (IMPORT-29, IMPORT-31)
        return Response(Gravacao(request.user).importar(resultados), status=status.HTTP_200_OK)

# Parâmetros conhecidos da exportação (CONTRATO-14)
PARAMETROS_DA_EXPORTACAO = frozenset({
    'accountId', 'categoryId', 'classId', 'type', 'startDate', 'endDate', 'tagIds', 'search',
})


class ExportTransactionsPDFView(ParametrosConhecidosMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('exportacao_pdf')]
    parametros_permitidos = PARAMETROS_DA_EXPORTACAO

    def get(self, request):
        # O mesmo filtro da lista de transações (CONTRATO-13)
        qs = filtrar_transacoes(
            Transaction.objects.filter(user=request.user), request.query_params, request.user,
        )
        qs = qs.order_by('date')
        
        buffer = ExportService.generate_pdf(qs, request.user)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="relatorio_fluxar.pdf"'
        return response

class ExportTransactionsXLSView(ParametrosConhecidosMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('exportacao_xlsx')]
    parametros_permitidos = PARAMETROS_DA_EXPORTACAO

    def get(self, request):
        # O mesmo filtro da lista de transações (CONTRATO-13)
        qs = filtrar_transacoes(
            Transaction.objects.filter(user=request.user), request.query_params, request.user,
        )
        qs = qs.select_related('account', 'category__parent').prefetch_related('tags').order_by('date')

        buffer = ExportService.generate_xls(qs, mapa_de_classes(request.user))
        
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="relatorio_fluxar.xlsx"'
        return response
