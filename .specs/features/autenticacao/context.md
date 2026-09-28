# Autenticacao Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/autenticacao/spec.md`
**Status:** Spec aprovada; design e tasks aprovados em 2026-09-28; execução em andamento

---

## Feature Boundary

Cadastro, verificação de e-mail, login, "esqueci a senha" e redefinição, nos dois repositórios; os e-mails transacionais desses fluxos; os limites de tentativas; e a configuração da qual os tokens dependem (`SECRET_KEY` e CORS). Duração, renovação e encerramento da sessão ficam na feature `sessao`.

---

## Implementation Decisions

### Limite de tentativas de cada rota

- Login: 5 por minuto por IP e 10 falhas por hora por e-mail.
- Cadastro: 5 por hora por IP.
- "Esqueci a senha" e reenvio de verificação: 3 por hora por e-mail e 10 por hora por IP.
- Verificação e redefinição por link: 20 por hora por IP.
- Hoje não há nenhum `DEFAULT_THROTTLE_CLASSES` em `core/settings.py:171-180`.

### Conta que não verificou o e-mail

- Fica aguardando, sem exclusão automática; o login avisa e oferece reenviar o link.
- O comando `cleanup_inactive_users` apaga hoje as contas pendentes com mais de 7 dias (`api/management/commands/cleanup_inactive_users.py:16-29`), mas não está agendado em nenhum arquivo do repositório.
- Não existe endpoint nem tela de reenvio em nenhum dos dois repositórios.

### Falha no envio de e-mail

- Não bloqueia o cadastro: a conta é criada, e a tela avisa e oferece reenviar (AD-011).
- Hoje as views disparam `threading.Thread` (`api/views.py:54-59` e `:140-145`), e `send_verification_email` e `send_password_reset_email` só registram a falha no log (`api/utils/email_service.py:274-275` e `:351-352`).

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- E-mail sem diferença de caixa e cadastro com e-mail já existente.
- Remoção da rota `/api/token/`.
- Aviso de conta pendente ou desativada só com a senha correta.
- Redefinição por link que também confirma o e-mail.
- Tempo máximo do envio, falha no e-mail de redefinição, EmailJS e e-mails mascarados nos logs.
- Validade dos links e IP usado nos limites.
- Troca da `SECRET_KEY` e contas com e-mails que diferem só na caixa.

---

## Specific References

- O nome entra sem escape no HTML dos dois e-mails (`api/utils/email_service.py:213` e `:292`).
- A cadeia de envio tenta Resend, SMTP e EmailJS (`api/utils/email_service.py:141-196`); o SMTP não tem timeout, e o EmailJS usa `timeout=15` (`:129`).
- Os links usam `FRONTEND_URL`, com fallback para `http://localhost:3000` em produção apenas com um aviso no log (`api/utils/email_service.py:35-46`).
- O login com senha errada revela que a conta está inativa (`api/serializers.py:137-145`); a rota `/api/token/` usa outro serializer, sem essa mensagem (`api/urls.py:60`, `api/serializers_auth.py:5-21`).
- O "esqueci a senha" já responde de forma neutra (`api/views.py:151-158`), mas grava no log o e-mail não cadastrado inteiro (`api/views.py:153-156`).
- A tela de redefinição envia `password` (`fluxar-frontend/src/app/auth/reset-password/page.tsx:56`), e o backend exige `new_password` e `new_password_confirm` (`api/serializers.py:167-175`).
- A tela de cadastro transforma qualquer erro em mensagens genéricas (`fluxar-frontend/src/app/auth/register/page.tsx:83-87`).
- O `SECRET_KEY` tem fallback público (`core/settings.py:17`), e o CORS libera tudo quando a variável falta (`core/settings.py:184-188`).

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
