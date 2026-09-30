# Sessao Design

**Spec**: `.specs/features/sessao/spec.md`
**Status**: Approved

---

## Architecture Overview

Cada login cria uma **sessão** no banco. O token de acesso (15 minutos) e o de renovação (7 dias) levam o identificador dela no claim `sid`. A autenticação do DRF passa a conferir, a cada requisição, se a sessão do token ainda está aberta e se a conta está ativa. Isso permite encerrar sessões na hora: logout, troca ou redefinição de senha e desativação.

A renovação é rotativa. A sessão guarda o `jti` do token de renovação atual, e um token já usado é recusado.

O token de renovação vai num cookie httpOnly. Para o cookie ser de primeira parte em qualquer navegador, o frontend passa a chamar a API pelo próprio domínio: o Next.js faz o rewrite de `/api/*` para o Render (escolha do usuário em 2026-09-30).

No frontend:
- o token de acesso fica numa variável do módulo do `apiClient`;
- a renovação usa um lock entre abas (Web Locks) e um canal de mensagens (BroadcastChannel), o que dá uma renovação só para várias requisições e abas;
- erros de rede e 5xx não encerram a sessão.

O modo manutenção sai da consulta ao banco em cada requisição e passa a usar um cache em memória de 30 segundos. O middleware reconhece o administrador pelo token de acesso.

```mermaid
graph TD
    B[Navegador] -->|/api/* mesmo domínio| NX[Next.js na Vercel: rewrite]
    NX --> API[Django no Render]
    API --> MW[Middleware de manutenção: cache 30 s, admin pelo token]
    MW --> AUTH[SessaoJWTAuthentication: sid aberto e conta ativa]
    AUTH --> V[Views]
    L[Login e verificação] --> S[api/sessoes.py: criar, renovar, encerrar]
    R[/auth/refresh/: origem conferida] --> S
    O[/auth/logout/: origem conferida] --> S
    P[Troca e redefinição de senha, admin] --> S
    S --> DB[(Sessao: sid, jti atual, expira_em, encerrada_em)]
    S --> C[Cookie fluxar_refresh httpOnly, Secure, SameSite=Lax, path /api/auth/]
```

### Abordagens consideradas para a revogação

| Abordagem | Como funciona | Decisão |
| --------- | ------------- | ------- |
| **Tabela de sessões própria (escolhida)** | Uma linha por sessão, com o `jti` do token de renovação atual; o token de acesso leva o `sid` | Encerra uma sessão, as outras ou todas com um update, recusa o token de acesso de sessão encerrada (SESSAO-18) e detecta o token de renovação reapresentado |
| Blacklist do SimpleJWT (`token_blacklist`) | Guarda cada token de renovação emitido e os revogados | Não revoga tokens de acesso; "encerrar as outras sessões" exigiria outra tabela de qualquer jeito |
| Carimbo de data na conta (`sessoes_validas_desde`) | Tokens emitidos antes da data são recusados | Não distingue a sessão atual das outras (SESSAO-15), nem permite o logout de uma sessão só |

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --------- | -------- | ---------- |
| `JWTAuthentication` e `RefreshToken`/`AccessToken` do SimpleJWT | pacote | Base da autenticação e dos tokens; o `sid` entra como claim |
| `CustomTokenObtainPairSerializer` | `api/serializers.py` | Mantém as regras de login da `autenticacao`; a emissão dos tokens passa para `api/sessoes.py` |
| `VerifyEmailView`, `ResetPasswordView`, `ChangePasswordView`, `AdminResetPasswordView`, `AdminUserDetailView` | `api/views.py` | Recebem as chamadas de criar ou encerrar sessões |
| `MaintenanceModeMiddleware` e `GlobalSetting` | `api/middleware.py`, `api/models.py` | Reescrito com cache em memória; a chave `maintenance_mode` continua a mesma |
| `apiClient` e `ROTAS_PUBLICAS` | `src/services/apiClient.ts` | Recebe o token em memória, a renovação única e o tratamento de 5xx e 503 |
| `AuthProvider` | `src/contexts/auth-context.tsx` | Inicia a sessão pela renovação e encerra em todas as abas |
| Página de manutenção | `src/app/manutencao/page.tsx` | Passa a consultar o estado e voltar sozinha |
| Testes | `tests/autenticacao/` (back) e `fluxar-frontend/tests/autenticacao/` (front) | Referência de estilo; esta feature usa `tests/sessao/` nos dois |

