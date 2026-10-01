# Sessao Validation

## Validation: sessao (rodada 2, tier leve) - PASS ✅

**Date**: 2026-09-30
**Spec**: `.specs/features/sessao/spec.md`
**Diff range (backend)**: `development..HEAD` na branch `fix/sessao`, `c91710b..74db362` (23 commits, de `4fa24d6` design e tasks até `74db362` health com `maintenance: null`). Sem mudança desde a rodada 1.
**Diff range (frontend)**: `development..HEAD` na branch `fix/sessao`, `d54c20c..bfa0144` (11 commits, de `5afb2ff` proxy até `bfa0144`, a correção da G1).
**Verifier**: sub-agente independente (autor ≠ verificador), evidence-or-zero, tier leve a pedido do usuário. A rodada 1 rodou o lote completo de 8 mutações. A rodada 2 reverificou só a SESSAO-14, com 3 mutações focadas na correção.

Resumo: a rodada 1 terminou com o veredito de reprovação por uma lacuna real (G1, SESSAO-14). Quando a renovação era recusada com 401 durante o uso, a aba encerrava a própria sessão, mas não avisava as outras abas. O commit `bfa0144` do frontend corrige isso. O ouvinte de `aoSessaoEncerrada` no `AuthProvider` agora chama `anunciarFimDaSessao()` uma vez só por sessão, e o teste da recusa durante o uso confere que sai exatamente um aviso `{ tipo: "fim" }` com duas recusas seguidas. Os gates passam nos dois repositórios (384 testes no backend, 75 no frontend, lint com os mesmos 164 erros por regra) e o sensor desta rodada matou as 3 mutações. Agora as 25 ACs têm evidência completa. G2, G3 e G4 continuam como lacunas de precisão da spec, sem bloquear.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T21 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md`. O T21 (fluxo completo pela API) corresponde a `9b02f3b`, e o ajuste pós-lote `74db362` fez o health devolver `maintenance: null` quando a leitura do banco falha |
| Fix 1 (G1) | ✅ Done | `bfa0144` no frontend: `src/contexts/auth-context.tsx` e `tests/sessao/auth-context.test.tsx` |

A matriz de rastreabilidade de `spec.md` continua `Pending`. Pelas regras desta verificação, só este arquivo pode ser alterado no repositório, e o status fica para o orquestrador atualizar.

---

## Gate Check

### Backend (rodada 2)

- **Gate command**: `docker compose exec -T backend python manage.py test --noinput`
- **Exit**: 0, `Ran 384 tests in 98.787s ... OK`. Nada mudou no backend desde a rodada 1, e o número bate.
- **Test count before feature**: 306 (384 menos os 78 de `tests/sessao/`)
- **Test count after feature**: 384
- **Delta**: +78
- **Skipped tests**: nenhum
- **Failures**: nenhuma

Na rodada 1 também rodaram `compileall` e `makemigrations --check --dry-run` (sem erro, "No changes detected"). A integridade dos testes alterados em `tests/autenticacao/` (`test_email_minusculo.py:42`, `test_fluxo_completo.py:95`, `test_login.py:59`, `test_verificacao.py:55`) foi conferida naquela rodada. Eles trocam `resposta.data['refresh']` pelo valor do cookie `fluxar_refresh` e continuam conferindo o `user_id`, sem enfraquecer nada.

### Frontend

| Gate | Rodada 1 (`5c898a8`) | Rodada 2 (`bfa0144`) |
| ---- | -------------------- | -------------------- |
| `npx tsc --noEmit -p . --incremental false` | exit 0 | exit 0 |
| `npm test` | 16 arquivos, 75 testes | 16 arquivos, 75 testes passando (a correção reforçou um teste existente, sem criar outro) |
| `npm run lint` | 166 → 164 erros, nenhuma regra com erro novo | 164 erros, com a mesma contagem por regra: `no-explicit-any` 128, `no-unescaped-entities` 18, `no-var` 4, `prefer-const` 4, `ban-ts-comment` 4, `set-state-in-effect` 3, `no-empty-object-type` 2, `immutability` 1. Em `src/contexts/auth-context.tsx`, só o aviso `react-hooks/exhaustive-deps` da linha 132, que já existia antes da correção (linha 121 em `5c898a8`) |
| `NEXT_PUBLIC_API_URL=http://build-check-placeholder npm run build` | exit 0, 30 páginas | não repetido (a mudança é de lógica do cliente, e o `tsc` passa) |
| `npm audit --omit=dev` | 0 vulnerabilidades | não repetido (sem dependência nova) |

**Integridade do teste alterado em `bfa0144`.** O `CanalFalso` de `tests/sessao/auth-context.test.tsx:25-34` passou a guardar as mensagens enviadas, e o `beforeEach` limpa a lista (`:98`). Nenhuma asserção foi retirada. O teste da recusa durante o uso (`:191-208`) ganhou a linha `:207`.

---

## Spec-Anchored Acceptance Criteria

