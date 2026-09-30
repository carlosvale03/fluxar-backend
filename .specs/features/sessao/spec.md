# Sessao Specification

## Problem Statement

A sessão do Fluxar é frágil e fácil de roubar. Os dois tokens ficam no `localStorage`, onde qualquer script injetado os lê, o refresh vale 7 dias sem rotação nem revogação, não existe logout no backend e trocar a senha não derruba as sessões abertas (SEG-05). Ao mesmo tempo, a sessão cai quando não deveria: qualquer erro em `/auth/me`, inclusive um 502 durante o deploy, desloga o usuário (FE-01), e o modo manutenção desloga todo mundo, inclusive os administradores, enquanto o `/api/health/` passa a responder 503 (OPS-04).

Origem: `docs/auditoria-2026-09.md`, seções 3 (SEG-05), 5 (FE-01, FE-04, FE-11, FE-12), 6 (PERF-06) e 7 (OPS-04).

## Goals

- [ ] Nenhum script da página consegue ler o token de renovação.
- [ ] A sessão só termina quando o usuário sai, fica 7 dias sem usar o app, troca ou redefine a senha, ou tem a conta desativada.
- [ ] Durante a manutenção, os administradores trabalham normalmente e ninguém é deslogado.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Cadastro, verificação de e-mail, login, "esqueci a senha", redefinição e limites de tentativas | Feature `autenticacao` |
| Política de segurança de conteúdo (CSP) e outros cabeçalhos de segurança (SEG-05, SEG-13) | Feature de infraestrutura |
| Tela de sessões ativas e encerramento de uma sessão específica | Não foi pedido |
| Unificar `role` e `is_staff` na definição de administrador (SEG-06) | Feature `permissoes-e-planos` |
| Link da página de manutenção para `/suporte`, que não existe (FE-17) | Ajuste de interface fora desta feature |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Onde guardar os tokens | O token de renovação fica num cookie httpOnly, Secure e SameSite, restrito às rotas de sessão; o token de acesso fica só na memória da aba | Decisão do usuário (AD-013). Um XSS não consegue roubar o token de renovação | sim |
| Trocar ou redefinir a senha | Encerra as outras sessões; na troca com o usuário logado, a sessão atual continua; a redefinição por link ou pelo administrador encerra todas | Decisão do usuário (AD-014) | sim |
| Quem acessa durante a manutenção | Só administradores usam o app; os demais veem a página de manutenção sem perder a sessão; login, renovação, `/auth/me`, logout e `/api/health/` continuam respondendo | Decisão do usuário (AD-015) | sim |
| Frontend e API no mesmo site | Por domínio próprio compartilhado ou por proxy do Next.js; a escolha fica para o design | Vercel e Render são sites diferentes, e navegadores como o Safari bloqueiam cookies de terceiros | sim |
| Duração dos tokens | Acesso: 15 minutos. Renovação: 7 dias, renovados a cada uso | Um token de acesso curto limita o estrago de um vazamento; 7 dias é o valor atual | sim |
| Token de renovação reapresentado | Recusado | Com rotação, um token de renovação usado duas vezes indica cópia | sim |
| Sessão sem uso | Termina depois de 7 dias sem uso; não há limite absoluto de duração | Quem usa o app com frequência não precisa entrar de novo | sim |
| Erro de rede ou 5xx durante a sessão | A sessão continua, e a tela oferece tentar de novo | Hoje um 502 do Render desloga o usuário (FE-01) | sim |
| Conta desativada ou excluída | Os tokens dela são recusados a partir da próxima requisição | A conta não pode mais usar o app | sim |
| Sessões antigas guardadas no `localStorage` | São descartadas na implantação, e todos entram de novo uma vez | A troca da `SECRET_KEY` (AUTH-42) já encerra essas sessões | sim |
| Administrador durante a manutenção | Quem o backend reconhece como administrador | Hoje o frontend usa `role` e o backend usa `is_staff`; a unificação fica na feature `permissoes-e-planos` (AD-016) | sim |
| Tempo para ligar ou desligar a manutenção valer | Até 30 segundos, sem consulta ao banco em cada requisição | Hoje cada requisição faz uma consulta ao banco só para isso (PERF-06) | sim |
| Volta da página de manutenção | A página verifica o estado a cada 30 segundos e volta sozinha para a página anterior | O usuário não precisa recarregar nem entrar de novo | sim |
| Rotas abertas para não administradores na manutenção | Login, renovação, `/auth/me`, logout e `/api/health/`; cadastro, verificação e redefinição ficam fechados | A manutenção não deve aceitar contas novas nem mudanças | sim |