### Integration Points

| System | Integration Method |
| ------ | ------------------ |
| Vercel | `rewrites()` no `next.config.ts` com destino `${BACKEND_URL}/api/:path*`; `BACKEND_URL` nas variáveis da Vercel |
| Render | Recebe as requisições pelo proxy; `NUM_PROXIES` passa a contar a Vercel na frente |
| Navegador | Cookie de primeira parte, porque a página e `/api` têm a mesma origem |

---

## Components

### Modelo `Sessao` e serviço (`api/models.py` e `api/sessoes.py`)

- **Purpose**: guardar e controlar cada sessão (SESSAO-08, SESSAO-09, SESSAO-13, SESSAO-15 e SESSAO-16).
- **Modelo**: `Sessao(id UUID, user FK, refresh_jti, criada_em, ultimo_uso, expira_em, encerrada_em nullable)`, com índice em `(user, encerrada_em)`.
- **Interfaces**:
  - `criar_sessao(user) -> (access, refresh)`: cria a linha e emite os dois tokens com o `sid`.
  - `renovar(refresh_str) -> (access, refresh)`:
    - valida a assinatura e a validade do token;
    - exige a sessão aberta e não vencida, com o `jti` igual ao atual e a conta ativa;
    - emite um token de renovação novo, com 7 dias contados a partir de agora, e grava o `jti` novo. Qualquer falha levanta `SessaoInvalida`.
  - `encerrar(sid)`, `encerrar_outras(user, sid_atual)` e `encerrar_todas(user)`: gravam `encerrada_em`.
  - `sessao_aberta(sid, user_id) -> bool`: usada pela autenticação.

### Autenticação (`core/authentication.py`)

- **Purpose**: recusar na hora o token de sessão encerrada ou de conta desativada (SESSAO-07, SESSAO-17 e SESSAO-18).
- **Interfaces**:
  - `SessaoJWTAuthentication(JWTAuthentication)`: depois de validar o token, exige o claim `sid` e a sessão aberta, com uma consulta por requisição, o que é aceito na AD-014.
  - Token sem `sid`, que vem das versões antigas, recebe 401.
  - Vira a `DEFAULT_AUTHENTICATION_CLASSES`.
  - `SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']` passa a 15 minutos.

### Cookie e origem (`api/cookies.py`)

- **Purpose**: SESSAO-01 e SESSAO-04.
- **Interfaces**:
  - `gravar_cookie_de_renovacao(response, refresh)`: grava o cookie `fluxar_refresh` com `httponly=True`, `secure=not DEBUG`, `samesite='Lax'`, `path='/api/auth/'` e `max_age` de 7 dias.
  - `apagar_cookie_de_renovacao(response)`.
  - `origem_permitida(request) -> bool`:
    - compara o `Origin` com a origem do `FRONTEND_URL` e as de `CORS_ALLOWED_ORIGINS`;
    - na falta do `Origin`, compara o `Referer`;
    - sem os dois cabeçalhos, a origem é recusada.

### Rotas de sessão (`api/views.py` e `api/urls.py`)

- **Login e verificação** (SESSAO-01):
  - chamam `criar_sessao`;
  - a resposta traz o `access` no corpo e o cookie de renovação, sem o `refresh` no corpo.
- **`POST /api/auth/refresh/`** (SESSAO-04, SESSAO-08 e SESSAO-09):
  - rota nova, no lugar do `TokenRefreshView`;
  - sem origem permitida, responde 403;
  - lê o cookie e chama `renovar`;
  - com sucesso, devolve o `access` no corpo e grava o cookie novo;
  - com `SessaoInvalida`, responde 401 e apaga o cookie.
- **`POST /api/auth/logout/`** (SESSAO-04 e SESSAO-13):
  - rota nova; sem origem permitida, responde 403;
  - encerra a sessão do cookie, se houver, e apaga o cookie;
  - responde 204 também sem cookie, para o logout ser idempotente.
