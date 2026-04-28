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
    def preflight_spreadsheet(file, mapping, import_type):
        """
        Lê a planilha e retorna os nomes únicos das contas encontradas.
        """
        file.seek(0) # Garante leitura do início
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        except Exception as e:
            raise Exception(f"Erro ao ler arquivo: {str(e)}")

        unique_accounts = set()
        
        if import_type == 'TRANSFER':
            col_source = mapping.get('source_account_column')
            col_dest = mapping.get('dest_account_column')
            if col_source and col_source in df.columns:
                unique_accounts.update([str(x).strip() for x in df[col_source].dropna().unique()])
            if col_dest and col_dest in df.columns:
                unique_accounts.update([str(x).strip() for x in df[col_dest].dropna().unique()])
        else:
            col_acc = mapping.get('account_column')
            if col_acc and col_acc in df.columns:
                unique_accounts.update([str(x).strip() for x in df[col_acc].dropna().unique()])
        
        return sorted(list(filter(None, unique_accounts)))

    @staticmethod
    def process_spreadsheet(file, mapping, account, user, import_type='INCOME_EXPENSE', account_mapping=None):
        """
        Lê CSV/XLS usando pandas e cria transações ou transferências.
        account_mapping: dict { 'Nome na Planilha': 'UUID da Conta' }
        """
        file.seek(0) # Garante leitura do início
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            print(f"[IMPORT] Arquivo lido. Linhas: {len(df)}")
            if len(df) == 0:
                print("[IMPORT] AVISO: Planilha vazia.")
        except Exception as e:
            return {'total': 0, 'created': 0, 'ignored': 0, 'errors': [f"Erro ao ler arquivo: {str(e)}"]}
            
        created_count = 0
        ignored_count = 0
        errors = []
        total = len(df)
        
        col_date = mapping.get('date_column')
        col_desc = mapping.get('description_column', 'Transferência via Importação')
        col_amount = mapping.get('amount_column')
        col_type = mapping.get('type_column') 
        col_status = mapping.get('status_column')
        col_category = mapping.get('category_column')
        col_subcategory = mapping.get('subcategory_column')
        col_tags = mapping.get('tags_column')
        col_account_name = mapping.get('account_column')
        
        # Colunas específicas de transferência
        col_source_acc = mapping.get('source_account_column')
        col_dest_acc = mapping.get('dest_account_column')
        
        # Validação de colunas obrigatórias
        required_cols = [col_date, col_amount]
        if import_type == 'TRANSFER':
            required_cols.extend([col_source_acc, col_dest_acc])
        else:
            required_cols.append(col_desc)
            
        if not all(required_cols):
             return {'total': 0, 'created': 0, 'ignored': 0, 'errors': ["Colunas obrigatórias não informadas para o tipo de importação"]}

        # Validar se as colunas mapeadas existem no DataFrame
        missing_cols = []
        # Apenas colunas que o usuário realmente mapeou para nomes na planilha
        cols_to_check = [col_date, col_amount]
        if import_type == 'TRANSFER':
            cols_to_check.extend([col_source_acc, col_dest_acc])
        else:
            if mapping.get('description_column'): # Só checa se o usuário enviou um nome de coluna
                cols_to_check.append(col_desc)
        
        # Opcionais
        optional_fields = ['type_column', 'status_column', 'category_column', 'subcategory_column', 'tags_column', 'account_column']
        for field in optional_fields:
            col_name = mapping.get(field)
            if col_name:
                cols_to_check.append(col_name)

        for col in set(cols_to_check):
            if col and col not in df.columns:
                missing_cols.append(col)
                
        if missing_cols:
             error_msg = f"As seguintes colunas mapeadas não foram encontradas na planilha: {', '.join(missing_cols)}"
             print(f"[IMPORT] ERRO: {error_msg}")
             return {'total': 0, 'created': 0, 'ignored': 0, 'errors': [error_msg]}

        from accounts.models import Account
        from transactions.models import Category, Tag
        import unicodedata
        import re

        def normalize_str(s):
            if not s: return ""
            return "".join(
                c for c in unicodedata.normalize('NFKD', str(s))
                if not unicodedata.combining(c)
            ).lower().strip()

        # Cache para evitar queries repetitivas
        category_cache = {} # (norm_name, type, parent_id) -> CategoryObject
        tag_cache = {}      # norm_name -> TagObject
        
        account_cache = {}
        if account:
            account_cache[str(account.id)] = account
            account_cache[normalize_str(account.name)] = account

        # Warmup de cache: Carrega todas as categorias e tags do usuário de uma vez
        all_categories = Category.objects.filter(user=user).select_related('parent')
        for c in all_categories:
            norm_name = normalize_str(c.name)
            p_id = c.parent_id
            cache_key = (norm_name, c.type, p_id)
            category_cache[cache_key] = c
            
        all_tags = Tag.objects.filter(user=user)
        for t in all_tags:
            tag_cache[normalize_str(t.name)] = t

        def get_mapped_account(acc_name):
            if not acc_name: return account
            
            # 1. Tenta pelo mapeamento explícito (Nome da planilha para ID)
            if account_mapping:
                # Tenta nome exato, nome com strip e nome normalizado
                mapped_id = account_mapping.get(acc_name) or \
                            account_mapping.get(acc_name.strip()) or \
                            account_mapping.get(normalize_str(acc_name))
                
                if mapped_id:
                    if mapped_id in account_cache:
                        return account_cache[mapped_id]
                    acc = Account.objects.filter(user=user, id=mapped_id, is_active=True).first()
                    if acc:
                        account_cache[mapped_id] = acc
                        return acc

            # 2. Tenta pelo nome direto no banco (cache normalizado)
            norm_acc = normalize_str(acc_name)
            if norm_acc in account_cache:
                return account_cache[norm_acc]
            
            acc = Account.objects.filter(user=user, name__iexact=acc_name, is_active=True).first()
            if acc:
                account_cache[norm_acc] = acc
                return acc
            
            return account

        def get_or_create_cached_cat(name, cat_type, parent=None):
            if not name: return None
            norm_name = normalize_str(name)
            parent_id = parent.id if parent else None
            cache_key = (norm_name, cat_type, parent_id)
            
            if cache_key in category_cache:
                return category_cache[cache_key]
            
            # Se não está no cache (warmup), cria
            cat = Category.objects.create(user=user, name=name, type=cat_type, parent=parent)
            category_cache[cache_key] = cat
            return cat

        def get_or_create_cached_tag(name):
            if not name: return None
            norm_name = normalize_str(name)
            if norm_name in tag_cache:
                return tag_cache[norm_name]
            
            # Se não está no cache, cria
            tag = Tag.objects.create(user=user, name=name)
            tag_cache[norm_name] = tag
            return tag

        for index, row in df.iterrows():
            try:
                if pd.isna(row[col_date]) or pd.isna(row[col_amount]) or str(row[col_date]).strip() == "":
                    continue

                raw_date = row[col_date]
                description = "Transferência via Importação"
                if col_desc and col_desc in df.columns and pd.notna(row[col_desc]):
                    description = str(row[col_desc])
                amount_val = row[col_amount]
                
                try:
                    date_val = pd.to_datetime(raw_date, dayfirst=True).date()
                except:
                    continue
                
                # Limpeza e conversão do valor
                amount_str = str(amount_val).replace('R$', '').replace(' ', '').replace(',', '.')
                amount_str = re.sub(r'[^-0-9.]', '', amount_str)
                
                if not amount_str or amount_str == '-':
                    continue
                    
                amount_dec = abs(Decimal(amount_str))
                
                if import_type == 'TRANSFER':
                    source_acc_name = str(row[col_source_acc]).strip()
                    dest_acc_name = str(row[col_dest_acc]).strip()
                    
                    source_acc = get_mapped_account(source_acc_name)
                    dest_acc = get_mapped_account(dest_acc_name)
                    
                    if not source_acc:
                        errors.append(f"Linha {index}: Conta de origem '{source_acc_name}' não mapeada.")
                        continue
                    if not dest_acc:
                        errors.append(f"Linha {index}: Conta de destino '{dest_acc_name}' não mapeada.")
                        continue
                    if source_acc == dest_acc:
                        errors.append(f"Linha {index}: Conta de origem e destino são iguais ({source_acc_name}).")
                        continue

                    # Check Duplicata de Transferência
                    # Como não temos um link direto fácil, checamos se existe uma saída com os mesmos dados
                    exists = Transaction.objects.filter(
                        user=user, account=source_acc, date=date_val, amount=amount_dec, type='TRANSFER_OUT'
                    ).exists()
                    # Nota: Uma validação mais rigorosa checaria se o 'transfer_id' dessa transação 
                    # possui um par 'TRANSFER_IN' na conta de destino.

                    if exists:
                        ignored_count += 1
                        continue
                    
                    TransactionService.create_transfer(
                        user=user, 
                        account_from=source_acc, 
                        account_to=dest_acc,
                        amount=amount_dec, 
                        date=date_val, 
                        description=description
                    )
                else:
                    # Lógica INCOME/EXPENSE original
                    if col_type and pd.notna(row[col_type]):
                        type_str = str(row[col_type]).upper()
                        if type_str in ['INCOME', 'RECEITA', 'C', 'CREDITO']:
                            type_ = 'INCOME'
                        else:
                            type_ = 'EXPENSE'
                    else:
                        # Se não tem coluna de tipo, usa o sinal do valor
                        type_ = 'EXPENSE' if Decimal(amount_str) < 0 else 'INCOME'

                    target_account = get_mapped_account(str(row[col_account_name]).strip() if col_account_name and pd.notna(row[col_account_name]) else None)

                    exists = Transaction.objects.filter(
                        user=user, account=target_account, date=date_val,
                        amount=amount_dec, description=description, type=type_
                    ).exists()

                    if exists:
                        ignored_count += 1
                        continue

                    # Categoria
                    target_category = None
                    if col_category and pd.notna(row[col_category]):
                        cat_name = str(row[col_category]).strip()
                        main_cat = get_or_create_cached_cat(cat_name, type_)
                        target_category = main_cat
                        if col_subcategory and pd.notna(row[col_subcategory]):
                            sub_name = str(row[col_subcategory]).strip()
                            target_category = get_or_create_cached_cat(sub_name, type_, parent=main_cat)

                    if type_ == 'INCOME':
                        tx = TransactionService.create_income(
                            user=user, account=target_account, amount=amount_dec,
                            date=date_val, description=description, category=target_category
                        )
                    else:
                        tx = TransactionService.create_expense(
                            user=user, account=target_account, amount=amount_dec,
                            date=date_val, description=description, category=target_category
                        )
                    
                    if col_status and pd.notna(row[col_status]) and str(row[col_status]).upper() in ['PENDENTE', 'PENDING']:
                        tx.status = 'PENDING'
                        tx.save()

                    # Tags
                    if col_tags and pd.notna(row[col_tags]):
                        for tag_name in str(row[col_tags]).split(','):
                            tag_obj = get_or_create_cached_tag(tag_name.strip())
                            if tag_obj: tx.tags.add(tag_obj)

                created_count += 1

            except Exception as e:
                errors.append(f"Linha {index}: {str(e)}")

        return {
            'total': total, 'created': created_count, 'ignored': ignored_count, 'errors': errors
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
