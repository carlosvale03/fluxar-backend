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
        Retorna resumo: { 'total': N, 'created': N, 'ignored': N, 'errors': [] }
        """
        try:
            ofx = OfxParser.parse(file)
        except Exception as e:
            return {'total': 0, 'created': 0, 'ignored': 0, 'errors': [f"Erro ao ler OFX: {str(e)}"]}
        
        created_count = 0
        ignored_count = 0
        errors = []
        
        if not ofx.account:
             return {'total': 0, 'created': 0, 'ignored': 0, 'errors': ["Nenhuma conta encontrada no OFX"]}

        transactions = ofx.account.statement.transactions
        total = len(transactions)

        for tx in transactions:
            try:
                amount = Decimal(str(tx.amount))
                date_val = tx.date.date() # Date object
                description = tx.memo or tx.payee or "Sem descrição"
                
                # Definir tipo baseado no sinal
                if amount < 0:
                    type_ = 'EXPENSE'
                    abs_amount = abs(amount)
                else:
                    type_ = 'INCOME'
                    abs_amount = amount

                # Duplicate Check
                exists = Transaction.objects.filter(
                    user=user,
                    account=account,
                    date=date_val,
                    amount=abs_amount,
                    description=description,
                    type=type_
                ).exists()

                if exists:
                    ignored_count += 1
                    continue
                
                if type_ == 'INCOME':
                    TransactionService.create_income(
                        user=user,
                        account=account,
                        amount=abs_amount,
                        date=date_val,
                        description=description,
                        category=None
                    )
                else:
                    TransactionService.create_expense(
                        user=user,
                        account=account,
                        amount=abs_amount,
                        date=date_val,
                        description=description,
                        category=None
                    )
                created_count += 1
                
            except Exception as e:
                errors.append(f"Erro na transação {description}: {str(e)}")
        
        return {
            'total': total,
            'created': created_count,
            'ignored': ignored_count,
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
            return {'total': 0, 'created': 0, 'ignored': 0, 'errors': [f"Erro ao ler arquivo: {str(e)}"]}
            
        created_count = 0
        ignored_count = 0
        errors = []
        total = len(df)
        
        col_date = mapping.get('date_column')
        col_desc = mapping.get('description_column')
        col_amount = mapping.get('amount_column')
        col_type = mapping.get('type_column') 
        col_status = mapping.get('status_column')
        col_category = mapping.get('category_column')
        col_subcategory = mapping.get('subcategory_column')
        col_tags = mapping.get('tags_column')
        col_account_name = mapping.get('account_column')
        
        if not all([col_date, col_desc, col_amount]):
             return {'total': 0, 'created': 0, 'ignored': 0, 'errors': ["Colunas obrigatórias (Data, Descrição, Valor) não informadas"]}

        # Validar se as colunas mapeadas existem no DataFrame
        missing_cols = []
        for col in [col_date, col_desc, col_amount, col_type, col_status, col_category, col_subcategory, col_tags, col_account_name]:
            if col and col not in df.columns:
                missing_cols.append(col)
                
        if missing_cols:
             return {'total': 0, 'created': 0, 'ignored': 0, 'errors': [f"As seguintes colunas mapeadas não foram encontradas na planilha: {', '.join(missing_cols)}"]}

        from accounts.models import Account
        from transactions.models import Category, Tag

        for index, row in df.iterrows():
            try:
                # Basic row validation to skip empty/footer rows
                if pd.isna(row[col_date]) or pd.isna(row[col_amount]) or str(row[col_date]).strip() == "":
                    continue

                raw_date = row[col_date]
                description = str(row[col_desc]) if pd.notna(row[col_desc]) else ""
                amount_val = row[col_amount]
                
                try:
                    date_val = pd.to_datetime(raw_date, dayfirst=True).date()
                except:
                    # Skip rows where date is not a valid date (like "Total" line)
                    continue
                
                # Handle +/- signs and clean value
                amount_str = str(amount_val).replace('R$', '').replace(' ', '').replace(',', '.')
                # Remove any other non-numeric chars except . and -
                import re
                amount_str = re.sub(r'[^-0-9.]', '', amount_str)
                
                if not amount_str or amount_str == '-':
                    continue
                    
                amount_dec = Decimal(amount_str)
                
                # Determine type from amount sign if not provided
                if col_type and pd.notna(row[col_type]):
                    type_str = str(row[col_type]).upper()
                    if type_str in ['INCOME', 'RECEITA', 'C', 'CREDITO']:
                        type_ = 'INCOME'
                    else:
                        type_ = 'EXPENSE'
                else:
                    if amount_dec < 0:
                        type_ = 'EXPENSE'
                    else:
                        type_ = 'INCOME'
                
                amount_dec = abs(amount_dec)

                # Optional: Account override
                target_account = account
                if col_account_name and pd.notna(row[col_account_name]):
                    acc_name = str(row[col_account_name])
                    acc_exists = Account.objects.filter(user=user, name__iexact=acc_name).first()
                    if acc_exists:
                        target_account = acc_exists

                # Optional: Status
                status_val = 'COMPLETED'
                if col_status and pd.notna(row[col_status]):
                    st_str = str(row[col_status]).upper()
                    if st_str in ['PENDENTE', 'PENDING', 'A PAGAR', 'A RECEBER']:
                        status_val = 'PENDING'

                # Duplicate Check
                exists = Transaction.objects.filter(
                    user=user,
                    account=target_account,
                    date=date_val,
                    amount=amount_dec,
                    description=description,
                    type=type_
                ).exists()

                if exists:
                    ignored_count += 1
                    continue

                # Utility for normalization (accent and case insensitive)
                import unicodedata
                def normalize_str(s):
                    if not s: return ""
                    return "".join(
                        c for c in unicodedata.normalize('NFKD', str(s))
                        if not unicodedata.combining(c)
                    ).lower().strip()

                # Logic to find or create Category hierarchically
                def find_or_create_cat(user, name, cat_type, parent=None):
                    if not name: return None
                    norm_name = normalize_str(name)
                    # Check existing for user
                    qs = Category.objects.filter(user=user, parent=parent, type=cat_type)
                    for c in qs:
                        if normalize_str(c.name) == norm_name:
                            return c
                    # Create if not found
                    return Category.objects.create(user=user, name=name, type=cat_type, parent=parent)

                # Optional: Category & Subcategory
                target_category = None
                if col_category and pd.notna(row[col_category]):
                    cat_name = str(row[col_category]).strip()
                    if cat_name:
                        # Find/Create Parent Category
                        main_cat = find_or_create_cat(user, cat_name, type_)
                        target_category = main_cat
                        
                        # Find/Create Subcategory if provided
                        if col_subcategory and pd.notna(row[col_subcategory]):
                            sub_name = str(row[col_subcategory]).strip()
                            if sub_name:
                                target_category = find_or_create_cat(user, sub_name, type_, parent=main_cat)

                # Create transaction
                if type_ == 'INCOME':
                    tx = TransactionService.create_income(
                        user=user,
                        account=target_account,
                        amount=amount_dec,
                        date=date_val,
                        description=description,
                        category=target_category
                    )
                else:
                    tx = TransactionService.create_expense(
                        user=user,
                        account=target_account,
                        amount=amount_dec,
                        date=date_val,
                        description=description,
                        category=target_category
                    )
                
                # Additional updates (status, tags)
                if status_val == 'PENDING':
                    tx.status = 'PENDING'
                    tx.save()
                
                if col_tags and pd.notna(row[col_tags]):
                    tag_names = [t.strip() for t in str(row[col_tags]).split(',')]
                    for tag_name in tag_names:
                        if tag_name:
                            norm_tag = normalize_str(tag_name)
                            # Find existing tag for user
                            existing_tag = None
                            for t in Tag.objects.filter(user=user):
                                if normalize_str(t.name) == norm_tag:
                                    existing_tag = t
                                    break
                            
                            if not existing_tag:
                                existing_tag = Tag.objects.create(user=user, name=tag_name)
                            
                            tx.tags.add(existing_tag)

                created_count += 1

            except Exception as e:
                errors.append(f"Linha {index}: {str(e)}")

        return {
            'total': total,
            'created': created_count,
            'ignored': ignored_count,
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
            elif tx.type in ['EXPENSE', 'CREDIT_CARD', 'INVOICE_PAYMENT']:
                total_expense += tx.amount
                
            p.drawString(x_coords[0], y, date)
            p.drawString(x_coords[1], y, type_[:18]) # Truncate to avoid overlap
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
            # Format amount with +/- prefix
            sign = "+" if tx.type == 'INCOME' else "-"
            formatted_amount = f"{sign} {tx.amount:.2f}"
            
            # Categoria e Subcategoria
            category_name = tx.category.name if tx.category else ''
            subcategory_name = ''
            if tx.category and tx.category.parent_id: # Check for parent category
                subcategory_name = tx.category.name
                category_name = tx.category.parent.name

            data.append({
                'Data': tx.date.strftime('%d/%m/%Y'),
                'Descrição': tx.description,
                'Valor': formatted_amount,
                'Conta': tx.account.name if tx.account else '',
                'Situação': 'Liquidado' if tx.status == 'COMPLETED' else 'Pendente',
                'Categoria': category_name,
                'Subcategoria': subcategory_name,
                'Tags': ', '.join([t.name for t in tx.tags.all()]),
                'Tipo': tx.get_type_display()
            })
            
        df = pd.DataFrame(data)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Transações')
            
        buffer.seek(0)
        return buffer