Caminhos relativos a cada repositório: `tests/sessao/*.py` é o backend e `tests/**/*.ts(x)` é o frontend. As linhas da rodada 1 continuam válidas, porque o `bfa0144` só mexeu em `auth-context.tsx` e no teste dele. As linhas de `tests/sessao/auth-context.test.tsx` foram atualizadas, já que o teste cresceu 3 linhas acima e 2 linhas no fim.

### P1: Onde os tokens ficam

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| SESSAO-01 login, verificação e renovação entregam a renovação em cookie httpOnly, Secure, SameSite, restrito às rotas de sessão, e o acesso no corpo | cookie `httponly`, `secure`, `samesite`, `path` das rotas de sessão; `refresh` fora do corpo | `tests/sessao/test_cookies.py:35-39` - `assertIs(cookie['httponly'], True)`, `cookie['samesite'] == 'Lax'`, `cookie['path'] == '/api/auth/'`, `assertIs(cookie['secure'], True)` (DEBUG=False), `max-age == 7*24*60*60`; `tests/sessao/test_login_sessao.py:29-39` - `assertNotIn('refresh', resposta.data)` e cookie httpOnly com o `sid` e o `jti` da sessão, usado no login (`:63`) e na verificação (`:112`); `tests/sessao/test_renovacao.py:58-63` - `set(resposta.data) == {'access'}` e cookie novo httpOnly | ✅ PASS |
| SESSAO-02 o token de acesso fica só na memória da aba | nada em `localStorage`, `sessionStorage` ou `document.cookie` | `tests/sessao/token-em-memoria.test.ts:29-33` - `localStorage.length` 0, `sessionStorage.length` 0, `document.cookie === ""`, depois de renovar (`:67`); `tests/sessao/login-sem-refresh.test.tsx:93` e `:110` - `legivelPorScript()` não contém o token do login nem o da verificação | ✅ PASS |
| SESSAO-03 a página carregada com o cookie válido renova antes de carregar os dados, sem login | uma renovação antes do `/auth/me/`, que leva o token novo; sem ida ao login | `tests/sessao/auth-context.test.tsx:116-120` - `renovacao` chamado 1 vez com `/api/auth/refresh/`, `enviadas` igual a `[{ url: "/auth/me/", authorization: "Bearer acesso-1" }]`, `push` não chamado | ✅ PASS |
| SESSAO-04 renovação ou logout de outra origem recebe 403 | HTTP 403 | `tests/sessao/test_renovacao.py:94-105` - `status_code == 403`, `code == 'origin_not_allowed'`, sem cookie e com o `jti` intacto, para outra origem e sem origem; `tests/sessao/test_logout.py:97-103` - 403 e sessão aberta; `tests/sessao/test_cookies.py:81-106` - porta, esquema, sufixo de domínio, `null`, `Referer` de outra origem e `Origin` estranho com `Referer` válido são recusados | ✅ PASS |
| SESSAO-05 navegador que bloqueia cookies de terceiros renova normalmente | a renovação funciona no Safari | `tests/sessao/proxy.test.ts:37-40` - `/api/auth/refresh/` vai para `${BACKEND_URL}/api/auth/refresh/` com a barra final e `skipTrailingSlashRedirect === true`; `:51` - `api.defaults.baseURL === "/api"`; `tests/sessao/renovacao.test.ts:118` - a renovação chama `/api/auth/refresh/` na própria origem | ✅ PASS por desenho (ver nota abaixo) |
| SESSAO-06 a nova versão apaga `fluxar.token` e `fluxar.refresh_token` e pede login | as duas chaves somem; outras chaves ficam | `tests/sessao/token-em-memoria.test.ts:95-97` - as duas chaves `toBeNull()` e `fluxar-tema` preservada; `tests/sessao/auth-context.test.tsx:121-122` - apagadas na montagem do `AuthProvider`; `:76` em `token-em-memoria.test.ts` - o token antigo não vai no `Authorization` | ✅ PASS |

**Nota sobre a SESSAO-05.** A evidência é adequada para o que um teste automático consegue provar. Com `baseURL: "/api"` e o rewrite do Next.js, o cookie é gravado pela própria origem da página. Por definição, ele é de primeira parte, e a política de cookies de terceiros do Safari não se aplica. O teste do rewrite confere a regra que o Next.js aplica. O que não dá para provar aqui é o comportamento real da Vercel: se o `Set-Cookie`, o `Origin` e o `Host` atravessam o rewrite externo e se o `BACKEND_URL` existe no build. Esses pontos estão nas notas de deploy. Recomendo um teste manual no Safari no primeiro deploy: entrar, recarregar e continuar logado.

