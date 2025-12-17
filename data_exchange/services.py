import io
import pandas as pd
from ofxparse import OfxParser
from decimal import Decimal
from datetime import datetime
from transactions.models import Transaction, Category
from transactions.services import TransactionService
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

class ImportService:
    @staticmethod
    def process_ofx(file, account, user):
        """
        Lê arquivo OFX e cria transações.
        Retorna resumo: { 'total': N, 'created': N, 'errors': [] }
        """
        try:
            ofx = OfxParser.parse(file)
        except Exception as e:
            return {'total': 0, 'created': 0, 'errors': [f"Erro ao ler OFX: {str(e)}"]}
        
        created_count = 0
        errors = []
        
        if not ofx.account:
             return {'total': 0, 'created': 0, 'errors': ["Nenhuma conta encontrada no OFX"]}

        transactions = ofx.account.statement.transactions
        total = len(transactions)

        for tx in transactions:
            try:
                amount = Decimal(str(tx.amount))
                date = tx.date # datetime object
                description = tx.memo or tx.payee or "Sem descrição"
                
                # Definir tipo baseado no sinal
                if amount < 0:
                    type_ = 'EXPENSE'
                    amount = abs(amount)
                else:
                    type_ = 'INCOME'
                
                if type_ == 'INCOME':
                    TransactionService.create_income(
                        user=user,
                        account=account,
                        amount=amount,
                        date=date.date(),
                        description=description,
                        category=None
                    )
                else:
                    TransactionService.create_expense(
                        user=user,
                        account=account,
                        amount=amount,
                        date=date.date(),
                        description=description,
                        category=None
                    )
                created_count += 1
                
            except Exception as e:
                errors.append(f"Erro na transação {description}: {str(e)}")
        
        return {
            'total': total,
            'created': created_count,
            'errors': errors
        }

    @staticmethod
    def process_spreadsheet(file, mapping, account, user):
        """
        Lê CSV/XLS usando pandas e cria transações.
        """
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        except Exception as e:
            return {'total': 0, 'created': 0, 'errors': [f"Erro ao ler arquivo: {str(e)}"]}
            
        created_count = 0
        errors = []
        total = len(df)
        
        col_date = mapping.get('date_column')
        col_desc = mapping.get('description_column')
        col_amount = mapping.get('amount_column')
        col_type = mapping.get('type_column') 
        
        if not all([col_date, col_desc, col_amount]):
             return {'total': 0, 'created': 0, 'errors': ["Colunas obrigatórias não informadas"]}

        for index, row in df.iterrows():
            try:
                raw_date = row[col_date]
                description = str(row[col_desc])
                amount_val = row[col_amount]
                
                date = pd.to_datetime(raw_date).date()
                amount = Decimal(str(amount_val))
                type_ = 'EXPENSE' 
                
                if col_type and pd.notna(row[col_type]):
                    type_str = str(row[col_type]).upper()
                    if type_str in ['INCOME', 'RECEITA', 'C', 'CREDITO']:
                        type_ = 'INCOME'
                    elif type_str in ['EXPENSE', 'DESPESA', 'D', 'DEBITO']:
                        type_ = 'EXPENSE'
                else:
                    if amount < 0:
                        type_ = 'EXPENSE'
                        amount = abs(amount)
                    else:
                        type_ = 'INCOME'

                if type_ == 'INCOME':
                    TransactionService.create_income(
                        user=user,
                        account=account,
                        amount=amount,
                        date=date,
                        description=description,
                        category=None
                    )
                else:
                    TransactionService.create_expense(
                        user=user,
                        account=account,
                        amount=amount,
                        date=date,
                        description=description,
                        category=None
                    )
                created_count += 1

            except Exception as e:
                errors.append(f"Linha {index}: {str(e)}")

        return {
            'total': total,
            'created': created_count,
            'errors': errors
        }

class ExportService:
    @staticmethod
    def generate_pdf(queryset, user):
        """
        Gera PDF de transações.
        Retorna bytes buffer.
        """
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Cabeçalho
        y = height - 50
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, y, f"Fluxar Report - {user.name or user.email}")
        y -= 25
        p.setFont("Helvetica", 10)
        p.drawString(50, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        y -= 30
        
        # Tabela Simples (Cabeçalho)
        headers = ["Data", "Tipo", "Conta", "Categoria", "Valor"]
        x_coords = [50, 130, 180, 300, 450]
        
        p.setFont("Helvetica-Bold", 10)
        for i, h in enumerate(headers):
            p.drawString(x_coords[i], y, h)
            
        y -= 20
        p.line(50, y+15, 550, y+15)
        
        p.setFont("Helvetica", 9)
        total_income = Decimal(0)
        total_expense = Decimal(0)
        
        for tx in queryset:
            if y < 50:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 9)

            date = tx.date.strftime("%d/%m/%Y")
            type_ = tx.get_type_display()
            account = tx.account.name[:15]
            category = tx.category.name if tx.category else "-"
            amount = f"R$ {tx.amount:,.2f}"
            
            if tx.type == 'INCOME':
                total_income += tx.amount
            else:
                total_expense += tx.amount
                
            p.drawString(x_coords[0], y, date)
            p.drawString(x_coords[1], y, type_)
            p.drawString(x_coords[2], y, account)
            p.drawString(x_coords[3], y, category[:20])
            p.drawString(x_coords[4], y, amount)
            
            y -= 15
            
        # Resumo
        y -= 20
        p.line(50, y+15, 550, y+15)
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, y, f"Total Receitas: R$ {total_income:,.2f}")
        y -= 15
        p.drawString(50, y, f"Total Despesas: R$ {total_expense:,.2f}")
        y -= 15
        p.drawString(50, y, f"Saldo no Período: R$ {(total_income - total_expense):,.2f}")
        
        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_xls(queryset):
        """
        Gera Excel de transações.
        Retorna bytes buffer.
        """
        data = []
        for tx in queryset:
            data.append({
                'Data': tx.date,
                'Descrição': tx.description,
                'Tipo': tx.get_type_display(),
                'Conta': tx.account.name,
                'Categoria': tx.category.name if tx.category else "-",
                'Valor': tx.amount
            })
            
        df = pd.DataFrame(data)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Transações')
            
        buffer.seek(0)
        return buffer
