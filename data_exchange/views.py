from rest_framework import views, status, permissions, parsers
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
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
        
        return Response(result, status=status.HTTP_200_OK if result['created'] > 0 else status.HTTP_400_BAD_REQUEST)

class ImportSpreadsheetView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        account_id = request.data.get('account_id')
        
        mapping = {
            'date_column': request.data.get('date_column', 'date'),
            'description_column': request.data.get('description_column', 'description'),
            'amount_column': request.data.get('amount_column', 'amount'),
            'type_column': request.data.get('type_column'),
        }
        
        if not file_obj:
            return Response({'error': 'Arquivo não enviado.'}, status=400)
            
        account = get_object_or_404(Account, id=account_id, user=request.user)
        
        result = ImportService.process_spreadsheet(file_obj, mapping, account, request.user)
        
        return Response(result, status=status.HTTP_200_OK if result['created'] > 0 else status.HTTP_400_BAD_REQUEST)

class ExportTransactionsPDFView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsPremium]

    def get(self, request):
        qs = Transaction.objects.filter(user=request.user)
        
        account_id = request.query_params.get('account')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        
        if account_id: qs = qs.filter(account_id=account_id)
        if month and year: qs = qs.filter(date__month=month, date__year=year)
        
        qs = qs.order_by('date')
        
        buffer = ExportService.generate_pdf(qs, request.user)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="relatorio_fluxar.pdf"'
        return response

class ExportTransactionsXLSView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsPremium]

    def get(self, request):
        qs = Transaction.objects.filter(user=request.user)
        
        account_id = request.query_params.get('account')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        
        if account_id: qs = qs.filter(account_id=account_id)
        if month and year: qs = qs.filter(date__month=month, date__year=year)
        
        qs = qs.order_by('date')
        
        buffer = ExportService.generate_xls(qs)
        
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="relatorio_fluxar.xlsx"'
        return response