### P1: Duração e renovação

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| SESSAO-07 token de acesso com 15 minutos | `exp - iat == 15 min` | `tests/sessao/test_servico.py:72` - `momento(acesso,'exp') - momento(acesso,'iat') == timedelta(minutes=15)`; também na renovação (`:107`) | ✅ PASS |
| SESSAO-08 o uso emite renovação nova de 7 dias e revoga a usada | `jti` novo gravado, 7 dias a partir do uso, mesma sessão | `tests/sessao/test_servico.py:104-115` - `jti` diferente, `sessao.refresh_jti == renovacao['jti']`, `exp >= antes + 7 dias`, `expira_em` entre antes e depois + 7 dias, `encerrada_em` nulo; `tests/sessao/test_renovacao.py:63-67` | ✅ PASS |
| SESSAO-09 token usado, revogado ou vencido recebe 401 | HTTP 401 | `tests/sessao/test_renovacao.py:44-50` - `status_code == 401`, corpo `session_expired`, cookie apagado (`max-age 0`, mesmo `path`), para token reapresentado (`:76`), ausente (`:79`), vencido (`:85`) e de sessão encerrada (`:90`); `tests/sessao/test_servico.py:119-169` - `SessaoInvalida` para usado, encerrado, vencido, sem uso há 7 dias, conta desativada, sem `sid` e `sid` de outra pessoa | ✅ PASS (com o ⚠️ de precisão G4) |
| SESSAO-10 vários 401 ao mesmo tempo, na aba ou entre abas: uma renovação, cada requisição refeita uma vez, ninguém desloga | 1 renovação; N novas tentativas com o token novo | `tests/sessao/renovacao.test.ts:116-123` - 3 respostas 200, `renovacao` chamado 1 vez, 1 pedido de lock, 6 requisições e as 3 últimas com `Bearer novo`; `:140-142` - token de outra aba usado sem chamar `/auth/refresh/`; `:169` - uma renovação sem Web Locks; `:200-203` - a requisição refeita que recebe 401 de novo não entra em laço | ✅ PASS |
| SESSAO-11 renovação recusada com 401 encerra a sessão e, numa página protegida, leva ao login | sessão encerrada; `push('/auth/login')` | `tests/sessao/renovacao.test.ts:185-187` - erros 401, `fim` chamado, token `null`; `tests/sessao/auth-context.test.tsx:170-173` (no carregamento) e `:202-205` (durante o uso) - `push` chamado 1 vez com `/auth/login`; `:186-187` - a página pública não redireciona | ✅ PASS |
| SESSAO-12 rede, tempo esgotado ou 5xx na renovação ou no `/auth/me` mantêm a sessão e mostram mensagem com "tentar de novo" | sessão mantida; mensagem e botão | `tests/sessao/erros-de-rede.test.ts:89-94` - para 502, 503 sem `maintenance_mode`, tempo esgotado e rede: `fim` não chamado, token mantido, nenhum aviso `fim` e nenhum redirecionamento; `:107-112` - a falha numa requisição comum não renova; `tests/sessao/auth-context.test.tsx:150-161` - aviso "Não conseguimos falar com o servidor.", "Sua sessão continua aberta", sem `push`, layout preservado e "Tentar de novo" carrega o usuário | ✅ PASS (com o ⚠️ de precisão G2) |

