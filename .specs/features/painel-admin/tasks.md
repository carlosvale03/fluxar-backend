# Painel admin Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/painel-admin/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Log de auditoria, senha do administrador, limpeza, exclusão, dashboard e estatísticas (backend) | integration | Cada AC com status, código e mensagem exatos; Cloudinary simulado; concorrência com `TransactionTestCase` e duas threads | `tests/painel_admin/test_*.py` | `docker compose exec -T backend python manage.py test tests.painel_admin --noinput` |
| Dashboard, configurações, log, lista e detalhe do usuário (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/painel-admin/*.test.tsx` | `npx vitest run tests/painel-admin` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 166 erros de lint antigos: o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.painel_admin --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/painel_admin` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Log de auditoria

```
T1 → T2
T2 → T3
T3 → T4
```

### Phase 2: Operações sobre usuários

```
T5 → T6
T6 → T7
T7 → T8
```

### Phase 3: Dashboard e estatísticas

```
T9 → T10
T10 → T11
```

### Phase 4: Telas do painel

```
T12 → T13
T13 → T14
T14 → T15
T15 → T16
T16 → T17
```

---

## Task Breakdown

### Phase 1: Log de auditoria

#### T1: Log de auditoria estruturado

**What**: `SystemLog` ganha `admin_ref`, `usuario_email`, `antes` e `depois`; `api/auditoria.py` com `Acoes` e `registrar`; `SystemLogSerializer` devolve `admin_id`, `admin_email`, `user_id`, `user_email`, `before` e `after`; `excluir_definitivamente` limpa também o `usuario_email` dos registros mantidos.
**Where**: `api/models.py`, `api/migrations/`, `api/auditoria.py` (novo), `api/serializers.py`, `api/exclusao.py`
**Depends on**: None
**Reuses**: `_mask_email`
**Requirement**: ADMIN-10, ADMIN-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `registrar` grava o `admin_ref`, o `usuario_ref`, os dois e-mails mascarados, a ação e os valores de antes e depois
- [x] Nenhum registro gravado por `registrar` contém o nome nem o e-mail completo do administrador ou do usuário
- [x] Depois da exclusão definitiva do usuário, os registros sobre ele continuam com o `usuario_ref` e sem o `usuario_email`
- [x] A API do log devolve os campos novos
- [x] Build gate passa
- [x] Test count: 5 testes

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat: guarda no log de auditoria quem fez, sobre quem e os valores de antes e depois`

---

#### T2: Log das ações sobre usuários

**What**: Mudança de plano, papel e status (individual e em lote), redefinição de senha e exclusão pelo admin (as duas rotas) passam por `registrar`, um registro por campo alterado; a exclusão grava `DELETE_ACCOUNT` antes de excluir.
**Where**: `api/views.py`
**Depends on**: T1
**Reuses**: `registrar`
**Requirement**: ADMIN-08, ADMIN-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Mudar o plano de COMMON para PREMIUM grava `CHANGE_PLAN` com `before` "COMMON" e `after` "PREMIUM"
- [x] Mudar plano e papel juntos grava dois registros; campo sem mudança não gera registro
- [x] Arquivar em lote grava `CHANGE_STATUS` para cada usuário
- [x] Redefinir a senha grava `RESET_PASSWORD` sem a senha
- [x] A exclusão pelas duas rotas grava `DELETE_ACCOUNT`, que continua no log do usuário depois da exclusão
- [x] Quick gate passa
- [x] Test count: 9 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: registra no log toda ação do administrador sobre um usuário`

---

#### T3: Log das configurações

**What**: Modo manutenção, liberação para testes, travas e limites dos planos passam por `registrar`, só quando o valor muda, com antes e depois.
**Where**: `api/views.py`
**Depends on**: T2
**Reuses**: `registrar`, `gravar_liberacao`, `gravar_trava`
**Requirement**: ADMIN-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Ligar o modo manutenção grava `UPDATE_MAINTENANCE` com `before` falso e `after` verdadeiro
- [x] Gravar o mesmo valor do modo manutenção não gera registro
- [x] Liberação para testes, travas e limites gravam o antes e o depois nos campos novos
- [x] Full gate passa
- [x] Test count: 6 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat: registra no log as mudanças das configurações com o valor de antes`

---

#### T4: Consulta do log

**What**: `GET /admin/logs/` filtra por `action`, `admin`, `inicio` e `fim`; o log do usuário funciona depois da exclusão; escrita nas rotas do log recebe 405.
**Where**: `api/views.py`
**Depends on**: T3
**Reuses**: `PaginacaoPadrao`, `ParametrosConhecidosMixin`
**Requirement**: ADMIN-12, ADMIN-13, ADMIN-14, ADMIN-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cada filtro, sozinho e combinado, devolve só os registros que o atendem, do mais recente para o mais antigo
- [x] O período inclui os dois dias; data inválida recebe 400 no campo
- [x] O log de um usuário excluído continua consultável pelo identificador
- [x] `POST`, `PUT`, `PATCH` e `DELETE` nas duas rotas do log recebem 405
- [x] Quick gate passa
- [x] Test count: 9 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: filtra o log de auditoria por ação, administrador e período`

---

### Phase 2: Operações sobre usuários

#### T5: Senha do administrador

**What**: `conferir_senha_do_admin` com 403 `{admin_password: ["Senha do administrador incorreta."]}`; senha exigida para excluir, arquivar, limpar, redefinir a senha, mudar o papel e desativar; mudar só o plano e reativar não pedem; `AdminUserSerializer` só com `plan`, `role` e `is_active` graváveis.
**Where**: `api/views.py`, `api/serializers.py`
**Depends on**: T4
**Reuses**: `recusar_remocao_de_admin`
**Requirement**: ADMIN-17, ADMIN-18, ADMIN-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Mudar só o plano sem senha responde 200
- [x] Mudar o papel, desativar, arquivar, limpar, redefinir a senha e excluir sem senha ou com a senha errada recebem 403 com a mensagem no campo `admin_password`
- [x] Nome e preferências enviados pelo painel são ignorados
- [x] Full gate passa
- [x] Test count: 14 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix: pede a senha do administrador só nas ações sensíveis e não na troca de plano`

---

#### T6: Padrão do cadastro numa função

**What**: `transactions/padrao.py` com `criar_padrao_do_cadastro(usuario)`; o sinal do cadastro passa a chamá-la.
**Where**: `transactions/padrao.py` (novo), `transactions/signals.py`
**Depends on**: T5
**Reuses**: `DEFAULT_CATEGORIES`
**Requirement**: ADMIN-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Um cadastro novo recebe as mesmas categorias, subcategorias e a conta Carteira de antes
- [x] Chamar a função num usuário sem dados cria o mesmo padrão
- [x] Quick gate passa
- [x] Test count: 3 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `refactor: junta numa função o que um cadastro novo recebe`

---

#### T7: Limpeza tudo ou nada

**What**: `api/limpeza.py` com `MANTIDOS_NA_LIMPEZA`, `LimpezaFalhou` e `limpar_dados` (Cloudinary das metas primeiro, trava do usuário, apaga a lista derivada, recria o padrão); a view recusa o próprio administrador com 400, grava `CLEAR_DATA`, devolve as estatísticas novas e transforma `LimpezaFalhou` em 503 `clear_failed`.
**Where**: `api/limpeza.py` (novo), `api/exclusao.py`, `api/views.py`
**Depends on**: T6
**Reuses**: `MODELOS_DO_USUARIO`, `_remover_do_cloudinary`, `criar_padrao_do_cadastro`
**Requirement**: ADMIN-21, ADMIN-22, ADMIN-23, ADMIN-24, ADMIN-25, ADMIN-26, ADMIN-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Limpar um usuário com 300 transações, cartão com fatura paga, metas, orçamentos, tags e recorrências deixa só as categorias padrão e a Carteira
- [ ] Login, senha, perfil, plano e papel continuam; o usuário entra depois da limpeza
- [ ] As imagens das metas são removidas no Cloudinary; com o Cloudinary falhando, a resposta é 503 e nada é apagado
- [ ] Com uma falha forçada depois de apagar parte dos dados, as 300 transações continuam lá
- [ ] Duas limpezas simultâneas terminam com um único conjunto padrão
- [ ] Limpar os próprios dados recebe 400
- [ ] Todo modelo de `MODELOS_DO_USUARIO` está apagado ou em `MANTIDOS_NA_LIMPEZA`
- [ ] Full gate passa
- [ ] Test count: pelo menos 8 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix: limpa os dados do usuário tudo ou nada e recria o padrão do cadastro`

---

#### T8: Exclusão pelo admin com todos os dados

**What**: Teste de ponta a ponta da exclusão pelo admin de um usuário com compra parcelada no cartão, fatura paga, transferência e metas com aportes; corrige o que falhar.
**Where**: `tests/painel_admin/`, `api/exclusao.py` se preciso
**Depends on**: T7
**Reuses**: `excluir_definitivamente`
**Requirement**: ADMIN-28

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A exclusão termina com 200 e nenhum dado do usuário no banco
- [ ] Fica o `RegistroDeExclusao` com `executada_por` ADMIN e o `DELETE_ACCOUNT` no log
- [ ] Build gate passa
- [ ] Test count: pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `test: confere a exclusão pelo admin de um usuário com cartão, parcelas, transferências e metas`

---

### Phase 3: Dashboard e estatísticas

#### T9: Dashboard e saúde sem dados fixos

**What**: `AdminStatsView` devolve `total_users`, `users_by_plan`, `paid_users_percentage`, `recent_users`, `health` e `version`, sem receita; `VERSAO_DO_SISTEMA` por `APP_VERSION` ou `RENDER_GIT_COMMIT`; `DEPLOY.md` e `.env.example` com `APP_VERSION`.
**Where**: `api/views.py`, `core/settings.py`, `DEPLOY.md`, `.env.example`, `tests/contratos/test_dinheiro.py`
**Depends on**: T8
**Reuses**: medição de latência atual
**Requirement**: ADMIN-02, ADMIN-03, ADMIN-05, ADMIN-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A resposta tem a contagem de cada plano e a porcentagem de planos pagos, e não tem `estimated_revenue` nem `conversion_rate`
- [ ] A saúde traz a latência e a versão do banco medidas na hora; com `DatabaseError`, o banco vem "error" e a latência nula
- [ ] `version` vem de `APP_VERSION`; sem ela, dos 7 primeiros caracteres de `RENDER_GIT_COMMIT`; sem as duas, "desenvolvimento"
- [ ] Nenhum "Operacional" nem "1.2.5" fixo na resposta
- [ ] Full gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix: mostra no dashboard do admin só números medidos, sem receita estimada`

---

#### T10: Estatísticas financeiras pelas regras

**What**: `get_user_financial_stats` usa `reports/regras.py`, `report_date`, `core.datas.hoje` e só as contas ativas.
**Where**: `reports/services.py`
**Depends on**: T9
**Reuses**: `regras.despesas`, `regras.receitas`
**Requirement**: ADMIN-29

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Receitas e despesas dos 30 dias batem com as do relatório do usuário no mesmo período
- [ ] Ajuste de saldo e transação de conta excluída ficam fora
- [ ] Compra no cartão entra pela data do relatório
- [ ] Quick gate passa
- [ ] Test count: pelo menos 4 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix: calcula as estatísticas do usuário no painel pelas regras dos relatórios`

---

#### T11: Busca de usuários

**What**: Testes da busca por nome ou e-mail com os filtros de plano, papel e status na lista paginada; corrige o que faltar.
**Where**: `api/views.py` se preciso
**Depends on**: T10
**Reuses**: `AdminUserListView`
**Requirement**: ADMIN-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Buscar "maria" com o plano PREMIUM traz só as Marias do Premium
- [ ] A busca acha pelo e-mail
- [ ] Os filtros de papel e de status (arquivados) combinam com a busca
- [ ] Build gate passa
- [ ] Test count: pelo menos 4 testes

**Tests**: integration
**Gate**: build

**Commit**: `test: confere a busca de usuários com os filtros de plano, papel e status`

---

### Phase 4: Telas do painel

#### T12: Dashboard do admin

**What**: Tipos novos em `services/admin.ts`; o dashboard mostra total, cada plano, "Usuários em planos pagos", cadastros recentes e a saúde real.
**Where**: `src/services/admin.ts`, `src/app/(admin)/admin/dashboard/page.tsx`
**Depends on**: T11
**Reuses**: `tratarErro`
**Requirement**: ADMIN-02, ADMIN-05, ADMIN-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O dashboard mostra a contagem de cada plano e o rótulo "Usuários em planos pagos"
- [ ] A saúde mostra a latência e a versão do banco da API, e o banco com erro quando vier "error"
- [ ] Não aparecem "API HEALTH CHECK OK", "ASSINATURAS ATIVAS" nem receita
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix: mostra no dashboard do admin os planos e a saúde medida`

---

#### T13: Configurações sem valores fixos

**What**: A tela de configurações mostra só modo manutenção, liberação para testes e travas, com a saúde e a versão vindas da API.
**Where**: `src/app/(admin)/admin/configuracoes/page.tsx`
**Depends on**: T12
**Reuses**: NONE
**Requirement**: ADMIN-02, ADMIN-03, ADMIN-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A versão mostrada é a da API
- [ ] Não aparecem "Uptime", "PostgreSQL 15.4", "Build" nem "Limpar Cache"
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix: tira das configurações do admin os valores fixos e o botão que não fazia nada`

---

#### T14: Log com filtros e antes e depois

**What**: O log das configurações ganha filtros de ação, administrador e período e a coluna de antes e depois; o log do usuário mostra o antes e o depois.
**Where**: `src/app/(admin)/admin/configuracoes/page.tsx`, `src/app/(admin)/admin/usuarios/[id]/page.tsx`, `src/services/admin.ts`
**Depends on**: T13
**Reuses**: `Paginacao`
**Requirement**: ADMIN-12, ADMIN-13, ADMIN-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Escolher um filtro chama a API com o parâmetro e volta à página 1
- [ ] Cada registro mostra o antes e o depois
- [ ] A navegação entre as páginas continua
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: filtra o log do admin e mostra os valores de antes e depois`

---

#### T15: Detalhe do usuário sem dados falsos

**What**: Falha ao carregar mostra o erro com "Tentar de novo" e todas as ações desabilitadas; a aba "Assinatura" sai e a mudança de plano vai para a visão geral; depois da limpeza a tela usa as estatísticas da API.
**Where**: `src/app/(admin)/admin/usuarios/[id]/page.tsx`
**Depends on**: T14
**Reuses**: `tratarErro`
**Requirement**: ADMIN-01, ADMIN-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Com a API devolvendo 500, a tela mostra o erro, nenhum dado de usuário e nenhum botão de ação habilitado
- [ ] "Tentar de novo" chama a API de novo
- [ ] Não existe aba "Assinatura", nem "#TRX-9902" ou "R$ 29,90"
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix: mostra o erro no detalhe do usuário e tira a aba de assinatura simulada`

---

#### T16: Confirmações com e-mail e senha

**What**: Limpar e excluir mostram o que será apagado e só confirmam com o e-mail digitado igual e a senha; mudar papel, arquivar e redefinir senha pedem a senha; mudar o plano não pede; o erro da senha aparece no campo; vale no detalhe e na lista.
**Where**: `src/app/(admin)/admin/usuarios/[id]/page.tsx`, `src/app/(admin)/admin/usuarios/page.tsx`, `src/services/admin.ts`
**Depends on**: T15
**Reuses**: `tratarErro`
**Requirement**: ADMIN-17, ADMIN-18, ADMIN-19, ADMIN-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Com o e-mail errado, o botão de confirmar limpar e excluir fica desabilitado
- [ ] Mudar o plano envia a requisição sem `admin_password`
- [ ] O 403 `admin_password` aparece no campo da senha
- [ ] Mudar o papel e arquivar pedem a senha
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 5 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `fix: confirma limpar e excluir pelo e-mail do usuário e não pede senha para trocar o plano`

---

#### T17: Lista de usuários

**What**: A lista usa `tratarErro` e envia a busca e os filtros de plano, papel e status na lista paginada.
**Where**: `src/app/(admin)/admin/usuarios/page.tsx`
**Depends on**: T16
**Reuses**: `tratarErro`
**Requirement**: ADMIN-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A busca e os filtros vão como parâmetros e voltam à página 1
- [ ] Erros da lista passam pelo `tratarErro`
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `fix: trata os erros da lista de usuários do admin pelo padrão do app`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T8), lote 2 com a fase 3 (T9 a T11), lote 3 com a fase 4 (T12 a T17).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Log de auditoria estruturado | um componente | ✅ Granular |
| T2: Log das ações sobre usuários | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T3: Log das configurações | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T4: Consulta do log | um componente | ✅ Granular |
| T5: Senha do administrador | um componente | ✅ Granular |
| T6: Padrão do cadastro numa função | um componente | ✅ Granular |
| T7: Limpeza tudo ou nada | um componente | ✅ Granular |
| T8: Exclusão pelo admin com todos os dados | um componente | ✅ Granular |
| T9: Dashboard e saúde sem dados fixos | um componente | ✅ Granular |
| T10: Estatísticas financeiras pelas regras | um componente | ✅ Granular |
| T11: Busca de usuários | um componente | ✅ Granular |
| T12: Dashboard do admin | um componente | ✅ Granular |
| T13: Configurações sem valores fixos | um componente | ✅ Granular |
| T14: Log com filtros e antes e depois | um componente | ✅ Granular |
| T15: Detalhe do usuário sem dados falsos | um componente | ✅ Granular |
| T16: Confirmações com e-mail e senha | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T17: Lista de usuários | um componente | ✅ Granular |

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
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |
| T17 | T16 | T16 → T17 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Log de auditoria estruturado | Backend | integration | integration | ✅ OK |
| T2: Log das ações sobre usuários | Backend | integration | integration | ✅ OK |
| T3: Log das configurações | Backend | integration | integration | ✅ OK |
| T4: Consulta do log | Backend | integration | integration | ✅ OK |
| T5: Senha do administrador | Backend | integration | integration | ✅ OK |
| T6: Padrão do cadastro numa função | Backend | integration | integration | ✅ OK |
| T7: Limpeza tudo ou nada | Backend | integration | integration | ✅ OK |
| T8: Exclusão pelo admin com todos os dados | Backend | integration | integration | ✅ OK |
| T9: Dashboard e saúde sem dados fixos | Backend | integration | integration | ✅ OK |
| T10: Estatísticas financeiras pelas regras | Backend | integration | integration | ✅ OK |
| T11: Busca de usuários | Backend | integration | integration | ✅ OK |
| T12: Dashboard do admin | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T13: Configurações sem valores fixos | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T14: Log com filtros e antes e depois | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T15: Detalhe do usuário sem dados falsos | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T16: Confirmações com e-mail e senha | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T17: Lista de usuários | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