- **Encerramento de sessões**:
  - `ChangePasswordView` chama `encerrar_outras` com o `sid` do token atual (SESSAO-15);
  - `ResetPasswordView` e `AdminResetPasswordView` chamam `encerrar_todas` (SESSAO-16);
  - a desativação e a exclusão pelo administrador chamam `encerrar_todas`. A exclusão também apaga as sessões em cascata, e a autenticação já recusa conta inativa (SESSAO-17).

### Modo manutenção (`core/manutencao.py`, `api/middleware.py` e `health_check`)

- **Purpose**: SESSAO-19, SESSAO-20 e SESSAO-23 a SESSAO-25.
- **Interfaces**:
  - `manutencao_ligada() -> bool`: lê a `GlobalSetting` no máximo uma vez a cada 30 segundos por processo, guardando o valor e o horário em memória.
  - `invalidar()`: chamado pelo `AdminSystemSettingsView` ao salvar, para o próprio processo refletir a mudança na hora.
  - `MaintenanceModeMiddleware`:
    1. com a manutenção ligada, deixa passar as rotas `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`, `/api/auth/logout/` e `/api/health/`;
    2. nas demais, autentica o `Authorization` com `SessaoJWTAuthentication` e deixa passar quem tem `role == 'ADMIN'` (AD-016);
    3. o resto recebe 503 com `code: maintenance_mode`.
  - `health_check`: responde sempre 200, com `{"status": "ok", "maintenance": bool}`.

### Frontend

- **`next.config.ts`** (SESSAO-05): `rewrites()` de `/api/:path*` para `${BACKEND_URL || 'http://localhost:8000'}/api/:path*`.
- **`src/services/apiClient.ts`**:
  - `baseURL: '/api'`;
  - `definirTokenDeAcesso(token | null)` e `obterTokenDeAcesso()`, só em memória (SESSAO-02);
  - no 401 de uma rota privada, `renovarSessao()` roda uma vez e refaz a requisição uma única vez com o token novo (SESSAO-10);
  - com a renovação recusada, emite o evento de sessão encerrada (SESSAO-11);
  - rede, tempo esgotado e 5xx não encerram a sessão (SESSAO-12);
  - o 503 `maintenance_mode` guarda a página atual em `sessionStorage` e vai para `/manutencao` (SESSAO-21).
- **`src/lib/sessao-entre-abas.ts`** (SESSAO-10 e SESSAO-14):
  - `renovarSessao()` roda dentro de `navigator.locks.request('fluxar-renovacao')`. Quem pega o lock depois de outra aba ter renovado nos últimos 10 segundos usa o token que chegou pelo `BroadcastChannel('fluxar-sessao')`, sem renovar de novo.
  - `anunciarFimDaSessao()` e `aoFimDaSessao(callback)` avisam e escutam o fim da sessão nas outras abas.
  - Sem Web Locks, o que vale é a promessa única da aba.
- **`src/contexts/auth-context.tsx`**:
  - na montagem, apaga `fluxar.token` e `fluxar.refresh_token` do `localStorage` (SESSAO-06), chama a renovação e depois `/auth/me/` (SESSAO-03);
  - com erro que não seja 401, fica no estado `erro`, mostra o aviso com "Tentar de novo" e não desloga (SESSAO-12);
  - `login(access, user)` guarda o token em memória;
  - `logout()` chama `/auth/logout/`, limpa o token, o `dashboard_layout_config` e o usuário, e avisa as outras abas (SESSAO-13 e SESSAO-14).
- **`src/components/sessao/aviso-de-conexao.tsx`** (SESSAO-12): aviso com a mensagem e o botão "Tentar de novo".
- **Telas de login e verificação**: passam a chamar `login(access, user)`, sem o token de renovação.
- **`src/app/manutencao/page.tsx`** (SESSAO-22): consulta `/api/health/` a cada 30 segundos e, com `maintenance: false`, volta para a página guardada.

---

## Data Models (if applicable)

### Sessao

```python
class Sessao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessoes')
    refresh_jti = models.CharField(max_length=64)
    criada_em = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    encerrada_em = models.DateTimeField(null=True, blank=True)
```

