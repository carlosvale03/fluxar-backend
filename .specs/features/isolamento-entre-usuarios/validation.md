# Isolamento entre usuarios Validation

## Validation: isolamento-entre-usuarios (rodada 2) - FAIL ❌

**Date**: 2026-09-27
**Spec**: `.specs/features/isolamento-entre-usuarios/spec.md`
**Diff range**: `development..fix/isolamento-entre-usuarios` (base `f4f560e`, HEAD `8b3da34`, 36 commits; Phase 6 = `53dfcbd`, `9858af6`, `8b3da34`)
**Verifier**: sub-agente independente da rodada 2 (autor ≠ verificador), evidence-or-zero; o relatório da rodada 1 não foi usado como evidência, e as citações antigas foram conferidas linha a linha

Resumo: T29, T30 e T31 fecharam os gaps 1 a 3 da rodada 1, e cada mudança tem teste que mata as mutações correspondentes. O gap 4 fica para a IMPORT-21 e o gap 5 é só nota de precisão; nenhum dos dois bloqueia. O FAIL vem de três caminhos novos, achados nesta rodada e confirmados por sonda. Nos três, uma ação de A mexe em dados de B ou copia uma ligação cruzada quando essa ligação já está gravada. O mais sério é o pagamento de fatura (ISOL-14, "compras de um cartão"). Há também um mutante sobrevivente no ramo "sem `request`" do campo. É a mesma classe de gravidade dos gaps 1 e 2 da rodada 1: tudo depende de uma ligação cruzada gravada antes da correção, e a migração `0007_corrige_isolamento` desfaz essas ligações no mesmo deploy.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T28 | ✅ Done | Marcadas `✅ Complete` em `tasks.md` |
| T29 (leitura do orçamento) | ✅ Done | `53dfcbd`; `budgets/serializers.py:27-33` |
| T30 (uso do orçamento) | ✅ Done | `9858af6`; `budgets/services.py:24-26` |
| T31 (edição parcial com ligação cruzada) | ✅ Done | `8b3da34`; `transactions/serializers.py:179-197` |

---

## Gate Check

