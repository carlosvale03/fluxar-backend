# Contratos frontend backend Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/contratos-frontend-backend/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Views, serializers, paginação, filtros e relatórios (backend) | integration | Cada AC com status, formato e mensagem exatos; cada rota alterada com o caminho feliz e as recusas | `tests/contratos/test_*.py` | `docker compose exec -T backend python manage.py test tests.contratos --noinput` |
| Bibliotecas do frontend (`dinheiro`, `datas`, `erros`) | unit (frontend) | Todos os exemplos da spec e de AD-009; datas nos fusos de Brasília e de Lisboa | `fluxar-frontend/tests/contratos/*.test.ts` | `npx vitest run tests/contratos` |
| Telas e formulários (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/contratos/*.test.tsx` | idem |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 160 erros de lint antigos (MAN-04): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.contratos --noinput` |
| Full | Tarefas de backend que mudam rotas compartilhadas, settings ou relatórios | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/contratos` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Listas e filtros no backend

```
T1 → T2
T2 → T3
T3 → T4
```

### Phase 2: Valores, datas, preferências e erros no backend

```
T5 → T6
T6 → T7
T7 → T8
```

### Phase 3: Fundações do frontend

```
T9 → T10
T10 → T11
T11 → T12
T12 → T13
```

### Phase 4: Listas no frontend

```
T14 → T15
T15 → T16
T16 → T17
```

### Phase 5: Valores, datas, preferências e erros nas telas

```
T18 → T19
T19 → T20
T20 → T21
T21 → T22
```

---

## Task Breakdown

### Phase 1: Listas e filtros no backend

#### T1: Paginação padrão e coleções completas

**What**: `PaginacaoPadrao` no formato único, página além da última com 200 vazio, `DEFAULT_PAGINATION_CLASS = None` e a paginação ligada em transações, usuários do admin e logs do admin (global e de um usuário).
**Where**: `core/pagination.py`, `core/settings.py`, `transactions/views.py`, `api/views.py`
**Depends on**: None
**Reuses**: `StandardResultsSetPagination`
**Requirement**: CONTRATO-01, CONTRATO-02, CONTRATO-03, CONTRATO-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com 15 tags, 12 orçamentos, 11 cartões, 11 metas e 11 monitores, cada rota devolve um array com todos
- [x] Transações, usuários e logs do admin devolvem `count`, `total_pages`, `current_page`, `next`, `previous` e `results`
- [x] `page_size` ausente dá 20; `page_size=150` dá 100; `page_size=5` dá 5
- [x] Página 99 de uma lista com 2 páginas responde 200 com `results` vazio, `count` e `total_pages` corretos
- [x] Testes antigos que liam `results` em coleções são ajustados ao contrato (AD-021)
- [x] Full gate passa
- [x] Test count: pelo menos 8 testes (real: 14 testes novos; suíte 629 → 643)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(api): devolve coleções completas e listas paginadas num formato único`

---

#### T2: Recusa de filtro desconhecido

**What**: `core/filtros.py` com `conferir_parametros` e `ParametrosConhecidosMixin`, aplicado em todas as rotas `GET` com a tabela de parâmetros do design.
**Where**: `core/filtros.py` (novo), views de `accounts`, `transactions`, `budgets`, `goals`, `reports`, `data_exchange` e `api`
**Depends on**: T1
**Reuses**: NONE
**Requirement**: CONTRATO-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `/transactions/?limit=50` responde 400 com `{"detail": "Filtro desconhecido: limit."}`
- [x] Cada rota aceita os parâmetros da tabela do design sem erro
- [x] `/tags/?x=1` (coleção sem filtros) responde 400 com a mensagem exata
- [x] `POST` e outros métodos não são afetados
- [x] Full gate passa
- [x] Test count: pelo menos 6 testes (real: 10 testes novos; suíte 643 → 653)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(api): recusa filtros que a rota não conhece`

---

#### T3: Filtro de transações da lista e da exportação

**What**: `transactions/filtros.py` com `filtrar_transacoes` e `TIPOS_DE_DESPESA`, usado pela lista e pelas duas exportações; os relatórios passam a importar `TIPOS_DE_DESPESA`.
**Where**: `transactions/filtros.py` (novo), `transactions/views.py`, `data_exchange/views.py`, `reports/services.py`
**Depends on**: T2
**Reuses**: os filtros atuais de `TransactionViewSet.get_queryset`
**Requirement**: CONTRATO-10, CONTRATO-11, CONTRATO-13, CONTRATO-15, CONTRATO-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Filtrar por "Alimentação" (pai de "Restaurante" e "Mercado") e "Transporte" devolve as transações das quatro, cada uma uma vez
- [x] Categoria-pai sem subcategorias traz só as dela; pai e filha juntos não repetem transação
- [x] `type=EXPENSE` inclui as compras no cartão na lista e na exportação, com o mesmo conjunto de linhas
- [x] `is_recurring=true` devolve só transações de série; `transfer_id` devolve as duas pernas
- [x] `startDate=2026-09-01T03:00:00Z` responde 400 no campo `startDate`; `2026-09-30` como fim não inclui 1º de outubro
- [x] Categoria de outro usuário no filtro não traz nada dele (ISOL)
- [x] Full gate passa
- [x] Test count: pelo menos 9 testes (real: 12 testes novos; suíte 653 → 665)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(transactions): aplica o mesmo filtro na lista e na exportação, com várias categorias`

---

#### T4: Total do dia na lista de transações

**What**: `day_totals` na resposta paginada das transações, para as datas da página, sobre o filtro inteiro.
**Where**: `transactions/views.py`
**Depends on**: T3
**Reuses**: `filtrar_transacoes`
**Requirement**: CONTRATO-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Um dia com lançamentos em duas páginas tem o mesmo total nas duas, igual à soma de todos os lançamentos do dia
- [x] Entradas somam e saídas subtraem; o valor sai como texto com duas casas
- [x] O total respeita o filtro ativo (ex.: só despesas)
- [x] Build gate passa
- [x] Test count: pelo menos 3 testes (real: 4 testes novos; suíte 665 → 669)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat(transactions): devolve o total de cada dia para o filtro inteiro`

---

### Phase 2: Valores, datas, preferências e erros no backend

#### T5: Dinheiro como texto na API

**What**: `dinheiro()` em `core/valores.py`, aplicada aos `SerializerMethodField` de dinheiro, aos valores de dinheiro de `reports/services.py` e ao `estimated_revenue` do admin.
**Where**: `core/valores.py`, `accounts/serializers.py`, `transactions/serializers.py`, `budgets/serializers.py`, `goals/serializers.py`, `reports/services.py`, `api/views.py`
**Depends on**: None
**Reuses**: `core/valores.py`
**Requirement**: CONTRATO-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cada relatório devolve todo valor de dinheiro como texto `^-?\d+\.\d{2}$`, inclusive zero como "0.00"
- [x] Percentuais e razões continuam números
- [x] `available_limit`, `current_invoice_total`, `signed_amount`, `total_spent` e os valores das metas saem como texto
- [x] `dinheiro(Decimal('1234.565'))` dá "1234.57"
- [x] Full gate passa
- [x] Test count: pelo menos 8 testes (real: 13 testes novos; suíte 669 → 682)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(api): envia todo valor em dinheiro como texto com duas casas`

---

#### T6: Datas sem hora no aporte, no resgate e na exportação

**What**: `ler_data` em `core/datas.py`; aporte e resgate de meta leem `date` por ela e usam `hoje()` quando falta; datas com hora seguem ISO 8601 com fuso.
**Where**: `core/datas.py`, `goals/views.py`, `goals/services.py`
**Depends on**: T5
**Reuses**: `hoje()`
**Requirement**: CONTRATO-22, CONTRATO-23, CONTRATO-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Aporte com `date: "2026-12-31"` grava 31/12/2026
- [x] Aporte com data ISO com hora, ou inválida, responde 400 no campo `date` sem gravar
- [x] Aporte sem data grava `hoje()` de Brasília (com o relógio às 23h de Brasília, que já é o dia seguinte em UTC)
- [x] `created_at` sai em ISO 8601 com fuso
- [x] Quick gate passa
- [x] Test count: pelo menos 5 testes (real: 6 testes novos; suíte 682 → 688)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(goals): lê a data do aporte e do resgate sem hora e sem fuso`

---

#### T7: Preferências no formato da tela

**What**: Campo de escrita `preferences` no `UserProfileSerializer`, com validação de cada preferência e notificações mescladas.
**Where**: `api/serializers.py`
**Depends on**: T6
**Reuses**: o `to_representation` atual
**Requirement**: CONTRATO-26, CONTRATO-28

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `PATCH /users/me/` com `{preferences: {theme: "dark", notifications: {email: false}}}` grava e devolve os dois valores
- [x] As outras notificações e preferências continuam como estavam
- [x] Tema "roxo" responde 400 com o erro em `preferences.theme`
- [x] Os campos planos continuam aceitos
- [x] Quick gate passa
- [x] Test count: pelo menos 4 testes (real: 4 testes novos; suíte 688 → 692)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): salva as preferências enviadas no objeto preferences`

---

#### T8: Erros em português no formato do DRF

**What**: O handler acrescenta `code` ao `detail`; as respostas `{"error": ...}` e os `str(e)` viram exceções do DRF com `detail` em português; orçamento duplicado vira erro no campo `category`.
**Where**: `core/exceptions.py`, `budgets/views.py`, `budgets/serializers.py`, `data_exchange/views.py`, `goals/views.py`, `reports/views.py`, `transactions/views.py`, `api/views.py`
**Depends on**: T7
**Reuses**: `core/exceptions.py`
**Requirement**: CONTRATO-29, CONTRATO-30

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Nenhuma view devolve a chave `error` (busca no código e testes das rotas alteradas)
- [x] Uma rota inexistente devolve `{"detail": "Não encontrado.", "code": "not_found"}`
- [x] Orçamento duplicado responde 400 com mensagem em português no campo `category`
- [x] Mensagem padrão do DRF de campo obrigatório vem em português
- [x] Erro inesperado num service vira 500 sem o texto da exceção
- [x] Build gate passa
- [x] Test count: pelo menos 7 testes (real: 9 testes novos; suíte 692 → 701)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(api): devolve todos os erros em português no formato do DRF`

---

### Phase 3: Fundações do frontend

#### T9: Biblioteca de dinheiro

**What**: `src/lib/dinheiro.ts` com `paraCentavos`, `deCentavos`, `lerValorDigitado`, `formatarMoeda` e `formatarMoedaCompacta`; `formatCurrency` de `src/lib/utils.ts` reexporta `formatarMoeda`.
**Where**: `src/lib/dinheiro.ts` (novo), `src/lib/utils.ts`
**Depends on**: None
**Reuses**: NONE
**Requirement**: CONTRATO-17, CONTRATO-18, CONTRATO-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] "1.500" → "1500.00"; "12,5" → "12.50"; "0.50" → "0.50"; "12.5" → "12.50"; "1.234,56" → "1234.56"
- [x] "-50,00" só é aceito com `negativo`
- [x] `formatarMoeda("1234.56")` dá "R$ 1.234,56"; aceita número e texto
- [x] Somar "0.10" e "0.20" em centavos dá "0.30"
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 8 testes (real: 15 testes novos; suíte 101 → 116)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(frontend): centraliza leitura, conta e formatação de dinheiro`

---

#### T10: Campo de dinheiro em texto

**What**: `MoneyInput` com valor em texto decimal, leitura por AD-009 ao sair do campo e ao colar, e `permitirNegativo`.
**Where**: `src/components/ui/money-input.tsx`
**Depends on**: T9
**Reuses**: `lerValorDigitado`, `formatarMoeda`
**Requirement**: CONTRATO-19, CONTRATO-20, CONTRATO-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Digitar "1.500" e sair do campo entrega "1500.00" e mostra "R$ 1.500,00"
- [x] Colar "100" entrega "100.00"
- [x] Com `permitirNegativo`, "-50,00" entrega "-50.00"; sem, o sinal é recusado
- [x] O valor recebido "1234.56" aparece formatado
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 5 testes (real: 6 testes novos; suíte 116 → 122)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(frontend): aceita valor digitado ou colado no formato brasileiro`

---

#### T11: Datas sem hora no frontend

**What**: `paraApi` e `hojeNaApi` em `src/lib/datas.ts`; `lerData` em todas as datas sem hora exibidas (metas, histórico, recorrentes, relatórios).
**Where**: `src/lib/datas.ts`, `src/app/(app)/metas/page.tsx`, `src/components/goals/GoalDetails.tsx`, `src/components/goals/GoalHistory.tsx`, `src/app/(app)/relatorios/page.tsx`
**Depends on**: T10
**Reuses**: `lerData`
**Requirement**: CONTRATO-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com o fuso de Brasília e com o de Lisboa, "2026-12-31" aparece como 31/12/2026 nas telas de meta
- [x] 29/02/2028 aparece como 29/02
- [x] `paraApi(new Date(2026, 11, 31, 23, 30))` dá "2026-12-31" nos dois fusos
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 4 testes (real: 10 testes novos; suíte 122 → 132)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(frontend): mostra as datas sem hora sem mudar o dia`

---

#### T12: Tratamento único de erros

**What**: `src/lib/erros.ts` com `tratarErro`; tempo máximo de 120 s na importação e na exportação; overlay de servidor acordando com botão de fechar.
**Where**: `src/lib/erros.ts` (novo), `src/services/import-export.ts`, `src/components/ui/server-wakeup-overlay.tsx`, `src/services/serverStatus.ts`
**Depends on**: T11
**Reuses**: `mensagemDeErro`, `aviso-de-conexao.tsx`
**Requirement**: CONTRATO-30, CONTRATO-31, CONTRATO-33, CONTRATO-34, CONTRATO-35

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Erro 400 por campo chama `setError` em cada campo do formulário; o que sobra vai para o Sonner
- [x] `detail` aparece no Sonner
- [x] Erro de rede, 503 e tempo esgotado mostram "Não foi possível falar com o servidor." com "Tentar de novo", que chama a função passada
- [x] Importação e exportação usam 120 s; as demais, 30 s
- [x] O overlay fecha pelo botão e não volta no mesmo episódio
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 7 testes (real: 11 testes novos; suíte 132 → 143)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(frontend): trata erros de campo, de servidor e de rede num lugar só`

---

#### T13: Só o Sonner

**What**: Os 9 arquivos que usam `useToast` passam ao Sonner; `toaster.tsx` e `use-toast.ts` saem.
**Where**: `src/app/(app)/calendario/page.tsx`, `categorias/page.tsx`, `dashboard/page.tsx`, `orcamentos/page.tsx`, `tags/page.tsx`, `src/components/budgets/BudgetForm.tsx`, `ImportBudgetsDialog.tsx`, `src/components/categories/CategoryForm.tsx`, `src/components/tags/TagForm.tsx`
**Depends on**: T12
**Reuses**: `tratarErro`
**Requirement**: CONTRATO-32

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Nenhum arquivo importa `useToast` nem `@/components/ui/toaster`
- [x] Salvar uma tag com erro mostra o aviso do Sonner
- [x] Build gate (frontend) passa
- [x] Test count: pelo menos 3 testes (real: 3 testes novos; suíte 143 → 146)

**Tests**: unit (frontend)
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(frontend): mostra todos os avisos pelo Sonner`

---

### Phase 4: Listas no frontend

#### T14: Coleções completas e listas do admin

**What**: Services e componentes de coleção leem o array; os services deixam de engolir erro; o admin lê o formato paginado, com paginação nos logs e sem o usuário de mentira.
**Where**: `src/services/*.ts`, `src/app/(app)/cartoes/page.tsx`, componentes de transação e fatura que leem coleções, `src/app/(admin)/admin/*`
**Depends on**: None
**Reuses**: `tratarErro`
**Requirement**: CONTRATO-01, CONTRATO-02, CONTRATO-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com 15 tags e 12 orçamentos simulados, a tela de tags, o seletor de tags e a tela de orçamentos mostram todos
- [x] A lista de logs do admin mostra total e controles de página
- [x] Nenhum arquivo de `src` lê `results ||`
- [x] Erro ao carregar tags mostra o aviso com "Tentar de novo"
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 5 testes (real: 6 testes novos; suíte 146 → 152)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(frontend): mostra todos os itens das coleções e pagina as listas do admin`

---

#### T15: Busca da lista de transações

**What**: Um efeito de busca; página 1 junto com a mudança de filtro; espera de 300 ms na busca; `AbortController` para descartar a resposta antiga.
**Where**: `src/app/(app)/transacoes/page.tsx`
**Depends on**: T14
**Reuses**: NONE
**Requirement**: CONTRATO-05, CONTRATO-06, CONTRATO-07, CONTRATO-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Montar a tela faz um GET de transações
- [x] Mudar um filtro estando na página 3 faz um GET só, com `page=1`
- [x] Digitar "mercado" faz um GET só, 300 ms depois da última tecla
- [x] Uma resposta lenta que chega depois da mais nova não aparece e não mostra erro
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 4 testes (real: 4 testes novos; suíte 152 → 156)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(frontend): busca as transações uma vez por mudança, sem respostas atrasadas`

---

#### T16: Várias categorias e total do dia

**What**: Filtro com seleção de várias categorias, enviadas como `categoryId` repetido; o "Saldo do Dia" vem de `day_totals`.
**Where**: `src/components/transactions/transaction-filters.tsx`, `src/app/(app)/transacoes/page.tsx`
**Depends on**: T15
**Reuses**: `formatarMoeda`
**Requirement**: CONTRATO-09, CONTRATO-10, CONTRATO-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Escolher duas categorias envia `categoryId=a&categoryId=b`
- [x] O total do dia mostrado é o de `day_totals`, não a soma da página
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 3 testes (real: 3 testes novos; suíte 156 → 159)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(frontend): filtra por várias categorias e mostra o total real do dia`

---

#### T17: Recorrentes e outras listas de transações

**What**: Recorrentes com `is_recurring=true`, paginação e `lerData`; `transaction-form-dialog` com `page_size`; `transfer-form-dialog` e `SpareChangeBank` com `results`.
**Where**: `src/app/(app)/transacoes/recorrentes/page.tsx`, `src/components/transactions/transaction-form-dialog.tsx`, `src/components/transactions/transfer-form-dialog.tsx`, `src/components/goals/SpareChangeBank.tsx`
**Depends on**: T16
**Reuses**: NONE
**Requirement**: CONTRATO-05, CONTRATO-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Recorrentes pede `is_recurring=true` e mostra total e controles de página
- [x] Nenhuma chamada envia `limit`
- [x] Build gate (frontend) passa
- [x] Test count: pelo menos 3 testes (real: 4 testes novos; suíte 159 → 163)

**Tests**: unit (frontend)
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(frontend): lista as recorrentes e lê as transações pelo contrato`

---

### Phase 5: Valores, datas, preferências e erros nas telas

#### T18: Formatador único

**What**: As 20 cópias locais de `formatCurrency` e os formatadores inline de moeda passam a `formatarMoeda`; os eixos dos gráficos usam `formatarMoeda` ou `formatarMoedaCompacta`; leituras de dinheiro da API passam por `paraCentavos` (os valores agora chegam como texto).
**Where**: telas e componentes listados no design (seção Frontend: dinheiro)
**Depends on**: None
**Reuses**: `src/lib/dinheiro.ts`
**Requirement**: CONTRATO-16, CONTRATO-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Nenhuma definição local de `formatCurrency` ou `Intl.NumberFormat` de moeda fora de `src/lib/dinheiro.ts`
- [x] O eixo de um gráfico com 800 mostra "R$ 800,00"
- [x] Nenhuma soma de dois valores da API concatena texto (teste do dashboard com valores em texto)
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 3 testes (real: 3 testes novos; suíte 163 → 166)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `refactor(frontend): formata todo valor em reais num formatador único`

---

#### T19: Formulários enviam dinheiro em texto

**What**: Formulários com `MoneyInput`, metas (`parseAmount` sai), orçamento, transferência e cofrinho enviam texto decimal calculado em centavos; ajuste de saldo usa `permitirNegativo`.
**Where**: formulários de transação, transferência, compra no cartão, fatura, conta, cartão, orçamento, meta, aporte, resgate, ajuste de saldo e `SpareChangeBank`
**Depends on**: T18
**Reuses**: `MoneyInput`, `paraCentavos`, `deCentavos`
**Requirement**: CONTRATO-17, CONTRATO-19, CONTRATO-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Aporte de "1.500" envia `amount: "1500.00"`
- [x] Ajuste para "-50,00" envia `new_balance: "-50.00"`
- [x] Nenhum formulário envia valor calculado em ponto flutuante (teste do cofrinho com valores que somam 0.1 + 0.2)
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 4 testes (real: 5 testes novos; suíte 166 → 171)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(frontend): envia valores em dinheiro calculados sem ponto flutuante`

---

#### T20: Datas enviadas sem hora

**What**: Aporte e resgate enviam `date: hojeNaApi()`; meta envia `target_date` por `paraApi`; exportação envia `startDate` e `endDate` como texto.
**Where**: `src/components/goals/GoalDepositForm.tsx`, `GoalWithdrawForm.tsx`, `GoalForm.tsx`, `src/services/goals.ts`, `src/app/(app)/importar/page.tsx`, `src/services/import-export.ts`
**Depends on**: T19
**Reuses**: `paraApi`
**Requirement**: CONTRATO-24, CONTRATO-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Editar só o nome de uma meta com data-alvo 31/12/2026 envia `target_date: "2026-12-31"` nos fusos de Brasília e de Lisboa
- [x] Exportar setembro envia `endDate=2026-09-30`
- [x] Aporte e resgate não enviam `datetime`
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 4 testes (real: 10 testes novos, 5 casos em cada fuso; suíte 171 → 181)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(frontend): envia as datas sem hora no formato AAAA-MM-DD`

---

#### T21: Preferências salvas e aplicadas

**What**: Configurações enviam `PATCH /users/me/` só com `preferences`; o tema do usuário é aplicado ao carregar.
**Where**: `src/app/(app)/configuracoes/page.tsx`, `src/contexts/auth-context.tsx` ou componente de tema no layout autenticado
**Depends on**: T20
**Reuses**: `next-themes`
**Requirement**: CONTRATO-26, CONTRATO-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Salvar o tema escuro e desligar o e-mail envia só `{preferences: {...}}`
- [x] Com um usuário que volta com `theme: "dark"`, o tema escuro é aplicado ao carregar
- [x] Erro de preferência aparece no campo
- [x] Quick gate (frontend) passa
- [x] Test count: pelo menos 3 testes (real: 3 testes novos; suíte 181 → 184)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(frontend): salva as preferências e aplica o tema do usuário ao carregar`

---

#### T22: Erros de campo e falhas silenciosas

**What**: Os formulários tratam o erro por `tratarErro` com `form`; os catches silenciosos do inventário passam a `tratarErro` com `tentarDeNovo`; as leituras de `.error` saem.
**Where**: formulários de transação, transferência, compra no cartão, conta, cartão, orçamento, categoria, tag e meta; telas e componentes com catch silencioso listados no design
**Depends on**: T21
**Reuses**: `tratarErro`
**Requirement**: CONTRATO-30, CONTRATO-31, CONTRATO-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Orçamento duplicado mostra a mensagem do backend embaixo do campo de categoria
- [x] Com o backend fora, a tela de tags mostra o aviso com "Tentar de novo", e clicar busca de novo
- [x] Nenhum `catch` em `src` fica só com `console.error`
- [x] Build gate (frontend) passa
- [x] Test count: pelo menos 4 testes (real: 4 testes novos; suíte 184 → 188)

**Tests**: unit (frontend)
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(frontend): mostra os erros no campo e não deixa falha silenciosa`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T8, backend), lote 2 com as fases 3 e 4 (T9 a T17), lote 3 com a fase 5 (T18 a T22).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Paginação padrão e coleções completas | um componente | ✅ Granular |
| T2: Recusa de filtro desconhecido | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T3: Filtro de transações da lista e da exportação | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T4: Total do dia na lista de transações | um componente | ✅ Granular |
| T5: Dinheiro como texto na API | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T6: Datas sem hora no aporte, no resgate e na exportação | um componente | ✅ Granular |
| T7: Preferências no formato da tela | um componente | ✅ Granular |
| T8: Erros em português no formato do DRF | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T9: Biblioteca de dinheiro | um componente | ✅ Granular |
| T10: Campo de dinheiro em texto | um componente | ✅ Granular |
| T11: Datas sem hora no frontend | um componente | ✅ Granular |
| T12: Tratamento único de erros | um componente | ✅ Granular |
| T13: Só o Sonner | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T14: Coleções completas e listas do admin | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T15: Busca da lista de transações | um componente | ✅ Granular |
| T16: Várias categorias e total do dia | um componente | ✅ Granular |
| T17: Recorrentes e outras listas de transações | um componente | ✅ Granular |
| T18: Formatador único | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T19: Formulários enviam dinheiro em texto | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T20: Datas enviadas sem hora | um componente | ✅ Granular |
| T21: Preferências salvas e aplicadas | um componente | ✅ Granular |
| T22: Erros de campo e falhas silenciosas | uma regra aplicada em vários arquivos | ⚠️ Coeso |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | None | sem seta dentro da fase | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | None | sem seta dentro da fase | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |
| T14 | None | sem seta dentro da fase | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |
| T17 | T16 | T16 → T17 | ✅ Match |
| T18 | None | sem seta dentro da fase | ✅ Match |
| T19 | T18 | T18 → T19 | ✅ Match |
| T20 | T19 | T19 → T20 | ✅ Match |
| T21 | T20 | T20 → T21 | ✅ Match |
| T22 | T21 | T21 → T22 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Paginação padrão e coleções completas | Backend | integration | integration | ✅ OK |
| T2: Recusa de filtro desconhecido | Backend | integration | integration | ✅ OK |
| T3: Filtro de transações da lista e da exportação | Backend | integration | integration | ✅ OK |
| T4: Total do dia na lista de transações | Backend | integration | integration | ✅ OK |
| T5: Dinheiro como texto na API | Backend | integration | integration | ✅ OK |
| T6: Datas sem hora no aporte, no resgate e na exportação | Backend | integration | integration | ✅ OK |
| T7: Preferências no formato da tela | Backend | integration | integration | ✅ OK |
| T8: Erros em português no formato do DRF | Backend | integration | integration | ✅ OK |
| T9: Biblioteca de dinheiro | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T10: Campo de dinheiro em texto | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T11: Datas sem hora no frontend | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T12: Tratamento único de erros | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T13: Só o Sonner | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T14: Coleções completas e listas do admin | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T15: Busca da lista de transações | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T16: Várias categorias e total do dia | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T17: Recorrentes e outras listas de transações | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T18: Formatador único | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T19: Formulários enviam dinheiro em texto | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T20: Datas enviadas sem hora | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T21: Preferências salvas e aplicadas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T22: Erros de campo e falhas silenciosas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
