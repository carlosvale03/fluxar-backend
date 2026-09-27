# Isolamento entre usuarios Validation

## Validation: isolamento-entre-usuarios - FAIL ❌

**Date**: 2026-09-27
**Spec**: `.specs/features/isolamento-entre-usuarios/spec.md`
**Diff range**: `development..fix/isolamento-entre-usuarios` (base `f4f560e`, HEAD `0253099`, 33 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), evidence-or-zero

O motivo do FAIL: um caminho de leitura do ISOL-15 não foi tratado nem testado (orçamento mostra a categoria de outro usuário) e dois edge cases só têm cobertura parcial. As 32 mutações foram mortas e o gate passa. Os três gaps só aparecem com ligação cruzada já gravada, e a migração `0007_corrige_isolamento` apaga essa ligação no mesmo deploy. Por isso a gravidade é baixa, mas as falhas existem no código e ficam sem teste.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T28 (T25 a T28 acrescentadas na execução) | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md`, com os "Done when" marcados |

---

## Gate Check

- **Gate command**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`
- **Resultado**: exit 0. `compileall` sem erro; `makemigrations --check`: "No changes detected"; `Ran 138 tests ... OK`
- **Passaram**: 138; **falharam**: 0; **pulados**: 0
- **Testes antes da feature**: 0 (`api/tests.py` e `data_exchange/tests.py` são o modelo vazio do Django)
- **Testes depois da feature**: 138 (todos em `tests/isolamento/`)
- **Delta**: +138
- **CI**: `.github/workflows/ci-backend.yml` dispara em push e PR para `main` e `development`, sem `paths`, com serviço `postgres:15`, e o último passo é `python manage.py test --noinput`. Os critérios de T1 e da AD-033 foram atendidos.

---

## Spec-Anchored Acceptance Criteria

