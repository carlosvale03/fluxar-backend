# Relatórios Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/relatorios/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Regras comuns, relatórios, orçamentos, migração e PDF (backend) | integration | Cada AC com os valores exatos do Independent Test de cada história; o mesmo cenário conferido no dashboard, na pizza, no calendário e na comparação mensal | `tests/relatorios/test_*.py` | `docker compose exec -T backend python manage.py test tests.relatorios --noinput` |
| Dashboard e tela de relatórios (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/relatorios/*.test.tsx` | `npx vitest run tests/relatorios` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 167 erros de lint antigos (MAN-04 e as regras novas do react-hooks): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.relatorios --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/relatorios` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Regras comuns

```
T1 → T2
T2 → T3
```

### Phase 2: Relatórios

```
T4 → T5
T5 → T6
T6 → T7
T7 → T8
T8 → T9
T9 → T10
```

### Phase 3: Frontend

```
T11 → T12
T12 → T13
```

---

## Task Breakdown

### Phase 1: Regras comuns

#### T1: Data no relatório e ajuste de saldo

**What**: Campos `report_date` (recalculada no `save()`) e `is_balance_adjustment` em `Transaction`, com a migração que preenche os dois; o ajuste de saldo grava o campo e os trocos passam a usá-lo.
**Where**: `transactions/models.py`, `transactions/migrations/`, `accounts/views.py`, `goals/trocos.py`
**Depends on**: None
**Reuses**: `accounts/faturas.dia_no_mes`
**Requirement**: REL-01, REL-02, REL-03, REL-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Compra no cartão em 10/03 tem `report_date` 10/03 mesmo com vencimento em abril
- [x] TV de R$ 1.200,00 em 12x comprada em 31/01/2026: parcelas em 31/01, 28/02, 31/03, 30/04 e assim por diante
- [x] Editar a data da compra recalcula a `report_date` das parcelas; o restante de um pagamento parcial mantém a da compra
- [x] Compra antiga sem `purchase_date` fica com a `date`; demais tipos, com a `date`
- [x] O ajuste de saldo grava `is_balance_adjustment`; a migração marca os antigos pela descrição; os trocos ignoram ajustes pelo campo
- [x] Build gate passa
- [x] Test count: 11 testes (mínimo 8)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: guarda a data de cada transação nos relatórios e marca os ajustes de saldo`

---

#### T2: Módulo de regras comuns

**What**: `reports/regras.py` com limites do mês e hoje em Brasília, meses do calendário, despesas, "A pagar", receitas, patrimônio atual e em uma data, dinheiro guardado, faturas do mês e hora em Brasília, tudo em `Decimal`.
**Where**: `reports/regras.py` (novo)
**Depends on**: T1
**Reuses**: `core/datas`, `accounts/saldo`
**Requirement**: REL-01, REL-02, REL-03, REL-04, REL-05, REL-07, REL-08, REL-10, REL-13, REL-14, REL-16, REL-17, REL-18, REL-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Despesa efetivada de R$ 100,00, pendente de R$ 50,00 e compra no cartão de R$ 80,00 com fatura aberta: despesas R$ 180,00 e "A pagar" R$ 50,00
- [x] Transferências, pagamento de fatura e ajustes ficam fora das despesas e receitas; receita pendente fica fora
- [x] Despesa efetivada de conta excluída conta no período
- [x] Patrimônio com R$ 3.000,00 em corrente, R$ 800,00 em cofrinho, R$ 2.000,00 em investimento e R$ 450,00 de compras não pagas: total R$ 5.350,00, com as quatro partes
- [x] Patrimônio no fim de um mês passado conta só o efetivado até aquele dia e as compras não pagas nele
- [x] Seis meses a partir de 31/03/2026: outubro a março, um de cada
- [x] Dinheiro guardado com aporte de R$ 500,00, transferência de R$ 300,00 para investimento e resgate de R$ 100,00: R$ 700,00; cofrinho → investimento não conta; aporte do saldo livre não conta
- [x] Faturas do mês: valor em aberto das faturas que vencem no mês de Brasília
- [x] Com o relógio às 23h de Brasília do último dia do mês, o mês atual ainda é o de Brasília
- [x] Quick gate passa
- [x] Test count: 16 testes (mínimo 14)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: concentra as regras dos relatórios num módulo só`

---

#### T3: Limite do parâmetro months

**What**: `months` validado como inteiro de 1 a 24 na comparação mensal e nos insights de tag.
**Where**: `reports/views.py`
**Depends on**: T2
**Reuses**: NONE
**Requirement**: REL-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `months=1000`, `months=0`, `months=abc` e `months=2.5` recebem 400 com "O parâmetro months aceita de 1 a 24."
- [x] `months=24` e a ausência do parâmetro funcionam
- [x] Quick gate passa
- [x] Test count: 3 testes (mínimo 3)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: limita o parâmetro months dos relatórios de 1 a 24`

---

### Phase 2: Relatórios

#### T4: Dashboard

**What**: `get_dashboard_summary` usa as regras: despesas, receitas, `payable`, faturas do mês e `net_worth` com `net_worth_breakdown`.
**Where**: `reports/services.py`
**Depends on**: None
**Reuses**: `reports/regras.py`
**Requirement**: REL-04, REL-13, REL-15, REL-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O cenário de despesas do Independent Test de REL-01 mostra R$ 180,00 de despesas e `payable` R$ 50,00
- [x] O cenário de patrimônio de REL-13 mostra `net_worth` 5350.00 e `net_worth_breakdown` com 3000.00, 800.00, 2000.00 e 450.00
- [x] `total_current_invoices` soma só as faturas não pagas que vencem no mês atual
- [x] Quick gate passa
- [x] Test count: 6 testes (mínimo 5)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: calcula o dashboard pelas regras comuns dos relatórios`

---

#### T5: Saúde financeira e score

**What**: `get_financial_health_metrics` com liquidez só do disponível, `saved_this_month`, `savings_rate` (ou `null`) e score de orçamentos pelos estourados.
**Where**: `reports/services.py`
**Depends on**: T4
**Reuses**: `dinheiro_guardado`
**Requirement**: REL-14, REL-19, REL-21, REL-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Quatro orçamentos dentro do limite valem 20 pontos; com um estourado, 15; com cinco, 0
- [x] Com R$ 5.000,00 de receitas e R$ 700,00 guardados, a taxa é 14,0
- [x] Sem receitas no mês, `savings_rate` é `null`
- [x] A liquidez não soma cofrinhos nem investimentos
- [x] Quick gate passa
- [x] Test count: 6 testes (mínimo 6)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: calcula o score e a taxa de poupança pelo dinheiro guardado`

---

#### T6: Gasto dos orçamentos

**What**: `BudgetService.get_budget_usage` soma as despesas das regras comuns no mês do orçamento, na categoria e nas subcategorias.
**Where**: `budgets/services.py`
**Depends on**: T5
**Reuses**: `despesas`
**Requirement**: REL-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Compra parcelada em 3x na categoria do orçamento conta só a parcela de cada mês
- [x] Despesa pendente não entra no gasto; compra no cartão com fatura aberta entra
- [x] O score e o dashboard contam o mesmo orçamento como estourado
- [x] Full gate passa
- [x] Test count: 4 testes (mínimo 4)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix: calcula o gasto dos orçamentos pelas mesmas despesas dos relatórios`

---

#### T7: Calendário, gráficos simples, comparação e tags

**What**: `get_calendar_data`, `get_simple_charts`, `get_monthly_comparison`, `get_tag_insights` e `get_tag_distribution` usam as regras comuns e os meses do calendário, sem `float`.
**Where**: `reports/services.py`
**Depends on**: T6
**Reuses**: `reports/regras.py`
**Requirement**: REL-01, REL-02, REL-03, REL-05, REL-07, REL-10, REL-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O cenário de REL-01 dá R$ 180,00 de despesas no calendário, na pizza e na comparação mensal
- [x] A comparação de 6 meses a partir de março mostra outubro a março, sem repetir
- [x] Receitas pendentes, transferências e ajustes ficam fora dos gráficos
- [x] Nenhum `float(` em valor de dinheiro nessas funções
- [x] Full gate passa
- [x] Test count: 8 testes (mínimo 6)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix: soma as mesmas despesas no calendário, nos gráficos e nas comparações`

---

#### T8: Relatórios avançados

**What**: `get_advanced_charts`: evolução do patrimônio no fim de cada mês, mapa de calor pela hora de Brasília, investimentos mês a mês, monitor de foco e próximo grande gasto pelas regras comuns, projeção com o último dia do mês e contas em `Decimal`.
**Where**: `reports/services.py`
**Depends on**: T7
**Reuses**: `patrimonio`, `hora_em_brasilia`, `dia_no_mes`
**Requirement**: REL-09, REL-10, REL-11, REL-16, REL-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Despesa lançada às 22h de Brasília aparece às 22h no mapa de calor
- [x] A evolução do patrimônio traz um ponto por mês do calendário, pela regra do fim do mês, com a dívida do cartão
- [x] O histórico de investimentos tem um mês do calendário por item
- [x] Projeção para o dia 31 em fevereiro vira 28 ou 29
- [x] Nenhum `float(` em valor de dinheiro em `get_advanced_charts`
- [x] Full gate passa
- [x] Test count: 8 testes (mínimo 7)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix: corrige patrimônio, mapa de calor e projeções dos relatórios avançados`

---

#### T9: PDF com transação sem conta

**What**: A exportação em PDF deixa a conta em branco quando a transação não tem conta.
**Where**: `data_exchange/services.py`
**Depends on**: T8
**Reuses**: `_do_dono`
**Requirement**: REL-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Exportar um período com uma transação sem conta gera o PDF com status 200
- [x] A linha dessa transação tem a conta em branco
- [x] Quick gate passa
- [x] Test count: 2 testes (mínimo 2)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: gera o PDF com transações sem conta`

---

#### T10: Mesmos números em todas as telas

**What**: Teste que monta o cenário do Independent Test de cada história e confere o mesmo resultado no dashboard, na saúde financeira, no calendário, na pizza, na comparação mensal e no orçamento.
**Where**: `tests/relatorios/test_consistencia.py`
**Depends on**: T9
**Reuses**: NONE
**Requirement**: REL-01, REL-06, REL-13, REL-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Despesas, "A pagar", patrimônio e dinheiro guardado batem entre as rotas
- [x] Build gate passa
- [x] Test count: 2 testes (mínimo 2)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `test: confere os mesmos números em todos os relatórios`

---

### Phase 3: Frontend

#### T11: Dashboard com "A pagar" e patrimônio dividido

**What**: O dashboard mostra "A pagar", o patrimônio separado em disponível, reservas, investimentos e faturas em aberto, e as faturas do mês.
**Where**: `src/app/(app)/dashboard/page.tsx`, `src/components/dashboard/`, `src/types/reports.ts`
**Depends on**: None
**Reuses**: `formatarMoeda`
**Requirement**: REL-04, REL-15, REL-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com `payable` 50.00, o dashboard mostra "A pagar" R$ 50,00
- [x] O patrimônio mostra as quatro partes de `net_worth_breakdown`
- [x] Quick gate (frontend) passa
- [x] Test count: 4 testes (mínimo 3)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: mostra o que falta pagar e o patrimônio dividido no dashboard`

---

#### T12: Taxa indisponível e média zero

**What**: A taxa de poupança aparece como "Indisponível" quando `savings_rate` é `null`, e as comparações com média zero mostram "Sem histórico para comparar".
**Where**: `src/app/(app)/relatorios/page.tsx`, componentes de saúde financeira e monitor de foco
**Depends on**: T11
**Reuses**: NONE
**Requirement**: REL-22, REL-23

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `savings_rate: null` mostra "Indisponível", sem "Infinity" nem "NaN"
- [x] Monitor com `average_month` 0.00 mostra "Sem histórico para comparar"
- [x] Quick gate (frontend) passa
- [x] Test count: 5 testes (mínimo 3)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: mostra a taxa indisponível e a falta de histórico em vez de Infinity`

---

#### T13: Erro por bloco nos relatórios

**What**: Cada bloco da tela de relatórios carrega com o próprio estado e mostra o erro com "Tentar de novo" só nele.
**Where**: `src/app/(app)/relatorios/page.tsx`
**Depends on**: T12
**Reuses**: `tratarErro`
**Requirement**: REL-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com a comparação mensal falhando, só esse bloco mostra o erro e os demais carregam
- [x] "Tentar de novo" chama só a rota do bloco
- [x] Build gate (frontend) passa
- [x] Test count: 5 testes (mínimo 3)

**Tests**: unit (frontend)
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix: mostra o erro só no bloco do relatório que falhou`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T10, backend), lote 2 com a fase 3 (T11 a T13, frontend).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Data no relatório e ajuste de saldo | um componente | ✅ Granular |
| T2: Módulo de regras comuns | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T3: Limite do parâmetro months | um componente | ✅ Granular |
| T4: Dashboard | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T5: Saúde financeira e score | um componente | ✅ Granular |
| T6: Gasto dos orçamentos | um componente | ✅ Granular |
| T7: Calendário, gráficos simples, comparação e tags | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T8: Relatórios avançados | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T9: PDF com transação sem conta | um componente | ✅ Granular |
| T10: Mesmos números em todas as telas | um componente | ✅ Granular |
| T11: Dashboard com "A pagar" e patrimônio dividido | um componente | ✅ Granular |
| T12: Taxa indisponível e média zero | um componente | ✅ Granular |
| T13: Erro por bloco nos relatórios | um componente | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | None | sem seta dentro da fase | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | None | sem seta dentro da fase | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Data no relatório e ajuste de saldo | Backend | integration | integration | ✅ OK |
| T2: Módulo de regras comuns | Backend | integration | integration | ✅ OK |
| T3: Limite do parâmetro months | Backend | integration | integration | ✅ OK |
| T4: Dashboard | Backend | integration | integration | ✅ OK |
| T5: Saúde financeira e score | Backend | integration | integration | ✅ OK |
| T6: Gasto dos orçamentos | Backend | integration | integration | ✅ OK |
| T7: Calendário, gráficos simples, comparação e tags | Backend | integration | integration | ✅ OK |
| T8: Relatórios avançados | Backend | integration | integration | ✅ OK |
| T9: PDF com transação sem conta | Backend | integration | integration | ✅ OK |
| T10: Mesmos números em todas as telas | Backend | integration | integration | ✅ OK |
| T11: Dashboard com "A pagar" e patrimônio dividido | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T12: Taxa indisponível e média zero | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T13: Erro por bloco nos relatórios | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
