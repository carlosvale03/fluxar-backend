# Vínculo entre transações Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/vinculo-entre-transacoes/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Regras do vínculo, rotas, gasto relacionado, campos, filtros e relatório (backend) | integration | Cada AC com status, código e mensagem exatos; concorrência com `TransactionTestCase` e duas threads; saldos conferidos antes e depois | `tests/vinculos/test_*.py` | `docker compose exec -T backend python manage.py test tests.vinculos --noinput` |
| Marcas na lista, ações de vínculo, filtro e relatório (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/vinculos/*.test.tsx` | `npx vitest run tests/vinculos` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 149 erros de lint antigos: o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.vinculos --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/vinculos` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Vínculo

```
T1 → T2
T2 → T3
T3 → T4
```

### Phase 2: Filtro e relatório

```
T5 → T6
```

### Phase 3: Telas

```
T7 → T8
T8 → T9
T9 → T10
```

---

## Task Breakdown

### Phase 1: Vínculo

#### T1: Campo e regras do vínculo

**What**: `Transaction.principal` (SET_NULL) com a restrição de não ser principal de si mesma; `transactions/vinculos.py` com `raiz_da_compra`, `vincular` e `desvincular`, travando as duas raízes em ordem de id; troca para receita limpa os vínculos.
**Where**: `transactions/models.py`, `transactions/migrations/`, `transactions/vinculos.py` (novo), `transactions/serializers.py`
**Depends on**: None
**Reuses**: compra inteira de `transactions/services.py:18-24`
**Requirement**: VINCULO-04, VINCULO-05, VINCULO-06, VINCULO-07, VINCULO-08, VINCULO-09, VINCULO-10, VINCULO-12, VINCULO-13, VINCULO-14, VINCULO-15, VINCULO-16, VINCULO-17, VINCULO-19, VINCULO-22, VINCULO-23

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Receita, transferência e pagamento de fatura recebem "Só despesas e compras no cartão podem ser vinculadas."
- [ ] Dependente como principal, principal como dependente e ela mesma recebem as mensagens da spec
- [ ] Ligar a outra principal troca; ligar à mesma não muda nada
- [ ] A parcela 3 de 10 liga a compra inteira pela raiz; uma ocorrência recorrente liga só ela
- [ ] Excluir a principal mantém as dependentes sem vínculo; despesa que vira receita perde os vínculos
- [ ] Saldos, faturas e orçamentos iguais antes e depois de vincular, trocar e desfazer
- [ ] Pedidos simultâneos de A em B e de B em A: só um passa
- [ ] Build gate passa
- [ ] Test count: pelo menos 14 testes

**Tests**: integration
**Gate**: build

**Commit**: `feat: cria o vínculo entre uma transação principal e as dependentes`

---

#### T2: Rotas de vincular e desfazer

**What**: `POST` e `DELETE /api/transactions/{id}/link/`; vincular com a trava `vinculos`, desfazer sempre livre; `vinculos` sai de `SEM_ROTA` no teste de travas.
**Where**: `transactions/views.py`, `core/fields.py`, `tests/permissoes/`, `tests/isolamento/`
**Depends on**: T1
**Reuses**: `vincular`, `desvincular`, `exigir_recurso`
**Requirement**: VINCULO-02, VINCULO-04, VINCULO-09, VINCULO-10, VINCULO-11, VINCULO-20, VINCULO-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Ligar uma transação existente devolve 200 com a principal
- [ ] Principal de outro usuário ou inexistente recebe 400 "Transação não encontrada." no campo `principal`; dependente de outro usuário recebe 404
- [ ] Com o recurso travado, ligar recebe 403 `plan_locked` e desfazer funciona
- [ ] Full gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat: permite ligar e desfazer o vínculo de uma transação existente`

---

#### T3: Gasto relacionado na criação

**What**: `POST /transactions/` (despesa) e `POST /transactions/credit-card-expense/` aceitam `principal`, gravado na mesma transação do banco; recusa desfaz a criação; trava `vinculos`.
**Where**: `transactions/serializers.py`, `transactions/services.py`, `transactions/views.py`
**Depends on**: T2
**Reuses**: `vincular`, `create_credit_card_expense`
**Requirement**: VINCULO-01, VINCULO-12, VINCULO-18, VINCULO-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Lançar o transporte de R$ 45,00 com o cinema como principal cria a dependente
- [ ] Compra parcelada com principal liga a raiz da compra
- [ ] Principal que já é dependente recebe 400 e nenhuma transação fica criada
- [ ] Com o recurso travado, enviar `principal` recebe 403
- [ ] Quick gate passa
- [ ] Test count: pelo menos 5 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat: permite lançar um gasto relacionado a partir de uma transação`

---

#### T4: Custo total e principal na API

**What**: `TransactionSerializer` ganha `principal`, `principal_detail`, `dependents_count` e `total_cost`, com as parcelas somadas e uma consulta agregada por página.
**Where**: `transactions/serializers.py`, `transactions/views.py`
**Depends on**: T3
**Reuses**: NONE
**Requirement**: VINCULO-26, VINCULO-27, VINCULO-28

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O cinema de R$ 50,00 com o transporte de R$ 45,00 devolve `total_cost` "95.00" e `dependents_count` 1
- [ ] O transporte devolve `principal_detail` com a descrição e a data do cinema
- [ ] Um jantar em 3 parcelas de R$ 40,00 ligado ao cinema soma R$ 120,00 no custo
- [ ] O gráfico por categoria continua com R$ 50,00 em Lazer e R$ 45,00 em Transporte
- [ ] A lista com 20 transações vinculadas não faz uma consulta por linha
- [ ] Full gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat: mostra na API o custo total da principal e a principal da dependente`

---

### Phase 2: Filtro e relatório

#### T5: Filtros de vínculo

**What**: `principalId` e `linked=true` em `filtrar_transacoes`, na lista e nas exportações, com as parcelas; id inválido recebe 400; trava `vinculos` nos dois filtros.
**Where**: `transactions/filtros.py`, `transactions/views.py`, `data_exchange/views.py`
**Depends on**: T4
**Reuses**: `filtrar_transacoes`
**Requirement**: VINCULO-29, VINCULO-30, VINCULO-32, VINCULO-33, VINCULO-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `principalId` do cinema traz o cinema e o transporte
- [ ] `linked=true` traz só principais e dependentes, com as parcelas
- [ ] Id de outro usuário recebe 400 "Transação inválida no filtro: <valor>."
- [ ] A exportação com o filtro do cinema traz as mesmas duas linhas, sem coluna de vínculo
- [ ] Com o recurso travado, os filtros recebem 403
- [ ] Full gate passa
- [ ] Test count: pelo menos 7 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat: filtra a lista e a exportação pelas transações vinculadas`

---

#### T6: Relatório de gastos puxados

**What**: `GET /api/reports/linked-expenses/` com os parâmetros de período dos gráficos simples e a trava `vinculos`: dependentes por `regras.despesas` no período, agrupadas pela categoria raiz da principal e da dependente.
**Where**: `reports/services.py`, `reports/views.py`
**Depends on**: T5
**Reuses**: `regras.despesas`, `_get_date_range`
**Requirement**: VINCULO-34, VINCULO-35, VINCULO-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Três cinemas com transportes de R$ 60,00 no mês dão Lazer com R$ 180,00 puxados de Transporte
- [ ] Transporte do mês seguinte ligado a um cinema deste mês entra no mês seguinte
- [ ] Dependente sem categoria entra em "Sem categoria"; subcategoria entra na raiz
- [ ] Mês sem vínculos devolve `groups` vazio; com o recurso travado, 403
- [ ] Build gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: build

**Commit**: `feat: mostra quanto cada categoria puxa de gastos em outras`

---

### Phase 3: Telas

#### T7: Custo total e principal na lista

**What**: Tipos e serviço; a principal mostra "Custo total R$ X" com a quantidade de dependentes e abre `/transacoes?principalId=<id>`; a dependente mostra "Por causa de: <descrição>, dd/mm/aaaa".
**Where**: `src/types/transactions.ts`, `src/services/vinculos.ts` (novo), `src/app/(app)/transacoes/page.tsx`
**Depends on**: T6
**Reuses**: `src/lib/dinheiro.ts`
**Requirement**: VINCULO-24, VINCULO-25, VINCULO-31

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O cinema mostra "Custo total R$ 95,00" e 1 dependente
- [ ] O transporte mostra "Por causa de: Cinema, 12/09/2026"
- [ ] Clicar no custo abre a lista filtrada pela principal, com descrição, categoria e valor das dependentes
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: mostra o custo total e a principal das transações vinculadas`

---

#### T8: Lançar, vincular e desfazer

**What**: Ações "Lançar gasto relacionado" (formulário de despesa com a principal), "Vincular a um gasto" (busca por descrição, data ou valor) e "Desfazer vínculo"; as duas primeiras travadas pelo plano.
**Where**: `src/components/transactions/vincular-transacao.tsx` (novo), `src/components/transactions/transaction-form-dialog.tsx`, `src/app/(app)/transacoes/page.tsx`
**Depends on**: T7
**Reuses**: `usePlan`, `tratarErro`
**Requirement**: VINCULO-01, VINCULO-02, VINCULO-03, VINCULO-04, VINCULO-20, VINCULO-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] "Lançar gasto relacionado" envia `principal` na criação
- [ ] A busca procura só despesas e compras no cartão e liga a escolhida
- [ ] O 400 do vínculo aparece no toast
- [ ] Com o recurso travado, lançar e vincular aparecem travados e desfazer funciona
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 6 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: permite lançar, vincular e desfazer gastos relacionados pela tela`

---

#### T9: Filtro com vínculo

**What**: "Com vínculo" no `TransactionFilters`, na lista e na exportação, travado pelo plano; a lista lê `principalId` da URL.
**Where**: `src/components/transactions/transaction-filters.tsx`, `src/app/(app)/transacoes/page.tsx`, `src/services/import-export.ts`
**Depends on**: T8
**Reuses**: `TransactionFilters`
**Requirement**: VINCULO-30, VINCULO-31, VINCULO-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Marcar "Com vínculo" envia `linked=true` na lista e na exportação
- [ ] `/transacoes?principalId=<id>` envia o filtro
- [ ] Com o recurso travado, o filtro aparece travado
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: filtra a lista e a exportação pelas transações com vínculo`

---

#### T10: Relatório de gastos puxados

**What**: Seção "Gastos puxados" na tela Relatórios, dentro de `RecursoBloqueado chave="vinculos"`, com cada grupo como "Lazer puxou R$ 180,00 de Transporte" e a mensagem sem vínculos.
**Where**: `src/components/reports/GastosPuxados.tsx` (novo), `src/app/(app)/relatorios/page.tsx`, `src/services/reports.ts`
**Depends on**: T9
**Reuses**: `RecursoBloqueado`
**Requirement**: VINCULO-36, VINCULO-37

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O relatório mostra "Lazer puxou R$ 180,00 de Transporte"
- [ ] Sem vínculos aparece "Nenhum gasto vinculado no período."
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `feat: mostra o relatório de gastos puxados na tela Relatórios`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T6), lote 2 com a fase 3 (T7 a T10).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Campo e regras do vínculo | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T2: Rotas de vincular e desfazer | um componente | ✅ Granular |
| T3: Gasto relacionado na criação | um componente | ✅ Granular |
| T4: Custo total e principal na API | um componente | ✅ Granular |
| T5: Filtros de vínculo | um componente | ✅ Granular |
| T6: Relatório de gastos puxados | um componente | ✅ Granular |
| T7: Custo total e principal na lista | um componente | ✅ Granular |
| T8: Lançar, vincular e desfazer | um componente | ✅ Granular |
| T9: Filtro com vínculo | um componente | ✅ Granular |
| T10: Relatório de gastos puxados | um componente | ✅ Granular |

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

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Campo e regras do vínculo | Backend | integration | integration | ✅ OK |
| T2: Rotas de vincular e desfazer | Backend | integration | integration | ✅ OK |
| T3: Gasto relacionado na criação | Backend | integration | integration | ✅ OK |
| T4: Custo total e principal na API | Backend | integration | integration | ✅ OK |
| T5: Filtros de vínculo | Backend | integration | integration | ✅ OK |
| T6: Relatório de gastos puxados | Backend | integration | integration | ✅ OK |
| T7: Custo total e principal na lista | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T8: Lançar, vincular e desfazer | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T9: Filtro com vínculo | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T10: Relatório de gastos puxados | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