Helper usado nas recusas: `tests/isolamento/base.py:100-106` (`assert_mesma_recusa`). Ele confere status 400 nas duas respostas (`:100-101`), o campo no corpo (`:102`), a igualdade exata dos corpos alheio e inexistente (`:104`) e, quando recebe `mensagem`, `resp.data[campo] == [mensagem]` (`:106`). Toda chamada de escrita abaixo passa a mensagem em português. O próprio helper é testado: `test_base.py:44-70` confirma que ele falha quando status, campo, chaves ou mensagem divergem.

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| ISOL-01 (invariante: toda relação só com objetos do dono) | Nenhuma relação gravável aceita objeto de outro usuário | `tests/isolamento/test_inventario.py:121` - `assertIsInstance(relacao, OwnedPrimaryKeyRelatedField)` para todo campo de relação gravável das rotas e dos módulos `serializers`; `:125` - `assertEqual(ESPERADAS - verificadas, set())` (17 relações); para os dados gravados, `test_correcao.py:83` - `assertEqual(find_cross_links(apps), [])` | ✅ |
| ISOL-02 transação (criar/editar) com conta, cartão, categoria, tag ou conta-destino de B | 400, erro no campo, mesma mensagem de inexistente, nada gravado | `test_escrita_transacoes.py:73` - `assert_mesma_recusa(resp_alheio, resp_inexistente, campo, mensagem)`; `:74` - `assertEqual(Transaction.objects.count(), total_antes)`; `:75` → `:55-60` saldo de B = 1000.00 e nenhuma transação ligada a B; edição `:136` e `:137` - `assertEqual(self.estado(t), antes)`; casos em `:77-90` e `:140-153` | ✅ |
| ISOL-03 edição em lote com categoria de B | 400 em `category`, nenhuma ocorrência alterada | `test_escrita_lote.py:50` - `assert_mesma_recusa(resp, resp_inexistente, 'category', 'Categoria não encontrada.')`; `:52` - `assertEqual(self.estado_da_serie(), antes)`; `:53` - 3 ocorrências | ✅ |
| ISOL-04 categoria-pai de B (criar/editar) | 400 em `parent`, nada gravado | `test_escrita_categorias.py:37` - `assert_mesma_recusa(resp, resp_inexistente, 'parent', 'Categoria não encontrada.')`; `:39-40` contagem e nome; edição `:51`, `:54` - `assertIsNone(categoria.parent_id)` | ✅ |
| ISOL-05 orçamento com categoria de B (criar/editar) | 400 em `category`, nada gravado | `test_escrita_orcamentos.py:28` - `assert_mesma_recusa(..., 'category', 'Categoria não encontrada.')`; `:29-30` estado igual e nenhum orçamento em 10/2026; edição `:49`, `:51-52` | ✅ |
| ISOL-06 meta com conta de B (criar/editar) | 400 em `account`, nada gravado | `test_metas.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account', 'Conta não encontrada.')`; `:25-27` contagens de metas e contas; edição `:34`, `:35` - conta continua `a.cofrinho` | ✅ |
| ISOL-07 monitor de foco com categoria ou tag de B | 400 no campo, nada gravado | `test_monitor_foco.py:20` - `assert_mesma_recusa(resp, resp_inexistente, campo, mensagem)`; `:21` estado igual; casos `:23-30` (categoria de B, categoria-modelo, tag de B) | ✅ |
| ISOL-08 cartão com conta de pagamento de B (criar/editar) | 400 em `account_id` | `test_cartao_fatura.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')`; `:25-26`; edição `:33-34` | ✅ |
| ISOL-09 compra no cartão, transferência, pagamento de fatura, aporte/resgate e importação | 400 no campo do corpo | transferência e compra: `test_escrita_transferencia_cartao.py:40` + `:41-44` (nenhuma transação ou fatura criada, saldo e fatura de B intactos), casos `:48-95`; pagamento: `test_cartao_fatura.py:93` + `:94-98`; aporte/resgate nos 4 nomes de campo: `test_aporte_resgate.py:32` + `:33-36`, casos `:53-71`; importação: `test_importacao.py:76-77` (OFX) e `:84-85` (planilha) | ✅ |
| ISOL-10 categoria-modelo sem dono | Recusa igual à de inexistente | `test_campo.py:70-72` - `assert_recusa({'category': modelo}, 'category', 'Categoria não encontrada.')` (`:45` - `assertEqual(serializer.errors, {campo: [mensagem]})`); pela API: `test_escrita_categorias.py:16`+`:37`, `test_escrita_lote.py:43`+`:50`, `test_escrita_orcamentos.py:35-36`, `test_escrita_transferencia_cartao.py:85-89`, `test_monitor_foco.py:26-27`; helper: `test_campo.py:129`+`:135` | ✅ (sem caso na API para `TransactionSerializer.category`, mas o campo é a mesma classe) |
| ISOL-11 formato da recusa | 400, erro no campo, mesma mensagem de inexistente, texto em português | `base.py:100-106` (acima); UUID malformado `test_campo.py:74-77`; tipo errado `:79-82`; sem `request` `:96-100`; `get_owned_or_400` `:122-135` - `assertEqual(ctx.exception.detail, {'campo_x': [mensagem]})` | ✅ |
| ISOL-12 ID de B no endereço (ler/editar/excluir) | 404 igual ao de inexistente | `test_endereco_filtros.py:55-57` - `assertEqual(resp.status_code, 404)` e `assertEqual(resp.data, resp_inexistente.data)` para GET/PATCH/PUT/DELETE de conta, cartão, fatura (`pay`/`unpay` 404; PATCH/DELETE 405 igual), categoria, tag, transação, orçamento, meta (`deposit`/`withdraw`/`history`) e monitor (`:67-138`), com o objeto de B intacto; relatório de tag `test_relatorios.py:46-48` e UUID malformado `:55-56` | ✅ |
| ISOL-13 filtros com ID de B | Resultado vazio, igual ao de inexistente | `test_endereco_filtros.py:158` - `assertEqual(resp.data['results'], [])`; `:159` - `assertEqual(resp.data, resp_inexistente.data)`; `:161` controle positivo com ID de A; `accountId`/`account`, `credit_card`, `invoice`, `categoryId`/`category`, `tagIds` (`:163-178`), orçamentos `category` (`:180-181`); exportação PDF/XLS `:201-203` | ✅ |
| ISOL-14 listas e somas só com dados do dono | Subcategorias, transações da conta, compras do cartão, metas do cofrinho, parceira | subcategorias `test_leitura_categorias.py:25`, `:30`; saldo `test_saldo_limite.py:23` - `get_balance == 900.00` e `:29` dashboard; limite `:44` - `available_limit == 1700.00`; total da fatura `test_total_fatura.py:33` (350.00), `:41` (300.00); metas do cofrinho `test_signal_metas.py:27-28`, `:44-45`; parceira `test_leitura_transacoes.py:70`, `test_signal_transferencia.py:42`, `:53`, `test_escrita_transacoes.py:219`; subcategorias no monitor `test_relatorios.py:34` (40.0) | ⚠️ Coberto no que foi tratado; `BudgetService.get_budget_usage` (`budgets/services.py:24`) soma `budget.category.subcategories` sem filtro do dono e não tem teste (gap 2) |
| ISOL-15 respostas só com objetos relacionados do dono | Nome da conta, categoria, subcategorias, tags e conta da meta, só do dono | transação `test_leitura_transacoes.py:43-50`; nome da conta da parceira `:88` (`'Desconhecida'`); pai da categoria `test_leitura_categorias.py:40-41`; meta `test_metas.py:87-88`, `:96-97`; histórico `test_historico_meta.py:30`; monitor `test_monitor_foco.py:61-64`; cartão `test_cartao_fatura.py:63-64`, `:70-71`; relatório avançado `test_relatorio_avancado.py:34-35`, `:47-48` | ❌ GAP: `BudgetSerializer.category_detail` (`budgets/serializers.py:13`) mostra a categoria de outro usuário. Sonda P1: um orçamento de A ligado à categoria de B devolve `category_detail.name == 'Mercado B'` em `GET /api/budgets/`. Sem código nem teste (gap 1) |
| ISOL-16 verificação lista cada ligação com tipo, ID e relação | Uma linha por registro cruzado | `test_verificacao.py:31` - `assertEqual(como_tuplas(links), sorted(registros.esperadas))` (18 ligações, cada linha da tabela do design, mais parcela e série de origem); `:22` - base limpa → `[]`; comando `test_comando.py:35-36`; saída só com tipos e IDs (AD-019) `:46-50` | ✅ |
| ISOL-17 correção desfaz cada ligação conforme a tabela | Relações anuladas; orçamentos, monitores e aportes excluídos | `test_correcao.py:58` - `relatorio.ligacoes == 18`; `:66` - `assertIsNone(getattr(transacao, f'{relacao}_id'))`; `:70` - tag de B removida; `:73` série; `:75-77` pai, conta do cartão e conta da meta nulas; `:79-81` Budget, monitores e aporte excluídos; `:83` sem sobras; idempotência `:117-118`; dados sem ligação intactos `:146-147`; migração `test_migracao.py:37`, com registro histórico `:47-49`, dependências `:20-30` | ✅ |
| ISOL-18 recálculo do saldo pela SALDO-01 | Saldo = inicial + entradas efetivadas − saídas efetivadas, só do dono | `test_correcao.py:87` antes = 1400.00; `:93` - `balance == 900.00` (1000 − 100; a receita pendente fica fora); fatura `:95` (120.00); meta `:97` (250.00, AD-028); `test_comando.py:61` e `test_migracao.py:39`, `:50` (1000.00) | ✅ |

