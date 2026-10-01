# Saldo Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/saldo/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Views, serializers e services que movem dinheiro (backend) | integration | Cada operação: saldo depois de cada passo igual a SALDO-01, cada recusa da spec com status e mensagem exatos, e os edge cases | `tests/saldo/test_*.py` | `docker compose exec -T backend python manage.py test tests.saldo --noinput` |
| Cálculo do saldo, totais, migração e comandos | integration | Todos os ramos; concorrência com `TransactionTestCase` e threads | `tests/saldo/test_*.py` | idem |
| Diálogos e telas (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/saldo/*.test.ts(x)` | `npx vitest run tests/saldo` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 164 erros de lint antigos (MAN-04): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.saldo --noinput` |
| Full | Tarefas de backend que mexem em signals, settings, totais ou migração | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/saldo` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `NEXT_PUBLIC_API_URL=http://build-check-placeholder npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Núcleo do saldo

Data de hoje, cálculo único do saldo, valor positivo e atomicidade.

```
T1 → T2
T2 → T3
T2 → T4
T4 → T5
```

### Phase 2: Endpoint genérico e contas excluídas

```
T6 → T7
T7 → T8
T8 → T9
```

### Phase 3: Transferências

```
T10 → T11
T11 → T12
```

### Phase 4: Séries recorrentes

```
T13 → T14
T14 → T15
```

### Phase 5: Fatura

```
T16 → T17
```

### Phase 6: Totais

```
T18
```

### Phase 7: Ajuste de saldo e dados existentes

```
T19 → T20
T20 → T21
T21 → T22
T29
T30
```

### Phase 8: Frontend

```
T23 → T24
T24 → T25
T25 → T26
```

### Phase 9: Fluxo completo e concorrência

```
T27 → T28
```

---

## Task Breakdown

### Phase 1: Núcleo do saldo

#### T1: Data de hoje no fuso de Brasília

**What**: `core/datas.py` com `hoje()`, a data corrente em `America/Sao_Paulo`.
**Where**: `core/datas.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AD-008 (usada por SALDO-37 e SALDO-40)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_datas.py` confere, com o relógio simulado em 2026-10-01 02:00 UTC, que `hoje()` devolve 2026-09-30
- [x] Quick gate passa
- [x] Test count: pelo menos 2 testes (real: 2 testes novos; suíte 384 → 386)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(core): adiciona a data de hoje no fuso de Brasília`

---

#### T2: Saldo recalculado do razão

**What**: `accounts/saldo.py` com `calcular` e `recalcular` (trava por id), e os signals de saldo de `transactions/signals.py` chamando `recalcular` para a conta antiga e a nova; `AccountService.get_balance` delega para `calcular`.
**Where**: `accounts/saldo.py`
**Depends on**: T1
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-01 a SALDO-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_saldo.py` com uma base de conta de R$ 1.000,00 confere o saldo igual a SALDO-01 depois de criar efetivada, criar pendente, efetivar, voltar a pendente, mudar valor, mudar tipo, mudar de conta e excluir
- [x] Uma transação de outro usuário gravada à força na conta não entra no saldo
- [x] Full gate passa
- [x] Test count: pelo menos 10 testes (real: 15 testes novos; suíte 386 → 401; o setUp de tests/isolamento/test_correcao.py passa a gravar à força o saldo antigo da conta de B)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(accounts): recalcula o saldo a partir das transações efetivadas`

---

#### T3: Saldo inicial e criação da conta

**What**: `accounts/signals.py`: a criação da conta e a mudança do saldo inicial chamam `recalcular`, e a resposta da criação traz o saldo certo.
**Where**: `accounts/signals.py`
**Depends on**: T2
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-43

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_saldo_inicial.py` confere que mudar o saldo inicial de 1.000,00 para 1.200,00 sobe o saldo em 200,00, com transações já lançadas
- [x] A resposta do `POST /api/accounts/` traz `balance` igual ao saldo inicial
- [x] Quick gate passa
- [x] Test count: pelo menos 2 testes (real: 3 testes novos; suíte 401 → 404)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(accounts): recalcula o saldo ao mudar o saldo inicial`

---

#### T4: Valor positivo com até duas casas

**What**: `core/valores.py` com `validar_valor_positivo`, usado no `amount` dos serializers de transação, transferência, compra no cartão e pagamento de fatura, e no aporte e resgate de meta.
**Where**: `core/valores.py`
**Depends on**: T2
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_valor.py` confere 400 no campo `amount` para 0, -10 e 100.123 em cada uma das operações, e que 100.1 é aceito
- [x] Nenhum saldo muda nas recusas
- [x] Quick gate passa
- [x] Test count: pelo menos 8 testes (real: 12 testes novos; suíte 404 → 416)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(core): recusa valores zerados, negativos ou com mais de duas casas`

---

#### T5: Operações atômicas

**What**: `ATOMIC_REQUESTS` nas settings e `atomic` nos services que movem dinheiro (transferência, compra no cartão, pagamento e estorno, aporte e resgate).
**Where**: `core/settings.py`
**Depends on**: T4
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_atomicidade.py` força uma falha depois da primeira perna de uma transferência e no meio de um pagamento de fatura e confere que nenhuma transação nem saldo mudou
- [x] Full gate passa
- [x] Test count: pelo menos 3 testes (real: 8 testes novos; suíte 416 → 424; as rotas com limite de tentativas e o health ficam fora do ATOMIC_REQUESTS)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(core): desfaz a operação inteira quando uma etapa falha`

---

### Phase 2: Endpoint genérico e contas excluídas

#### T6: Tipos do endpoint genérico

**What**: `TransactionSerializer`: criação só de `INCOME` e `EXPENSE`; edição de tipo só entre esses dois; `CREDIT_CARD` não vai para `COMPLETED` fora do pagamento da fatura.
**Where**: `transactions/serializers.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-18, SALDO-19, SALDO-46

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_tipos.py` confere 400 em `type` na criação de cada um dos quatro tipos especiais e na troca de tipo de/para eles
- [x] Efetivar uma compra no cartão pela lista recebe 400, e o saldo não muda
- [x] Criar e editar receita e despesa continua funcionando
- [x] Quick gate passa
- [x] Test count: pelo menos 8 testes (real: 13 testes novos; suíte 424 → 437)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): restringe os tipos do endpoint genérico`

---

#### T7: Conta excluída fora das operações novas

**What**: Os campos de conta da transação, da transferência, do pagamento de fatura e do aporte e resgate só aceitam contas ativas.
**Where**: `transactions/serializers.py`
**Depends on**: T6
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-35

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_conta_excluida.py` confere 400 ao criar transação, transferência (origem e destino), pagamento de fatura e aporte com conta excluída
- [x] Quick gate passa
- [x] Test count: pelo menos 5 testes (real: 7 testes novos; suíte 437 → 444)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): recusa operações novas em conta excluída`

---

#### T8: Histórico da conta excluída só para leitura

**What**: Editar ou excluir uma transação de conta excluída, ou uma transferência com uma perna em conta excluída, recebe 400 com a mensagem do design.
**Where**: `transactions/views.py`
**Depends on**: T7
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-36

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_conta_excluida.py` confere 400 em PATCH, PUT e DELETE de uma transação e de uma transferência ligadas a conta excluída, sem mudar nada
- [x] Quick gate passa
- [x] Test count: pelo menos 4 testes (real: 8 testes novos; suíte 444 → 452)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): mantém o histórico da conta excluída só para leitura`

---

#### T9: Exclusão de conta

**What**: `AccountViewSet.destroy` recusa saldo diferente de zero e transações pendentes com as mensagens da spec; `is_active` vira somente leitura no serializer.
**Where**: `accounts/views.py`
**Depends on**: T8
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-32, SALDO-33, SALDO-34

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_exclusao_de_conta.py` confere 400 com saldo positivo, com saldo negativo e com pendentes, com as mensagens exatas
- [x] Com saldo zero e sem pendentes, a conta sai da lista e as transações efetivadas continuam no histórico
- [x] PATCH com `is_active: false` não exclui a conta
- [x] Build gate passa
- [x] Test count: pelo menos 5 testes (real: 5 testes novos; suíte 452 → 457)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(accounts): exige saldo zero e nenhuma pendente para excluir a conta`

---

### Phase 3: Transferências

#### T10: Criação de transferência

**What**: `create_transfer`: origem diferente do destino, as duas pernas no mesmo `atomic` e com o mesmo status, e a descrição enviada.
**Where**: `transactions/services.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-11, SALDO-12, SALDO-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_transferencia.py` confere a saída na origem, a entrada no destino e a soma das contas igual antes e depois
- [x] Origem igual ao destino recebe 400 com a mensagem do design
- [x] Quick gate passa
- [x] Test count: pelo menos 4 testes (real: 5 testes novos; suíte 457 → 462)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): valida e cria as duas pernas da transferência juntas`

---

#### T11: Edição de transferência

**What**: Serviço `editar_transferencia` usado pelo `TransactionSerializer.update`: valor, data e status nas duas pernas, troca da conta da perna editada e da outra, tipo imutável; o signal `sync_transfer_update` sai.
**Where**: `transactions/serializers.py`
**Depends on**: T10
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-13, SALDO-14, SALDO-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_transferencia.py` transfere R$ 100,00 de A para B, muda o valor para R$ 150,00, troca o destino para C, troca a origem e muda o status, conferindo A, B e C por SALDO-01 e a soma total em cada passo
- [x] Mudar o tipo de uma perna recebe 400
- [x] Quick gate passa
- [x] Test count: pelo menos 6 testes (real: 7 testes novos; suíte 462 → 469)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): mantém as duas pernas da transferência iguais na edição`

---

#### T12: Exclusão de transferência

**What**: A exclusão de uma perna apaga as duas e desfaz o efeito nas duas contas.
**Where**: `transactions/signals.py`
**Depends on**: T11
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_transferencia.py` exclui a perna de saída e depois, noutra transferência, a de entrada, conferindo as duas pernas apagadas e os saldos por SALDO-01
- [x] Build gate passa
- [x] Test count: pelo menos 2 testes (real: 2 testes novos; suíte 469 → 471)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `test(saldo): cobre a exclusão de transferência`

---

### Phase 4: Séries recorrentes

#### T13: Ocorrências geradas pendentes

**What**: Na criação de uma série, a primeira ocorrência segue o status enviado e as geradas nascem `PENDING`, inclusive as receitas.
**Where**: `transactions/serializers.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_series.py` cria um salário de R$ 5.000,00 com a primeira efetivada: o saldo sobe exatamente R$ 5.000,00 e as 11 seguintes estão pendentes
- [x] Com a primeira pendente, o saldo não muda
- [x] Quick gate passa
- [x] Test count: pelo menos 3 testes (real: 3 testes novos; suíte 471 → 474)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): gera as ocorrências da série como pendentes`

---

#### T14: Alterar todas as ocorrências

**What**: `bulk_update` aplica descrição, valor, categoria, conta e tipo só às pendentes da série e ao modelo dela, com validação de conta ativa, categoria do usuário e tipo, e recalcula as contas.
**Where**: `transactions/views.py`
**Depends on**: T13
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_series.py` efetiva a segunda ocorrência, altera todas para R$ 5.500,00 e outra conta, e confere que só as pendentes mudaram e que os saldos batem com SALDO-01
- [x] Conta excluída, categoria de outro usuário e tipo especial recebem 400
- [x] Quick gate passa
- [x] Test count: pelo menos 5 testes (real: 10 testes novos; suíte 474 → 484)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): altera só as ocorrências pendentes da série`

---

#### T15: Excluir a série

**What**: `bulk_delete` por série apaga só as pendentes e marca a série como inativa.
**Where**: `transactions/views.py`
**Depends on**: T14
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_series.py` confere que as efetivadas continuam, as pendentes somem, `is_active` da série fica falso e o saldo não muda
- [x] Build gate passa
- [x] Test count: pelo menos 2 testes (real: 2 testes novos; suíte 484 → 486)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(transactions): exclui só as ocorrências pendentes da série`

---

### Phase 5: Fatura

#### T16: Pagamento de fatura sob trava

**What**: `pay_invoice` em `atomic` com `select_for_update` na fatura; fatura já paga recebe 400 com "Fatura já está paga.".
**Where**: `accounts/services.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-23, SALDO-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_fatura.py` paga uma fatura de R$ 1.000,00 de uma conta com R$ 3.000,00 e confere R$ 2.000,00
- [x] Pagar de novo recebe 400 com a mensagem exata, sem segundo débito
- [x] Quick gate passa
- [x] Test count: pelo menos 3 testes (real: 3 testes novos; suíte 486 → 489)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(accounts): paga a fatura uma vez só e debita o valor exato`

---

#### T17: Estorno de fatura

**What**: `unpay_invoice` em `atomic`: recusa fatura não paga, volta as compras pagas a pendentes sem conta e sem data de pagamento, e recalcula a conta de pagamento.
**Where**: `accounts/services.py`
**Depends on**: T16
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-24, SALDO-25, SALDO-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_fatura.py` paga, estorna (volta a R$ 3.000,00) e paga de novo (R$ 2.000,00)
- [x] O estorno de um pagamento parcial devolve só o valor pago
- [x] Estornar fatura não paga recebe 400 sem mudar saldo
- [x] Build gate passa
- [x] Test count: pelo menos 4 testes (real: 5 testes novos; suíte 489 → 494)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(accounts): devolve o valor pago no estorno da fatura`

---

### Phase 6: Totais

#### T18: Totais com as contas ativas

**What**: `reports/services.py`: saldo total, patrimônio, saldo em contas, investimentos e as estatísticas do admin somam o `balance` das contas ativas.
**Where**: `reports/services.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-28, SALDO-29, SALDO-30, SALDO-31

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_totais.py` com uma corrente de R$ 1.000,00, uma de investimento de R$ 500,00 e uma excluída com R$ 300,00 confere "Saldo em Contas" 1.000,00, saldo total 1.500,00, investimentos 500,00 e o total do admin 1.500,00
- [x] Cada total usa o mesmo valor da lista de contas
- [x] Full gate passa
- [x] Test count: pelo menos 4 testes (real: 5 testes novos; suíte 494 → 499)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(reports): soma nos totais só o saldo das contas ativas`

---

### Phase 7: Ajuste de saldo e dados existentes

#### T19: Ajuste de saldo

**What**: Rota `POST /api/accounts/{id}/adjust-balance/` com `new_balance`: diferença em decimal, transação efetivada com a data de `hoje()`, nenhuma transação quando não há diferença.
**Where**: `accounts/views.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-40, SALDO-41, SALDO-42

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_ajuste.py` ajusta de 1.000,10 para 999,90 e confere uma saída de 0,20 com a data de hoje e o saldo 999,90
- [x] Ajuste para cima vira entrada; ajuste para negativo é permitido; mesmo saldo não cria transação
- [x] Conta excluída recebe 400
- [x] Quick gate passa
- [x] Test count: pelo menos 5 testes (real: 9 testes novos; suíte 499 → 508)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(accounts): adiciona o ajuste de saldo pelo valor final`

---

#### T20: cleanup_db sem apagar histórico

**What**: `cleanup_db` deixa de apagar contas excluídas com transações e perde a opção `--all-transactions`.
**Where**: `accounts/management/commands/cleanup_db.py`
**Depends on**: T19
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-47

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_cleanup.py` roda o comando e confere o histórico da conta excluída e o saldo das contas ativas iguais aos de antes
- [x] Quick gate passa
- [x] Test count: pelo menos 2 testes (real: 4 testes novos; suíte 508 → 512)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(accounts): impede o cleanup_db de apagar histórico e mudar saldos`

---

#### T21: Migração de correção dos saldos

**What**: `transactions/migrations/0008_corrige_saldos.py`: ocorrências de série efetivadas com data depois de hoje voltam a pendentes (menos a primeira de cada série), e o saldo de todas as contas é recalculado.
**Where**: `transactions/migrations/0008_corrige_saldos.py`
**Depends on**: T20
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-37, SALDO-38

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_migracao.py` chama a função da migração sobre uma série com a primeira e duas futuras efetivadas e saldos gravados errados, e confere as futuras pendentes, a primeira intacta e os saldos iguais a SALDO-01
- [x] `makemigrations --check` sem mudanças
- [x] Full gate passa
- [x] Test count: pelo menos 3 testes (real: 5 testes novos; suíte 512 → 517)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(transactions): corrige ocorrências futuras efetivadas e recalcula os saldos`

---

#### T22: Comando check_saldos

**What**: `python manage.py check_saldos` lista cada conta com saldo diferente de SALDO-01 (id, exibido e calculado) e o total.
**Where**: `accounts/management/commands/check_saldos.py`
**Depends on**: T21
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/saldo/test_check_saldos.py` grava à força um saldo errado e confere a linha com o id e os dois valores, sem nomes, e o total; sem divergência, o total é zero
- [x] Build gate passa
- [x] Test count: pelo menos 2 testes (real: 2 testes novos; suíte 517 → 519)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat(accounts): adiciona o comando que confere os saldos`

---

#### T29: Compra no cartão com a conta do cartão excluída

**What**: A compra no cartão é recusada com 400 e `{"detail": "Conta não encontrada."}` quando a conta de pagamento do cartão (`card.account`) está excluída. Hoje ela cria uma compra pendente numa conta excluída. A guarda fica em `create_credit_card_expense`, que a rota `credit-card-expense` chama depois do `CreditCardExpenseSerializer`.
**Where**: `transactions/services.py`
**Depends on**: None
**Reuses**: `CONTA_NAO_ENCONTRADA` de `core/fields.py`
**Requirement**: SALDO-35

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/saldo/test_conta_excluida.py` cria uma compra pela rota com a conta do cartão excluída e recebe 400 com "Conta não encontrada.", sem nenhuma transação nova e sem mudar saldo
- [ ] O service recusa a mesma compra chamado direto
- [ ] Quick gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix(transactions): recusa compra no cartão com a conta do cartão excluída`

---

#### T30: Transferência recusa conta excluída no service

**What**: `TransactionService.create_transfer` recusa conta excluída na origem ou no destino com 400 e `{"detail": "Conta não encontrada."}`, como guarda do service. Aporte e resgate de meta chamam esse service, então uma meta cujo cofrinho foi excluído não recebe nem devolve dinheiro; as views de meta já repassam o `ValidationError` do DRF como 400.
**Where**: `transactions/services.py`
**Depends on**: None
**Reuses**: `CONTA_NAO_ENCONTRADA` de `core/fields.py`
**Requirement**: SALDO-35

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/saldo/test_conta_excluida.py` chama `create_transfer` com origem excluída e com destino excluído e confere o 400 sem nenhuma perna gravada
- [ ] Aporte e resgate de uma meta com o cofrinho excluído recebem 400 com "Conta não encontrada.", sem mudar saldo nem a meta
- [ ] Build gate passa
- [ ] Test count: pelo menos 4 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix(transactions): recusa transferência com conta excluída no service`

---

### Phase 8: Frontend

#### T23: Ajuste de saldo pelo valor final

**What**: `balance-adjustment-dialog.tsx` chama `POST /accounts/{id}/adjust-balance/` com o novo saldo em texto decimal.
**Where**: `fluxar-frontend/src/components/accounts/balance-adjustment-dialog.tsx`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-40, SALDO-41

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/saldo/ajuste-de-saldo.test.tsx` confere a chamada com `{ new_balance: "999.90" }` para um saldo de 1.000,10 ajustado para 999,90, sem criar transação pelo endpoint genérico
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): ajusta o saldo pelo valor final, sem conta em ponto flutuante`

---

#### T24: Pagamento de fatura exige a fatura

**What**: `invoice-payment-dialog.tsx` exige uma fatura e remove o caminho que criava `INVOICE_PAYMENT` pelo endpoint genérico.
**Where**: `fluxar-frontend/src/components/transactions/invoice-payment-dialog.tsx`
**Depends on**: T23
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/saldo/pagamento-de-fatura.test.tsx` confere que, sem fatura, o envio fica bloqueado e nada chama `/transactions/`, e que com fatura chama `/invoices/{id}/pay/`
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): paga fatura só com a fatura escolhida`

---

#### T25: Edição de transferência

**What**: `transfer-form-dialog.tsx` envia na edição `account`, `target_account_id`, `amount`, `date` e `description`.
**Where**: `fluxar-frontend/src/components/transactions/transfer-form-dialog.tsx`
**Depends on**: T24
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-13, SALDO-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/saldo/edicao-de-transferencia.test.tsx` confere o corpo da edição com os cinco campos
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 1 teste

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): envia a conta certa na edição da transferência`

---

#### T26: Exclusão de conta com a mensagem do backend

**What**: `contas/page.tsx` mostra a mensagem do backend quando a exclusão é recusada.
**Where**: `fluxar-frontend/src/app/(app)/contas/page.tsx`
**Depends on**: T25
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-32, SALDO-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/saldo/exclusao-de-conta.test.tsx` confere o aviso com a mensagem de SALDO-32 vinda do backend
- [ ] Build gate do frontend passa
- [ ] Test count: pelo menos 1 teste

**Tests**: unit (frontend)
**Gate**: build (frontend)

**Commit**: `fix(frontend): mostra por que a conta não pode ser excluída`

---

### Phase 9: Fluxo completo e concorrência

#### T27: Sequência de operações com o saldo conferido

**What**: `tests/saldo/test_fluxo_completo.py`: transações avulsas, transferências, série, fatura, ajuste e exclusão de conta pela API, conferindo todas as contas por SALDO-01 depois de cada passo.
**Where**: `tests/saldo/test_fluxo_completo.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: Success Criteria

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O teste percorre todas as operações sem passo manual e confere cada conta e os totais depois de cada passo
- [ ] Full gate passa
- [ ] Test count: suíte cresce em pelo menos 1 teste

**Tests**: integration
**Gate**: full

**Commit**: `test(saldo): confere o saldo em toda a sequência de operações`

---

#### T28: Operações simultâneas

**What**: `tests/saldo/test_concorrencia.py` com `TransactionTestCase` e threads: 20 criações de R$ 10,00 na mesma conta e duas efetivações da mesma pendente.
**Where**: `tests/saldo/test_concorrencia.py`
**Depends on**: T27
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SALDO-44, SALDO-45

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O saldo final bate com SALDO-01 nos dois cenários, e a efetivação dupla conta uma vez
- [ ] Dois pagamentos simultâneos da mesma fatura debitam uma vez (SALDO-26)
- [ ] Build gate passa
- [ ] Test count: pelo menos 3 testes

**Tests**: integration
**Gate**: build

**Commit**: `test(saldo): cobre operações simultâneas na mesma conta`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9
```

Execution is strictly sequential - there is no intra-phase parallelism.

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Data de hoje no fuso de Brasília | 1 arquivo | ✅ Granular |
| T2: Saldo recalculado do razão | 1 módulo e os signals | ⚠️ Coeso |
| T3: Saldo inicial e criação da conta | 1 arquivo | ✅ Granular |
| T4: Valor positivo com até duas casas | 1 validador e o uso em 5 lugares | ⚠️ Coeso |
| T5: Operações atômicas | settings e os services | ⚠️ Coeso |
| T6: Tipos do endpoint genérico | 1 arquivo | ✅ Granular |
| T7: Conta excluída fora das operações novas | querysets de conta em 4 lugares | ⚠️ Coeso |
| T8: Histórico da conta excluída só para leitura | 1 arquivo | ✅ Granular |
| T9: Exclusão de conta | 1 arquivo | ✅ Granular |
| T10: Criação de transferência | 1 arquivo | ✅ Granular |
| T11: Edição de transferência | 1 serviço e o uso no serializer | ⚠️ Coeso |
| T12: Exclusão de transferência | 1 arquivo | ✅ Granular |
| T13: Ocorrências geradas pendentes | 1 arquivo | ✅ Granular |
| T14: Alterar todas as ocorrências | 1 arquivo | ✅ Granular |
| T15: Excluir a série | 1 arquivo | ✅ Granular |
| T16: Pagamento de fatura sob trava | 1 arquivo | ✅ Granular |
| T17: Estorno de fatura | 1 arquivo | ✅ Granular |
| T18: Totais com as contas ativas | 5 totais no mesmo arquivo | ⚠️ Coeso |
| T19: Ajuste de saldo | 1 arquivo | ✅ Granular |
| T20: cleanup_db sem apagar histórico | 1 arquivo | ✅ Granular |
| T21: Migração de correção dos saldos | 1 arquivo | ✅ Granular |
| T22: Comando check_saldos | 1 arquivo | ✅ Granular |
| T29: Compra no cartão com a conta do cartão excluída | 1 arquivo | ✅ Granular |
| T30: Transferência recusa conta excluída no service | 1 arquivo | ✅ Granular |
| T23: Ajuste de saldo pelo valor final | 1 arquivo | ✅ Granular |
| T24: Pagamento de fatura exige a fatura | 1 arquivo | ✅ Granular |
| T25: Edição de transferência | 1 arquivo | ✅ Granular |
| T26: Exclusão de conta com a mensagem do backend | 1 arquivo | ✅ Granular |
| T27: Sequência de operações com o saldo conferido | 1 arquivo | ✅ Granular |
| T28: Operações simultâneas | 1 arquivo | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T2 | T2 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | None | sem seta dentro da fase | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | None | sem seta dentro da fase | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | None | sem seta dentro da fase | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |
| T16 | None | sem seta dentro da fase | ✅ Match |
| T17 | T16 | T16 → T17 | ✅ Match |
| T18 | None | sem seta dentro da fase | ✅ Match |
| T19 | None | sem seta dentro da fase | ✅ Match |
| T20 | T19 | T19 → T20 | ✅ Match |
| T21 | T20 | T20 → T21 | ✅ Match |
| T22 | T21 | T21 → T22 | ✅ Match |
| T29 | None | sem seta dentro da fase | ✅ Match |
| T30 | None | sem seta dentro da fase | ✅ Match |
| T23 | None | sem seta dentro da fase | ✅ Match |
| T24 | T23 | T23 → T24 | ✅ Match |
| T25 | T24 | T24 → T25 | ✅ Match |
| T26 | T25 | T25 → T26 | ✅ Match |
| T27 | None | sem seta dentro da fase | ✅ Match |
| T28 | T27 | T27 → T28 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Data de hoje no fuso de Brasília | Backend | integration | integration | ✅ OK |
| T2: Saldo recalculado do razão | Backend | integration | integration | ✅ OK |
| T3: Saldo inicial e criação da conta | Backend | integration | integration | ✅ OK |
| T4: Valor positivo com até duas casas | Backend | integration | integration | ✅ OK |
| T5: Operações atômicas | Backend | integration | integration | ✅ OK |
| T6: Tipos do endpoint genérico | Backend | integration | integration | ✅ OK |
| T7: Conta excluída fora das operações novas | Backend | integration | integration | ✅ OK |
| T8: Histórico da conta excluída só para leitura | Backend | integration | integration | ✅ OK |
| T9: Exclusão de conta | Backend | integration | integration | ✅ OK |
| T10: Criação de transferência | Backend | integration | integration | ✅ OK |
| T11: Edição de transferência | Backend | integration | integration | ✅ OK |
| T12: Exclusão de transferência | Backend | integration | integration | ✅ OK |
| T13: Ocorrências geradas pendentes | Backend | integration | integration | ✅ OK |
| T14: Alterar todas as ocorrências | Backend | integration | integration | ✅ OK |
| T15: Excluir a série | Backend | integration | integration | ✅ OK |
| T16: Pagamento de fatura sob trava | Backend | integration | integration | ✅ OK |
| T17: Estorno de fatura | Backend | integration | integration | ✅ OK |
| T18: Totais com as contas ativas | Backend | integration | integration | ✅ OK |
| T19: Ajuste de saldo | Backend | integration | integration | ✅ OK |
| T20: cleanup_db sem apagar histórico | Backend | integration | integration | ✅ OK |
| T21: Migração de correção dos saldos | Backend | integration | integration | ✅ OK |
| T22: Comando check_saldos | Backend | integration | integration | ✅ OK |
| T29: Compra no cartão com a conta do cartão excluída | Backend | integration | integration | ✅ OK |
| T30: Transferência recusa conta excluída no service | Backend | integration | integration | ✅ OK |
| T23: Ajuste de saldo pelo valor final | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T24: Pagamento de fatura exige a fatura | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T25: Edição de transferência | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T26: Exclusão de conta com a mensagem do backend | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T27: Sequência de operações com o saldo conferido | Backend | integration | integration | ✅ OK |
| T28: Operações simultâneas | Backend | integration | integration | ✅ OK |
