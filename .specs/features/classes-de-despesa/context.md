# Classes de despesa Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/classes-de-despesa/spec.md`
**Status:** Spec aprovada; design e tasks aprovados em 2026-10-10 (aprovação automática pedida pelo usuário)

---

## Feature Boundary

Classes para as categorias de despesa: as duas classes padrão e as criadas pelo usuário, a classe de cada categoria com herança da categoria-mãe, a divisão das despesas por classe nos gráficos simples, o filtro por classe e a coluna na exportação XLSX. Receitas e orçamentos ficam de fora.

---

## Implementation Decisions

### Quais classes existem

- Duas classes padrão, Essencial e Dispensável. O usuário cria outras, com sugestões que não repetem as padrão, até no máximo 4 ou 5 no total; a spec usa 5 (AD-025).

### Subcategoria

- Herda a classe da categoria-mãe e pode trocar (AD-025).

### Receitas

- Só as categorias de despesa têm classe (AD-025).

### Orçamentos

- Continuam por categoria; a classe entra só em relatórios, filtros e exportação.

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Limite exato de 5 classes e as sugestões Dívidas, Impostos e taxas e Profissional.
- Classes padrão fixas, nome, cor e exclusão das classes.
- Classe inicial das categorias padrão e dos usuários que já existem.
- Classe e histórico, onde a divisão aparece, filtro "Sem classe", categorias criadas pela importação e recurso essencial.

---

## Specific References

- `Category` só tem a árvore pelo campo `parent` e nenhum campo de classe (`transactions/models.py:5-35`); o serializer não valida o tipo nem o dono da categoria-mãe (`transactions/serializers.py:8-30`).
- A lista de categorias devolve só as raízes, com as subcategorias aninhadas e sem paginação (`transactions/views.py:14-37`).
- As categorias padrão são criadas por um signal no cadastro (`transactions/signals.py:8-64`): Casa, com Aluguel e Energia, Comida, Transporte, Lazer, Educação, Eletrônicos, Doces, Doação e Presente.
- Os gráficos simples agrupam as despesas pelo nome da categoria raiz, com os tipos `EXPENSE` e `CREDIT_CARD` e sem filtro de status (`reports/services.py:366-435`). Eles alimentam o gráfico do dashboard e o da tela Relatórios (`fluxar-frontend/src/components/dashboard/CategoryDistributionChart.tsx:65-85`, `fluxar-frontend/src/app/(app)/dashboard/page.tsx:389-408` e `fluxar-frontend/src/app/(app)/relatorios/page.tsx:265-279`).
- A exportação XLSX monta a categoria e a subcategoria de cada linha (`data_exchange/services.py:512-535`), e a importação cria categorias pelo nome (`data_exchange/services.py:278-290`).
- Na interface, a subcategoria criada já herda o tipo, o ícone e a cor da mãe (`fluxar-frontend/src/components/categories/CategoryForm.tsx:92-100`).
- O relatório de gastos fixos e variáveis continua por palavras-chave e recorrência (`reports/services.py:793-845`).

---

## Deferred Ideas

- Limite ou orçamento por classe, como "no máximo R$ 800 em dispensáveis": pode voltar com a gestão do salário (PROP-01).
- Classe para categorias de receita, como fixa e variável: fica para a PROP-01, se ela precisar reconhecer o salário.
