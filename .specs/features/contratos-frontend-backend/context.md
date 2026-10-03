# Contratos frontend backend Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/contratos-frontend-backend/spec.md`
**Status:** Spec aprovada; design e tasks aprovados em 2026-10-03

---

## Feature Boundary

Como o frontend e o backend combinam paginação, filtros, datas, valores em dinheiro e preferências, e como os erros chegam ao usuário. Redefinição de senha, sessão, faturas e saldo já estão nas próprias specs.

---

## Implementation Decisions

### Listas paginam ou vêm completas

- Coleções pequenas vêm completas; transações e as listas de usuários e de logs do admin vêm paginadas num formato único (AD-021).

### Filtro de categorias

- Aceita várias categorias, e a categoria-pai inclui as subcategorias, com o mesmo significado na lista, na exportação e nos relatórios (AD-022).

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Formato e tamanho da página, página além da última, espera da busca e total do dia.
- Filtro desconhecido.
- Formato e exibição dos valores em dinheiro.
- Formato das datas.
- Formato das preferências.
- Idioma e formato dos erros, sistema de avisos, tempo máximo das requisições e aviso de "servidor acordando".

---

## Specific References

Paginação hoje:

| Rota | Hoje |
| ---- | ---- |
| Contas, categorias e logs de um usuário no admin | Sem paginação (`accounts/views.py:20`, `transactions/views.py:16`, `api/views.py:580`) |
| Transações | `StandardResultsSetPagination`, 20 por página, com `links`, `count`, `total_pages` e `current_page` (`core/pagination.py:4-19`, `transactions/views.py:65`) |
| Cartões, faturas, tags, orçamentos, metas, monitores de foco, usuários e logs globais do admin | Paginação padrão do DRF, 10 por página e formato diferente (`core/settings.py:178-179`) |

- Cerca de vinte pontos do frontend leem `response.data.results || response.data` e ficam só com a primeira página, como `fluxar-frontend/src/services/tags.ts:9-10`, `fluxar-frontend/src/components/cards/invoice-list.tsx:48` e `fluxar-frontend/src/components/transactions/transaction-filters.tsx:92`.
- A lista de transações busca duas vezes ao montar, volta para a página 1 depois da busca e dispara a cada tecla (`fluxar-frontend/src/app/(app)/transacoes/page.tsx:355-367` e `:473`).

Filtros hoje:

- A tela envia `categoryId` repetido (`fluxar-frontend/src/app/(app)/transacoes/page.tsx:315`), e o backend lê só o último valor com `query_params.get` (`transactions/views.py:80`).
- A exportação filtra `type` de outro jeito que a lista (`data_exchange/views.py:128-129` e `transactions/views.py:98-99`).
- A tela Recorrentes pede `?is_recurring=true`, que o backend não filtra (`fluxar-frontend/src/app/(app)/transacoes/recorrentes/page.tsx:39-40`).

Valores, datas e preferências hoje:

- O frontend usa `Number(...)` ou `parseFloat(...)` em valores em cerca de 50 lugares e tem 21 definições locais de `formatCurrency`.
- Os relatórios devolvem valores com `float(...)` (`reports/services.py`, 37 ocorrências).
- O aporte e o resgate de meta enviam `datetime: new Date().toISOString()` (`fluxar-frontend/src/components/goals/GoalDepositForm.tsx:104` e `GoalWithdrawForm.tsx:121`), e o backend cai para a data do servidor quando não consegue ler (`goals/services.py:31-38`).
- A tela de configurações envia o objeto `preferences` (`fluxar-frontend/src/app/(app)/configuracoes/page.tsx:99-100`), mas o serializer só grava os campos planos (`api/serializers.py:61-66` e `:109-113`).

Erros hoje:

- O backend está com `LANGUAGE_CODE = 'en-us'` (`core/settings.py:129`).
- Só o Toaster do Sonner é montado (`fluxar-frontend/src/app/layout.tsx:50`), e nove arquivos usam `useToast`: dashboard, calendário, categorias, orçamentos, tags, `BudgetForm`, `ImportBudgetsDialog`, `CategoryForm` e `TagForm`.
- O axios não tem tempo máximo (`fluxar-frontend/src/services/apiClient.ts:7-12`).

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