**Open questions:** none. As suposições da tabela foram aprovadas pelo usuário em 2026-09-26.

---

## User Stories

### P1: Onde os tokens ficam ⭐ MVP

**User Story**: Como usuário, quero que um script malicioso na página não consiga levar a minha sessão.

**Why P1**: hoje os dois tokens ficam no `localStorage`, e qualquer XSS ou dependência comprometida os lê (SEG-05).

**Acceptance Criteria**:
1. **SESSAO-01** WHEN o usuário entra, confirma o e-mail ou renova a sessão THEN o sistema SHALL entregar o token de renovação num cookie httpOnly, Secure e SameSite, restrito às rotas de sessão, e o token de acesso no corpo da resposta.
2. **SESSAO-02** WHILE a sessão estiver aberta, a interface SHALL manter o token de acesso só na memória da aba, sem gravá-lo em `localStorage`, `sessionStorage` ou cookie legível por JavaScript.
3. **SESSAO-03** WHEN a página é carregada ou recarregada com um cookie de renovação válido THEN a interface SHALL obter um novo token de acesso antes de carregar os dados, sem pedir login.
4. **SESSAO-04** IF a rota de renovação ou a de logout receber um pedido de uma origem diferente da do frontend THEN o sistema SHALL recusá-lo com HTTP 403.
5. **SESSAO-05** WHEN a interface é usada num navegador que bloqueia cookies de terceiros, como o Safari, THEN o sistema SHALL renovar a sessão normalmente.
6. **SESSAO-06** WHEN a nova versão do frontend abre pela primeira vez THEN a interface SHALL apagar do `localStorage` os tokens antigos (`fluxar.token` e `fluxar.refresh_token`) e pedir um novo login.

**Independent Test**: depois do login, `document.cookie` e o `localStorage` não mostram nenhum token; recarregar a página mantém o usuário logado; no Safari, a sessão continua depois de recarregar; um `POST` à rota de renovação feito de outra origem recebe 403.

---

### P1: Duração e renovação ⭐ MVP

**User Story**: Como usuário, quero continuar logado enquanto uso o app, sem ser deslogado por uma falha passageira.

**Why P1**: hoje não há rotação, a fila de renovação pode travar (FE-11) e qualquer erro em `/auth/me` desloga (FE-01).

**Acceptance Criteria**:
1. **SESSAO-07** WHEN um token de acesso é emitido THEN o sistema SHALL defini-lo com validade de 15 minutos.
2. **SESSAO-08** WHEN um token de renovação é usado THEN o sistema SHALL emitir um novo, válido por 7 dias, e revogar o usado.
3. **SESSAO-09** IF um token de renovação já usado, revogado ou vencido for apresentado THEN o sistema SHALL recusá-lo com HTTP 401.
4. **SESSAO-10** WHEN várias requisições recebem 401 ao mesmo tempo, na mesma aba ou em abas diferentes, THEN a interface SHALL fazer uma única renovação, refazer cada requisição uma única vez com o novo token de acesso e não deslogar nenhuma aba.
5. **SESSAO-11** IF a renovação for recusada com 401 THEN a interface SHALL encerrar a sessão conforme SESSAO-14 e, numa página protegida, levar o usuário ao login.
6. **SESSAO-12** IF a renovação ou o `/auth/me` falhar por erro de rede, tempo esgotado ou resposta 5xx THEN a interface SHALL manter a sessão e mostrar uma mensagem com a opção de tentar de novo.

