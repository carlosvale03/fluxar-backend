# Sessao Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/sessao/spec.md`
**Status:** Spec aprovada; implementada e verificada em 2026-09-30 (validation.md: PASS na 2ª rodada)

---

## Feature Boundary

Onde os tokens ficam, quanto duram, como são renovados e quando a sessão termina, nos dois repositórios; e quem continua acessando o sistema durante o modo manutenção. A entrada no sistema (cadastro, login, verificação e redefinição) fica na feature `autenticacao`.

---

## Implementation Decisions

### Onde guardar os tokens

- Token de renovação num cookie httpOnly, Secure e SameSite, restrito às rotas de sessão; token de acesso só na memória da aba (AD-013).
- Exige frontend e API no mesmo site, por domínio próprio ou proxy do Next.js; hoje o frontend está na Vercel e a API no Render.

### Trocar a senha e as outras sessões

- A troca com o usuário logado encerra as outras sessões e mantém a atual; a redefinição por link ou pelo administrador encerra todas (AD-014).

### Quem acessa durante a manutenção

- Só administradores; os demais veem a página de manutenção sem perder a sessão (AD-015).

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Mesmo site para frontend e API.
- Duração dos tokens, recusa de token de renovação reapresentado e fim por falta de uso.
- Sessão mantida em erro de rede ou 5xx.
- Conta desativada ou excluída.
- Descarte das sessões antigas do `localStorage`.
- Definição de administrador durante a manutenção.
- Tempo para a manutenção valer, volta automática da página e rotas abertas.

---

## Specific References

- Os tokens ficam em `localStorage` com as chaves `fluxar.token` e `fluxar.refresh_token` (`fluxar-frontend/src/contexts/auth-context.tsx:79-82`), e o interceptador os lê a cada requisição (`fluxar-frontend/src/services/apiClient.ts:15-20`).
- A renovação grava só o novo token de acesso e ignora um token de renovação novo (`fluxar-frontend/src/services/apiClient.ts:103-107`); sem token de renovação, `isRefreshing` nunca volta a `false` (`:92` e `:123-128`).
- Qualquer erro em `/auth/me` chama `logout()` (`fluxar-frontend/src/contexts/auth-context.tsx:62-64`), e o `logout()` só limpa o `localStorage`, sem avisar o backend nem limpar o cabeçalho padrão do axios (`:99-104`; `apiClient.ts:106`).
- O backend usa token de acesso de 60 minutos e de renovação de 7 dias, sem rotação nem lista de revogação (`core/settings.py:194-202`), e não tem rota de logout (`api/urls.py`).
- A troca de senha logada (`api/views.py:251-272`), a redefinição por link (`:162-193`) e a redefinição pelo administrador (`:586-615`) não encerram nenhuma sessão.
- O middleware de manutenção roda antes da autenticação JWT, libera `/api/auth/token/refresh/`, que não existe, e bloqueia `/api/health/` (`api/middleware.py:15-37`); ele consulta o banco em toda requisição (`:26`).
- O frontend redireciona para `/manutencao` em qualquer 503 de manutenção (`fluxar-frontend/src/services/apiClient.ts:64-77`), e o `catch` de `/auth/me` desloga em seguida.

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