### P1: Fim da sessão

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| SESSAO-13 sair revoga a renovação da sessão e apaga o cookie | sessão encerrada; cookie apagado; o token reapresentado recebe 401 | `tests/sessao/test_logout.py:63-70` - 204, cookie com valor vazio, `max-age 0` e `path /api/auth/`; `encerrada(self.sessao)` verdadeiro e a outra sessão aberta; renovar com o token antigo recebe 401 `session_expired`; `:77-83` - o token vencido também encerra a sessão; `tests/sessao/logout.test.tsx:133` - a interface faz `POST /auth/logout/` | ✅ PASS |
| SESSAO-14 fim da sessão na interface (logout, renovação recusada ou revogação) descarta o token, limpa os dados do usuário e encerra a sessão nas outras abas | token nulo; `dashboard_layout_config` removido; aviso `fim` às outras abas nos três gatilhos | **Logout**: `tests/sessao/logout.test.tsx:134-136` - token `null`, layout `null`, `expect(canal().enviadas).toContainEqual({ tipo: "fim" })`; `:147-149` - o mesmo com o `/auth/logout/` sem resposta. **Renovação recusada** (rodada 2): `tests/sessao/auth-context.test.tsx:191-208` - duas requisições recebem 401 com a renovação recusada; `:202-203` - token `null` e layout `null`; `:207` - `expect(mensagensDoCanal.filter((m) => (m as { tipo?: string }).tipo === "fim")).toHaveLength(1)`. **Revogação**: no frontend, a sessão revogada (SESSAO-15 a 18) aparece como 401 na requisição seguida de renovação recusada, e passa pelo mesmo caminho (`src/services/apiClient.ts:130-141`). **Aviso vindo de outra aba**: `tests/sessao/logout.test.tsx:155-165` - encerra a sessão local e `:164` `expect(canal().enviadas).not.toContainEqual({ tipo: "fim" })`. **Código**: `src/contexts/auth-context.tsx:118-124` - o ouvinte de `aoSessaoEncerrada` chama `encerrarSessaoLocal()` e, se `!fimAnunciado.current`, marca a flag e chama `anunciarFimDaSessao()`; `:126` - `aoFimDaSessao(encerrarSessaoLocal)` sem reenviar; flag zerada em `:86` (`carregarUsuario` com o `/auth/me/` aceito) e `:138` (`login`) | ✅ PASS (G1 resolvida) |
| SESSAO-15 troca de senha logado encerra as outras sessões e mantém a atual | outra sessão com 401; atual com 200 | `tests/sessao/test_troca_de_senha.py:49-50` - a outra sessão recebe 401 no `/auth/me/` e na renovação; `:55-56` - a atual recebe 200 nos dois; `:61-64` - a troca recusada não encerra nada; `tests/sessao/test_servico.py:198-201` - as sessões da Bia continuam abertas | ✅ PASS |
| SESSAO-16 redefinição por link ou pelo administrador encerra todas as sessões | todas com 401 | `tests/sessao/test_redefinicao_sessoes.py:43-46` - 401 no `/auth/me/` e na renovação de cada sessão, por link (`:58`) e pelo administrador (`:74`), com a sessão do administrador ainda 200 (`:76`) | ✅ PASS |
| SESSAO-17 desativar ou excluir a conta faz os tokens receberem 401 na próxima requisição | HTTP 401 | `tests/sessao/test_desativacao.py:44-52` - 401 no `/auth/me/` e na renovação, administrador 200, depois de desativar (`:57`), arquivar (`:66`), arquivar em massa (`:75`) e excluir pelas duas rotas (`:84-94`, com a sessão apagada em cascata); `tests/sessao/test_autenticacao.py:45-48` | ✅ PASS |
| SESSAO-18 token de acesso de sessão encerrada por SESSAO-15 ou 16 recebe 401 antes de vencer | HTTP 401 | `tests/sessao/test_autenticacao.py:38-41` - `status_code == 401` dentro da validade; `:50-63` - token sem `sid` e `sid` da vítima num token de outra pessoa recebem 401; `tests/sessao/test_fluxo_completo.py:113` | ✅ PASS |

**Rederivação da SESSAO-14 (rodada 2).**

- **Uma vez por sessão.** No teste `:191-208`, as duas requisições (`/accounts/` e `/goals/`) dividem a mesma renovação recusada (`src/lib/sessao-entre-abas.ts:63-72`). Mesmo assim, cada uma passa pelo `catch` do interceptor (`src/services/apiClient.ts:136-141`) e dispara os ouvintes. O ouvinte roda duas vezes, e a flag segura o segundo aviso. A mutação S2 confirma isso: sem a guarda, saem dois avisos.
- **O aviso de outra aba não é reenviado.** O ouvinte do canal (`auth-context.tsx:126`) chama só `encerrarSessaoLocal`, que não toca no canal (`:107-112`). A mutação S3 confirma isso.
- **A flag volta a zero.** Isso acontece no `login` (`:138`, antes de carregar o usuário) e no início da sessão com o `/auth/me/` aceito (`:86`, em `carregarUsuario`, chamado pelo `iniciarSessao`, pelo `tentarDeNovo` e pelo `login` sem usuário). Assim, uma segunda sessão na mesma aba volta a avisar as outras abas na recusa seguinte. A conferência foi feita pela leitura do código. Nenhum teste faz login de novo depois de uma recusa na mesma montagem (ver Residual Notes).