**Status**: ❌ 1 AC com gap (ISOL-15), 1 AC com cobertura parcial (ISOL-14) e 16/18 ACs com evidência que confere com o resultado definido na spec.

**Regra de payload e conjunção**: atendida. As recusas conferem status, campo, mensagem e corpo idêntico, e também o estado gravado (contagens, `estado()`, saldo e fatura de B). As leituras conferem valores (`None`, listas exatas de IDs e nomes, somas decimais), não só a existência de chaves.

---

## Edge Cases

- [x] ID inexistente e ID de outro usuário dão respostas idênticas: `base.py:104` (corpo) e `test_endereco_filtros.py:57` (endereço).
- [x] Tag de outro usuário entre tags próprias recusa a transação inteira: `test_escrita_transacoes.py:100-102`, `:164-166`; compra `test_escrita_transferencia_cartao.py:94`; campo `test_campo.py:87-90`.
- [x] Transferência com origem própria e destino de outro usuário: `test_escrita_transferencia_cartao.py:54-58`.
- [x] Conta própria excluída: fora do escopo, vai para SALDO-35. O campo mantém o filtro `is_active` (`test_campo.py:102-106`).
- [ ] ⚠️ Mapeamento de importação para uma conta de B: coberto só em parte. A conta padrão de B recusa a importação inteira (`test_importacao.py:76`). O mapeamento para a conta de B não grava nada em B (`test_importacao.py:99-101`), mas a spec diz que a linha é "rejeitada como 'Conta não mapeada' (IMPORT-21)", e isso não é conferido. Sonda P3: resposta 200 com `{'imported': 1, 'errors': 0}`; a linha foi importada com `account=None` e não foi rejeitada. A rejeição depende da IMPORT-21, de outra spec (gap 4).
- [ ] ⚠️ Edição de transação própria já ligada à conta de B antes da correção: coberto só em parte. O PUT que reenvia `account` de B recebe 400 (`test_escrita_transacoes.py:192-195`). Sonda P2: um PATCH só com `description` recebe 200, grava a descrição e mantém a ligação cruzada. A spec diz "a gravação é recusada até a ligação cruzada ser desfeita", sem dizer se isso vale para uma edição parcial que não manda a relação (gap 3, spec-precision).

