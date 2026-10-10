# Classes de despesa Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/classes-de-despesa/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Classes, classe das categorias, divisão nos gráficos, filtro e exportação (backend) | integration | Cada AC com status, código e mensagem exatos; concorrência com `TransactionTestCase` e duas threads; migração testada importando o módulo | `tests/classes/test_*.py` | `docker compose exec -T backend python manage.py test tests.classes --noinput` |
| Gerenciar classes, formulário e lista de categorias, gráfico por classe e filtro (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/classes/*.test.tsx` | `npx vitest run tests/classes` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 152 erros de lint antigos: o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.classes --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/classes` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Classes e classe das categorias

```
T1 → T2
T2 → T3
T3 → T4
```

### Phase 2: Divisão, filtro e exportação

```
T5 → T6
T6 → T7
```

### Phase 3: Telas

```
T8 → T9
T9 → T10
T10 → T11
```

---

## Task Breakdown

### Phase 1: Classes e classe das categorias

#### T1: Modelo das classes e implantação

**What**: `ClasseDeDespesa` e `Category.classe` (SET_NULL); `normalizar` vai para `core/texto.py`; migração que cria Essencial e Dispensável para cada usuário e dá a classe inicial às categorias de despesa sem mãe com nome de categoria padrão; `ClasseDeDespesa` em `MODELOS_DO_USUARIO`.
**Where**: `transactions/models.py`, `transactions/migrations/`, `core/texto.py` (novo), `data_exchange/importacao/texto.py`, `api/exclusao.py`
**Depends on**: None
**Reuses**: `normalizar`, padrão de migração de `transactions/0011_relatorios`
**Requirement**: CLASSE-14, CLASSE-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A migração cria Essencial e Dispensável para cada usuário existente
- [x] "comida" em minúsculas recebe Essencial; "Mercado" fica sem classe; subcategorias e categorias de receita ficam sem classe própria
- [x] A exclusão definitiva apaga as classes do usuário, e o teste de completude da LGPD passa
- [x] Build gate passa
- [x] Test count: 7 testes

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: cria as classes de despesa e as implanta para quem já usa o app`

---

#### T2: Classes no padrão do cadastro

**What**: `criar_padrao_do_cadastro` cria Essencial e Dispensável e dá a classe inicial às categorias padrão; o teste da limpeza conta as duas classes.
**Where**: `transactions/padrao.py`, `tests/painel_admin/`
**Depends on**: T1
**Reuses**: `criar_padrao_do_cadastro`
**Requirement**: CLASSE-01, CLASSE-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Um usuário novo tem Essencial e Dispensável
- [x] Casa, Comida, Transporte e Educação ficam em Essencial; Lazer, Eletrônicos, Doces, Doação e Presente (despesa) em Dispensável; Aluguel e Energia herdam de Casa
- [x] A limpeza do painel termina com as duas classes, sem duplicar
- [x] Quick gate passa
- [x] Test count: 5 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: dá as classes Essencial e Dispensável a todo cadastro novo`

---

#### T3: API das classes

**What**: `/api/expense-classes/` sem paginação, com `categories_count`; criação com trava do usuário, limite de 5, nome de 1 a 30 caracteres e único sem maiúsculas e acentos; classes padrão sem renomear nem excluir; exclusão tira a classe das categorias.
**Where**: `transactions/views.py`, `transactions/serializers.py`, `transactions/urls.py`
**Depends on**: T2
**Reuses**: `normalizar`, `select_for_update` de `conferir_limite`
**Requirement**: CLASSE-02, CLASSE-04, CLASSE-05, CLASSE-06, CLASSE-07, CLASSE-08, CLASSE-10, CLASSE-11, CLASSE-12, CLASSE-13, CLASSE-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A lista vem completa, sem paginação, com `is_default` e `categories_count`
- [x] A sexta classe recebe 400 "Limite de 5 classes atingido."
- [x] Nome vazio ou com 31 caracteres recebe 400 no campo `name`; "dividas" depois de "Dívidas" recebe "Já existe uma classe com esse nome."
- [x] Renomear ou excluir Essencial recebe 400 com a mensagem das classes padrão; mudar a cor dela funciona
- [x] Excluir uma classe usada por duas categorias as deixa sem classe própria; com uma falha forçada no meio, nada muda
- [x] Duas criações simultâneas com 4 classes terminam com 5; duas com o mesmo nome terminam com uma
- [x] Nenhum log grava o nome da classe; nenhum plano trava a rota
- [x] Full gate passa
- [x] Test count: 18 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: permite criar, editar e excluir classes de despesa até o limite de 5`

---

#### T4: Classe das categorias

**What**: `transactions/classes.py` com `mapa_de_classes` e `categorias_das_classes`; `CategorySerializer` ganha `expense_class` (gravável), `effective_class` e `class_inherited`; recusa classe em receita; tira a classe ao virar receita.
**Where**: `transactions/classes.py` (novo), `transactions/serializers.py`, `core/fields.py`
**Depends on**: T3
**Reuses**: `OwnedPrimaryKeyRelatedField`
**Requirement**: CLASSE-16, CLASSE-17, CLASSE-18, CLASSE-21, CLASSE-22, CLASSE-23, CLASSE-26, CLASSE-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Delivery dentro de Comida (Essencial) devolve `effective_class` Essencial com `class_inherited` verdadeiro; com classe própria Dispensável, só ela muda; sem a própria, volta a herdar
- [x] Mãe sem classe com subcategoria classificada: a subcategoria usa a dela e a mãe fica sem classe
- [x] Classe em Salário recebe 400 "Categorias de receita não têm classe."; despesa que vira receita perde a classe própria
- [x] Classe de outro usuário e id inexistente recebem a mesma resposta no campo `expense_class`
- [x] A importação cria categorias sem classe própria; categoria excluída mantém a classe no mapa
- [x] Full gate passa
- [x] Test count: 12 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: dá classe às categorias de despesa com herança da categoria-mãe`

---

### Phase 2: Divisão, filtro e exportação

#### T5: Divisão por classe nos gráficos simples

**What**: `get_simple_charts` devolve `expense_by_class` com `class_id`, `class_name`, `color` e `amount`, pelas mesmas transações de `expense_by_category`, com "Sem classe" em cinza.
**Where**: `reports/services.py`
**Depends on**: T4
**Reuses**: `regras.despesas`, `mapa_de_classes`
**Requirement**: CLASSE-28, CLASSE-29, CLASSE-30, CLASSE-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] R$ 600,00 em Comida, R$ 300,00 em Doces e R$ 100,00 sem categoria dão Essencial 600.00, Dispensável 300.00 e Sem classe 100.00
- [x] A soma por classe é igual à soma por categoria, com compras parceladas no cartão e despesas pendentes
- [x] Passar Doces para Essencial muda também o mês anterior
- [x] Período sem despesas devolve a lista vazia; a rota não tem trava de plano
- [x] Quick gate passa
- [x] Test count: 7 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: mostra nos gráficos quanto das despesas foi para cada classe`

---

#### T6: Filtro por classe

**What**: `filtrar_transacoes` aceita `classId` repetido, com `sem_classe`, só despesas e compras no cartão, combinado com a categoria; valor inválido recebe 400; a lista e as exportações aceitam o parâmetro.
**Where**: `transactions/filtros.py`, `transactions/views.py`, `data_exchange/views.py`
**Depends on**: T5
**Reuses**: `categorias_das_classes`
**Requirement**: CLASSE-34, CLASSE-35, CLASSE-36, CLASSE-37, CLASSE-38, CLASSE-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Dispensável traz as despesas e compras no cartão de Doces e nenhuma receita, transferência ou pagamento de fatura
- [x] `sem_classe` traz a despesa sem categoria e a de categoria sem classe; junto com uma classe, traz os dois grupos
- [x] Dispensável com a categoria Comida não traz nada
- [x] Classe de outro usuário ou texto qualquer recebe 400 "Classe inválida no filtro: <valor>."
- [x] A exportação em XLSX e em PDF com o mesmo filtro traz as mesmas transações da lista
- [x] Full gate passa
- [x] Test count: 9 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: filtra as transações e a exportação por classe`

---

#### T7: Coluna Classe no XLSX

**What**: `_linhas_de_transacoes` ganha a coluna "Classe" pelo mapa; o XLSX das transações e o download dos dados da LGPD a mostram; a view do XLSX ganha `select_related`.
**Where**: `data_exchange/services.py`, `data_exchange/views.py`
**Depends on**: T6
**Reuses**: `mapa_de_classes`
**Requirement**: CLASSE-40

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Despesas e compras no cartão mostram a classe efetiva ou "Sem classe"; receitas e transferências ficam vazias
- [x] O XLSX dos dados da LGPD também tem a coluna
- [x] Build gate passa
- [x] Test count: 3 testes

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: inclui a classe na exportação em XLSX`

---

### Phase 3: Telas

#### T8: Gerenciar classes

**What**: Serviço e tipos das classes; diálogo "Gerenciar classes" na página de categorias com a lista, as sugestões ainda não criadas, criação, edição e exclusão com a contagem de categorias.
**Where**: `src/services/expense-classes.ts` (novo), `src/types/categories.ts`, `src/components/categories/GerenciarClasses.tsx` (novo), `src/app/(app)/categorias/page.tsx`
**Depends on**: T7
**Reuses**: `tratarErro`
**Requirement**: CLASSE-03, CLASSE-04, CLASSE-05, CLASSE-07, CLASSE-08, CLASSE-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] As sugestões mostram só Dívidas, Impostos e taxas e Profissional que o usuário ainda não criou
- [ ] Criar pela sugestão envia o nome e a cor; o erro de nome repetido aparece no campo e o limite no toast
- [ ] Essencial e Dispensável não têm as ações de renomear e excluir
- [ ] Excluir mostra quantas categorias usam a classe e só chama a API depois da confirmação
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 5 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: permite gerenciar as classes de despesa na tela de categorias`

---

#### T9: Classe no formulário e na lista de categorias

**What**: O formulário de despesa ganha a seleção da classe, com "Herdar da categoria-mãe" nas subcategorias; a lista mostra a classe efetiva com a cor e "(herdada)".
**Where**: `src/components/categories/CategoryForm.tsx`, `src/app/(app)/categorias/page.tsx`
**Depends on**: T8
**Reuses**: NONE
**Requirement**: CLASSE-17, CLASSE-19, CLASSE-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A subcategoria nova começa herdando a classe da mãe e pode escolher outra
- [ ] Categoria de receita não mostra a seleção de classe
- [ ] A lista mostra a classe efetiva com a cor e "(herdada)" quando vem da mãe
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: mostra e escolhe a classe nas categorias de despesa`

---

#### T10: Gráfico por classe

**What**: `ClassDistributionChart` no dashboard e na tela Relatórios, com valor, porcentagem de uma casa, cor da classe, cinza para "Sem classe", mensagem sem despesas e clique para a lista filtrada.
**Where**: `src/components/dashboard/ClassDistributionChart.tsx` (novo), `src/app/(app)/dashboard/page.tsx`, `src/app/(app)/relatorios/page.tsx`, `src/services/reports.ts`
**Depends on**: T9
**Reuses**: `CategoryDistributionChart`, `src/lib/dinheiro.ts`
**Requirement**: CLASSE-31, CLASSE-32, CLASSE-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] 600, 300 e 100 aparecem como 60,0%, 30,0% e 10,0%, com "Sem classe" em cinza
- [ ] Sem despesas aparece "Nenhuma despesa no período."
- [ ] Clicar numa classe abre `/transacoes` com `classId` e o período dos gráficos, inclusive na tela Relatórios sem os relatórios avançados
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: mostra a divisão das despesas por classe no dashboard e nos relatórios`

---

#### T11: Filtro de classe na lista e na exportação

**What**: `TransactionFilters` ganha a seleção de classes com "Sem classe"; a lista lê `classId` da URL; a lista e a exportação enviam `classId` repetido.
**Where**: `src/components/transactions/transaction-filters.tsx`, `src/app/(app)/transacoes/page.tsx`, `src/services/import-export.ts`
**Depends on**: T10
**Reuses**: `TransactionFilters`
**Requirement**: CLASSE-33, CLASSE-34, CLASSE-35, CLASSE-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Abrir `/transacoes?classId=<id>&startDate=&endDate=` já filtra pela classe e pelo período
- [ ] Escolher duas classes e "Sem classe" envia três `classId`
- [ ] A exportação envia as classes escolhidas
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `feat: filtra a lista e a exportação por classe`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T7), lote 2 com a fase 3 (T8 a T11).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Modelo das classes e implantação | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T2: Classes no padrão do cadastro | um componente | ✅ Granular |
| T3: API das classes | um componente | ✅ Granular |
| T4: Classe das categorias | um componente | ✅ Granular |
| T5: Divisão por classe nos gráficos simples | um componente | ✅ Granular |
| T6: Filtro por classe | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T7: Coluna Classe no XLSX | um componente | ✅ Granular |
| T8: Gerenciar classes | um componente | ✅ Granular |
| T9: Classe no formulário e na lista de categorias | um componente | ✅ Granular |
| T10: Gráfico por classe | um componente | ✅ Granular |
| T11: Filtro de classe na lista e na exportação | um componente | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Modelo das classes e implantação | Backend | integration | integration | ✅ OK |
| T2: Classes no padrão do cadastro | Backend | integration | integration | ✅ OK |
| T3: API das classes | Backend | integration | integration | ✅ OK |
| T4: Classe das categorias | Backend | integration | integration | ✅ OK |
| T5: Divisão por classe nos gráficos simples | Backend | integration | integration | ✅ OK |
| T6: Filtro por classe | Backend | integration | integration | ✅ OK |
| T7: Coluna Classe no XLSX | Backend | integration | integration | ✅ OK |
| T8: Gerenciar classes | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T9: Classe no formulário e na lista de categorias | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T10: Gráfico por classe | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T11: Filtro de classe na lista e na exportação | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
