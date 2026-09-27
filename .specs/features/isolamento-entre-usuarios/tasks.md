# Isolamento entre usuarios Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/isolamento-entre-usuarios/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: none. Não há `AGENTS.md`, `CONTRIBUTING.md` nem configuração de cobertura; o `CLAUDE.md` só trata das specs, e o CI só compila e confere migrações (`.github/workflows/ci-backend.yml`). O repositório não tem nenhum teste (`api/tests.py` e `data_exchange/tests.py` são o modelo vazio do Django), por isso valem os padrões fortes, com o `TestCase` do Django e o `APITestCase` do DRF, já instalados.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Campo de relação e helper (`core/fields.py`) | integration | Todos os ramos: objeto próprio, de outro usuário, inexistente, categoria-modelo, UUID malformado, tipo errado, `many=True` e sem `request` | `tests/isolamento/test_*.py` | `docker compose exec -T backend python manage.py test tests.isolamento --noinput` |
| Serializers e views da API | integration | Cada relação gravável da tabela do design: recusa com 400 no campo, corpo idêntico ao de um ID inexistente, nada gravado, e o caminho feliz com o objeto próprio | `tests/isolamento/test_*.py` | `docker compose exec -T backend python manage.py test tests.isolamento --noinput` |
| Services, signals e leituras | integration | Cada soma, lista e detalhe da tabela de leituras do design, com a ligação cruzada gravada à força no banco | `tests/isolamento/test_*.py` | `docker compose exec -T backend python manage.py test tests.isolamento --noinput` |
| Correção de dados (`core/isolation.py`, migração e comando) | integration | Cada linha da tabela de correção do design, os recálculos de ISOL-18, a idempotência e a saída do comando | `tests/isolamento/test_*.py` | `docker compose exec -T backend python manage.py test tests.isolamento --noinput` |
| Configuração do CI | none | - (build gate only) | - | build gate only |

## Gate Check Commands

> Generated from codebase - confirm before Execute. Não há linter configurado: existe um `mypy.ini`, mas o mypy não está nas dependências. O build gate usa o que o CI já roda (compilação e migrações pendentes) mais a suíte inteira.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Depois de cada tarefa com testes da feature | `docker compose exec -T backend python manage.py test tests.isolamento --noinput` |
| Full | Depois das tarefas que mexem em signals, services ou migrações | `docker compose exec -T backend python manage.py test --noinput` |
| Build | No fim de cada fase e nas tarefas só de configuração | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Base

CI, base de testes com dois usuários e o campo de relação do dono.

```
T1 → T2 → T3
```

### Phase 2: Escrita em transações e categorias

```
T4 → T5 → T6
T7
```

### Phase 3: Escrita nas demais relações

```
T8 → T14
T9 → T14
T10 → T14
T11 → T14
T12 → T14
T13 → T14
```

### Phase 4: Leitura restrita ao dono

```
T15 → T16
T17
T18
T19
T20
T25
T26
T27
T28
```

### Phase 5: Correção dos dados existentes

```
T21 → T22 → T23
T22 → T24
```

### Phase 6: Correções da verificação

Lacunas apontadas pelo verificador na primeira rodada.

```
T29 → T30
T31
```

### Phase 7: Correções da segunda verificação

Lacunas apontadas pelo verificador na segunda rodada.

```
T32
T33
T34
T35
```

### Phase 8: Correções da terceira verificação

Lacunas apontadas pelo verificador na terceira rodada; o usuário escolheu corrigir as duas.

```
T36
T37
T38
```

---

## Task Breakdown

### Phase 1: Base

#### T1: Corrigir o CI do backend

**What**: o workflow dispara em push e PR para `main` e `development`, sem filtro de pasta nem `working-directory`, sobe um serviço Postgres 15 e roda compilação, checagem de migrações e `python manage.py test`.
**Where**: `.github/workflows/ci-backend.yml`
**Depends on**: None
**Reuses**: os passos atuais do workflow; o banco do `docker-compose.yml`
**Requirement**: Success Criteria da spec (teste automatizado)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O gatilho cobre `main` e `development` e não tem `paths`
- [x] Os passos rodam na raiz do repositório
- [x] O job tem o serviço `postgres:15` e as variáveis `DB_*`, `SECRET_KEY` e `DEBUG` de teste
- [x] O último passo é `python manage.py test --noinput`
- [x] Build gate passa: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`

**Tests**: none
**Gate**: build
**Status**: ✅ Complete

**Commit**: `ci(backend): roda testes com Postgres em main e development`

---

#### T2: Base de testes com dois usuários

**What**: `tests/isolamento/base.py` com a classe `DoisUsuariosTestCase` (`APITestCase`), que cria os usuários A e B, cada um com conta, cofrinho com meta, cartão com fatura, categoria com subcategoria, tag, orçamento e monitor de foco. Traz também os helpers `como(usuario)` e `assert_mesma_recusa(resp_alheio, resp_inexistente, campo)`. Os pacotes `tests/` e `tests/isolamento/` ganham `__init__.py`.
**Where**: `tests/isolamento/base.py`
**Depends on**: T1
**Reuses**: criação automática de categorias e da conta "Carteira" (`transactions/signals.py:35-73`)
**Requirement**: base para ISOL-01 a ISOL-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_base.py` confere que cada objeto criado pertence ao usuário certo e que A não enxerga nada de B na listagem de contas
- [x] `assert_mesma_recusa` compara status, chaves de erro e mensagens
- [x] Quick gate passa: `docker compose exec -T backend python manage.py test tests.isolamento --noinput`
- [x] Test count: 2 tests pass

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `test(isolamento): cria base de testes com dois usuários`