---

## Success Criteria

| Critério | Evidência | Status |
| -------- | --------- | ------ |
| Um teste automatizado percorre todas as relações graváveis com IDs de outro usuário: 400 em todas, com o corpo de ID inexistente | O inventário (`test_inventario.py:121`, `:125`) garante o tipo do campo nas 17 relações. Cada relação tem o próprio teste HTTP com `assert_mesma_recusa` (tabela acima), e as views sem serializer também (lote, aporte/resgate, importação). A cobertura é da suíte, não de um único teste | ✅ |
| Depois da correção em produção, a verificação não lista nenhum registro | É operacional. O equivalente em teste está em `test_correcao.py:83`, `test_comando.py:59`, `:62` e `test_migracao.py:37` | ⏭️ Só verificável em produção |
| Nenhum endpoint devolve dado de outro usuário no teste com dois usuários | `GET /api/budgets/` devolve o nome da categoria de B quando há um orçamento forjado (sonda P1) | ❌ (gap 1) |

---

## Discrimination Sensor

**Profundidade**: ampliada (P0, segurança): 32 mutações de comportamento, feitas à mão.
**Isolamento**: `git worktree add --detach ../fluxar-backend-verif HEAD`. Os testes rodaram num container avulso, `docker run --rm --network fluxar-backend_default --env-file .env -e DB_HOST=db -v <worktree>:/app fluxar-backend-backend python manage.py test tests.isolamento --noinput`, contra o serviço `db` do compose. Cada mutação foi aplicada e depois revertida por um script, e a worktree foi removida com `git worktree remove --force`. `git status --porcelain` da árvore real: vazio antes e vazio depois (bate com o baseline). Não houve `git stash`.
**Controle**: a worktree sem mutação rodou 138 testes e passou; M01 foi morta, o que mostra que o container montou a worktree.