**Independent Test**: com o token de acesso vencido, abrir o dashboard em duas abas ao mesmo tempo gera uma única renovação e nenhuma aba desloga; reapresentar o token de renovação antigo recebe 401; com o backend respondendo 502, recarregar a página mostra a mensagem de erro e o usuário continua logado quando o backend volta.

---

### P1: Fim da sessão ⭐ MVP

**User Story**: Como usuário, quero sair de verdade quando clico em sair e derrubar quem estiver usando minha conta quando troco a senha.

**Why P1**: hoje o logout só apaga o `localStorage`, e trocar ou redefinir a senha não derruba as outras sessões (SEG-05).

**Acceptance Criteria**:
1. **SESSAO-13** WHEN o usuário sai THEN o sistema SHALL revogar o token de renovação dessa sessão e apagar o cookie.
2. **SESSAO-14** WHEN a sessão termina na interface, por logout, renovação recusada ou revogação, THEN a interface SHALL descartar o token de acesso, limpar os dados do usuário guardados no navegador (como o layout do dashboard) e encerrar a sessão nas outras abas abertas.
3. **SESSAO-15** WHEN o usuário troca a senha estando logado THEN o sistema SHALL encerrar todas as outras sessões dele e manter a sessão atual.
4. **SESSAO-16** WHEN a senha é redefinida por link ou pelo administrador THEN o sistema SHALL encerrar todas as sessões do usuário.
5. **SESSAO-17** WHEN o administrador desativa ou exclui uma conta THEN o sistema SHALL recusar os tokens dessa conta com HTTP 401 a partir da próxima requisição.
6. **SESSAO-18** IF uma requisição usar um token de acesso de uma sessão encerrada por SESSAO-15 ou SESSAO-16 THEN o sistema SHALL recusá-la com HTTP 401, mesmo antes de o token vencer.

**Independent Test**: com o usuário logado em dois navegadores, trocar a senha no primeiro mantém o primeiro logado e faz o segundo receber 401 na próxima requisição; clicar em sair numa aba desloga as outras abas do mesmo navegador; depois do logout, reapresentar o token de renovação recebe 401.

---

### P1: Modo manutenção ⭐ MVP

**User Story**: Como administrador, quero ligar a manutenção e continuar trabalhando, sem que os usuários percam a sessão.

**Why P1**: hoje a manutenção desloga até os administradores, que só conseguem desligá-la chamando a API diretamente, e o `/api/health/` responde 503 (OPS-04).

**Acceptance Criteria**:
1. **SESSAO-19** WHILE o modo manutenção estiver ligado, o sistema SHALL responder HTTP 503, com o código `maintenance_mode`, às requisições de quem não é administrador, exceto nas rotas de login, renovação, `/auth/me`, logout e `/api/health/`.
2. **SESSAO-20** WHILE o modo manutenção estiver ligado, o sistema SHALL atender normalmente as requisições de administradores, reconhecidos pelo token de acesso.
3. **SESSAO-21** WHILE o modo manutenção estiver ligado, a interface SHALL mostrar a página de manutenção a quem não é administrador, sem encerrar a sessão.
4. **SESSAO-22** WHEN o modo manutenção é desligado THEN a interface SHALL levar, em até 30 segundos, quem estava na página de manutenção de volta à página em que estava, ainda logado.
5. **SESSAO-23** WHEN `/api/health/` é chamado THEN o sistema SHALL responder HTTP 200 enquanto a aplicação estiver no ar, com ou sem manutenção.
6. **SESSAO-24** WHEN o administrador liga ou desliga o modo manutenção THEN o sistema SHALL aplicar a mudança a todas as requisições em até 30 segundos.
7. **SESSAO-25** WHILE o sistema atende requisições, o sistema SHALL verificar o estado da manutenção sem consultar o banco em cada requisição.

**Independent Test**: ligar a manutenção pelo painel: o administrador continua navegando e desliga a manutenção pelo painel; um usuário comum vê a página de manutenção, e seu token de renovação continua válido; o `/api/health/` responde 200 o tempo todo; ao desligar, o usuário comum volta à página em que estava em até 30 segundos.

---

## Edge Cases