### P1: Modo manutenção

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| SESSAO-19 não administrador recebe 503 `maintenance_mode`, menos nas cinco rotas | 503 com o corpo exato; as cinco rotas respondem | `tests/sessao/test_manutencao.py:61-63` - `status_code == 503` e `json() == EM_MANUTENCAO` (com `code: 'maintenance_mode'`), com token (`:68`), sem token (`:71`), em cadastro, verificação e redefinição (`:104-117`, sem efeito no banco) e em caminhos que só começam como os liberados (`:120-121`); `:74-92` - login 200, `/auth/me/` 200, renovação 200, logout 204 e health 200 | ✅ PASS |
| SESSAO-20 administrador, reconhecido pelo token, usa o app normalmente | 200 para `role == 'ADMIN'` | `tests/sessao/test_manutencao.py:161-168` - rota de dados 200 e o painel desliga a manutenção; `:123-127` - `is_staff` sem o papel recebe 503; `:129-137` - o administrador rebaixado recebe 503 e a sessão continua. SPEC_DEVIATION (`api/middleware.py:59`): o token recusado recebe 401, e não 503 (`:170-192`, `session_expired` e `token_not_valid`) | ✅ PASS (deviação registrada) |
| SESSAO-21 a interface mostra a página de manutenção ao não administrador, sem encerrar a sessão | vai a `/manutencao`; token mantido; sem fim de sessão | `tests/sessao/manutencao.test.tsx:71-75` - 503, `window.location.href == "/manutencao"`, página guardada `"/transacoes?mes=3"`, `fim` não chamado, token `"acesso-1"`; `tests/sessao/test_manutencao.py:139-153` - a renovação do usuário comum continua válida | ✅ PASS |
| SESSAO-22 desligada a manutenção, volta em até 30 s à página em que estava, logado | consulta a cada 30 s; `replace(página guardada)` | `tests/sessao/manutencao.test.tsx:119-129` - 1 consulta em t=0, nenhuma em 29 s, a segunda em 30 s, `replace("/transacoes?mes=3")` e a chave removida; `:139-141` - com `maintenance: null`, não volta; `:150` - sem página guardada, vai ao `/dashboard` | ✅ PASS (com o ⚠️ de precisão G3) |
| SESSAO-23 `/api/health/` responde 200 com ou sem manutenção | HTTP 200 | `tests/sessao/test_manutencao.py:212-213` - 200 e `{'status':'ok','maintenance':True}`; `:220-221` - 200 e `False`; `:230-235` - sem banco, 200 e `maintenance: None`, com o log só do tipo do erro (AD-019) | ✅ PASS |
| SESSAO-24 ligar ou desligar vale para todas as requisições em até 30 s | releitura no máximo a cada 30 s por processo | `tests/sessao/test_manutencao_cache.py:51-56` - em 29,9 s ainda vale o valor antigo, e em 30,0 s faz 1 consulta e devolve `False`; `:85-88` - salvar pelo painel vale na hora no próprio processo | ✅ PASS |
| SESSAO-25 verifica o estado sem consultar o banco em cada requisição | 1 consulta na janela | `tests/sessao/test_manutencao_cache.py:36-42` - `assertNumQueries(1)` em 4 chamadas dentro de 30 s | ✅ PASS |

**Status**: ✅ 25/25 ACs com evidência completa. As 3 lacunas de precisão da spec (G2, G3 e G4) continuam sinalizadas e não bloqueiam.

---

## Edge Cases

- [x] Duas abas renovam no mesmo instante: `tests/sessao/renovacao.test.ts:126-143` (o token da outra aba é usado sem renovar de novo) e `:116-117` (uma renovação para três 401).
- [x] Sete dias sem abrir o app: `tests/sessao/test_servico.py:142-149` (sessão vencida é recusada) e `tests/sessao/test_renovacao.py:81-85` (cookie vencido recebe 401). Na interface, a recusa leva ao login (`tests/sessao/auth-context.test.tsx:170`).
- [x] Redefinição por link com o usuário em outro aparelho: `tests/sessao/test_redefinicao_sessoes.py:48-58`.
- [x] Administrador rebaixado durante a manutenção: `tests/sessao/test_manutencao.py:129-137` (503 e sessão aberta). Na interface, o 503 leva à página de manutenção sem encerrar a sessão (`tests/sessao/manutencao.test.tsx:64-77`).
- [x] Backend reiniciando durante o deploy: `tests/sessao/erros-de-rede.test.ts:78-113` e `tests/sessao/auth-context.test.tsx:133-162`.
- [x] Cookie apagado pelo usuário: `tests/sessao/test_renovacao.py:78-79` (sem cookie, 401) e `tests/sessao/auth-context.test.tsx:164-174` (401 no carregamento leva ao login).
- [x] Página pública com a sessão vencida: `tests/sessao/auth-context.test.tsx:176-189` (sem redirecionar) e `tests/autenticacao/api-client.test.ts:74-83` (AUTH-41: o 401 de rota pública não renova nem redireciona).
- [x] Várias requisições recusadas seguidas na mesma aba (rodada 2): um aviso só às outras abas (`tests/sessao/auth-context.test.tsx:207`).

---

## Discrimination Sensor

### Rodada 1 (lote completo, 8 mutações)

Scratch isolado: `git worktree add --detach ../fluxar-backend-verif HEAD` e `../fluxar-frontend-verif` (HEAD), com o `node_modules` ligado por junção. Antes das mutações, o scratch sem mudança passou (backend `Ran 78 tests ... OK`, frontend `44 passed`). Cada mutação foi aplicada, testada e revertida com `git checkout -- <arquivo>` no scratch. Backend: `docker run ... python manage.py test tests.sessao --noinput`. Frontend: `npx vitest run tests/sessao tests/autenticacao`.

