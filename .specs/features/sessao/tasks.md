# Sessao Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/sessao/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Views, autenticação e middleware (backend) | integration | Cada rota e caminho: sucesso, cada recusa da spec com status e código exatos, e os edge cases | `tests/sessao/test_*.py` | `docker compose exec -T backend python manage.py test tests.sessao --noinput` |
| Serviço de sessões, cookies e estado da manutenção | integration | Todos os ramos; tempo simulado nas validades e no cache de 30 s | `tests/sessao/test_*.py` | idem |
| apiClient, sessão entre abas, contexto e telas (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API, o canal entre abas e os timers simulados | `fluxar-frontend/tests/sessao/*.test.ts(x)` | `npx vitest run tests/sessao` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 166 erros de lint antigos (MAN-04): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.sessao --noinput` |
| Full | Tarefas de backend que mexem em autenticação, settings ou rotas | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/sessao` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `NEXT_PUBLIC_API_URL=http://build-check-placeholder npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Sessões no backend

Modelo, autenticação, cookie e as rotas que abrem, renovam e encerram sessões.

```
T1 → T2
T1 → T3
T2 → T4
T3 → T4
T4 → T5
T5 → T6
T6 → T7
T7 → T8
T8 → T9
```

### Phase 2: Manutenção no backend

```
T10 → T11
T11 → T12
```

### Phase 3: Base da sessão no frontend

```
T13 → T14
T14 → T15
T15 → T16
```

### Phase 4: Contexto, telas e manutenção no frontend

```
T17 → T18
T18 → T19
T19 → T20
```

### Phase 5: Fluxo completo

```
T21
```

---

## Task Breakdown

### Phase 1: Sessões no backend

#### T1: Modelo e serviço de sessões

**What**: Modelo `Sessao` em `api/models.py` com a migração, e `api/sessoes.py` com `criar_sessao`, `renovar`, `encerrar`, `encerrar_outras`, `encerrar_todas` e `sessao_aberta`; tokens com o claim `sid` e acesso de 15 minutos.
**Where**: `api/sessoes.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-07, SESSAO-08, SESSAO-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/sessao/test_servico.py` confere o `sid` e o `jti` nos tokens, o acesso com 15 minutos e a renovação com 7 dias a partir do uso
- [x] `renovar` recusa o token já usado, o de sessão encerrada, o vencido, o de conta desativada e o sem `sid`
- [x] `encerrar_outras` mantém a sessão atual e fecha as demais; `encerrar_todas` fecha todas
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 10 testes (real: 17 testes novos; suíte 306 → 323)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat(api): adiciona sessões com renovação rotativa`

---

#### T2: Autenticação pela sessão

**What**: `core/authentication.py` com `SessaoJWTAuthentication`, que exige o `sid` e a sessão aberta, como classe padrão do DRF.
**Where**: `core/authentication.py`
**Depends on**: T1
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-17, SESSAO-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/sessao/test_autenticacao.py` confere 401 com token de acesso de sessão encerrada ainda dentro da validade, de conta desativada e sem `sid`, e 200 com a sessão aberta
- [x] As suítes existentes continuam passando; as que usam `force_authenticate` não passam pela autenticação e não precisam mudar
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 4 testes (real: 5 testes novos; suíte 323 → 328; nenhum teste existente precisou de ajuste)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat(core): confere a sessão do token a cada requisição`

---

#### T3: Cookie de renovação e origem

**What**: `api/cookies.py` com `gravar_cookie_de_renovacao`, `apagar_cookie_de_renovacao` e `origem_permitida`.
**Where**: `api/cookies.py`
**Depends on**: T1
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-01, SESSAO-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_cookies.py` confere o cookie `fluxar_refresh` com httpOnly, SameSite=Lax, path `/api/auth/`, Secure fora do DEBUG e validade de 7 dias
- [ ] `origem_permitida` aceita o `FRONTEND_URL` e as origens do CORS pelo `Origin` ou pelo `Referer`, e recusa outra origem e a ausência dos dois
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(api): grava o token de renovação em cookie httpOnly`

---

#### T4: Login e verificação abrem a sessão

**What**: O login e o link de verificação passam a usar `criar_sessao`: o `access` no corpo e o token de renovação só no cookie.
**Where**: `api/views.py`
**Depends on**: T2, T3
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_login_sessao.py` confere, no login e na verificação, o `access` no corpo, a ausência de `refresh` no corpo e o cookie gravado
- [ ] As mensagens e códigos da `autenticacao` continuam iguais
- [ ] Full gate passa
- [ ] Test count: suíte cresce em pelo menos 4 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat(api): abre a sessão com cookie no login e na verificação`

---

#### T5: Renovação rotativa

**What**: Rota `POST /api/auth/refresh/` no lugar do `TokenRefreshView`: confere a origem, renova pelo cookie, grava o cookie novo e responde 401 apagando o cookie quando a renovação é recusada.
**Where**: `api/views.py`
**Depends on**: T4
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-04, SESSAO-08, SESSAO-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_renovacao.py` confere o `access` novo e o cookie novo, e 401 ao reapresentar o cookie antigo
- [ ] Sem cookie, com cookie vencido e com sessão encerrada: 401 e cookie apagado
- [ ] De outra origem: 403, sem renovar
- [ ] Full gate passa
- [ ] Test count: suíte cresce em pelo menos 6 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat(api): renova a sessão pelo cookie com rotação`

---

#### T6: Logout

**What**: Rota `POST /api/auth/logout/`: confere a origem, encerra a sessão do cookie e apaga o cookie; responde 204 também sem cookie.
**Where**: `api/urls.py`
**Depends on**: T5
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-04, SESSAO-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_logout.py` confere o 204, o cookie apagado e o 401 ao reapresentar o token de renovação depois
- [ ] Sem cookie: 204; de outra origem: 403 e sessão aberta
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 4 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(api): adiciona o logout que encerra a sessão`

---

#### T7: Troca de senha encerra as outras sessões

**What**: `ChangePasswordView` chama `encerrar_outras` com o `sid` do token atual.
**Where**: `api/views.py`
**Depends on**: T6
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_troca_de_senha.py` com duas sessões: depois da troca na primeira, a primeira continua com 200 e a segunda recebe 401 na próxima requisição e na renovação
- [ ] Senha atual errada não encerra nada
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 3 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix(api): encerra as outras sessões ao trocar a senha`

---

#### T8: Redefinição encerra todas as sessões

**What**: `ResetPasswordView` e `AdminResetPasswordView` chamam `encerrar_todas`.
**Where**: `api/views.py`
**Depends on**: T7
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_redefinicao_sessoes.py` confere que, depois da redefinição por link e da feita pelo administrador, todas as sessões do usuário recebem 401
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 2 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix(api): encerra todas as sessões ao redefinir a senha`

---

#### T9: Desativação e exclusão pelo administrador

**What**: A desativação e o arquivamento pelo administrador chamam `encerrar_todas`; a exclusão apaga as sessões em cascata.
**Where**: `api/views.py`
**Depends on**: T8
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_desativacao.py` confere 401 na próxima requisição e na renovação depois de desativar, arquivar e excluir a conta pelo painel
- [ ] Build gate passa
- [ ] Test count: suíte cresce em pelo menos 3 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix(api): encerra as sessões da conta desativada ou excluída`

---

### Phase 2: Manutenção no backend

#### T10: Estado da manutenção em cache

**What**: `core/manutencao.py` com `manutencao_ligada()` (lê a `GlobalSetting` no máximo a cada 30 segundos por processo) e `invalidar()`, chamado pelo `AdminSystemSettingsView` ao salvar.
**Where**: `core/manutencao.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-24, SESSAO-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_manutencao_cache.py` confere uma única consulta em várias chamadas dentro de 30 segundos (`assertNumQueries`), a leitura nova depois de 30 segundos (tempo simulado) e o efeito imediato de `invalidar()`
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 3 testes

**Tests**: integration
**Gate**: quick

**Commit**: `perf(core): lê o modo manutenção de um cache de 30 segundos`

---

#### T11: Middleware de manutenção

**What**: `api/middleware.py`: com a manutenção ligada, libera login, renovação, `/auth/me/`, logout e health; libera quem tem `role == 'ADMIN'` pelo token de acesso; responde 503 `maintenance_mode` aos demais.
**Where**: `api/middleware.py`
**Depends on**: T10
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-19, SESSAO-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_manutencao.py` confere o 503 com o código para usuário comum numa rota de dados, o 200 nas cinco rotas liberadas e o 200 para o administrador
- [ ] Cadastro, verificação e redefinição recebem 503
- [ ] O token de renovação do usuário comum continua válido durante a manutenção
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `fix(api): deixa os administradores usarem o app na manutenção`

---

#### T12: Health sempre no ar

**What**: `health_check` responde 200 com `{"status": "ok", "maintenance": bool}`.
**Where**: `api/views.py`
**Depends on**: T11
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-23

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/test_manutencao.py` confere 200 com `maintenance: true` e com `maintenance: false`
- [ ] Build gate passa
- [ ] Test count: suíte cresce em pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix(api): mantém o health check no ar durante a manutenção`

---

### Phase 3: Base da sessão no frontend

#### T13: Proxy da API

**What**: `next.config.ts` com `rewrites()` de `/api/:path*` para `${BACKEND_URL}/api/:path*`, e o `apiClient` com `baseURL: '/api'`.
**Where**: `fluxar-frontend/next.config.ts`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/proxy.test.ts` confere o rewrite com `BACKEND_URL` definido e com o padrão `http://localhost:8000`
- [ ] O `apiClient` usa `/api` como base
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `feat(frontend): chama a API pelo proxy do Next.js`

---

#### T14: Token de acesso em memória

**What**: `apiClient` com `definirTokenDeAcesso` e `obterTokenDeAcesso` em memória, sem `localStorage`, e a limpeza de `fluxar.token` e `fluxar.refresh_token` antigos.
**Where**: `fluxar-frontend/src/services/apiClient.ts`
**Depends on**: T13
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-02, SESSAO-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/token-em-memoria.test.ts` confere o `Authorization` com o token em memória e que nada é gravado em `localStorage`, `sessionStorage` ou `document.cookie`
- [ ] A limpeza remove as duas chaves antigas do `localStorage`
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): guarda o token de acesso só na memória da aba`

---

#### T15: Renovação única entre requisições e abas

**What**: `src/lib/sessao-entre-abas.ts` com `renovarSessao()` (Web Locks e BroadcastChannel) e `anunciarFimDaSessao`/`aoFimDaSessao`; o `apiClient` renova uma vez no 401 e refaz cada requisição uma única vez.
**Where**: `fluxar-frontend/src/lib/sessao-entre-abas.ts`
**Depends on**: T14
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-10, SESSAO-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/renovacao.test.ts` confere que três 401 simultâneos geram uma chamada a `/auth/refresh/` e três novas tentativas com o token novo
- [ ] Com o token vindo de outra aba pelo canal, a aba não chama `/auth/refresh/`
- [ ] Renovação recusada com 401 dispara o fim da sessão; requisição refeita que recebe 401 de novo não entra em laço
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `feat(frontend): renova a sessão uma vez só entre requisições e abas`

---

#### T16: Rede e 5xx não encerram a sessão

**What**: `apiClient`: erro de rede, tempo esgotado e 5xx, inclusive na renovação, não disparam o fim da sessão.
**Where**: `fluxar-frontend/src/services/apiClient.ts`
**Depends on**: T15
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/erros-de-rede.test.ts` confere que 502, 503 sem `maintenance_mode`, tempo esgotado e erro de rede na renovação não disparam o fim da sessão
- [ ] Build gate do frontend passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: build (frontend)

**Commit**: `fix(frontend): não encerra a sessão por falha de rede ou do servidor`

---

### Phase 4: Contexto, telas e manutenção no frontend

#### T17: Início da sessão e aviso de conexão

**What**: `AuthProvider` inicia pela renovação e `/auth/me/`, fica no estado de erro sem deslogar quando a falha não é 401, e o componente `aviso-de-conexao.tsx` mostra a mensagem com "Tentar de novo".
**Where**: `fluxar-frontend/src/contexts/auth-context.tsx`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-03, SESSAO-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/auth-context.test.tsx` confere que, com o cookie válido (renovação simulada), o usuário carrega sem ir ao login
- [ ] Com 502 no `/auth/me/`, o aviso aparece, o usuário não é deslogado e "Tentar de novo" recarrega
- [ ] Com renovação 401, a sessão termina
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): inicia a sessão pela renovação e não desloga por erro de conexão`

---

#### T18: Logout em todas as abas

**What**: `logout()` chama `/auth/logout/`, limpa o token, o usuário e o `dashboard_layout_config`, e avisa as outras abas; o aviso vindo de outra aba encerra a sessão local.
**Where**: `fluxar-frontend/src/contexts/auth-context.tsx`
**Depends on**: T17
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-13, SESSAO-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/logout.test.tsx` confere a chamada a `/auth/logout/`, a limpeza do token e do layout e a mensagem no canal
- [ ] A mensagem de outra aba encerra a sessão e leva ao login
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `feat(frontend): encerra a sessão em todas as abas no logout`

---

#### T19: Telas de login e verificação

**What**: `login/page.tsx` e `verify-email/page.tsx` passam a chamar `login(access, user)`, sem token de renovação.
**Where**: `fluxar-frontend/src/app/auth/login/page.tsx`
**Depends on**: T18
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-01, SESSAO-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Os testes de `tests/autenticacao/login.test.tsx` e `verify-email.test.tsx` são atualizados para a nova assinatura e continuam passando
- [ ] `tests/sessao/login-sem-refresh.test.tsx` confere que nenhuma das duas telas grava token no navegador
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 2 testes novos

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): entra sem guardar o token de renovação no navegador`

---

#### T20: Página de manutenção

**What**: O `apiClient` guarda a página atual em `sessionStorage` no 503 `maintenance_mode` e vai para `/manutencao`; a página consulta `/api/health/` a cada 30 segundos e, com `maintenance: false`, volta à página guardada.
**Where**: `fluxar-frontend/src/app/manutencao/page.tsx`
**Depends on**: T19
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: SESSAO-21, SESSAO-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/sessao/manutencao.test.tsx` confere o redirecionamento com a página guardada e sem fim da sessão, e a volta depois de uma consulta com `maintenance: false` (timers simulados)
- [ ] Build gate do frontend passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: build (frontend)

**Commit**: `feat(frontend): volta sozinho da página de manutenção`

---

### Phase 5: Fluxo completo

#### T21: Fluxo de sessão de ponta a ponta pela API

**What**: `tests/sessao/test_fluxo_completo.py`: login em dois clientes, renovação com rotação, reuso recusado, troca de senha num cliente derrubando o outro, logout e manutenção com usuário comum e administrador.
**Where**: `tests/sessao/test_fluxo_completo.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: Success Criteria

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O teste percorre o fluxo sem passo manual e confere cada resposta pelo status e código da spec
- [ ] Build gate passa
- [ ] Test count: suíte cresce em pelo menos 1 teste

**Tests**: integration
**Gate**: build

**Commit**: `test(sessao): cobre o fluxo completo de sessão pela API`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

Execution is strictly sequential - there is no intra-phase parallelism.

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Modelo e serviço de sessões | 1 modelo, 1 migração e 1 serviço | ⚠️ Coeso |
| T2: Autenticação pela sessão | 1 arquivo | ✅ Granular |
| T3: Cookie de renovação e origem | 1 arquivo | ✅ Granular |
| T4: Login e verificação abrem a sessão | 1 arquivo | ✅ Granular |
| T5: Renovação rotativa | 1 arquivo | ✅ Granular |
| T6: Logout | 1 arquivo | ✅ Granular |
| T7: Troca de senha encerra as outras sessões | 1 arquivo | ✅ Granular |
| T8: Redefinição encerra todas as sessões | 2 views com a mesma chamada | ⚠️ Coeso |
| T9: Desativação e exclusão pelo administrador | 3 caminhos do admin | ⚠️ Coeso |
| T10: Estado da manutenção em cache | 1 arquivo | ✅ Granular |
| T11: Middleware de manutenção | 1 middleware | ⚠️ Coeso |
| T12: Health sempre no ar | 1 arquivo | ✅ Granular |
| T13: Proxy da API | 1 arquivo | ✅ Granular |
| T14: Token de acesso em memória | 1 arquivo | ✅ Granular |
| T15: Renovação única entre requisições e abas | 1 módulo e o uso no apiClient | ⚠️ Coeso |
| T16: Rede e 5xx não encerram a sessão | 1 arquivo | ✅ Granular |
| T17: Início da sessão e aviso de conexão | 1 arquivo | ✅ Granular |
| T18: Logout em todas as abas | 1 arquivo | ✅ Granular |
| T19: Telas de login e verificação | 2 telas com a mesma troca | ⚠️ Coeso |
| T20: Página de manutenção | 1 página e o redirecionamento no apiClient | ⚠️ Coeso |
| T21: Fluxo de sessão de ponta a ponta pela API | 1 arquivo | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T1 | T1 → T3 | ✅ Match |
| T4 | T2, T3 | T2 → T4, T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | None | sem seta dentro da fase | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | None | sem seta dentro da fase | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |
| T17 | None | sem seta dentro da fase | ✅ Match |
| T18 | T17 | T17 → T18 | ✅ Match |
| T19 | T18 | T18 → T19 | ✅ Match |
| T20 | T19 | T19 → T20 | ✅ Match |
| T21 | None | sem seta dentro da fase | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Modelo e serviço de sessões | Backend | integration | integration | ✅ OK |
| T2: Autenticação pela sessão | Backend | integration | integration | ✅ OK |
| T3: Cookie de renovação e origem | Backend | integration | integration | ✅ OK |
| T4: Login e verificação abrem a sessão | Backend | integration | integration | ✅ OK |
| T5: Renovação rotativa | Backend | integration | integration | ✅ OK |
| T6: Logout | Backend | integration | integration | ✅ OK |
| T7: Troca de senha encerra as outras sessões | Backend | integration | integration | ✅ OK |
| T8: Redefinição encerra todas as sessões | Backend | integration | integration | ✅ OK |
| T9: Desativação e exclusão pelo administrador | Backend | integration | integration | ✅ OK |
| T10: Estado da manutenção em cache | Backend | integration | integration | ✅ OK |
| T11: Middleware de manutenção | Backend | integration | integration | ✅ OK |
| T12: Health sempre no ar | Backend | integration | integration | ✅ OK |
| T13: Proxy da API | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T14: Token de acesso em memória | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T15: Renovação única entre requisições e abas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T16: Rede e 5xx não encerram a sessão | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T17: Início da sessão e aviso de conexão | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T18: Logout em todas as abas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T19: Telas de login e verificação | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T20: Página de manutenção | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T21: Fluxo de sessão de ponta a ponta pela API | Backend | integration | integration | ✅ OK |