**Relationships**: muitas sessões por usuário. A exclusão da conta apaga as sessões em cascata.

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| -------------- | -------- | ----------- |
| Token de acesso vencido | 401 e renovação transparente | Nenhum |
| Token de renovação usado, revogado, vencido ou ausente | 401 e cookie apagado | Login de novo |
| Renovação ou logout de outra origem | 403 | Nenhum para o usuário legítimo |
| Sessão encerrada em outro aparelho | Próxima requisição com 401 e renovação recusada | Vai para o login |
| Conta desativada ou excluída | 401 | Vai para o login |
| Rede, tempo esgotado ou 5xx | A sessão continua | Aviso com "Tentar de novo" |
| Manutenção ligada, usuário comum | 503 `maintenance_mode` | Página de manutenção, que volta sozinha |

---

## Risks & Concerns

| Concern | Location (file:line) | Impact | Mitigation |
| ------- | -------------------- | ------ | ---------- |
| O proxy da Vercel tem tempo máximo, e o Render gratuito leva dezenas de segundos para acordar | `next.config.ts` (novo) | A primeira requisição depois do Render dormir pode receber 504 da Vercel | O 5xx não desloga (SESSAO-12), e o aviso oferece tentar de novo. **Incerto:** o limite exato do rewrite externo da Vercel depende do plano; conferir no primeiro deploy |
| O cabeçalho `Origin` precisa chegar ao Django pelo proxy | `api/cookies.py` | Sem ele, a renovação responderia 403 para todos | Na falta do `Origin`, vale o `Referer`. **Incerto:** documentação da Vercel sobre repassar os cabeçalhos no rewrite externo; conferir no primeiro deploy e ajustar a lista de origens |
| `ALLOWED_HOSTS` e o `Host` que o Render recebe pelo proxy | `core/settings.py:22` | Com o `Host` da Vercel, o Django responderia 400 | O rewrite externo manda o `Host` do destino; conferir e, se preciso, acrescentar o domínio da Vercel em `ALLOWED_HOSTS` |
| `NUM_PROXIES` muda com a Vercel na frente | `core/settings.py` | O limite por IP usaria o IP errado | Ajustar a variável no Render depois de conferir o `X-Forwarded-For` num log |
| Uma consulta a mais por requisição autenticada | `core/authentication.py` | Custo pequeno no banco | Consulta pela chave primária, aceita na AD-014 |
| O painel de manutenção usa `IsAdminUser` (`is_staff`), e o middleware usa `role` | `api/views.py:611-615` | Um admin só com `role` passa pela manutenção, mas não consegue desligá-la | A unificação fica com `permissoes-e-planos` (AD-016); os admins atuais têm os dois |
| Web Locks e BroadcastChannel ausentes em navegadores antigos | `src/lib/sessao-entre-abas.ts` | Duas abas poderiam renovar ao mesmo tempo, e a segunda recebe 401 | Sem os dois recursos, uma renovação recusada logo depois de outra aba renovar tenta de novo uma vez |

---

## Tech Decisions (only non-obvious ones)

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Mesmo site | Proxy do Next.js (rewrite `/api/*`) | Decisão do usuário; sem domínio próprio |
| Revogação | Tabela `Sessao` com `sid` nos tokens | Cobre SESSAO-13 a SESSAO-18 com um modelo só |
| Cookie | `SameSite=Lax`, `path=/api/auth/`, `Secure` fora do `DEBUG` | Primeira parte pelo proxy; o `Lax`, junto com a checagem de origem, barra pedidos de outros sites |
| Renovação entre abas | Web Locks mais BroadcastChannel | Uma renovação só, sem janela de reuso entre abas |
| Estado da manutenção | Cache em memória por processo, 30 s | Atende a SESSAO-24 e a SESSAO-25 sem Redis nem consulta por requisição |

Estas decisões valem para as próximas features e foram registradas em `.specs/STATE.md`:
- **AD-036**: o frontend chama a API por `/api` na própria origem, pelo rewrite do Next.js; toda chamada nova usa o `apiClient`.
- **AD-037**: toda sessão tem uma linha em `Sessao`, e a autenticação confere o `sid` a cada requisição; qualquer fluxo que troque credenciais ou desative a conta encerra as sessões pelo `api/sessoes.py`.
