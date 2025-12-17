from django.core.management.base import BaseCommand
from transactions.models import Category

class Command(BaseCommand):
    help = 'Popula o banco com categorias e subcategorias template'

    def handle(self, *args, **kwargs):
        self.stdout.write("Criando templates de categorias...")

        # Limpar templates antigos para evitar duplicação em desenvolvimento
        Category.objects.filter(is_template=True).delete()

        # Estrutura: TYPE -> [(Name, Icon, [Sub1, Sub2, ...])]
        
        data_income = [
            ("Salário", "mdi-cash", ["Adiantamento", "13º Salário", "Férias"]),
            ("Investimentos", "mdi-chart-line", ["Dividendos", "Juros", "Venda de Ativos"]),
            ("Presente", "mdi-gift", []),
            ("Outros", "mdi-dots-horizontal", [])
        ]
        
        data_expense = [
            ("Moradia", "mdi-home", ["Aluguel", "Condomínio", "Energia", "Água", "Internet"]),
            ("Alimentação", "mdi-food", ["Mercado", "Restaurante", "Delivery"]),
            ("Transporte", "mdi-car", ["Combustível", "Uber/Táxi", "Manutenção", "IPVA"]),
            ("Saúde", "mdi-hospital", ["Farmácia", "Consultas", "Plano de Saúde", "Dentes"]),
            ("Lazer", "mdi-controller", ["Cinema", "Viagens", "Jogos"]),
            ("Educação", "mdi-school", ["Faculdade", "Cursos", "Livros"]),
            ("Compras", "mdi-cart", ["Roupas", "Eletrônicos", "Casa"])
        ]

        def create_tree(type_cat, items):
            for name, icon, subs in items:
                # Criar Raiz
                root = Category.objects.create(
                    user=None, # System wide
                    name=name,
                    type=type_cat,
                    icon=icon,
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
                        is_template=True
                    )

        create_tree('INCOME', data_income)
        create_tree('EXPENSE', data_expense)

        self.stdout.write(self.style.SUCCESS('Templates criados com sucesso!'))
