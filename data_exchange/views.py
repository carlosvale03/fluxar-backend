import json
from rest_framework import views, status, permissions, parsers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.http import HttpResponse
from accounts.models import Account
from transactions.filtros import filtrar_transacoes
from transactions.models import Transaction
from .services import ImportService, ExportService
from core.fields import get_owned_or_400, CONTA_NAO_ENCONTRADA
from core.filtros import ParametrosConhecidosMixin
# Tenta importar IsPremium, fallback para IsAuthenticated se não existir (evita crash se BD-007 não tiver ok)
try:
    from reports.permissions import IsPremium
except ImportError:
    IsPremium = permissions.IsAuthenticated

# Erros no formato do DRF, em português e sem o texto da exceção (CONTRATO-29)
ARQUIVO_NAO_ENVIADO = 'Arquivo não enviado.'
ARQUIVO_ILEGIVEL = 'Não foi possível ler o arquivo. Confira o formato e as colunas escolhidas.'


class ImportOFXView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    
    def post(self, request):
        file_obj = request.FILES.get('file')
        account_id = request.data.get('account_id')
        
        if not file_obj:
            raise ValidationError({'file': [ARQUIVO_NAO_ENVIADO]})
        
        account = get_owned_or_400(
            Account.objects.all(), request.user, account_id, 'account_id', CONTA_NAO_ENCONTRADA,
        )
        
        result = ImportService.process_ofx(file_obj, account, request.user)
        
        # Garante que as chaves batam com o frontend (total, imported, ignored, errors)
        summary = {
            'total': result.get('total', 0),
            'imported': result.get('created', 0),
            'ignored': result.get('ignored', 0),
            'errors': len(result.get('errors', []))
        }
        
        return Response(summary, status=status.HTTP_200_OK if result['created'] > 0 else status.HTTP_400_BAD_REQUEST)

class ImportSpreadsheetPreflightView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
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
        
        try:
            unique_accounts = ImportService.preflight_spreadsheet(file_obj, mapping, import_type)
            return Response({'accounts': unique_accounts}, status=200)
        except Exception:
            raise ValidationError({'file': [ARQUIVO_ILEGIVEL]})

class ImportSpreadsheetView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
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
            account_mapping = json.loads(account_mapping_raw) if account_mapping_raw else None
        except:
            account_mapping = None
        
        if not file_obj:
            raise ValidationError({'file': [ARQUIVO_NAO_ENVIADO]})
            
        account = get_owned_or_400(
            Account.objects.all(), request.user, account_id, 'account_id', CONTA_NAO_ENCONTRADA,
        ) if account_id else None
        
        result = ImportService.process_spreadsheet(
            file_obj, mapping, account, request.user, 
            import_type=import_type, account_mapping=account_mapping
        )
        
        summary = {
            'total': result.get('total', 0),
            'imported': result.get('created', 0),
            'ignored': result.get('ignored', 0),
            'errors': len(result.get('errors', [])),
            'errors_list': result.get('errors', [])
        }
        
        return Response(summary, status=status.HTTP_200_OK if result['created'] >= 0 else status.HTTP_400_BAD_REQUEST)

# Parâmetros conhecidos da exportação (CONTRATO-14)
PARAMETROS_DA_EXPORTACAO = frozenset({
    'accountId', 'categoryId', 'type', 'startDate', 'endDate', 'tagIds', 'search',
})


class ExportTransactionsPDFView(ParametrosConhecidosMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsPremium]
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
    permission_classes = [permissions.IsAuthenticated, IsPremium]
    parametros_permitidos = PARAMETROS_DA_EXPORTACAO

    def get(self, request):
        # O mesmo filtro da lista de transações (CONTRATO-13)
        qs = filtrar_transacoes(
            Transaction.objects.filter(user=request.user), request.query_params, request.user,
        )
        qs = qs.order_by('date')
        
        buffer = ExportService.generate_xls(qs)
        
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="relatorio_fluxar.xlsx"'
        return response