- Duas abas renovam no mesmo instante: só uma renovação acontece, e as duas continuam logadas (SESSAO-10).
- Usuário 7 dias sem abrir o app: o token de renovação vence, e o próximo acesso pede login (SESSAO-08, SESSAO-09).
- Redefinição de senha por link com o usuário logado em outro aparelho: a sessão do outro aparelho termina na próxima requisição (SESSAO-16, SESSAO-18).
- Administrador rebaixado durante a manutenção: passa a receber 503 na próxima requisição, sem perder a sessão (SESSAO-19, SESSAO-21).
- Backend reiniciando durante o deploy: a tela mostra a mensagem de erro, e ninguém é deslogado (SESSAO-12).
- Cookie de renovação apagado pelo usuário no navegador: o próximo carregamento pede login (SESSAO-03).
- Página pública, como o link de verificação, aberta com a sessão vencida: segue AUTH-40 e AUTH-41, sem redirecionar para o login.

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | SESSAO-04, SESSAO-09 |
| Falha e falha parcial | SESSAO-11, SESSAO-12 |
| Idempotência, repetição e duplicidade | SESSAO-09, SESSAO-10 |
| Autorização e rate limiting | SESSAO-01 a SESSAO-04, SESSAO-13 a SESSAO-20; o rate limiting das rotas de entrada fica na feature `autenticacao` |
| Concorrência e ordem | SESSAO-10 |
| Ciclo de vida dos dados | SESSAO-06 a SESSAO-08, SESSAO-17 |
| Observabilidade | N/A because a spec não pede auditoria de sessões; o encerramento aparece para o próprio usuário, que precisa entrar de novo |
| Falha de dependência externa | N/A because a sessão não depende de nenhum serviço externo |
| Integridade das transições de estado | SESSAO-13 a SESSAO-16, SESSAO-19 a SESSAO-22 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SESSAO-01 | P1: Onde os tokens ficam | T3, T4, T19 | Pending |
| SESSAO-02 | P1: Onde os tokens ficam | T14, T19 | Pending |
| SESSAO-03 | P1: Onde os tokens ficam | T17 | Pending |
| SESSAO-04 | P1: Onde os tokens ficam | T3, T5, T6 | Pending |
| SESSAO-05 | P1: Onde os tokens ficam | T13 | Pending |
| SESSAO-06 | P1: Onde os tokens ficam | T14 | Pending |
| SESSAO-07 | P1: Duração e renovação | T1 | Pending |
| SESSAO-08 | P1: Duração e renovação | T1, T5 | Pending |
| SESSAO-09 | P1: Duração e renovação | T1, T5 | Pending |
| SESSAO-10 | P1: Duração e renovação | T15 | Pending |
| SESSAO-11 | P1: Duração e renovação | T15 | Pending |
| SESSAO-12 | P1: Duração e renovação | T16, T17 | Pending |
| SESSAO-13 | P1: Fim da sessão | T6, T18 | Pending |
| SESSAO-14 | P1: Fim da sessão | T18 | Pending |
| SESSAO-15 | P1: Fim da sessão | T7 | Pending |
| SESSAO-16 | P1: Fim da sessão | T8 | Pending |
| SESSAO-17 | P1: Fim da sessão | T2, T9 | Pending |
| SESSAO-18 | P1: Fim da sessão | T2 | Pending |
| SESSAO-19 | P1: Modo manutenção | T11 | Pending |
| SESSAO-20 | P1: Modo manutenção | T11 | Pending |
| SESSAO-21 | P1: Modo manutenção | T20 | Pending |
| SESSAO-22 | P1: Modo manutenção | T20 | Pending |
| SESSAO-23 | P1: Modo manutenção | T12 | Pending |
| SESSAO-24 | P1: Modo manutenção | T10 | Pending |
| SESSAO-25 | P1: Modo manutenção | T10 | Pending |

**Coverage:** 25 total, 25 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Nenhum token aparece em `localStorage`, `sessionStorage` ou `document.cookie` durante o uso do app.
- [ ] Nenhum usuário é deslogado por erro de rede, 5xx ou modo manutenção.
- [ ] Depois de trocar ou redefinir a senha, nenhuma outra sessão consegue fazer uma requisição autenticada.
