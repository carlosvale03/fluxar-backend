# Saldo Validation

**Date**: 2026-10-01
**Spec**: `.specs/features/saldo/spec.md`
**Diff range**: backend `development..fix/saldo` (`cf4ed95..6078c6a`, 34 commits); frontend `development..fix/saldo` (`cf4ed95..fc3084b`, 4 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve, uma rodada
**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T30 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md`; T29 e T30 entraram durante a execução (SALDO-35 no cartão e no service de transferência) |

---

## Gate Check

### Backend

- **Comando**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`
- **Resultado**: exit 0. `compileall` sem erro; `makemigrations --check`: "No changes detected"; `Ran 529 tests ... OK`
- **Falhas**: nenhuma. **Skips**: nenhum
- **Contagem**: 529 (esperado ~529). `tests/saldo` sozinho: 145 testes

### Frontend

| Gate | Resultado |
| ---- | --------- |
| `npx tsc --noEmit -p . --incremental false` | exit 0 |
| `npm test` | 20 arquivos, 84 testes, todos passando (esperado ~84) |
| `npm run lint` | 160 erros (246 avisos). Linha de base na `development` (worktree descartável): 164. Única regra que mudou: `@typescript-eslint/no-explicit-any` 128 → 124. Nenhuma regra ganhou erro |
| `NEXT_PUBLIC_API_URL=http://build-check-placeholder npm run build` | exit 0 |
| `npm audit --omit=dev` | `found 0 vulnerabilities` |

---

## Spec-Anchored Acceptance Criteria

Testes do backend em `tests/saldo/` (repositório `fluxar-backend`); os marcados FE estão em `tests/saldo/` do `fluxar-frontend`. Saldo inicial da conta corrente de A nos fixtures: R$ 1.000,00 (`tests/saldo/base.py:33`).

### P1: Saldo em transações avulsas

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-01 regra do saldo | inicial + INCOME/TRANSFER_IN − EXPENSE/TRANSFER_OUT/CREDIT_CARD/INVOICE_PAYMENT efetivadas | `tests/saldo/test_saldo.py:94` - `assertEqual(self.saldo(conta), Decimal('1500.00'))` (1000+500+200−100−50−30−20); `:96` `calcular(...) == 1500.00`; `:102` transação de outro usuário fora (`1000.00`) | ✅ PASS |
| SALDO-02 pendente fora do saldo | saldo inalterado | `tests/saldo/test_saldo.py:39` - `saldo == Decimal('1000.00')`; `:90-94` pendentes dos seis tipos fora | ✅ PASS |
| SALDO-03 criar efetivada | +entrada / −saída | `tests/saldo/test_saldo.py:31` - `1200.00`; `:35` - `700.00` | ✅ PASS |
| SALDO-04 efetivar pendente | aplica o valor | `tests/saldo/test_saldo.py:44` - `700.00` | ✅ PASS |
| SALDO-05 voltar a pendente | desfaz | `tests/saldo/test_saldo.py:50` - `1000.00` | ✅ PASS |
| SALDO-06 valor ou tipo mudam | diferença | `tests/saldo/test_saldo.py:55` - `879.50`; `:60` - `1300.00` (despesa vira receita) | ✅ PASS |
| SALDO-07 troca de conta | sai da antiga, entra na nova | `tests/saldo/test_saldo.py:65-66` - conta `1000.00`, poupança `250.00`; `:121-122` pelo ORM | ✅ PASS |
| SALDO-08 excluir efetivada | desfaz | `tests/saldo/test_saldo.py:71-72` - `204` e `1000.00` | ✅ PASS |
| SALDO-09 valor ≤ 0 ou > 2 casas | HTTP 400, erro no campo do valor, nenhum saldo muda; 100,1 aceito | `tests/saldo/test_valor.py:71-75` - `status_code == 400`, `'amount' in resp.data`, `resp.data['amount'] == ['O valor deve ser maior que zero.']`, `estado() == antes`, para transação, transferência, compra no cartão, pagamento de fatura, aporte e resgate; `:87-88` 100.1 aceito (`899.90`); lote da série em `tests/saldo/test_series.py:160-164` | ✅ PASS (⚠️ ver lacuna de precisão 1) |
| SALDO-10 falha no meio desfaz tudo | todos os saldos e transações como antes | `tests/saldo/test_atomicidade.py:70`, `:80`, `:93`, `:106`, `:117`, `:131`, `:142`, `:152` - `assertEqual(self.estado(), antes)` (transferência, compra parcelada, pagamento, estorno, aporte, edição pela rota) | ✅ PASS |

### P1: Transferências

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-11 saída e entrada juntas | origem −V, destino +V, mesmo `transfer_id` | `tests/saldo/test_transferencia.py:54-65` - `900.00`/`100.00`, contas das pernas, `transfer_id` igual, status `COMPLETED` nas duas | ✅ PASS |
| SALDO-12 soma constante | soma das contas inalterada ao criar, editar, excluir | `tests/saldo/test_transferencia.py:56` (criar), `:147` em cada passo da edição, `:268` (excluir) - `assertEqual(self.soma(), ...)` | ✅ PASS |
| SALDO-13 novo valor nas duas pernas | ambas com o valor novo; saldos pela diferença | `tests/saldo/test_transferencia.py:154-155` - `(150.00, 150.00)` e `850.00/150.00/0.00` | ✅ PASS |
| SALDO-14 troca de conta de uma perna | efeito sai da antiga, vai para a nova | `tests/saldo/test_transferencia.py:159-166` - destino B→C (`850/0/150`) e origem A→B (`1000/−150/150`); `:187-192` PUT pela perna de entrada | ✅ PASS |
| SALDO-15 status espelhado | outra perna com o mesmo status | `tests/saldo/test_transferencia.py:170-176` - `('PENDING','PENDING')`, depois `('COMPLETED','COMPLETED')` | ✅ PASS |
| SALDO-16 excluir uma perna | as duas somem, efeito desfeito nas duas | `tests/saldo/test_transferencia.py:267-268`, `:275` (`1000.00`, `0.00`), `:284` (`970.00`, `30.00`) | ✅ PASS |
| SALDO-17 origem = destino | HTTP 400 | `tests/saldo/test_transferencia.py:80-82` - `400`, `{'detail': MESMA_CONTA}`, estado inalterado; meta `:95-97`; edição `:226-228` | ✅ PASS |
| SALDO-18 tipos especiais no endpoint genérico | HTTP 400 | `tests/saldo/test_tipos.py:25-28` - `400`, `'type' in resp.data`, contagem e saldo inalterados, para os 4 tipos (`:30-40`); FE `tests/saldo/pagamento-de-fatura.test.tsx:75` - `expect(post).not.toHaveBeenCalled()` sem fatura | ✅ PASS |
| SALDO-19 troca de tipo para/de especial | HTTP 400 | `tests/saldo/test_tipos.py:65-68` - `400`, `'type' in resp.data`, estado e saldo inalterados, PATCH e PUT (`:70-87`); perna de transferência `tests/saldo/test_transferencia.py:205-207` | ✅ PASS |

### P1: Séries recorrentes

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-20 primeira com o status escolhido, geradas pendentes | 1ª `COMPLETED`, 11 `PENDING`, saldo +5.000 | `tests/saldo/test_series.py:40-44` - 12 ocorrências, `primeira.status == 'COMPLETED'`, `['PENDING'] * 11`, saldo `6000.00`; `:49-50` primeira pendente → `['PENDING'] * 12`, `1000.00` | ✅ PASS |
| SALDO-21 alterar todas | só as pendentes recebem descrição, valor, categoria, conta e tipo | `tests/saldo/test_series.py:102-103` - efetivadas `(5000.00, conta)` × 2, pendentes `(5500.00, poupança)` × 10; `:124-125` descrição, categoria e tipo | ✅ PASS |
| SALDO-22 excluir série | pendentes apagadas, série encerrada, efetivadas mantidas | `tests/saldo/test_series.py:209-213` - restam a 1ª e a 2ª `COMPLETED`, nenhuma pendente, `is_active` falso, saldo `11000.00` | ✅ PASS |

### P1: Pagamento e estorno de fatura

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-23 pagar V | conta pagadora −V exatamente | `tests/saldo/test_fatura.py:55` - `saldo(pagadora) == 2000.00` (3000 − 1000) | ✅ PASS |
| SALDO-24 estornar | +valor pago | `tests/saldo/test_fatura.py:114` - `3000.00`; parcial `:146` - `3000.00` depois de pagar 300 | ✅ PASS |
| SALDO-25 pagar, estornar, pagar | um único débito | `tests/saldo/test_fatura.py:121` - `2000.00` | ✅ PASS |
| SALDO-26 segundo pagamento | um só processado; demais 400 "Fatura já está paga." | `tests/saldo/test_fatura.py:67-69` - `400`, `{'detail': 'Fatura já está paga.'}`, `2000.00`; `:90-91` fatura lida antes; `tests/saldo/test_concorrencia.py:116-119` - simultâneos `[200, 400]`, mensagem exata, `2000.00` | ✅ PASS (repetição com o mesmo identificador fica com FATURA-30, AD-007) |
| SALDO-27 estornar fatura não paga | HTTP 400, nenhum saldo muda | `tests/saldo/test_fatura.py:160-164` - `400`, `{'detail': 'Esta fatura não está paga.'}`, saldos `3000.00`/`1000.00`; `:182-184` estorno atrasado | ✅ PASS |
| SALDO-46 efetivar compra fora da fatura | HTTP 400 | `tests/saldo/test_tipos.py:126-130` - `400`, `resp.data['status'] == ['Compras no cartão são efetivadas pelo pagamento da fatura.']`, compra `PENDING`, saldo `1000.00` (PATCH e PUT) | ✅ PASS |

### P1: Totais do dashboard e contas excluídas

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-28 mesmo valor da lista | totais = soma da lista de contas | `tests/saldo/test_totais.py:83-90` - líquido, investimento, total e admin iguais aos da lista mesmo com razão divergente; `tests/saldo/test_fluxo_completo.py:48-60` em cada passo | ✅ PASS |
| SALDO-29 "Saldo em Contas" | corrente+poupança+carteira ativas | `tests/saldo/test_totais.py:48` - `total_liquid_balance == 1000.00` (sem investimento nem excluída) | ✅ PASS |
| SALDO-30 saldo total | todas as ativas, qualquer tipo | `tests/saldo/test_totais.py:52` - `total_balance == 1500.00`; `:54` `net_worth == 1500.00` | ✅ PASS |
| SALDO-31 excluída fora de todos os totais | fora de líquido, total, patrimônio, investimentos e admin | `tests/saldo/test_totais.py:48`, `:52`, `:54`, `:61` - a excluída de R$ 300,00 não entra; `:57` investimentos `500.00` | ✅ PASS (⚠️ ver lacuna 2: nenhuma conta de investimento excluída no fixture) |
| SALDO-32 excluir com saldo ≠ 0 | HTTP 400 e a mensagem exata | `tests/saldo/test_exclusao_de_conta.py:31-35` - `400`, `{'detail': 'Zere o saldo antes de excluir a conta: transfira ou ajuste o valor restante.'}`, conta ativa; negativo `:41-44`; FE `tests/saldo/exclusao-de-conta.test.tsx:60` - `toast.error` com a mensagem | ✅ PASS |
| SALDO-33 excluir com pendentes | HTTP 400 e a mensagem exata | `tests/saldo/test_exclusao_de_conta.py:46-49` - `{'detail': 'Resolva as transações pendentes antes de excluir a conta: efetive, mova ou exclua cada uma.'}`; FE `tests/saldo/exclusao-de-conta.test.tsx:70` | ✅ PASS |
| SALDO-34 excluir conta zerada | sai da lista, histórico mantido | `tests/saldo/test_exclusao_de_conta.py:58-69` - `204`, `is_active` falso, fora da lista, transações efetivadas listadas | ✅ PASS |
| SALDO-35 operação nova em conta excluída | HTTP 400 | `tests/saldo/test_conta_excluida.py:53-55` - `400`, `resp.data[campo] == ['Conta não encontrada.']`, estado inalterado (transação, transferência nos dois lados, pagamento de fatura, aporte, resgate, edição); ajuste `tests/saldo/test_ajuste.py:101-104`; compra no cartão `tests/saldo/test_conta_excluida.py:200-202`; service de transferência `:231-232` | ✅ PASS |
| SALDO-36 editar ou excluir histórico da excluída | HTTP 400 | `tests/saldo/test_conta_excluida.py:135-137` - `400`, `{'detail': 'Esta transação é de uma conta excluída e não pode ser alterada.'}`, estado inalterado (PATCH, PUT, DELETE, pernas e exclusão em lote) | ✅ PASS |
| SALDO-47 `cleanup_db` | histórico da excluída e saldos das ativas intactos | `tests/saldo/test_cleanup.py:55-60` - `fotografia() == antes`, transações da excluída mantidas, `1200.00` | ✅ PASS |

### P1: Correção dos saldos existentes

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-37 futuras efetivadas voltam a pendentes, exceto a 1ª | status por data de Brasília | `tests/saldo/test_migracao.py:102-108` - `['COMPLETED','COMPLETED','PENDING','PENDING','PENDING','PENDING']`, 1ª futura mantida `['COMPLETED','PENDING']`, avulsa futura `COMPLETED`; desempate `:118` | ✅ PASS |
| SALDO-38 recálculo de todas as contas | saldo = SALDO-01 | `tests/saldo/test_migracao.py:124-132` - `balance == calcular(c)` para todas, `10900.00`, `-800.00`, excluída `30.00`, B `1000.00`; modelos históricos `:141-142` | ✅ PASS |
| SALDO-39 verificação de consistência | lista id e os dois valores de cada divergente | `tests/saldo/test_check_saldos.py:32-36` - linhas `'<id> 950.00 900.00'` e `'<id> -10.50 0.00'`, total `2`; `:44` sem divergência | ✅ PASS |

### P2: Ajuste de saldo

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-40 novo saldo ≠ atual | transação efetivada, data de hoje, entrada/saída | `tests/saldo/test_ajuste.py:51-53` - `('EXPENSE', 0.20, 'COMPLETED', 2026-09-30, ...)` com o relógio em 01/10 02:00 UTC; `:61-63` `INCOME 250.25`; negativo `:70-73`; FE `tests/saldo/ajuste-de-saldo.test.tsx:61` - `post` em `/accounts/conta-1/adjust-balance/` com `{ new_balance: "999.90" }` | ✅ PASS |
| SALDO-41 saldo exato com centavos | 1.000,10 → 999,90 com saída de 0,20 | `tests/saldo/test_ajuste.py:52-55` - saída `0.20`, `saldo == 999.90`, resposta `999.90` | ✅ PASS |
| SALDO-42 novo saldo = atual | nenhuma transação | `tests/saldo/test_ajuste.py:91-94` - `200`, nenhuma transação, saldo igual; FE `tests/saldo/ajuste-de-saldo.test.tsx:70-72` - botão desabilitado, `post` não chamado | ✅ PASS |
| SALDO-43 saldo inicial muda | saldo atual pela mesma diferença | `tests/saldo/test_saldo_inicial.py:30-31` - `900.00` (700 + 200), resposta `'900.00'`; `:35` - `550.00` | ✅ PASS |

### P2: Operações simultâneas

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| SALDO-44 duas operações ao mesmo tempo | mesmo saldo da sequência | `tests/saldo/test_concorrencia.py:80-82` - 20 × `201`, 20 transações, `1200.00` e `balance == calcular` | ✅ PASS |
| SALDO-45 duas efetivações da mesma pendente | uma única aplicação | `tests/saldo/test_concorrencia.py:95-98` - `[200, 200]`, `COMPLETED`, `700.00` | ✅ PASS |

**Status**: ✅ 47/47 ACs com evidência `file:line` e asserção no valor da spec; ⚠️ 2 lacunas de precisão/cobertura menores sinalizadas.

---

## Edge Cases

- [x] Efetivada com data futura fora de série entra no saldo: `tests/saldo/test_saldo.py:74-76` (`700.00`)
- [x] Série com início no passado gera pendentes: `tests/saldo/test_series.py:52-58`
- [x] Série com a 1ª pendente não mexe no saldo: `tests/saldo/test_series.py:46-50`
- [x] Estorno de pagamento parcial devolve só o pago: `tests/saldo/test_fatura.py:138-155`
- [x] Compra no cartão não paga fica pendente: `tests/saldo/test_fluxo_completo.py:189-190`; `tests/saldo/test_fatura.py:55-57`
- [x] Pagamento sem fatura (CON-09) recusado: `tests/saldo/test_tipos.py:39-40`; FE `tests/saldo/pagamento-de-fatura.test.tsx:62-76`
- [x] Saldo negativo bloqueia exclusão: `tests/saldo/test_exclusao_de_conta.py:41-44`
- [x] Ajuste para saldo negativo permitido: `tests/saldo/test_ajuste.py:66-73`
- [x] Transferência entre ativa e excluída não é criada, editada nem excluída: `tests/saldo/test_conta_excluida.py:60-70`, `:150-163`; `tests/saldo/test_transferencia.py:230-244`
- [x] Aporte e resgate seguem as regras de transferência: `tests/saldo/test_transferencia.py:99-107`; `tests/saldo/test_valor.py:117-131`
- [x] Conta excluída com saldo antes da correção fica fora dos totais: `tests/saldo/test_totais.py:30-35`, `:48-61`

---

## Discrimination Sensor

Worktrees descartáveis: `../fluxar-backend-verif` (detached em `6078c6a`, testes num container avulso `fluxar-backend-backend` na rede `fluxar-backend_default`) e `../fluxar-frontend-verif` (detached em `fc3084b`, `node_modules` por junction). Sem mutação, `tests.saldo` passou (145 testes OK) e `npx vitest run tests/saldo` passou (9 testes). Cada mutação foi revertida com `git checkout -- <arquivo>` antes da seguinte, com o worktree conferido limpo.

| # | File:line | Descrição | Killed? |
| - | --------- | --------- | ------- |
| 1 | `accounts/saldo.py:23` | `calcular` soma também as pendentes (`status='COMPLETED'` → `status__in=('COMPLETED', 'PENDING')`) | ✅ Killed (29 falhas: `test_saldo`, `test_fatura`, `test_migracao`, `test_saldo_inicial`, `test_fluxo_completo` e outros) |
| 2 | `transactions/signals.py:135` | Transação movida de conta não recalcula a conta antiga (`recalcular(instance.account_id)`) | ✅ Killed (4 falhas: `test_mudar_de_conta_move_o_efeito`, `test_mudar_de_conta_pelo_orm_recalcula_as_duas`, `test_saldo_confere_em_toda_a_sequencia`) |
| 3 | `transactions/services.py:114` | `editar_transferencia` não aplica o valor à perna parceira (`('amount', 'date', 'status')` → `('date', 'status')`) | ✅ Killed (4 falhas: `test_valor_destino_origem_e_status_em_sequencia`, `test_put_pela_perna_de_entrada_como_a_tela_envia`, fluxo completo) |
| 4 | `transactions/views.py:273` | `bulk_update` altera também as ocorrências efetivadas (sem `status='PENDING'`) | ✅ Killed (5 falhas: `test_valor_e_conta_mudam_so_as_pendentes`, `test_descricao_categoria_e_tipo_mudam_so_as_pendentes`, fluxo completo) |
| 5 | `accounts/services.py:252` | `unpay_invoice` sem `recalcular` | ✅ Killed (5 falhas: `test_pagar_estornar_e_pagar_de_novo`, `test_estorno_de_pagamento_parcial_devolve_so_o_valor_pago`, `test_segundo_estorno_...`, fluxo completo) |
| 6 | `reports/services.py:87` | Saldo total do dashboard inclui contas excluídas (sem `is_active=True`) | ✅ Killed (2 falhas: `test_saldo_total_soma_as_contas_ativas_de_qualquer_tipo`, `test_totais_usam_o_mesmo_valor_da_lista_de_contas`) |
| 7 | `transactions/migrations/0008_corrige_saldos.py:36` | Migração não poupa a primeira ocorrência (sem `.exclude(pk=primeira)`) | ✅ Killed (3 falhas: `test_ocorrencias_futuras_...`, `test_primeira_ocorrencia_desempata_pela_criacao`, `test_saldos_de_todas_as_contas_ficam_iguais_a_saldo_01`) |
| 8 | `src/components/accounts/balance-adjustment-dialog.tsx:56` (frontend) | Diálogo de ajuste envia o número em ponto flutuante (`new_balance = newBalance`) | ✅ Killed (1 falha: `ajuste-de-saldo.test.tsx` "envia o novo saldo 999.90 para a rota de ajuste") |

**Sensor depth**: leve (8 mutações de comportamento nos pontos centrais, pedido do usuário)
**Result**: 8/8 killed, 0 survived - PASS

---

## Code Quality (nível leve, amostragem)

| Princípio | Status |
| --------- | ------ |
| Mudanças cirúrgicas, só nos caminhos de saldo | ✅ (a exceção do `ATOMIC_REQUESTS` nas rotas de auth e health está documentada no mixin `SemTransacaoPorRequisicao`, `api/views.py:53`) |
| Uma única fórmula de saldo | ✅ `accounts/saldo.py:18`; `AccountService.get_balance` delega; a migração repete a fórmula por não poder importar a aplicação, e `check_saldos` confere as duas |
| Testes mapeados aos ACs | ✅ cada arquivo de `tests/saldo/` cita os IDs que cobre |
| Asserções no valor da spec | ✅ mensagens exatas de SALDO-26, SALDO-32 e SALDO-33 conferidas literalmente |
| Guidelines | nenhum guideline de testes próprio do projeto; padrão forte aplicado |

---

## Spec-Precision Gaps

1. **SALDO-09 na edição.** A spec diz "receber um valor", sem dizer se vale só na criação. Os testes cobrem a criação de cada operação e o lote da série, mas nenhum teste faz PATCH/PUT de uma transação avulsa ou de uma perna de transferência com valor 0, negativo ou com 3 casas. O validador está no campo do serializer (`transactions/serializers.py:127`, `extra_kwargs`), então vale também na edição, mas sem evidência de teste.
2. **SALDO-31, saldo de investimentos.** O fixture de `tests/saldo/test_totais.py` tem só uma conta corrente excluída; nenhuma conta de investimento excluída. A asserção `total_investment_balance == 500.00` (`:57`) passaria mesmo sem o filtro `is_active` nas contas de investimento. O filtro já existia antes da feature (`reports/services.py:251` e `:518`), então o risco é baixo.
3. **SALDO-17 e SALDO-35 sem mensagem na spec.** A spec define só o HTTP 400; as mensagens ("A conta de origem e a de destino devem ser diferentes.", "Conta não encontrada.") vêm do design e os testes as conferem literalmente. Não é falha, só registro.

---

## Notas residuais e passos de deploy

**Deploy**

1. A migração `transactions/migrations/0008_corrige_saldos.py` roda no `migrate` do deploy: volta a pendentes as ocorrências de série efetivadas com data depois de hoje (Brasília), menos a primeira de cada série, e recalcula o saldo de todas as contas (SALDO-37, SALDO-38). É irreversível na prática (`reverse_code` é `noop`).
2. Logo depois, rodar `python manage.py check_saldos`. O esperado é `Contas com saldo divergente: 0` (Success Criteria da spec).

**Achados fora do escopo relatados pelos executores, todos da feature `faturas`**

- `pay_invoice` deixa o `total_amount` da fatura desatualizado depois de um pagamento parcial.
- Estornar um pagamento parcial não junta de volta a parte "(Parcial)" e a "(Restante)" (o teste `tests/saldo/test_fatura.py:138-155` fixa o comportamento atual: o restante fica na fatura seguinte).
- A compra no cartão é aceita quando o cartão não tem conta de pagamento ou foi excluído.
- No jsdom, o diálogo de pagamento de fatura reseta o valor pré-preenchido.

**Outras notas**

- A repetição da mesma tentativa de pagamento com o mesmo identificador (AD-007, FATURA-30) não é desta feature; aqui só a recusa da segunda tentativa diferente.
- Desvio conhecido do design: as views de auth e o health ficam fora do `ATOMIC_REQUESTS` (`SemTransacaoPorRequisicao`), para que os contadores do rate limit não sejam desfeitos.
- O lint do frontend continua com 160 erros antigos (MAN-04); a feature reduziu 4 de `no-explicit-any` e não criou nenhum.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| SALDO-01 a SALDO-47 | Pending | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (PASS)

**Spec-anchored check**: 47/47 ACs com evidência; 2 lacunas menores de cobertura (SALDO-09 na edição, SALDO-31 em investimentos) e 1 nota de precisão
**Sensor**: 8/8 mutações mortas (7 no backend, 1 no frontend)
**Gate**: backend 529 OK; frontend tsc 0, 84 testes, lint 160 (base 164, nenhuma regra piorou), build 0, audit 0 vulnerabilidades

**validate_state**: `python validate_state.py saldo --root <fluxar-backend>` → `validate_state: 0 error(s) across [saldo]` (exit 0)

**Lições registradas** (`lessons.py add`): L-017 (`spec_precision_gap`, SALDO-09 na edição) e L-018 (`ac_gap`, fixture sem conta de investimento excluída em SALDO-31).

**Próximos passos**: opcional, antes do merge, um teste de PATCH com valor inválido numa transação avulsa e numa perna de transferência, e uma conta de investimento excluída no fixture de `tests/saldo/test_totais.py`. Nenhum dos dois bloqueia.
