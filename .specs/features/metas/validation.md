# Metas Validation

**Date**: 2026-10-08
**Spec**: `.specs/features/metas/spec.md`
**Diff range**: backend `fix/metas-aportes-resgates-e-cofrinho` (`4d234a9..3e6bea5`, 19 commits: 13 de código e testes, 1 de design/tasks, 5 de marcação das tasks e do estado); frontend `fix/metas-aportes-resgates-e-cofrinho` (`2da410b..cd98208`, 5 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve, uma rodada
**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T15 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md` (T1 a T10 no backend, T11 a T15 no frontend). O cabeçalho de `tasks.md` ainda diz `Status: In Progress` (observação 6) |

---

## Gate Check

### Backend

- **Comando**: `docker compose exec -T backend python manage.py test --noinput`
- **Resultado**: exit 0. `Ran 959 tests in 267.800s ... OK`
- **Falhas**: nenhuma. **Skips**: nenhum. O teste instável conhecido (`tests.importacao.test_sugestao.test_linha_com_categoria_no_arquivo_mantem_a_do_arquivo`) passou nesta rodada
- **Contagem**: 872 antes da feature (`def test_` em `4d234a9`), 959 depois: +87 (85 em `tests/metas/`, que `manage.py test tests.metas` roda, e 2 novos em `tests/isolamento/test_correcao.py`)
- **Migrações**: `python manage.py makemigrations --check --dry-run` → `No changes detected`
- **Testes antigos ajustados**: `tests/isolamento/` (aporte e resgate, histórico, metas, signal das metas), `tests/saldo/test_valor.py` e `tests/contratos/`. As asserções mudaram para a regra nova: o rateio automático saiu (AD-028), as metas não trazem mais `deposits`, a exclusão da meta responde 200 com `piggy_bank_empty` e a mensagem do resgate é a da META-17. Nenhuma asserção foi retirada sem substituta

### Frontend

| Gate | Resultado |
| ---- | --------- |
| `npm test` | 56 arquivos, 299 testes, todos passando (270 antes da feature, +29 em `tests/metas/`) |

Testes antigos ajustados no frontend: `tests/contratos/datas-sem-hora.test.tsx`, `dinheiro-nos-formularios.test.tsx` (formulários de aporte e resgate com a prop `cofrinho` e o novo campo de origem) e `tests/permissoes/limites-nas-telas.test.tsx`, `uso-depois-de-criar.test.tsx` (mock de `getPiggyBanks`).

---

## Spec-Anchored Acceptance Criteria

Os caminhos `tests/metas/*.py` são do `fluxar-backend`. Os marcados **FE** estão em `tests/metas/` do `fluxar-frontend`.

### P1: Valor das metas e saldo livre do cofrinho

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| META-01 aportes menos resgates, sem transferência ou com ela efetivada | soma com sinal; pendente não conta | `tests/metas/test_valores.py:23` - `calcular == 350.25` (300 + 150,50 - 100,25); `:32` - efetivada 500 + pendente 200 → `500.00`; `:40` - uma perna pendente já tira o registro; `:50`, `:60-62` registros antigos por `transfer_id` e por `id` | ✅ PASS |
| META-02 saldo livre = saldo − todas as metas, inclusive arquivadas | 1000 − 600 − 150 = 250 | `tests/metas/test_valores.py:102` - `saldo_livre == 250.00` com a arquivada e sem a meta de B; `:108` pode ficar negativo (`-200.00`) | ✅ PASS |
| META-03 transação comum no cofrinho muda só o saldo livre | livre +200; meta igual | `tests/metas/test_vinculo.py:66-68` - `livre − antes == 200.00`, meta `100.00`, 1 registro; `:80-82` despesa pelo cofrinho → livre `-300.00`, meta `100.00`; `:200-202` excluir receita comum não muda a meta | ✅ PASS |
| META-04 interface agrupa por cofrinho com saldo, soma e livre | grupo por cofrinho | `tests/metas/test_cofrinhos.py:40-45` - `piggy-banks` com `balance`, `goals_total`, `free_balance` exatos; FE `metas-por-cofrinho.test.tsx:64-69` - região "Cofrinho Casa" com Viagem e Carro, sem Reserva, `R$ 700,00` / `R$ 500,00` / `R$ 200,00` | ✅ PASS |
| META-05 aviso com saldo livre negativo | "O cofrinho <nome> tem R$ <valor> a menos do que as metas somam." | FE `metas-por-cofrinho.test.tsx:80` - texto exato com `R$ 200,00`; `:83` e `:91` sem aviso quando o livre não é negativo | ✅ PASS |
| META-06 excluir a transferência remove o registro na mesma operação | meta 0,00; registro removido | `tests/metas/test_vinculo.py:92-96` - 204, meta `0.00`, registro e pernas removidos, corrente `1000.00`; `:103-105` pela perna do cofrinho; `:114-116` registro antigo | ✅ PASS |
| META-07 valor e data acompanham a transferência | mesmo valor e data | `tests/metas/test_vinculo.py:127-128` - registro `(350.00, 2026-09-20)` e meta `350.00`; `:135`, `:139` pendente → 0, efetivada → 500 | ✅ PASS |
| META-08 perna do cofrinho sai do cofrinho → registro removido | registro removido | `tests/metas/test_vinculo.py:149-150` - aporte com destino na poupança: registro removido, meta `0.00`; `:163-164` resgate com origem na poupança: removido, meta `500.00` | ✅ PASS |
| META-09 meta ficaria negativa | 400, "A meta <nome> ficaria negativa. Desfaça o resgate antes." | `tests/metas/test_vinculo.py:175-177` - exclusão: `400`, `detail == 'A meta Viagem A ficaria negativa. Desfaça o resgate antes.'`, banco idêntico; `:187-189` alteração do valor, igual | ✅ PASS |
| META-10 recálculo na implantação | valor pela META-01 | `tests/metas/test_correcao.py:64` - meta inflada (`999.99`) volta a `275.00`; `:40-47` a migração `0009` é um `RunPython` com `recalcular`; `:117-120` com o registro histórico de models | ✅ PASS |
| META-11 negativo vira zero com registro de correção; aviso único | zero, correção no histórico, antes/depois uma vez | `tests/metas/test_correcao.py:74-83` - `(0.00, -50.00)`, correção `DEPOSIT 50.00 'Correção do valor da meta'`, `correction == {'before': '-50.00', 'after': '0.00'}`; `:93-95` some depois do `dismiss-correction`; FE `historico-e-correcao.test.tsx:98` - "O valor desta meta foi corrigido de -R$ 50,00 para R$ 0,00."; `:103-104` "Entendi" chama a rota e esconde | ✅ PASS |

### P1: Aportes e resgates

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| META-12 aporte de outra conta cria transferência e registra só nessa meta | transferência conta → cofrinho; outra meta igual | `tests/metas/test_aporte_resgate.py:90-103` - registro ligado às duas pernas, pernas corretas, meta `300.00`, outra meta `0.00`, saldos `700.00`/`300.00`; `:111-113` próprio cofrinho → SALDO-17 e nada muda | ✅ PASS |
| META-13 aporte do saldo livre sem transferência | registro sem transação | `tests/metas/test_aporte_resgate.py:58-68` - 200, `current_amount '150.00'`, nenhuma transação nova, registro sem FKs, livre `50.00`; FE `aporte-e-resgate.test.tsx:66-68` - envia `from_free_balance: true` sem conta | ✅ PASS |
| META-14 aporte acima do saldo livre | 400, "O saldo livre do cofrinho é de R$ <valor>." | `tests/metas/test_aporte_resgate.py:72-75` - `400`, `'O saldo livre do cofrinho é de R$ 50,00.'`, nada gravado | ✅ PASS |
| META-15 resgate para outra conta cria transferência | cofrinho → conta | `tests/metas/test_aporte_resgate.py:122-133` - 200, `380.00`, pernas `(cofrinho, conta)`, saldos `380.00`/`620.00` | ✅ PASS |
| META-16 resgate para o saldo livre sem transferência | registro sem transação | `tests/metas/test_aporte_resgate.py:141-150` - nenhuma transação nova, meta `300.00`, cofrinho `500.00`, livre `200.00`; FE `aporte-e-resgate.test.tsx:127-128` - envia `to_free_balance` | ✅ PASS |
| META-17 resgate acima da meta | 400, "A meta tem R$ <valor> para resgatar." | `tests/metas/test_aporte_resgate.py:160-162` - `'A meta tem R$ 1.234,56 para resgatar.'` nos dois destinos, nada muda | ✅ PASS |
| META-18 resgate para outra conta acima do cofrinho | 400, "O cofrinho tem só R$ <valor>." | `tests/metas/test_aporte_resgate.py:175-180` - `'O cofrinho tem só R$ 300,00.'`, nada muda; 300,00 passa | ✅ PASS |
| META-19 valor < R$ 0,01 | 400 no campo do valor | `tests/metas/test_aporte_resgate.py:195-197` - `0.00`, `0`, `-5.00`, `0.001` nos quatro caminhos → 400 com só a chave `amount` | ✅ PASS |
| META-20 conta de outro usuário ou inexistente | 400 no campo, mesma mensagem (AD-010) | `tests/metas/test_aporte_resgate.py:210-212` - `{campo: ['Conta não encontrada.']}` igual para a conta de B e para o UUID inexistente, nos quatro campos | ✅ PASS |
| META-21 aporte em meta arquivada | 400, "Metas arquivadas não recebem aportes." | `tests/metas/test_aporte_resgate.py:231-237` - texto exato com conta e com saldo livre; resgate continua 200 | ✅ PASS |
| META-22 resgates simultâneos mantêm a meta ≥ 0 | só um passa | `tests/metas/test_concorrencia.py:56-62` - status `[200, 400]`, recusa `'A meta tem R$ 200,00 para resgatar.'`, meta `200.00`, um resgate (threads reais, `TransactionTestCase`) | ✅ PASS |
| META-23 meta atinge o alvo → concluída e aceita aportes | `COMPLETED`; aporte aceito | `tests/metas/test_cofrinhos.py:63`, `:70-71` - `COMPLETED`, aporte de 0,01 → `1000.01` | ✅ PASS |
| META-24 sugestão mensal pelo dia de Brasília, mínimo 1 mês | falta / meses | `tests/metas/test_cofrinhos.py:89-90` - 23h de 31/10 em Brasília: 2 meses, `300.00`; `:95-96` mínimo 1 mês, `600.00` | ✅ PASS |

### P1: Cadastro e consulta das metas

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| META-25 sem cofrinho cria um novo | cofrinho novo | `tests/metas/test_cadastro.py:27` - `('PIGGY_BANK', usuário, 'Cofrinho: Carro')`; `:32-34` segunda meta no mesmo cofrinho, um grupo | ✅ PASS |
| META-26 só cofrinho ativo do usuário | 400 para os demais | `tests/metas/test_cadastro.py:42-43` - corrente, cofrinho inativo e cofrinho de B → `400 {'account': ['Conta não encontrada.']}`; FE `formulario-e-exclusao.test.tsx:67` - só "Cofrinho Casa" entre as opções | ✅ PASS |
| META-27 nome vazio ou alvo < 0,01 | 400 no campo | `tests/metas/test_cadastro.py:51-58` - `['name']`; `{'target_amount': ['O valor deve ser maior que zero.']}` para 0, 0.00, -10; PATCH `['target_amount']`; nada gravado | ✅ PASS |
| META-28 trocar cofrinho com valor | 400, "Resgate o valor da meta antes de trocar o cofrinho." | `tests/metas/test_cadastro.py:69-71` - texto exato, cofrinho mantido; `:78-79` meta zerada troca | ✅ PASS |
| META-29 excluir meta com valor | 400, "Resgate o valor da meta antes de excluí-la." | `tests/metas/test_cadastro.py:89-91` - texto exato, meta mantida; FE `formulario-e-exclusao.test.tsx:153` - toast com a mensagem | ✅ PASS |
| META-30 última meta de cofrinho zerado → interface pergunta | pergunta e exclui o cofrinho se confirmado | `tests/metas/test_cadastro.py:96-99` - `200 {'piggy_bank_empty': True}`, cofrinho ainda ativo; `:105`, `:109` `False` com outra meta ou com saldo; FE `formulario-e-exclusao.test.tsx:95-98` - pergunta exata e `deleteAccount('cofrinho-1')`; `:111-112` sem confirmar não exclui | ✅ PASS |
| META-31 lista completa sem histórico | sem `deposits` | `tests/metas/test_cadastro.py:120-122` - lista (não paginada, 1 item) e detalhe sem `deposits` | ✅ PASS |
| META-32 histórico paginado (CONTRATO-02), mais recente primeiro, com tipo, valor, data, conta e transação | páginas de 20 | `tests/metas/test_historico.py:33-44` - `(45, 3, 1)`, 20 itens, ordem decrescente, página 3 com 5; `:55-59` campos `type, amount, date, account, account_name, transaction, is_correction`; FE `historico-e-correcao.test.tsx:52-60` - página 1 → 2 | ✅ PASS |
| META-33 recurso `metas` travado; transferências comuns liberadas | 403 `plan_locked`; transferência 201 | `tests/metas/test_historico.py:87-95` - rotas novas → `403 ('plan_locked', 'metas')`; transferência para o cofrinho 201 e saldo `100.00`; `test_trocos_configuracao.py:124-126`, `test_trocos_deposito.py:127-128` | ✅ PASS |
| META-34 exclusão definitiva apaga metas e registros | apagados; dados de B ficam | `tests/metas/test_historico.py:111-115` - metas, registros e transações de A apagados, registro de B fica; `test_trocos_configuracao.py:107-109` configuração e trocos | ✅ PASS |

### P1: Cofrinho de trocos

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| META-35 ativar guarda a meta e conta só despesas depois da ativação | meta e hora gravadas | `tests/metas/test_trocos_configuracao.py:49` - `(True, meta, AGORA)`; `tests/metas/test_trocos_geracao.py:93-94` - despesa criada antes da ativação não gera troco | ✅ PASS |
| META-36 troco até o próximo real; zero para inteiro | 12,30 → 0,70; 12,00 → nada | `tests/metas/test_trocos_geracao.py:51-54` - `0.40` (7,60) e `0.70` (12,30), `PENDENTE`; `:61` - 12,00 sem troco; `:84` sem conta, cofrinho e ajuste de saldo sem troco | ✅ PASS |
| META-37 interface mostra total e quantidade pendentes | total e quantidade | FE `cofrinho-de-trocos.test.tsx:51-54` - "Total pendente" `R$ 1,10`, "Juntando o troco de 2 despesas.", sem buscar transações | ✅ PASS |
| META-38 um aporte por conta de origem e cada troco depositado | 0,70 de A e 0,40 de B | `tests/metas/test_trocos_deposito.py:56-75` - `deposits` exatos, meta `1.10`, aportes por conta, saldos de origem, cofrinho `1.10`, cada troco `DEPOSITADO` ligado ao aporte da conta dele | ✅ PASS |
| META-39 pedido repetido não deposita de novo | nada novo | `tests/metas/test_trocos_deposito.py:83-86` - `{'deposits': [], 'discarded': 0}`, meta `1.10`, 2 registros | ✅ PASS |
| META-40 pedidos simultâneos depositam cada troco uma vez | uma vez | `tests/metas/test_trocos_deposito.py:164-169` - `[0, 2]` aportes, meta e cofrinho `1.10`, nenhum pendente (threads reais) | ✅ PASS |
| META-41 despesa com troco pendente editada/excluída | recalcula ou remove | `tests/metas/test_trocos_geracao.py:116` - 12,30 → 12,80 na conta B: `0.20` na conta B; `:131` deixa de gerar → removido; `:140` excluída → removido | ✅ PASS |
| META-42 troco já depositado não muda | aporte igual | `tests/metas/test_trocos_geracao.py:154-160` - trocos `DEPOSITADO` com `0.70`/`0.40`, aporte `1.10`, meta `1.10` | ✅ PASS |
| META-43 conta excluída → trocos descartados e a interface diz quantos | descartados; quantidade na tela | `tests/metas/test_trocos_deposito.py:94-98` - `discarded == 1`, troco `DESCARTADO`, meta `0.70`; FE `cofrinho-de-trocos.test.tsx:72` - "1 troco de conta excluída foi descartado." | ✅ PASS |
| META-44 meta arquivada/excluída pausa até escolher outra | `paused` | `tests/metas/test_trocos_configuracao.py:72`, `:76`, `:81` - arquivada e excluída → `paused True`, outra meta → `False`; `test_trocos_geracao.py:105-106` sem troco novo; `test_trocos_deposito.py:113-116` depósito recusado; FE `cofrinho-de-trocos.test.tsx:90-100` | ✅ PASS |
| META-45 desativar para de contar e mantém pendentes | pendentes depositáveis | `tests/metas/test_trocos_configuracao.py:95-98` - `pending_total '1.10'`, `pending_count 2`; `test_trocos_geracao.py:105`; `test_trocos_deposito.py:105-107` - depósito com os trocos desativados; FE `cofrinho-de-trocos.test.tsx:110-113` | ✅ PASS |

**Status**: ✅ 45/45 ACs com evidência no valor definido pela spec; nenhuma lacuna de precisão (META-19 e META-27 definem só "erro no campo", e os testes conferem a chave do campo).

---

## Edge Cases

- [x] Próprio cofrinho como origem do aporte → SALDO-17 (`tests/metas/test_aporte_resgate.py:111-113`)
- [x] Transferência entre dois cofrinhos muda só os saldos livres: coberta pela transferência comum para o cofrinho (`test_vinculo.py:66-68`); a variante cofrinho → cofrinho não tem teste próprio (observação 2)
- [x] Mover entre metas do mesmo cofrinho: resgate para o livre e aporte do livre (`test_aporte_resgate.py:141-150` e `:58-68`, separados)
- [x] Despesa paga pelo cofrinho reduz o livre e mostra o aviso (`test_vinculo.py:80-82`; FE `metas-por-cofrinho.test.tsx:80`)
- [x] Meta com R$ 500,00 num cofrinho com R$ 300,00: resgate até 300,00 (`test_aporte_resgate.py:173-180`)
- [ ] Divisão do salário com destino numa meta: depende da feature futura `gestao-do-salario` (observação 3)
- [x] Despesa de 12,30 editada para 12,80: troco 0,70 → 0,20 (`test_trocos_geracao.py:116`)
- [x] Registros antigos do rateio entram no recálculo (`test_correcao.py:49-66`)

---

## Discrimination Sensor

**Isolamento no backend**: worktree descartável `../fluxar-backend-mut` (detached em `3e6bea5`) e container avulso: `docker run --rm --network fluxar-backend_default --env-file <.env do backend> -e <variáveis do bloco environment do serviço> -v <worktree>:/app -w /app fluxar-backend-backend python manage.py test tests.metas --noinput`. Os mutantes rodaram depois do gate inteiro, para não disputar o banco de teste. Sem mutação, os 85 testes passaram no worktree (BASE). Cada mutação foi aplicada por um script que exige uma ocorrência única do trecho e revertida com `git checkout -- .` no worktree, conferido limpo (`git diff --quiet`) antes da seguinte.

**Isolamento no frontend**: sem worktree e sem junction de `node_modules`. A mutação foi aplicada no arquivo real, `npx vitest run tests/metas` rodou (29 testes) e o arquivo foi restaurado com `git checkout -- <arquivo>`. Depois, `git diff --quiet` e `git status --porcelain` estavam vazios e `git hash-object` era igual a `git rev-parse HEAD:<arquivo>` (CRLF preservado). Uma primeira tentativa com `sed` não alterou o arquivo (o `\r` não casou) e os 29 testes passaram; ela foi descartada sem contar e refeita com um script que confere a ocorrência única.

| # | File:line | Descrição | Killed? |
| - | --------- | --------- | ------- |
| M1 | `goals/valores.py:21` | `calcular` conta transferência pendente (`nao_efetivadas = Transaction.objects.none()`) | ✅ Killed (5 falhas: 4 em `test_valores`, 1 em `test_vinculo`) |
| M2 | `goals/vinculo.py:90` | Exclusão da transferência não remove o registro (`delete()` → `pass`) | ✅ Killed (4 falhas em `test_vinculo`) |
| M3 | `goals/vinculo.py:55` | Recusa da META-09 desligada (`if negativas and recusar:` → `if False:`) | ✅ Killed (2 falhas: exclusão e redução do aporte) |
| M4 | `goals/services.py:74` | Aporte do saldo livre sem checar o limite (`if amount > livre:` → `if False:`) | ✅ Killed (1 falha: `test_aporte_do_saldo_livre_sobe_a_meta_sem_transacao_e_respeita_o_limite`) |
| M5 | `goals/services.py:100` | Resgate confere o valor lido antes da trava (`meta.current_amount` → `goal.current_amount`) | ✅ Killed (2 falhas: os dois testes de resgates simultâneos) |
| M6 | `goals/trocos.py:79` | Troco gerado também para valor inteiro (`troco > 0` → `troco >= 0`) | ✅ Killed (2 falhas: valor inteiro e despesa que deixa de gerar troco) |
| M7 | `goals/trocos.py:163` | Depósito dos trocos sem marcar como depositado (`.update(aporte=aporte)`) | ✅ Killed (4 falhas: depósito por conta, reenvio, descartados e depósitos simultâneos) |
| F1 | `src/components/goals/GoalDepositForm.tsx:105` (FE) | `from_free_balance` não é enviado | ✅ Killed (1 falha: "o saldo livre do cofrinho envia from_free_balance, sem conta") |

Nota sobre M5: a trava da meta em si (`select_for_update` em `_travar`) não é discriminável isoladamente, porque a trava das contas (cofrinho) feita antes já serializa os resgates. Por isso o mutante remove o efeito da trava, conferindo o valor lido fora dela.

**Verificação do isolamento**: `git status --porcelain` vazio nos dois repositórios depois do sensor, exceto este `validation.md`. `git worktree list` mostra só a árvore principal nos dois, e a pasta `fluxar-backend-mut` não existe mais. Os únicos containers no ar são `fluxar-backend-backend-1` e `fluxar-backend-db-1` do compose.

**Sensor depth**: leve (8 mutações de comportamento, 7 no backend e 1 no frontend, por decisão do usuário)
**Result**: 8/8 killed, 0 survived - PASS

---

## Code Quality (nível leve, amostragem)

| Princípio | Status |
| --------- | ------ |
| Fonte única do valor | ✅ `goals/valores.py` (`calcular`, `recalcular`, `saldo_livre`); o rateio automático e o `sync_goals` saíram |
| Vínculo com as transações | ✅ `goals/vinculo.py`, chamado pelos signals; recusa por `ValidationError` desfeita pelo `atomic` |
| Ordem das travas | ✅ contas antes da meta (AD-045), com teste de deadlock (`tests/metas/test_ordem_das_travas.py`) |
| Reuso | ✅ `create_transfer`, `travar`, `reais`/`dinheiro`, `hoje`, `PaginacaoPadrao`, `RecursoLiberado('metas')` |
| Testes mapeados aos ACs | ✅ docstrings e comentários citam os IDs; asserções no texto exato das mensagens e nos valores |
| Testes antigos ajustados | ✅ mudanças coerentes com a regra nova, sem asserções retiradas sem substituta |
| Guidelines | AD-033 e AD-034 (testes no container e no vitest) seguidos |

---

## Observações (não bloqueiam)

1. **`goals/services.py:121-128`.** A docstring antiga de `get_progress` ainda fala em "atualizado por cada aporte ou resgate (manual ou automático)", que não vale mais depois da saída do rateio.
2. **Transferência entre dois cofrinhos.** O edge case é coberto pela regra geral (META-03), sem um teste cofrinho → cofrinho com metas nos dois lados.
3. **Divisão do salário (SALARIO-46).** Depende da feature `gestao-do-salario`; o caminho (`GoalService.aportar` + META-06) está testado, a divisão em si não existe ainda.
4. **Trava da meta redundante.** Com a trava do cofrinho feita antes, o `select_for_update` da meta não muda o resultado dos resgates simultâneos (nota de M5). Não é defeito; é defesa extra.
5. **Interface da META-28.** O backend recusa com o texto exato; o frontend repassa o erro por `tratarErro`, sem teste próprio da troca de cofrinho no formulário.
6. **Artefatos desatualizados.** O cabeçalho de `tasks.md` está `Status: In Progress`, e a rastreabilidade em `spec.md` está `Implemented`, sem `Verified`.
7. **Gates reduzidos.** Rodaram a suíte inteira do backend, o `makemigrations --check` e o `npm test`. `compileall`, `tsc`, lint e build não foram repetidos.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| META-01 a META-45 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (PASS)

**Spec-anchored check**: 45/45 ACs com evidência no valor da spec; nenhuma lacuna de precisão; 7 observações menores
**Sensor**: 8/8 mutações mortas (7 no backend, 1 no frontend)
**Gate**: backend 959 OK; frontend 299 testes OK

**Próximos passos**: opcionais. Atualizar a docstring de `get_progress`, um teste de transferência entre dois cofrinhos, e atualizar o cabeçalho de `tasks.md` e os status da rastreabilidade. Nenhum deles bloqueia.