---

#### T3: Campo de relação do dono

**What**: `OwnedPrimaryKeyRelatedField` e `get_owned_or_400` em `core/fields.py`, com as quatro mensagens em português e a mesma falha para ID de outro usuário, inexistente, categoria-modelo, UUID malformado e tipo errado.
**Where**: `core/fields.py`
**Depends on**: T2
**Reuses**: o padrão de filtro no `__init__` de `transactions/serializers.py:255-279`
**Requirement**: ISOL-10, ISOL-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_campo.py` cobre objeto próprio, de outro usuário, inexistente, categoria-modelo sem dono, UUID malformado, número no lugar do UUID, `many=True` com uma tag alheia no meio e serializer sem `request`
- [x] `get_owned_or_400` devolve o objeto próprio e levanta `{campo: [mensagem]}` nos demais casos
- [x] Quick gate passa
- [x] Test count: 12 tests pass

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(core): adiciona campo de relação que só aceita objetos do usuário`

---

### Phase 2: Escrita em transações e categorias

#### T4: Relações graváveis da transação

**What**: no `TransactionSerializer`, `account`, `credit_card`, `category`, `tags` e `target_account_id` passam a usar `OwnedPrimaryKeyRelatedField`; a troca de conta da parceira no `update` busca a parceira só entre as transações do dono.
**Where**: `transactions/serializers.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-02, ISOL-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_escrita_transacoes.py` cobre criação e edição com cada relação de B: 400 no campo, corpo igual ao de um UUID inexistente, nenhuma transação criada ou alterada e saldo de B intacto
- [x] Uma tag de B entre tags de A recusa a transação inteira
- [x] O caminho feliz com objetos de A continua criando a transação
- [x] Quick gate passa
- [x] Test count: 26 tests pass

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): recusa conta, cartão, categoria e tag de outro usuário`

---

#### T5: Categoria-pai do próprio usuário

**What**: o campo `parent` do `CategorySerializer` passa a usar `OwnedPrimaryKeyRelatedField`, na criação e na edição.
**Where**: `transactions/serializers.py`
**Depends on**: T3, T4
**Reuses**: `core/fields.py`
**Requirement**: ISOL-04, ISOL-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_escrita_categorias.py` cobre pai de B, pai inexistente e pai categoria-modelo, na criação e na edição, com 400 em `parent`, respostas idênticas e nada gravado
- [x] Subcategoria sob categoria própria continua funcionando
- [x] Quick gate passa
- [x] Test count: 33 tests pass

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): recusa categoria-pai de outro usuário`

---

#### T6: Transferência e compra no cartão

**What**: `TransferSerializer` e `CreditCardExpenseSerializer` trocam o filtro manual do `__init__` por `OwnedPrimaryKeyRelatedField`, com as mensagens em português.
**Where**: `transactions/serializers.py`
**Depends on**: T3, T5
**Reuses**: `core/fields.py`
**Requirement**: ISOL-09, ISOL-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_escrita_transferencia_cartao.py` cobre origem de B, destino de B, cartão de B, categoria de B e tag de B, com 400 no campo, respostas idênticas às de UUID inexistente e nenhuma transação criada
- [x] Transferência e compra com objetos de A continuam funcionando
- [x] Quick gate passa
- [x] Test count: 40 tests pass

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): padroniza a recusa de IDs alheios na transferência e na compra no cartão`

---

#### T7: Categoria na edição em lote da série

**What**: o `bulk_update` valida a `category` com `get_owned_or_400` antes do `update()`.
**Where**: `transactions/views.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_escrita_lote.py` cobre categoria de B, inexistente e categoria-modelo: 400 em `category`, respostas idênticas e nenhuma ocorrência da série alterada
- [x] A edição em lote com categoria de A continua funcionando
- [x] Quick gate passa
- [x] Test count: 44 tests pass

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): recusa categoria de outro usuário na edição em lote`

---

### Phase 3: Escrita nas demais relações

#### T8: Categoria do orçamento

