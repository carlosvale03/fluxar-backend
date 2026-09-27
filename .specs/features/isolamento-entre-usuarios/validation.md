# Isolamento entre usuarios Validation

## Validation: isolamento-entre-usuarios (rodada 4, focada) - PASS ✅

**Date**: 2026-09-27
**Spec**: `.specs/features/isolamento-entre-usuarios/spec.md`
**Diff range**: `development..HEAD` (base `f4f560e`, HEAD `99ce9d9`, branch `fix/isolamento-entre-usuarios`). Phase 8 = `12e7688` (T36), `5b02de0` (T37), `99ce9d9` (T38).
**Verifier**: sub-agente independente da rodada 4 (autor ≠ verificador), evidence-or-zero. Rodada extra, pedida pelo usuário, com foco nas correções da Phase 8. Não usei o relatório da rodada 3 como evidência: conferi cada citação no HEAD atual e corrigi as linhas que mudaram.

Resumo: T36 e T37 fecham o gap 1 da rodada 3. Com uma transação de A ligada à força à conta, à categoria, à categoria-pai e à tag de B, nenhum relatório e nenhuma exportação mostra nome, ícone ou cor de B. A sonda S1, repetida no código atual, confirma isso em 11 respostas. T38 fecha o gap 2: o mutante N03 e o equivalente no estorno agora são mortos. O sensor desta rodada matou as 12 mutações. Continuam de pé as notas residuais e o spec-precision gap sobre ligações já gravadas. Nesta rodada ele ganha um caso novo, sem dado de B: com uma ligação antiga, um filtro por ID de B traz a transação da própria A. Esse caso não bloqueia (ver a seção "Ligações já gravadas").

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T35 | ✅ Done | Marcadas `✅ Complete` em `tasks.md`. Código de T1 a T35 sem mudança desde a rodada 3 (`git diff 9f90936..HEAD` só toca `reports/services.py`, `data_exchange/services.py`, 3 arquivos de teste e `.specs/`) |
| T36 (nomes nos relatórios) | ✅ Done | `12e7688`; `reports/services.py:14-27`, `:414-415`, `:432-433`, `:712-714`, `:765-767`, `:830-831`, `:923-924`, `:1269-1273`, `:1296-1300`; 11 testes em `tests/isolamento/test_relatorios_nomes.py` |
| T37 (nomes na exportação) | ✅ Done | `5b02de0`; `data_exchange/services.py:436-443` (`_do_dono`), PDF `:489-492`, XLS `:535-553`; 2 testes em `tests/isolamento/test_exportacao_nomes.py` |
| T38 (N03 no pagamento e no estorno) | ✅ Done | `99ce9d9`; `tests/isolamento/test_pagamento_fatura.py:30-32`, `:101-132` (2 testes) |

---

## Gate Check