| Mutação | File:line | Descrição | Killed? |
| ------- | --------- | --------- | ------- |
| M01 | `core/fields.py:44` | `get_queryset` sem filtro do dono | ✅ Killed (42 falhas) |
| M02 | `core/fields.py:47` | Mensagem diferente ("Sem permissão.") para ID de outro usuário | ✅ Killed (40) |
| M03 | `core/fields.py:43` | Sem `request`, o campo aceita qualquer objeto | ✅ Killed (1) |
| M04 | `core/fields.py:58` | `get_owned_or_400` sem filtro do dono | ✅ Killed (12) |
| M05 | `accounts/services.py:21` | `get_balance` sem filtro do dono | ✅ Killed (1) |
| M06 | `accounts/services.py:52` | Limite do cartão soma compras de outro usuário | ✅ Killed (1) |
| M07 | `goals/signals.py:38` | Signal de metas sem filtro do dono | ✅ Killed (2) |
| M08 | `core/isolation.py:40` | Correção e verificação pulam a linha do Budget | ✅ Killed (4) |
| M09 | `core/isolation.py:150` | Correção não recalcula saldos | ✅ Killed (4) |
| M10 | `core/isolation.py:151` | Correção não recalcula faturas | ✅ Killed (1) |
| M11 | `core/isolation.py:152` | Correção não recalcula metas | ✅ Killed (1) |
| M12 | `core/isolation.py:72` | Verificação e correção ignoram tags | ✅ Killed (4) |
| M13 | `transactions/views.py:196` | `bulk_update` volta a não validar a categoria | ✅ Killed (3) |
| M14 | `transactions/serializers.py:35` | `get_subcategories` sem filtro do dono | ✅ Killed (1) |
| M15 | `transactions/serializers.py:29` | Categoria mostra pai de outro usuário | ✅ Killed (1) |
| M16 | `transactions/serializers.py:126` | Transação mostra conta de outro usuário | ✅ Killed (1) |
| M17 | `transactions/serializers.py:132` | Transação mostra tags de outro usuário | ✅ Killed (1) |
| M18 | `transactions/serializers.py:166` | `related_transaction` sem filtro do dono | ✅ Killed (1) |
| M19 | `transactions/serializers.py:258` | Troca de conta da parceira sem filtro do dono | ✅ Killed (1) |
| M20 | `transactions/signals.py:91` | Total da fatura soma compras de outro usuário | ✅ Killed (2) |
| M21 | `transactions/signals.py:108` | `sync_transfer_update` sem filtro do dono | ✅ Killed (1) |
| M22 | `transactions/signals.py:125` | `sync_transfer_delete` sem filtro do dono | ✅ Killed (1) |
| M23 | `goals/views.py:103` | `history` sem filtro do dono | ✅ Killed (2) |
| M24 | `goals/serializers.py:64` | `GoalSerializer.deposits` sem filtro do dono | ✅ Killed (1) |
| M25 | `goals/serializers.py:52` | Meta mostra conta de outro usuário | ✅ Killed (1) |
| M26 | `goals/views.py:49` | Aporte manda o erro para o campo errado | ✅ Killed (1) |
| M27 | `reports/services.py:577` | Relatório avançado inclui monitor ligado a dado de outro usuário | ✅ Killed (2) |
| M28 | `reports/services.py:586` | Monitor soma subcategoria de outro usuário | ✅ Killed (1) |
| M29 | `reports/services.py:1141` | `tag_id` malformado volta a dar 500 | ✅ Killed (1 erro) |
| M30 | `reports/serializers.py:32` | Monitor mostra tag de outro usuário | ✅ Killed (1) |
| M31 | `accounts/serializers.py:77` | Cartão mostra conta de outro usuário | ✅ Killed (1) |
| M32 | `data_exchange/views.py:27` | Importação OFX aceita conta de outro usuário | ✅ Killed (1) |

Sensor: 32/32 mortas. Todos os caminhos tratados pela feature se mostraram discriminados pelos testes.

**Sondas extras** (arquivo temporário só na worktree, já removida). Elas não são mutações; servem para caracterizar caminhos que a suíte não confere:

| Sonda | Cenário | Observado |
| ----- | ------- | --------- |
| P1 | Orçamento de A gravado à força com a categoria de B; `GET /api/budgets/` como A | 200, `category_detail.name == 'Mercado B'` |
| P2 | Transação de A com `account` de B gravada à força; `PATCH {'description': 'Nova'}` | 200, descrição gravada, ligação cruzada mantida |
| P3 | Planilha com mapeamento `{'Banco B': conta de B}` e sem conta padrão | 200, `imported: 1, errors: 0`, linha gravada com `account=None` |

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Mínimo de código | ✅ Campo e helper únicos em `core/fields.py`; os `__init__` que filtravam à mão foram removidos |
| Mudanças cirúrgicas | ✅ |
| Sem scope creep | ✅ T25 a T28 cobrem caminhos de ISOL-14 e ISOL-15 que a tabela do design não listava |
| Segue os padrões do projeto | ✅ |
| Spec-anchored (valores conferem com a spec) | ⚠️ Gaps 1 a 4 |
| Cobertura por camada (campo com todos os ramos; rotas com caminho feliz, recusa e erro) | ✅ `test_campo.py` cobre todos os ramos da matriz; cada rota tem caminho feliz e recusa |
| Todo teste mapeia um AC, edge case ou Done-when | ✅ |
| Diretrizes documentadas | nenhuma além de AD-010, AD-019, AD-024, AD-032 e AD-033, todas seguidas. Nenhum `print` foi acrescentado no diff; a saída do comando só traz tipos e IDs (`test_comando.py:46-50`) |
| SPEC_DEVIATION | `core/isolation.py:28-33`: `parent_transaction` e `recurring_source` entram na correção além da tabela do design. Justificada e coberta (`ligacoes.py:73-74`, `test_correcao.py:63-66`) |

---

## Spec-precision gaps