**What**: o campo `category` do `BudgetSerializer` passa a usar `OwnedPrimaryKeyRelatedField`.
**Where**: `budgets/serializers.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_escrita_orcamentos.py` cobre criação e edição com categoria de B, inexistente e categoria-modelo, com 400 em `category`, respostas idênticas e nada gravado
- [x] Orçamento com categoria de A continua funcionando
- [x] Quick gate passa
- [x] Test count: 49 tests pass (51 na execução: a fase 2 terminou com 46, e não 44)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(budgets): recusa categoria de outro usuário`

---

#### T9: Conta da meta

**What**: o campo `account` do `GoalSerializer` passa a usar `OwnedPrimaryKeyRelatedField`; na leitura, a meta mostra a conta e os movimentos só quando são do dono da meta.
**Where**: `goals/serializers.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-06, ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_metas.py` cobre criação e edição com conta de B e inexistente, com 400 em `account`, respostas idênticas e nada gravado
- [x] Com uma meta de B ligada à força ao cofrinho de A, B recebe `account` nulo e nenhum movimento do cofrinho de A
- [x] Meta com cofrinho automático e com conta de A continua funcionando
- [x] Quick gate passa
- [x] Test count: 55 tests pass (57 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(goals): recusa e oculta conta de outro usuário na meta`

---

#### T10: Aporte e resgate de meta