- **Gate command**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`
- **Resultado**: exit 0. `compileall` sem erro. `makemigrations --check` diz "No changes detected". A suíte mostra `Found 175 test(s).`, `Ran 175 tests in 17.530s` e `OK`.
- **Passaram**: 175; **falharam**: 0; **pulados**: 0
- **Contagem de testes**: 0 antes da feature; 138 na rodada 1, 152 na rodada 2, 160 na rodada 3 e 175 agora. A Phase 8 acrescentou 15 testes: 11 (T36), 2 (T37) e 2 (T38). Nenhuma asserção antiga foi removida ou enfraquecida: a T38 só acrescenta linhas a `test_pagamento_fatura.py`.
- **Prints**: a Phase 8 não acrescenta nenhum `print(`. Os `print` de `data_exchange/services.py:140`, `:142` e `:202` já existiam antes da feature.

---

## Spec-Anchored Acceptance Criteria

Helper das recusas: `tests/isolamento/base.py:94-106` (`assert_mesma_recusa`). Ele confere:
- 400 nas duas respostas (`:100-101`);
- o campo (`:102`);
- as mesmas chaves (`:103`);
- o corpo idêntico ao de um ID inexistente (`:104`);
- `resp.data[campo] == [mensagem]` (`:106`).

Helper das leituras de nomes (T36): `tests/isolamento/test_relatorios_nomes.py:49-55` (`obter`). Ele confere o status 200 (`:51`) e `assertNotIn(dado_de_b, str(resp.data))` para cada item de `DADOS_DE_B` (`:53-54`): "Conta B", "Mercado B", "Feira B", "Viagem B", o ícone `icone-de-b` e as cores `#b0b0b0` e `#b1b1b1` (`:18`, `:31-32`).

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| ISOL-01 invariante | Registro ligado só a objetos do dono, ou a nenhum | `test_inventario.py:121` - `assertIsInstance(relacao, OwnedPrimaryKeyRelatedField)`; `:125` - `assertEqual(ESPERADAS - verificadas, set(), ...)`; dados gravados: `test_correcao.py:83` - `assertEqual(find_cross_links(apps), [])`; cópia interna (T34): `test_importar_orcamentos.py:42-43` - `(imported_count, skipped_count) == (1, 2)`, `:44-47` - só `(A, categoria de A, 300.00)`, `:48-49` - nenhum orçamento novo nas categorias de B e modelo, `:54-56` | ✅ (nota residual: o "Restante" do pagamento parcial) |
| ISOL-02 transação com conta, cartão, categoria ou tag de B | 400 no campo, mesma mensagem de inexistente, nada gravado | criação: `test_escrita_transacoes.py:73` - `assert_mesma_recusa(...)`, `:74` - `assertEqual(Transaction.objects.count(), total_antes)`; edição: `:136`, `:137` - `assertEqual(self.estado(t), antes)`; transação já cruzada: `test_edicao_parcial.py:65-67` | ✅ |
| ISOL-03 edição em lote com categoria de B | 400 em `category`, nenhuma ocorrência alterada | `test_escrita_lote.py:50` - `assert_mesma_recusa(resp, resp_inexistente, 'category', 'Categoria não encontrada.')`; `:52` - `assertEqual(self.estado_da_serie(), antes)` | ✅ |
| ISOL-04 categoria-pai de B | 400 em `parent`, nada gravado | `test_escrita_categorias.py:37` - `assert_mesma_recusa(..., 'parent', 'Categoria não encontrada.')`; `:54` - `assertIsNone(categoria.parent_id)` | ✅ |
| ISOL-05 orçamento com categoria de B | 400 em `category`, nada gravado | `test_escrita_orcamentos.py:28` - `assert_mesma_recusa(..., 'category', 'Categoria não encontrada.')`; `:29` - `assertEqual(self.estado_dos_orcamentos(), antes)` | ✅ |
| ISOL-06 meta com conta de B | 400 em `account` | `test_metas.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account', 'Conta não encontrada.')` | ✅ |
| ISOL-07 monitor com categoria ou tag de B | 400 no campo | `test_monitor_foco.py:20` - `assert_mesma_recusa(resp, resp_inexistente, campo, mensagem)` | ✅ |
| ISOL-08 cartão com conta de B | 400 em `account_id` | `test_cartao_fatura.py:24` - `assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')` | ✅ |
| ISOL-09 compra no cartão, transferência, pagamento de fatura, aporte ou resgate, importação | 400 no campo do corpo | `test_escrita_transferencia_cartao.py:40`; `test_cartao_fatura.py:93` (`account_id`); `test_aporte_resgate.py:32`; `test_importacao.py:76` (OFX) e `:84` (planilha); todos com `assert_mesma_recusa(...)` | ✅ |
| ISOL-10 categoria-modelo | Recusa igual à de inexistente | `test_campo.py:71-73` via `assert_recusa` → `:46` - `assertEqual(serializer.errors, {campo: [mensagem]})`; sem `request` e com usuário anônimo (T35): `test_campo.py:109`, `:125` - `assertEqual(serializer.errors, {campo: [mensagem]})`; `bulk_import` com categoria-modelo: `test_importar_orcamentos.py:49` | ✅ |
| ISOL-11 formato da recusa | 400, erro no campo, mesma mensagem em português | `base.py:100-106`; corpo exato: `test_edicao_parcial.py:66` - `assertEqual(resp.data, {campo: [mensagem]})`; `test_escrita_transacoes.py:101` - `{'tags': ['Tag não encontrada.']}` | ✅ |
| ISOL-12 ID de B no endereço | 404 igual a inexistente | `test_endereco_filtros.py:56` - `assertEqual(resp_inexistente.status_code, status, ...)`; `:57` - `assertEqual(resp.data, resp_inexistente.data)` | ✅ |
| ISOL-13 filtros com ID de B | Vazio, igual a inexistente | `test_endereco_filtros.py:158` - `assertEqual(resp.data['results'], [], parametro)`; `:159` - `assertEqual(resp.data, resp_inexistente.data, parametro)`; exportação `:201-203`; relatório de tag `test_relatorios.py:46` (404, igual a inexistente) | ✅ (nota de precisão sobre o relatório de recurso único; caso de ligação já gravada na seção "Ligações já gravadas") |
| ISOL-14 listas e somas só com dados do dono | Subcategorias, transações da conta, compras do cartão, metas do cofrinho, parceira | subcategorias `test_leitura_categorias.py:25` - `== ['Feira A']`; saldo `test_saldo_limite.py:23` - `Decimal('900.00')`; limite `:44` - `Decimal('1700.00')`; total da fatura `test_total_fatura.py:33` - `Decimal('350.00')`; metas `test_signal_metas.py:27`; parceira `test_leitura_transacoes.py:70`; uso do orçamento `test_uso_orcamento.py:33`; `ALL_FUTURE` `test_parcelas_futuras.py:49-50`, `:53-56`, `:65`, `:68-71`. **Pagamento e estorno (T32)**: `test_pagamento_fatura.py:59` - `assertEqual(self.estado(compra_b), antes_b)`, `:60-62` - compra de A `('COMPLETED', cofrinho de A, 100.00)`, `:64` - cofrinho de A `Decimal('-100.00')`, `:65` - saldo de B inalterado, `:66` - fatura `'PAID'`; parcial `:74-83`; estorno `:94-99`. **Compra de B no cartão e na fatura de A (T38)**: pagamento de 150.00, que cobriria as duas compras: `:109` - `assertEqual(self.estado(compra_b), antes_b)`, `:110` - `antes_b[1:3] == ('PENDING', self.b.conta.id)`, `:111-113` - compra de A `('COMPLETED', cofrinho de A, 100.00)`, `:114` - cofrinho de A `Decimal('-100.00')`, `:115` - saldo de B inalterado, `:116` - `'PAID'`; estorno `:127` - 200, `:128` - compra de B inalterada, `:129` - `('COMPLETED', conta de B)`, `:130`, `:131` - compra de A `'PENDING'`, `:132` - `'OPEN'` | ✅ (V09 e V10 mortas) |
| ISOL-15 respostas só com relacionados do dono | Nome da conta, categoria, subcategorias, tags, conta da meta | transação `test_leitura_transacoes.py:43` - `assertIsNone(dados['account'])`; `:88` - `'Desconhecida'`; orçamento `test_leitura_orcamentos.py:36-41`. **Relatórios (T36)**, todos via `obter` (sem nenhum item de `DADOS_DE_B`): `charts/simple`: `test_relatorios_nomes.py:77-81` - `expense_by_category == [{'Sem Categoria', 55.0, '#CBD5E1'}, {'Mercado A', 37.0, '#a0a0a0'}, {'Pendurada A', 15.0, '#a1a1a1'}]` (categoria de B, subcategoria de B e categoria de A pendurada na de B), `:89-92` - receitas; `charts/tag-distribution`: `:99` - `assertNotIn(str(self.b.tag.id), ...)`, `:109-112` - `[{Viagem A, 40.0, '#a2a2a2'}, {'others', 'Outros', 27.0}]`, `:120-123`; `charts/advanced`: `:151-154` - próximo gasto agendado `'Geral'`, controle `:159-162` - `'Mercado A'`; gasto que se repete `:176-179` `'Geral'`, controle `:184-187`; categoria sensível `:198` - `assertIsNone(...)`, controle `:201` - `'Mercado A'`; gasto fixo `:211` - `assertNotIn('Aluguel B', ...)`, `:213` - `{'fixed': 30.0, 'variable': 100.0, 'total': 130.0}`. **Exportação (T37)**: XLS `test_exportacao_nomes.py:60-64` - linhas exatas `('Forjada', '', '', '', 'Viagem A')`, `('Pendurada', 'Conta A', 'Pendurada A', '', '')`, `('Própria', 'Conta A', 'Mercado A', 'Feira A', 'Viagem A')`; `:66-67` - `assertNotIn(nome, texto)` para os 4 nomes de B; PDF `:72-73` - `assertNotIn`; `:75` - `texto.count('(-) Tj') == 2`; `:76-77` - `(Conta A)`, `(Pendurada A)` e `(Feira A)` presentes | ✅ (V01 a V08 mortas; sonda S1 limpa) |
| ISOL-16 verificação | Uma linha por ligação, com tipo, ID e relação | `test_verificacao.py:31` - `assertEqual(como_tuplas(links), sorted(registros.esperadas, key=str))` | ✅ |
| ISOL-17 correção | Relações anuladas; orçamentos, monitores e aportes excluídos | `test_correcao.py:58` - `relatorio.ligacoes == 18`; `:66` - `assertIsNone(getattr(transacao, f'{relacao}_id'))`; `:79` - `assertFalse(Budget.objects.filter(pk=r.orcamento.pk).exists())`; `:83` | ✅ |
| ISOL-18 recálculo pela SALDO-01 | Saldo = inicial + entradas − saídas efetivadas do dono | `test_correcao.py:93` - `assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('900.00'))` | ✅ |

**Status**: ✅ 18 de 18 ACs têm evidência que confere com a spec. Continuam 3 spec-precision gaps, nenhum bloqueante (ver abaixo).

**Regra de payload e conjunção** (testes novos):
- T36 compara listas inteiras (nome, valor e cor de cada fatia) e o dicionário inteiro do próximo gasto. Cada caso com B tem um controle positivo com A.
- T37 compara as linhas inteiras da planilha, nas 5 colunas relevantes, e confere no PDF a ausência dos nomes de B, a presença dos nomes de A e a contagem exata de `-`.
- T38 confere a tupla inteira da compra de B, a compra de A com valores exatos, o saldo exato do cofrinho de A, o saldo de B e o status da fatura.

**Correção de citações da rodada 3**: `test_importar_orcamentos.py:114-127` não existia (o arquivo tem 56 linhas e não mudou desde `24d7ec7`). As asserções certas são `:42-49` e `:54-56`. Em `test_pagamento_fatura.py`, as linhas depois de `:28` desceram 4 (T38 acrescentou `:30-32`). Todas as outras citações da rodada 3 continuam nas mesmas linhas, com a mesma asserção.

---

## Edge Cases

- [x] ID inexistente e ID de B dão respostas idênticas: `base.py:104` (corpo) e `test_endereco_filtros.py:57` (endereço).
- [x] Tag de B entre tags próprias recusa a transação inteira: `test_escrita_transacoes.py:100-102`.
- [x] Transferência com origem própria e destino de B é recusada: `test_escrita_transferencia_cartao.py:54-58` (`assert_recusa` em `account_to`).
- [x] Conta própria excluída: fica com a SALDO-35, fora do escopo.
- [x] Mapeamento de importação para conta de B: o isolamento está garantido. Nada é gravado em B nem ligado a B (`test_importacao.py:99-101`). A rejeição "Conta não mapeada" pertence à IMPORT-21 (`importacao/spec.md`, `Pending`). A conta padrão de B recusa a importação inteira: `test_importacao.py:84`.
- [x] Edição de transação própria já ligada a B: `test_edicao_parcial.py:62-67`.

---

## Success Criteria

| Critério | Evidência | Status |
| -------- | --------- | ------ |
| Um teste automatizado percorre todas as relações graváveis com IDs de B e recebe 400 com o corpo de um ID inexistente | `test_inventario.py:121`, `:125`, mais o teste HTTP de cada relação (tabela acima) | ✅ |
| Depois da correção em produção, a verificação não lista nada | Operacional; em teste: `test_correcao.py:83` | ⏭️ Só verificável em produção |
| Nenhum endpoint devolve dado de B no teste com dois usuários | Relatórios e exportação: `test_relatorios_nomes.py:53-54` e `test_exportacao_nomes.py:66-67`, `:72-73`. A sonda S1 cobre 11 respostas com uma ligação cruzada gravada, sem nenhum nome de B | ✅ |

---

## Sonda S1 repetida (código atual)

Teste temporário só na worktree, removido antes do sensor. Cenário da rodada 3: despesa de A de 40.00 em 2026-09-05, com `account` = conta de B, `category` = categoria de B e a tag de B. Procurei nas respostas "Conta B", "Mercado B", "Feira B", "Viagem B", "Cartão B", "Cofrinho B" e "Meta B".

| Resposta | Status | Nomes de B encontrados |
| -------- | ------ | ---------------------- |
| `charts/simple` (09/2026) | 200 | nenhum (na rodada 3: "Mercado B") |
| `charts/tag-distribution` (09/2026) | 200 | nenhum (na rodada 3: "Viagem B") |
| `charts/advanced` | 200 | nenhum |
| `dashboard`, `calendar`, `charts/monthly-comparison` | 200 | nenhum |
| `charts/tag-insights` (tag de A) | 200 | nenhum |
| `focused-monitors/`, `transactions/` | 200 | nenhum |
| `export/transactions/xls/` | 200 | nenhum (na rodada 3: "Mercado B", "Viagem B" e "Conta B") |
| `export/transactions/pdf/` | 200 | nenhum |

Resultado da sonda: o vazamento da rodada 3 não se reproduz.

---

## Discrimination Sensor

**Profundidade**: leve e focada (rodada extra): 12 mutações de comportamento, feitas à mão, sobre T36, T37, T38 e o núcleo.

**Isolamento**:
1. Baseline de `git status --porcelain` da árvore real: vazio.
2. Criei a worktree com `git worktree add --detach ../fluxar-backend-verif4 HEAD`.
3. Os testes rodaram com `docker run --rm --network fluxar-backend_default --env-file .env -e DB_HOST=db -v <worktree>:/app fluxar-backend-backend python manage.py test tests.isolamento --noinput`.
4. Um script aplicava cada mutação, rodava a suíte e restaurava os bytes originais. Ele trata o CRLF da worktree e exige exatamente uma ocorrência antes de aplicar.
5. Removi a worktree com `git worktree remove --force` e rodei `git worktree prune`. Não usei `git stash`.

**Controle**: a worktree sem mutação rodou 175 testes, `OK`.

| Mutação | File:line | Descrição | Killed? |
| ------- | --------- | --------- | ------- |
| V01 | `reports/services.py:22` | T36: `_categoria_do_usuario` com `When(category__isnull=False, ...)`, sem conferir o dono da categoria | ✅ Killed (2: `test_relatorios_nomes.py:63`, `:83`) |
| V02 | `reports/services.py:23` | T36: `_categoria_do_usuario` usa a categoria-pai sem conferir o dono dela | ✅ Killed (1: `:63`, "Pendurada A" sob a categoria de B) |
| V03 | `reports/services.py:1273` | T36: despesas por tag com `tags__isnull=False` no lugar de `tags__user=user` | ✅ Killed (1: `:102`) |
| V04 | `reports/services.py:1297` | T36: "Outros" das receitas volta a `filter(tags__isnull=True)` | ✅ Killed (1: `:114`) |
| V05 | `reports/services.py:713` | T36: próximo gasto agendado usa a categoria sem conferir o dono | ✅ Killed (1: `:148`) |
| V06 | `data_exchange/services.py:489-490` | T37: PDF usa `tx.account` e `tx.category` direto | ✅ Killed (1: `test_exportacao_nomes.py:69`) |
| V07 | `data_exchange/services.py:553` | T37: XLS escreve todas as tags, inclusive as de B | ✅ Killed (1: `:55`) |
| V08 | `data_exchange/services.py:541` | T37: XLS usa a categoria-pai com `categoria.parent_id`, sem conferir o dono | ✅ Killed (1: `:55`) |
| V09 | `accounts/services.py:135` | N03: `pay_invoice` filtra por `credit_card_id=invoice.card_id` em vez do dono | ✅ Killed (1: `test_pagamento_fatura.py:101`) |
| V10 | `accounts/services.py:240` | N03 no estorno: `unpay_invoice` filtra por `credit_card_id=invoice.card_id` | ✅ Killed (1: `:118`) |
| V11 | `core/fields.py:44` | Núcleo: `get_queryset` do `OwnedPrimaryKeyRelatedField` sem filtro do dono | ✅ Killed (42) |
| V12 | `accounts/services.py:20` | Núcleo: `get_balance` soma transações de outro usuário | ✅ Killed (1: `test_saldo_limite.py`) |

**Resultado do sensor**: 12 mutações, 12 mortas, nenhuma sobrevivente. Sensor ✅.

**Isolamento conferido**: no fim, a worktree estava limpa (`git status --porcelain` vazio), foi removida, e `git worktree list` mostra só a árvore real. O porcelain da árvore real mostra só ` M .specs/features/isolamento-entre-usuarios/validation.md`, o próprio relatório. Os arquivos de lições são atualizados depois, pelo `lessons.py`.

**Rodadas anteriores** (conforme os relatórios em `7b31831`, `2ae2c6a` e `4df79de`):
- Rodada 1: 32 mutações, 32 mortas.
- Rodada 2: 24 mutações. 22 mortas, 1 equivalente (M16) e 1 sobrevivente real (M13), que virou a T35.
- Rodada 3: 20 mutações. 19 mortas e 1 sobrevivente real (N03), que virou a T38.
- Nesta rodada, a N03 (V09) e o equivalente dela no estorno (V10) foram mortos.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Mínimo de código | ✅ T36: 1 helper (`_categoria_do_usuario`) e filtros pontuais; T37: 1 helper (`_do_dono`) usado no PDF e no XLS; T38: só teste |
| Mudanças cirúrgicas | ✅ Cada commit da Phase 8 toca só o arquivo da tarefa, o teste e `tasks.md` |
| Sem scope creep | ✅ O PDF agora sai com "-" para uma transação sem conta. É efeito direto de tratar a conta de B como ausente, e está no corpo do commit |
| Segue os padrões | ✅ O mesmo filtro pelo dono e o comentário `(ISOL-15)` das fases anteriores |
| Spec-anchored | ✅ |
| Cobertura por camada | ✅ Cada ponto alterado da T36 tem teste com controle positivo; o PDF e o XLS têm teste próprio |
| Todo teste mapeia um AC, edge case ou Done-when | ✅ `test_relatorios_nomes.py` e `test_exportacao_nomes.py` → ISOL-15; `test_pagamento_fatura.py:101-132` → ISOL-14 |
| Diretrizes documentadas | AD-010, AD-019, AD-024, AD-028, AD-032 e AD-033 seguidas |
| SPEC_DEVIATION | `core/isolation.py:28-33` (`parent_transaction` e `recurring_source`). Justificada e coberta; sem mudança nesta rodada |

---

## Varredura de nomes de relacionados (`reports/services.py` e `data_exchange/services.py`)

Procurei `__name`, `__color`, `__icon`, `.name`, `.icon`, `.color`, `category__`, `tags__`, `account__`, `invoice__` e buscas em `Category`, `Tag`, `Account` e `CreditCard`.

- **Nome, ícone ou cor, agora pelo dono (ok)**: `reports/services.py:14-27` e o uso em `:414-415` e `:432-433` (pizza de categorias); `:712-714` (próximo gasto agendado); `:765-767` (gasto que se repete); `:830-831` (gasto fixo pelo nome); `:923-924` (categoria sensível); `:1269-1273` e `:1296-1300` (tags e "Outros"); `data_exchange/services.py:489-492` (PDF) e `:535-553` (XLS: conta, categoria, categoria-pai e tags).
- **Já conferidos pelo dono antes da Phase 8 (ok)**: `reports/services.py:590-594`, `:601`, `:667-669` (monitor de foco); `:1162`, `:1242-1243` (tag insights, tag buscada com `user=user`).
- **Objetos do próprio usuário por construção (ok)**: `reports/services.py:132-165` (cartões com `user=user`); `:518-577` (contas de investimento com `user=user`).
- **Sem nome, mas com atributo de um relacionado sem conferir o dono (nota residual)**: `account__type='INVESTMENT'` em `reports/services.py:112`, `:212`, `:223`, `:266`, `:271`, `:545`, `:549`, `:557`, e `invoice__year`/`invoice__month` em `:102`, `:619` e `:1180`. Com uma ligação cruzada antiga, o tipo da conta de B ou o mês da fatura de B decide se uma transação de A entra num total de A. Não sai nenhum nome nem valor de B, os totais somam só transações de A, e a migração `0007` desfaz a ligação. Ver o julgamento abaixo.

Não achei nenhum outro nome de relacionado exibido sem conferir o dono.

---

## Ligações já gravadas (julgamento desta rodada)

As duas situações abaixo só existem com uma ligação cruzada gravada antes da correção. A API não cria mais nenhuma (ISOL-01 a ISOL-11), e a migração `0007` desfaz as antigas no mesmo deploy (ISOL-17).

1. **`account__type='INVESTMENT'` e `invoice__year/month` nos relatórios.** O filtro usa o tipo da conta de B (ou o mês da fatura de B) para incluir ou excluir uma transação **de A** num total **de A**. Julgamento: **nota residual, não falha**.
   - ISOL-15 fala de dados de relacionados na resposta, e nenhum aparece.
   - ISOL-14 fala de somar os dados ligados a um objeto, e aqui a soma é só de transações do próprio A.
   - O critério de sucesso 3 pede que nenhum dado de B seja devolvido. No máximo, A deduz um bit (o tipo de uma conta de B) de um ID que ele mesmo ligou, e só antes da migração.
2. **Filtro de lista ou exportação por um ID de B com ligação antiga (sonda S3, nova).** Com a despesa de A ligada à conta e à categoria de B, `GET /api/transactions/?accountId=<conta de B>` e `?categoryId=<categoria de B>` trazem 1 resultado, e um ID inexistente traz 0. Depois de `fix_cross_links(apps)`, os dois trazem 0. O resultado é a transação do próprio A, com `account` nulo (ISOL-15), e nenhum campo de B. Julgamento: **spec-precision gap, não falha**. Pela letra, a ISOL-13 pede "resultado vazio", mas a justificativa dela na spec é "não revela nada", e nada de B é revelado. O caso é o mesmo gap aberto desde a rodada 2 (defesa contra ligações já gravadas). O design (`design.md:114`) trata os filtros como já restritos ao usuário. Diferença do gap 1 da rodada 3: lá, nomes de B apareciam na resposta.

---

## Spec-precision gaps

1. **ISOL-13, relatório de recurso único** (desde a rodada 1): `tag-insights` responde 404, igual a uma tag inexistente (`test_relatorios.py:46`). Não afeta o isolamento. Recomendação: registrar na spec que um relatório de recurso único segue a ISOL-12.
2. **Edge case 5 → IMPORT-21** (desde a rodada 1): a rejeição da linha pertence à spec `importacao`.
3. **Defesa contra ligações já gravadas** (desde a rodada 2): a spec não diz se cada caminho de servidor precisa conferir o dono das relações já gravadas, ou se basta a correção ISOL-17 (migração `0007`, no mesmo deploy). Nesta rodada, os caminhos que mostravam dado de B estão fechados. Restam os dois casos da seção anterior, sem dado de B. Recomendação: registrar em STATE.md que, fora da exibição de dados de outro usuário, as ligações antigas ficam cobertas pela ISOL-17 e pela migração `0007`.

---

## Resolução dos gaps anteriores

| Gap | Resolução | Evidência |
| --- | --------- | --------- |
| R3-1. ISOL-15 e critério de sucesso 3: relatórios e exportação mostravam nomes de B | ✅ Resolvido (T36, T37) | `reports/services.py:14-27`, `:712-714`, `:765-767`, `:830-831`, `:923-924`, `:1269-1273`, `:1296-1300`; `data_exchange/services.py:436-443`, `:489-492`, `:535-553`; `test_relatorios_nomes.py:53-54`, `:77-81`, `:109-112`; `test_exportacao_nomes.py:60-67`, `:72-77`; V01 a V08 mortas; sonda S1 limpa |
| R3-2. Mutante N03 em `pay_invoice` | ✅ Resolvido (T38) | `test_pagamento_fatura.py:30-32`, `:109-116`, `:128-132`; V09 (N03) e V10 (N03 no estorno) mortas |
| R2-1. Pagamento e estorno mexiam em compras de B | ✅ Resolvido (T32) | `accounts/services.py:135`, `:240`; `test_pagamento_fatura.py:59-66`, `:74-83`, `:94-99` |
| R2-2. `ALL_FUTURE` alterava a parcela de B | ✅ Resolvido (T33) | `transactions/serializers.py:295-296`; `test_parcelas_futuras.py:49-56`, `:65-71` |
| R2-3. `bulk_import` copiava a categoria de B | ✅ Resolvido (T34) | `budgets/views.py:96-98`; `test_importar_orcamentos.py:42-49`, `:54-56` |
| R2-4. Mutante M13 (ramo sem `request`) | ✅ Resolvido (T35) | `core/fields.py:42-43`; `test_campo.py:103-125` |
| R1-1 a R1-3. Leitura do orçamento, uso do orçamento, edição parcial | ✅ Resolvidos (T29, T30, T31) | `test_leitura_orcamentos.py:36-41`; `test_uso_orcamento.py:33`; `test_edicao_parcial.py:65-67` |
| R1-4. Edge case 5 | ➡️ IMPORT-21 | Spec-precision gap 2 |
| R1-5. `tag_id` com 404 | ⚠️ Nota de precisão | Spec-precision gap 1 |

---

## Notas residuais (não bloqueiam)

- Edge case 5: a rejeição "Conta não mapeada" pertence à IMPORT-21, na spec `importacao`.
- ISOL-13: `tag-insights` com `tag_id` de B responde 404 (nota de precisão).
- `unpay_invoice` usa `QuerySet.update()` (`accounts/services.py:244`), então o `Account.balance` guardado não é revertido. Esse problema é do modelo de saldo e fica com a spec `saldo`.
- `pay_invoice`, pagamento parcial: o "Restante" copia `category`, `tags` e `parent_transaction` da compra de A (`accounts/services.py:195-212`). Isso só importa com uma ligação já gravada, que a migração `0007` desfaz.
- Relatórios: `account__type='INVESTMENT'` e `invoice__year/month` usam o atributo de um relacionado de B numa ligação antiga (ver "Ligações já gravadas", item 1).
- Filtros por ID de B com ligação antiga trazem a transação do próprio A (sonda S3; ver "Ligações já gravadas", item 2).
- `bulk_import` faz uma consulta por orçamento de origem (`budget.category.user_id`). É um custo pequeno, sem efeito sobre o isolamento.

---

## Requirement Traceability Update

Recomendação (a verificação não edita `spec.md`):

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| ISOL-01 a ISOL-18 | Pending | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready.

**Spec-anchored check**: 18 de 18 ACs conferem com a spec. Continuam 3 spec-precision gaps, nenhum bloqueante.
**Sensor**: 12 mutações, 12 mortas.
**Gate**: 175 passaram, 0 falharam, 0 pulados.

**O que funciona**:
- Os dois gaps da rodada 3 estão resolvidos e discriminados.
- Relatórios e exportação não mostram nome, ícone ou cor de B, mesmo com uma ligação cruzada gravada.
- Continuam de pé a recusa por campo, o 404 no endereço, as listas vazias, as somas pelo dono, a verificação, a correção, o comando e a migração.

**Próximos passos**: registrar em STATE.md a decisão sobre ligações já gravadas (spec-precision gap 3) e atualizar a rastreabilidade em `spec.md`.

---

## validate_state

`python validate_state.py isolamento-entre-usuarios --root .` terminou com exit 0:

```
validate_state: 0 error(s) across [isolamento-entre-usuarios]
```

---

## Lições

Os spec-precision gaps desta rodada são os mesmos das rodadas anteriores, que já têm lição (L-004, L-005 e L-008). Não criei lição nova. Acrescentei evidência às lições já existentes com `lessons.py add`:
- L-008 recebeu a sonda S3 e os filtros `account__type` como evidência nova do gap 3.
- L-009 e L-010 receberam a evidência da resolução: T36/T37 com V01 a V08 mortas, e T38 com V09 e V10 mortas.
