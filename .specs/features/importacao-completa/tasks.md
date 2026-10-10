# Importação completa Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/importacao-completa/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Leitura das abas, detecção, interpretação, repetidos, contas e rotas (backend) | integration | Cada AC com status, código e mensagem exatos; fixture com o layout do Mobills (4 abas, rodapé Total, valor com sinal, "Paga") | `tests/importacao/test_*.py` | `docker compose exec -T backend python manage.py test tests.importacao --noinput` |
| Assistente de planilha: arquivo, abas, contas, linhas e resultado (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/importacao/*.test.tsx` | `npx vitest run tests/importacao` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 149 erros de lint antigos: o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.importacao --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/importacao` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Leitura e detecção

```
T1 → T2
```

### Phase 2: Interpretação e repetidos

```
T3 → T4
```

### Phase 3: Contas e rotas

```
T5 → T6
```

### Phase 4: Telas

```
T7 → T8
T8 → T9
T9 → T10
T10 → T11
T11 → T12
T12 → T13
```

---

## Task Breakdown

### Phase 1: Leitura e detecção

#### T1: Leitura de todas as abas

**What**: `ler_abas` devolve todas as abas do XLSX e o CSV como aba única, com cabeçalho na primeira linha não vazia, linhas vazias puladas e o limite de 10.000 linhas na soma; `arquivo_xlsx` dos testes ganha várias abas.
**Where**: `data_exchange/importacao/leitura.py`, `tests/importacao/base.py`
**Depends on**: None
**Reuses**: `ler_csv`, `vazio`, `LinhaBruta`
**Requirement**: IMPCOMP-01, IMPCOMP-02, IMPCOMP-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Um XLSX de 4 abas devolve as 4 com nome, cabeçalho e linhas numeradas
- [x] Um CSV devolve uma aba com o nome do arquivo
- [x] Duas abas com 6.000 linhas cada recebem 400 "O arquivo passa do limite de 10.000 linhas."
- [x] As rotas atuais continuam passando nos testes da spec `importacao`
- [x] Quick gate passa
- [x] Test count: 8 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: lê todas as abas da planilha na importação`

---

#### T2: Detecção de colunas, papéis, modelo e contas

**What**: `deteccao.py` com `nome_comparavel`, sinônimos, papel de cada aba, modelo Mobills, abas contidas, contas do arquivo com a sugestão de vincular ou criar e `detectar_plano` que respeita o plano editado.
**Where**: `data_exchange/importacao/deteccao.py` (novo)
**Depends on**: T1
**Reuses**: `normalizar`
**Requirement**: IMPCOMP-04, IMPCOMP-05, IMPCOMP-06, IMPCOMP-07, IMPCOMP-08, IMPCOMP-09, IMPCOMP-10, IMPCOMP-11, IMPCOMP-12, IMPCOMP-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cabeçalhos "Histórico", "Quantia" e "Banco" viram descrição, valor e conta
- [x] Aba com origem e destino é de transferências; com data e valor, de receitas e despesas; sem elas, ignorada com "Colunas não reconhecidas"
- [x] O arquivo do Mobills é reconhecido e ignora "Despesas" e "Receitas"
- [x] Uma aba repetida dentro de outra, num arquivo que não é do Mobills, é ignorada com "Contida na aba <nome>"
- [x] As 11 contas do Mobills vêm com linhas, soma, período e o tipo sugerido; "nubank " vincula à conta "Nubank" existente
- [x] O papel e as colunas de um plano editado prevalecem
- [x] Quick gate passa
- [x] Test count: 17 testes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: detecta as abas, as colunas e as contas da planilha`

---

### Phase 2: Interpretação e repetidos

#### T3: Interpretação ampliada

**What**: Interpretação por aba com o papel e as colunas do plano e o resolvedor de contas; linha de resumo pulada; situações pendentes ampliadas; entrada e saída; transferência na aba de receitas e despesas; rejeição com a aba; correções e exclusões do plano; `description_column` conferida na transferência.
**Where**: `data_exchange/importacao/interpretacao.py`, `data_exchange/importacao/leitura.py`
**Depends on**: T2
**Reuses**: `Interpretador`
**Requirement**: IMPCOMP-15, IMPCOMP-16, IMPCOMP-17, IMPCOMP-18, IMPCOMP-19, IMPCOMP-20, IMPCOMP-21, IMPCOMP-22, IMPCOMP-32, IMPCOMP-33, IMPCOMP-34

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A linha "Total (57)" com descrição e conta vazias é pulada e contada em `summary_rows`; um lançamento "Total" com conta é importado
- [x] "Paga" é efetivada; "Não paga", "A pagar" e "Agendada" são pendentes
- [x] Entrada preenchida vira receita, saída vira despesa, as duas ou nenhuma rejeitam com "Valor inválido"
- [x] Tipo "Transferência" com destino mapeado vira transferência
- [x] A rejeição traz a aba, o número e o motivo
- [x] Corrigir a data de uma linha rejeitada a torna válida; uma correção inválida volta rejeitada; uma linha excluída fica como excluída
- [x] Coluna de descrição da transferência que não existe no cabeçalho recebe 400 com a coluna
- [x] Quick gate passa
- [x] Test count: 16 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: interpreta rodapés, situações, entrada e saída e correções da planilha`

---

#### T4: Repetidos com os dois tipos

**What**: `Repetidos` carrega os contadores de receitas e despesas e o de transferências quando o lote mistura tipos; `marcar` aponta as repetidas sem gravar.
**Where**: `data_exchange/importacao/repetidos.py`
**Depends on**: T3
**Reuses**: `Repetidos`
**Requirement**: IMPCOMP-31, IMPCOMP-46

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Num lote com receitas, despesas e transferências já importadas, todas são ignoradas
- [x] `marcar` devolve as repetidas sem criar transação
- [x] Quick gate passa
- [x] Test count: 4 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: confere os repetidos de receitas e de transferências no mesmo envio`

---

### Phase 3: Contas e rotas

#### T5: Criação de contas e saldo

**What**: `conferir_limite` com `quantidade`; `contas.py` com `criar_contas` e `acertar_saldos` (saldo inicial = saldo atual menos o efeito das transações efetivadas importadas).
**Where**: `data_exchange/importacao/contas.py` (novo), `core/travas.py`
**Depends on**: T4
**Reuses**: `calcular`, `recalcular`, `conferir_limite`
**Requirement**: IMPCOMP-25, IMPCOMP-26, IMPCOMP-27, IMPCOMP-29

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] As contas criadas têm nome, tipo, instituição e cor do plano
- [x] Depois da gravação, o saldo de cada conta criada é o saldo atual informado, inclusive com transferências e pendentes
- [x] Três contas a criar com duas vagas no plano recebem 403 `plan_limit_reached` sem gravar nada
- [x] `conferir_limite` sem quantidade continua igual
- [x] Quick gate passa
- [x] Test count: 7 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: cria as contas da planilha com o saldo atual informado`

---

#### T6: Rotas da análise e da importação

**What**: `PlanoSerializer`; `POST /api/import/analise/` e `POST /api/import/` com a trava `importacao_planilha`, a trava de tags no plano, as respostas com linhas, resumo, contas criadas, totais por aba e linhas de resumo; o "Out of Scope" da spec `importacao` atualizado.
**Where**: `data_exchange/serializers.py` (novo), `data_exchange/views.py`, `data_exchange/urls.py`, `.specs/features/importacao/spec.md`, `tests/permissoes/`
**Depends on**: T5
**Reuses**: `get_owned_or_400`, `ler_saldo`, `Gravacao.importar`
**Requirement**: IMPCOMP-13, IMPCOMP-23, IMPCOMP-24, IMPCOMP-28, IMPCOMP-30, IMPCOMP-35, IMPCOMP-36, IMPCOMP-45, IMPCOMP-47, IMPCOMP-48, IMPCOMP-50, IMPCOMP-51, IMPCOMP-52

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A análise do Mobills devolve o plano, as linhas com estado e o resumo, sem gravar nada
- [x] A importação do Mobills com as contas a criar grava 57 receitas e despesas e 9 transferências, cria as 11 contas com o saldo informado e responde com `accounts_created`, `by_sheet` e `summary_rows`
- [x] Reimportar com as contas vinculadas grava zero e ignora tudo
- [x] Conta vinculada de outro usuário, conta a criar inválida, JSON inválido e chave de linha inexistente recebem 400 nos campos
- [x] Com `importacao_planilha` travada, 403; com `tags` travada, as linhas entram sem tags
- [x] Nenhum log leva nomes de conta, descrições ou valores
- [x] Build gate passa
- [x] Test count: 17 testes, mais 2 casos no catálogo de travas (`tests/permissoes/test_travas_de_recurso.py`)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: analisa e importa a planilha completa com o plano revisado`

---

### Phase 4: Telas

#### T7: Serviço e tipos

**What**: `analisarArquivo` e `importarArquivo` com 120 s e os tipos `PlanoDeImportacao`, `AnaliseDeImportacao`, `LinhaAnalisada` e o resultado.
**Where**: `src/services/import-export.ts`, `src/types/importacao.ts` (novo)
**Depends on**: T6
**Reuses**: `api`
**Requirement**: IMPCOMP-13, IMPCOMP-45

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A análise envia o arquivo e o plano em JSON no multipart
- [ ] A importação envia o plano final e devolve o resumo
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: cria o serviço da análise e da importação completa`

---

#### T8: Passo do arquivo e resumo

**What**: `AssistenteDePlanilha` com arrastar e soltar; escolher o arquivo chama a análise; resumo fixo no topo da revisão.
**Where**: `src/components/importacao/AssistenteDePlanilha.tsx` (novo), `src/components/importacao/PassoArquivo.tsx` (novo)
**Depends on**: T7
**Reuses**: `tratarErro`
**Requirement**: IMPCOMP-37, IMPCOMP-43

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Escolher o arquivo chama a análise sem botão de avançar
- [ ] O resumo mostra válidas, rejeitadas, repetidas, excluídas, contas novas e os totais por tipo
- [ ] Um 400 da análise aparece pelo `tratarErro`
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: analisa a planilha assim que o arquivo é escolhido`

---

#### T9: Abas e colunas

**What**: Aba "Abas e colunas" com o papel e as colunas de cada aba preenchidos, os cabeçalhos reais como opções, o selo do Mobills e o motivo das ignoradas; mudanças pedem nova análise com debounce.
**Where**: `src/components/importacao/RevisaoDeAbas.tsx` (novo)
**Depends on**: T8
**Reuses**: `Select`
**Requirement**: IMPCOMP-38, IMPCOMP-44

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Os selects vêm preenchidos com o plano detectado
- [ ] Aparecem o selo "Modelo Mobills reconhecido" e "Contida na aba Receitas e Despesas"
- [ ] Trocar o papel de uma aba pede nova análise com o plano editado
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: mostra e ajusta as abas e as colunas detectadas`

---

#### T10: Contas

**What**: Aba "Contas" com nome no arquivo, linhas, soma e período; vincular a uma conta ativa ou criar com nome, tipo, instituição e saldo atual; aviso e trava do limite de contas.
**Where**: `src/components/importacao/RevisaoDeContas.tsx` (novo)
**Depends on**: T9
**Reuses**: `MoneyInput`, `BANKS`, `AvisoDeLimite`, `usePlan`
**Requirement**: IMPCOMP-39, IMPCOMP-40, IMPCOMP-44

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Uma conta com nome igual vem vinculada; as outras vêm para criar com o tipo sugerido
- [ ] Criar com saldo atual de R$ 1.234,56 manda `saldo_atual` "1234.56" no plano
- [ ] No limite de contas, marcar mais uma para criar fica impedido e o aviso aparece
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: permite vincular ou criar as contas da planilha com o saldo atual`

---

#### T11: Linhas

**What**: Aba "Linhas" com a tabela paginada, filtros Todas, Rejeitadas, Repetidas e Excluídas, busca, edição na linha e excluir ou restaurar, mandando as correções no plano.
**Where**: `src/components/importacao/RevisaoDeLinhas.tsx` (novo)
**Depends on**: T10
**Reuses**: `Paginacao`
**Requirement**: IMPCOMP-41, IMPCOMP-42

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O filtro Rejeitadas mostra só as rejeitadas, com o motivo
- [ ] Corrigir a data manda a correção no plano e mostra a linha reanalisada
- [ ] Excluir manda `excluir: true`; restaurar tira a chave do plano
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: permite revisar, corrigir e excluir as linhas antes de importar`

---

#### T12: Resultado

**What**: Resultado com os quatro totais, as contas criadas, os totais por aba e as rejeitadas com a aba; `atualizarUso()` quando contas foram criadas.
**Where**: `src/components/importacao/ResultadoDaImportacao.tsx` (novo), `src/components/importacao/AssistenteDePlanilha.tsx`
**Depends on**: T11
**Reuses**: `usePlan`
**Requirement**: IMPCOMP-49

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O resultado mostra as contas criadas e os totais por aba
- [ ] As rejeitadas aparecem como "<aba>, linha <n>: <motivo>"
- [ ] Com contas criadas, `atualizarUso` é chamado
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: mostra o resultado da importação completa por aba`

---

#### T13: Página de importação

**What**: O card de planilha abre o assistente novo; o guia de formatos fala da detecção automática; o OFX continua no diálogo atual.
**Where**: `src/app/(app)/importar/page.tsx`
**Depends on**: T12
**Reuses**: `RecursoBloqueado`
**Requirement**: IMPCOMP-43, IMPCOMP-50

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O card de planilha abre o assistente
- [ ] O OFX continua abrindo o diálogo atual
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `feat: troca a importação de planilha pelo assistente completo`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 a 3 (T1 a T6), lote 2 com a fase 4 (T7 a T13).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Leitura de todas as abas | um componente | ✅ Granular |
| T2: Detecção de colunas, papéis, modelo e contas | um componente | ✅ Granular |
| T3: Interpretação ampliada | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T4: Repetidos com os dois tipos | um componente | ✅ Granular |
| T5: Criação de contas e saldo | um componente | ✅ Granular |
| T6: Rotas da análise e da importação | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T7: Serviço e tipos | um componente | ✅ Granular |
| T8: Passo do arquivo e resumo | um componente | ✅ Granular |
| T9: Abas e colunas | um componente | ✅ Granular |
| T10: Contas | um componente | ✅ Granular |
| T11: Linhas | um componente | ✅ Granular |
| T12: Resultado | um componente | ✅ Granular |
| T13: Página de importação | um componente | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Leitura de todas as abas | Backend | integration | integration | ✅ OK |
| T2: Detecção de colunas, papéis, modelo e contas | Backend | unit | unit | ✅ OK |
| T3: Interpretação ampliada | Backend | integration | integration | ✅ OK |
| T4: Repetidos com os dois tipos | Backend | integration | integration | ✅ OK |
| T5: Criação de contas e saldo | Backend | integration | integration | ✅ OK |
| T6: Rotas da análise e da importação | Backend | integration | integration | ✅ OK |
| T7: Serviço e tipos | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T8: Passo do arquivo e resumo | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T9: Abas e colunas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T10: Contas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T11: Linhas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T12: Resultado | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T13: Página de importação | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
