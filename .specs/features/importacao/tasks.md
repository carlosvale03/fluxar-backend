# Importacao Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/importacao/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Leitura de valores, datas e textos (backend) | unit | Todos os exemplos da spec e de AD-009 | `tests/importacao/test_texto.py` | `docker compose exec -T backend python manage.py test tests.importacao --noinput` |
| Leitura, interpretação, repetidos, gravação, views e correções (backend) | integration | Cada AC com status, totais e motivo exatos; arquivos de exemplo gerados no próprio teste (CSV, XLSX e OFX) | `tests/importacao/test_*.py` | idem |
| Concorrência e desempenho (backend) | integration | Threads com `TransactionTestCase`; 10.000 linhas com tempo medido | `tests/importacao/test_concorrencia.py`, `test_desempenho.py` | idem |
| Diálogo e lista (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/importacao/*.test.tsx` | `npx vitest run tests/importacao` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 139 erros de lint antigos (MAN-04): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.importacao --noinput` |
| Full | Tarefas que mexem em saldo, signals, serializers ou filtros compartilhados | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/importacao` (em `fluxar-frontend`) |
| Build (frontend) | Fim da fase de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Leitura do arquivo

```
T1 → T2
```

### Phase 2: Interpretação e repetidos

```
T3 → T4
T4 → T5
```

### Phase 3: Gravação e resultado

```
T6 → T7
T7 → T8
T8 → T9
```

### Phase 4: Correções de categoria

```
T10 → T11
```

### Phase 5: Frontend

```
T12 → T13
```

---

## Task Breakdown

### Phase 1: Leitura do arquivo

#### T1: Valores e datas em texto

**What**: `ler_valor_em_texto` em `core/valores.py` (AD-009, com vírgula decimal, sinal e "R$") e `ler_data_em_texto` em `data_exchange/importacao/texto.py`, com a normalização de texto sem acentos.
**Where**: `core/valores.py`, `data_exchange/importacao/texto.py` (novo)
**Depends on**: None
**Reuses**: `normalize_str` de `data_exchange/services.py`
**Requirement**: IMPORT-09, IMPORT-10, IMPORT-12, IMPORT-13, IMPORT-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] "1.234,56" → 1234.56; "R$ -45,00" → -45.00; "1.500" → 1500.00; "1.500.000" → 1500000.00; "12.5" → 12.50; "0.50" → 0.50
- [x] "abc", "0,00" e "1,234" levantam o erro de "Valor inválido"
- [x] "04/03/2026", "04/03/26" e "2026-03-04" → 4 de março de 2026; "29/02/2025" e "2026/03/04" levantam "Data inválida"
- [x] Quick gate passa
- [x] Test count: pelo menos 6 testes (real: 7 testes novos; suíte 701 → 708)

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(importacao): lê valores e datas no formato brasileiro`

---

#### T2: Leitura do arquivo com formatos e limites

**What**: `data_exchange/importacao/leitura.py`: extensão, 5 MB, 10.000 linhas, CSV com `;` ou `,` e UTF-8 ou Windows-1252, XLSX com células tipadas, OFX com uma conta, número de cada linha e linhas vazias puladas; o preflight passa a usar essa leitura.
**Where**: `data_exchange/importacao/leitura.py` (novo), `data_exchange/views.py`
**Depends on**: T1
**Reuses**: `OfxParser`, `openpyxl`, `pandas`
**Requirement**: IMPORT-01, IMPORT-02, IMPORT-04, IMPORT-05, IMPORT-06, IMPORT-07, IMPORT-08, IMPORT-11, IMPORT-14, IMPORT-32

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `.xls` e `.txt` recebem 400 com "Formato não suportado. Envie um arquivo OFX, CSV ou XLSX."
- [x] CSV de 6 MB recebe 400 com "O arquivo passa do limite de 5 MB." sem ler linhas
- [x] CSV com 10.001 linhas de dados recebe 400 com "O arquivo passa do limite de 10.000 linhas."
- [x] CSV do Excel em português (`;` e Windows-1252, com "Crédito") é lido sem erro
- [x] Coluna mapeada ausente recebe 400 citando a coluna; arquivo corrompido recebe "Não foi possível ler o arquivo."
- [x] OFX com duas contas recebe 400 com a mensagem exata
- [x] Célula numérica 1500 e célula de data do XLSX chegam como número e data
- [x] Linhas totalmente vazias somem e as demais mantêm o número do arquivo (cabeçalho = 1)
- [x] O preflight recusa `.xls` com a mesma mensagem
- [x] Quick gate passa
- [x] Test count: pelo menos 10 testes (real: 14 testes novos; suíte 708 → 722)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(importacao): lê OFX, CSV e XLSX com formatos e limites`

---

### Phase 2: Interpretação e repetidos

#### T3: Interpretação de cada linha

**What**: `data_exchange/importacao/interpretacao.py`: tipo, sinal, descrição do OFX, status, conta, transferência e limites de texto, devolvendo `LinhaImportada` ou `Rejeicao`.
**Where**: `data_exchange/importacao/interpretacao.py` (novo)
**Depends on**: None
**Reuses**: `texto.py`
**Requirement**: IMPORT-16, IMPORT-17, IMPORT-18, IMPORT-19, IMPORT-20, IMPORT-21, IMPORT-22, IMPORT-24, IMPORT-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] "Crédito", "CREDITO", "Entrada" e "C" viram receita; "Débito", "saída" e "D" viram despesa; "Transferido" é rejeitado com "Tipo desconhecido: Transferido"
- [ ] Sem coluna de tipo, -45,00 é despesa de 45.00 e 100 é receita
- [ ] OFX sem memo usa o favorecido; sem os dois, "Sem descrição"
- [ ] "Pendente" e "pending" importam pendente; "Pago" e vazio, efetivada
- [ ] Conta não mapeada, conta excluída e sem conta rejeitam com "Conta não mapeada: <nome>", "Conta excluída: <nome>" e "Conta não informada"
- [ ] Transferência com origem igual ao destino rejeita com "Origem e destino iguais"
- [ ] Descrição de 300 caracteres rejeita com "Texto longo demais: descrição"; tag nova de 60, com "Texto longo demais: tag"
- [ ] Quick gate passa
- [ ] Test count: pelo menos 12 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(importacao): interpreta tipo, status e conta de cada linha`

---

#### T4: Campos de importação e correções

**What**: `Transaction.import_batch`, `fitid` e `categoria_sugerida`, a restrição de `fitid` único por conta e o modelo `CorrecaoDeCategoria`, com a migração `transactions/0010_importacao`.
**Where**: `transactions/models.py`, `transactions/migrations/`
**Depends on**: T3
**Reuses**: NONE
**Requirement**: IMPORT-34, IMPORT-42, IMPORT-48

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Duas transações da mesma conta com o mesmo `fitid` não podem existir; contas diferentes podem
- [ ] Apagar o usuário apaga as correções dele
- [ ] Build gate passa (makemigrations --check)
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `feat(transactions): guarda o lote, o FITID e as correções de categoria`

---

#### T5: Linhas já importadas

**What**: `data_exchange/importacao/repetidos.py`: contagem por chave limitada às contas e ao período do arquivo, consumida na ordem das linhas; `fitid` no OFX e chave de data, valor, tipo e descrição nos demais casos.
**Where**: `data_exchange/importacao/repetidos.py` (novo)
**Depends on**: T4
**Reuses**: NONE
**Requirement**: IMPORT-34, IMPORT-35, IMPORT-36, IMPORT-37, IMPORT-38

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] OFX com `fitid` já gravado na conta é ignorado mesmo com a descrição editada
- [ ] OFX antigo (transação gravada sem `fitid`) é reconhecido pela data, valor, tipo e descrição
- [ ] Duas compras iguais de R$ 5,00 no mesmo arquivo, com zero existentes, gravam as duas; com uma existente, gravam uma
- [ ] Transferência igual (origem, destino, data, valor) é ignorada
- [ ] A consulta não carrega transações fora das contas e do período do arquivo
- [ ] Quick gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(importacao): ignora linhas já importadas contando as repetições`

---

### Phase 3: Gravação e resultado

#### T6: Recálculo de saldo adiado

**What**: `recalculo_adiado()` em `accounts/saldo.py`: dentro do contexto, os signals anotam as contas e o recálculo roda uma vez na saída.
**Where**: `accounts/saldo.py`, `transactions/signals.py`
**Depends on**: None
**Reuses**: `recalcular`
**Requirement**: IMPORT-40

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Dentro do contexto, 100 transações numa conta disparam um recálculo só, e o saldo final segue SALDO-01
- [ ] Fora do contexto, o comportamento continua igual (suíte `tests.saldo` passa)
- [ ] Full gate passa
- [ ] Test count: pelo menos 3 testes

**Tests**: integration
**Gate**: full

**Commit**: `perf(accounts): recalcula o saldo uma vez por importação`

---

#### T7: Gravação linha a linha e resumo

**What**: `data_exchange/importacao/gravacao.py` com a trava das contas, o savepoint por linha, categorias e tags, transferências e `import_batch`; as views de OFX e planilha usam o pacote novo e devolvem o resumo `{total, imported, ignored, rejected, suggested, batch_id, rejected_rows}`; o código antigo de importação sai de `services.py`.
**Where**: `data_exchange/importacao/gravacao.py` (novo), `data_exchange/views.py`, `data_exchange/services.py`
**Depends on**: T6
**Reuses**: `create_transfer`, `recalculo_adiado`
**Requirement**: IMPORT-23, IMPORT-25, IMPORT-27, IMPORT-28, IMPORT-29, IMPORT-30, IMPORT-31

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O Independent Test de IMPORT-27 a IMPORT-33 (10 linhas, rejeitadas 3, 6 e 9) grava 7 e responde 200 com 10, 7, 0 e 3 e os motivos exatos
- [ ] Erro de banco simulado na linha 5 rejeita só ela com "Erro ao gravar a linha", sem o texto da exceção, e as outras ficam gravadas
- [ ] Reimportar o mesmo arquivo responde 200 com zero gravadas
- [ ] Categoria "alimentação" reaproveita "Alimentação"; uma nova é criada uma vez só
- [ ] Transferência importada cria as duas pernas pelas regras do saldo
- [ ] Arquivo só com o cabeçalho responde 200 com zeros
- [ ] O saldo final de cada conta segue SALDO-01
- [ ] Full gate passa
- [ ] Test count: pelo menos 9 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix(importacao): grava cada linha válida e informa as rejeitadas com o motivo`

---

#### T8: Importações simultâneas

**What**: Teste com threads de duas importações do mesmo arquivo ao mesmo tempo, com a trava das contas e a restrição do `fitid`.
**Where**: `tests/importacao/test_concorrencia.py`
**Depends on**: T7
**Reuses**: o padrão de `tests/saldo/test_concorrencia.py`
**Requirement**: IMPORT-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Duas importações simultâneas da mesma planilha gravam cada linha uma vez
- [ ] Duas importações simultâneas do mesmo OFX gravam cada `fitid` uma vez
- [ ] Quick gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: quick

**Commit**: `test(importacao): cobre importações simultâneas do mesmo arquivo`

---

#### T9: Tempo de importação e concorrência do servidor

**What**: Teste de 10.000 linhas em até 30 segundos e `gunicorn.conf.py` com `gthread`, workers por `WEB_CONCURRENCY` e threads; `DEPLOY.md` registra as variáveis.
**Where**: `gunicorn.conf.py` (novo), `DEPLOY.md`, `tests/importacao/test_desempenho.py`
**Depends on**: T8
**Reuses**: NONE
**Requirement**: IMPORT-40, IMPORT-41

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Um CSV de 10.000 linhas válidas importa em até 30 segundos no container local
- [ ] `gunicorn.conf.py` declara `gthread` com mais de uma thread e `WEB_CONCURRENCY` com padrão 2
- [ ] Build gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `perf(importacao): importa 10 mil linhas em até 30 segundos sem travar o servidor`

---

### Phase 4: Correções de categoria

#### T10: Registro das correções

**What**: `TransactionSerializer.update` registra a correção quando a categoria de uma transação importada muda e desliga `categoria_sugerida`; o serializer expõe `import_batch` e `category_suggested`; a lista aceita os filtros `import_batch` e `suggested_category`.
**Where**: `transactions/serializers.py`, `transactions/filtros.py`, `transactions/views.py`
**Depends on**: None
**Reuses**: `normalizar_descricao`
**Requirement**: IMPORT-42, IMPORT-45, IMPORT-46, IMPORT-48, IMPORT-49

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Trocar a categoria de uma transação importada grava descrição, conta, categoria de antes, de depois e data
- [ ] Definir a categoria de uma importada sem categoria também grava a correção
- [ ] Trocar a categoria de uma transação não importada não grava nada
- [ ] Trocar uma sugerida grava a correção e desliga `category_suggested`
- [ ] `?import_batch=<id>&suggested_category=true` lista só as sugeridas daquele lote
- [ ] As correções de um usuário não aparecem para outro (IMPORT-49) e somem com a exclusão dele (IMPORT-48)
- [ ] Full gate passa
- [ ] Test count: pelo menos 7 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat(transactions): registra as correções de categoria das transações importadas`

---

#### T11: Sugestão de categoria na importação

**What**: A gravação sugere, para a linha sem categoria, a categoria da correção mais recente do usuário com a mesma descrição normalizada, quando ela existe, está ativa e tem o tipo da linha; o resumo conta as sugeridas.
**Where**: `data_exchange/importacao/gravacao.py`
**Depends on**: T10
**Reuses**: `CorrecaoDeCategoria`
**Requirement**: IMPORT-43, IMPORT-44, IMPORT-47

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Depois de corrigir "UBER *TRIP 1234" para Transporte, "UBER *TRIP 5678" importa em Transporte com `category_suggested` e o resumo tem `suggested: 1`
- [ ] Duas correções para a mesma descrição: vale a mais recente
- [ ] Linha com categoria no arquivo mantém a do arquivo, sem sugestão
- [ ] Categoria da correção excluída: a linha fica sem categoria
- [ ] Build gate passa
- [ ] Test count: pelo menos 5 testes

**Tests**: integration
**Gate**: build

**Commit**: `feat(importacao): sugere a categoria pelas correções do usuário`

---

### Phase 5: Frontend

#### T12: Diálogo de importação

**What**: O diálogo aceita só `.ofx`, `.csv` e `.xlsx` e mostra os quatro totais, a lista de rejeitadas com linha e motivo, e as sugeridas com o atalho para a lista filtrada; `ImportSummary` no formato novo.
**Where**: `src/components/transactions/import-dialog.tsx`, `src/services/import-export.ts`
**Depends on**: None
**Reuses**: `tratarErro`
**Requirement**: IMPORT-03, IMPORT-33, IMPORT-45

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O seletor de arquivo de planilha aceita `.csv,.xlsx` e recusa `.xls` com a mensagem do backend
- [ ] O resumo mostra lidas, gravadas, ignoradas e rejeitadas, e cada rejeitada com "Linha N: motivo"
- [ ] Com `suggested: 3`, mostra "3 linhas com categoria sugerida" e o atalho leva a `/transacoes?import_batch=<id>&suggested_category=true`
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix(frontend): mostra o resultado completo da importação`

---

#### T13: Lista filtrada e selo de sugerida

**What**: A tela de transações lê `import_batch` e `suggested_category` da URL, envia os dois e mostra o filtro ativo com opção de limpar; a linha e o formulário mostram "Sugerida pelo seu histórico".
**Where**: `src/app/(app)/transacoes/page.tsx`, `src/components/transactions/transaction-filters.tsx`, `src/components/transactions/transaction-form-dialog.tsx`, `src/types/transactions.ts`
**Depends on**: T12
**Reuses**: NONE
**Requirement**: IMPORT-45, IMPORT-46

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Abrir `/transacoes?import_batch=abc&suggested_category=true` envia os dois parâmetros e mostra o filtro ativo
- [ ] Transação com `category_suggested` mostra o selo na lista e no formulário
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `feat(frontend): filtra as transações sugeridas e mostra de onde veio a categoria`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 a 3 (T1 a T9, backend), lote 2 com as fases 4 e 5 (T10 a T13).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Valores e datas em texto | um componente | ✅ Granular |
| T2: Leitura do arquivo com formatos e limites | uma etapa com várias regras | ⚠️ Coeso |
| T3: Interpretação de cada linha | uma etapa com várias regras | ⚠️ Coeso |
| T4: Campos de importação e correções | um componente | ✅ Granular |
| T5: Linhas já importadas | um componente | ✅ Granular |
| T6: Recálculo de saldo adiado | um componente | ✅ Granular |
| T7: Gravação linha a linha e resumo | uma etapa com várias regras | ⚠️ Coeso |
| T8: Importações simultâneas | um componente | ✅ Granular |
| T9: Tempo de importação e concorrência do servidor | um componente | ✅ Granular |
| T10: Registro das correções | uma etapa com várias regras | ⚠️ Coeso |
| T11: Sugestão de categoria na importação | um componente | ✅ Granular |
| T12: Diálogo de importação | um componente | ✅ Granular |
| T13: Lista filtrada e selo de sugerida | um componente | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | None | sem seta dentro da fase | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | None | sem seta dentro da fase | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | None | sem seta dentro da fase | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | None | sem seta dentro da fase | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Valores e datas em texto | Backend | unit | unit | ✅ OK |
| T2: Leitura do arquivo com formatos e limites | Backend | integration | integration | ✅ OK |
| T3: Interpretação de cada linha | Backend | integration | integration | ✅ OK |
| T4: Campos de importação e correções | Backend | integration | integration | ✅ OK |
| T5: Linhas já importadas | Backend | integration | integration | ✅ OK |
| T6: Recálculo de saldo adiado | Backend | integration | integration | ✅ OK |
| T7: Gravação linha a linha e resumo | Backend | integration | integration | ✅ OK |
| T8: Importações simultâneas | Backend | integration | integration | ✅ OK |
| T9: Tempo de importação e concorrência do servidor | Backend | integration | integration | ✅ OK |
| T10: Registro das correções | Backend | integration | integration | ✅ OK |
| T11: Sugestão de categoria na importação | Backend | integration | integration | ✅ OK |
| T12: Diálogo de importação | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T13: Lista filtrada e selo de sugerida | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