| # | File:line | Description | Killed? |
| - | --------- | ----------- | ------- |
| B1 | `api/sessoes.py:80` | `renovar` deixa de conferir o `jti` (`or False`), e o token reapresentado é aceito | ✅ Killed (3: `test_renovacao.py` reapresentar, `test_servico.py` já usado, fluxo completo) |
| B2 | `core/authentication.py:21` | `SessaoJWTAuthentication` deixa de conferir o `sid` (`if False:`) | ✅ Killed (8: sessão encerrada, sem `sid`, `sid` da vítima, troca e redefinição de senha, admin encerrado na manutenção, fluxo completo) |
| B3 | `api/sessoes.py:128` | `encerrar_outras` sem o `.exclude(pk=sid_atual)`, encerrando também a sessão atual | ✅ Killed (3: `test_servico.py`, `test_troca_de_senha.py` sessão atual, fluxo completo) |
| B4 | `api/cookies.py:14`, `:25` | cookie com `httponly=False` e `path='/'` | ✅ Killed (12: `test_login_sessao.py`, `test_renovacao.py`, `test_logout.py`, fluxo completo; `test_cookies.py:35,37` confere cada atributo isoladamente) |
| B6 | `api/middleware.py:68` | o middleware deixa passar por `is_staff` em vez de `role == 'ADMIN'` | ✅ Killed (2: `is_staff` sem papel, administrador rebaixado) |
| F1 | `src/lib/sessao-entre-abas.ts:64` | `renovarSessao` sem a promessa única da aba (`if (true)`), com duas renovações | ✅ Killed (2: três 401 simultâneos, sem Web Locks) |
| F2 | `src/services/apiClient.ts:138` | a renovação que falha com 5xx também encerra a sessão | ✅ Killed (2: 502 e 503 sem `maintenance_mode` na renovação) |
| F3 | `src/app/manutencao/page.tsx:22` | a página de manutenção volta com `maintenance !== true` | ✅ Killed (1: estado desconhecido continua na página) |

A mutação sugerida "`origem_permitida` aceita sem Origin e sem Referer" (`api/cookies.py:54`) não entrou no lote, para manter o tier leve em 8 mutações. O caso tem asserção direta em `tests/sessao/test_cookies.py:105-106` e em `tests/sessao/test_renovacao.py:95` (origem `None` deve dar 403).

Uma sondagem extra da rodada 1, que não era mutação, confirmou a G1. Com uma renovação recusada durante o uso, `canal().enviadas` continha só `{ tipo: 'token', … }`.

### Rodada 2 (focada na SESSAO-14, 3 mutações)

Scratch isolado: `git worktree add --detach ../fluxar-frontend-verif HEAD` (em `bfa0144`), com o `node_modules` ligado por junção. Antes das mutações, o scratch sem mudança passou: `npx vitest run tests/sessao` com 8 arquivos e `44 passed`. Cada mutação foi aplicada com `sed`, testada com `npx vitest run tests/sessao` e revertida com `git checkout -- src/contexts/auth-context.tsx`.

| # | File:line | Description | Killed? |
| - | --------- | ----------- | ------- |
| S1 | `src/contexts/auth-context.tsx:122` | o ouvinte da renovação recusada deixa de chamar `anunciarFimDaSessao()` (volta ao estado da G1) | ✅ Killed (1: `auth-context.test.tsx` "renovação recusada durante o uso encerra a sessão uma vez só", com `expected [] to have a length of 1 but got +0`) |
| S2 | `src/contexts/auth-context.tsx:120` | sem a guarda de uma vez só (`if (true)`) | ✅ Killed (1: o mesmo teste, com `expected [ { tipo: 'fim' }, { tipo: 'fim' } ] to have a length of 1 but got 2`) |
| S3 | `src/contexts/auth-context.tsx:126` | o ouvinte de `aoFimDaSessao` reenvia o aviso (`encerrarSessaoLocal(); anunciarFimDaSessao()`) | ✅ Killed (1: `logout.test.tsx` "o aviso de outra aba encerra a sessão e leva ao login, sem chamar o backend nem reenviar o aviso", na asserção `:164`) |

**Sensor depth**: lightweight (tier leve; 8 mutações na rodada 1 e 3 focadas na rodada 2)
**Sensor**: 11/11 killed no total (8/8 na rodada 1, 3/3 na rodada 2) - o sensor passa ✅

**Isolamento (rodada 2)**: a junção do `node_modules` foi desfeita com `rmdir` antes de remover o worktree, e o `node_modules` real continua intacto. Depois vieram `git worktree remove --force ../fluxar-frontend-verif` e `git worktree prune`, e o `git worktree list` mostra só o repositório principal. Não foi usado `git stash`. O `git status --porcelain` do frontend estava vazio antes e depois. No backend, antes desta rodada, já estavam pendentes `.specs/LESSONS.md` e `.specs/lessons.json` (modificados na rodada 1) e este arquivo (não versionado). Depois, mudaram só esses três arquivos.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ Serviço de sessão (`api/sessoes.py`), cookie (`api/cookies.py`), autenticação e cache pequenos e de uso direto. A correção da G1 tem 14 linhas, com um `useRef` e um ouvinte |
| Surgical changes | ✅ Só as views de credenciais e desativação chamam `encerrar_*`, como manda a AD-037. O `bfa0144` mexe só em `auth-context.tsx` e no teste dele |
| No scope creep | ✅ CSP, tela de sessões e unificação de `role`/`is_staff` ficaram de fora, como a spec pede |
| Matches patterns | ✅ Formato de erro do DRF com `detail` e `code` (AD-024), log sem dados (AD-019 em `api/views.py`, health). Comentários com a AC, como no resto do arquivo |
| Spec-anchored outcome check | ✅ 25/25 (SESSAO-14 resolvida na rodada 2) |
| Per-layer Coverage Expectation | ✅ Cada rota tem sucesso e cada recusa com status e código exatos |
| Every test maps to a spec requirement | ✅ Cada arquivo de teste abre com as ACs que cobre |
| Documented guidelines followed | ✅ `CLAUDE.md` do backend e `.specs/STATE.md` (AD-013 a AD-016, AD-019, AD-024, AD-036, AD-037) |

