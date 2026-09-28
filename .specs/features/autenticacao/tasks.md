# Autenticacao Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/autenticacao/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Views e serializers de auth (backend) | integration | Cada rota: caminho feliz, cada erro da spec com status, mensagem e campo exatos, e os edge cases | `tests/autenticacao/test_*.py` | `docker compose exec -T backend python manage.py test tests.autenticacao --noinput` |
| Serviço de e-mail, throttles, handler de exceções, checagem e settings | integration | Todos os ramos; provedores simulados; tempo simulado nos limites | `tests/autenticacao/test_*.py` | idem |
| Migração e comando | integration | Cada caso de AUTH-43 e AUTH-44 | `tests/autenticacao/test_*.py` | idem |
| Telas, componente e apiClient (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/autenticacao/*.test.ts(x)` | `npx vitest run tests/autenticacao` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 168 erros de lint antigos (MAN-04): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.autenticacao --noinput` |
| Full | Tarefas de backend que mexem em settings, rotas ou migração | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/autenticacao` (em `fluxar-frontend`) |
| Build (frontend) | Início e fim da fase de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `NEXT_PUBLIC_API_URL=http://build-check-placeholder npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Base

Configuração, testes do frontend e checagem da chave.

```
T1 → T2
T2 → T3
```

### Phase 2: E-mail

```
T4
```

### Phase 3: Cadastro e verificação

```
T5 → T6
T6 → T7
T7 → T8
T8 → T9
T10
```

### Phase 4: Login e redefinição

```
T29
T11 → T12
T12 → T13
T13 → T14
```

### Phase 5: Limites e rotas públicas

```
T15 → T16
T16 → T17
T17 → T18
```

### Phase 6: Dados existentes

```
T19 → T20
```

### Phase 7: Frontend

```
T21 → T22
T22 → T23
T23 → T24
T24 → T25
T25 → T26
T26 → T27
```

### Phase 8: Fluxo completo

```
T28
```

---

## Task Breakdown

### Phase 1: Base

#### T1: Base de testes do frontend

**What**: Vitest, Testing Library e jsdom no frontend, com `vitest.config.ts`, `tests/setup.ts`, o script `test` no `package.json` e o passo `npm test` no CI do frontend.
**Where**: `fluxar-frontend/vitest.config.ts`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: Success Criteria (teste automatizado nas telas)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/smoke.test.tsx` renderiza o `AuthShell` e confere o título
- [x] `npm test` roda no CI do frontend, depois da checagem de TypeScript
- [x] TypeScript, lint (sem erros novos) e build continuam passando
- [x] Test count: 1 teste (real: 1 teste no frontend)

**Tests**: unit (frontend)
**Gate**: build (frontend)
**Status**: ✅ Complete

**Commit**: `test(frontend): configura Vitest e Testing Library`

---

#### T2: Configuração de segurança

**What**: `core/settings.py`: `SECRET_KEY` e `FRONTEND_URL` obrigatórias com `DEBUG` desligado, CORS sem liberar tudo, `DatabaseCache`, `NUM_PROXIES`, `LOGGING` e `LANGUAGE_CODE = 'pt-br'`; `createcachetable` no `entrypoint.sh`.
**Where**: `core/settings.py`
**Depends on**: T1
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-37, AUTH-38, AUTH-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_configuracao.py` importa as settings num subprocesso com `DEBUG=0` sem `SECRET_KEY`, e depois sem `FRONTEND_URL`, e confere o erro com o nome da variável
- [x] Sem `CORS_ALLOWED_ORIGINS`, uma requisição com `Origin` de outro site não recebe `Access-Control-Allow-Origin`
- [x] Os testes existentes continuam passando (o `.env` local tem `DEBUG=1`)
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 4 testes (real: +7 testes, suíte de 175 para 182)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(core): impede configuração insegura em produção`

---

#### T3: Checagem da chave comprometida

**What**: `core/checks.py` com a checagem de sistema que recusa, em produção, a `SECRET_KEY` com hash na lista das chaves do histórico ou começando com `django-insecure`. Os hashes são calculados a partir do histórico do git sem imprimir a chave.
**Where**: `core/checks.py`
**Depends on**: T2
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-42

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_checagem_chave.py` confere erro para uma chave da lista (usando um hash de teste injetado), para `django-insecure-...` e nenhum erro para uma chave nova, com `DEBUG` desligado
- [x] Nenhuma chave aparece no código, nos testes nem na saída de comandos
- [x] Build gate passa
- [x] Test count: suíte cresce em pelo menos 3 testes (real: +7 testes, suíte de 182 para 189)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat(core): recusa a SECRET_KEY do histórico em produção`

---

### Phase 2: E-mail

#### T4: Serviço de e-mail seguro e com prazo

**What**: Reescrita de `api/utils/email_service.py`: escape do texto do usuário, Resend por HTTP com timeout e depois SMTP com timeout, 10 segundos no total, EmailJS só com `DEBUG`, links pelo `FRONTEND_URL`, log mascarado e retorno `True`/`False`.
**Where**: `api/utils/email_service.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-24, AUTH-25, AUTH-28, AUTH-29, AUTH-30

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_email.py` confere o nome `<a href="x">clique</a>` escapado no HTML dos dois e-mails
- [x] Resend falhando e SMTP funcionando: envia pelo SMTP e registra a falha do Resend; os dois falhando: devolve `False`
- [x] O prazo passado ao SMTP é o que sobra dos 10 segundos (Resend simulado demorando)
- [x] Com `DEBUG` desligado, o EmailJS nunca é chamado
- [x] Os logs trazem tipo, provedor, resultado e e-mail mascarado, e nenhum traz o e-mail inteiro
- [x] O link usa o `FRONTEND_URL` configurado
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 8 testes (real: +10 testes, suíte de 189 para 199)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): escapa, limita a 10 s e mascara o envio de e-mails`

---

### Phase 3: Cadastro e verificação

#### T5: E-mail sem diferença de caixa

**What**: `UserManager.normalize_email` em minúsculas e `get_by_natural_key` com busca pelo e-mail em minúsculas e, na falta, pelo exato.
**Where**: `api/models.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_email_minusculo.py` cria "Ana@X.com" e confere "ana@x.com" gravado e o login com "ANA@X.COM"
- [x] Uma conta antiga "Caio@x.com" gravada à força continua entrando com o e-mail exato
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 3 testes (real: +4 testes, suíte de 199 para 203)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): trata o e-mail sem diferença de maiúsculas`

---

#### T6: Validação do cadastro

**What**: `UserRegisterSerializer`: e-mail já cadastrado com a mensagem de AUTH-03 (comparação sem caixa), erros de senha no campo `password`, termos obrigatórios e nome entre 1 e 255 caracteres.
**Where**: `api/serializers.py`
**Depends on**: T5
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-03, AUTH-04, AUTH-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_cadastro.py` cobre e-mail repetido (inclusive com outra caixa), senha curta, parecida com o nome, comum, só números e diferente da confirmação, termos falsos ou ausentes e nome vazio ou longo, cada um com 400 e a mensagem no campo
- [x] As mensagens de senha saem em português
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 10 testes (real: +14 testes, suíte de 203 para 217)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): valida o cadastro com mensagens por campo`

---

#### T7: Criação da conta e envio da verificação

**What**: `RegisterView`: conta pendente (`email_verified=False`, `is_active=True`), envio na requisição, resposta 201 com `email_sent` e a mensagem de AUTH-26 na falha, e `IntegrityError` tratado como AUTH-03.
**Where**: `api/views.py`
**Depends on**: T6
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-01, AUTH-06, AUTH-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_cadastro.py` confere a conta pendente, o token de 24 horas e o e-mail enviado com `email_sent: true`
- [x] Com os provedores falhando, 201 com `email_sent: false`, a mensagem de AUTH-26 e a conta criada
- [x] Um `IntegrityError` simulado no `create_user` responde 400 com a mensagem de AUTH-03
- [x] Nenhuma thread é criada
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 4 testes (real: +4 testes, suíte de 217 para 221)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): cria a conta pendente e envia a verificação na requisição`

---

#### T8: Link de verificação

**What**: `VerifyEmailView`: token inexistente, usado, vencido ou substituído responde 400 com `Link inválido ou expirado.` e `code: invalid_link`; o válido confirma, ativa e devolve os tokens.
**Where**: `api/views.py`
**Depends on**: T7
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-08, AUTH-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_verificacao.py` cobre link válido (tokens na resposta e `email_verified` verdadeiro), aberto duas vezes, vencido há 25 horas e substituído por um mais novo
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 5 testes (real: +8 testes, suíte de 221 para 229)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): padroniza a recusa do link de verificação`

---

#### T9: Reenvio da verificação

**What**: Rota nova `/api/auth/resend-verification/`: para conta pendente, invalida os links anteriores, cria e envia um novo; para qualquer outro caso, a mesma resposta neutra sem enviar.
**Where**: `api/views.py`
**Depends on**: T8
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-10, AUTH-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_reenvio.py` confere o link novo válido e o antigo recusado para conta pendente
- [x] E-mail inexistente e conta já verificada recebem a mesma resposta, sem envio
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 3 testes (real: +5 testes, suíte de 229 para 234)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(api): adiciona o reenvio do e-mail de verificação`

---

#### T10: Contas pendentes sem exclusão automática

**What**: Remove o comando `cleanup_inactive_users`.
**Where**: `api/management/commands/cleanup_inactive_users.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_pendente.py` confere que uma conta pendente criada há 60 dias continua existindo e que o comando não existe mais (`call_command` levanta `CommandError`)
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 2 testes (real: +2 testes, suíte de 234 para 236)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): deixa de apagar contas que não verificaram o e-mail`

---

### Phase 4: Login e redefinição

#### T29: Mensagens de senha no cadastro

**What**: `verbose_name` "nome" e "e-mail" nos campos do `User` (migração só de estado), para a mensagem de senha parecida sair "A senha é muito parecida com nome", e a validação da senha no cadastro também quando outro campo tem erro. Acrescentada na execução, a partir do lote 2.
**Where**: `api/models.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-04, AUTH-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_cadastro.py` confere "A senha é muito parecida com nome." e "... com e-mail." no campo `password`
- [x] Um cadastro com e-mail inválido e senha fraca devolve os dois erros, cada um no seu campo
- [x] `makemigrations --check` sem mudanças depois da migração nova
- [x] Full gate passa
- [x] Test count: suíte cresce em pelo menos 3 testes (real: +3 testes, suíte de 236 para 239)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(api): mostra os nomes dos campos nas mensagens de senha`

---

#### T11: Login sem revelar a conta

**What**: `CustomTokenObtainPairSerializer`: confere a senha antes do estado da conta, responde AUTH-15, AUTH-13 (`email_not_verified`) e AUTH-16 (`account_disabled`) conforme o caso.
**Where**: `api/serializers.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-13, AUTH-14, AUTH-15, AUTH-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_login.py` com conta verificada, pendente e desativada: senha errada dá a mesma resposta nas três e num e-mail inexistente; senha certa entra na verificada e dá as mensagens e códigos de AUTH-13 e AUTH-16 nas outras
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 6 testes (real: +8 testes, suíte de 239 para 247)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): só avisa o estado da conta com a senha correta`

---

#### T12: Fim da rota /api/token/

**What**: Remove a rota `/api/token/` e `api/serializers_auth.py`.
**Where**: `api/urls.py`
**Depends on**: T11
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_login.py` confere 404 em `POST /api/token/`
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 1 teste (real: +1 teste, suíte de 247 para 248)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): remove a rota antiga de login`

---

#### T13: Esqueci a senha

**What**: `ForgotPasswordView`: resposta neutra de AUTH-18, links anteriores invalidados, link de 1 hora e envio na requisição, falha registrada no log com e-mail mascarado.
**Where**: `api/views.py`
**Depends on**: T12
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-18, AUTH-19, AUTH-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_esqueci_senha.py` confere a mesma resposta para e-mail cadastrado, inexistente e conta desativada
- [x] O link novo vale 1 hora e o anterior deixa de valer
- [x] Com os provedores falhando, a resposta é a mesma e o log registra a falha com o e-mail mascarado
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 4 testes (real: +7 testes, suíte de 248 para 255)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): envia a redefinição na requisição com resposta neutra`

---

#### T14: Redefinição por link

**What**: `ResetPasswordView` e `ResetPasswordSerializer`: link inválido com `Link inválido ou expirado.`, senha nova validada com o erro em `new_password`, e confirmação do e-mail sem reativar conta desativada.
**Where**: `api/views.py`
**Depends on**: T13
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-20, AUTH-21, AUTH-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/autenticacao/test_redefinicao.py` troca a senha, entra com a nova e recebe a recusa ao reabrir o link
- [x] Link vencido, senha fraca e confirmação diferente dão 400 com a mensagem no campo
- [x] A redefinição numa conta pendente confirma o e-mail; numa conta desativada, a conta continua desativada
- [x] Quick gate passa
- [x] Test count: suíte cresce em pelo menos 6 testes (real: +13 testes, suíte de 255 para 268)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): corrige a redefinição de senha por link`

---

### Phase 5: Limites e rotas públicas

#### T15: Limites por IP

**What**: `core/throttles.py` com `LoginIPThrottle`, `CadastroIPThrottle`, `PedidoIPThrottle` e `LinkIPThrottle`, aplicados às views.
**Where**: `core/throttles.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-31, AUTH-33, AUTH-34, AUTH-35

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/test_limites.py` confere o 429 na 6ª tentativa de login em um minuto, no 6º cadastro, no 11º pedido de "esqueci a senha" e no 21º link por IP, e a liberação depois do período (tempo simulado)
- [ ] IPs diferentes (por `X-Forwarded-For`) têm contadores separados
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(core): limita tentativas por IP nas rotas de autenticação`

---

#### T16: Limites por e-mail

**What**: `LoginFalhasEmailThrottle` (10 falhas por hora, bloqueando também a senha certa) e `PedidoEmailThrottle` (3 pedidos por hora), com o registro de falha chamado pelo login.
**Where**: `core/throttles.py`
**Depends on**: T15
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-32, AUTH-34

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/test_limites.py` confere que 10 senhas erradas de IPs diferentes bloqueiam a senha certa até a hora fechar, e que login certo não conta como falha
- [ ] O 4º "esqueci a senha" e o 4º reenvio para o mesmo e-mail em uma hora recebem 429
- [ ] E-mail com outra caixa conta no mesmo contador
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 5 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(core): limita tentativas por e-mail no login e nos pedidos`

---

#### T17: Resposta 429

**What**: `core/exceptions.py` troca a mensagem do `Throttled` por "Muitas tentativas. Tente novamente em N minutos.", mantendo o `Retry-After`.
**Where**: `core/exceptions.py`
**Depends on**: T16
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-36

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/test_limites.py` confere o `Retry-After` e a mensagem com N certo para bloqueio de 1 minuto e de 1 hora
- [ ] O 404 continua com uma mensagem única para qualquer objeto não encontrado ("Não encontrado.", em português desde a T2, conforme AD-024)
- [ ] Quick gate passa
- [ ] Test count: suíte cresce em pelo menos 2 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat(core): responde o 429 com mensagem e tempo de espera`

---

#### T18: Rotas públicas sem autenticação

**What**: `authentication_classes = []` nas seis views públicas.
**Where**: `api/views.py`
**Depends on**: T17
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-40

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/test_rotas_publicas.py` chama as seis rotas com um token vencido e com um token malformado e confere que nenhuma responde 401
- [ ] `/api/auth/me/` com o token vencido continua 401
- [ ] Full gate passa
- [ ] Test count: suíte cresce em pelo menos 7 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix(api): ignora token inválido nas rotas públicas de autenticação`

---

### Phase 6: Dados existentes

#### T19: Migração dos e-mails e das contas pendentes

**What**: `api/migrations/0009_email_minusculo_e_pendentes.py`: e-mails em minúsculas quando não colidem, e contas pendentes do modelo antigo marcadas como ativas.
**Where**: `api/migrations/0009_email_minusculo_e_pendentes.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-43

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/test_migracao.py` chama a função da migração sobre "Ana@x.com", "bia@X.com", "Caio@x.com" e "caio@x.com" e confere as duas primeiras em minúsculas e o par do Caio intacto
- [ ] Uma conta com `email_verified=False` e `is_active=False` passa a `is_active=True`; uma verificada e desativada continua desativada
- [ ] `makemigrations --check` sem mudanças
- [ ] Full gate passa
- [ ] Test count: suíte cresce em pelo menos 3 testes

**Tests**: integration
**Gate**: full

**Commit**: `fix(api): passa os e-mails para minúsculas e ativa as contas pendentes`

---

#### T20: Comando check_email_case

**What**: `python manage.py check_email_case` lista os grupos de contas cujos e-mails só diferem na caixa, com ID e e-mail mascarado, sem alterar nada.
**Where**: `api/management/commands/check_email_case.py`
**Depends on**: T19
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-44

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/test_comando_email.py` confere a listagem do par do Caio com IDs e e-mail mascarado, nenhum e-mail inteiro na saída e nenhuma conta alterada
- [ ] Build gate passa
- [ ] Test count: suíte cresce em pelo menos 2 testes

**Tests**: integration
**Gate**: build

**Commit**: `feat(api): lista contas com e-mails que só diferem na caixa`

---

### Phase 7: Frontend

#### T21: apiClient nas rotas públicas

**What**: `src/services/apiClient.ts`: lista `ROTAS_PUBLICAS`, sem `Authorization` e sem renovação ou redirecionamento no 401 dessas rotas, e a função `mensagemDeErro`.
**Where**: `fluxar-frontend/src/services/apiClient.ts`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-41, AUTH-36

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/api-client.test.ts` confere que as seis rotas saem sem `Authorization` mesmo com token no `localStorage`, que um 401 delas não redireciona e que `/auth/me/` continua com o token
- [ ] `mensagemDeErro` devolve o `detail` do 429
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 4 testes no frontend

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): envia as rotas públicas de auth sem token`

---

#### T22: Componente de reenvio

**What**: `src/components/auth/resend-verification.tsx`: botão que chama `/auth/resend-verification/` com o e-mail e mostra a mensagem neutra ou a do 429.
**Where**: `fluxar-frontend/src/components/auth/resend-verification.tsx`
**Depends on**: T21
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-10, AUTH-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/resend-verification.test.tsx` confere a chamada com o e-mail, a mensagem neutra no sucesso e a mensagem do 429
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `feat(frontend): adiciona o reenvio do e-mail de verificação`

---

#### T23: Tela de cadastro

**What**: `register/page.tsx`: cada erro do backend no campo correspondente e o reenvio quando `email_sent` é `false`.
**Where**: `fluxar-frontend/src/app/auth/register/page.tsx`
**Depends on**: T22
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-07, AUTH-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/register.test.tsx` confere as mensagens de `email`, `password`, `name` e `terms_accepted` vindas do backend em cada campo
- [ ] Com `email_sent: false`, a tela mostra a mensagem e o reenvio
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): mostra os erros do cadastro em cada campo`

---

#### T24: Tela de login

**What**: `login/page.tsx`: reenvio quando o `code` é `email_not_verified` e a mensagem do backend nos demais casos, inclusive o 429.
**Where**: `fluxar-frontend/src/app/auth/login/page.tsx`
**Depends on**: T23
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-13, AUTH-36

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/login.test.tsx` confere o reenvio com `email_not_verified`, a mensagem de conta desativada e a do 429
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): oferece o reenvio no login de conta não verificada`

---

#### T25: Tela de verificação

**What**: `verify-email/page.tsx`: com link inválido, mostra a mensagem do backend e o reenvio.
**Where**: `fluxar-frontend/src/app/auth/verify-email/page.tsx`
**Depends on**: T24
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/verify-email.test.tsx` confere o sucesso com login e, no 400, a mensagem e o reenvio
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): oferece o reenvio quando o link de verificação falha`

---

#### T26: Tela de redefinição

**What**: `reset-password/page.tsx`: envia `token`, `new_password` e `new_password_confirm`, mostra o erro de senha no campo e, com link inválido, oferece pedir um novo.
**Where**: `fluxar-frontend/src/app/auth/reset-password/page.tsx`
**Depends on**: T25
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-21, AUTH-22, AUTH-23

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/reset-password.test.tsx` confere o corpo da requisição com os três campos, o erro de `new_password` no campo e o link para "Esqueci a senha" no 400 de link inválido
- [ ] Quick gate do frontend passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick (frontend)

**Commit**: `fix(frontend): envia os campos certos na redefinição de senha`

---

#### T27: Tela de esqueci a senha

**What**: `forgot-password/page.tsx`: mostra a mensagem neutra do backend e a do 429.
**Where**: `fluxar-frontend/src/app/auth/forgot-password/page.tsx`
**Depends on**: T26
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: AUTH-18, AUTH-36

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/autenticacao/forgot-password.test.tsx` confere a mensagem neutra e a do 429
- [ ] TypeScript, lint (sem erros novos), build e `npm test` passam
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: build (frontend)

**Commit**: `fix(frontend): mostra a resposta neutra do esqueci a senha`

---

### Phase 8: Fluxo completo

#### T28: Fluxo de ponta a ponta pela API

**What**: `tests/autenticacao/test_fluxo_completo.py`: cadastro, e-mail capturado, verificação, login, reenvio, "esqueci a senha" e redefinição, só pela API e com os e-mails lidos do provedor simulado.
**Where**: `tests/autenticacao/test_fluxo_completo.py`
**Depends on**: None
**Reuses**: ver a seção Code Reuse Analysis do design
**Requirement**: Success Criteria

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O teste percorre o fluxo inteiro sem passo manual e confere cada resposta pela mensagem da spec
- [ ] Build gate passa
- [ ] Test count: suíte cresce em pelo menos 1 teste

**Tests**: integration
**Gate**: build

**Commit**: `test(autenticacao): cobre o fluxo completo de entrada pela API`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8
```

Execution is strictly sequential - there is no intra-phase parallelism.

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Base de testes do frontend | 1 arquivo | ✅ Granular |
| T2: Configuração de segurança | settings e uma linha no entrypoint | ⚠️ Coeso |
| T3: Checagem da chave comprometida | 1 arquivo | ✅ Granular |
| T4: Serviço de e-mail seguro e com prazo | 1 módulo reescrito | ⚠️ Coeso |
| T5: E-mail sem diferença de caixa | 1 arquivo | ✅ Granular |
| T6: Validação do cadastro | 1 arquivo | ✅ Granular |
| T7: Criação da conta e envio da verificação | 1 arquivo | ✅ Granular |
| T8: Link de verificação | 1 arquivo | ✅ Granular |
| T9: Reenvio da verificação | 1 arquivo | ✅ Granular |
| T10: Contas pendentes sem exclusão automática | 1 arquivo | ✅ Granular |
| T29: Mensagens de senha no cadastro | 1 model, 1 migração e o serializer | ⚠️ Coeso |
| T11: Login sem revelar a conta | 1 arquivo | ✅ Granular |
| T12: Fim da rota /api/token/ | 1 arquivo | ✅ Granular |
| T13: Esqueci a senha | 1 arquivo | ✅ Granular |
| T14: Redefinição por link | 1 arquivo | ✅ Granular |
| T15: Limites por IP | 4 classes pequenas e o uso nas views | ⚠️ Coeso |
| T16: Limites por e-mail | 2 classes e a chamada no login | ⚠️ Coeso |
| T17: Resposta 429 | 1 arquivo | ✅ Granular |
| T18: Rotas públicas sem autenticação | 1 arquivo | ✅ Granular |
| T19: Migração dos e-mails e das contas pendentes | 1 arquivo | ✅ Granular |
| T20: Comando check_email_case | 1 arquivo | ✅ Granular |
| T21: apiClient nas rotas públicas | 1 arquivo | ✅ Granular |
| T22: Componente de reenvio | 1 arquivo | ✅ Granular |
| T23: Tela de cadastro | 1 arquivo | ✅ Granular |
| T24: Tela de login | 1 arquivo | ✅ Granular |
| T25: Tela de verificação | 1 arquivo | ✅ Granular |
| T26: Tela de redefinição | 1 arquivo | ✅ Granular |
| T27: Tela de esqueci a senha | 1 arquivo | ✅ Granular |
| T28: Fluxo de ponta a ponta pela API | 1 arquivo | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | None | sem seta dentro da fase | ✅ Match |
| T5 | None | sem seta dentro da fase | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | None | sem seta dentro da fase | ✅ Match |
| T29 | None | sem seta dentro da fase | ✅ Match |
| T11 | None | sem seta dentro da fase | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | None | sem seta dentro da fase | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |
| T17 | T16 | T16 → T17 | ✅ Match |
| T18 | T17 | T17 → T18 | ✅ Match |
| T19 | None | sem seta dentro da fase | ✅ Match |
| T20 | T19 | T19 → T20 | ✅ Match |
| T21 | None | sem seta dentro da fase | ✅ Match |
| T22 | T21 | T21 → T22 | ✅ Match |
| T23 | T22 | T22 → T23 | ✅ Match |
| T24 | T23 | T23 → T24 | ✅ Match |
| T25 | T24 | T24 → T25 | ✅ Match |
| T26 | T25 | T25 → T26 | ✅ Match |
| T27 | T26 | T26 → T27 | ✅ Match |
| T28 | None | sem seta dentro da fase | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Base de testes do frontend | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T2: Configuração de segurança | Backend | integration | integration | ✅ OK |
| T3: Checagem da chave comprometida | Backend | integration | integration | ✅ OK |
| T4: Serviço de e-mail seguro e com prazo | Backend | integration | integration | ✅ OK |
| T5: E-mail sem diferença de caixa | Backend | integration | integration | ✅ OK |
| T6: Validação do cadastro | Backend | integration | integration | ✅ OK |
| T7: Criação da conta e envio da verificação | Backend | integration | integration | ✅ OK |
| T8: Link de verificação | Backend | integration | integration | ✅ OK |
| T9: Reenvio da verificação | Backend | integration | integration | ✅ OK |
| T10: Contas pendentes sem exclusão automática | Backend | integration | integration | ✅ OK |
| T29: Mensagens de senha no cadastro | Backend | integration | integration | ✅ OK |
| T11: Login sem revelar a conta | Backend | integration | integration | ✅ OK |
| T12: Fim da rota /api/token/ | Backend | integration | integration | ✅ OK |
| T13: Esqueci a senha | Backend | integration | integration | ✅ OK |
| T14: Redefinição por link | Backend | integration | integration | ✅ OK |
| T15: Limites por IP | Backend | integration | integration | ✅ OK |
| T16: Limites por e-mail | Backend | integration | integration | ✅ OK |
| T17: Resposta 429 | Backend | integration | integration | ✅ OK |
| T18: Rotas públicas sem autenticação | Backend | integration | integration | ✅ OK |
| T19: Migração dos e-mails e das contas pendentes | Backend | integration | integration | ✅ OK |
| T20: Comando check_email_case | Backend | integration | integration | ✅ OK |
| T21: apiClient nas rotas públicas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T22: Componente de reenvio | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T23: Tela de cadastro | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T24: Tela de login | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T25: Tela de verificação | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T26: Tela de redefinição | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T27: Tela de esqueci a senha | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T28: Fluxo de ponta a ponta pela API | Backend | integration | integration | ✅ OK |