1. **Edge case 6 (ISOL-02/ISOL-17)**: a spec diz que "a gravação é recusada até a ligação cruzada ser desfeita", mas não diz se isso vale para um PATCH que não manda a relação cruzada. Hoje esse PATCH passa (sonda P2).
2. **Edge case 5 (IMPORT-21)**: a spec diz que a linha é rejeitada como "Conta não mapeada", uma regra de outra spec (importação). O teste confere só o isolamento, sem gravação em B, e o código hoje importa a linha sem conta (sonda P3).
3. **ISOL-13 "relatório"**: o único filtro por ID nos relatórios é o `tag_id` do relatório de tag, que responde 404 e não "resultado vazio". Ele bate com "como para um ID inexistente" (`test_relatorios.py:46-48`), mas não com a palavra "vazio".

---

## Ranked gaps e Fix Plans

### Fix 1 (Major): ISOL-15, orçamento mostra a categoria de outro usuário

- **Root cause**: `BudgetSerializer.category_detail = CategorySerializer(source='category')` (`budgets/serializers.py:13`) não confere o dono; o caminho não estava na tabela de leituras do design.
- **Fix task**: em `BudgetSerializer.to_representation`, anular `category` e `category_detail` quando `instance.category.user_id != instance.user_id`, como já é feito em `TransactionSerializer`. Teste em `tests/isolamento/`: orçamento de A gravado à força com a categoria de B, e `GET /api/budgets/` e `/api/budgets/{id}/` sem `'Mercado B'` nem o ID de B.
- **Mitigação atual**: a migração `0007` exclui esses orçamentos (`test_correcao.py:79`), e a API não deixa criar novos (ISOL-05).

### Fix 2 (Minor): ISOL-14, uso do orçamento soma subcategorias sem filtro do dono

- **Root cause**: `budgets/services.py:24` usa `budget.category.subcategories.values_list('id')` sem `user_id=budget.user_id`.
- **Fix task**: filtrar as subcategorias por `user_id=budget.user_id` e testar com uma subcategoria de B pendurada à força na categoria do orçamento de A, com uma transação de A ligada a ela, conferindo `total_spent`.
- **Mitigação atual**: a transação só é somada se for de A (`user=budget.user`), e a correção desfaz a ligação da subcategoria.

### Fix 3 (Minor, spec-precision): edge case 6, edição parcial de transação já cruzada

- **Decisão pendente**: o PATCH sem a relação cruzada deve ser recusado? Se sim, validar no `TransactionSerializer.validate` a relação atual da instância (conta, cartão, categoria, tags) e testar o PATCH só com `description`. Se não, ajustar o texto do edge case.

### Fix 4 (Minor, spec-precision / outra spec): edge case 5, linha mapeada para conta de B

- **Decisão pendente**: implementar a rejeição "Conta não mapeada" aqui ou deixá-la com a IMPORT-21. Em qualquer caso, o teste deve conferir o resultado da linha (`errors`/`imported`), e não só a ausência de gravação em B.

---

## Requirement Traceability Update

A verificação não edita `spec.md`. Os status abaixo são a recomendação para quem aplicar os fixes:

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| ISOL-01 a ISOL-13, ISOL-16 a ISOL-18 | Pending | ✅ Verified |
| ISOL-14 | Pending | ⚠️ Verified com gap menor (Fix 2) |
| ISOL-15 | Pending | ❌ Needs Fix (Fix 1) |

---

## Summary

**Overall**: ❌ Not Ready. Os gaps têm gravidade baixa, porque a migração no mesmo deploy remove a condição que os dispara.

**Spec-anchored check**: 16/18 ACs conferem com a spec; ISOL-15 tem gap e ISOL-14 tem gap parcial; 3 spec-precision gaps.
**Sensor**: 32/32 mutações mortas.
**Gate**: 138 passaram, 0 falharam, 0 pulados.

**O que funciona**: recusa por campo com mensagem única em todas as relações graváveis, 404 no endereço e lista vazia nos filtros, leituras de transação, categoria, meta, monitor, cartão, saldo, limite, fatura, signals e relatórios, e a verificação, a correção, o comando e a migração, com recálculo SALDO-01.

**Próximos passos**: Fix 1 e Fix 2 como tarefas de implementação; decidir Fix 3 e Fix 4 com o usuário; depois, nova verificação.

---

## validate_state

`python validate_state.py isolamento-entre-usuarios --root .` terminou com exit 1, que é o esperado para um FAIL:

```
ERROR isolamento-entre-usuarios: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)
validate_state: 1 error(s) across [isolamento-entre-usuarios]
```
