# Faturas Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/faturas/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Funções de data da fatura (backend) | unit | Todas as combinações de dias 1 a 31 e todos os meses de 2024 a 2027 | `tests/faturas/test_datas.py` | `docker compose exec -T backend python manage.py test tests.faturas --noinput` |
| Services, views, serializers e signals da fatura (backend) | integration | Cada AC com status e mensagem exatos, os edge cases da spec e os totais depois de cada passo | `tests/faturas/test_*.py` | idem |
| Concorrência e migração (backend) | integration | Threads com `TransactionTestCase`; migração testada importando o módulo, como `tests/saldo/test_migracao.py` | `tests/faturas/test_*.py` | idem |
| Diálogos e telas (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/faturas/*.test.ts(x)` | `npx vitest run tests/faturas` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 160 erros de lint antigos (MAN-04): o gate confere que não aparecem erros novos. Toda tarefa de backend que muda comportamento roda também `tests.isolamento` (gate full).

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.faturas --noinput` |
| Full | Tarefas que mexem em signals, serializers compartilhados, relatórios ou migração | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/faturas` (em `fluxar-frontend`) |
| Build (frontend) | Fim da fase de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Datas e faturas

```
T1 → T2
T2 → T3
T2 → T4
```

### Phase 2: Compras e parcelas

```
T5 → T6
T6 → T7
T7 → T8
T8 → T9
```

### Phase 3: Pagamento e estorno

```
T10 → T11
T11 → T12
T12 → T13
T13 → T14
T14 → T15
```

### Phase 4: Dados existentes e ciclo completo

```
T16 → T17
```

### Phase 5: Frontend

```
T18 → T19
T19 → T20
T20 → T21
T21 → T22
```

---

## Task Breakdown

### Phase 1: Datas e faturas

#### T1: Funções de data da fatura

**What**: Camada sem banco de `accounts/faturas.py`: `dia_no_mes`, `datas_da_fatura`, `mes_da_fatura` e `mes_seguinte`.
**Where**: `accounts/faturas.py` (novo)
**Depends on**: None
**Reuses**: a regra de `TransactionService._get_or_create_invoice` para o último dia do mês
**Requirement**: FATURA-01, FATURA-02, FATURA-03, FATURA-04, FATURA-10, FATURA-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/faturas/test_datas.py` percorre todos os pares de fechamento e vencimento de 1 a 31 e todos os meses de 2024 a 2027 sem erro, conferindo cada data por FATURA-01 a FATURA-04 (inclui 29/02/2024 e 28/02/2025)
- [x] O dia ajustado não se acumula: fechamento no dia 31 cai em 30/04 e volta a 31/05
- [x] Compra em 30/04 com fechamento no dia 31 vai para a fatura seguinte; compra na véspera do fechamento fica na do mês
- [x] Quick gate passa
- [x] Test count: pelo menos 6 testes (real: 9 testes novos; suíte 529 → 538)

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(faturas): calcula fechamento e vencimento em qualquer mês`

---

#### T2: Fatura de cada compra e primeira fatura não paga

**What**: `obter_fatura`, `fatura_da_compra`, `primeira_nao_paga`, `alocar_parcelas`, `dividir_valor` e `colocar`; `_get_or_create_invoice` passa a delegar a `obter_fatura` e perde o `print`.
**Where**: `accounts/faturas.py`, `transactions/services.py`
**Depends on**: T1
**Reuses**: `CreditCardInvoice.objects.get_or_create`
**Requirement**: FATURA-07, FATURA-12, FATURA-13, FATURA-15, FATURA-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Fatura existente mantém as datas depois de mudar os dias do cartão; a criada depois usa os dias novos
- [x] Compra que cairia numa fatura paga vai para a primeira não paga seguinte, criada se faltar
- [x] Fechamento no dia 30, vencimento no dia 7 e compra em 4x em 30/01/2026: faturas de março, abril, maio e junho de 2026
- [x] R$ 100,00 em 3x dá R$ 33,34, R$ 33,33 e R$ 33,33
- [x] Quick gate passa
- [x] Test count: pelo menos 7 testes (real: 12 testes novos; suíte 538 → 550)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(faturas): coloca cada parcela numa fatura não paga e consecutiva`

---

#### T3: Status exibido, próximo vencimento e dias do cartão

**What**: `status_exibido` e `proximo_vencimento`; `CreditCardInvoiceSerializer.status` e `CreditCardSerializer.next_due_date` passam a usá-los; `calculate_due_date` e `get_next_due_date` saem; o dashboard usa `fatura_da_compra` sem criar fatura.
**Where**: `accounts/faturas.py`, `accounts/serializers.py`, `accounts/services.py`, `reports/services.py`
**Depends on**: T2
**Reuses**: `core/datas.py` (`hoje`)
**Requirement**: FATURA-05, FATURA-06, FATURA-08, FATURA-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Fatura não paga aparece aberta antes do fechamento e fechada no dia do fechamento e depois, com `hoje()` simulado
- [ ] Próximo vencimento: o deste mês antes dele, o do mês seguinte depois dele, e o último dia do mês quando o dia não existe
- [ ] Dashboard de um cartão com vencimento no dia 31 responde 200 em fevereiro (FIN-05)
- [ ] Dia de fechamento ou de vencimento 0 ou 32 recebe 400 no cadastro e na edição
- [ ] Full gate passa
- [ ] Test count: pelo menos 7 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix(faturas): mostra o status e o próximo vencimento pela data de hoje`

---

#### T4: Limite disponível com uma fórmula

**What**: `limite_disponivel` usado pelo `CreditCardSerializer` e pelo dashboard.
**Where**: `accounts/faturas.py`, `accounts/services.py`, `reports/services.py`
**Depends on**: T2
**Reuses**: a soma de `CreditCardService.get_invoice_data`
**Requirement**: FATURA-42

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Cartão de R$ 5.000,00 com R$ 1.200,00 em compras pendentes em duas faturas: tela do cartão e dashboard mostram R$ 3.800,00
- [ ] Os dois valores continuam iguais depois de um pagamento parcial
- [ ] Build gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix(faturas): calcula o limite disponível igual no cartão e no dashboard`

---

### Phase 2: Compras e parcelas

#### T5: Data da compra

**What**: Campo `Transaction.purchase_date` com a migração `transactions/0009`; `TransactionSerializer` expõe `purchase_date`.
**Where**: `transactions/models.py`, `transactions/migrations/`, `transactions/serializers.py`
**Depends on**: None
**Reuses**: NONE
**Requirement**: FATURA-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A transação devolve `purchase_date`, nulo para os tipos que não são compra no cartão
- [ ] `purchase_date` enviado numa receita ou despesa é ignorado
- [ ] Full gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat(transactions): guarda a data real da compra no cartão`

---

#### T6: Criação da compra no cartão

**What**: `create_credit_card_expense` usa `alocar_parcelas`, `dividir_valor` e `colocar`, e grava `purchase_date`; `CreditCardExpenseSerializer` recusa cartão excluído.
**Where**: `transactions/services.py`, `transactions/serializers.py`
**Depends on**: T5
**Reuses**: as funções da T2
**Requirement**: FATURA-12, FATURA-13, FATURA-14, FATURA-15, FATURA-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O cenário do Independent Test (R$ 100,00 em 4x em 30/01/2026) cria uma parcela por fatura, de março a junho, todas com `purchase_date` 30/01/2026 e `date` igual ao vencimento da fatura
- [ ] Compra em 12x com fechamento nos dias 29, 30 e 31 não repete fatura nem pula mês
- [ ] Compra com uma fatura do caminho já paga pula para a seguinte
- [ ] Cartão excluído recebe 400 "Cartão não encontrado."; cartão sem conta de pagamento continua aceito
- [ ] Quick gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix(transactions): coloca cada parcela na fatura certa e guarda a data da compra`

---

#### T7: Total da fatura igual à soma das compras

**What**: Signal guarda o `invoice_id` anterior e chama `recalcular_totais(antiga, nova)`; `recalcular_totais` no `accounts/faturas.py`.
**Where**: `transactions/signals.py`, `accounts/faturas.py`
**Depends on**: T6
**Reuses**: `capture_old_transaction_state`
**Requirement**: FATURA-14, FATURA-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Mover uma compra de fatura atualiza o total da antiga e da nova
- [ ] Mudar o valor e excluir uma compra atualizam o total
- [ ] Compras de outro usuário ligadas à fatura não entram no total (ISOL-14)
- [ ] Full gate passa
- [ ] Test count: pelo menos 4 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix(faturas): mantém o total da fatura antiga e da nova ao mover uma compra`

---

#### T8: Edição da compra no cartão

**What**: `editar_compra` chamado pelo `TransactionSerializer.update` para `CREDIT_CARD`: recusa a FATURA-19, realoca a compra inteira quando muda `purchase_date` ou cartão, ignora o `date` enviado e mantém os escopos de valor.
**Where**: `transactions/services.py`, `transactions/serializers.py`
**Depends on**: T7
**Reuses**: `alocar_parcelas`, `colocar`
**Requirement**: FATURA-17, FATURA-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Mudar a data da compra do Independent Test para 10/01/2026 move as quatro parcelas para fevereiro a maio, e os totais acompanham
- [ ] Mudar o cartão realoca as parcelas nas faturas do cartão novo
- [ ] Salvar uma compra antiga (sem `purchase_date`) com a data carregada não move nada
- [ ] Editar parcela de fatura paga, ou mudar a data de uma compra com parte paga, recebe 400 com a mensagem exata
- [ ] Quick gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix(transactions): realoca as parcelas quando a data ou o cartão da compra muda`

---

#### T9: Exclusão da compra no cartão

**What**: `destroy` de compra no cartão exclui o grupo inteiro e recusa quando alguma parte está em fatura paga.
**Where**: `transactions/views.py`
**Depends on**: T8
**Reuses**: o grupo da compra (raiz e filhas)
**Requirement**: FATURA-19, FATURA-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Excluir a parcela 5/12 exclui as 12, e os totais das 12 faturas caem
- [ ] Excluir a 1/12 também exclui as 12
- [ ] Compra com parcela em fatura paga recebe 400 com a mensagem da FATURA-19 e nada sai
- [ ] Build gate passa
- [ ] Test count: pelo menos 3 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix(transactions): exclui a compra inteira ao excluir uma parcela`

---

### Phase 3: Pagamento e estorno

#### T10: Registro do pagamento

**What**: Modelos `PagamentoDeFatura` e `ItemDePagamento` com a migração `accounts/0005`.
**Where**: `accounts/models.py`, `accounts/migrations/`
**Depends on**: None
**Reuses**: NONE
**Requirement**: FATURA-27, FATURA-30

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A mesma chave não se repete para o mesmo usuário; usuários diferentes podem ter a mesma chave; pagamentos sem chave convivem
- [ ] Quick gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(faturas): registra cada pagamento de fatura e o que ele mudou`

---

#### T11: Pagamento total e parcial

**What**: `pagar()` no `accounts/faturas.py` com a recusa da FATURA-26, a ordem da FATURA-22, a divisão, a rolagem e os itens; `CreditCardService.pay_invoice` delega a ele; a view perde o `except Exception`.
**Where**: `accounts/faturas.py`, `accounts/services.py`, `accounts/views.py`
**Depends on**: T10
**Reuses**: `accounts/saldo.py` (`recalcular`), `primeira_nao_paga`, `colocar`
**Requirement**: FATURA-21, FATURA-22, FATURA-23, FATURA-24, FATURA-25, FATURA-26, FATURA-28

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O Independent Test (R$ 700,00 de R$ 1.000,00) deixa a fatura paga com R$ 700,00 e R$ 300,00 na seguinte, cujo total sobe R$ 300,00
- [ ] Pagamento total marca todas as compras pagas e a fatura paga
- [ ] Compras não pagas vão para a primeira fatura não paga seguinte, criada se faltar
- [ ] Valor maior que o total recebe 400 com a mensagem exata
- [ ] Falha simulada no meio do pagamento deixa fatura, compras, fatura seguinte e saldo como estavam
- [ ] `tests/saldo/test_fatura.py` continua passando
- [ ] Full gate passa
- [ ] Test count: pelo menos 7 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix(faturas): paga a fatura de forma atômica e registra a divisão e a rolagem`

---

#### T12: Pagamento repetido

**What**: `idempotency_key` no `InvoicePaymentSerializer`; `pagar()` devolve o registro da mesma chave ou recusa a chave com outros dados; a view deixa de recusar a fatura paga antes do service e monta a resposta pelo registro.
**Where**: `accounts/faturas.py`, `accounts/serializers.py`, `accounts/views.py`
**Depends on**: T11
**Reuses**: `PagamentoDeFatura`
**Requirement**: FATURA-30, FATURA-32, FATURA-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Dez pedidos com a mesma chave recebem respostas iguais e há um único pagamento e um único débito
- [ ] A mesma chave com outro valor, conta, data ou fatura recebe 400 com a mensagem exata, sem pagar
- [ ] Chave nova ou sem chave numa fatura paga recebe 400 "Fatura já está paga."
- [ ] Repetir a chave depois do estorno devolve a resposta original e não paga de novo
- [ ] Quick gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix(faturas): aplica uma vez só o pagamento reenviado`

---

#### T13: Pedidos simultâneos com a mesma chave

**What**: Teste de concorrência com threads: dois pedidos com a mesma chave ao mesmo tempo; dois com a mesma chave para faturas diferentes.
**Where**: `tests/faturas/test_concorrencia.py`, `accounts/faturas.py` (tratamento do `IntegrityError`)
**Depends on**: T12
**Reuses**: o padrão de `tests/saldo/test_concorrencia.py`
**Requirement**: FATURA-31, FATURA-32

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Dois pedidos simultâneos com a mesma chave: um pagamento, as duas respostas iguais
- [ ] Mesma chave em duas faturas ao mesmo tempo: uma paga, a outra recebe 400 da FATURA-32
- [ ] Quick gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: quick

**Commit**: `test(faturas): cobre pagamentos simultâneos com a mesma chave`

---

#### T14: Estorno do pagamento

**What**: `estornar()` desfaz os itens do registro ativo, recusa a FATURA-38 e mantém o caminho antigo para pagamentos sem registro; `CreditCardService.unpay_invoice` delega a ele; a view perde o `except Exception`.
**Where**: `accounts/faturas.py`, `accounts/services.py`, `accounts/views.py`
**Depends on**: T13
**Reuses**: `recalcular`, `recalcular_totais`, `colocar`
**Requirement**: FATURA-28, FATURA-34, FATURA-35, FATURA-36, FATURA-37, FATURA-38

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O Independent Test (pagar R$ 700,00 e estornar) volta as compras de R$ 400,00 e R$ 600,00, pendentes, com a descrição original, total de R$ 1.000,00, e a seguinte volta ao total anterior
- [ ] Compras movidas voltam para a fatura original
- [ ] Fatura seguinte paga recebe 400 com a mensagem exata, nada muda
- [ ] Depois do estorno o status segue FATURA-08 e FATURA-09
- [ ] Restante editado ou excluído pelo usuário segue a regra do design
- [ ] Pagamento sem registro (feito antes da feature) ainda pode ser estornado
- [ ] Full gate passa
- [ ] Test count: pelo menos 7 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix(faturas): estorna o pagamento e devolve a fatura ao estado anterior`

---

#### T15: API de faturas

**What**: `CreditCardInvoiceViewSet` somente leitura com `pay` e `unpay`; ação `transactions`; `CreditCardInvoiceSerializer` com `credit_card_id` e `payment`.
**Where**: `accounts/views.py`, `accounts/serializers.py`
**Depends on**: T14
**Reuses**: `TransactionSerializer`
**Requirement**: FATURA-27, FATURA-44, FATURA-45

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `POST`, `PUT`, `PATCH` e `DELETE` nas rotas de fatura recebem 405
- [ ] Fatura com 35 compras devolve as 35 em `GET /api/invoices/{id}/transactions/`
- [ ] Fatura paga informa valor, conta e data do pagamento; não paga, `payment` nulo
- [ ] Fatura de outro usuário continua 404 nas rotas novas (ISOL)
- [ ] Build gate passa
- [ ] Test count: pelo menos 5 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix(faturas): expõe as compras e o pagamento da fatura e fecha a escrita direta`

---

### Phase 4: Dados existentes e ciclo completo

#### T16: Migração de correção das faturas

**What**: `accounts/0006_corrige_faturas` liga as compras sem fatura, realoca as parcelas pendentes duplicadas e recalcula todos os totais.
**Where**: `accounts/migrations/0006_corrige_faturas.py`
**Depends on**: None
**Reuses**: funções de data da T1; o padrão de `transactions/migrations/0008_corrige_saldos.py`
**Requirement**: FATURA-39, FATURA-40, FATURA-41

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Compra sem fatura passa a ter fatura, `purchase_date` com a data antiga e `date` no vencimento
- [ ] Compra com duas parcelas pendentes na mesma fatura fica com uma parcela por fatura consecutiva; parcelas pagas não se movem
- [ ] Total de fatura desatualizado volta à soma das compras
- [ ] Banco vazio: a migração não faz nada
- [ ] Build gate passa
- [ ] Test count: pelo menos 5 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix(faturas): corrige compras sem fatura, parcelas repetidas e totais gravados`

---

#### T17: Ciclo completo

**What**: Sequência de criar compras, pagar parcial, estornar e pagar de novo, conferindo faturas, compras, totais e saldo em cada passo.
**Where**: `tests/faturas/test_fluxo_completo.py`
**Depends on**: T16
**Reuses**: NONE
**Requirement**: FATURA-21, FATURA-34, FATURA-37

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Pagar, estornar e pagar de novo deixa faturas, compras e totais idênticos aos de um único pagamento (Success Criteria)
- [ ] O saldo da conta de pagamento acompanha cada passo (SALDO-23 a SALDO-25)
- [ ] Build gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `test(faturas): cobre pagar, estornar e pagar de novo`

---

### Phase 5: Frontend

#### T18: Datas da fatura sem deslocamento de fuso

**What**: `src/lib/datas.ts` com `lerData` e `nomeDoMes`; `invoice-list.tsx`, `invoice-payment-dialog.tsx` e `invoice-details-dialog.tsx` passam a usá-los; a lista mostra o pagamento da fatura paga.
**Where**: `src/lib/datas.ts` (novo), `src/components/cards/invoice-list.tsx`, `src/components/cards/invoice-details-dialog.tsx`, `src/components/transactions/invoice-payment-dialog.tsx`, `src/types/cards.ts`
**Depends on**: None
**Reuses**: `date-fns`
**Requirement**: FATURA-27, FATURA-43

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Com `TZ=America/Sao_Paulo`, vencimento "2026-10-01" aparece como 01/10/2026 e "outubro"
- [ ] O nome do mês da fatura está certo mesmo quando o teste roda num dia 31
- [ ] Fatura paga mostra valor, conta e data do pagamento
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix(frontend): mostra as datas da fatura sem perder um dia`

---

#### T19: Pagamento com identificador da tentativa

**What**: O diálogo gera `idempotency_key` ao abrir e o reusa até o sucesso; preenche a conta pelo `credit_card_id`; mostra a mensagem do backend.
**Where**: `src/components/transactions/invoice-payment-dialog.tsx`
**Depends on**: T18
**Reuses**: `mensagemDeErro`
**Requirement**: FATURA-29

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Um envio que falha por timeout e é reenviado manda a mesma chave nas duas vezes
- [ ] Fechar e abrir o diálogo gera chave nova
- [ ] A conta de pagamento do cartão vem preenchida ao abrir pela fatura
- [ ] A mensagem 400 do backend aparece no toast
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix(frontend): reenvia o pagamento da fatura com o mesmo identificador`

---

#### T20: Detalhe da fatura com todas as compras

**What**: O diálogo busca `GET /invoices/{id}/transactions/` e mostra a data da compra.
**Where**: `src/components/cards/invoice-details-dialog.tsx`, `src/types/transactions.ts`
**Depends on**: T19
**Reuses**: `lerData`
**Requirement**: FATURA-16, FATURA-44

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Uma fatura com 35 compras lista as 35
- [ ] Cada compra mostra `purchase_date`, ou `date` quando ele é nulo
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix(frontend): lista todas as compras da fatura com a data da compra`

---

#### T21: Edição e exclusão da compra no cartão

**What**: O formulário carrega e envia `purchase_date`; mostra a mensagem de recusa do backend; o aviso de exclusão diz que todas as parcelas saem; a lista de transações mostra "Compra em dd/mm".
**Where**: `src/components/transactions/card-expense-form-dialog.tsx`, `src/app/(app)/transacoes/page.tsx`
**Depends on**: T20
**Reuses**: `mensagemDeErro`, `lerData`
**Requirement**: FATURA-16, FATURA-17, FATURA-19, FATURA-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A edição envia `purchase_date` com a data escolhida e carrega `purchase_date` ou `date`
- [ ] A recusa da FATURA-19 aparece no toast com a mensagem do backend
- [ ] Excluir uma parcela avisa que todas as parcelas da compra serão excluídas
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix(frontend): edita a data da compra no cartão e avisa a exclusão das parcelas`

---

#### T22: Tela do cartão

**What**: A tela do cartão mostra `next_due_date` e usa só o `available_limit` do backend.
**Where**: `src/app/(app)/cartoes/[id]/page.tsx`, `src/components/cards/credit-card-item.tsx`
**Depends on**: T21
**Reuses**: `lerData`
**Requirement**: FATURA-06, FATURA-42

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O próximo vencimento mostrado é o `next_due_date` da API
- [ ] O limite disponível mostrado é o `available_limit` da API
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `fix(frontend): mostra o próximo vencimento e o limite que a API calcula`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

Execution is strictly sequential - there is no intra-phase parallelism.

Batches para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T9), lote 2 com as fases 3 e 4 (T10 a T17), lote 3 com a fase 5 (T18 a T22).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Funções de data da fatura | 1 módulo | ✅ Granular |
| T2: Fatura de cada compra e primeira fatura não paga | 1 módulo e 1 delegação | ⚠️ Coeso |
| T3: Status exibido, próximo vencimento e dias do cartão | 2 funções e 3 usos | ⚠️ Coeso |
| T4: Limite disponível com uma fórmula | 1 função e 2 usos | ✅ Granular |
| T5: Data da compra | 1 campo e a migração | ✅ Granular |
| T6: Criação da compra no cartão | 1 service e 1 serializer | ✅ Granular |
| T7: Total da fatura igual à soma das compras | 1 signal | ✅ Granular |
| T8: Edição da compra no cartão | 1 service e o uso no serializer | ⚠️ Coeso |
| T9: Exclusão da compra no cartão | 1 arquivo | ✅ Granular |
| T10: Registro do pagamento | 2 modelos e a migração | ✅ Granular |
| T11: Pagamento total e parcial | 1 função e a delegação | ⚠️ Coeso |
| T12: Pagamento repetido | 1 função, serializer e view | ⚠️ Coeso |
| T13: Pedidos simultâneos com a mesma chave | 1 teste | ✅ Granular |
| T14: Estorno do pagamento | 1 função e a delegação | ⚠️ Coeso |
| T15: API de faturas | 1 viewset e 1 serializer | ✅ Granular |
| T16: Migração de correção das faturas | 1 arquivo | ✅ Granular |
| T17: Ciclo completo | 1 teste | ✅ Granular |
| T18: Datas da fatura sem deslocamento de fuso | 1 helper e 3 usos | ⚠️ Coeso |
| T19: Pagamento com identificador da tentativa | 1 arquivo | ✅ Granular |
| T20: Detalhe da fatura com todas as compras | 1 arquivo | ✅ Granular |
| T21: Edição e exclusão da compra no cartão | 2 arquivos | ✅ Granular |
| T22: Tela do cartão | 2 arquivos | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T2 | T2 → T4 | ✅ Match |
| T5 | None | sem seta dentro da fase | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | None | sem seta dentro da fase | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |
| T16 | None | sem seta dentro da fase | ✅ Match |
| T17 | T16 | T16 → T17 | ✅ Match |
| T18 | None | sem seta dentro da fase | ✅ Match |
| T19 | T18 | T18 → T19 | ✅ Match |
| T20 | T19 | T19 → T20 | ✅ Match |
| T21 | T20 | T20 → T21 | ✅ Match |
| T22 | T21 | T21 → T22 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Funções de data da fatura | Funções de data | unit | unit | ✅ OK |
| T2: Fatura de cada compra e primeira fatura não paga | Backend | integration | integration | ✅ OK |
| T3: Status exibido, próximo vencimento e dias do cartão | Backend | integration | integration | ✅ OK |
| T4: Limite disponível com uma fórmula | Backend | integration | integration | ✅ OK |
| T5: Data da compra | Backend | integration | integration | ✅ OK |
| T6: Criação da compra no cartão | Backend | integration | integration | ✅ OK |
| T7: Total da fatura igual à soma das compras | Backend | integration | integration | ✅ OK |
| T8: Edição da compra no cartão | Backend | integration | integration | ✅ OK |
| T9: Exclusão da compra no cartão | Backend | integration | integration | ✅ OK |
| T10: Registro do pagamento | Backend | integration | integration | ✅ OK |
| T11: Pagamento total e parcial | Backend | integration | integration | ✅ OK |
| T12: Pagamento repetido | Backend | integration | integration | ✅ OK |
| T13: Pedidos simultâneos com a mesma chave | Concorrência | integration | integration | ✅ OK |
| T14: Estorno do pagamento | Backend | integration | integration | ✅ OK |
| T15: API de faturas | Backend | integration | integration | ✅ OK |
| T16: Migração de correção das faturas | Migração | integration | integration | ✅ OK |
| T17: Ciclo completo | Backend | integration | integration | ✅ OK |
| T18: Datas da fatura sem deslocamento de fuso | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T19: Pagamento com identificador da tentativa | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T20: Detalhe da fatura com todas as compras | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T21: Edição e exclusão da compra no cartão | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T22: Tela do cartão | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
