# Gestão do salário Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/gestao-do-salario/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Plano, cálculo, recebimentos, geração, desfazer e referências (backend) | integration | Cada AC com status, código e mensagem exatos; concorrência com `TransactionTestCase` e duas threads; datas pelo patch de `timezone.now` | `tests/salario/test_*.py` | `docker compose exec -T backend python manage.py test tests.salario --noinput` |
| Página, plano, revisão, desfazer e aviso (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/salario/*.test.tsx` | `npx vitest run tests/salario` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 149 erros de lint antigos: o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.salario --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/salario` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Plano

```
T1 → T2
T2 → T3
```

### Phase 2: Divisão

```
T4 → T5
T5 → T6
T6 → T7
```

### Phase 3: Telas

```
T8 → T9
T9 → T10
T10 → T11
T11 → T12
```

---

## Task Breakdown

### Phase 1: Plano

#### T1: App e modelos da gestão do salário

**What**: App `salario` com `GestaoDoSalario`, `ParteDoPlano`, `DivisaoDoSalario` (restrições únicas da chave e do recebimento ativo) e `ItemDaDivisao`; `Transaction.divisao_do_salario`; os modelos com usuário entram em `MODELOS_DO_USUARIO`.
**Where**: `salario/` (novo), `core/settings.py`, `core/urls.py`, `transactions/models.py`, `transactions/migrations/`, `api/exclusao.py`
**Depends on**: None
**Reuses**: padrão de restrição de `PagamentoDeFatura`
**Requirement**: SALARIO-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] As migrações criam as tabelas e o campo `divisao_do_salario`
- [x] A exclusão definitiva apaga a gestão, o plano e as divisões do usuário, e o teste de completude da LGPD passa
- [x] A limpeza do painel apaga a gestão e as divisões, e o cadastro novo continua igual
- [x] Build gate passa
- [x] Test count: 7 testes

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: cria os modelos do plano e das divisões do salário`

---

#### T2: Modelos da literatura e cálculo da divisão

**What**: `salario/modelos.py` com os três modelos e o Personalizado; `salario/calculo.py` com `dividir`: ordem, fixo e percentual com arredondamento para baixo, ajustes, redução a partir da última parte e itens que não geram transação.
**Where**: `salario/modelos.py` (novo), `salario/calculo.py` (novo)
**Depends on**: T1
**Reuses**: NONE
**Requirement**: SALARIO-02, SALARIO-03, SALARIO-06, SALARIO-26, SALARIO-27, SALARIO-28, SALARIO-30, SALARIO-34

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Os três modelos têm as partes, os percentuais, o destino inicial e a referência da spec; o Personalizado não tem partes
- [x] R$ 3.000,00 com 50/30/20 dá 1.500,00, 900,00 e 600,00, sem sobra
- [x] 33,33% de R$ 1.000,00 dá R$ 333,30, e R$ 666,70 ficam livres
- [x] R$ 1.000,00 com fixos de 700 e 500 reduz a última para 300 e a marca reduzida; fixos de 800, 300 e 200 zeram a última e reduzem a do meio
- [x] Ajuste vale só na divisão; parte na conta do salário, na conta do recebimento ou com zero não gera transação
- [x] Quick gate passa
- [x] Test count: 15 testes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: calcula a divisão do salário pelos modelos e pelo plano`

---

#### T3: API do plano

**What**: Rotas `models/`, `plan/` (GET e PUT) e `simulate/` com `RecursoLiberado('gestao_do_salario')`; categorias de salário com "Salário" e as subcategorias marcadas de início; validações das partes; quanto a meta pede por mês.
**Where**: `salario/views.py`, `salario/serializers.py`, `salario/urls.py`, `core/fields.py`, `tests/permissoes/`, `tests/isolamento/`
**Depends on**: T2
**Reuses**: `OwnedPrimaryKeyRelatedField`, `GoalService.get_progress`, `RecursoLiberado`
**Requirement**: SALARIO-01, SALARIO-04, SALARIO-05, SALARIO-07, SALARIO-08, SALARIO-09, SALARIO-10, SALARIO-11, SALARIO-12, SALARIO-13, SALARIO-14, SALARIO-16, SALARIO-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `GET models/` devolve os quatro modelos com a obra de origem
- [x] Salvar o 50/30/20 com Guardar na meta Viagem e reabrir devolve as partes na mesma ordem; mudar a ordem grava a nova
- [x] Percentuais somando 110% recebem 400 "A soma dos percentuais passa de 100%."; fixo de 0,00 e percentual de 100,01 recebem 400 no campo da parte
- [x] Conta de outro usuário ou inexistente recebe a mesma resposta; cofrinho, conta inativa e meta inativa recebem a mensagem do destino
- [x] Sem configuração, as categorias de salário trazem "Salário" e as subcategorias dela
- [x] Simular R$ 3.000,00 devolve a divisão e não cria transação
- [x] Com o recurso travado, as rotas recebem 403 `plan_locked`; nenhum log leva valores ou nomes
- [x] Full gate passa
- [x] Test count: 20 testes, mais a verificação da trava em `tests/permissoes/test_travas_de_recurso.py`

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: permite montar, salvar e simular o plano de divisão do salário`

---

### Phase 2: Divisão

#### T4: Recebimentos a dividir e revisão

**What**: `GET pending/` com os salários efetivados do mês atual e do anterior sem divisão ativa; `POST divisions/preview/` com os itens, o total, o livre, a data e os ajustes.
**Where**: `salario/divisao.py` (novo), `salario/views.py`
**Depends on**: T3
**Reuses**: `dividir`, `hoje()`
**Requirement**: SALARIO-24, SALARIO-29, SALARIO-30, SALARIO-40

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A lista traz o salário efetivado do mês e o do mês anterior, inclusive importado, e deixa de fora o pendente, o de dois meses atrás e o já dividido
- [x] A revisão mostra origem, destino, valor, data de hoje em Brasília, total e livre
- [x] Ajustes que passam do recebido recebem 400 no campo `adjustments`
- [x] Receita pendente, de outra categoria ou de outro usuário recebe 400 "Escolha um salário recebido para dividir."
- [x] Quick gate passa
- [x] Test count: 11 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: lista os salários a dividir e mostra a revisão da divisão`

---

#### T5: Geração das transações

**What**: `POST divisions/` com trava do recebimento, chave da tentativa, transferências e aportes efetivados com a data de hoje, marca `divisao_do_salario`, divisão e itens gravados, tudo ou nada; `GET divisions/<id>/`.
**Where**: `salario/divisao.py`, `salario/views.py`
**Depends on**: T4
**Reuses**: `create_transfer`, `GoalService.aportar`, idempotência de `accounts/faturas.py`
**Requirement**: SALARIO-32, SALARIO-33, SALARIO-35, SALARIO-36, SALARIO-37, SALARIO-38, SALARIO-39, SALARIO-41, SALARIO-42, SALARIO-43

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Dividir R$ 3.000,00 com Guardar na meta Viagem cria um aporte efetivado de R$ 600,00 com a data de hoje, que entra só em Viagem mesmo com o cofrinho dividido com outra meta
- [x] Parte com destino numa conta cria a transferência; todas as transações levam o id da divisão
- [x] Com uma falha forçada no segundo item, nenhuma transação fica gravada
- [x] O mesmo pedido com a mesma chave devolve a mesma divisão sem criar nada; outro pedido para o mesmo salário recebe 400 "Este salário já foi dividido."
- [x] Dois pedidos simultâneos criam as transações de um só
- [x] Parte sem destino, destino inativo e plano sem transação recebem as mensagens da spec
- [x] Full gate passa
- [x] Test count: 18 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: gera as transferências e os aportes da divisão do salário de uma vez`

---

#### T6: Desfazer a divisão

**What**: `POST divisions/<id>/undo/`: prazo de 7 dias, conferência de cada item e do valor das metas, exclusão das transações uma a uma, `desfeita_em` e recebimento liberado.
**Where**: `salario/divisao.py`, `salario/views.py`
**Depends on**: T5
**Reuses**: sinais de `goals/vinculo.py`
**Requirement**: SALARIO-46, SALARIO-47, SALARIO-48, SALARIO-49, SALARIO-50, SALARIO-51

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Desfazer remove o aporte, e a meta e a conta do salário voltam aos valores de antes; o salário volta à lista a dividir
- [x] Aporte editado recebe 400 dizendo que o aporte em Viagem mudou; transação excluída também recusa
- [x] Meta com valor menor que o aportado recebe 400 com o nome da meta
- [x] No 8º dia, recebe 400 "O prazo para desfazer esta divisão acabou."
- [x] Com uma falha forçada no meio, a divisão continua inteira
- [x] Desfazer de novo recebe "Esta divisão já foi desfeita." sem remover nada
- [x] Full gate passa
- [x] Test count: 12 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: permite desfazer a divisão do salário em até 7 dias`

---

#### T7: Referências do mês e histórico

**What**: `GET references/` com o comprometido no mês (recorrentes pendentes e faturas que vencem) e as médias dos 3 últimos meses completos de salário, despesas por classe e diferença, com os meses usados.
**Where**: `salario/referencias.py` (novo), `salario/views.py`
**Depends on**: T6
**Reuses**: `regras.faturas_do_mes`, `regras.despesas`, `mapa_de_classes`
**Requirement**: SALARIO-52, SALARIO-53, SALARIO-56

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Aluguel recorrente pendente de R$ 1.200,00 e fatura de R$ 450,00 no mês dão R$ 1.650,00 comprometidos
- [x] Essenciais de R$ 1.860,00 em média sobre salário médio de R$ 3.000,00 aparecem na classe Essencial com `reference` ESSENCIAL
- [x] Com um mês completo de histórico, `months_used` é 1
- [x] Build gate passa
- [x] Test count: 6 testes

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: mostra o comprometido no mês e as médias do histórico na gestão do salário`

---

### Phase 3: Telas

#### T8: Página da gestão do salário

**What**: Serviço e tipos; item "Gestão do salário" no menu; página `/salario` com `RecursoBloqueado`, salários a dividir, comprometido no mês e histórico com o aviso de meses.
**Where**: `src/services/salario.ts` (novo), `src/types/salario.ts` (novo), `src/app/(app)/salario/page.tsx` (novo), `src/components/layout/header.tsx`
**Depends on**: T7
**Reuses**: `RecursoBloqueado`, `tratarErro`
**Requirement**: SALARIO-15, SALARIO-16, SALARIO-24, SALARIO-52, SALARIO-53, SALARIO-56

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O menu tem "Gestão do salário"; com o recurso travado, a página mostra o aviso do plano
- [x] A página lista os salários a dividir com o botão de dividir
- [x] Mostra R$ 1.650,00 comprometidos e o aviso "Média de 1 mês" com um mês de histórico
- [x] Quick gate (frontend) passa
- [x] Test count: 7 testes

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: cria a página da gestão do salário com os salários a dividir e o histórico`

---

#### T9: Escolha do modelo e editor do plano

**What**: Escolha entre os quatro modelos com a obra de origem; editor com ordem, regra, destino, categorias de salário, "X% no seu histórico" nas partes com referência e quanto a meta pede por mês; simulação.
**Where**: `src/components/salario/EscolhaDoModelo.tsx` (novo), `src/components/salario/EditorDoPlano.tsx` (novo), `src/app/(app)/salario/page.tsx`
**Depends on**: T8
**Reuses**: `src/lib/dinheiro.ts`
**Requirement**: SALARIO-01, SALARIO-04, SALARIO-05, SALARIO-07, SALARIO-13, SALARIO-14, SALARIO-54, SALARIO-55

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A escolha mostra Pague-se primeiro, 50/30/20, Seis potes e Personalizado com a obra
- [x] Escolher o 50/30/20 enche o editor com as três partes; subir uma parte muda a ordem enviada
- [x] Essenciais mostra "62,0% no seu histórico" com essenciais de 1.860 sobre salário de 3.000
- [x] A parte com a meta Viagem mostra quanto ela pede por mês
- [x] Simular R$ 3.000,00 mostra o valor de cada parte e o livre
- [x] Quick gate (frontend) passa
- [x] Test count: 10 testes

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: permite escolher o modelo e montar o plano de divisão do salário`

---

#### T10: Revisão e geração

**What**: Diálogo da revisão com cada transação, partes reduzidas, ajuste de valor, total e livre; a marcação de confirmação, o botão com a quantidade e o total e a chave da tentativa; o resultado com as transações criadas.
**Where**: `src/components/salario/RevisaoDaDivisao.tsx` (novo), `src/app/(app)/salario/page.tsx`
**Depends on**: T9
**Reuses**: padrão de `invoice-payment-dialog.tsx`
**Requirement**: SALARIO-21, SALARIO-22, SALARIO-29, SALARIO-30, SALARIO-31, SALARIO-44

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O botão fica desabilitado até a marcação e diz "Gerar 1 transação de R$ 600,00"
- [x] Ajustar uma parte recalcula o total e envia o ajuste
- [x] Repetir depois de um erro de rede envia a mesma chave; reabrir gera outra
- [x] Depois da geração, aparecem as transações criadas e "Desfazer divisão"
- [x] `/salario?dividir=<id>` sem plano abre a escolha do modelo; com plano, a revisão
- [x] Quick gate (frontend) passa
- [x] Test count: 8 testes

**Tests**: unit (frontend)
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: revisa e gera as transações da divisão do salário com confirmação`

---

#### T11: Desfazer na tela

**What**: "Desfazer divisão" mostra as transações que serão removidas, pede confirmação e mostra o erro do backend.
**Where**: `src/components/salario/DesfazerDivisao.tsx` (novo)
**Depends on**: T10
**Reuses**: `tratarErro`
**Requirement**: SALARIO-45

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A confirmação lista as transações da divisão
- [ ] Confirmar chama o desfazer e atualiza a lista de salários a dividir
- [ ] O 400 do prazo aparece no toast
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: permite desfazer a divisão do salário pela tela`

---

#### T12: Aviso ao receber o salário

**What**: O formulário de transação e o "Efetivar" passam a transação ao `onSuccess`; receita efetivada numa categoria de salário, com o recurso liberado, abre o aviso com o valor, os três benefícios, "Dividir agora" e "Agora não".
**Where**: `src/components/salario/AvisoDoSalario.tsx` (novo), `src/components/transactions/transaction-form-dialog.tsx`, `src/app/(app)/transacoes/page.tsx`, `src/app/(app)/dashboard/page.tsx`
**Depends on**: T11
**Reuses**: `usePlan`
**Requirement**: SALARIO-19, SALARIO-20, SALARIO-21, SALARIO-23, SALARIO-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Lançar R$ 3.000,00 em Salário efetivada abre o aviso com o valor e os três benefícios
- [ ] Efetivar uma receita pendente de Salário abre o aviso
- [ ] Receita de outra categoria ou pendente não abre; com o recurso travado, não abre
- [ ] "Dividir agora" leva a `/salario?dividir=<id>`; "Agora não" fecha
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 6 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `feat: oferece dividir o salário assim que ele é lançado`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T7), lote 2 com a fase 3 (T8 a T12).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: App e modelos da gestão do salário | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T2: Modelos da literatura e cálculo da divisão | um componente | ✅ Granular |
| T3: API do plano | um componente | ✅ Granular |
| T4: Recebimentos a dividir e revisão | um componente | ✅ Granular |
| T5: Geração das transações | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T6: Desfazer a divisão | um componente | ✅ Granular |
| T7: Referências do mês e histórico | um componente | ✅ Granular |
| T8: Página da gestão do salário | um componente | ✅ Granular |
| T9: Escolha do modelo e editor do plano | um componente | ✅ Granular |
| T10: Revisão e geração | um componente | ✅ Granular |
| T11: Desfazer na tela | um componente | ✅ Granular |
| T12: Aviso ao receber o salário | um componente | ✅ Granular |

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
| T12 | T11 | T11 → T12 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: App e modelos da gestão do salário | Backend | integration | integration | ✅ OK |
| T2: Modelos da literatura e cálculo da divisão | Backend | unit | unit | ✅ OK |
| T3: API do plano | Backend | integration | integration | ✅ OK |
| T4: Recebimentos a dividir e revisão | Backend | integration | integration | ✅ OK |
| T5: Geração das transações | Backend | integration | integration | ✅ OK |
| T6: Desfazer a divisão | Backend | integration | integration | ✅ OK |
| T7: Referências do mês e histórico | Backend | integration | integration | ✅ OK |
| T8: Página da gestão do salário | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T9: Escolha do modelo e editor do plano | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T10: Revisão e geração | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T11: Desfazer na tela | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T12: Aviso ao receber o salário | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
