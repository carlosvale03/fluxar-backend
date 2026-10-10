"""
O que um cadastro novo recebe (ADMIN-22, AD-050).

`criar_padrao_do_cadastro` é o único lugar que define o padrão: o sinal do
cadastro e a limpeza dos dados pelo administrador chamam a mesma função.
"""
from accounts.models import Account

from core.texto import normalizar

from .models import Category, ClasseDeDespesa

# As classes padrão de todo usuário, como (nome, cor) (CLASSE-01, AD-025)
CLASSES_PADRAO = (
    ("Essencial", "#16A34A"),
    ("Dispensável", "#F97316"),
)

DEFAULT_CATEGORIES = [
    { "name": "Salário", "type": "INCOME", "icon": "DollarSign", "color": "#14b8a6" },
    { "name": "Investimento", "type": "INCOME", "icon": "TrendingUp", "color": "#06b6d4" },
    { "name": "Pagamentos", "type": "INCOME", "icon": "Banknote", "color": "#10b981" },
    { "name": "Prêmio", "type": "INCOME", "icon": "Trophy", "color": "#f59e0b" },
    { "name": "Presente", "type": "INCOME", "icon": "Gift", "color": "#fb7185" },
    { "name": "Outros", "type": "INCOME", "icon": "Sparkles", "color": "#64748b" },
    {
        "name": "Casa",
        "classe": "essencial",
        "type": "EXPENSE",
        "icon": "Home",
        "color": "#6366f1",
        "subcategories": [
            { "name": "Aluguel", "icon": "Key" },
            { "name": "Energia", "icon": "Zap" }
        ]
    },
    { "name": "Comida", "type": "EXPENSE", "classe": "essencial", "icon": "Utensils", "color": "#f97316" },
    { "name": "Transporte", "type": "EXPENSE", "classe": "essencial", "icon": "Car", "color": "#3b82f6" },
    { "name": "Lazer", "type": "EXPENSE", "classe": "dispensavel", "icon": "Gamepad2", "color": "#8b5cf6" },
    { "name": "Educação", "type": "EXPENSE", "classe": "essencial", "icon": "GraduationCap", "color": "#c084fc" },
    { "name": "Eletrônicos", "type": "EXPENSE", "classe": "dispensavel", "icon": "Smartphone", "color": "#64748b" },
    { "name": "Doces", "type": "EXPENSE", "classe": "dispensavel", "icon": "IceCream", "color": "#ec4899" },
    { "name": "Doação", "type": "EXPENSE", "classe": "dispensavel", "icon": "Heart", "color": "#f43f5e" },
    { "name": "Presente", "type": "EXPENSE", "classe": "dispensavel", "icon": "Gift", "color": "#fb7185" }
]


def criar_padrao_do_cadastro(usuario):
    """
    Cria as classes padrão, as categorias padrão com as subcategorias e a
    classe inicial (CLASSE-24), e a conta Carteira. As subcategorias ficam
    sem classe própria e herdam a da mãe (CLASSE-16).
    """
    classes = {
        normalizar(nome): ClasseDeDespesa.objects.create(
            user=usuario, nome=nome, nome_normalizado=normalizar(nome), cor=cor, padrao=True,
        )
        for nome, cor in CLASSES_PADRAO
    }
    for cat_data in DEFAULT_CATEGORIES:
        parent_category = Category.objects.create(
            user=usuario,
            name=cat_data["name"],
            type=cat_data["type"],
            icon=cat_data["icon"],
            color=cat_data["color"],
            classe=classes.get(cat_data.get("classe")),
            is_active=True,
        )
        # As subcategorias herdam o tipo e a cor da categoria pai
        for sub_data in cat_data.get("subcategories", ()):
            Category.objects.create(
                user=usuario,
                name=sub_data["name"],
                icon=sub_data["icon"],
                type=cat_data["type"],
                color=cat_data["color"],
                parent=parent_category,
                is_active=True,
            )

    Account.objects.create(
        user=usuario,
        name="Carteira",
        type="WALLET",
        initial_balance=0,
        color="#475569",
        is_active=True,
    )
