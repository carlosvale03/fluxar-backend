"""
O que um cadastro novo recebe (ADMIN-22, AD-050).

`criar_padrao_do_cadastro` é o único lugar que define o padrão: o sinal do
cadastro e a limpeza dos dados pelo administrador chamam a mesma função.
"""
from accounts.models import Account

from .models import Category

DEFAULT_CATEGORIES = [
    { "name": "Salário", "type": "INCOME", "icon": "DollarSign", "color": "#14b8a6" },
    { "name": "Investimento", "type": "INCOME", "icon": "TrendingUp", "color": "#06b6d4" },
    { "name": "Pagamentos", "type": "INCOME", "icon": "Banknote", "color": "#10b981" },
    { "name": "Prêmio", "type": "INCOME", "icon": "Trophy", "color": "#f59e0b" },
    { "name": "Presente", "type": "INCOME", "icon": "Gift", "color": "#fb7185" },
    { "name": "Outros", "type": "INCOME", "icon": "Sparkles", "color": "#64748b" },
    {
        "name": "Casa",
        "type": "EXPENSE",
        "icon": "Home",
        "color": "#6366f1",
        "subcategories": [
            { "name": "Aluguel", "icon": "Key" },
            { "name": "Energia", "icon": "Zap" }
        ]
    },
    { "name": "Comida", "type": "EXPENSE", "icon": "Utensils", "color": "#f97316" },
    { "name": "Transporte", "type": "EXPENSE", "icon": "Car", "color": "#3b82f6" },
    { "name": "Lazer", "type": "EXPENSE", "icon": "Gamepad2", "color": "#8b5cf6" },
    { "name": "Educação", "type": "EXPENSE", "icon": "GraduationCap", "color": "#c084fc" },
    { "name": "Eletrônicos", "type": "EXPENSE", "icon": "Smartphone", "color": "#64748b" },
    { "name": "Doces", "type": "EXPENSE", "icon": "IceCream", "color": "#ec4899" },
    { "name": "Doação", "type": "EXPENSE", "icon": "Heart", "color": "#f43f5e" },
    { "name": "Presente", "type": "EXPENSE", "icon": "Gift", "color": "#fb7185" }
]


def criar_padrao_do_cadastro(usuario):
    """Cria as categorias padrão, com as subcategorias, e a conta Carteira."""
    for cat_data in DEFAULT_CATEGORIES:
        parent_category = Category.objects.create(
            user=usuario,
            name=cat_data["name"],
            type=cat_data["type"],
            icon=cat_data["icon"],
            color=cat_data["color"],
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
