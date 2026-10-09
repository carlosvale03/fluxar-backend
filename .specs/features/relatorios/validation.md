# Relatórios Validation

**Date**: 2026-10-08
**Spec**: `.specs/features/relatorios/spec.md`
**Diff range**: backend `fix/relatorios-calculos-periodos-e-exportacao` (`18a027d..b3a7b0e`, 14 commits: 1 de design/tasks, 10 de código e testes, 3 de marcação das tasks); frontend `fix/relatorios-calculos-periodos-e-exportacao` (`485d911..38c031c`, 3 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve, uma rodada
**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T13 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md` (T1 a T10 no backend, T11 a T13 no frontend). O cabeçalho de `tasks.md` ainda diz `Status: In Progress` (observação 6) |

---

## Gate Check

### Backend

- **Comando**: `docker compose exec -T backend python manage.py test --noinput`
- **Resultado**: exit 0. `Ran 1025 tests in 292.752s ... OK`
- **Falhas**: nenhuma. **Skips**: nenhum. O teste instável conhecido (`tests.importacao.test_sugestao.test_linha_com_categoria_no_arquivo_mantem_a_do_arquivo`) passou nesta rodada
- **Contagem**: 959 antes da feature (`def test_` em `18a027d`), 1025 depois: +66, todos em `tests/relatorios/` (`manage.py test tests.relatorios` roda 66)
- **Migrações**: `python manage.py makemigrations --check --dry-run` → `No changes detected`
- **Testes antigos ajustados**: `tests/contratos/base.py` e `tests/saldo/test_totais.py` passam a preencher `report_date` no `bulk_create` (que não chama o `save()`); `tests/isolamento/test_exportacao_nomes.py` troca o `-` da conta pela conta em branco (REL-25), mantendo o `-` da categoria e a ausência dos nomes de B. Nenhuma asserção foi retirada sem substituta

### Frontend

| Gate | Resultado |
| ---- | --------- |
| `npm test` | 59 arquivos, 313 testes, todos passando (299 antes da feature, +14 em `tests/relatorios/`) |

Nenhum teste antigo do frontend foi alterado na faixa.

---

## Spec-Anchored Acceptance Criteria

Os caminhos `tests/relatorios/*.py` são do `fluxar-backend`. Os marcados **FE** estão em `tests/relatorios/` do `fluxar-frontend`.

### P1: Transações que entram nos relatórios

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| REL-01 despesas efetivadas na data e compra no cartão na data da compra, fatura aberta | 100 efetivada + 80 no cartão (fatura de 15/04) = 180,00 no mês | `tests/relatorios/test_regras.py:31` - `despesas == 180.00`; `test_dashboard.py:38` - `monthly_expense == '180.00'`; `test_graficos.py:62-71` - calendário, pizza e comparação `180.00`, abril `0.00`; `test_data_no_relatorio.py:41-42` - `date 15/04`, `report_date 10/03` | ✅ PASS |
| REL-02 parcela N no mesmo dia, N-1 meses depois, último dia quando falta | TV 1.200 em 12x em 31/01: 100,00 em 31/01, 28/02, 31/03... | `tests/relatorios/test_data_no_relatorio.py:48-49` - `report_date` das 12 parcelas `== TV_EM_12X` e valores `{100.00}`; `test_regras.py:50-51` - fevereiro `100.00` em `28/02` | ✅ PASS |
| REL-03 fora: pendentes, transferências, pagamento de fatura, ajuste | só a efetivada conta | `tests/relatorios/test_regras.py:42-43` - transferência, `INVOICE_PAYMENT`, ajuste de 0,20 → `despesas == 30.00`, `a_pagar == 0.00`; `:58-59` pendente de fevereiro fora das despesas | ✅ PASS |
| REL-04 "A pagar" à parte no dashboard | 50,00 "A pagar" | `tests/relatorios/test_dashboard.py:39` - `payable == '50.00'` (e `:48` com `days`); FE `dashboard-a-pagar-e-patrimonio.test.tsx:89-92` - grupo "A pagar" com `R$ 50,00`, "Despesas do Mês" com `R$ 180,00` | ✅ PASS |
| REL-05 receitas só efetivadas, sem transferência e ajuste | 5.000,00 | `tests/relatorios/test_regras.py:80-81` - `receitas == 5000.00` (pendente, transferência, ajuste e abril fora); `test_dashboard.py:59-61`; `test_graficos.py:123-133` | ✅ PASS |
| REL-06 gasto do orçamento pelas mesmas despesas | parcela do mês; pendente e ajuste fora | `tests/relatorios/test_orcamentos.py:34-37` - `[100, 100, 100, 0]`; `:50` - `35.00` (subcategoria entra, pendente e ajuste fora); `:56-57` compra com fatura aberta conta em março; `test_consistencia.py:43-53` - orçamento `180.00` igual às rotas | ✅ PASS |
| REL-07 contas excluídas nas receitas/despesas, fora do saldo | 25,00 e 40,00 no período; conta excluída fora do patrimônio | `tests/relatorios/test_regras.py:67-68` - `25.00` / `40.00`; `test_graficos.py:100-102` - calendário, pizza e comparação `25.00`; `test_regras.py:121-131` - conta excluída de 999,00 fora do patrimônio `5350.00` | ✅ PASS |
| REL-08 hoje e limites do mês em Brasília | 23h de 31/03 em Brasília ainda é março | `tests/relatorios/test_regras.py:99-100` - `mes_atual() == (2026, 4)` às 02h UTC de 01/05; `:94-95` limites com 29/02; `test_dashboard.py:68-71` - dashboard sem mês às 02h UTC de 01/04 → `180.00` (abril fora) | ✅ PASS |
| REL-09 hora do dia em Brasília | despesa das 22h aparece às 22h | `tests/relatorios/test_avancados.py:42` - `spending_frequency == [{'day_of_week': 3, 'hour_of_day': 22, 'count': 1}]`; `test_regras.py:110` - `(hora, dia) == (22, 3)` | ✅ PASS |
| REL-10 contas em decimal, duas casas no fim | valores em `Decimal`/texto, sem float | `tests/relatorios/test_avancados.py:175-180` - nenhum float fora de `volatility_score`, `total_invested '1333.33'`, `fixed_vs_variable.total '0.30'`; `test_regras.py:32`, `:82`, `:132`, `:186` - `assertIsInstance(..., Decimal)`; `test_graficos.py:155-162` - sem `float(` nas funções | ✅ PASS (observação 4) |
| REL-11 projeção num dia inexistente → último dia | 31 de fevereiro → 28/02 | `tests/relatorios/test_avancados.py:132-134` - `next_big_expense.date == '2026-02-28'` | ✅ PASS (observação 3) |
| REL-12 `months` fora de 1 a 24 → 400 | 400, "O parâmetro months aceita de 1 a 24." | `tests/relatorios/test_parametro_months.py:31-33` - `1000`, `0`, `abc`, `2.5`, `-3`, `25`, `''` nas duas rotas → `400` e `detail == MENSAGEM` (`:11`, texto exato); `:35-41` 1 e 24 → 200 | ✅ PASS |

### P1: Patrimônio, liquidez e reservas

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| REL-13 contas ativas menos compras não pagas | 3.000 + 800 + 2.000 − 450 = 5.350,00 | `tests/relatorios/test_regras.py:127-131` - `total == 5350.00`; `test_dashboard.py:84` - `net_worth == '5350.00'`; `test_consistencia.py:75` - `10350.00` igual no dashboard e no último ponto da evolução | ✅ PASS |
| REL-14 disponível = correntes, poupanças e carteiras | 3.000,00 (sem cofrinho e investimento) | `tests/relatorios/test_saude_financeira.py:110-111` - `total_liquid_balance == '3000.00'`, `liquidity_ratio == 6.0`; `test_regras.py:127-128` - `disponivel 3000.00` | ✅ PASS |
| REL-15 patrimônio separado em quatro partes | 3.000 / 800 / 2.000 / 450 | `tests/relatorios/test_dashboard.py:85-87` - `net_worth_breakdown == {available 3000.00, reserves 800.00, investments 2000.00, open_invoices 450.00}`; FE `dashboard-a-pagar-e-patrimonio.test.tsx:98-105` - região "Patrimônio" com `R$ 5.350,00` e as quatro partes (`- R$ 450,00`) | ✅ PASS |
| REL-16 histórico no fim de cada mês, efetivadas até o dia e compras não pagas nele | pendente não conta; compra paga depois ainda é dívida | `tests/relatorios/test_regras.py:152-159` - janeiro `1200.00` (compra paga em 15/02 ainda em aberto), fevereiro `950.00`; `test_avancados.py:57-64` - seis pontos de fim de mês, `1500.00` → `1200.00` com a compra de 20/02 | ✅ PASS |
| REL-17 cada mês do calendário uma vez | seis meses a partir de 31/03: outubro a março | `tests/relatorios/test_regras.py:89-91` - `[(2025,10) ... (2026,3)]`; `test_graficos.py:144`, `:150` - comparação e histórico da tag; `test_avancados.py:57-64`, `:80-87` - evolução e investimentos com um item por mês | ✅ PASS |
| REL-18 faturas do mês = em aberto das faturas que vencem no mês atual | 150,00; paga e de outro mês fora | `tests/relatorios/test_regras.py:224-229` - `150.00`, `150.00` às 23h de 31/03 em Brasília, `80.00` em abril; `test_dashboard.py:112` - `total_current_invoices == '150.00'`; FE `dashboard-a-pagar-e-patrimonio.test.tsx:111-112` | ✅ PASS |

### P1: Score financeiro e dinheiro guardado

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| REL-19 −5 por orçamento estourado, até zerar 20 | 4 dentro → 20; 1 estourado → 15 | `tests/relatorios/test_saude_financeira.py:49` - `financial_score == 20`; `:55` - `15`; `:60` - cinco estourados → `0`; `test_orcamentos.py:77-84` - mesmo estouro no score (`15`), no dashboard e na lista de orçamentos | ✅ PASS |
| REL-20 dinheiro guardado pelo fluxo | 500 + 300 − 100 = 700,00; saldo livre não muda | `tests/relatorios/test_regras.py:184-185` - `700.00`; `:194` - cofrinho ↔ investimento `0.00`; `:201-202` - aporte do saldo livre `0.00`; `test_saude_financeira.py:84` - `saved_this_month == '700.00'` | ✅ PASS (observação 1) |
| REL-21 taxa = guardado / receitas | 14,0% | `tests/relatorios/test_saude_financeira.py:85` - `savings_rate == 14.0`; `test_consistencia.py:81` | ✅ PASS |
| REL-22 receitas zero → indisponível | `null`, sem divisão | `tests/relatorios/test_saude_financeira.py:97` - `assertIsNone(savings_rate)` com 700,00 guardados; FE `taxa-indisponivel-e-media-zero.test.tsx:102-104` - "Indisponível" duas vezes, sem `Infinity`/`NaN`/`null` nem `0%` | ✅ PASS |

### P1: Telas e exportação

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| REL-23 média zero → "Sem histórico para comparar" | texto no lugar da porcentagem | FE `taxa-indisponivel-e-media-zero.test.tsx:120-122` - monitor de foco: texto exato, nenhum `\d+%`, nada impossível; `:147-149` - monitor da tag, igual; `:130` - com média, `75%` | ✅ PASS |
| REL-24 erro só no bloco, com "Tentar de novo" | comparação fora do ar: só ela com erro, demais carregam | FE `erro-por-bloco.test.tsx:109-118` - região "Comparação mensal" com "Tentar de novo", um botão só, "Mercado", "Viagem", "Distribuição de Gastos" e "Despesas por Tag" na tela; `:127-134` - tentar de novo chama só `getMonthlyComparison` (2×) e o gráfico volta; `:137-184` os outros blocos | ✅ PASS |
| REL-25 PDF com transação sem conta: gerado, conta em branco | arquivo gerado; conta vazia | `tests/relatorios/test_exportacao_pdf.py:36-39` - `200`, `application/pdf`, `%PDF`, os dois valores; `:53-56` - linha sem conta com a coluna 180 `''` e a com conta `'Corrente A'` | ✅ PASS |

**Status**: ✅ 25/25 ACs com evidência no valor definido pela spec, incluindo os valores exatos dos quatro Independent Tests; nenhuma lacuna de precisão.

---

## Edge Cases

- [x] Pendente de mês passado continua em "A pagar" daquele mês e fora das despesas (`test_regras.py:53-59`)
- [x] Transferência cofrinho ↔ investimento não muda o dinheiro guardado (`test_regras.py:189-194`; observação 1)
- [x] Pagamento de fatura fora das despesas (`test_regras.py:38`, `:42`)
- [x] Ajuste de saldo de 0,20 para baixo fora das despesas (`test_regras.py:39`, `:42`; `test_data_no_relatorio.py:114-122` grava a marca); muda o patrimônio pelo saldo da conta (regra geral do saldo, sem teste próprio)
- [x] Projeção para 31 de fevereiro vira 28 (`test_avancados.py:132-134`); a volta ao dia 31 no mês seguinte não tem teste na projeção, só nas parcelas (31/03 em `TV_EM_12X`) (observação 3)
- [x] Orçamento com compra parcelada recebe só a parcela do mês (`test_orcamentos.py:31-37`)
- [x] Mês sem receita → taxa indisponível (`test_saude_financeira.py:87-97`)

---

## Discrimination Sensor

**Isolamento no backend**: worktree descartável `../fluxar-backend-mut` (detached em `b3a7b0e`) e container avulso: `docker run --rm --network fluxar-backend_default --env-file <.env do backend> -v <worktree>:/app -w /app fluxar-backend-backend python manage.py test tests.relatorios --noinput` (o serviço `backend` só usa o `env_file: .env`). Os mutantes rodaram depois do gate inteiro, para não disputar o banco de teste. Sem mutação, os 66 testes passaram no worktree (BASE). Cada mutação foi aplicada por um script que exige uma ocorrência única do trecho e revertida com `git checkout -- .` no worktree, conferido limpo (`git diff --quiet`) antes da seguinte.

**Isolamento no frontend**: sem worktree e sem junction de `node_modules`. A mutação foi aplicada no arquivo real pelo mesmo script (leitura e escrita em bytes, CRLF preservado), `npx vitest run tests/relatorios` rodou (14 testes) e o arquivo foi restaurado com `git checkout -- <arquivo>`. Depois, `git diff --quiet` e `git status --porcelain` estavam vazios e `git hash-object` era igual a `git rev-parse HEAD:<arquivo>` (`341b4d3`).

| # | File:line | Descrição | Killed? |
| - | --------- | --------- | ------- |
| M1 | `transactions/models.py:162` | `report_date` sem o deslocamento da parcela (`meses = data_da_compra.month - 1`) | ✅ Killed (6 falhas: parcelas, edição da compra, restante, comparação, orçamento, regras) |
| M2 | `reports/regras.py:91` | Despesas incluem as pendentes (`Q(type='EXPENSE')`) | ✅ Killed (12 falhas: dashboard, gráficos, monitor, mapa de calor, orçamento, consistência, regras) |
| M3 | `reports/regras.py:92` | Ajuste de saldo conta como despesa (sem `is_balance_adjustment=False`) | ✅ Killed (4 falhas: regras, dashboard, gráficos, orçamento) |
| M4 | `reports/regras.py:170` | Patrimônio sem descontar o cartão (`- faturas` removido) | ✅ Killed (5 falhas: regras atual e no fim do mês, dashboard, evolução, consistência) |
| M5 | `reports/regras.py:195` | Transferências entre cofrinho e investimento contam (`Q(pk__isnull=False)`) | ✅ Killed (1 falha: histórico de investimentos; veja observação 1) |
| M6 | `reports/services.py:276` | Score desconta todo orçamento do mês (`if True`) | ✅ Killed (3 falhas: 4 dentro → 20, 1 estourado → 15, score igual ao dashboard) |
| M7 | `reports/regras.py:74` | Mapa de calor em UTC (`ExtractHour(campo)`) | ✅ Killed (2 falhas: mapa de calor e hora em Brasília) |
| F1 | `src/app/(app)/relatorios/page.tsx:796` (FE) | "Sem histórico para comparar" vira porcentagem (`` `${Math.round(percentual ?? 0)}%` ``) | ✅ Killed (2 falhas: monitor com média zero e taxa indisponível, que confere a ausência de `0%`) |

**Verificação do isolamento**: `git status --porcelain` vazio nos dois repositórios depois do sensor, exceto este `validation.md`. `git worktree list` mostra só a árvore principal nos dois, e a pasta `fluxar-backend-mut` não existe mais. Os únicos containers no ar são `fluxar-backend-backend-1` e `fluxar-backend-db-1` do compose.

**Sensor depth**: leve (8 mutações de comportamento, 7 no backend e 1 no frontend, por decisão do usuário)
**Result**: 8/8 killed, 0 survived - PASS

---

## Code Quality (nível leve, amostragem)

| Princípio | Status |
| --------- | ------ |
| Fonte única das regras | ✅ `reports/regras.py` usado pelo dashboard, saúde, gráficos, avançados e orçamentos (`budgets/services.py`) |
| Data no relatório | ✅ `Transaction.report_date` recalculada no `save()` (inclusive com `update_fields`), migração `0011` repete a regra com modelos históricos e `0012` torna o campo obrigatório |
| Ajuste de saldo | ✅ campo `is_balance_adjustment` gravado pelo `adjust-balance`; os trocos passaram a usá-lo em vez da descrição |
| Reuso | ✅ `dia_no_mes`, `mes_anterior`, `hoje`/`BRASILIA`, `ENTRADAS`/`SAIDAS`, `dinheiro`, `tratarErro` |
| Testes mapeados aos ACs | ✅ docstrings citam os IDs; asserções nos valores exatos dos Independent Tests e no texto exato da mensagem do REL-12 |
| Testes antigos ajustados | ✅ só o preenchimento de `report_date` no `bulk_create` e a conta em branco no PDF |
| Guidelines | AD-033 e AD-034 (testes no container e no vitest) seguidos |

---

## Observações (não bloqueiam)

1. **REL-20 e transferências internas.** Uma transferência entre cofrinho e investimento soma +X numa perna e −X na outra; por isso o total do dinheiro guardado não muda mesmo se o filtro das transferências internas sair (M5). O teste `test_regras.py:189-194` passa com ou sem o filtro; o mutante morreu pelo histórico de investimentos (`test_avancados.py:80-87`). É um mutante equivalente para o total, não uma lacuna do REL-20.
2. **"A pagar" nos relatórios de despesas.** O REL-04 diz "dashboard ou um relatório de despesas"; só o dashboard expõe `payable` (backend e FE). Atende a spec como escrita.
3. **Projeção com volta ao dia 31.** O edge case "o mês seguinte volta ao dia 31" está coberto nas parcelas (`TV_EM_12X`), não na projeção do próximo grande gasto.
4. **REL-10 por inspeção de fonte.** Parte da evidência (`test_graficos.py:155-162`) procura `float(` no código; a evidência de valor está nos testes de `Decimal` e nos textos com duas casas. `savings_rate` e `liquidity_ratio` continuam números (percentual e razão, AD-041).
5. **Ajuste de saldo no patrimônio.** O edge case diz que o ajuste muda o saldo e o patrimônio; o patrimônio usa o saldo da conta (regra da spec `saldo`), sem teste próprio aqui.
6. **Artefatos desatualizados.** O cabeçalho de `tasks.md` está `Status: In Progress`, e a rastreabilidade em `spec.md` está `Implemented`, sem `Verified`.
7. **Gates reduzidos.** Rodaram a suíte inteira do backend, o `makemigrations --check` e o `npm test`. `compileall`, `tsc`, lint e build não foram repetidos.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| REL-01 a REL-25 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (PASS)

**Spec-anchored check**: 25/25 ACs com evidência no valor da spec; nenhuma lacuna de precisão; 7 observações menores
**Sensor**: 8/8 mutações mortas (7 no backend, 1 no frontend)
**Gate**: backend 1025 OK; frontend 313 testes OK

**Próximos passos**: opcionais. Um teste da projeção voltando ao dia 31, e atualizar o cabeçalho de `tasks.md` e os status da rastreabilidade. Nenhum deles bloqueia.
