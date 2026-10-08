# Metas Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/metas/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Valor das metas, vínculo com transações, aportes, resgates, cadastro, histórico, migração e trocos (backend) | integration | Cada AC com status e mensagem exatos e o valor das metas e o saldo livre conferidos depois de cada passo; concorrência com `TransactionTestCase` e threads; migração testada importando o módulo | `tests/metas/test_*.py` | `docker compose exec -T backend python manage.py test tests.metas --noinput` |
| Tela de metas, formulários, histórico e trocos (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/metas/*.test.tsx` | `npx vitest run tests/metas` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 170 erros de lint antigos (MAN-04 e as regras novas do react-hooks): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.metas --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/metas` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Valor das metas

```
T1 → T2
T2 → T3
```

### Phase 2: Aportes e resgates

```
T4 → T5
```

### Phase 3: Cadastro e consulta

```
T6 → T7
```

### Phase 4: Cofrinho de trocos

```
T8 → T9
T9 → T10
```

### Phase 5: Frontend

```
T11 → T12
T12 → T13
T13 → T14
T14 → T15
```

---

## Task Breakdown

### Phase 1: Valor das metas

#### T1: Valor derivado e saldo livre

**What**: Campos novos em `GoalDeposit` (`eh_correcao`, `transacao_saida`, `transacao_entrada`) e em `Goal` (`valor_antes_da_correcao`) com a migração; `goals/valores.py` com `calcular`, `recalcular` sob trava e `saldo_livre`.
**Where**: `goals/models.py`, `goals/migrations/`, `goals/valores.py` (novo)
**Depends on**: None
**Reuses**: o padrão de `accounts/saldo.py`
**Requirement**: META-01, META-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Valor = aportes − resgates, contando registros sem transação e registros com a transferência efetivada; uma transferência pendente não conta
- [x] Registro antigo com só o `transaction_id` é resolvido pelas transações desse `transfer_id`
- [x] Saldo livre = saldo do cofrinho − soma das metas, inclusive as arquivadas
- [x] `recalcular` grava `current_amount` e devolve as metas que ficariam negativas
- [x] Quick gate passa
- [x] Test count: 9 testes (mínimo 6)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: calcula o valor das metas pelos aportes e resgates`

---

#### T2: Vínculo com as transações

**What**: Sai o rateio automático; `goals/vinculo.py` com os signals de `Transaction` que removem, sincronizam ou desligam o registro da meta quando a transferência é excluída ou alterada, recalculam e recusam meta negativa.
**Where**: `goals/vinculo.py` (novo), `goals/signals.py`
**Depends on**: T1
**Reuses**: `goals/valores.py`
**Requirement**: META-03, META-06, META-07, META-08, META-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Uma transferência comum de R$ 200,00 para o cofrinho sobe o saldo livre em R$ 200,00 e não muda nenhuma meta; uma despesa paga pelo cofrinho também só muda o saldo livre
- [x] Excluir a transferência de um aporte de R$ 500,00 deixa a meta em R$ 0,00 na mesma requisição
- [x] Mudar valor ou data da transferência muda o registro da meta igual
- [x] Trocar o destino de um aporte para outra conta remove o registro
- [x] Excluir o aporte depois de um resgate recebe 400 "A meta <nome> ficaria negativa. Desfaça o resgate antes." e nada muda
- [x] Full gate passa
- [x] Test count: 12 testes (mínimo 7)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix: mantém o valor da meta junto da transferência e remove o rateio do cofrinho`

---

#### T3: Correção dos valores gravados

**What**: Migração de dados que recalcula todas as metas e leva as negativas a zero com um registro de correção e o valor de antes; `correction` no serializer e `POST /goals/{id}/dismiss-correction/`; o comando `sync_goals` sai.
**Where**: `goals/migrations/`, `goals/serializers.py`, `goals/views.py`, `goals/management/commands/sync_goals.py`
**Depends on**: T2
**Reuses**: o padrão de `transactions/migrations/0008_corrige_saldos.py`
**Requirement**: META-10, META-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Meta com `current_amount` inflado pelo rateio volta à soma dos registros
- [x] Meta que daria −R$ 50,00 fica em zero, com um registro de correção de R$ 50,00 e `correction: {before: "-50.00", after: "0.00"}`
- [x] Depois de `dismiss-correction`, o aviso não aparece mais
- [x] Banco vazio: a migração não faz nada
- [x] Build gate passa
- [x] Test count: 7 testes (mínimo 5)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix: recalcula as metas gravadas e registra as correções`

---

### Phase 2: Aportes e resgates

#### T4: Aporte e resgate com conta ou saldo livre

**What**: `GoalService.aportar` e `resgatar` com conta (transferência) ou saldo livre (`from_free_balance`, `to_free_balance`), limites, meta arquivada e trava da meta e do cofrinho; os registros ligam as duas pernas da transferência.
**Where**: `goals/services.py`, `goals/views.py`
**Depends on**: None
**Reuses**: `create_transfer`, `goals/valores.py`
**Requirement**: META-12, META-13, META-14, META-15, META-16, META-17, META-18, META-19, META-20, META-21, META-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com R$ 200,00 livres, aporte de R$ 150,00 do saldo livre sobe a meta em R$ 150,00 sem nova transação; outro de R$ 100,00 recebe 400 "O saldo livre do cofrinho é de R$ 50,00."
- [x] Aporte de outra conta cria a transferência e registra só nessa meta; usar o próprio cofrinho como origem é recusado pela SALDO-17
- [x] Resgate acima da meta recebe "A meta tem R$ <valor> para resgatar."; para outra conta acima do cofrinho, "O cofrinho tem só R$ <valor>."
- [x] Resgate para o saldo livre registra sem transferência
- [x] Valor menor que R$ 0,01 e conta de outro usuário recebem 400 no campo
- [x] Meta arquivada recebe "Metas arquivadas não recebem aportes." e ainda permite resgate
- [x] Dois resgates simultâneos de R$ 300,00 numa meta de R$ 500,00: só um passa (teste com threads)
- [x] Test count: 13 testes (mínimo 12)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix: faz aportes e resgates com outra conta ou com o saldo livre do cofrinho`

---

#### T5: Cofrinhos, meta concluída e sugestão mensal

**What**: `GET /api/goals/piggy-banks/` com saldo, soma das metas e saldo livre; status concluída aceitando aportes; sugestão mensal com `hoje()`.
**Where**: `goals/views.py`, `goals/services.py`
**Depends on**: T4
**Reuses**: `saldo_livre`, `core/datas.hoje`
**Requirement**: META-02, META-04, META-23, META-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `piggy-banks` devolve um item por cofrinho com `balance`, `goals_total` e `free_balance` em texto; saldo livre negativo aparece negativo
- [x] Meta que atinge o alvo fica `COMPLETED` e ainda recebe aporte
- [x] Com o relógio às 23h de Brasília do último dia do mês, a sugestão conta os meses a partir do dia de Brasília, com mínimo de 1
- [x] Build gate passa
- [x] Test count: 5 testes (mínimo 5)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: mostra o saldo livre de cada cofrinho e a sugestão mensal pelo dia de Brasília`

---

### Phase 3: Cadastro e consulta

#### T6: Cadastro, troca de cofrinho e exclusão

**What**: `GoalSerializer` aceita só cofrinhos ativos do usuário, valida nome e alvo e recusa a troca de cofrinho com valor; a exclusão recusa meta com valor e informa `piggy_bank_empty`; `deposits` sai da lista.
**Where**: `goals/serializers.py`, `goals/views.py`
**Depends on**: None
**Reuses**: `OwnedPrimaryKeyRelatedField`
**Requirement**: META-25, META-26, META-27, META-28, META-29, META-30, META-31

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Meta sem cofrinho cria um novo; duas metas no mesmo cofrinho aparecem no mesmo item de `piggy-banks`
- [x] Conta corrente como cofrinho recebe 400 no campo `account`; nome vazio e alvo 0 recebem 400 no campo
- [x] Trocar o cofrinho com valor recebe "Resgate o valor da meta antes de trocar o cofrinho."
- [x] Excluir com R$ 10,00 recebe "Resgate o valor da meta antes de excluí-la."; excluir a última meta de um cofrinho zerado devolve `piggy_bank_empty: true`
- [x] A lista de metas não traz `deposits`
- [x] Quick gate passa
- [x] Test count: 9 testes (mínimo 8)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: valida o cofrinho e o cadastro das metas`

---

#### T7: Histórico paginado, trava e exclusão do usuário

**What**: `history` paginado com `PaginacaoPadrao`, do mais recente ao mais antigo, com tipo, valor, data, conta e transação; testes da trava `metas` nas rotas novas e da exclusão definitiva do usuário.
**Where**: `goals/views.py`, `goals/serializers.py`
**Depends on**: T6
**Reuses**: `PaginacaoPadrao`, `RecursoLiberado`
**Requirement**: META-32, META-33, META-34

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Uma meta com 45 registros devolve páginas de 20, com `count` 45, do mais recente ao mais antigo
- [x] Com `metas` fechada, `piggy-banks`, `history` e as rotas de trocos recebem 403 `plan_locked`, e a transferência para o cofrinho continua aceita
- [x] A exclusão definitiva do usuário apaga as metas, os registros e os trocos
- [x] Build gate passa
- [x] Test count: 5 testes (mínimo 5)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix: pagina o histórico da meta`

---

### Phase 4: Cofrinho de trocos

#### T8: Configuração dos trocos

**What**: Modelos `ConfiguracaoDeTrocos` e `Troco` com a migração; `GET` e `PUT /api/goals/spare-change/` para ativar, escolher a meta e desativar; pausa quando a meta está arquivada ou foi excluída.
**Where**: `goals/models.py`, `goals/migrations/`, `goals/trocos.py` (novo), `goals/views.py`
**Depends on**: None
**Reuses**: NONE
**Requirement**: META-35, META-44, META-45

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Ativar grava a meta e a hora da ativação; `GET` devolve `active`, `goal`, `paused`, `pending_total` e `pending_count`
- [x] Meta arquivada ou excluída deixa `paused: true` até escolher outra
- [x] Desativar mantém os trocos pendentes no total
- [x] Quick gate passa
- [x] Test count: 7 testes (mínimo 5)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: guarda a configuração do cofrinho de trocos`

---

#### T9: Troco de cada despesa

**What**: Geração do troco no `post_save` da despesa efetivada, com as condições do design; recálculo ou remoção do troco pendente quando a despesa muda ou é excluída.
**Where**: `goals/trocos.py`, `goals/signals.py`
**Depends on**: T8
**Reuses**: NONE
**Requirement**: META-36, META-41, META-42

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Despesas de R$ 12,30 na conta A e R$ 7,60 na conta B geram trocos de R$ 0,70 e R$ 0,40; R$ 12,00 não gera troco
- [x] Despesa pendente, sem conta, no cofrinho, ajuste de saldo ou anterior à ativação não gera troco
- [x] Editar R$ 12,30 para R$ 12,80 antes do depósito muda o troco para R$ 0,20; excluir remove o troco pendente
- [x] Editar ou excluir despesa com troco depositado não mexe no aporte
- [x] Full gate passa
- [x] Test count: 10 testes (mínimo 8)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: calcula o troco de cada despesa efetivada`

---

#### T10: Depósito dos trocos

**What**: `POST /api/goals/spare-change/deposit/` com trava da configuração, um aporte por conta, trocos marcados como depositados e os de conta excluída descartados.
**Where**: `goals/trocos.py`, `goals/views.py`
**Depends on**: T9
**Reuses**: `GoalService.aportar`
**Requirement**: META-38, META-39, META-40, META-43

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O cenário do Independent Test cria um aporte de R$ 0,70 a partir de A e um de R$ 0,40 a partir de B, e a meta sobe R$ 1,10
- [x] Reenviar o pedido responde 200 com `deposits` vazio
- [x] Dois pedidos simultâneos depositam cada troco uma vez (teste com threads)
- [x] Trocos de conta excluída são descartados e `discarded` informa quantos
- [x] Build gate passa
- [x] Test count: 7 testes (mínimo 6)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: deposita os trocos por conta de origem uma vez só`

---

### Phase 5: Frontend

#### T11: Metas agrupadas por cofrinho

**What**: A tela agrupa as metas por cofrinho com saldo, soma e saldo livre (de `piggy-banks`), mostra o aviso de cofrinho descoberto e perde o texto do rateio.
**Where**: `src/app/(app)/metas/page.tsx`, `src/services/goals.ts`, `src/types/`
**Depends on**: None
**Reuses**: `formatarMoeda`
**Requirement**: META-04, META-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Duas metas no mesmo cofrinho aparecem no mesmo grupo, com saldo, soma e saldo livre
- [x] Saldo livre de −200.00 mostra "O cofrinho <nome> tem R$ 200,00 a menos do que as metas somam."
- [x] O texto que explicava o rateio sai
- [x] Quick gate (frontend) passa
- [x] Test count: 4 testes (mínimo 3)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: agrupa as metas por cofrinho e mostra o saldo livre`

---

#### T12: Aporte e resgate na tela

**What**: Formulários de aporte e resgate com a opção do saldo livre, sem o próprio cofrinho entre as contas, e as mensagens do backend.
**Where**: `src/components/goals/GoalDepositForm.tsx`, `src/components/goals/GoalWithdrawForm.tsx`, `src/services/goals.ts`
**Depends on**: T11
**Reuses**: `MoneyInput`, `tratarErro`
**Requirement**: META-12, META-13, META-14, META-15, META-16, META-17, META-18, META-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Escolher "Saldo livre do cofrinho" envia `from_free_balance: true` sem conta; no resgate, `to_free_balance: true`
- [x] O próprio cofrinho não aparece entre as contas de origem do aporte
- [x] A recusa de saldo livre, de valor da meta e de meta arquivada aparece com a mensagem do backend
- [x] Quick gate (frontend) passa
- [x] Test count: 9 testes (mínimo 4)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: permite aportar e resgatar pelo saldo livre do cofrinho`

---

#### T13: Formulário e exclusão da meta

**What**: O formulário oferece só cofrinhos ativos como cofrinho existente; troca e exclusão mostram a mensagem do backend; excluir a última meta de um cofrinho zerado pergunta se exclui o cofrinho.
**Where**: `src/components/goals/GoalForm.tsx`, `src/app/(app)/metas/page.tsx`
**Depends on**: T12
**Reuses**: `tratarErro`
**Requirement**: META-25, META-26, META-27, META-28, META-29, META-30

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A lista de cofrinhos do formulário tem só contas `PIGGY_BANK` ativas
- [x] Com `piggy_bank_empty: true`, a tela pergunta e, confirmando, chama `DELETE /accounts/{id}/`
- [x] A recusa de exclusão com valor mostra a mensagem do backend
- [x] Quick gate (frontend) passa
- [x] Test count: 6 testes (mínimo 3)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: oferece só cofrinhos e pergunta pelo cofrinho vazio ao excluir a meta`

---

#### T14: Histórico paginado e aviso de correção

**What**: O histórico usa o endpoint paginado com o componente `Paginacao`; a meta com `correction` mostra uma vez o valor de antes e o de depois, com "Entendi" chamando `dismiss-correction`.
**Where**: `src/components/goals/GoalHistory.tsx`, `src/components/goals/GoalDetails.tsx`
**Depends on**: T13
**Reuses**: `Paginacao`, `lerData`
**Requirement**: META-11, META-32

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O histórico pede `page` e mostra total e controles
- [x] Meta com `correction` mostra o aviso; "Entendi" chama `dismiss-correction` e o aviso some
- [x] Quick gate (frontend) passa
- [x] Test count: 4 testes (mínimo 3)

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: pagina o histórico da meta e avisa a correção do valor`

---

#### T15: Cofrinho de trocos na tela

**What**: `SpareChangeBank` usa as rotas de trocos: ativar e desativar, escolher a meta, total e quantidade pendentes, depositar, mostrar descartados e pausado; o cálculo no navegador sai.
**Where**: `src/components/goals/SpareChangeBank.tsx`, `src/services/goals.ts`
**Depends on**: T14
**Reuses**: `formatarMoeda`, `tratarErro`
**Requirement**: META-35, META-37, META-43, META-44, META-45

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A tela mostra `pending_total` e `pending_count` da API, sem buscar transações
- [x] Depositar chama a rota e mostra os aportes e, quando houver, quantos trocos foram descartados
- [x] Com `paused`, a tela pede outra meta; desativar mantém o total pendente
- [x] Build gate (frontend) passa
- [x] Test count: pelo menos 4 testes (real: 6 testes novos em `tests/metas/cofrinho-de-trocos.test.tsx`; suíte do frontend com 299)

**Tests**: unit (frontend)
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix: mostra e deposita os trocos calculados pelo backend`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 a 3 (T1 a T7, backend), lote 2 com as fases 4 e 5 (T8 a T15, trocos no backend e frontend).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Valor derivado e saldo livre | um componente | ✅ Granular |
| T2: Vínculo com as transações | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T3: Correção dos valores gravados | um componente | ✅ Granular |
| T4: Aporte e resgate com conta ou saldo livre | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T5: Cofrinhos, meta concluída e sugestão mensal | um componente | ✅ Granular |
| T6: Cadastro, troca de cofrinho e exclusão | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T7: Histórico paginado, trava e exclusão do usuário | um componente | ✅ Granular |
| T8: Configuração dos trocos | um componente | ✅ Granular |
| T9: Troco de cada despesa | um componente | ✅ Granular |
| T10: Depósito dos trocos | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T11: Metas agrupadas por cofrinho | um componente | ✅ Granular |
| T12: Aporte e resgate na tela | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T13: Formulário e exclusão da meta | um componente | ✅ Granular |
| T14: Histórico paginado e aviso de correção | um componente | ✅ Granular |
| T15: Cofrinho de trocos na tela | um componente | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | None | sem seta dentro da fase | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | None | sem seta dentro da fase | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | None | sem seta dentro da fase | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | None | sem seta dentro da fase | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Valor derivado e saldo livre | Backend | integration | integration | ✅ OK |
| T2: Vínculo com as transações | Backend | integration | integration | ✅ OK |
| T3: Correção dos valores gravados | Backend | integration | integration | ✅ OK |
| T4: Aporte e resgate com conta ou saldo livre | Backend | integration | integration | ✅ OK |
| T5: Cofrinhos, meta concluída e sugestão mensal | Backend | integration | integration | ✅ OK |
| T6: Cadastro, troca de cofrinho e exclusão | Backend | integration | integration | ✅ OK |
| T7: Histórico paginado, trava e exclusão do usuário | Backend | integration | integration | ✅ OK |
| T8: Configuração dos trocos | Backend | integration | integration | ✅ OK |
| T9: Troco de cada despesa | Backend | integration | integration | ✅ OK |
| T10: Depósito dos trocos | Backend | integration | integration | ✅ OK |
| T11: Metas agrupadas por cofrinho | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T12: Aporte e resgate na tela | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T13: Formulário e exclusão da meta | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T14: Histórico paginado e aviso de correção | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T15: Cofrinho de trocos na tela | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
