from django.core.management.base import BaseCommand
from transactions.models import Category

class Command(BaseCommand):
    help = 'Popula o banco com categorias e subcategorias template'

    def handle(self, *args, **kwargs):
        self.stdout.write("Criando templates de categorias...")

        # Limpar templates antigos para evitar duplicação em desenvolvimento
        Category.objects.filter(is_template=True).delete()

        # Estrutura: TYPE -> [(Name, Icon, Color, [Sub1, Sub2, ...])]
        
        data_income = [
            ("Salário", "Briefcase", "#10b981", []), # Green-500
            ("Pagamentos", "Banknote", "#3b82f6", []), # Blue-500
            ("Outros", "Tag", "#9ca3af", []) # Gray-400
        ]
        
        data_expense = [
            ("Beleza", "Flower2", "#1e3a8a", []), # Azul Escuro
            ("Casa", "Home", "#60a5fa", []), # Azul Claro
            ("Comida", "Utensils", "#86efac", []), # Verde Claro
            ("Doação", "Heart", "#9333ea", []), # Roxo
            ("Lazer", "Smile", "#ef4444", []), # Vermelho
            ("Outros", "Tag", "#d1d5db", []) # Cinza Claro (Gray-300)
        ]

        def create_tree(type_cat, items):
            for name, icon, color, subs in items:
                # Criar Raiz
                root = Category.objects.create(
                    user=None, # System wide
                    name=name,
                    type=type_cat,
                    icon=icon,
                    color=color,
                    is_template=True,
                    parent=None
                )
                # Criar Subs
                for sub_name in subs:
                    Category.objects.create(
                        user=None,
                        name=sub_name,
                        type=type_cat, # Herda tipo
                        parent=root,
                        is_template=True,
                         # Herda cor do pai ou define padrao? Frontend herda. 
                         # Backend model permite null? Sim.
                        color=color 
                    )

        create_tree('INCOME', data_income)
        create_tree('EXPENSE', data_expense)

        self.stdout.write(self.style.SUCCESS('Templates criados com sucesso!'))
