# Isolamento entre usuarios Validation

## Validation: isolamento-entre-usuarios (rodada 3) - FAIL ❌

**Date**: 2026-09-27
**Spec**: `.specs/features/isolamento-entre-usuarios/spec.md`
**Diff range**: `development..fix/isolamento-entre-usuarios` (base `f4f560e`, HEAD `9f90936`; Phase 7 = `99dcea1`, `75e7f5b`, `24d7ec7`, `9f90936`)
**Verifier**: sub-agente independente da rodada 3 (autor ≠ verificador), evidence-or-zero. Os relatórios das rodadas 1 e 2 não valeram como evidência: conferi cada citação linha a linha no HEAD atual.

Resumo: T32 a T35 fecharam os quatro gaps da rodada 2. Cada mudança tem teste que mata a mutação direta (N01, N02, N04 a N09). O FAIL vem de dois achados novos. O primeiro é um caminho de leitura confirmado por sonda: com uma ligação cruzada já gravada numa transação de A, os relatórios e a exportação mostram a A o nome da categoria, da tag e da conta de B (ISOL-15 e critério de sucesso 3). O segundo é o mutante N03, que sobrevive na T32. A gravidade é a mesma dos gaps das rodadas 1 e 2: tudo depende de uma ligação cruzada gravada antes da correção. A sonda mostra que a correção (`fix_cross_links`, a mesma da migração `0007`) elimina o vazamento. **Esta é a rodada 3, a última do ciclo. Os gaps restantes vão para decisão do usuário.**

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T31 | ✅ Done | Marcadas `✅ Complete` em `tasks.md` (35 de 35 tarefas) |
| T32 (pagamento e estorno só do dono) | ✅ Done | `99dcea1`; `accounts/services.py:135`, `:240` |
| T33 (`ALL_FUTURE` só do dono) | ✅ Done | `75e7f5b`; `transactions/serializers.py:295-296` |
| T34 (`bulk_import` sem categoria alheia) | ✅ Done | `24d7ec7`; `budgets/views.py:96-98` |
| T35 (campo sem `request`) | ✅ Done | `9f90936`; `tests/isolamento/test_campo.py:103-125` |

---

## Gate Check

