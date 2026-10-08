import io
import pandas as pd
from decimal import Decimal
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


def _do_dono(tx, relacionado):
    """
    O objeto relacionado (conta, categoria ou tag) se for do dono da
    transação; senão None, como se a transação não tivesse a relação (ISOL-15).
    """
    if relacionado is not None and relacionado.user_id == tx.user_id:
        return relacionado
    return None


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
            conta = _do_dono(tx, tx.account)
            categoria = _do_dono(tx, tx.category)
            account = conta.name[:15] if conta else "-"
            category = categoria.name if categoria else "-"
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
            
            conta = _do_dono(tx, tx.account)
            categoria = _do_dono(tx, tx.category)

            # Categoria e Subcategoria
            category_name = categoria.name if categoria else ''
            subcategory_name = ''
            if categoria and _do_dono(tx, categoria.parent): # Check for parent category
                subcategory_name = categoria.name
                category_name = categoria.parent.name

            data.append({
                'Data': tx.date.strftime('%d/%m/%Y'),
                'Descrição': tx.description,
                'Valor': formatted_amount,
                'Conta': conta.name if conta else '',
                'Situação': 'Liquidado' if tx.status == 'COMPLETED' else 'Pendente',
                'Categoria': category_name,
                'Subcategoria': subcategory_name,
                'Tags': ', '.join([t.name for t in tx.tags.all() if _do_dono(tx, t)]),
                'Tipo': tx.get_type_display()
            })
            
        df = pd.DataFrame(data)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Transações')
            
        buffer.seek(0)
        return buffer
