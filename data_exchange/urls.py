from django.urls import path
from .views import (
    ImportOFXView, ImportSpreadsheetView, 
    ExportTransactionsPDFView, ExportTransactionsXLSView
)

urlpatterns = [
    path('import/ofx/', ImportOFXView.as_view(), name='import_ofx'),
    path('import/spreadsheet/', ImportSpreadsheetView.as_view(), name='import_spreadsheet'),
    path('export/transactions/pdf/', ExportTransactionsPDFView.as_view(), name='export_pdf'),
    path('export/transactions/xls/', ExportTransactionsXLSView.as_view(), name='export_xls'),
]