---

## Spec-Precision Gaps

- **G1 - SESSAO-14, a renovação recusada não avisava as outras abas. ✅ Resolvida em `bfa0144`.** Era uma lacuna da implementação, e não da spec. O ouvinte de `aoSessaoEncerrada` no `AuthProvider` (`src/contexts/auth-context.tsx:118-124`) agora chama `anunciarFimDaSessao()` uma vez por sessão. A evidência está em `tests/sessao/auth-context.test.tsx:207`, e as mutações S1, S2 e S3 foram mortas.
- **G2 - SESSAO-12, a mensagem durante o uso.** A spec pede "mostrar uma mensagem com a opção de tentar de novo" quando a renovação ou o `/auth/me` falham. A mensagem com o botão existe e está testada no início da sessão (`AuthGuard` e `AdminGuard`, `tests/sessao/auth-context.test.tsx:150-161`). Quando a renovação falha no meio do uso, por exemplo com 502, a sessão continua (`tests/sessao/erros-de-rede.test.ts:89-94`), mas a mensagem fica por conta do tratamento de erro de cada tela. A spec não diz qual camada mostra a mensagem nesse caso.
- **G3 - SESSAO-22 somada à SESSAO-24.** A página consulta a cada 30 s, e cada processo do backend relê o estado a cada 30 s. O processo que salva o painel invalida o próprio cache na hora. Com mais de um processo do gunicorn (`WEB_CONCURRENCY` maior que 1 no Render), o caso pior chega a cerca de 60 s, e não aos 30 s da SESSAO-22. Com um processo só (o padrão do `entrypoint.sh:22`), vale o limite de 30 s. A spec não diz se os 30 s da SESSAO-22 contam a partir do clique no painel ou a partir de o backend passar a responder `false`.
- **G4 - SESSAO-09, o reuso como sinal de cópia.** A spec recusa o token reapresentado, e as Assumptions dizem que o reuso "indica cópia". A implementação recusa só o token, e a sessão continua aberta para quem tem o token mais novo. Se o ladrão renovar primeiro, ele fica com a sessão, e o usuário legítimo recebe 401 e precisa entrar de novo. A spec não diz se o reuso deve encerrar a sessão inteira, que é a revogação da família de tokens.

---

## Fix Plans

### Fix 1 (G1): a renovação recusada avisa as outras abas (SESSAO-14) - ✅ aplicado e verificado

- **Root cause (rodada 1)**: `src/services/apiClient.ts:138-140` avisava só os ouvintes locais (`aoSessaoEncerrada`). O ouvinte do `AuthProvider`, `encerrarSessaoLocal`, não chamava `anunciarFimDaSessao()`, que só o `logout()` chamava.
- **Applied**: `bfa0144` - ouvinte próprio em `src/contexts/auth-context.tsx:118-124`, com a flag `fimAnunciado` (`:75`), zerada em `:86` e `:138`. O aviso de outra aba continua sem reenviar (`:126`).
- **Verified**: `tests/sessao/auth-context.test.tsx:207` (um aviso só com duas recusas), `tests/sessao/logout.test.tsx:164` (sem reenvio), `tests/sessao/erros-de-rede.test.ts:93` (5xx sem aviso). 75 testes passando, lint igual e as mutações S1 a S3 mortas.
- **Não aplicado (opcional, da rodada 1)**: limpar o `dashboard_layout_config` também na recusa durante o carregamento (`auth-context.tsx:95-98`). Ver Residual Notes.

---

## Residual Notes

**Deploy (conferir no primeiro deploy):**

- **`BACKEND_URL` na Vercel no momento do build.** O `next.config.ts:20` lê a variável quando gera os rewrites. Sem ela, o build aponta para `http://localhost:8000`, e todas as chamadas falham em produção. A variável precisa estar em Production (e em Preview, se houver) antes do build, e um redeploy é necessário depois de criá-la.
- **`NUM_PROXIES` com a Vercel na frente.** O `core/settings.py:205` usa 1 por padrão. Com Vercel mais Render, o `X-Forwarded-For` ganha um salto, e o limite por IP da `autenticacao` pode passar a contar o IP da Vercel. Conferir o `X-Forwarded-For` num log do Render e ajustar a variável.
- **`Origin` e `Host` chegando ao Django pelo rewrite.** O `origem_permitida` (`api/cookies.py:48-61`) exige `Origin` ou `Referer` igual ao `FRONTEND_URL` ou a uma das `CORS_ALLOWED_ORIGINS`. Se o rewrite externo da Vercel não repassar esses cabeçalhos, toda renovação e todo logout recebem 403. Conferir num `POST /api/auth/refresh/` real. Conferir também se o `Set-Cookie` da resposta volta pelo proxy com `Path=/api/auth/` e `Secure`.
- **`ALLOWED_HOSTS`.** Se o rewrite mandar o `Host` da Vercel em vez do do Render, o Django responde 400. Conferir e, se preciso, acrescentar o domínio da Vercel (`core/settings.py:40`).
- **Todos entram de novo uma vez.** Os tokens antigos não têm `sid` e passam a receber 401 (`tests/sessao/test_autenticacao.py:50-54`), e o `localStorage` antigo é apagado na primeira abertura. Avisar os usuários, se for o caso.

