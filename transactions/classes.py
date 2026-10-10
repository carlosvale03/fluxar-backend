"""
Classe efetiva das categorias de despesa (CLASSE-16, AD-052).

A classe efetiva nunca é gravada: é a classe própria da categoria; sem ela,
a classe efetiva da categoria-mãe; sem as duas, nenhuma ("Sem classe").
`mapa_de_classes` resolve isso para todas as categorias do usuário, ativas e
excluídas (CLASSE-27), com uma consulta às categorias e outra às classes.
Relatórios, filtro e exportação usam o mesmo mapa.
"""
from .models import Category, ClasseDeDespesa

# Valor do filtro `classId` para "Sem classe" (CLASSE-35)
SEM_CLASSE = 'sem_classe'


def classes_efetivas(usuario):
    """
    `{categoria_id: (classe | None, herdada)}` para todas as categorias do
    usuário; `herdada` é verdadeiro quando a classe efetiva vem da mãe.
    Categorias de receita ficam com `(None, False)`. Um ciclo na árvore não
    trava a resolução: a subida para ao voltar a uma categoria já vista.
    """
    classes = {c.pk: c for c in ClasseDeDespesa.objects.filter(user=usuario)}
    categorias = {
        c['id']: c
        for c in Category.objects.filter(user=usuario).values('id', 'parent_id', 'type', 'classe_id')
    }
    efetivas = {}

    def efetiva(categoria_id):
        caminho = []
        atual = categoria_id
        classe = None
        while atual is not None and atual not in efetivas:
            categoria = categorias.get(atual)
            if categoria is None or categoria['type'] != 'EXPENSE' or atual in caminho:
                break
            caminho.append(atual)
            classe = classes.get(categoria['classe_id'])
            if classe is not None:
                break
            atual = categoria['parent_id']
        else:
            if atual is not None:
                classe = efetivas[atual]
        # As categorias do caminho sem classe própria herdam a encontrada
        for vista in caminho:
            efetivas.setdefault(vista, classe)
        return efetivas.get(categoria_id)

    resultado = {}
    for categoria_id, categoria in categorias.items():
        classe = efetiva(categoria_id) if categoria['type'] == 'EXPENSE' else None
        propria = classes.get(categoria['classe_id']) if categoria['type'] == 'EXPENSE' else None
        resultado[categoria_id] = (classe, classe is not None and propria is None)
    return resultado


def mapa_de_classes(usuario):
    """`{categoria_id: classe | None}` com a classe efetiva de cada categoria do usuário."""
    return {categoria_id: classe for categoria_id, (classe, _) in classes_efetivas(usuario).items()}


def categorias_das_classes(usuario, ids_de_classe, sem_classe=False):
    """
    Os ids das categorias do usuário com classe efetiva entre `ids_de_classe`
    e, com `sem_classe`, os das categorias sem classe efetiva.
    """
    pedidas = {str(i) for i in ids_de_classe}
    return {
        categoria_id
        for categoria_id, classe in mapa_de_classes(usuario).items()
        if (classe is not None and str(classe.pk) in pedidas) or (classe is None and sem_classe)
    }