**What**: `deposit` e `withdraw` trocam o `get_object_or_404` da conta por `get_owned_or_400`, com o erro no campo que a requisição usou (`account_id`, `account_from` ou `account_to`).
**Where**: `goals/views.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-09, ISOL-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_aporte_resgate.py` cobre aporte e resgate com conta de B e inexistente, em cada nome de campo aceito: 400 no campo, respostas idênticas, nenhum registro de aporte ou transação criado
- [x] Aporte e resgate com conta de A continuam funcionando
- [x] Quick gate passa
- [x] Test count: 63 tests pass (65 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(goals): responde 400 no campo para conta alheia no aporte e no resgate`

---

#### T11: Monitor de foco

**What**: `category` e `tag` do `FocusedMonitorItemSerializer` passam a usar `OwnedPrimaryKeyRelatedField`; `category_name` e `tag_name` só aparecem para objetos do dono do monitor.
**Where**: `reports/serializers.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-07, ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_monitor_foco.py` cobre categoria de B, tag de B e inexistentes, com 400 no campo, respostas idênticas e nada gravado
- [x] Um monitor de A ligado à força à tag de B não mostra o nome da tag
- [x] Quick gate passa
- [x] Test count: 69 tests pass (71 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(reports): recusa categoria e tag de outro usuário no monitor de foco`

---

#### T12: Conta do cartão e do pagamento de fatura

**What**: `account_id` do `CreditCardSerializer` e do `InvoicePaymentSerializer` passa a usar `OwnedPrimaryKeyRelatedField`, mantendo o filtro `is_active=True`; o `account` aninhado do cartão só aparece quando é do dono do cartão.
**Where**: `accounts/serializers.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-08, ISOL-09, ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_cartao_fatura.py` cobre criação e edição de cartão com conta de B e pagamento de fatura com conta de B, com 400 em `account_id`, respostas idênticas e nada gravado
- [x] Um cartão de A ligado à força à conta de B mostra `account` nulo
- [x] Quick gate passa
- [x] Test count: 75 tests pass (77 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(accounts): recusa conta de outro usuário no cartão e no pagamento de fatura`

---

#### T13: Conta da importação

**What**: `ImportOFXView` e `ImportSpreadsheetView` trocam o `get_object_or_404` da conta por `get_owned_or_400`.
**Where**: `data_exchange/views.py`
**Depends on**: T3
**Reuses**: `core/fields.py`
**Requirement**: ISOL-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_importacao.py` envia um OFX e uma planilha com `account_id` de B e inexistente: 400 em `account_id`, respostas idênticas e nenhuma transação criada
- [x] Um mapeamento de contas que aponta para uma conta de B não grava nada na conta de B
- [x] Quick gate passa
- [x] Test count: 80 tests pass (82 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(data_exchange): responde 400 no campo para conta alheia na importação`

---

#### T14: Teste-inventário das relações graváveis

**What**: um teste percorre os serializers de escrita registrados nas rotas da API e falha se algum campo de relação gravável não for `OwnedPrimaryKeyRelatedField`.
**Where**: `tests/isolamento/test_inventario.py`
**Depends on**: T4, T5, T6, T7, T8, T9, T10, T11, T12, T13
**Reuses**: o roteador do DRF em `api/urls.py`
**Requirement**: ISOL-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O teste lista cada serializer e campo verificado e passa com todas as relações convertidas
- [x] Trocar um campo convertido de volta para `PrimaryKeyRelatedField` faz o teste falhar (conferido na tarefa e desfeito)
- [x] Build gate passa
- [x] Test count: 81 tests pass (83 na execução)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `test(isolamento): garante que toda relação gravável confere o dono`

---

### Phase 4: Leitura restrita ao dono

#### T15: Detalhes da transação

**What**: `account_detail`, `category_detail`, `tags_detail` e `related_transaction` do `TransactionSerializer` mostram só objetos do dono da transação.
**Where**: `transactions/serializers.py`
**Depends on**: T4
**Reuses**: `CategorySerializer` e `TagSerializer` para manter o formato da resposta
**Requirement**: ISOL-14, ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_leitura_transacoes.py` grava à força uma transação de A com conta, categoria e tag de B e confere que a resposta não traz nome nem dado de B
- [x] Uma transferência com a parceira forjada em outro usuário não mostra a parceira
- [x] O formato da resposta das transações normais não muda
- [x] Quick gate passa
- [x] Test count: 85 tests pass (87 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): mostra só dados do dono nos detalhes da transação`

---

#### T16: Árvore de categorias

**What**: `get_subcategories` e `parent_name` do `CategorySerializer` consideram só categorias do dono.
**Where**: `transactions/serializers.py`
**Depends on**: T15
**Reuses**: `CategorySerializer`
**Requirement**: ISOL-14, ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_leitura_categorias.py` grava à força uma subcategoria de B sob uma categoria de A e confere que A não a vê na árvore e que B não recebe o nome da categoria de A
- [x] Quick gate passa
- [x] Test count: 87 tests pass (89 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): monta a árvore de categorias só com as do dono`

---

#### T17: Movimentos do cofrinho nas metas

**What**: o signal de metas repassa o movimento do cofrinho só às metas do dono do cofrinho.
**Where**: `goals/signals.py`
**Depends on**: T9
**Reuses**: o signal atual
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_signal_metas.py` liga à força uma meta de B ao cofrinho de A, lança uma transação no cofrinho e confere que nenhum registro de aporte nasce na meta de B, enquanto a meta de A recebe o dela
- [x] Full gate passa: `docker compose exec -T backend python manage.py test --noinput`
- [x] Test count: 89 tests pass (91 na execução)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(goals): repassa movimentos do cofrinho só às metas do dono`

---

#### T18: Saldo da conta e limite do cartão

**What**: `AccountService.get_balance` e `CreditCardService.get_invoice_data` somam só transações do dono da conta e do cartão.
**Where**: `accounts/services.py`
**Depends on**: T12
**Reuses**: as somas atuais
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_saldo_limite.py` grava à força transações de B na conta de A e compras de B no cartão de A e confere que o saldo e o limite disponível de A não mudam
- [x] Full gate passa
- [x] Test count: 91 tests pass (93 na execução)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(accounts): soma no saldo e no limite só transações do dono`

---

#### T19: Relatórios com categoria e tag

**What**: a busca de subcategorias do monitor de foco considera só categorias do usuário, e o relatório de tag trata um `tag_id` malformado como tag inexistente.
**Where**: `reports/services.py`
**Depends on**: T11
**Reuses**: `get_all_child_categories` e `get_tag_insights`
**Requirement**: ISOL-12, ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_relatorios.py` grava à força uma subcategoria de B sob a categoria monitorada por A e confere que o monitor de A não usa essa subcategoria
- [x] O relatório de tag responde 404 igual para tag de B, tag inexistente e `tag_id` malformado
- [x] Quick gate passa
- [x] Test count: 95 tests pass (97 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(reports): considera só categorias e tags do usuário`

---

#### T20: Endereço e filtros com IDs de outro usuário

**What**: testes que fixam o comportamento atual de ISOL-12 e ISOL-13: 404 no endereço e resultado vazio nos filtros de transações, exportação e orçamentos, iguais aos de um ID inexistente.
**Where**: `tests/isolamento/test_endereco_filtros.py`
**Depends on**: None
**Reuses**: `DoisUsuariosTestCase`
**Requirement**: ISOL-12, ISOL-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Leitura, edição e exclusão de conta, cartão, fatura, categoria, tag, transação, orçamento, meta e monitor de B respondem 404, igual a um ID inexistente
- [x] Os filtros `accountId`, `credit_card`, `invoice`, `categoryId` e `tagIds` com IDs de B devolvem a lista vazia na listagem de transações e na exportação, e `category` na listagem de orçamentos
- [x] Se algum caso falhar, o conserto entra nesta tarefa e é descrito no commit
- [x] Build gate passa
- [x] Test count: 113 tests pass (114 na execução)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `test(isolamento): cobre endereço e filtros com IDs de outro usuário`

---

#### T25: Parceira da transferência nos signals

**What**: `sync_transfer_update` e `sync_transfer_delete` atualizam e excluem a parceira só entre as transações do dono da transação editada ou excluída. Acrescentada durante a execução: o lote 1 encontrou esse caminho, que a tabela de leituras do design não listava.
**Where**: `transactions/signals.py`
**Depends on**: None
**Reuses**: os signals atuais
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_signal_transferencia.py` grava à força uma transação de B com o `transfer_id` de uma transferência de A e confere que editar a perna de A não muda data nem valor da transação de B, e que excluir a perna de A não exclui a transação de B
- [x] A parceira de A continua sendo atualizada e excluída junto
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 4 testes (4 novos, 118 na execução)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(transactions): sincroniza só a parceira do dono na transferência`

---

#### T26: Histórico de movimentos da meta

**What**: a rota `history` do `GoalViewSet` devolve só os movimentos cuja conta é do dono da meta, como o `GoalSerializer.deposits` da T9. Acrescentada durante a execução: o lote 2 encontrou essa leitura, que a tabela do design não listava.
**Where**: `goals/views.py`
**Depends on**: None
**Reuses**: o filtro `account__user=goal.user` da T9
**Requirement**: ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_historico_meta.py` grava à força um movimento do cofrinho de A numa meta de B e confere que `GET /api/goals/{meta de B}/history/` não o traz, enquanto os movimentos próprios de B continuam aparecendo
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (2 novos, 120 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(goals): mostra no histórico da meta só movimentos do dono`

---

#### T27: Monitores de foco no relatório avançado

**What**: `get_advanced_charts` monta a lista de monitores só com categoria ou tag do dono do monitor e ignora o monitor ligado a objeto de outro usuário. Acrescentada durante a execução: o lote 3 encontrou essa leitura, que a tabela do design não listava.
**Where**: `reports/services.py`
**Depends on**: None
**Reuses**: o laço atual dos monitores
**Requirement**: ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_relatorio_avancado.py` liga à força um monitor de A à categoria de B e outro à tag de B e confere que `/api/reports/charts/advanced/` não traz nome, ícone nem cor de B, enquanto o monitor próprio de A continua aparecendo
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (2 novos, 122 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(reports): ignora monitores ligados a dados de outro usuário`

---

#### T28: Total da fatura só com compras do dono

**What**: o signal `update_invoice_total` soma só as compras do dono do cartão da fatura. Acrescentada durante a execução: o lote 3 encontrou essa soma, que a tabela do design não listava.
**Where**: `transactions/signals.py`
**Depends on**: None
**Reuses**: a soma atual
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_total_fatura.py` grava à força uma compra de B na fatura de A, salva uma compra de A na mesma fatura e confere que o total guardado soma só as compras de A
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (2 novos, 124 na execução)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(transactions): soma no total da fatura só compras do dono do cartão`

---

### Phase 5: Correção dos dados existentes

#### T21: Verificação das ligações cruzadas

**What**: `find_cross_links(apps)` em `core/isolation.py` lista cada registro ligado a objeto de outro usuário, com tipo, ID, relação e ID do objeto alheio.
**Where**: `core/isolation.py`
**Depends on**: None
**Reuses**: os models das seis apps via `apps.get_model`
**Requirement**: ISOL-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_verificacao.py` grava à força uma ligação de cada linha da tabela de correção do design e confere que cada uma aparece uma vez, com tipo, ID e relação
- [x] Uma base sem ligações cruzadas devolve a lista vazia
- [x] Quick gate passa
- [x] Test count: 115 tests pass (126 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(core): lista ligações entre dados de usuários diferentes`

---

#### T22: Correção das ligações cruzadas

**What**: `fix_cross_links(apps)` em `core/isolation.py` desfaz cada ligação conforme a tabela do design e recalcula o saldo das contas, o total das faturas e o valor das metas afetadas.
**Where**: `core/isolation.py`
**Depends on**: T21
**Reuses**: a fórmula de `AccountService.get_balance` e a soma de `transactions/signals.py:75-93`
**Requirement**: ISOL-17, ISOL-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_correcao.py` confere cada correção da tabela, e depois dela `find_cross_links` devolve a lista vazia
- [x] O saldo guardado da conta que recebia transações de outro usuário bate com SALDO-01, e o total da fatura e o valor da meta afetados batem com os registros restantes
- [x] Rodar a correção duas vezes dá o mesmo resultado
- [x] Os dados sem ligação cruzada não mudam
- [x] Full gate passa
- [x] Test count: 121 tests pass (131 na execução)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat(core): desfaz ligações entre dados de usuários diferentes`

---

#### T23: Comando check_isolation

**What**: `python manage.py check_isolation [--fix]` imprime uma linha por ligação cruzada, só com tipos e IDs, e o total; com `--fix`, corrige e imprime o resumo.
**Where**: `transactions/management/commands/check_isolation.py`
**Depends on**: T22
**Reuses**: `core/isolation.py`
**Requirement**: ISOL-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_comando.py` roda o comando com `call_command` e confere as linhas, o total, a ausência de nomes, valores e e-mails na saída e a correção com `--fix`
- [x] Quick gate passa
- [x] Test count: 124 tests pass (135 na execução)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(transactions): adiciona comando que verifica o isolamento entre usuários`

---

#### T24: Migração de dados da correção

**What**: `transactions/migrations/0007_corrige_isolamento.py` com `RunPython`, que chama `fix_cross_links(apps)` com o registro histórico, e reverso vazio.
**Where**: `transactions/migrations/0007_corrige_isolamento.py`
**Depends on**: T22
**Reuses**: `core/isolation.py`
**Requirement**: ISOL-17, ISOL-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_migracao.py` chama a função da migração com o registro de models sobre ligações gravadas à força e confere que nenhuma sobra
- [x] A migração depende das últimas migrações de `accounts`, `budgets`, `goals` e `reports`
- [x] `makemigrations --check` continua sem mudanças pendentes
- [x] Build gate passa
- [x] Test count: 125 tests pass (138 na execução)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(transactions): corrige ligações entre usuários já gravadas`

---

### Phase 6: Correções da verificação

#### T29: Categoria do orçamento na leitura

**What**: o `BudgetSerializer` mostra `category` e `category_detail` como nulos quando a categoria não é do dono do orçamento, como o `TransactionSerializer` faz desde a T15.
**Where**: `budgets/serializers.py`
**Depends on**: None
**Reuses**: a convenção de leitura da T15
**Requirement**: ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_leitura_orcamentos.py` liga à força um orçamento de A à categoria de B e confere que a listagem e o detalhe não trazem id, nome, ícone nem cor da categoria de B
- [x] O orçamento com categoria própria continua com o mesmo formato
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (141 na execução, +3)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(budgets): oculta categoria de outro usuário na leitura do orçamento`

---

#### T30: Subcategorias no uso do orçamento

**What**: `BudgetService.get_budget_usage` considera só as subcategorias do dono do orçamento.
**Where**: `budgets/services.py`
**Depends on**: T29
**Reuses**: a soma atual
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_uso_orcamento.py` grava à força uma subcategoria de B sob a categoria do orçamento de A, com uma despesa de A nessa subcategoria, e confere que o gasto do orçamento de A não a soma, enquanto a despesa de A numa subcategoria própria continua somando
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (143 na execução, +2)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(budgets): soma no uso do orçamento só subcategorias do dono`

---

#### T31: Edição parcial de transação com ligação cruzada

**What**: a edição de uma transação própria que ainda aponta para conta, cartão, categoria ou tag de outro usuário é recusada, mesmo quando o corpo não traz esse campo, até a ligação ser desfeita (edge case da spec). O erro sai no campo da relação cruzada, com a mensagem de ISOL-11.
**Where**: `transactions/serializers.py`
**Depends on**: None
**Reuses**: as mensagens de `core/fields.py`
**Requirement**: ISOL-02, ISOL-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_edicao_parcial.py` liga à força uma transação de A à conta de B e confere que um PATCH só com `description` responde 400 em `account` com "Conta não encontrada." e não altera a transação; o mesmo para categoria e tag
- [x] Um PATCH que troca a relação cruzada por uma própria é aceito
- [x] Uma transação sem ligação cruzada continua aceitando PATCH parcial
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 4 testes (152 na execução, +9)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(transactions): recusa edição de transação ainda ligada a outro usuário`

---

### Phase 7: Correções da segunda verificação

#### T32: Pagamento e estorno da fatura só com compras do dono

**What**: `pay_invoice` e o estorno em `accounts/services.py` alteram só as compras do dono do cartão da fatura (hoje `invoice.transactions.filter(...)` sem dono, linhas 132 e 236).
**Where**: `accounts/services.py`
**Depends on**: None
**Reuses**: o filtro pelo dono usado nas fases anteriores
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_pagamento_fatura.py` grava à força uma compra de B na fatura de A, paga a fatura e confere que a compra de B continua como estava (status, conta) e que o saldo guardado da conta de A desconta só as compras de A
- [x] O estorno do pagamento não muda a compra de B
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 3 testes (155 na execução, +3)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(accounts): paga e estorna na fatura só compras do dono do cartão`

---

#### T33: Edição de parcelas futuras só do dono

**What**: A edição `ALL_FUTURE` do `TransactionSerializer.update` altera só parcelas do dono da transação editada.
**Where**: `transactions/serializers.py`
**Depends on**: None
**Reuses**: o filtro pelo dono usado nas fases anteriores
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_parcelas_futuras.py` grava à força uma parcela de B na série de A, edita com `update_scope=ALL_FUTURE` e confere que o valor e a categoria da parcela de B não mudam, enquanto as parcelas futuras de A mudam
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (157 na execução, +2)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(transactions): edita em lote só parcelas futuras do dono`

---

#### T34: Importação de orçamentos sem categoria de outro usuário

**What**: `bulk_import` de orçamentos pula o orçamento de origem cuja categoria não é do usuário, contando-o como ignorado.
**Where**: `budgets/views.py`
**Depends on**: None
**Reuses**: o filtro pelo dono usado nas fases anteriores
**Requirement**: ISOL-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_importar_orcamentos.py` liga à força um orçamento de A à categoria de B, importa para outro mês e confere que nenhum orçamento novo aponta para a categoria de B, enquanto os orçamentos de categorias próprias são importados
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (159 na execução, +2)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(budgets): não copia categoria de outro usuário na importação de orçamentos`

---

#### T35: Campo sem requisição recusa categoria-modelo

**What**: Teste do ramo sem `request` do `OwnedPrimaryKeyRelatedField` com a entrada que ele existe para bloquear: categoria-modelo e objeto de qualquer usuário (mutante M13 da segunda verificação).
**Where**: `tests/isolamento/test_campo.py`
**Depends on**: None
**Reuses**: o filtro pelo dono usado nas fases anteriores
**Requirement**: ISOL-10, ISOL-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O teste falha se o ramo sem `request` de `core/fields.py` for removido (conferido na tarefa e desfeito)
- [x] Build gate passa
- [x] Test count: suíte cresce em pelo menos 1 teste (160 na execução, +1)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `test(isolamento): cobre o campo sem requisição com categoria-modelo`

---

### Phase 8: Correções da terceira verificação

#### T36: Nomes de outro usuário nos relatórios

**What**: Os relatórios que mostram nome, ícone ou cor de categoria, tag ou conta a partir das transações do usuário (`reports/services.py:396-419`, `:697`, `:748-749`, `:903-910`, `:1251`, `:1278`) ignoram a relação de outro usuário, como se a transação não tivesse aquela categoria, tag ou conta.
**Where**: `reports/services.py`
**Depends on**: None
**Reuses**: o filtro pelo dono usado nas fases anteriores
**Requirement**: ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_relatorios_nomes.py` liga à força transações de A à categoria, à tag e à conta de B e confere que nenhum dos relatórios dessas linhas traz nome, ícone ou cor de B (entre eles `/api/reports/charts/simple/` e `/api/reports/charts/tag-distribution/`)
- [x] Os totais de A continuam aparecendo com as categorias, tags e contas próprias
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 3 testes (171 na execução, +11)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(reports): ignora nomes de outro usuário nos relatórios`

---

#### T37: Nomes de outro usuário na exportação

**What**: A exportação em PDF e XLS (`data_exchange/services.py:479-480` e `:524-538`) não escreve nome de conta, categoria ou tag de outro usuário.
**Where**: `data_exchange/services.py`
**Depends on**: None
**Reuses**: o filtro pelo dono usado nas fases anteriores
**Requirement**: ISOL-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/isolamento/test_exportacao_nomes.py` liga à força transações de A à conta, à categoria e à tag de B e confere que o XLS exportado não contém os nomes de B, e que o PDF é gerado sem eles
- [x] As transações de A continuam exportadas com os nomes próprios
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (173 na execução, +2)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(data_exchange): não exporta nomes de outro usuário`

---

#### T38: Pagamento de fatura com compra forjada no cartão da vítima

**What**: Casos de teste em que a compra de B aponta para o cartão e a fatura de A, no pagamento e no estorno (mutante N03 da terceira verificação).
**Where**: `tests/isolamento/test_pagamento_fatura.py`
**Depends on**: None
**Reuses**: o filtro pelo dono usado nas fases anteriores
**Requirement**: ISOL-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O teste falha se o filtro de `pay_invoice` trocar o dono do cartão por `credit_card_id=invoice.card_id` (conferido na tarefa e desfeito), e o mesmo para `unpay_invoice`
- [ ] Build gate passa
- [ ] Test count: suíte cresce em pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `test(isolamento): cobre compra forjada no cartão da vítima no pagamento da fatura`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8

Phase 1:  T1 → T2 → T3
Phase 2:  T7 · T4 → T5 → T6
Phase 3:  T8 · T9 · T10 · T11 · T12 · T13 → T14
Phase 4:  T17 · T18 · T19 · T20 · T25 · T26 · T27 · T28 · T15 → T16
Phase 5:  T21 → T22 → T23
          T22 → T24
Phase 6:  T31 · T29 → T30
Phase 7:  T32 · T33 · T34 · T35
Phase 8:  T36 · T37 · T38
```

Execution is strictly sequential - there is no intra-phase parallelism. A single agent (or batch worker) works one task at a time, in order.

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: CI do backend | 1 arquivo de configuração | ✅ Granular |
| T2: Base de testes | 1 módulo de apoio e o teste dele | ✅ Granular |
| T3: Campo de relação | 1 campo e 1 helper no mesmo arquivo | ✅ Granular |
| T4: Relações da transação | 1 serializer | ✅ Granular |
| T5: Categoria-pai | 1 campo | ✅ Granular |
| T6: Transferência e compra no cartão | 2 serializers pequenos no mesmo arquivo, mesma troca | ⚠️ Coeso |
| T7: Edição em lote | 1 endpoint | ✅ Granular |
| T8: Orçamento | 1 campo | ✅ Granular |
| T9: Conta da meta | 1 serializer, escrita e leitura do mesmo campo | ⚠️ Coeso |
| T10: Aporte e resgate | 2 endpoints com a mesma troca | ⚠️ Coeso |
| T11: Monitor de foco | 1 serializer | ✅ Granular |
| T12: Cartão e pagamento de fatura | 2 serializers no mesmo arquivo, mesma troca | ⚠️ Coeso |
| T13: Importação | 2 endpoints com a mesma troca | ⚠️ Coeso |
| T14: Teste-inventário | 1 teste | ✅ Granular |
| T15: Detalhes da transação | 1 serializer | ✅ Granular |
| T16: Árvore de categorias | 1 serializer | ✅ Granular |
| T17: Signal de metas | 1 função | ✅ Granular |
| T18: Saldo e limite | 2 funções no mesmo arquivo, mesmo filtro | ⚠️ Coeso |
| T19: Relatórios | 2 funções no mesmo arquivo | ⚠️ Coeso |
| T20: Endereço e filtros | 1 arquivo de testes | ✅ Granular |
| T25: Parceira nos signals | 2 signals no mesmo arquivo, mesmo filtro | ⚠️ Coeso |
| T26: Histórico da meta | 1 endpoint | ✅ Granular |
| T27: Relatório avançado | 1 função | ✅ Granular |
| T28: Total da fatura | 1 signal | ✅ Granular |
| T21: Verificação | 1 função | ✅ Granular |
| T22: Correção | 1 função | ✅ Granular |
| T23: Comando | 1 comando | ✅ Granular |
| T24: Migração | 1 migração | ✅ Granular |
| T29: Leitura do orçamento | 1 serializer | ✅ Granular |
| T30: Uso do orçamento | 1 função | ✅ Granular |
| T31: Edição parcial | 1 serializer | ✅ Granular |
| T32: Pagamento e estorno | 2 funções no mesmo arquivo, mesmo filtro | ⚠️ Coeso |
| T33: Parcelas futuras | 1 método | ✅ Granular |
| T34: Importação de orçamentos | 1 endpoint | ✅ Granular |
| T35: Campo sem requisição | 1 teste | ✅ Granular |
| T36: Nomes nos relatórios | várias funções no mesmo arquivo, mesmo filtro | ⚠️ Coeso |
| T37: Nomes na exportação | 2 funções no mesmo arquivo | ⚠️ Coeso |
| T38: Teste da fatura | 1 arquivo de testes | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | início da fase 1 | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T3 (fase 1) | início da fase 2 | ✅ Match |
| T5 | T3 (fase 1), T4 | T4 → T5 | ✅ Match |
| T6 | T3 (fase 1), T5 | T5 → T6 | ✅ Match |
| T7 | T3 (fase 1) | isolada na fase 2 | ✅ Match |
| T8 a T13 | T3 (fase 1) | cada uma → T14 | ✅ Match |
| T14 | T4 a T7 (fase 2), T8 a T13 | T8, T9, T10, T11, T12, T13 → T14 | ✅ Match |
| T15 | T4 (fase 2) | início da fase 4 | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |
| T17 | T9 (fase 3) | isolada na fase 4 | ✅ Match |
| T18 | T12 (fase 3) | isolada na fase 4 | ✅ Match |
| T19 | T11 (fase 3) | isolada na fase 4 | ✅ Match |
| T20 | None | isolada na fase 4 | ✅ Match |
| T25 | None | isolada na fase 4 | ✅ Match |
| T26 | None | isolada na fase 4 | ✅ Match |
| T27 | None | isolada na fase 4 | ✅ Match |
| T28 | None | isolada na fase 4 | ✅ Match |
| T21 | None | início da fase 5 | ✅ Match |
| T22 | T21 | T21 → T22 | ✅ Match |
| T23 | T22 | T22 → T23 | ✅ Match |
| T24 | T22 | T22 → T24 | ✅ Match |
| T29 | None | início da fase 6 | ✅ Match |
| T30 | T29 | T29 → T30 | ✅ Match |
| T31 | None | isolada na fase 6 | ✅ Match |
| T32 a T35 | None | isoladas na fase 7 | ✅ Match |
| T36 a T38 | None | isoladas na fase 8 | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: CI do backend | Configuração do CI | none | none | ✅ OK |
| T2: Base de testes | Base de testes | integration | integration | ✅ OK |
| T3: Campo de relação | Campo de relação e helper | integration | integration | ✅ OK |
| T4 a T6: Serializers de transações e categorias | Serializers da API | integration | integration | ✅ OK |
| T7: Edição em lote | Views da API | integration | integration | ✅ OK |
| T8, T9, T11, T12: Serializers | Serializers da API | integration | integration | ✅ OK |
| T10, T13: Views | Views da API | integration | integration | ✅ OK |
| T14: Inventário | Teste | integration | integration | ✅ OK |
| T15, T16: Leitura nos serializers | Serializers da API | integration | integration | ✅ OK |
| T17 a T19: Signal e services | Services, signals e leituras | integration | integration | ✅ OK |
| T20: Endereço e filtros | Views da API | integration | integration | ✅ OK |
| T25: Signals da transferência | Services, signals e leituras | integration | integration | ✅ OK |
| T26: Histórico da meta | Views da API | integration | integration | ✅ OK |
| T27: Relatório avançado | Services, signals e leituras | integration | integration | ✅ OK |
| T28: Total da fatura | Services, signals e leituras | integration | integration | ✅ OK |
| T21, T22: Verificação e correção | Correção de dados | integration | integration | ✅ OK |
| T23: Comando | Correção de dados | integration | integration | ✅ OK |
| T24: Migração | Correção de dados | integration | integration | ✅ OK |
| T29: Leitura do orçamento | Serializers da API | integration | integration | ✅ OK |
| T30: Uso do orçamento | Services, signals e leituras | integration | integration | ✅ OK |
| T31: Edição parcial | Serializers da API | integration | integration | ✅ OK |
| T32: Pagamento e estorno | Services, signals e leituras | integration | integration | ✅ OK |
| T33: Parcelas futuras | Serializers da API | integration | integration | ✅ OK |
| T34: Importação de orçamentos | Views da API | integration | integration | ✅ OK |
| T35: Campo sem requisição | Campo de relação e helper | integration | integration | ✅ OK |
| T36: Nomes nos relatórios | Services, signals e leituras | integration | integration | ✅ OK |
| T37: Nomes na exportação | Services, signals e leituras | integration | integration | ✅ OK |
| T38: Teste da fatura | Services, signals e leituras | integration | integration | ✅ OK |