**Outros:**

- **Rodada 2, a flag sem teste próprio.** A volta da flag `fimAnunciado` a zero (`auth-context.tsx:86` e `:138`) está correta pela leitura do código, mas nenhum teste faz login de novo na mesma aba depois de uma recusa. Se alguém tirar essas linhas, a segunda sessão da aba deixa de avisar as outras abas na recusa, e a suíte não pega. O impacto é baixo, mas um teste "recusa, login, recusa: dois avisos" fecharia o ponto.
- **Rodada 2, a recusa no carregamento.** Quando a renovação é recusada na montagem (`auth-context.tsx:95-98`), a aba não avisa as outras abas e não limpa o `dashboard_layout_config`. Isso não é fim de sessão na interface, porque a aba ainda não tinha sessão. As outras abas descobrem na próxima requisição: se a sessão foi revogada, o `sid` fechado dá 401, e a renovação também é recusada. Fica como observação, e não como lacuna.
- **Rodada 2, um aviso repetido é inofensivo.** Uma aba que recebeu o `fim` de outra não marca a flag. Se uma requisição pendente dela receber 401 depois, ela avisa de novo. Quem recebe só chama `encerrarSessaoLocal`, que pode repetir sem efeito, e não reenvia o aviso (S3). Por isso não há laço.
- O design prevê, para navegadores sem Web Locks, que "uma renovação recusada logo depois de outra aba renovar tenta de novo uma vez" (`design.md`, Risks). Isso não foi implementado: `src/lib/sessao-entre-abas.ts:53` não tenta de novo. Além disso, o 401 do backend apaga o cookie, e se as respostas chegarem fora de ordem, ele pode apagar o cookie novo que a outra aba acabou de receber. Só afeta navegadores sem Web Locks (Safari anterior ao 15.4), por isso o impacto é baixo. Com a correção da G1, essa recusa também avisa as outras abas, e elas saem juntas. O efeito continua limitado a esses navegadores.
- O painel de manutenção (`AdminSystemSettingsView`) continua autorizando por `IsAdminUser` (`is_staff`), enquanto o middleware usa `role` (AD-016). Um administrador só com `role` passa pela manutenção, mas não consegue desligá-la. O risco é conhecido no design e fica para `permissoes-e-planos`.
- A SPEC_DEVIATION em `api/middleware.py:59` (401 em vez de 503 para o token recusado durante a manutenção) é coerente com a SESSAO-20 e tem teste (`tests/sessao/test_manutencao.py:170-192`). O usuário comum com o token vencido renova (rota liberada), repete o pedido, recebe 503 e vai para a página de manutenção.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| SESSAO-01 a SESSAO-13 | Pending | ✅ Verified |
| SESSAO-14 | Pending (Needs Fix na rodada 1) | ✅ Verified (rodada 2, `bfa0144`) |
| SESSAO-15 a SESSAO-25 | Pending | ✅ Verified |

(O `spec.md` não foi alterado; a atualização fica para o orquestrador.)

---

## Summary

**Overall**: ✅ Ready. A G1 foi corrigida e verificada.

**Spec-anchored check**: 25/25 ACs com evidência; 3 lacunas de precisão da spec sinalizadas (G2, G3, G4), sem bloquear
**Sensor**: 11/11 killed (8 na rodada 1, 3 na rodada 2)
**Gate**: backend 384 OK; frontend tsc 0, 75 testes, lint 164 erros com a mesma contagem por regra (build e audit limpos na rodada 1)

**What works**: cookie httpOnly com rotação e recusa de reuso, revogação por `sid` a cada requisição, troca, redefinição e desativação derrubando as sessões certas, origem conferida em renovação e logout, renovação única entre requisições e abas, rede e 5xx sem logout, fim da sessão avisado às outras abas no logout e na renovação recusada (uma vez só), manutenção com administrador trabalhando, health sempre 200 e cache de 30 s.

**Issues found**: nenhuma que bloqueie. Fica como opcional um teste para a volta da flag a zero (Residual Notes).

**Next steps**: atualizar a matriz de rastreabilidade de `spec.md` e seguir as notas de deploy no primeiro deploy.
