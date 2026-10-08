# Importacao Validation

**Date**: 2026-10-07
**Spec**: `.specs/features/importacao/spec.md`
**Diff range**: backend `fix/importacao` (`bfa92c3..b2c6dcd`, 14 commits: 11 de código e testes, 1 de design/tasks, 2 de marcação das tasks); frontend `fix/importacao` (`6e1d226..8b8e33d`, 2 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve, uma rodada
**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T13 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md` (T1 a T11 no backend, T12 e T13 no frontend). O cabeçalho de `tasks.md` ainda diz `Status: In Progress` (observação 5) |

---

## Gate Check

### Backend

- **Comando**: `docker compose exec -T backend python manage.py test --noinput`
- **Resultado**: exit 0. `Ran 782 tests in 177.046s ... OK`
- **Falhas**: nenhuma. **Skips**: nenhum
- **Contagem**: 701 antes da feature (gate da `contratos-frontend-backend`), 782 depois: +81, todos em `tests/importacao/` (80 sem o teste de 10.000 linhas, mais ele)
- **IMPORT-40 medido no gate**: `[IMPORT-40] 10.000 linhas em 15.2 s`
- **Teste antigo ajustado**: `tests/contratos/test_erros.py:137`, a mensagem do preflight ilegível passou de "Não foi possível ler o arquivo. Confira o formato e as colunas escolhidas." para "Não foi possível ler o arquivo.", que é a mensagem do design para IMPORT-06. A asserção continua no corpo exato, sem perder força

### Frontend

| Gate | Resultado |
| ---- | --------- |
| `npm test` | 42 arquivos, 198 testes, todos passando (188 antes da feature, +10 em `tests/importacao/`) |

---

## Spec-Anchored Acceptance Criteria

Os caminhos `tests/importacao/*.py` são do `fluxar-backend`. Os marcados **FE** estão em `tests/importacao/` do `fluxar-frontend`.

### P1: Arquivos aceitos e limites

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| IMPORT-01 `.ofx`, `.csv`, `.xlsx` processados | processados pelas regras da spec | `tests/importacao/test_leitura.py:50` - CSV e `EXTRATO.XLSX` → `(200, {'accounts': []})`; `tests/importacao/test_gravacao.py:232` - OFX → resumo `3, 2, 0, [(2, 'Valor inválido')]` | ✅ PASS |
| IMPORT-02 outra extensão | 400, "Formato não suportado. Envie um arquivo OFX, CSV ou XLSX." | `tests/importacao/test_leitura.py:38` - `.xls`, `.txt` e sem extensão → `assert_recusado` (400 e `{'file': [mensagem]}`, `base.py:129-130`); `:42` mesma mensagem no OFX | ✅ PASS |
| IMPORT-03 interface só oferece os três | `accept` sem `.xls` | FE `dialogo-de-importacao.test.tsx:98` - `accept == ".csv,.xlsx"`; `:100` `.xls` → `toast.error(FORMATO_NAO_SUPORTADO)`; `:102-103` botão desabilitado e nenhum POST | ✅ PASS (observação 1) |
| IMPORT-04 mais de 5 MB | 400, "O arquivo passa do limite de 5 MB.", antes de ler | `tests/importacao/test_leitura.py:58` - `assert_recusado(resp, 'O arquivo passa do limite de 5 MB.')`; `:64` - `read_csv.assert_not_called()` | ✅ PASS |
| IMPORT-05 mais de 10.000 linhas | 400, "O arquivo passa do limite de 10.000 linhas.", nada gravado | `tests/importacao/test_leitura.py:70` - 10.001 linhas → `assert_recusado(resp, LINHAS_DEMAIS)`; `:73` 10.000 mais 5 vazias → 200 | ✅ PASS (observação 2) |
| IMPORT-06 ilegível ou sem colunas | 400 dizendo se é ilegível ou quais colunas faltam | `tests/importacao/test_leitura.py:79` - "Colunas não encontradas no arquivo: Categoria, Conta."; `:88` - "Não foi possível ler o arquivo." (XLSX lixo e CSV vazio); `tests/importacao/test_gravacao.py:247` - OFX ilegível pela rota | ✅ PASS |
| IMPORT-07 OFX com mais de uma conta | 400, "O arquivo tem mais de uma conta. Exporte um arquivo por conta." | `tests/importacao/test_leitura.py:170` - `recusa.exception.detail == {'file': [MAIS_DE_UMA_CONTA]}` (`ValidationError` do DRF → 400) | ✅ PASS |
| IMPORT-08 `;`/`,`, UTF-8/Windows-1252 | lido sem pedir ao usuário | `tests/importacao/test_leitura.py:105` - `;` e `cp1252` com "Salário" e "Crédito" → `LinhaBruta(2, {...})` exata; `:114` - `,` e UTF-8 com BOM | ✅ PASS |

### P1: Valores e datas no formato brasileiro

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| IMPORT-09 com vírgula | "1.234,56" → 1234.56; "R$ -45,00" → −45.00 | `tests/importacao/test_texto.py:26-27` - `assert_valor('1.234,56', '1234.56')`, `('R$ -45,00', '-45.00')` | ✅ PASS |
| IMPORT-10 sem vírgula (AD-009) | "1.500" → 1500.00; "1.500.000" → 1500000.00; "12.5" → 12.50; "0.50" → 0.50 | `tests/importacao/test_texto.py:33-34` e `:39-40` - os quatro exemplos da spec | ✅ PASS |
| IMPORT-11 célula numérica do XLSX | número da célula | `tests/importacao/test_leitura.py:156-157` - `'Valor': 1500` como `int`; `tests/importacao/test_interpretacao.py:89` - `1500` → `Decimal('1500.00')`, igual a "1.500" em `:90` | ✅ PASS |
| IMPORT-12 ilegível, zero, mais de duas casas | rejeita com "Valor inválido" | `tests/importacao/test_texto.py:46-50` - "abc", "0,00", "1,234" levantam `VALOR_INVALIDO == 'Valor inválido'`; `tests/importacao/test_interpretacao.py:103-107` - `Rejeicao(n, 'Valor inválido')` para "abc", "0,00", `0`, `45.555` e vazio | ✅ PASS |
| IMPORT-13 três formatos | "04/03/2026", "04/03/26", "2026-03-04" → 4/3/2026 | `tests/importacao/test_texto.py:59` - `ler_data_em_texto(texto) == date(2026, 3, 4)` para os três | ✅ PASS |
| IMPORT-14 célula de data do XLSX | data da célula | `tests/importacao/test_leitura.py:156`, `:160` - `datetime(2026, 3, 4)` e `datetime(2026, 3, 5)`; `tests/importacao/test_interpretacao.py:89`, `:91` → `date(2026, 3, 4)` | ✅ PASS |
| IMPORT-15 data ilegível ou inexistente | rejeita com "Data inválida" | `tests/importacao/test_texto.py:63-67` - "29/02/2025" e "2026/03/04" levantam `DATA_INVALIDA == 'Data inválida'`; `tests/importacao/test_interpretacao.py:108` - `Rejeicao(8, 'Data inválida')` | ✅ PASS |

### P1: Tipo, status e conta de cada linha

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| IMPORT-16 palavras de tipo | receita/entrada/crédito/C e despesa/saída/débito/D, sem maiúsculas nem acentos, valor sem sinal | `tests/importacao/test_interpretacao.py:51-55` - "Crédito", "CREDITO", "Entrada", "C", "receita" com `-100,00` → `('INCOME', Decimal('100.00'))`; `:60-63` - "Débito", "saída", "D", "DESPESA" → `('EXPENSE', Decimal('45.00'))` | ✅ PASS |
| IMPORT-17 outro tipo | "Tipo desconhecido: <valor>" | `tests/importacao/test_interpretacao.py:68` - `Rejeicao(7, 'Tipo desconhecido: Transferido')` | ✅ PASS |
| IMPORT-18 sem coluna de tipo ou OFX | sinal decide, valor sem sinal | `tests/importacao/test_interpretacao.py:75-76` - `-45,00` → `('EXPENSE', 45.00)`, `100` → `('INCOME', 100.00)`; `:131-135` - OFX `-45.00` → `EXPENSE 45.00`, `100.50` → `INCOME` | ✅ PASS |
| IMPORT-19 descrição do OFX | memo, senão favorecido, senão "Sem descrição" | `tests/importacao/test_interpretacao.py:122-124` - 'Padaria', 'Loja', 'Sem descrição' | ✅ PASS |
| IMPORT-20 status | "pendente"/"pending" → pendente; resto → efetivada | `tests/importacao/test_interpretacao.py:148-152` - Pendente, pending, PENDENTE → `PENDING`; Pago, vazio e sem coluna → `COMPLETED`; `tests/importacao/test_gravacao.py:152-154` - gravada `('Aluguel', 'EXPENSE', 'PENDING', 1500.00)` | ✅ PASS |
| IMPORT-21 conta não mapeada ou excluída | "Conta não mapeada: <nome>" / "Conta excluída: <nome>" | `tests/importacao/test_interpretacao.py:167-168` - "Conta não mapeada: Banco X" e conta de B → "Conta não mapeada: Banco B"; `:174-175` - "Conta excluída: Velha" e "Conta excluída: antiga"; `:140` - OFX em conta excluída | ✅ PASS |
| IMPORT-22 sem conta | "Conta não informada" | `tests/importacao/test_interpretacao.py:187-189` - `Rejeicao(2, 'Conta não informada')` com coluna vazia e sem coluna | ✅ PASS |
| IMPORT-23 categoria, subcategoria, tag nova | cria, reaproveitando sem maiúsculas nem acentos | `tests/importacao/test_gravacao.py:179-180` - "alimentação"/"ALIMENTACAO" → `{alimentacao.pk}`; `:183-184` - "Lazer novo" criada uma vez, "Filmes" com `parent == lazer`; `:188-189` - tag "trabalho" uma vez, "VIAGEM" → `viagem` | ✅ PASS |
| IMPORT-24 texto longo | "Texto longo demais: <coluna>" | `tests/importacao/test_interpretacao.py:229-236` - descrição 300 → "Texto longo demais: descrição", categoria/subcategoria 51 e tag 60 → "categoria", "subcategoria", "tag"; `:243-245` 255 e 50 passam | ✅ PASS |
| IMPORT-25 transferência | duas pernas pelas regras do saldo | `tests/importacao/test_gravacao.py:208-216` - `TRANSFER_OUT` na poupança e `TRANSFER_IN` na corrente, mesmo `transfer_id`, 200.00, saldos `-200.00` e `1200.00` iguais a `calcular()` | ✅ PASS |
| IMPORT-26 origem = destino, não mapeada, excluída | "Origem e destino iguais", "Conta não mapeada: <nome>", "Conta excluída: <nome>" | `tests/importacao/test_interpretacao.py:213-221` - os três motivos; `tests/importacao/test_gravacao.py:205` - `[(3, 'Origem e destino iguais')]` pela rota | ✅ PASS |

### P1: Resultado da importação

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| IMPORT-27 grava as válidas | só as inválidas rejeitadas | `tests/importacao/test_gravacao.py:81-84` - as 7 descrições gravadas (linhas 2, 4, 5, 7, 8, 10, 11) | ✅ PASS |
| IMPORT-28 falha de gravação de uma linha | só ela rejeitada, com motivo; as outras ficam | `tests/importacao/test_gravacao.py:110` - `[(5, 'Erro ao gravar a linha')]` com erro real do Postgres; `:111` sem o texto da exceção; `:114-117` linhas 2, 3, 4, 6, 7 gravadas; `:123` saldo `995.00` | ✅ PASS |
| IMPORT-29 resposta 200 com os totais | lidas, gravadas, ignoradas, rejeitadas | `tests/importacao/test_gravacao.py:45-52` (`assert_resumo`) - `status_code == 200`, chaves exatas e `(total, imported, ignored, rejected)`; `:77` - Independent Test `10, 7, 0, 3` | ✅ PASS |
| IMPORT-30 rejeitadas com número e motivo | planilha com cabeçalho = 1; OFX pela posição | `tests/importacao/test_gravacao.py:77-79` - `(3, 'Data inválida'), (6, 'Data inválida'), (9, 'Texto longo demais: descrição')`; `:232` - OFX `(2, 'Valor inválido')`; `tests/importacao/test_leitura.py:179` - posição 1 e 2 | ✅ PASS |
| IMPORT-31 tudo já existia | 200 com zero gravadas | `tests/importacao/test_gravacao.py:133` - `assert_resumo(segunda, 2, 0, 2)` (200) | ✅ PASS |
| IMPORT-32 linhas vazias | puladas, sem contar | `tests/importacao/test_leitura.py:132-134` - `[(2, 'Linha 2'), (4, 'Linha 4'), (7, 'Linha 7')]` com quatro linhas vazias; XLSX em `:155` (`[2, 4, 5]`) | ✅ PASS |
| IMPORT-33 interface mostra os totais e as rejeitadas | quatro totais e cada rejeitada com motivo | FE `dialogo-de-importacao.test.tsx:143-146` - Lidas 12, Gravadas 7, Ignoradas 2, Rejeitadas 3; `:148-152` - "Linha 3: Data inválida", "Linha 6: Data inválida", "Linha 9: Texto longo demais: descrição" | ✅ PASS |

### P1: Linhas já importadas

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| IMPORT-34 FITID | ignorada se a conta já tem o FITID | `tests/importacao/test_repetidos.py:45` - só a linha 1 ignorada (mesmo FITID, descrição editada); F1 em outra conta é gravada; `tests/importacao/test_gravacao.py:240` - reimportar o OFX → `3, 0, 2`; `tests/importacao/test_modelos.py:31` - `IntegrityError` no mesmo FITID por conta | ✅ PASS |
| IMPORT-35 OFX sem FITID ou antigo | data, valor, tipo e descrição | `tests/importacao/test_repetidos.py:56` - só a linha 1 (contra a gravada sem FITID) é ignorada; a gravada com outro FITID não conta | ✅ PASS |
| IMPORT-36 planilha | data, valor, tipo e descrição na conta | `tests/importacao/test_repetidos.py:69` - `[2]`: outra conta, tipo, valor, dia e descrição não são repetidas | ✅ PASS |
| IMPORT-37 transferência de planilha | origem, destino, data e valor | `tests/importacao/test_repetidos.py:98` - `[2]`: a segunda igual, a invertida e a de outro dia são gravadas | ✅ PASS |
| IMPORT-38 N − M | grava N − M, nenhuma se M ≥ N | `tests/importacao/test_repetidos.py:74-84` - `[]` com M=0, `[2]` com M=1, `[2, 3]` com M=2, `[2, 3, 4]` com M=4 | ✅ PASS |
| IMPORT-39 duas importações ao mesmo tempo | cada linha uma vez | `tests/importacao/test_concorrencia.py:66-67` - `imported` e `ignored` `[0, n]`; `:83-85` - 4 transações, 2 "Café", saldo `3890.00`; `:102` - FITIDs `['F1', 'F2', 'F3']` | ✅ PASS |

### P2: Tempo de processamento

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| IMPORT-40 até 30 s | 10.000 linhas em até 30 s | `tests/importacao/test_desempenho.py:50-51` - `(10_000, 10_000, 0)` e `duracao <= 30`; medido 15.2 s no gate | ✅ PASS |
| IMPORT-41 outras requisições atendidas | servidor segue atendendo durante a importação | `tests/importacao/test_desempenho.py:78` - `gunicorn.conf.py` com `('gthread', 2, 4, 120)`; `:85` variáveis de ambiente ajustam | ✅ PASS (observação 3) |

### P2: Correções de categoria

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| IMPORT-42 registro da correção | descrição, conta, categoria de antes, de depois e data | `tests/importacao/test_correcoes.py:65-71` - `(user, transacao, 'UBER *TRIP 1234', 'uber *trip', conta, despesa, transporte)` e `criada_em` preenchida; `:79-83` definir sem categoria → `categoria_antes None`; `:100` não importada não grava | ✅ PASS |
| IMPORT-43 sugestão pela correção mais recente | sem maiúsculas, acentos, espaços extras e dígitos | `tests/importacao/test_correcoes.py:28-30` - "UBER *TRIP 1234"/"5678" → `'uber *trip'`; `tests/importacao/test_sugestao.py:61-63` - "UBER *TRIP 5678" em Transporte; `:75` - vale a mais recente (Lazer) | ✅ PASS |
| IMPORT-44 grava com a sugerida e marca | categoria e marca de sugerida | `tests/importacao/test_sugestao.py:63` - `(self.transporte, True)`; `:90` linha com categoria no arquivo mantém `(Lazer, False)` | ✅ PASS |
| IMPORT-45 quantas sugeridas e atalho | contagem e link para a lista filtrada | FE `dialogo-de-importacao.test.tsx:165-167` - "3 linhas com categoria sugerida" e `href == /transacoes?import_batch=<lote>&suggested_category=true`; FE `lista-filtrada-e-selo.test.tsx:97-98` - a lista envia os dois parâmetros; `tests/importacao/test_correcoes.py:151` - API devolve só a sugerida do lote | ✅ PASS |
| IMPORT-46 indicação de sugerida | "veio do histórico do usuário" | FE `lista-filtrada-e-selo.test.tsx:136-138` - "Sugerida pelo seu histórico" na linha e no cartão, 2 ocorrências; `:152` no formulário; `tests/importacao/test_correcoes.py:111` - `category_suggested == True` na API | ✅ PASS |
| IMPORT-47 categoria da correção excluída | sem sugestão | `tests/importacao/test_sugestao.py:110-113` - categoria excluída pela API, apagada do banco e de outro tipo → `suggested == 0` e `[(None, False)] * 3` | ✅ PASS |
| IMPORT-48 exclusão definitiva apaga correções | correções somem com o usuário | `tests/importacao/test_correcoes.py:199-201` - as duas rotas de exclusão definitiva do painel apagam a correção do excluído e mantêm a de A; `tests/importacao/test_modelos.py:59` | ✅ PASS |
| IMPORT-49 só nas sugestões do próprio usuário | correção de B nunca sugere para A | `tests/importacao/test_sugestao.py:123-126` - `suggested == 0`, linha sem categoria, nenhuma transação com a categoria de B; `tests/importacao/test_correcoes.py:172-173` - correção fica com o dono | ✅ PASS |

**Status**: ✅ 49/49 ACs com evidência `file:line` e asserção no valor definido pela spec. Nenhuma lacuna de precisão da spec.

---

## Edge Cases

- [x] Extrato que cresceu: só as novas entram (`tests/importacao/test_repetidos.py:56`, `:69`, `:84`)
- [x] Duas compras iguais no mesmo arquivo: as duas entram (`tests/importacao/test_repetidos.py:74`; pela rota em `tests/importacao/test_gravacao.py:129`)
- [x] "Crédito" e "CREDITO": receita (`tests/importacao/test_interpretacao.py:51`)
- [x] "1.500" em texto e 1500 numérico: R$ 1.500,00 (`tests/importacao/test_interpretacao.py:89-90`)
- [x] "29/02/2025": rejeitada (`tests/importacao/test_texto.py:63`)
- [x] "0,00": rejeitada (`tests/importacao/test_interpretacao.py:104`)
- [x] Arquivo só com o cabeçalho: 200 com zeros (`tests/importacao/test_gravacao.py:139`)
- [x] Preflight com os mesmos formatos e limites: os testes de recusa passam pela rota do preflight (`tests/importacao/test_leitura.py:38`, `:58`, `:70`)
- [x] OFX antigo reimportado: reconhecido pela chave (`tests/importacao/test_repetidos.py:56`)
- [x] Conta excluída depois do mapeamento: rejeitada (`tests/importacao/test_interpretacao.py:174`)
- [x] Duas correções para a mesma descrição: vale a mais recente (`tests/importacao/test_sugestao.py:75`)
- [x] Sugerida trocada vira correção nova e desliga a marca (`tests/importacao/test_correcoes.py:115-118`)

---

## Discrimination Sensor

**Isolamento no backend**: o serviço `backend` monta `.:/app`, então os mutantes rodaram num worktree descartável `../fluxar-backend-mut` (detached em `b2c6dcd`), com um container avulso: `docker run --rm --network fluxar-backend_default --env-file <ambiente do serviço> -v <worktree>:/app -w /app fluxar-backend-backend python manage.py test <rótulos> --noinput`. Os rótulos foram os 10 módulos de `tests.importacao` mais `test_desempenho.ConfiguracaoDoGunicornTests`, sem o teste de 10.000 linhas: 80 testes. Os mutantes rodaram depois do gate inteiro, para não disputar o banco de teste. Sem mutação, os 80 passaram no worktree (M0). Cada mutação foi aplicada por um script que exige uma ocorrência única do trecho original e foi revertida com `git checkout -- .` no worktree antes da seguinte. O arquivo de ambiente ficou no scratchpad e foi apagado no fim.

**Isolamento no frontend**: sem worktree e sem junction de `node_modules`. A mutação foi aplicada no arquivo real, `npx vitest run tests/importacao` rodou, e o arquivo foi restaurado com `git checkout -- <arquivo>`. Depois disso, `git diff --quiet` e `git status --porcelain` estavam vazios. O arquivo voltou com CRLF, como estava antes: o SHA-1 do arquivo no disco é igual ao de antes da mutação (`c46bdb75…`), e `git hash-object` é igual ao blob do `HEAD` (`712759ee…`).

| # | File:line | Descrição | Killed? |
| - | --------- | --------- | ------- |
| 1 | `core/valores.py:51` | AD-009 quebrado: "1.500" vira 1,50 (`inteiro, fracao = grupos[0], grupos[1][:2]`) | ✅ Killed (3 falhas: `test_sem_virgula_ponto_de_milhar_com_grupos_de_tres`, `test_celulas_tipadas_e_textos_brasileiros`, `test_status_pendente_nao_entra_no_saldo`) |
| 2 | `data_exchange/importacao/interpretacao.py:180-182` | Tipo sem normalizar acento (`tipo_na_linha.lower().strip()` no lugar de `normalizar`) | ✅ Killed (2 falhas e 2 erros: "Crédito", "Débito", "saída" e o teste de status pela rota) |
| 3 | `data_exchange/importacao/repetidos.py:69-72` | Repetidos como conjunto: a existência ignora todas as iguais e a primeira linha do arquivo marca a chave (FIN-21) | ✅ Killed (6 falhas: N − M, OFX antigo, transferência, reimportação e as duas importações simultâneas) |
| 4 | `data_exchange/importacao/gravacao.py:72-73` | Savepoint por linha removido (`with transaction.atomic()` → `if True`) | ✅ Killed (1 erro: `test_erro_de_banco_rejeita_so_a_linha_sem_o_texto_da_excecao`) |
| 5 | `data_exchange/importacao/leitura.py:121-122` | Linha vazia contada como lida (`continue` → `pass`) | ✅ Killed (3 falhas: linhas vazias no CSV e no XLSX e o limite de 10.000 com linhas vazias no fim) |
| 6 | `data_exchange/importacao/gravacao.py:139` | Sugestão sem checar se a categoria está ativa | ✅ Killed (1 falha: `test_categoria_excluida_ou_de_outro_tipo_nao_e_sugerida`) |
| 7 | `transactions/serializers.py:355` | A correção não desliga `categoria_sugerida` | ✅ Killed (1 falha: `test_trocar_uma_sugerida_grava_a_correcao_e_desliga_a_marca`) |
| 8 | `src/components/transactions/import-dialog.tsx:541` (FE) | Atalho sem `import_batch` (`/transacoes?suggested_category=true`) | ✅ Killed (1 falha: "com sugeridas, mostra quantas e o atalho para a lista filtrada") |

**Verificação do isolamento**: `git status --porcelain` vazio antes e depois nos dois repositórios, exceto este `validation.md`. `git worktree list` mostra só a árvore principal nos dois. Não sobrou pasta `fluxar-*-mut`, e o `node_modules` do frontend não foi tocado. O único container que continua no ar é o `fluxar-backend-backend-1` do compose.

**Sensor depth**: leve (8 mutações de comportamento, 7 no backend e 1 no frontend, por decisão do usuário)
**Result**: 8/8 killed, 0 survived - PASS

---

## Code Quality (nível leve, amostragem)

| Princípio | Status |
| --------- | ------ |
| Etapas com fronteiras claras | ✅ `data_exchange/importacao/` com `leitura.py`, `interpretacao.py`, `repetidos.py` e `gravacao.py`, como no design; `data_exchange/services.py` perdeu as 426 linhas da importação antiga |
| Reuso | ✅ `ler_valor_em_texto` em `core/valores.py` segue `lerValorDigitado`; transferências por `TransactionService.create_transfer`; recálculo adiado em `accounts/saldo.py` |
| Erros sem texto da exceção (CONTRATO-29) | ✅ `ERRO_AO_GRAVAR` na resposta e a exceção no log (`tests/importacao/test_gravacao.py:111-113`) |
| Testes mapeados aos ACs | ✅ cada teste cita os IDs na docstring; os poucos sem ID cobrem edge cases ou o "Done when" de T5, T6 e T9 |
| Asserções no valor da spec | ✅ mensagens exatas, os totais do Independent Test (10, 7, 0, 3) e os valores de AD-009 conferidos literalmente |
| Teste antigo ajustado | ✅ só `tests/contratos/test_erros.py:137`, com a mensagem nova do design e o corpo ainda exato |
| Guidelines | AD-033 e AD-034 (testes no container e no vitest) seguidos |

---

## Observações (não bloqueiam)

1. **IMPORT-03 só no seletor da planilha.** O teste confere `accept=".csv,.xlsx"` no modo planilha (FE `dialogo-de-importacao.test.tsx:98`). O `.ofx` do modo OFX está no código (`import-dialog.tsx:50`, `ACEITOS.OFX`), mas nenhum teste o confere.
2. **IMPORT-05 "sem gravar nenhuma linha" pelo preflight.** O limite de 10.000 linhas é testado pela rota do preflight, que não grava nada. A rota de importação usa a mesma `ler_planilha` antes de qualquer gravação (`data_exchange/views.py`), mas não há teste de importação com 10.001 linhas que confira zero transações.
3. **IMPORT-41 por configuração.** A evidência é a configuração do `gunicorn.conf.py` (`gthread`, 2 workers e 4 threads), não uma requisição atendida durante uma importação real. A abordagem foi escolhida no design, mas o comportamento sob carga não é testado.
4. **IMPORT-07 testado na função.** A mensagem é conferida no `ValidationError` de `ler_ofx` (`tests/importacao/test_leitura.py:170`), não pela rota. O DRF converte esse erro em 400 no campo `file`, como nas outras recusas testadas pela rota.
5. **Artefatos desatualizados.** O cabeçalho de `tasks.md` ainda está como `Status: In Progress`, e a rastreabilidade em `spec.md` está como `Implemented`, sem `Verified`.
6. **Gates reduzidos.** Nesta rodada, o Verifier rodou só a suíte inteira do backend e o `npm test` do frontend. `compileall`, `makemigrations --check`, `tsc`, lint e build não foram repetidos.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| IMPORT-01 a IMPORT-49 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (PASS)

**Spec-anchored check**: 49/49 ACs com evidência; nenhuma lacuna de precisão da spec; 6 observações menores
**Sensor**: 8/8 mutações mortas (7 no backend, 1 no frontend)
**Gate**: backend 782 OK; frontend 198 testes OK

**Próximos passos**: opcionais. Um teste para o `accept=".ofx"`, um teste de importação com 10.001 linhas que confira zero gravadas, e a atualização do cabeçalho de `tasks.md` e dos status da rastreabilidade. Nenhum deles bloqueia.
