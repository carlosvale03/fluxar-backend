# Contratos frontend backend Validation

**Date**: 2026-10-07
**Spec**: `.specs/features/contratos-frontend-backend/spec.md`
**Diff range**: backend `fix/contratos-frontend-backend` (`e522712..6739b15`, 23 commits: 8 de código, 1 de design/tasks, 14 de marcação das tasks); frontend `fix/contratos-frontend-backend` (`16611b4..b5ebc5f`, 14 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve, uma rodada
**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T22 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md` (T1 a T8 no backend, T9 a T22 no frontend). O cabeçalho de `tasks.md` ainda diz `Status: In Progress` (observação 5) |

---

## Gate Check

### Backend

- **Comando**: `docker compose exec -T backend python manage.py test --noinput`
- **Resultado**: exit 0. `Ran 701 tests in 197.514s ... OK`
- **Falhas**: nenhuma. **Skips**: nenhum
- **Contagem**: 629 antes da feature (gate da `faturas`), 701 depois: +72, todos em `tests/contratos/` (`tests.contratos` sozinho: 72 testes, também rodado no container isolado sem mutação)
- **Testes antigos ajustados** (21 arquivos em `tests/autenticacao`, `tests/faturas`, `tests/isolamento` e `tests/saldo`): leitura de coleção como array em vez de `results` (AD-021), valores de relatório como texto (`'55.00'` em vez de `55.0`, CONTRATO-16), `code` acrescentado ao `detail` (`tests/autenticacao/test_limites.py`) e os aliases `account` e `category` passando a esperar 400 "Filtro desconhecido" (`tests/isolamento/test_endereco_filtros.py`). Amostra conferida: nenhuma asserção ficou mais fraca; todas ficaram iguais ou mais estritas

### Frontend

| Gate | Resultado |
| ---- | --------- |
| `npm test` | 40 arquivos, 188 testes, todos passando (101 antes da feature, +87; `tests/contratos` tem 15 arquivos, mais ajustes em `tests/saldo` e `tests/faturas`) |

---

## Spec-Anchored Acceptance Criteria

Os caminhos `tests/contratos/*.py` são do `fluxar-backend`; os marcados **FE** estão em `tests/contratos/` do `fluxar-frontend`.

### P1: Listas e paginação

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| CONTRATO-01 coleções completas | contas, cartões, faturas, categorias, tags, orçamentos, metas e monitores como array completo | `tests/contratos/test_paginacao.py:24-25` - `assertIsInstance(resp.data, list)` e o conjunto de ids igual ao criado; usado com 15 tags (`:29`), 12 orçamentos (`:39`), 11 cartões (`:49`), 11 metas (`:56`), 11 monitores (`:66`), contas, faturas e categorias (`:72-94`). FE `colecoes-completas.test.tsx:93-96` - "Mostrando 1 a 12 de 15 tags" e as tags 13 a 15; `:102` seletor com as 15 | ✅ PASS |
| CONTRATO-02 listas paginadas | transações, usuários e logs do admin com `count`, `total_pages`, `current_page`, `next`, `previous`, `results` | `tests/contratos/test_paginacao.py:107` - `set(resp.data) == CHAVES_DA_PAGINA \| {'day_totals'}` (transações); `:177` - `set(resp.data) == CHAVES_DA_PAGINA` para `/admin/users/` (`:190`), `/admin/logs/` (`:198`) e logs de um usuário (`:201`) | ✅ PASS |
| CONTRATO-03 `page_size` | padrão 20, máximo 100 | `tests/contratos/test_paginacao.py:123` - `len(results) == 20`; `:125` - `page_size=150` → `100`; `:128-129` - `page_size=5` → 5 e `total_pages == 22` | ✅ PASS |
| CONTRATO-04 página além da última | HTTP 200, `results` vazio, totais corretos | `tests/contratos/test_paginacao.py:136-141` - `status_code == 200`, `results == []`, `count == 25`, `total_pages == 2`, `current_page == 99`; `:184-187` nas listas do admin | ✅ PASS |
| CONTRATO-05 total e controles | a interface mostra o total e navega entre páginas | FE `colecoes-completas.test.tsx:118-126` - "25 registros", "1 de 2", clique em próxima → "Ação 25" e `get("/admin/logs/", {params: {page: 2}})`; FE `recorrentes-e-listas.test.tsx:74-81` - "25 transações", "1 de 2" → "2 de 2" | ✅ PASS |
| CONTRATO-06 filtro volta à página 1 | uma busca, com `page=1` | FE `busca-de-transacoes.test.tsx:109-111` - na página 3, trocar o mês gera `novas.length == 1` e `page == "1"` | ✅ PASS |
| CONTRATO-07 resposta substituída descartada | sem os dados e sem erro | FE `busca-de-transacoes.test.tsx:159-162` - `signal.aborted == true`, "Antiga" ausente, "Nova" presente, `toast.error` não chamado; FE `tratamento-de-erros.test.ts:93` - `CanceledError` não mostra aviso | ✅ PASS |
| CONTRATO-08 espera de 300 ms | busca só depois de 300 ms sem digitação | FE `busca-de-transacoes.test.tsx:126` - nenhum GET durante a digitação; `:130-133` - um GET só, `search == "mercado"`, `page == "1"`, `horarios[0] - ultimaTecla >= 290` | ✅ PASS |
| CONTRATO-09 total do dia do filtro inteiro | total do dia igual nas duas páginas, sobre o filtro | `tests/contratos/test_total_do_dia.py:23-24` - `{'2026-09-15': '-12.50'}` nas páginas 1 e 2; `:37` sinais (`'68.00'`); `:47` respeita `type=EXPENSE` e o isolamento (`'-40.50'`). FE `categorias-e-total-do-dia.test.tsx:91-92` - "Saldo do Dia: -R$ 250,00" vindo de `day_totals`, não os R$ 10,00 da página | ✅ PASS |

### P1: Filtros

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| CONTRATO-10 várias categorias | transações de qualquer uma | `tests/contratos/test_filtro_de_transacoes.py:64-67` - `categoryId=[alimentação, transporte]` → exatamente as 4 transações, na lista, no PDF e no XLS (`:38-40`) | ✅ PASS |
| CONTRATO-11 pai inclui subcategorias | descendentes incluídas; pai sem filhas só as dele; pai e filha sem repetir | `tests/contratos/test_filtro_de_transacoes.py:64-67`, `:70` (pai sem filhas → só `t_transp`), `:73-76` (pai e filha → 3 ids, uma vez cada, `len(ids) == count` em `:25`), `:83-85` (neta inativa incluída), `:94` (categoria de B → `[]`) | ✅ PASS |
| CONTRATO-12 parâmetro repetido | `categoryId=a&categoryId=b` | FE `categorias-e-total-do-dia.test.tsx:83` - `getAll("categoryId") == ["alim", "transp"]`; FE `datas-enviadas.test.tsx:116-118` - exportação com `categoryId=alim&categoryId=transp&tagIds=t1&tagIds=t2` | ✅ PASS |
| CONTRATO-13 mesmo significado | "despesas" inclui compras no cartão na lista, exportação e relatórios | `tests/contratos/test_filtro_de_transacoes.py:106` - `type=EXPENSE` → `[despesa, compra]` na lista, PDF e XLS; `:139-140` - soma da lista `80.00` igual a `monthly_expense` do dashboard | ✅ PASS |
| CONTRATO-14 filtro desconhecido | HTTP 400 "Filtro desconhecido: <nome>." | `tests/contratos/test_filtros_desconhecidos.py:47-48` - `status_code == 400` e `detail == f'Filtro desconhecido: {nome}.'`, aplicado a `?limit=50` (`:55`), coleção (`:58`), aliases (`:66-68`), rotas sem filtro (`:117`) e admin (`:126`, `:130`); `tests/contratos/test_erros.py:44` - corpo exato `{'detail': 'Filtro desconhecido: limit.', 'code': 'invalid'}` | ✅ PASS |
| CONTRATO-15 Recorrentes | só transações de série | `tests/contratos/test_filtro_de_transacoes.py:153` - `is_recurring=true` → `[da_serie.id]`; FE `recorrentes-e-listas.test.tsx:73` - `get("/transactions/", {params: {is_recurring: "true", page: 1}})` | ✅ PASS |

### P1: Valores em dinheiro

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| CONTRATO-16 texto com duas casas | "1234.56" em todas as rotas, inclusive relatórios; zero "0.00" | `tests/contratos/test_dinheiro.py:41-42` - `isinstance(valor, str)` e `^-?\d+\.\d{2}$`, aplicado a dashboard (`:78-87`), calendário e gráficos (`:96-111`), avançados (`:114-135`), comparação mensal (`:141-142`), tags (`:146-156`), admin (`:166-171`) e serializers (`:186-213`); `:92-93` zero → `'0.00'`; `:27` `dinheiro(Decimal('1234.565')) == '1234.57'`; percentuais continuam números (`:82-83`) | ✅ PASS |
| CONTRATO-17 conta sem ponto flutuante | duas casas exatas no envio | FE `dinheiro.test.ts:45` - `deCentavos(paraCentavos("0.10") + paraCentavos("0.20")) == "0.30"`; FE `dinheiro-nos-formularios.test.tsx:174` - cofrinho envia `amount: "0.30"`; `:93` aporte `"1500.00"` | ✅ PASS |
| CONTRATO-18 formatador único | "R$ 1.234,56", inclusive eixos | FE `dinheiro.test.ts:64` - `formatarMoeda("1234.56") == "R$ 1.234,56"`; `:70` - `formatCurrency === formatarMoeda`; FE `formatador-unico.test.tsx:135` - eixo `["R$ 0,00", …, "R$ 800,00"]`; `:123` - nenhuma cópia de formatação de moeda fora de `src/lib/dinheiro.ts` | ✅ PASS |
| CONTRATO-19 leitura AD-009 | "1.500" → R$ 1.500,00; "12,5" → R$ 12,50 | FE `dinheiro.test.ts:11-17` - `lerValorDigitado("1.500") == "1500.00"`, `"12,5" == "12.50"`; FE `campo-de-dinheiro.test.tsx:36-37` - entrega `"1500.00"` e mostra "R$ 1.500,00" | ✅ PASS |
| CONTRATO-20 sinal de menos | "-50,00" aceito onde o campo permite | FE `campo-de-dinheiro.test.tsx:69-70` - `"-50.00"` e "-R$ 50,00"; `:80-82` sem `permitirNegativo` o sinal é recusado; FE `dinheiro-nos-formularios.test.tsx:118` - ajuste envia `{ new_balance: "-50.00" }` | ✅ PASS |
| CONTRATO-21 colagem | "100" colado → R$ 100,00 | FE `campo-de-dinheiro.test.tsx:58-59` - `ultimo(aoMudar) == "100.00"` e valor "R$ 100,00" | ✅ PASS |

### P1: Datas

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| CONTRATO-22 data sem hora | `AAAA-MM-DD`, sem fuso | `tests/contratos/test_datas.py:44` - aporte grava `date(2026, 12, 31)`; `:53-54` - data com hora ou inválida → 400 com `['Data inválida. Use o formato AAAA-MM-DD.']`; `tests/contratos/test_filtro_de_transacoes.py:117` mesma mensagem nos filtros; `:127` fim `2026-09-30` não inclui 1º/10; `tests/contratos/test_datas.py:95` - `date == '2026-09-15'` | ✅ PASS |
| CONTRATO-23 data com hora | ISO 8601 com fuso | `tests/contratos/test_datas.py:94` - `created_at` casa `…T…(Z\|[+-]HH:MM)$` | ✅ PASS |
| CONTRATO-24 mesmo dia em qualquer fuso | "2026-12-31" → 31/12/2026, salvo como "2026-12-31" | FE `datas-sem-hora.test.tsx:75-76` - "31 de dez, 2026" e "29 de fev, 2028" em Brasília e Lisboa; FE `datas-enviadas.test.tsx:92` - editar só o nome envia `target_date: "2026-12-31"` nos dois fusos | ✅ PASS |
| CONTRATO-25 envio sem hora | período e aporte/resgate como `AAAA-MM-DD` | FE `datas-enviadas.test.tsx:116-118` - exportação de setembro com `endDate=2026-09-30`; `:157-158` - aporte e resgate com `date` do dia local e sem `datetime`; FE `datas-sem-hora.test.tsx:59` - `paraApi(new Date(2026, 11, 31, 23, 30)) == "2026-12-31"` | ✅ PASS |

### P1: Preferências

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| CONTRATO-26 objeto `preferences` | aceita e devolve o mesmo formato | `tests/contratos/test_preferencias.py:29-31` - `preferences.theme == 'dark'`, `notifications.email is False`, gravado no banco; `:41` demais notificações mantidas. FE `preferencias.test.tsx:84-91` - `PATCH /users/me/` só com `{ preferences: {…, theme: "dark", notifications: {email: false, …}} }` | ✅ PASS |
| CONTRATO-27 recarregar mostra o salvo | tema aplicado ao carregar | `tests/contratos/test_preferencias.py:33` - GET devolve `theme == 'dark'`; FE `preferencias.test.tsx:105-106` - `/auth/me/` com `theme: "dark"` → `<html class="dark">`, sem `light` | ✅ PASS |
| CONTRATO-28 preferência inválida | HTTP 400 com o erro no campo | `tests/contratos/test_preferencias.py:47-49` - tema "roxo" → `400`, `'theme' in resp.data['preferences']`, tema não muda; `:52-58` moeda e notificação inválidas. FE `preferencias.test.tsx:118-120` - mensagem no campo, sem aviso | ✅ PASS |

### P1: Erros e avisos

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| CONTRATO-29 português | mensagens em português, inclusive as padrão do Django/DRF | `tests/contratos/test_erros.py:40` - `{'detail': 'Não encontrado.', 'code': 'not_found'}`; `:49` - `{'name': ['Este campo é obrigatório.']}`; `:31-32` nenhuma view com `'error':` nem `str(e)`; `:73-74` 500 sem o texto da exceção | ✅ PASS |
| CONTRATO-30 erros por campo | por campo na API e no campo do formulário | `tests/contratos/test_erros.py:59-60` - orçamento duplicado `{'category': ['Já existe um orçamento para esta categoria neste mês.']}`; FE `erros-nos-formularios.test.tsx:111-114` - mensagem no item da categoria, sem aviso; FE `tratamento-de-erros.test.ts:39-44` - `setError` por campo e as sobras no Sonner | ✅ PASS |
| CONTRATO-31 `detail` no Sonner | `toast.error(detail)` | FE `tratamento-de-erros.test.ts:69` - `[["Não encontrado."], ["Recurso disponível no plano Premium."]]`; FE `erros-nos-formularios.test.tsx:150` - `toast.error("Sem permissão.")` | ✅ PASS |
| CONTRATO-32 só o Sonner | nenhum `useToast`/Toaster do Radix | FE `so-o-sonner.test.tsx:49` - nenhum arquivo de `src` importa `useToast` nem `ui/toaster`, `ui/use-toast`, `ui/toast`; `:59` erro da tag chega por `toast.error` | ✅ PASS |
| CONTRATO-33 rede/5xx/tempo com "Tentar de novo" | mensagem com opção de repetir, sem falha silenciosa | FE `tratamento-de-erros.test.ts:83-87` - rede, 503 e timeout → "Não foi possível falar com o servidor." com ação "Tentar de novo" que chama `tentarDeNovo`; FE `colecoes-completas.test.tsx:138-143` - tela de tags com backend parado, o clique busca de novo; FE `erros-nos-formularios.test.tsx:194` - nenhum `catch` em `src` só com `console` | ✅ PASS |
| CONTRATO-34 tempo máximo | 30 s; 120 s para importação e exportação; tratado como CONTRATO-33 | FE `tratamento-de-erros.test.ts:105` - `api.defaults.timeout == 30_000`; `:122` - `[120_000 ×5]` em importação OFX, preflight, planilha, PDF e XLS; `:75` timeout (`ECONNABORTED`) tratado como CONTRATO-33 | ✅ PASS |
| CONTRATO-35 fechar o aviso | o usuário fecha o "servidor acordando" | FE `aviso-de-servidor-acordando.test.tsx:45-46` - botão "Fechar" tira o aviso; `:51` não volta no mesmo episódio; `:60` volta no episódio seguinte | ✅ PASS |

**Status**: ✅ 35/35 ACs com evidência `file:line` e asserção no valor definido pela spec.

---

## Edge Cases

- [x] Mais de 100 tags vêm inteiras: coleção sem paginação (`DEFAULT_PAGINATION_CLASS = None`); testado com 15 tags em `tests/contratos/test_paginacao.py:29` e `page` recusado em coleção em `tests/contratos/test_filtros_desconhecidos.py:60`. Sem teste com mais de 100 (observação 2)
- [x] Subcategoria e pai juntos, cada transação uma vez: `tests/contratos/test_filtro_de_transacoes.py:73-76`
- [x] Pai sem subcategorias traz só as dele: `tests/contratos/test_filtro_de_transacoes.py:70`
- [x] Relatório com zero vem "0.00": `tests/contratos/test_dinheiro.py:92-93`
- [x] 29/02 em ano bissexto: FE `datas-sem-hora.test.tsx:76`
- [x] Exportação de 90 s termina: tempo de 120 s em FE `tratamento-de-erros.test.ts:122`
- [ ] 403 de trava de plano segue PERM-19: fora do alcance desta feature; o design registra que o 403 de plano ainda não existe e fica com `permissoes-e-planos`. Hoje o `detail` do 403 vai ao Sonner (FE `tratamento-de-erros.test.ts:69`) (observação 3)

---

## Discrimination Sensor

Isolamento no backend: o serviço `backend` monta `.:/app`, então os mutantes rodaram num worktree descartável `../fluxar-backend-mut` (detached em `6739b15`) com um container avulso `docker run --rm --network fluxar-backend_default --env-file <env do serviço> -v <worktree>:/app fluxar-backend-backend:latest python manage.py test tests.contratos --noinput`, depois que o gate inteiro terminou (para não disputar o banco de teste). Sem mutação, `tests.contratos` passou no worktree (72 OK). Cada mutação foi revertida com `git checkout -- .` no worktree antes da seguinte. O arquivo de ambiente ficou no scratchpad e foi apagado no fim.

Isolamento no frontend: sem worktree e sem junction de `node_modules`. A mutação foi aplicada no arquivo real, os testes do arquivo rodaram com `npx vitest run`, e o arquivo foi restaurado com `git checkout -- <arquivo>` logo depois, com `git diff --quiet` e `git status --porcelain` vazios antes da mutação seguinte. `src/lib/erros.ts` voltou do checkout com CRLF (o original no disco era LF, `core.autocrlf=true`); as quebras foram convertidas de volta para LF e o índice atualizado com o mesmo blob do `HEAD`, então o arquivo voltou byte a byte ao estado inicial.

| # | File:line | Descrição | Killed? |
| - | --------- | --------- | ------- |
| 1 | `core/pagination.py:43` | Página além da última volta 404 (`raise NotFound` no lugar da página vazia) | ✅ Killed (5 falhas e 1 erro: `test_pagina_alem_da_ultima`, `test_pagina_que_nao_e_numero`, as três listas do admin, `test_pagina_vazia_nao_tem_totais`) |
| 2 | `transactions/filtros.py:33` | Categoria sem descendentes (`fronteira = set()`) | ✅ Killed (3 falhas: pai com subcategorias, pai e filha juntos, neta inativa). Variante só sem netas (`fronteira = filhas` → `set()` em `:39`): morta por `test_descendentes_em_qualquer_nivel_inclusive_inativas` |
| 3 | `core/valores.py:29` | `dinheiro()` devolve `float` em vez de texto | ✅ Killed (13 falhas: `FuncaoDinheiroTests` ×2, `RelatoriosTests` ×7, `SerializersTests` ×4) |
| 4 | `api/serializers.py:178` | `preferences` ignorado no `update` (`preferencias = {}`) | ✅ Killed (2 falhas: `test_salva_e_devolve_o_objeto_preferences`, `test_demais_preferencias_continuam_como_estavam`) |
| 5 | `src/lib/dinheiro.ts:66` (FE) | Ponto de milhar lido como decimal: `lerValorDigitado("1.500")` vira `"1.50"` | ✅ Killed (6 falhas em `dinheiro.test.ts`, `campo-de-dinheiro.test.tsx` e `dinheiro-nos-formularios.test.tsx`) |
| 6 | `src/app/(app)/transacoes/page.tsx:350` (FE) | Busca sem espera (`setTimeout` de 300 → 0 ms) | ✅ Killed (`busca-de-transacoes.test.tsx`, "digitar "mercado" faz um GET só, 300 ms depois da última tecla") |
| 7 | `src/app/(app)/transacoes/page.tsx:315` (FE) | Resposta de busca abortada não é descartada (`if (controlador.signal.aborted) return` removido) | ✅ Killed (`busca-de-transacoes.test.tsx`, "uma resposta lenta que chega depois da mais nova não aparece") |
| 8 | `src/lib/erros.ts:80` (FE) | `tratarErro` sem `setError`: o erro de campo vai para o Sonner | ✅ Killed (5 falhas: `tratamento-de-erros.test.ts` ×2, `erros-nos-formularios.test.tsx` ×2, `preferencias.test.tsx`) |

**Verificação do isolamento**: `git status --porcelain` vazio antes e depois nos dois repositórios; `git worktree list` só com a árvore principal nos dois; nenhuma pasta `.mut-tmp` nem `fluxar-*-mut` sobrou; `node_modules` do frontend não foi tocado.

**Sensor depth**: leve (8 mutações de comportamento, 4 em cada lado, decisão do usuário)
**Result**: 8/8 killed, 0 survived - PASS

---

## Code Quality (nível leve, amostragem)

| Princípio | Status |
| --------- | ------ |
| Um ponto único por assunto | ✅ `core/pagination.py`, `core/filtros.py`, `transactions/filtros.py` (lista e as duas exportações chamam `filtrar_transacoes`), `core/valores.py:dinheiro`; no frontend `src/lib/dinheiro.ts`, `src/lib/datas.ts` e `src/lib/erros.ts` |
| Sem cópias locais | ✅ varreduras estáticas nos testes: formatação de moeda (`formatador-unico.test.tsx:123`), `results \|\|` (`colecoes-completas.test.tsx:150`), `limit` (`recorrentes-e-listas.test.tsx:104`), `useToast` (`so-o-sonner.test.tsx:49`), `catch` silencioso (`erros-nos-formularios.test.tsx:194`) |
| Testes mapeados aos ACs | ✅ cada arquivo de `tests/contratos/` nos dois repositórios cita os IDs que cobre |
| Asserções no valor da spec | ✅ mensagens exatas ("Filtro desconhecido: limit.", "Não encontrado.", "Este campo é obrigatório.", "Data inválida. Use o formato AAAA-MM-DD."), formatos e valores do Independent Test conferidos literalmente |
| Testes antigos | ✅ ajustes seguem AD-021 e CONTRATO-14/16; nenhuma asserção enfraquecida na amostra |
| Guidelines | AD-033 e AD-034 (local e ferramentas de teste) seguidos |

---

## Observações (não bloqueiam)

1. **CONTRATO-34 sem um timeout real.** Os testes conferem a configuração (`timeout` de 30 s e de 120 s) e o tratamento de um `ECONNABORTED` (`tratamento-de-erros.test.ts:75`, `:105`, `:122`). O cancelamento em si é do axios. Basta para a spec, mas nenhum teste deixa uma requisição passar do tempo.
2. **Coleção com mais de 100 itens.** O edge case "mais de 100 tags" não tem teste com mais de 100 itens. Os testes usam 11 a 15 itens. Como a paginação é desligada por padrão, o comportamento está certo; falta só a evidência no limite.
3. **403 de trava de plano (PERM-19).** O edge case depende da feature `permissoes-e-planos`. Hoje o `detail` do 403 vai ao aviso genérico do Sonner.
4. **CONTRATO-28 confere o campo, não a mensagem.** `tests/contratos/test_preferencias.py:48` verifica que o erro está em `preferences.theme`. A spec pede só "o erro no campo", então está coberto.
5. **Artefatos desatualizados.** O cabeçalho de `tasks.md` está como `Status: In Progress`, e a linha "Coverage" da rastreabilidade em `spec.md` ainda diz "35 unmapped ⚠️ (design e tasks ainda não iniciados)", embora a tabela esteja preenchida.
6. **Gate do frontend reduzido.** Por instrução desta rodada, só `npm test` rodou no frontend; `tsc`, lint e build não foram repetidos pelo Verifier. No backend rodou a suíte inteira; `compileall` e `makemigrations --check` não foram repetidos.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| CONTRATO-01 a CONTRATO-35 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (PASS)

**Spec-anchored check**: 35/35 ACs com evidência; nenhuma lacuna de precisão da spec; 6 observações menores
**Sensor**: 8/8 mutações mortas (4 no backend, 4 no frontend)
**Gate**: backend 701 OK; frontend 188 testes OK

**Próximos passos**: opcionais, um teste de coleção com mais de 100 itens e a atualização do cabeçalho de `tasks.md` e da linha de cobertura de `spec.md`. Não bloqueiam.
