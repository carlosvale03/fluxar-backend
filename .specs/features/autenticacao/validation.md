# Autenticacao Validation

**Date**: 2026-09-28
**Spec**: `.specs/features/autenticacao/spec.md`
**Diff range**:
- Backend: `development..fix/autenticacao` = `47b7bfc..148f8cf` (33 commits)
- Frontend: `development..fix/autenticacao` = `ab99f61..0349f2e` (9 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve (uma rodada, 8 mutações nos pontos centrais)

**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T29 | ✅ Done | `tasks.md` tem 29 tarefas com `Status: ✅ Complete`; nenhuma bloqueada ou parcial |

---

## Gate Check

### Backend

- **Build gate**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`
- **Resultado**: compileall ok; `makemigrations --check`: "No changes detected"; **305 testes, 305 passaram, 0 falhas, 0 pulados** (exit 0)
- **Quick gate**: `docker compose exec -T backend python manage.py test tests.autenticacao --noinput` → **130 testes, OK**
- **Contagem antes da feature**: 175 (registrada em T2, `tasks.md`)
- **Contagem depois**: 305
- **Delta**: +130 testes, todos em `tests/autenticacao/`; nenhum teste removido fora do comando `cleanup_inactive_users`, que a spec manda remover (AUTH-12)

### Frontend

| Comando | Resultado |
| ------- | --------- |
| `npx tsc --noEmit -p . --incremental false` | exit 0 |
| `npm test` | 8 arquivos, **31 testes, 31 passaram** |
| `npm run lint` | 166 erros, 250 avisos (baseline da `development`: 168 erros) |
| `NEXT_PUBLIC_API_URL=http://build-check-placeholder npm run build` | exit 0 |
| `npm audit --omit=dev` | 0 vulnerabilidades |

**Lint por regra** (`development` medido num worktree temporário com o mesmo `node_modules`):

| Regra | development | HEAD |
| ----- | ----------- | ---- |
| `@typescript-eslint/no-explicit-any` | 132 | 130 |
| `react/no-unescaped-entities` | 18 | 18 |
| `no-var` | 4 | 4 |
| `prefer-const` | 4 | 4 |
| `@typescript-eslint/ban-ts-comment` | 4 | 4 |
| `react-hooks/set-state-in-effect` | 3 | 3 |
| `@typescript-eslint/no-empty-object-type` | 2 | 2 |
| `react-hooks/immutability` | 1 | 1 |

Nenhuma regra e nenhum arquivo ganhou erros. A queda de 2 vem dos `catch (error: any)` removidos em `login/page.tsx` e `register/page.tsx`.

---

## Spec-Anchored Acceptance Criteria

Caminhos do backend relativos a `tests/autenticacao/`; os do frontend, a `fluxar-frontend/tests/autenticacao/`.

### P1: Cadastro

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-01 cadastro válido | conta não verificada + e-mail de verificação | `test_cadastro.py:214` `status_code == 201`; `:221` `assertFalse(usuario.email_verified)`; `:222` `assertTrue(usuario.is_active)`; `:227-228` validade de 24 h; `:229-232` `envio.assert_called_once()` com o usuário e o token | ✅ PASS |
| AUTH-02 e-mail sem caixa | ignora a caixa e guarda em minúsculas | `test_cadastro.py:211,220` cadastro de `Ricardo@Fluxar.teste` gravado como `ricardo@fluxar.teste`; `test_email_minusculo.py:181` `usuario.email == 'ana@x.com'`; `:197` login `ANA@X.COM` → 200; `test_cadastro.py:64` `ANA@X.COM` recusado como repetido | ✅ PASS |
| AUTH-03 e-mail repetido | 400 + mensagem exata no campo `email` | `test_cadastro.py:44` `status_code == 400`; `:55` `resposta.data['email'] == [EMAIL_JA_CADASTRADO]` (texto idêntico ao da spec, `:18`) | ✅ PASS |
| AUTH-04 senha fraca | 400 + motivo no campo `password` | `test_cadastro.py:82-84` curta; `:93-95` parecida com o nome; `:104-105` parecida com o e-mail; `:111` comum; `:116` só números; `:121` confirmação diferente, todos com a lista exata em `resposta.data['password']` e 400 em `:44` | ✅ PASS |
| AUTH-05 nome e termos | 400 + motivo no campo | `test_cadastro.py:167-168` e `:175-176` `terms_accepted`; `:183` `name == ['Informe o nome.']`; `:189-190` 256 caracteres; `:197` 255 aceitos | ✅ PASS |
| AUTH-06 cadastros simultâneos | uma conta só; o outro recebe AUTH-03 | `test_cadastro.py:267-268` `IntegrityError` simulado → 400 e `data['email'] == [EMAIL_JA_CADASTRADO]`; `:269-271` nenhuma conta, token ou envio | ✅ PASS (concorrência simulada; ver notas) |
| AUTH-07 erros na tela | cada erro no campo, com a mensagem do backend | frontend `register.test.tsx:201-209` `within(campo(...)).getByText(...)` para `name`, `email`, `password`, `password_confirm` e `terms_accepted` | ✅ PASS |

### P1: Verificação de e-mail e conta não verificada

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-08 link válido | confirma, ativa e inicia a sessão | `test_verificacao.py:51` 200; `:52-53` `AccessToken(...)['user_id'] == str(pk)`; `:55` `email_verified`; `:56` `is_active`; `:58` `token.used`; frontend `verify-email.test.tsx:129` `login` chamado com os tokens | ✅ PASS |
| AUTH-09 link vencido, usado ou substituído | 400 + "Link inválido ou expirado." + oferta de reenvio | `test_verificacao.py:80-81` usado; `:91` (via `:38-39`) vencido há 25 h; `:101` substituído, todos com `data == {'detail': 'Link inválido ou expirado.', 'code': 'invalid_link'}`; frontend `verify-email.test.tsx:141` mensagem e `:145` reenvio chamado | ✅ PASS |
| AUTH-10 reenvio | link novo; anteriores inválidos | `test_reenvio.py:167-174` token novo de 24 h enviado; `:176` `link_antigo.used`; `:179-180` link antigo → 400 `invalid_link`; `:183` link novo → 200; frontend `resend-verification.test.tsx:347` | ✅ PASS |
| AUTH-11 reenvio neutro | mesma resposta, sem envio | `test_reenvio.py:194-195` inexistente; `:207-208` já verificada: `data == RESPOSTA_NEUTRA` (texto idêntico ao da spec, `:141`) e `envio.assert_not_called()` | ✅ PASS |
| AUTH-12 sem exclusão automática | conta pendente continua existindo | `test_pendente.py:257-258` comando não existe (`CommandError`); `:268-269` conta pendente de 60 dias existe | ✅ PASS |
| AUTH-13 login de conta pendente | 400 + `email_not_verified` + "Confirme seu e-mail para entrar." + reenvio | `test_login.py:76` `assertRecusado(..., {'detail': 'Confirme seu e-mail para entrar.', 'code': 'email_not_verified'})` com 400 em `:40`; frontend `login.test.tsx:50` mensagem e `:53` reenvio para o e-mail digitado | ✅ PASS |

### P1: Login

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-14 login válido | inicia a sessão | `test_login.py:50` 200; `:52` `acesso['user_id'] == str(pk)`; `:57` refresh do mesmo usuário | ✅ PASS |
| AUTH-15 senha errada ou e-mail inexistente | 400 + "E-mail ou senha incorretos." nos dois casos | `test_login.py:62,65,68,71` `data == {'detail': 'E-mail ou senha incorretos.', 'code': 'invalid_credentials'}` para verificada, pendente, desativada e inexistente | ✅ PASS |
| AUTH-16 conta desativada | 400 + "Esta conta está desativada." | `test_login.py:81` e `:87` `data == {'detail': 'Esta conta está desativada.', 'code': 'account_disabled'}` | ✅ PASS |
| AUTH-17 rota antiga | 404 | `test_login.py:103` `status_code == 404`; `:104` sem `access` | ✅ PASS |

### P1: Esqueci a senha e redefinição

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-18 resposta neutra | 200 + mensagem exata, exista ou não a conta | `test_esqueci_senha.py:151-152` cadastrada; `:159-160` inexistente; `:169-170` desativada: `data == RESPOSTA_NEUTRA` (texto idêntico ao da spec); frontend `forgot-password.test.tsx:296` mensagem e `:298` sem "instruções enviadas" | ✅ PASS |
| AUTH-19 link de 1 hora | link válido por 1 h; anteriores inválidos | `test_esqueci_senha.py:192-193` `expires_at` em 1 h; `:195-196` anterior `used` e `not is_valid()` | ✅ PASS |
| AUTH-20 redefinição válida | troca a senha, invalida o link, confirma o e-mail, ativa se só pendente | `test_redefinicao.py:73-78` 200, `token.used`, entra com a nova e não com a antiga; `:87-89` conta pendente confirmada e entra; `:98` conta desativada continua com `is_active=False` | ✅ PASS |
| AUTH-21 link vencido ou usado | 400 + "Link inválido ou expirado." + pedir novo | `test_redefinicao.py:110-111` usado; `:121` (via `:56-57`) vencido há 61 min: `data == LINK_INVALIDO`; frontend `reset-password.test.tsx:239-240` mensagem e link para `/auth/forgot-password` | ✅ PASS |
| AUTH-22 senha nova fraca | 400 + motivo no campo da senha | `test_redefinicao.py:137-157` via `:61-62` `data['new_password'] == [mensagem]` para curta, parecida com o nome, comum, só números e confirmação diferente; frontend `reset-password.test.tsx:227` erro no campo `newPassword` | ✅ PASS |
| AUTH-23 campos enviados | `token`, `new_password`, `new_password_confirm` | frontend `reset-password.test.tsx:210-214` `post` chamado com exatamente esses três campos; backend `test_fluxo_completo.py:208-214` | ✅ PASS |

### P1: E-mails transacionais

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-24 escape | nome como texto, sem virar link | `test_email.py:98-99` e `:112-113` `NOME_ESCAPADO in html` e `NOME_MALICIOSO not in html`, nos dois e-mails; `:133-134` também no SMTP | ✅ PASS |
| AUTH-25 provedores em ordem, 10 s, sem thread | Resend e depois SMTP, 10 s no total, na requisição | `test_email.py:137-138` falha do Resend e envio pelo SMTP; `:167-169` prazo do Resend 10 s e do SMTP 3 s restantes; `:185-188` sem tempo, SMTP não tentado; `test_cadastro.py:239` e `test_esqueci_senha.py:202` `thread.assert_not_called()` | ✅ PASS |
| AUTH-26 verificação não enviada | 201 + `email_sent: false` + mensagem exata + reenvio | `test_cadastro.py:249-251` 201, `email_sent is False`, mensagem idêntica à da spec (`:19-21`); `:252-255` conta e token mantidos; frontend `register.test.tsx:220-226` mensagem, botão e chamada de reenvio | ✅ PASS |
| AUTH-27 redefinição não enviada | resposta de AUTH-18 + log | `test_esqueci_senha.py:213-214` 200 e `RESPOSTA_NEUTRA`; `:216-217` log com `ri***@fluxar.teste`, sem o e-mail inteiro | ✅ PASS |
| AUTH-28 log | tipo, provedor, resultado, endereço mascarado | `test_email.py:237-249` linhas exatas `tipo=... provedor=... resultado=... destinatario=an***@fluxar.teste`; `:251-254` sem e-mail, nome ou token | ✅ PASS |
| AUTH-29 EmailJS em produção | desligado | `test_email.py:202-205` com `DEBUG=False` e a flag ligada, só o Resend é chamado | ✅ PASS |
| AUTH-30 links pelo `FRONTEND_URL` | link montado pelo `FRONTEND_URL` | `test_email.py:267-275` os dois links com o `FRONTEND_URL` configurado e sem `localhost` | ✅ PASS |

### P1: Limites de tentativas

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-31 login por IP | 6ª tentativa em 60 s → 429 até o fim do período | `test_limites.py:79` 5 passam; `:81,83` 6ª e 7ª (59 s) → 429 com `Retry-After` (`:72-74`); `:86` liberado depois | ✅ PASS |
| AUTH-32 login por e-mail | 10 falhas em 1 h → 429 inclusive com a senha certa | `test_limites.py:194-195` 9 falhas não bloqueiam; `:197-200` 10ª falha bloqueia a senha certa, também aos 3599 s; `:203` liberado depois da hora | ✅ PASS |
| AUTH-33 cadastro por IP | 6º cadastro em 1 h → 429 | `test_limites.py:92` 5 × 201; `:94,96` 429 até 3599 s; `:99` liberado | ✅ PASS |
| AUTH-34 esqueci e reenvio | 3 por e-mail e 10 por IP por hora | `test_limites.py:106` 11º por IP → 429; `:115` reenvio com contador próprio; `:248` 4º esqueci para o mesmo e-mail (três caixas) → 429; `:260` 4º reenvio → 429 | ✅ PASS |
| AUTH-35 links por IP | 21ª tentativa em 1 h → 429 | `test_limites.py:124` 20 × 400; `:126-127` verificação e redefinição → 429 no contador comum; `:130` liberado | ✅ PASS |
| AUTH-36 resposta do 429 | `Retry-After` + "Muitas tentativas. Tente novamente em N minutos." (ou "1 minuto") + tela | `test_limites.py:292-296` `headers['Retry-After']` e `data == {'detail': 'Muitas tentativas. Tente novamente em {N} {unidade}.'}`, com `:309,311` "1 minuto" e `:321,323` "60 minutos" e "10 minutos"; frontend `login.test.tsx:77`, `register.test.tsx:248`, `forgot-password.test.tsx:310`, `reset-password.test.tsx:252`, `resend-verification.test.tsx:367` e `api-client.test.ts:123` | ✅ PASS |

### P1: Configuração dos tokens

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-37 sem `SECRET_KEY` | interrompe nomeando a variável | `test_configuracao.py:107-108` via `:99-104` exit ≠ 0, `ImproperlyConfigured` e `'SECRET_KEY' in erro` | ✅ PASS |
| AUTH-38 sem `FRONTEND_URL` | interrompe nomeando a variável | `test_configuracao.py:111-112` ausente e `:115-116` vazia, com `'FRONTEND_URL' in erro` | ✅ PASS |
| AUTH-39 sem `CORS_ALLOWED_ORIGINS` | nenhuma origem liberada | `test_configuracao.py:144-146` `Access-Control-Allow-Origin` ausente na requisição simples e na preflight, `allow_all` falso | ✅ PASS |

### P1: Rotas públicas sem sessão

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-40 token inválido nas rotas públicas | processa como anônima, sem 401 | `test_rotas_publicas.py:42` `status_code == esperado` com token vencido e malformado para as seis rotas (`:44-90`: 201, 200, 200, 200, 200, 200); `:92-96` a rota protegida continua com 401 | ✅ PASS |
| AUTH-41 interface sem token | sem `Authorization` e sem redirecionar | frontend `api-client.test.ts:79` `Authorization` ausente nas seis rotas; `:97-99` o 401 de rota pública não renova nem redireciona | ✅ PASS |

### P2: Implantação e dados existentes

| Critério | Resultado definido na spec | `file:line` + asserção | Result |
| -------- | -------------------------- | ---------------------- | ------ |
| AUTH-42 `SECRET_KEY` nova | chave de produção diferente de qualquer chave do histórico | `test_checagem_chave.py:35` `ids == ['core.E001']` para chave do histórico; `:40` prefixo `django-insecure`; `:44` chave nova sem erro; `:52-54` `check --deploy` falha; `:67-71` `entrypoint.sh` roda `check --deploy` antes do `migrate` e do `gunicorn` | ✅ PASS (checagem); a troca da chave é passo manual de implantação |
| AUTH-43 e-mails em minúsculas | converte os que não colidem | `test_migracao.py:45-46` `ana@x.com` e `bia@x.com` | ✅ PASS |
| AUTH-44 colisões | listadas e mantidas | `test_migracao.py:47-48` e `:57-58` par intacto; `test_comando_email.py:126-129` par listado com ID e e-mail mascarado; `:152` nenhuma conta alterada | ✅ PASS |

**Status**: ✅ 44/44 critérios com evidência `file:line` e asserção no resultado definido pela spec. AUTH-42 depende também de um passo manual de implantação.

---

## Edge Cases

- [x] E-mail de outra pessoa cadastrado e não verificado; o dono redefine a senha e assume a conta: `test_redefinicao.py:80-89`.
- [x] Link de verificação aberto duas vezes: `test_verificacao.py:74-82`; a tela chama a API uma vez só, mesmo no StrictMode: `verify-email.test.tsx:149-160`.
- [x] Reenvio pedido quatro vezes em uma hora, o quarto recebe 429: `test_limites.py:254-260`.
- [x] Conta desativada pede "esqueci a senha": resposta neutra (`test_esqueci_senha.py:164-171`) e a redefinição não a reativa (`test_redefinicao.py:91-101`).
- [x] Login com "ANA@X.COM": `test_email_minusculo.py:189-200`.
- [x] Resend fora do ar e SMTP funcionando: `test_email.py:121-138`.
- [~] Bloqueio de 10 senhas erradas; o dono ainda pode redefinir: o bloqueio está em `test_limites.py:193-203`. A redefinição durante o bloqueio não tem teste próprio, mas vale por construção: `ForgotPasswordView` (`api/views.py:212`) e `ResetPasswordView` (`api/views.py:249`) não usam `LoginFalhasEmailThrottle`.

---

## Discrimination Sensor

Worktrees temporários: `../fluxar-backend-verif` e `../fluxar-frontend-verif`, os dois em `HEAD` sem mutação. Antes das mutações, o backend passou nos 130 testes de `tests.autenticacao` (via `docker run ... fluxar-backend-backend`) e o frontend nos 31 testes de `tests/autenticacao` (depois de `npm ci`). Cada mutação foi aplicada, testada e revertida com `git checkout -- <arquivo>` no worktree temporário.

| # | File:line | Descrição | Killed? | Testes que falharam |
| - | --------- | --------- | ------- | ------------------- |
| B1 | `api/serializers.py:211` | O login revela `email_not_verified` antes de conferir a senha | ✅ Killed | `test_login` (2): senha errada na conta pendente; conta desativada e não verificada |
| B2 | `api/serializers.py:213` | `registrar_falha` removido do login | ✅ Killed | `test_limites.LimitesPorEmailTests` (3), inclusive o bloqueio da senha certa depois de 10 falhas |
| B3 | `core/throttles.py:24` | Limite de login por IP de `5/min` para `6/min` | ✅ Killed | `test_limites` (5), inclusive a 6ª tentativa em um minuto e a mensagem de "1 minuto" |
| B4 | `api/views.py:121` | Verificação aceita o link substituído por um mais novo | ✅ Killed | `test_verificacao` (1): link substituído por um mais novo |
| B5 | `api/views.py:281-282` | A redefinição reativa a conta desativada | ✅ Killed | `test_redefinicao` (1): conta desativada continua desativada |
| B6 | `api/utils/email_service.py:181,257` | `escape` retirado do nome nos dois e-mails | ✅ Killed | `test_email` (4): nome escapado na verificação, na redefinição, no SMTP e no `to_name` do EmailJS |
| F1 | `src/services/apiClient.ts:19` | `/auth/verify-email/` retirado de `ROTAS_PUBLICAS` | ✅ Killed | `api-client.test.ts`: envio de `/auth/verify-email/?token=abc` sem `Authorization` |
| F2 | `src/app/auth/reset-password/page.tsx:66` | A redefinição envia `password` em vez de `new_password` | ✅ Killed | `reset-password.test.tsx`: envio de `token`, `new_password` e `new_password_confirm` |

**Sensor depth**: leve, a pedido do usuário (8 mutações de comportamento nos pontos centrais; a feature é de autenticação, P0)
**Result**: 8/8 killed - PASS ✅

Depois do sensor, `git status --porcelain` dos dois worktrees temporários ficou vazio, e os dois foram removidos com `git worktree remove --force` e `git worktree prune`.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes | ✅ (o `LANGUAGE_CODE` para `pt-br` muda as mensagens padrão de todo o backend, coerente com a AD-024) |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored outcome check (asserted values match spec) | ✅ |
| Per-layer Coverage Expectation met | ✅ as seis rotas públicas têm caminho feliz, de erro e de limite |
| Every test maps to a spec requirement | ✅ cada arquivo de teste cita os AUTH que cobre |
| Documented guidelines followed | `CLAUDE.md` do backend e AD-011, AD-012, AD-019, AD-024, AD-034 e AD-035 do `STATE.md` |

---

## SPEC_DEVIATION

`api/views.py:151`: um link de verificação válido numa conta desativada pelo administrador confirma o e-mail e responde 400 `{"detail": "Esta conta está desativada.", "code": "account_disabled"}`, sem tokens. A decisão protege a desativação (AD-035) e usa a mesma mensagem de AUTH-16.

O teste `test_verificacao.py:61-70` confere só que não há `access` nem `refresh` e que a conta continua desativada. Ele não confere o status 400, o código `account_disabled` nem o `email_verified=True`, que a view grava. O comportamento está correto no código; a asserção é mais fraca do que o comportamento documentado.

---

## Spec-precision gaps

Nenhum critério ficou sem resultado preciso. Pontos em que a spec deixa margem:

1. **AUTH-04 e AUTH-22** dizem "o motivo no campo da senha", sem fixar o texto. Os testes fixam as mensagens do Django em pt-BR (e o `SenhaParecidaValidator`), o que é mais estrito que a spec.
2. **AUTH-06**: a concorrência é simulada com um `IntegrityError` no `create_user`. A garantia de conta única vem da restrição `unique` do banco sobre o e-mail já em minúsculas; não há teste com duas requisições paralelas de verdade.
3. **SPEC_DEVIATION da verificação de conta desativada**: a spec não define o caso; a decisão está no código, não na spec.

---

## Segredos no diff

- Nenhum valor real de `SECRET_KEY` aparece no diff dos dois repositórios. A busca comparou o SHA-256 de cada texto entre aspas das linhas adicionadas com a lista `CHAVES_COMPROMETIDAS` de `core/checks.py` e procurou textos longos com cara de chave.
- Único acerto: `core/settings.py:38`, o valor de desenvolvimento usado só com `DEBUG` ligado. Ele já existia na `development`, está na lista de chaves comprometidas e é recusado pelo `check --deploy`, tanto pelo hash quanto pelo prefixo `django-insecure`.
- `core/checks.py` guarda só hashes; os testes usam chaves de teste (`test_checagem_chave.py:19-21`, `test_configuracao.py:19`).

---

## Notas residuais e passos de implantação

O Render roda o backend em Python nativo, não pelo `Dockerfile`. Por isso o `entrypoint.sh` (com `check --deploy` e `createcachetable`) não roda lá, e o `DEPLOY.md` ainda mostra o build antigo (`pip install -r requirements.txt && python manage.py collectstatic --noinput`). Antes do merge em produção:

1. **`SECRET_KEY` nova** (AUTH-42): gerar uma chave nova e defini-la no Render. A troca encerra as sessões abertas, como a spec prevê.
2. **`FRONTEND_URL`**: obrigatória com `DEBUG` desligado (AUTH-38). Sem ela, o backend não sobe.
3. **`CORS_ALLOWED_ORIGINS`**: sem a lista, nenhuma origem é liberada (AUTH-39), e o frontend deixa de chamar a API.
4. **Build ou pre-deploy do Render**: acrescentar `python manage.py check --deploy`, `python manage.py migrate --noinput` e `python manage.py createcachetable`. Sem o `createcachetable`, os limites de tentativas (DatabaseCache) dão erro 500. Sem o `migrate`, as migrações 0009 e 0010 não rodam. Sem o `check --deploy`, a checagem da chave comprometida não roda.
5. **`NUM_PROXIES`** (padrão 1): confirmar quantos proxies o Render põe na frente do app. Um valor errado faz todos os clientes dividirem o mesmo contador de IP ou deixa o IP ser forjado pelo `X-Forwarded-For`.
6. **Contas com e-mails que só diferem na caixa**: rodar `python manage.py check_email_case` depois da migração e resolver os grupos listados à mão (AUTH-44).
7. **Atualizar o `DEPLOY.md`** com as variáveis e os comandos acima.

Observações de código, sem impacto nos critérios:

- `VerifyEmailView` (`api/views.py:139-140`) marca o link como usado com um `save` comum, sem a atualização condicional que a redefinição usa (`api/views.py:276`). Duas aberturas exatamente simultâneas do mesmo link poderiam gerar duas sessões para o mesmo usuário. O risco é baixo; a tela já evita a chamada dupla do StrictMode.
- A versão em texto puro dos e-mails usa o nome escapado (`api/utils/email_service.py:242,316`), então um nome com `<` ou `&` aparece como `&lt;` ou `&amp;` nesse texto. É cosmético; o HTML, que é o que a spec exige, está certo.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| AUTH-01 a AUTH-41, AUTH-43, AUTH-44 | Pending | ✅ Verified |
| AUTH-42 | Pending | ✅ Verified (checagem); troca da chave pendente na implantação |

---

## Summary

**Overall**: ✅ Ready, com os passos de implantação acima

**Spec-anchored check**: 44/44 critérios com evidência; nenhum critério sem resultado preciso; 3 pontos de margem registrados
**Sensor**: 8/8 mutações mortas (6 no backend, 2 no frontend)
**Gate**: backend 305/305; frontend 31/31, `tsc`, build e audit limpos, lint 166 erros (168 na `development`, nenhuma regra piorou)

**What works**: os cinco fluxos de entrada de ponta a ponta pela API (`test_fluxo_completo.py:150-230`), os limites por IP e por e-mail, o escape nos e-mails, a configuração que falha fechada e as rotas públicas sem sessão nos dois repositórios.

**Issues found**: nenhum bloqueante. Recomendado: reforçar `test_verificacao.py:61-70` para conferir o 400, o `account_disabled` e o `email_verified=True` da SPEC_DEVIATION.

**Next steps**: aplicar os passos de implantação 1 a 7 junto com o merge.

---

## Fechamento

- `validate_state.py autenticacao`: `validate_state: 0 error(s) across [autenticacao]` (exit 0).
- Lições: registrada `L-011` (candidata, sinal `spec_deviation`, fonte `api/views.py:151` e `test_verificacao.py:61`) pelo `lessons.py`. Os pontos de margem da spec não viraram lição, porque nenhum critério ficou sem resultado preciso.

---

## Ajustes depois da verificação

- `d520715`: o link de verificação passa a ser marcado como usado com um update condicional, como na redefinição, e o teste do desvio de spec (conta desativada) confere o 400, o código `account_disabled`, o e-mail confirmado e o link usado (nota 1 e item de baixo risco da seção anterior). Suíte do backend: 306 testes.
- `DEPLOY.md` atualizado com os passos de deploy da nota 2.
- A parte em texto puro dos e-mails continua com o nome escapado, como os testes de `test_email.py` pedem; o custo é só visual num nome com `<` ou `&`.