- **Gate command**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`
- **Resultado**: exit 0. `compileall` sem erro; `makemigrations --check`: "No changes detected"; `Found 152 test(s)` … `Ran 152 tests in 14.796s` … `OK`
- **Passaram**: 152; **falharam**: 0; **pulados**: 0
- **Testes antes da feature**: 0. **Rodada 1**: 138. **Agora**: 152. A Phase 6 acrescentou 14 (3 + 2 + 9), e nenhum arquivo de teste antigo mudou (`git diff --stat 0253099..HEAD -- tests` mostra só os 3 arquivos novos)
- **Prints**: o diff não acrescenta nenhum `print(` fora de `tests/` (AD-019). Os `DEBUG` da saída já existiam antes da feature

---

## Spec-Anchored Acceptance Criteria

Helper das recusas: `tests/isolamento/base.py:94-106` (`assert_mesma_recusa`). Ele confere 400 nas duas respostas (`:100-101`), o campo (`:102`), as mesmas chaves (`:103`), o corpo idêntico ao de um ID inexistente (`:104`) e `resp.data[campo] == [mensagem]` (`:106`).

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| ISOL-01 invariante | Registro ligado só a objetos do dono, ou a nenhum | `test_inventario.py:121` - `assertIsInstance(relacao, OwnedPrimaryKeyRelatedField)`; `:125` - `assertEqual(ESPERADAS - verificadas, set())`; dados gravados: `test_correcao.py:83` - `assertEqual(find_cross_links(apps), [])` | ⚠️ Coberto na entrada pela API e na correção. Dois caminhos internos criam uma ligação cruzada nova a partir de uma já gravada: sondas P1 e P3 (gaps 1 e 3) |
| ISOL-02 transação com conta, cartão, categoria ou tag de B | 400 no campo, mesma mensagem de inexistente, nada gravado | criação `test_escrita_transacoes.py:73` - `assert_mesma_recusa(...)`, `:74` - `assertEqual(Transaction.objects.count(), total_antes)`; edição `:136`, `:137` - `assertEqual(self.estado(t), antes)`; edição de transação já cruzada (T31): `test_edicao_parcial.py:65` - `assert_mesma_recusa(resp, resp_inexistente, campo, mensagem)`, `:66` - `assertEqual(resp.data, {campo: [mensagem]})`, `:67` - `assertEqual(self.estado(t), antes)` para conta, cartão, categoria, categoria-modelo e tag (`:71-89`) | ✅ |
| ISOL-03 edição em lote com categoria de B | 400 em `category`, nenhuma ocorrência alterada | `test_escrita_lote.py:50` - `assert_mesma_recusa(resp, resp_inexistente, 'category', 'Categoria não encontrada.')`; `:52` - `assertEqual(self.estado_da_serie(), antes)` | ✅ |
| ISOL-04 categoria-pai de B | 400 em `parent`, nada gravado | `test_escrita_categorias.py:37` - `assert_mesma_recusa(..., 'parent', 'Categoria não encontrada.')`; `:54` - `assertIsNone(categoria.parent_id)` | ✅ |
| ISOL-05 orçamento com categoria de B | 400 em `category`, nada gravado | `test_escrita_orcamentos.py:28` - `assert_mesma_recusa(..., 'category', 'Categoria não encontrada.')`; `:29` - `assertEqual(self.estado_dos_orcamentos(), antes)` | ✅ |
| ISOL-06 meta com conta de B | 400 em `account` | `test_metas.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account', 'Conta não encontrada.')` | ✅ |
| ISOL-07 monitor com categoria ou tag de B | 400 no campo | `test_monitor_foco.py:20` - `assert_mesma_recusa(resp, resp_inexistente, campo, mensagem)` | ✅ |
| ISOL-08 cartão com conta de B | 400 em `account_id` | `test_cartao_fatura.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')` | ✅ |
| ISOL-09 compra no cartão, transferência, pagamento de fatura, aporte/resgate e importação | 400 no campo do corpo | `test_escrita_transferencia_cartao.py:40` - `assert_mesma_recusa(...)`; `test_cartao_fatura.py:93` - `assert_mesma_recusa(..., 'account_id', 'Conta não encontrada.')`; `test_aporte_resgate.py:32` - `assert_mesma_recusa(resp, resp_inexistente, campo, 'Conta não encontrada.')`; `test_importacao.py:76` (OFX) e `:84` (planilha) - `assert_mesma_recusa(..., 'account_id', 'Conta não encontrada.')` | ✅ |
| ISOL-10 categoria-modelo | Recusa igual à de inexistente | `test_campo.py:45` - `assertEqual(serializer.errors, {campo: [mensagem]})` via `:70`; edição de transação já ligada à categoria-modelo: `test_edicao_parcial.py:83-85`; leitura do orçamento com categoria-modelo: `test_leitura_orcamentos.py:50-55` | ✅ (o ramo "sem `request`" deixa passar a categoria-modelo, mutante M13; ver gap 4) |
| ISOL-11 formato da recusa | 400, erro no campo, mesma mensagem em português | `base.py:100-106`; `test_edicao_parcial.py:66` - corpo exatamente `{campo: [mensagem]}` | ✅ |
| ISOL-12 ID de B no endereço | 404 igual a inexistente | `test_endereco_filtros.py:56` - `assertEqual(resp_inexistente.status_code, status)`; `:57` - `assertEqual(resp.data, resp_inexistente.data)` | ✅ |
| ISOL-13 filtros com ID de B | Vazio, igual a inexistente | `test_endereco_filtros.py:158` - `assertEqual(resp.data['results'], [])`; `:159` - `assertEqual(resp.data, resp_inexistente.data)`; exportação `:201` - `assertEqual(self.transacoes_exportadas(...), [])`; relatório de tag `test_relatorios.py:46-48` (404 igual a inexistente) | ✅ (nota de precisão sobre o relatório de tag; ver gap 5 da rodada 1) |
| ISOL-14 listas e somas só com dados do dono | Subcategorias, transações da conta, compras do cartão, metas do cofrinho, parceira | subcategorias `test_leitura_categorias.py:25`; saldo `test_saldo_limite.py:23` - `assertEqual(AccountService.get_balance(self.a.conta), Decimal('900.00'))`; limite `:44` - `Decimal('1700.00')`; fatura `test_total_fatura.py:33` - `Decimal('350.00')`; metas `test_signal_metas.py:27`; parceira `test_leitura_transacoes.py:70`; **uso do orçamento (T30)**: `test_uso_orcamento.py:33` - `assertEqual(self.uso(), (Decimal('0.00'), Decimal('0.00'), 'OK'))` e `:40` - `(Decimal('60.00'), Decimal('20.00'), 'OK')` | ❌ GAP: o pagamento e o estorno de fatura (`accounts/services.py:132`, `:236`) percorrem as compras da fatura sem filtrar pelo dono, e a edição `ALL_FUTURE` (`transactions/serializers.py:291-292`) percorre as parcelas sem esse filtro. Sondas P3, P4 e P5, sem teste (gaps 1 e 2) |
| ISOL-15 respostas só com relacionados do dono | Nome da conta, categoria, subcategorias, tags, conta da meta | transação `test_leitura_transacoes.py:43` - `assertIsNone(dados['account'])`; `:88` - `'Desconhecida'`; **orçamento (T29)**: `test_leitura_orcamentos.py:36` - `assertIsNone(dados['category'])`, `:37` - `assertIsNone(dados['category_detail'])`, `:39` - `assertNotIn(str(categoria.id), texto)`, `:41` - `assertNotIn(trecho, texto)` para nome, subcategoria, ícone e cor de B, no detalhe e na lista (`:35`); formato próprio inalterado `:63-73` | ✅ |
| ISOL-16 verificação | Uma linha por ligação, com tipo, ID e relação | `test_verificacao.py:31` - `assertEqual(como_tuplas(links), sorted(registros.esperadas, key=str))` | ✅ |
| ISOL-17 correção | Relações anuladas; orçamentos, monitores e aportes excluídos | `test_correcao.py:58` - `relatorio.ligacoes == 18`; `:66` - `assertIsNone(getattr(transacao, f'{relacao}_id'))`; `:79` - `assertFalse(Budget.objects.filter(pk=r.orcamento.pk).exists())`; `:83` | ✅ |
| ISOL-18 recálculo SALDO-01 | Saldo = inicial + entradas − saídas efetivadas do dono | `test_correcao.py:93` - `assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('900.00'))` | ✅ |

**Status**: ❌ 16/18 ACs com evidência que confere com a spec. ISOL-14 tem gap. ISOL-01 está coberto na entrada e na correção, mas a sonda mostra caminhos internos que copiam uma ligação cruzada já gravada.

**Regra de payload e conjunção**: atendida nos testes novos. T29 confere `None` nos dois campos e a ausência do ID, do nome, da subcategoria, do ícone e da cor, no detalhe e na lista. T30 confere a tupla exata (`total_spent`, `percentage_used`, `status`), com controle positivo. T31 confere o corpo exato, a igualdade com um ID inexistente e o estado inteiro da transação (conta, cartão, categoria, descrição, valor, `updated_at` e tags).

---

## Edge Cases

- [x] ID inexistente e ID de B dão respostas idênticas: `base.py:104` (corpo) e `test_endereco_filtros.py:57` (endereço).
- [x] Tag de B entre tags próprias recusa a transação inteira: `test_escrita_transacoes.py:100`.
- [x] Transferência com origem própria e destino de B: `test_escrita_transferencia_cartao.py:54-58`.
- [x] Conta própria excluída: fica com a SALDO-35, fora do escopo.
- [x] Mapeamento de importação para conta de B: o isolamento está garantido. Nada é gravado em B nem ligado a B (`test_importacao.py:99` - `assertFalse(Transaction.objects.filter(account=self.b.conta).exists())`, `:100`, `:101`), e a sonda P2 mostra que a resposta e o resultado são idênticos aos de um ID inexistente (`200`, mesmo corpo, linha de A com `account=None`). A rejeição "Conta não mapeada" é da IMPORT-21, `Pending` em `.specs/features/importacao/spec.md:117,258`, e fica para essa feature. A conta padrão de B recusa a importação inteira: `test_importacao.py:84`.
- [x] Edição de transação própria já ligada a B (T31): `test_edicao_parcial.py:62-67`. Um PATCH só com `description` recebe 400 no campo cruzado, igual ao de um ID inexistente, sem alterar nada. Outra relação ainda cruzada mantém a recusa (`:91-100`). Trocar a relação por uma própria (`:104-132`) ou por nula (`:134-150`) é aceito. O PATCH parcial sem ligação cruzada continua funcionando (`:152-162`).

---

## Success Criteria

| Critério | Evidência | Status |
| -------- | --------- | ------ |
| Teste automatizado percorre todas as relações graváveis com IDs de B: 400 com o corpo de inexistente | `test_inventario.py:121`, `:125` e o teste HTTP de cada relação (tabela acima) | ✅ |
| Depois da correção em produção, a verificação não lista nada | Operacional; em teste: `test_correcao.py:83` | ⏭️ Só verificável em produção |
| Nenhum endpoint devolve dado de B no teste com dois usuários | O orçamento já não mostra a categoria de B (T29). Sem ligação cruzada gravada, nenhum endpoint vazou. Com ligação cruzada gravada, `POST /api/invoices/{id}/pay/` **altera** a compra de B (sonda P3), sem devolver os dados dela | ⚠️ Leitura ✅; escrita indireta, gap 1 |

---

## Discrimination Sensor

**Profundidade**: ampliada (P0, segurança): 24 mutações de comportamento, feitas à mão.
**Isolamento**: baseline `git status --porcelain` da árvore real: vazio. Worktree `git worktree add --detach ../fluxar-backend-verif2 HEAD`. Os testes rodaram com `docker run --rm --network fluxar-backend_default --env-file .env -e DB_HOST=db -v <worktree>:/app fluxar-backend-backend python manage.py test tests.isolamento --noinput`. Um script aplicava e revertia cada mutação, e a worktree terminou sem mudanças (`WORKTREE PORCELAIN: ''`). Depois, `git worktree remove --force` e `git worktree prune`. Porcelain da árvore real no fim: vazio, igual ao baseline. Não houve `git stash`.
**Controle**: a worktree sem mutação rodou 152 testes, `OK`.
**Nota**: a worktree saiu com CRLF. Dez mutações de várias linhas não casaram na primeira passada e rodaram de novo depois que o script passou a tratar o CRLF. Cada mutação da tabela foi aplicada de fato: o script confere uma ocorrência exata antes de aplicar.

| Mutação | File:line | Descrição | Killed? |
| ------- | --------- | --------- | ------- |
| M01 | `budgets/serializers.py:30-32` | T29: remove o bloco que anula `category` e `category_detail` | ✅ Killed (2) |
| M02 | `budgets/serializers.py:31` | T29: anula só `category_detail`; o ID de B continua em `category` | ✅ Killed (2) |
| M03 | `budgets/serializers.py:30` | T29: a categoria-modelo (`user_id None`) volta a aparecer | ✅ Killed (1) |
| M04 | `budgets/services.py:25` | T30: subcategorias sem filtro do dono | ✅ Killed (2) |
| M05 | `budgets/services.py:25` | T30: descarta também as subcategorias próprias | ✅ Killed (1) |
| M06 | `transactions/serializers.py:193` | T31: não confere as tags atuais | ✅ Killed (1) |
| M07 | `transactions/serializers.py:190` | T31: confere a relação atual mesmo quando o corpo a substitui | ✅ Killed (6) |
| M08 | `transactions/serializers.py:187` | T31: deixa de conferir o cartão atual | ✅ Killed (1) |
| M09 | `transactions/serializers.py:190` | T31: aceita a categoria-modelo atual | ✅ Killed (1) |
| M10 | `transactions/serializers.py:191` | T31: erro em `non_field_errors` em vez do campo | ✅ Killed (5) |
| M11 | `core/fields.py:44` | `get_queryset` sem filtro do dono | ✅ Killed (42) |
| M12 | `core/fields.py:58` | `get_owned_or_400` sem filtro do dono | ✅ Killed (12) |
| M13 | `core/fields.py:42-43` | Sem `request`, o campo filtra por `user=None` e aceita a categoria-modelo | ❌ **Survived** (gap 4) |
| M14 | `core/isolation.py:40` | Verificação e correção pulam `Budget.category` | ✅ Killed (4) |
| M15 | `core/isolation.py:150` | Correção não recalcula saldos | ✅ Killed (4) |
| M16 | `core/isolation.py:93` | O recálculo do saldo deixa de filtrar pelo dono da conta | ⚪ Survived, **equivalente**: `fix_cross_links` anula todo `Transaction.account` cruzado (`:148`) antes de `_recalcular_saldos` (`:150`), então o filtro não muda o resultado |
| M17 | `core/isolation.py:71` | Verificação e correção ignoram tags | ✅ Killed (4) |
| M18 | `core/isolation.py:47` | `GoalDeposit` sai de `EXCLUIDOS` (a correção tenta anular a conta) | ✅ Killed (9 erros) |
| M19 | `accounts/services.py:21` | `get_balance` soma transações de outro usuário | ✅ Killed (1) |
| M20 | `accounts/services.py:53` | Limite do cartão soma compras de outro usuário | ✅ Killed (1) |
| M21 | `goals/signals.py:38` | Signal usa metas de outro usuário | ✅ Killed (2) |
| M22 | `transactions/serializers.py:125` | Transação mostra a conta de outro usuário | ✅ Killed (1) |
| M23 | `transactions/serializers.py:35` | Árvore de categorias com subcategoria de outro usuário | ✅ Killed (1) |
| M24 | `transactions/serializers.py:131` | Transação mostra tags de outro usuário | ✅ Killed (1) |

**Resultado**: 24 mutações; 22 mortas, 1 sobrevivente real (M13) e 1 equivalente (M16). As mutações de T29, T30 e T31 (M01 a M10) foram todas mortas. Sensor: ❌ por M13.

**Sondas** (teste temporário só na worktree, removido antes da limpeza). Não são mutações; mostram o que o código faz num caminho que a suíte não confere:

| Sonda | Cenário (ligação cruzada gravada à força) | Observado |
| ----- | ----------------------------------------- | --------- |
| P1 | Orçamento de A com a categoria de B; `POST /api/budgets/bulk_import/` com esse orçamento como origem | `201`, `imported_count: 1`; o orçamento novo de A fica ligado à categoria de B |
| P2 | Planilha com `account_mapping` para a conta de B e, em outra chamada, para um UUID inexistente | Respostas idênticas (`200`, `{'total': 1, 'imported': 1, ...}`); nas duas, a linha fica com A e `account=None` |
| P3 | Compra de B ligada à fatura de A; A paga a fatura (`/pay/`, 150.00 do cofrinho de A) | `200`; a compra de B passa a `COMPLETED` com `account` = cofrinho de A, e o saldo do cofrinho de A fica em `-150.00`, com os 50.00 de B |
| P4 | Mesmo cenário; A estorna (`/unpay/`) | `200`; a compra de B volta a `PENDING` |
| P5 | Parcela de B com `parent_transaction` = parcela 1 de A; `PATCH` da parcela de A com `amount=10.00` e `update_scope=ALL_FUTURE` | `200`; o valor da parcela de B passa a `10.00` |

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Mínimo de código | ✅ T29: 6 linhas; T30: 1 filtro; T31: 1 `validate` com as mensagens de `core/fields.py` |
| Mudanças cirúrgicas | ✅ Cada commit da Phase 6 toca só o arquivo da tarefa, o teste e `tasks.md` |
| Sem scope creep | ✅ |
| Segue os padrões | ✅ T29 repete a convenção do `TransactionSerializer.to_representation`; T31 usa as constantes de `core/fields.py` |
| Spec-anchored | ⚠️ Gaps 1 a 3 |
| Cobertura por camada | ⚠️ `test_campo.py:96-100` testa o ramo "sem `request`" só com objeto próprio (M13) |
| Todo teste mapeia um AC, edge case ou Done-when | ✅ `test_leitura_orcamentos.py` → ISOL-15; `test_uso_orcamento.py` → ISOL-14; `test_edicao_parcial.py` → edge case 6 / ISOL-02 |
| Diretrizes documentadas | AD-010, AD-019, AD-024, AD-032 e AD-033 seguidas. O trade-off da AD-032 diz que as gravações internas "continuam responsáveis por usar só objetos já validados", e os gaps 1 a 3 são justamente gravações internas que usam uma relação já gravada, sem conferir o dono |
| SPEC_DEVIATION | `core/isolation.py:28-33` (`parent_transaction` e `recurring_source` entram na correção). Justificada e coberta. É ela que garante que a correção desfaz o pré-requisito da sonda P5 |

---

## Resolução dos gaps da rodada 1

| Gap R1 | Resolução | Evidência |
| ------ | --------- | --------- |
| 1. ISOL-15, orçamento mostra a categoria de B | ✅ Resolvido (T29) | `budgets/serializers.py:27-33`; `test_leitura_orcamentos.py:36-41` (detalhe e lista, categoria de B e categoria-modelo), `:63-73` (formato próprio). M01, M02 e M03 mortas |
| 2. ISOL-14, uso do orçamento soma a subcategoria de B | ✅ Resolvido (T30) | `budgets/services.py:24-26`; `test_uso_orcamento.py:33`, `:40`. M04 e M05 mortas |
| 3. Edge case 6, PATCH parcial em transação já cruzada | ✅ Resolvido (T31). A decisão tomada foi recusar, que é a leitura literal do edge case | `transactions/serializers.py:179-197`; `test_edicao_parcial.py:62-67`, `:91-100`, `:104-162`. M06 a M10 mortas |
| 4. Edge case 5, mapeamento de importação para conta de B | ✅ Não bloqueia: fica com a IMPORT-21. A garantia que é desta feature (nada gravado em B nem ligado a B, resposta igual à de um ID inexistente) está coberta | `test_importacao.py:99-101`; sonda P2 (respostas idênticas). A mensagem "Conta não mapeada" depende da IMPORT-21 (`importacao/spec.md:117`, `Pending`). Recomendação: o teste deveria comparar com a resposta de um ID inexistente, como faz a sonda P2 |
| 5. ISOL-13, `tag_id` do relatório de tag dá 404, não "vazio" | ✅ Não bloqueia: é nota de precisão. `tag-insights` é o relatório de um único recurso, a própria tag, e não uma lista filtrada. A resposta é idêntica à de um ID inexistente (`test_relatorios.py:46-48`, também com UUID malformado `:55-56`), que é a garantia pedida pela suposição "não revela nada" | Recomendação: registrar na spec que um relatório de recurso único segue ISOL-12 (404) |

---

## Spec-precision gaps

1. **ISOL-13, relatório de recurso único**: continua a nota da rodada 1 (gap 5), sem efeito sobre o isolamento.
2. **Edge case 5 → IMPORT-21**: a rejeição da linha é da outra spec. Aqui fica só a garantia de isolamento.
3. **Caminhos internos que copiam ou percorrem uma relação já gravada** (novo): a spec trata a ligação cruzada já gravada em ISOL-14 e ISOL-15 (leitura e soma), no edge case 6 (edição da transação) e em ISOL-17 (correção). Ela não diz se as operações de servidor que **copiam** ou **alteram em série** registros ligados precisam conferir o dono: pagar e estornar fatura, `ALL_FUTURE` e `bulk_import`. O pagamento de fatura está dentro do texto de ISOL-14 ("compras de um cartão"), por isso conta como gap. Os outros dois ficam na zona cinzenta.

---

## Ranked gaps e Fix Plans

Todos dependem de uma ligação cruzada gravada antes da correção: `Transaction.invoice`, `Transaction.parent_transaction` ou `Budget.category`. A migração `0007` desfaz essas três relações (`core/isolation.py:26`, `:32`, `:40`; `test_correcao.py:58-83`), e a API não cria nenhuma delas (ISOL-01/ISOL-05). A gravidade é baixa, a mesma dos gaps 1 e 2 da rodada 1.

### Gap 1 (Major): ISOL-14, pagamento e estorno de fatura mexem em compras de outro usuário

- **Root cause**: `CreditCardService.pay_invoice` (`accounts/services.py:132`) e `unpay_invoice` (`:236`) usam `invoice.transactions.filter(type='CREDIT_CARD', status=...)` sem `user_id=invoice.card.user_id`. No pagamento, `tx.account = account` (`:164`, `:183`) liga a compra de B à conta de A, o que cria uma ligação cruzada nova, e o saldo guardado da conta de A passa a contar a compra de B. No pagamento parcial, a compra de B também é dividida e movida para a próxima fatura (`:178-211`).
- **Fix task**: filtrar as duas buscas por `user_id=invoice.card.user_id`, como `update_invoice_total` já faz desde a T28. Teste em `tests/isolamento/`: compra de B gravada à força na fatura de A. Depois do `pay`, a compra de B continua `PENDING`, com a conta de B, e o saldo do cofrinho de A cai só o valor da compra de A. Depois do `unpay`, a compra de B não muda.

### Gap 2 (Minor): ISOL-14, a edição `ALL_FUTURE` altera parcelas de outro usuário

- **Root cause**: `transactions/serializers.py:291-292` busca `Q(id=root_id) | Q(parent_transaction_id=root_id)` sem filtrar pelo dono. Uma parcela de B com `parent_transaction` apontando para a parcela de A recebe o valor e a categoria de A (sonda P5).
- **Fix task**: acrescentar `user_id=instance.user_id` à busca e testar com a parcela de B forjada: o `amount` dela não muda.

### Gap 3 (Minor): ISOL-01, `bulk_import` de orçamentos copia a categoria de outro usuário

- **Root cause**: `budgets/views.py:100` copia `budget.category` do orçamento de origem sem conferir o dono da categoria (sonda P1).
- **Fix task**: ignorar (ou contar como `skipped`) as origens cuja categoria não é do usuário (`category__user=request.user` na busca de `:75`). Testar com um orçamento forjado de A ligado à categoria de B: nenhum orçamento novo fica ligado à categoria de B.

### Gap 4 (Minor, teste): mutante M13 sobrevive no ramo "sem `request`"

- **Root cause**: `test_campo.py:96-100` só confere que um objeto **próprio** é recusado sem `request`. Se o ramo `core/fields.py:42-43` for removido, o campo filtra por `user=None` e passa a aceitar a categoria-modelo, e nenhum teste falha. Hoje nenhum código de produção usa esses serializers sem `request` (busca por `Serializer(data=` sem `context`), então é uma fraqueza latente.
- **Fix task**: no mesmo teste, ou num teste irmão, conferir que a categoria-modelo também é recusada sem `request`.

**Alternativa ao ciclo de correção**: esta é a rodada 2 de 3. Se o usuário preferir não abrir mais uma rodada, a opção é registrar uma decisão em STATE.md: as operações internas sobre ligações cruzadas gravadas antes da correção ficam cobertas pela ISOL-17/migração `0007`, sem filtro próprio. Nesse caso, os gaps 1 a 3 seriam aceitos como risco residual, e só o gap 4 (teste) precisaria de tarefa.

---

## Requirement Traceability Update

Recomendação (a verificação não edita `spec.md`):

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| ISOL-02 a ISOL-13, ISOL-15 a ISOL-18 | Pending | ✅ Verified |
| ISOL-01 | Pending | ⚠️ Verified na entrada e na correção; gap 3 (cópia interna) |
| ISOL-14 | Pending | ❌ Needs Fix (gaps 1 e 2) |

---

## Summary

**Overall**: ❌ Not Ready. A gravidade é baixa, porque a migração no mesmo deploy remove o pré-requisito dos gaps 1 a 3.

**Spec-anchored check**: 16/18 ACs conferem com a spec. ISOL-14 tem gap; ISOL-01 tem gap parcial em caminho interno; há 3 spec-precision gaps.
**Sensor**: 24 mutações; 22 mortas, 1 sobrevivente (M13), 1 equivalente (M16).
**Gate**: 152 passaram, 0 falharam, 0 pulados.

**O que funciona**: os gaps 1 a 3 da rodada 1 estão resolvidos e discriminados pelos testes (M01 a M10 mortas). A recusa por campo, o 404 no endereço, as listas vazias e as leituras e somas tratadas pela feature, além da verificação, da correção, do comando e da migração, continuam de pé.

**Próximos passos**: rotear os gaps 1 a 4 como T32 a T35 (ou aceitar os gaps 1 a 3 por decisão, como descrito acima) e verificar de novo na rodada 3.

---

## validate_state

`python validate_state.py isolamento-entre-usuarios --root .` terminou com exit 1, o esperado para um FAIL:

```
ERROR isolamento-entre-usuarios: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)
validate_state: 1 error(s) across [isolamento-entre-usuarios]
```
