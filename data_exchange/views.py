import json
from rest_framework import views, status, permissions, parsers
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from accounts.models import Account
from transactions.models import Transaction
from .services import ImportService, ExportService
# Tenta importar IsPremium, fallback para IsAuthenticated se não existir (evita crash se BD-007 não tiver ok)
try:
    from reports.permissions import IsPremium
except ImportError:
    IsPremium = permissions.IsAuthenticated

class ImportOFXView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    
    def post(self, request):
        file_obj = request.FILES.get('file')
        account_id = request.data.get('account_id')
        
        if not file_obj:
            return Response({'error': 'Arquivo não enviado.'}, status=400)
        
        account = get_object_or_404(Account, id=account_id, user=request.user)
        
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
            return Response({'error': 'Arquivo não enviado.'}, status=400)
        
        try:
            unique_accounts = ImportService.preflight_spreadsheet(file_obj, mapping, import_type)
            return Response({'accounts': unique_accounts}, status=200)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

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
            return Response({'error': 'Arquivo não enviado.'}, status=400)
            
        account = get_object_or_404(Account, id=account_id, user=request.user) if account_id else None
        
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

class ExportTransactionsPDFView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsPremium]

    def get(self, request):
        qs = Transaction.objects.filter(user=request.user)
        
        # Extração de parâmetros da query string
        account_id = request.query_params.get('accountId')
        category_id = request.query_params.get('categoryId')
        type_ = request.query_params.get('type')
        start_date_str = request.query_params.get('startDate')
        end_date_str = request.query_params.get('endDate')
        tag_ids = request.query_params.getlist('tagIds') or request.query_params.getlist('tagIds[]')
        tags_str = request.query_params.get('tagIds')

        if account_id and account_id != 'ALL': 
            qs = qs.filter(account_id=account_id)
        
        if category_id and category_id != 'ALL':
            qs = qs.filter(category_id=category_id)

        if type_ and type_ != 'ALL':
            qs = qs.filter(type=type_)

        if start_date_str:
            dt = parse_datetime(start_date_str)
            if dt: qs = qs.filter(date__gte=dt.date())

        if end_date_str:
            dt = parse_datetime(end_date_str)
            if dt: qs = qs.filter(date__lte=dt.date())

        if tag_ids:
            qs = qs.filter(tags__id__in=tag_ids).distinct()
        elif tags_str:
            ids = [tid.strip() for tid in tags_str.split(',') if tid.strip()]
            if ids:
                qs = qs.filter(tags__id__in=ids).distinct()
        
        qs = qs.order_by('date')
        
        buffer = ExportService.generate_pdf(qs, request.user)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="relatorio_fluxar.pdf"'
        return response

class ExportTransactionsXLSView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsPremium]

    def get(self, request):
        qs = Transaction.objects.filter(user=request.user)
        
        # Extração de parâmetros da query string
        account_id = request.query_params.get('accountId')
        category_id = request.query_params.get('categoryId')
        type_ = request.query_params.get('type')
        start_date_str = request.query_params.get('startDate')
        end_date_str = request.query_params.get('endDate')
        tag_ids = request.query_params.getlist('tagIds') or request.query_params.getlist('tagIds[]')
        tags_str = request.query_params.get('tagIds')

        if account_id and account_id != 'ALL': 
            qs = qs.filter(account_id=account_id)
        
        if category_id and category_id != 'ALL':
            qs = qs.filter(category_id=category_id)

        if type_ and type_ != 'ALL':
            qs = qs.filter(type=type_)

        if start_date_str:
            dt = parse_datetime(start_date_str)
            if dt: qs = qs.filter(date__gte=dt.date())

        if end_date_str:
            dt = parse_datetime(end_date_str)
            if dt: qs = qs.filter(date__lte=dt.date())

        if tag_ids:
            qs = qs.filter(tags__id__in=tag_ids).distinct()
        elif tags_str:
            ids = [tid.strip() for tid in tags_str.split(',') if tid.strip()]
            if ids:
                qs = qs.filter(tags__id__in=ids).distinct()
        
        qs = qs.order_by('date')
        
        buffer = ExportService.generate_xls(qs)
        
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="relatorio_fluxar.xlsx"'
        return response