- **Gate command**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`
- **Resultado**: exit 0. `compileall` sem erro. `makemigrations --check` diz "No changes detected". A suíte mostra `Found 160 test(s).`, `Ran 160 tests in 15.308s` e `OK`.
- **Passaram**: 160; **falharam**: 0; **pulados**: 0
- **Contagem de testes**: 0 antes da feature, 138 na rodada 1, 152 na rodada 2 e 160 agora. A Phase 7 acrescentou 8 testes (3 + 2 + 2 + 1). `git diff --stat 8b3da34..HEAD -- tests` mostra 3 arquivos novos e 25 linhas acrescentadas a `test_campo.py`. Nenhuma asserção antiga foi removida ou enfraquecida.
- **Prints**: o diff não acrescenta nenhum `print(` fora de `tests/` (AD-019). As linhas `DEBUG` da saída já existiam antes da feature.
- **Nota**: o `import` novo em `test_campo.py:3` desloca uma linha as citações antigas desse arquivo. As citações abaixo já estão corrigidas.

---

## Spec-Anchored Acceptance Criteria

Helper das recusas: `tests/isolamento/base.py:94-106` (`assert_mesma_recusa`). Ele confere:
- 400 nas duas respostas (`:100-101`);
- o campo (`:102`);
- as mesmas chaves (`:103`);
- o corpo idêntico ao de um ID inexistente (`:104`);
- `resp.data[campo] == [mensagem]` (`:106`).

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| ISOL-01 invariante | Registro ligado só a objetos do dono, ou a nenhum | `test_inventario.py:121` - `assertIsInstance(relacao, OwnedPrimaryKeyRelatedField)`; `:125` - `assertEqual(ESPERADAS - verificadas, set(), ...)`; dados gravados: `test_correcao.py:83` - `assertEqual(find_cross_links(apps), [])`; **cópia interna (T34)**: `test_importar_orcamentos.py:114` - `assertEqual((imported_count, skipped_count), (1, 2))`, `:115-118` - só `(A, categoria de A, 300.00)` em outubro, `:119-120` - nenhum orçamento novo nas categorias de B e modelo, `:126-127` | ✅ (nota residual: o "Restante" do pagamento parcial copia a categoria e as tags da compra de A; ver notas) |
| ISOL-02 transação com conta, cartão, categoria ou tag de B | 400 no campo, mesma mensagem de inexistente, nada gravado | criação: `test_escrita_transacoes.py:73` - `assert_mesma_recusa(...)`, `:74` - `assertEqual(Transaction.objects.count(), total_antes)`; edição: `:136`, `:137` - `assertEqual(self.estado(t), antes)`; edição de transação já cruzada: `test_edicao_parcial.py:65-67` | ✅ |
| ISOL-03 edição em lote com categoria de B | 400 em `category`, nenhuma ocorrência alterada | `test_escrita_lote.py:50` - `assert_mesma_recusa(resp, resp_inexistente, 'category', 'Categoria não encontrada.')`; `:52` - `assertEqual(self.estado_da_serie(), antes)` | ✅ |
| ISOL-04 categoria-pai de B | 400 em `parent`, nada gravado | `test_escrita_categorias.py:37` - `assert_mesma_recusa(..., 'parent', 'Categoria não encontrada.')`; `:54` - `assertIsNone(categoria.parent_id)` | ✅ |
| ISOL-05 orçamento com categoria de B | 400 em `category`, nada gravado | `test_escrita_orcamentos.py:28` - `assert_mesma_recusa(..., 'category', ...)`; `:29` - `assertEqual(self.estado_dos_orcamentos(), antes)` | ✅ |
| ISOL-06 meta com conta de B | 400 em `account` | `test_metas.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account', 'Conta não encontrada.')` | ✅ |
| ISOL-07 monitor com categoria ou tag de B | 400 no campo | `test_monitor_foco.py:20` - `assert_mesma_recusa(resp, resp_inexistente, campo, mensagem)` | ✅ |
| ISOL-08 cartão com conta de B | 400 em `account_id` | `test_cartao_fatura.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')` | ✅ |
| ISOL-09 compra no cartão, transferência, pagamento de fatura, aporte ou resgate, importação | 400 no campo do corpo | `test_escrita_transferencia_cartao.py:40`; `test_cartao_fatura.py:93` (`account_id`); `test_aporte_resgate.py:32`; `test_importacao.py:76` (OFX) e `:84` (planilha) - todos `assert_mesma_recusa(...)` | ✅ |
| ISOL-10 categoria-modelo | Recusa igual à de inexistente | `test_campo.py:71-74` via `assert_recusa` → `:46` - `assertEqual(serializer.errors, {campo: [mensagem]})`; **sem `request` e com usuário anônimo (T35)**: `test_campo.py:109`, `:125` - `assertEqual(serializer.errors, {campo: [mensagem]})`; `bulk_import` com categoria-modelo: `test_importar_orcamentos.py:120` | ✅ (M13 agora morta: N08, N09) |
| ISOL-11 formato da recusa | 400, erro no campo, mesma mensagem em português | `base.py:100-106`; corpo exato: `test_edicao_parcial.py:66` - `assertEqual(resp.data, {campo: [mensagem]})`; `test_escrita_transacoes.py:101` - `{'tags': ['Tag não encontrada.']}` | ✅ |
| ISOL-12 ID de B no endereço | 404 igual a inexistente | `test_endereco_filtros.py:56` - `assertEqual(resp_inexistente.status_code, status, ...)`; `:57` - `assertEqual(resp.data, resp_inexistente.data)` | ✅ |
| ISOL-13 filtros com ID de B | Vazio, igual a inexistente | `test_endereco_filtros.py:158` - `assertEqual(resp.data['results'], [], ...)`; `:159` - igual à resposta de um ID inexistente; exportação `:201-203`; relatório de tag `test_relatorios.py:46` (404, igual a inexistente) | ✅ (nota de precisão: o relatório de tag é de recurso único) |
| ISOL-14 listas e somas só com dados do dono | Subcategorias, transações da conta, compras do cartão, metas do cofrinho, parceira | subcategorias `test_leitura_categorias.py:25`; saldo `test_saldo_limite.py:23` - `Decimal('900.00')`; limite `:44` - `Decimal('1700.00')`; total da fatura `test_total_fatura.py:33` - `Decimal('350.00')`; metas `test_signal_metas.py:27`; parceira `test_leitura_transacoes.py:70`; uso do orçamento `test_uso_orcamento.py:33`. **Pagamento e estorno (T32)**: `test_pagamento_fatura.py:55` - `assertEqual(self.estado(compra_b), antes_b)` (usuário, status, conta, valor, fatura, `payment_date`, descrição), `:56-58` - compra de A `('COMPLETED', cofrinho de A, 100.00)`, `:60` - saldo do cofrinho de A `Decimal('-100.00')`, `:61` - saldo de B inalterado; parcial `:70`, `:75-79`; estorno `:91-94`. **`ALL_FUTURE` (T33)**: `test_parcelas_futuras.py:49-50` - a parcela de B mantém `(B, 50.00, categoria de B)` e `updated_at`; `:53-56` e `:68-71` - as parcelas de A mudam para `(A, 10.00, subcategoria de A)`; `:65` - a parcela anterior de A fica inalterada | ✅ (mutante N03 sobrevive; ver gap 2) |
| ISOL-15 respostas só com relacionados do dono | Nome da conta, categoria, subcategorias, tags, conta da meta | transação `test_leitura_transacoes.py:43` - `assertIsNone(dados['account'])`; `:88` - `'Desconhecida'`; orçamento `test_leitura_orcamentos.py:36-41`; meta via N18 (morta) | ❌ **GAP**: relatórios e exportação montam nomes de relacionados a partir das transações de A sem conferir o dono. Com uma transação de A ligada à força à categoria, à tag e à conta de B, `GET /api/reports/charts/simple/` traz "Mercado B", `charts/tag-distribution/` traz "Viagem B" e `export/transactions/xls/` traz "Mercado B", "Viagem B" e "Conta B" (sonda S1). Não há teste que cubra esses caminhos |
| ISOL-16 verificação | Uma linha por ligação, com tipo, ID e relação | `test_verificacao.py:31` - `assertEqual(como_tuplas(links), sorted(registros.esperadas, key=str))` | ✅ |
| ISOL-17 correção | Relações anuladas; orçamentos, monitores e aportes excluídos | `test_correcao.py:58` - `relatorio.ligacoes == 18`; `:66` - `assertIsNone(getattr(transacao, f'{relacao}_id'))`; `:79` - `assertFalse(Budget.objects.filter(pk=r.orcamento.pk).exists())`; `:83` | ✅ |
| ISOL-18 recálculo pela SALDO-01 | Saldo = inicial + entradas − saídas efetivadas do dono | `test_correcao.py:93` - `assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('900.00'))` | ✅ (N17 morta) |

**Status**: ❌ 17 de 18 ACs têm evidência que confere com a spec. ISOL-15 tem gap: os relatórios e a exportação estão fora dos testes, e a sonda confirma o vazamento.

**Regra de payload e conjunção**: atendida nos testes novos.
- T32 confere a tupla inteira da compra de B: usuário, status, conta, valor, fatura, `payment_date` e descrição. Confere também a compra de A com valores exatos, o saldo exato do cofrinho de A, o saldo de B e o status da fatura.
- T33 confere o valor, a categoria e o `updated_at` da parcela de B. Como controle positivo, confere as parcelas de A.
- T34 confere as contagens exatas e a lista exata de orçamentos criados.
- T35 confere o corpo exato do erro em 10 combinações (5 casos × 2 contextos).

---

## Edge Cases

- [x] ID inexistente e ID de B dão respostas idênticas: `base.py:104` (corpo) e `test_endereco_filtros.py:57` (endereço).
- [x] Tag de B entre tags próprias recusa a transação inteira: `test_escrita_transacoes.py:100-102`.
- [x] Transferência com origem própria e destino de B é recusada: `test_escrita_transferencia_cartao.py:54-58` (`assert_recusa` em `account_to`).
- [x] Conta própria excluída: fica com a SALDO-35, fora do escopo.
- [x] Mapeamento de importação para conta de B: o isolamento está garantido. Nada é gravado em B nem ligado a B (`test_importacao.py:99-101`). A rejeição "Conta não mapeada" pertence à IMPORT-21 (`importacao/spec.md`, `Pending`). A conta padrão de B recusa a importação inteira: `test_importacao.py:84`.
- [x] Edição de transação própria já ligada a B: `test_edicao_parcial.py:62-67`, `:91-100`, `:104-162`. N14 e N20 foram mortas.

---

## Success Criteria

| Critério | Evidência | Status |
| -------- | --------- | ------ |
| Um teste automatizado percorre todas as relações graváveis com IDs de B e recebe 400 com o corpo de um ID inexistente | `test_inventario.py:121`, `:125`, mais o teste HTTP de cada relação (tabela acima) | ✅ |
| Depois da correção em produção, a verificação não lista nada | Operacional; em teste: `test_correcao.py:83` | ⏭️ Só verificável em produção |
| Nenhum endpoint devolve dado de B no teste com dois usuários | O pagamento, o estorno, o `ALL_FUTURE` e o `bulk_import` já não mexem em B. Com uma ligação cruzada gravada numa transação de A, os relatórios e a exportação devolvem o nome da categoria, da tag e da conta de B (sonda S1) | ❌ Gap 1 |

---

## Discrimination Sensor

**Profundidade**: ampliada (P0, segurança): 20 mutações de comportamento, feitas à mão.

**Isolamento**:
1. Baseline de `git status --porcelain` da árvore real: vazio.
2. Criei a worktree com `git worktree add --detach ../fluxar-backend-verif3 HEAD`.
3. Os testes rodaram com `docker run --rm --network fluxar-backend_default --env-file .env -e DB_HOST=db -v <worktree>:/app fluxar-backend-backend python manage.py test tests.isolamento --noinput`.
4. Um script aplicava cada mutação, rodava a suíte e restaurava os bytes originais. Ele trata o CRLF da worktree e exige exatamente uma ocorrência antes de aplicar. No fim, a worktree estava limpa (`WORKTREE PORCELAIN: ''`).
5. Removi a worktree com `git worktree remove --force` e rodei `git worktree prune`.
6. Porcelain da árvore real no fim: vazio, igual ao baseline. Não usei `git stash`.

**Controle**: a worktree sem mutação rodou 160 testes, `OK`.

| Mutação | File:line | Descrição | Killed? |
| ------- | --------- | --------- | ------- |
| N01 | `accounts/services.py:135` | T32: `pay_invoice` sem filtro do dono | ✅ Killed (2) |
| N02 | `accounts/services.py:240` | T32: `unpay_invoice` sem filtro do dono | ✅ Killed (1) |
| N03 | `accounts/services.py:135` | T32: `pay_invoice` filtra por `credit_card_id=invoice.card_id` em vez do dono | ❌ **Survived**, não equivalente (gap 2) |
| N04 | `transactions/serializers.py:296` | T33: `ALL_FUTURE` sem filtro do dono | ✅ Killed (2) |
| N05 | `budgets/views.py:97` | T34: `bulk_import` não pula a categoria alheia | ✅ Killed (2) |
| N06 | `budgets/views.py:97` | T34: pula só a categoria-modelo e copia a categoria de B | ✅ Killed (2) |
| N07 | `budgets/views.py:98` | T34: pula, mas não conta como ignorado | ✅ Killed (2) |
| N08 | `core/fields.py:42-43` | T35/M13: remove o ramo sem usuário (repetição da M13) | ✅ Killed (6) |
| N09 | `core/fields.py:42` | T35: `if user is None:` (o usuário anônimo cai no filtro) | ✅ Killed (5) |
| N10 | `core/fields.py:44` | `get_queryset` sem filtro do dono (M11) | ✅ Killed (42) |
| N11 | `core/fields.py:58` | `get_owned_or_400` sem filtro do dono (M12) | ✅ Killed (12) |
| N12 | `accounts/services.py:21` | T18: `get_balance` soma transações de outro usuário | ✅ Killed (1) |
| N13 | `transactions/signals.py:90-91` | T28: total da fatura sem filtro do dono | ✅ Killed (2) |
| N14 | `transactions/serializers.py:191` | T31: não confere a relação atual cruzada | ✅ Killed (5) |
| N15 | `budgets/services.py:25` | T30: o uso do orçamento soma a subcategoria alheia | ✅ Killed (2) |
| N16 | `transactions/signals.py:109-113` | T25: `sync_transfer_update` sem filtro do dono | ✅ Killed (1) |
| N17 | `core/isolation.py:150` | T22: a correção não recalcula saldos (ISOL-18) | ✅ Killed (4) |
| N18 | `goals/serializers.py:64` | T9/T26: a meta mostra movimentos em conta alheia | ✅ Killed (1) |
| N19 | `reports/services.py:577-578` | T19: o monitor ligado a categoria alheia entra no relatório | ✅ Killed (2) |
| N20 | `transactions/serializers.py:193` | T31: não confere as tags atuais cruzadas | ✅ Killed (1) |

**Resultado**: 20 mutações: 19 mortas e 1 sobrevivente real (N03). As mutações diretas de T32 a T35 (N01, N02, N04 a N09) foram todas mortas. Sensor: ❌ por N03.

**Não equivalência de N03, provada por sonda.** Montei uma compra de B com o cartão **e** a fatura de A, e A pagou 150.00.
- Sob N03, a compra de B passa a `COMPLETED` e sai da conta de B, e o teste da sonda falha.
- Sem mutação, a compra fica `PENDING` na conta de B, e o teste passa.

O teste da T32 (`test_pagamento_fatura.py:27-28`) só forja a compra de B com o cartão de B. Por isso não distingue o filtro pelo dono de um filtro pelo cartão.

**Sondas** (testes temporários só na worktree, removidos antes da limpeza):

| Sonda | Cenário (ligação cruzada gravada à força) | Observado |
| ----- | ----------------------------------------- | --------- |
| S1 | Despesa de A (40.00, 2026-09-05) com `account` = conta de B, `category` = categoria de B e a tag de B | `charts/simple` → 200, contém "Mercado B"; `charts/tag-distribution` → 200, contém "Viagem B"; `export/transactions/xls` → 200, a planilha contém "Mercado B", "Viagem B" e "Conta B" |
| S1' | Mesmo cenário, depois de `fix_cross_links(apps)` | As três respostas deixam de conter qualquer nome de B |
| S2 | N03 aplicada; compra de B com o cartão e a fatura de A; A paga | A compra de B passa a `COMPLETED` e sai da conta de B |

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Mínimo de código | ✅ T32: 2 filtros; T33: 1 filtro; T34: 1 condição; T35: só teste |
| Mudanças cirúrgicas | ✅ Cada commit da Phase 7 toca só o arquivo da tarefa, o teste e `tasks.md` |
| Sem scope creep | ✅ |
| Segue os padrões | ✅ O mesmo filtro por `user_id` do dono e o comentário `(ISOL-14)` ou `(ISOL-01)` das fases anteriores |
| Spec-anchored | ⚠️ Gap 1 (ISOL-15, relatórios e exportação) |
| Cobertura por camada | ⚠️ N03: a fixture da T32 não cruza o cartão |
| Todo teste mapeia um AC, edge case ou Done-when | ✅ `test_pagamento_fatura.py` → ISOL-14; `test_parcelas_futuras.py` → ISOL-14; `test_importar_orcamentos.py` → ISOL-01 e ISOL-10; `test_campo.py:103` → ISOL-10 e ISOL-11 |
| Diretrizes documentadas | AD-010, AD-019, AD-024, AD-028, AD-032 e AD-033 seguidas. O gap 1 é mais um caso do trade-off da AD-032: um caminho de servidor que usa uma relação já gravada sem conferir o dono |
| SPEC_DEVIATION | `core/isolation.py:28-33` (`parent_transaction` e `recurring_source`). Justificada e coberta; é ela que remove o pré-requisito da T33 |

---

## Resolução dos gaps da rodada 2

| Gap R2 | Resolução | Evidência |
| ------ | --------- | --------- |
| 1. ISOL-14: pagamento e estorno de fatura mexiam em compras de B | ✅ Resolvido (T32) | `accounts/services.py:135`, `:240`; `test_pagamento_fatura.py:55-62`, `:70-79`, `:91-95`; N01 e N02 mortas. Resta a fraqueza de teste N03 (gap 2 abaixo) |
| 2. ISOL-14: `ALL_FUTURE` alterava a parcela de B | ✅ Resolvido (T33) | `transactions/serializers.py:295-296`; `test_parcelas_futuras.py:49-56`, `:64-71`; N04 morta |
| 3. ISOL-01: `bulk_import` copiava a categoria de B | ✅ Resolvido (T34). A categoria-modelo também é pulada, e a origem pulada conta como `skipped` | `budgets/views.py:96-98`; `test_importar_orcamentos.py:113-127`; N05, N06 e N07 mortas |
| 4. Mutante M13 (ramo sem `request`) | ✅ Resolvido (T35) | `test_campo.py:103-125`; N08 (a própria M13) e N09 mortas |

Gaps da rodada 1: os cinco continuam resolvidos. T29, T30 e T31 estão cobertos, como mostram N14, N15 e N20 mortas nesta rodada. O gap 4 (edge case 5) fica com a IMPORT-21. O gap 5 (`tag_id` com 404) é nota de precisão.

---

## Varredura de travessias sem dono (código tocado pela feature)

Procurei `.transactions.`, `.subcategories.`, `.deposits.`, `.invoices.`, `objects.filter(` sem dono e `.update(`/`.delete(` em conjuntos relacionados. Resultados:

- **Com filtro do dono (ok)**: `accounts/services.py:21`, `:51-56`, `:132-136`, `:237-241`; `transactions/signals.py:90-92`, `:109-113`, `:126-130`; `transactions/serializers.py:35`, `:277-279`, `:292-297`; `transactions/views.py:167-177` e `:202-205` (`user=request.user`); `budgets/services.py:25`; `budgets/views.py:75-78`, `:96`; `goals/serializers.py:64`; `goals/views.py:103`; `goals/signals.py:38`; `reports/services.py:576-578`, `:586`; `core/isolation.py:93`, `:107`.
- **Objeto do próprio usuário por construção (ok)**: `accounts/services.py:62`, `accounts/views.py:55` e `reports/services.py:127-137` percorrem as faturas de um cartão já filtrado pelo dono. `GoalDeposit.objects.filter(transaction_id=...)` (`goals/signals.py:42`, `:103`) usa o UUID da própria transação.
- **Leitura de nomes de relacionados sem conferir o dono (gap 1)**:
  - `reports/services.py:396-419`: `category__name`, `category__parent__name` e cores;
  - `:697`: `t.category.name`;
  - `:748-749`: `Category.objects.filter(id=cat_id)` sem dono;
  - `:903-910`: `category__name`;
  - `:1251`, `:1278`: `tags__name` e `tags__color`;
  - `data_exchange/services.py:479-480` (PDF) e `:524-538` (XLS): nome da conta, da categoria, da categoria-pai e das tags.
  Todos partem de `Transaction.objects.filter(user=user)`. Por isso só vazam com uma ligação cruzada já gravada numa transação de A.
- **Cópia interna (nota residual)**: `accounts/services.py:195-212`. O "Restante" do pagamento parcial copia `category`, `tags` e `parent_transaction` da compra de A. Se essa compra estiver cruzada desde antes da correção, a ligação passa para o registro novo. A migração `0007` desfaz a origem.

---

## Spec-precision gaps

1. **ISOL-13, relatório de recurso único** (desde a rodada 1): `tag-insights` responde 404, igual a uma tag inexistente. Não afeta o isolamento. Recomendação: registrar na spec que um relatório de recurso único segue a ISOL-12.
2. **Edge case 5 → IMPORT-21** (desde a rodada 1): a rejeição da linha pertence à outra spec.
3. **Defesa contra ligações já gravadas** (rodada 2, ainda aberta): a spec não diz se cada caminho de servidor precisa conferir o dono das relações já gravadas, ou se basta a correção ISOL-17 (a migração `0007`, no mesmo deploy). Cada rodada achou caminhos novos dessa classe: 3 na rodada 1, 3 na rodada 2 e 2 nesta. A ISOL-15 ("uma resposta") e o critério de sucesso 3 ("nenhum endpoint") cobrem o gap 1 pela letra, por isso ele conta como gap e não como nota.

---

## Ranked gaps e Fix Plans

Os dois gaps dependem de uma ligação cruzada gravada antes da correção. A API não cria mais nenhuma: os caminhos de entrada estão cobertos (ISOL-01 a ISOL-11), e os caminhos internos também (T32 a T34). A migração `0007` desfaz as ligações existentes no mesmo deploy, e a sonda S1' mostra o vazamento sumindo depois de `fix_cross_links`. A gravidade é baixa, a mesma dos gaps das rodadas 1 e 2.

### Gap 1 (Major pela letra da spec, baixa gravidade prática): relatórios e exportação mostram nomes de relacionados de B

- **AC**: ISOL-15; critério de sucesso 3.
- **Root cause**: os relatórios (`reports/services.py:396-419`, `:697`, `:748-749`, `:903-910`, `:1251`, `:1278`) e a exportação (`data_exchange/services.py:479-480`, `:524-538`) leem o nome e a cor da categoria, da categoria-pai, das tags e da conta através das transações de A, sem conferir se esses objetos são de A. A tabela de leituras do design (`design.md:105-114`) não lista esses caminhos.
- **Fix task (T36)**: nas agregações, trocar o nome de um relacionado alheio por "Sem Categoria" ou vazio, filtrando pelo dono (por exemplo, `Case(When(category__user_id=F('user_id'), ...))`, ou `tags__user_id=user.id` nas agregações de tags). Na exportação, usar só conta, categoria e tags do dono. Teste em `tests/isolamento/`: transação de A ligada à força à conta, à categoria (e à categoria-pai) e à tag de B. Os corpos de `charts/simple`, `charts/tag-distribution` e `charts/advanced`, e as linhas do XLS e do PDF, não podem conter nenhum nome de B.

### Gap 2 (Minor, teste): mutante N03 sobrevive em `pay_invoice`

- **Root cause**: `test_pagamento_fatura.py:27-28` forja a compra de B só com o cartão de B. Um filtro por cartão no lugar do filtro pelo dono passa na suíte, mas paga uma compra de B que também tenha o cartão de A (sonda S2).
- **Fix task (T37)**: acrescentar um caso com a compra de B gravada com `credit_card` = cartão de A e `invoice` = fatura de A, no pagamento e no estorno, e conferir que ela não muda.

**Escalonamento (rodada 3 de 3)**: pelo limite do ciclo, a decisão fica com o usuário. Opções:
- **(a)** Executar T36 e T37 e verificar de novo, fora do ciclo.
- **(b)** Registrar em STATE.md uma decisão: as leituras e cópias internas sobre ligações gravadas antes da correção ficam cobertas só pela ISOL-17 e pela migração `0007`. O gap 1 vira risco residual aceito, com a sonda S1' como evidência de que a migração remove o pré-requisito. Nesse caso, só a T37 (teste) seria executada.

Recomendação: **(b) + T37**. A classe de caminho não tem fim claro dentro do código legado, e a garantia real é a migração no mesmo deploy.

---

## Notas residuais (não bloqueiam)

- `unpay_invoice` usa `QuerySet.update()` (`accounts/services.py:244`), então o `Account.balance` guardado não é revertido. Esse problema é do modelo de saldo e fica com a spec `saldo`.
- `pay_invoice`: o "Restante" copia a categoria e as tags da compra de A (`accounts/services.py:195-212`). Isso depende de uma ligação já gravada, desfeita pela migração `0007`.
- `bulk_import` faz uma consulta por orçamento de origem (`budget.category.user_id`). É um custo pequeno, sem efeito sobre o isolamento.

---

## Requirement Traceability Update

Recomendação (a verificação não edita `spec.md`):

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| ISOL-01 a ISOL-14, ISOL-16 a ISOL-18 | Pending | ✅ Verified (ISOL-14 com a fraqueza de teste N03, gap 2) |
| ISOL-15 | Pending | ❌ Needs Fix, ou risco aceito por decisão (gap 1) |

---

## Summary

**Overall**: ❌ Not Ready. A gravidade é baixa: a migração no mesmo deploy remove o pré-requisito dos dois gaps. Esta rodada é a última do ciclo, então os gaps vão para decisão do usuário.

**Spec-anchored check**: 17 de 18 ACs conferem com a spec. ISOL-15 tem gap. Continuam 3 spec-precision gaps (2 antigos e a pergunta sobre a defesa contra ligações já gravadas).
**Sensor**: 20 mutações: 19 mortas e 1 sobrevivente real (N03).
**Gate**: 160 passaram, 0 falharam, 0 pulados.

**O que funciona**:
- Os quatro gaps da rodada 2 estão resolvidos e discriminados.
- A recusa por campo, o 404 no endereço e as listas vazias continuam de pé.
- Continuam de pé também as somas e listas pelo dono, a verificação, a correção, o comando e a migração.

**Próximos passos**: o usuário escolhe (a) T36 + T37 ou (b) uma decisão em STATE.md + T37.

---

## validate_state

`python validate_state.py isolamento-entre-usuarios --root .` terminou com exit 1, o esperado para um FAIL:

```
ERROR isolamento-entre-usuarios: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)
validate_state: 1 error(s) across [isolamento-entre-usuarios]
```
