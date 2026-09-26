# Autenticacao Specification

## Problem Statement

A entrada no Fluxar tem falhas de segurança e fluxos quebrados. Login, cadastro e "esqueci a senha" não têm limite de tentativas, e o nome do usuário entra sem escape no HTML dos e-mails, o que permite força bruta e phishing com o remetente oficial (SEG-02). A `SECRET_KEY` e o CORS falham abertos em produção (SEG-03). A redefinição de senha nunca funciona, porque o frontend e o backend usam campos diferentes (CON-01). Os e-mails saem em threads soltas, sem reenvio de verificação, e uma conta não verificada pode ser apagada sem aviso (OPS-05).

Origem: `docs/auditoria-2026-09.md`, seções 3 (SEG-02, SEG-03, SEG-09, SEG-10, SEG-11, SEG-12), 4 (CON-01), 5 (FE-04, FE-05, FE-08) e 7 (OPS-05).

## Goals

- [ ] Todo fluxo de entrada (cadastro, verificação, login, "esqueci a senha" e redefinição) funciona de ponta a ponta nos dois repositórios.
- [ ] Nenhuma rota de autenticação aceita tentativas ilimitadas, e nenhuma resposta revela se um e-mail está cadastrado quando isso não é necessário.
- [ ] Nenhum e-mail se perde sem que o usuário possa pedir outro, e nenhum texto do usuário entra sem escape no HTML.
- [ ] O backend não sobe em produção com configuração insegura.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Duração, renovação e encerramento da sessão, e revogação dos tokens ao trocar a senha (SEG-05) | Feature `sessao` |
| Troca de senha com o usuário logado | Fluxo do perfil; não foi pedido |
| Redefinição de senha feita pelo administrador | Painel admin |
| Login social e autenticação em dois fatores | Não existem e não foram pedidos |
| Captcha no cadastro | Não foi pedido; os limites de tentativas cobrem o abuso previsto |
| HSTS, redirecionamento para HTTPS e cookies seguros do admin do Django (SEG-13) | Configuração de transporte; fica numa feature de infraestrutura |
| URL da API no frontend com fallback para `localhost` (SEG-14) | Configuração do frontend; fica numa feature de infraestrutura |
| Exclusão da conta pelo próprio usuário (SEG-09) | Feature de privacidade |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Limite de tentativas de cada rota | Login: 5 por minuto por IP e 10 falhas por hora por e-mail. Cadastro: 5 por hora por IP. "Esqueci a senha" e reenvio de verificação: 3 por hora por e-mail e 10 por hora por IP. Verificação e redefinição por link: 20 por hora por IP | Decisão do usuário | sim |
| Conta que não verificou o e-mail | Fica aguardando, sem exclusão automática; o login avisa e oferece reenviar o link | Decisão do usuário | sim |
| Falha no envio do e-mail de verificação | Não bloqueia o cadastro: a conta é criada, e a tela avisa e oferece reenviar | Decisão do usuário (AD-011) | sim |
| E-mail com maiúsculas e minúsculas diferentes | É o mesmo e-mail em todos os fluxos, guardado em minúsculas | Hoje "Ana@x.com" e "ana@x.com" viram contas diferentes (SEG-11) | sim |
| Cadastro com e-mail já cadastrado | Recusado com mensagem explícita e a dica de usar "Esqueci a senha" | Ajuda quem já tem conta; os limites de tentativas freiam a varredura de e-mails | sim |
| Rota antiga `/api/token/` | Removida; o login é só por `/api/auth/login/` | Uma segunda rota contornaria os limites e as mensagens (SEG-12); o frontend não a usa | sim |
| Aviso de conta não verificada ou desativada no login | Só aparece com a senha correta; com a senha errada, a mensagem é sempre a mesma | Hoje o aviso revela que a conta existe mesmo com a senha errada (SEG-10) | sim |
| Redefinição de senha por link numa conta não verificada | Também confirma o e-mail e ativa a conta | Quem cadastrou o e-mail de outra pessoa perde o acesso quando o dono do e-mail redefine a senha | sim |
| Tempo máximo do envio de e-mail | 10 segundos no total, somando os provedores | Cabe na requisição sem travar o cadastro; hoje o SMTP não tem timeout | sim |
| Falha no envio do e-mail de redefinição | A resposta continua neutra, e a falha vai para o log | Dizer que o envio falhou revelaria que o e-mail está cadastrado | sim |
| EmailJS | Desligado em produção | É um fallback de teste e usa uma chave privada | sim |
| E-mails nos logs | Sempre mascarados (por exemplo, `an***@x.com`) | Hoje o "esqueci a senha" e a limpeza de contas gravam e-mails inteiros (SEG-09) | sim |
| Validade dos links | 24 horas para a verificação e 1 hora para a redefinição | É o comportamento atual | sim |
| IP usado nos limites | O IP do cliente informado pelo proxy do Render | Atrás do proxy, o IP da conexão é sempre o do próprio proxy | sim |
| Troca da `SECRET_KEY` na implantação | Encerra todas as sessões abertas, e os usuários entram de novo | A chave original está no histórico público do repositório (SEG-03) | sim |
| Contas existentes com e-mails que diferem só na caixa | São listadas e ficam como estão até uma resolução manual | Juntar duas contas automaticamente poderia misturar dados de pessoas diferentes | sim |

**Open questions:** none. As suposições da tabela foram aprovadas pelo usuário em 2026-09-26.

---

## User Stories

### P1: Cadastro ⭐ MVP

**User Story**: Como visitante, quero criar minha conta e entender na hora o que precisa ser corrigido no formulário.

**Why P1**: hoje qualquer erro de e-mail aparece como "já está em uso" e uma senha comum mostra "Tente novamente mais tarde" (FE-08).

**Acceptance Criteria**:
1. **AUTH-01** WHEN o visitante se cadastra com nome, e-mail, senha, confirmação e aceite dos termos válidos THEN o sistema SHALL criar a conta como não verificada e enviar o e-mail de verificação.
2. **AUTH-02** WHEN um e-mail é cadastrado ou comparado com os existentes THEN o sistema SHALL ignorar a diferença entre maiúsculas e minúsculas e guardá-lo em minúsculas.
3. **AUTH-03** IF o e-mail já estiver cadastrado THEN o sistema SHALL recusar o cadastro com HTTP 400 e a mensagem "Este e-mail já está cadastrado. Se a conta é sua, use \"Esqueci a senha\"." no campo do e-mail.
4. **AUTH-04** IF a senha tiver menos de 8 caracteres, for parecida com o nome ou o e-mail, for comum, tiver só números ou for diferente da confirmação THEN o sistema SHALL recusar o cadastro com HTTP 400 e o motivo no campo da senha.
5. **AUTH-05** IF o nome estiver vazio ou passar de 255 caracteres, ou o aceite dos termos não vier marcado, THEN o sistema SHALL recusar o cadastro com HTTP 400 e o motivo no campo correspondente.
6. **AUTH-06** WHEN dois cadastros com o mesmo e-mail chegam ao mesmo tempo THEN o sistema SHALL criar uma única conta e responder ao outro pedido conforme AUTH-03.
7. **AUTH-07** WHEN o cadastro é recusado THEN a interface SHALL mostrar cada erro no campo correspondente, com a mensagem enviada pelo backend.

**Independent Test**: cadastrar "Ana@X.com" cria a conta como "ana@x.com", pendente de verificação; cadastrar "ana@x.com" de novo, uma senha "12345678" e um cadastro sem o aceite recebem 400, cada um com a mensagem no campo certo da tela.

---

### P1: Verificação de e-mail e conta não verificada ⭐ MVP

**User Story**: Como usuário recém-cadastrado, quero confirmar meu e-mail quando puder e pedir um novo link se o primeiro não chegar ou expirar.

**Why P1**: hoje não existe reenvio, e uma conta não verificada pode ser apagada em 7 dias (OPS-05).

**Acceptance Criteria**:
1. **AUTH-08** WHEN o usuário abre um link de verificação válido THEN o sistema SHALL confirmar o e-mail, ativar a conta e iniciar a sessão.
2. **AUTH-09** IF o link de verificação estiver expirado (mais de 24 horas), já tiver sido usado ou tiver sido substituído por um mais novo THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "Link inválido ou expirado.", e a interface SHALL oferecer reenviar o e-mail.
3. **AUTH-10** WHEN o usuário pede o reenvio da verificação para uma conta pendente THEN o sistema SHALL enviar um novo link e invalidar os anteriores.
4. **AUTH-11** WHEN o reenvio é pedido para um e-mail inexistente ou já verificado THEN o sistema SHALL responder da mesma forma que para uma conta pendente ("Se houver uma conta aguardando verificação com este e-mail, enviamos um novo link."), sem enviar nada.
5. **AUTH-12** WHILE uma conta estiver aguardando verificação, o sistema SHALL mantê-la sem nenhuma exclusão automática.
6. **AUTH-13** WHEN uma conta não verificada tenta entrar com a senha correta THEN o sistema SHALL recusar o login com HTTP 400, o código `email_not_verified` e a mensagem "Confirme seu e-mail para entrar.", e a interface SHALL oferecer reenviar o link.

**Independent Test**: cadastrar, esperar o link vencer (simulando 25 horas), abri-lo e receber 400 com a oferta de reenvio; pedir o reenvio, abrir o link novo e entrar direto; o link antigo continua recusado. Uma conta pendente há 60 dias continua existindo.

---

### P1: Login ⭐ MVP

**User Story**: Como usuário, quero entrar com meu e-mail e senha e receber uma mensagem clara, sem que o sistema revele dados da conta para quem não sabe a senha.

**Why P1**: hoje o login revela que uma conta existe e está inativa mesmo com a senha errada (SEG-10), e uma segunda rota de login escapa das regras (SEG-12).

**Acceptance Criteria**:
1. **AUTH-14** WHEN o usuário entra com e-mail e senha corretos de uma conta verificada e ativa THEN o sistema SHALL iniciar a sessão.
2. **AUTH-15** IF o e-mail não estiver cadastrado ou a senha estiver errada THEN o sistema SHALL recusar o login com HTTP 400 e a mesma mensagem nos dois casos: "E-mail ou senha incorretos."
3. **AUTH-16** WHEN uma conta desativada pelo administrador tenta entrar com a senha correta THEN o sistema SHALL recusar o login com HTTP 400 e a mensagem "Esta conta está desativada."
4. **AUTH-17** IF uma requisição usar a rota antiga `/api/token/` THEN o sistema SHALL responder HTTP 404.

**Independent Test**: com uma conta verificada, uma pendente e uma desativada, a senha errada devolve "E-mail ou senha incorretos." para as três e para um e-mail inexistente; a senha certa entra na verificada e devolve as mensagens de AUTH-13 e AUTH-16 nas outras duas.

---

### P1: Esqueci a senha e redefinição ⭐ MVP

**User Story**: Como usuário que esqueceu a senha, quero receber um link e criar uma senha nova.

**Why P1**: hoje a redefinição nunca funciona, porque o frontend envia `password` e o backend exige `new_password` e `new_password_confirm` (CON-01).

**Acceptance Criteria**:
1. **AUTH-18** WHEN o usuário pede a redefinição de senha para um e-mail THEN o sistema SHALL responder HTTP 200 com a mensagem "Se o e-mail estiver cadastrado, enviamos um link para redefinir a senha.", exista ou não a conta.
2. **AUTH-19** WHEN a redefinição é pedida para um e-mail cadastrado THEN o sistema SHALL enviar um link válido por 1 hora e invalidar os links de redefinição anteriores.
3. **AUTH-20** WHEN o usuário envia uma nova senha válida com um link de redefinição válido THEN o sistema SHALL trocar a senha, invalidar o link, confirmar o e-mail e ativar a conta se ela só estava pendente de verificação.
4. **AUTH-21** IF o link de redefinição estiver expirado ou já tiver sido usado THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "Link inválido ou expirado.", e a interface SHALL oferecer pedir um novo.
5. **AUTH-22** IF a nova senha não passar pelas regras de AUTH-04 ou for diferente da confirmação THEN o sistema SHALL recusá-la com HTTP 400 e o motivo no campo da senha.
6. **AUTH-23** WHEN a interface envia a redefinição THEN o sistema SHALL enviar os campos `token`, `new_password` e `new_password_confirm`.

**Independent Test**: pedir a redefinição, abrir o link, definir uma senha nova e entrar com ela; reabrir o mesmo link devolve "Link inválido ou expirado."; pedir a redefinição para um e-mail inexistente devolve a mesma mensagem de AUTH-18.

---

### P1: E-mails transacionais ⭐ MVP

**User Story**: Como usuário, quero receber e-mails do Fluxar que não possam ser usados por terceiros para me enganar, e saber quando um deles não saiu.

**Why P1**: hoje o nome entra sem escape no HTML (SEG-02) e o envio roda em threads soltas, sem aviso de falha (OPS-05).

**Acceptance Criteria**:
1. **AUTH-24** WHEN um e-mail transacional é montado THEN o sistema SHALL escapar no HTML todo texto vindo do usuário, como o nome (um nome `<a href="x">clique</a>` aparece como texto, sem virar link).
2. **AUTH-25** WHEN um e-mail transacional é enviado THEN o sistema SHALL tentar os provedores em ordem (Resend e depois SMTP) dentro da própria requisição, com no máximo 10 segundos no total e sem thread em segundo plano.
3. **AUTH-26** IF nenhum provedor conseguir enviar o e-mail de verificação THEN o sistema SHALL manter a conta criada e responder ao cadastro com HTTP 201, o campo `email_sent` igual a `false` e a mensagem "Conta criada, mas não conseguimos enviar o e-mail de verificação. Use \"Reenviar e-mail\".", e a interface SHALL oferecer o reenvio.
4. **AUTH-27** IF nenhum provedor conseguir enviar o e-mail de redefinição THEN o sistema SHALL manter a resposta de AUTH-18 e registrar a falha no log.
5. **AUTH-28** WHEN um e-mail é enviado ou falha THEN o sistema SHALL registrar no log o tipo do e-mail, o provedor usado e o resultado, com o endereço mascarado.
6. **AUTH-29** WHILE o backend estiver em produção, o sistema SHALL manter o EmailJS desligado.
7. **AUTH-30** WHEN um e-mail transacional traz um link THEN o sistema SHALL montá-lo a partir do `FRONTEND_URL` configurado.

**Independent Test**: cadastrar o nome `<a href="x">clique</a>` e ver o texto literal no e-mail; com os dois provedores fora do ar, o cadastro responde 201 com `email_sent: false` em até 10 segundos, e o log mostra as duas falhas com o e-mail mascarado.

---

### P1: Limites de tentativas ⭐ MVP

**User Story**: Como usuário, quero que ninguém consiga testar senhas na minha conta nem usar o Fluxar para mandar e-mails em massa.

**Why P1**: hoje nenhuma rota tem limite (SEG-02).

**Acceptance Criteria**:
1. **AUTH-31** WHEN um mesmo IP passa de 5 tentativas de login em 60 segundos THEN o sistema SHALL responder HTTP 429 às tentativas seguintes desse IP até o fim do período.
2. **AUTH-32** WHEN um mesmo e-mail acumula 10 tentativas de login com senha errada em 1 hora THEN o sistema SHALL responder HTTP 429 a qualquer tentativa de login com esse e-mail até completar a hora, inclusive com a senha correta.
3. **AUTH-33** WHEN um mesmo IP passa de 5 cadastros em 1 hora THEN o sistema SHALL responder HTTP 429 aos cadastros seguintes desse IP até completar a hora.
4. **AUTH-34** WHEN "esqueci a senha" ou o reenvio de verificação passa de 3 pedidos em 1 hora para o mesmo e-mail, ou de 10 pedidos em 1 hora para o mesmo IP, THEN o sistema SHALL responder HTTP 429 aos pedidos seguintes até completar a hora.
5. **AUTH-35** WHEN um mesmo IP passa de 20 tentativas em 1 hora de verificação de e-mail ou de redefinição por link THEN o sistema SHALL responder HTTP 429 às tentativas seguintes até completar a hora.
6. **AUTH-36** WHEN o sistema responde HTTP 429 THEN o sistema SHALL incluir o cabeçalho `Retry-After` e a mensagem "Muitas tentativas. Tente novamente em N minutos.", e a interface SHALL exibir essa mensagem.

**Independent Test**: seis logins seguidos do mesmo IP em um minuto recebem 429 na sexta tentativa, com `Retry-After`; dez senhas erradas para o mesmo e-mail, vindas de IPs diferentes, bloqueiam também a senha certa até a hora fechar; o quarto "esqueci a senha" para o mesmo e-mail em uma hora recebe 429.

---

### P1: Configuração dos tokens ⭐ MVP

**User Story**: Como responsável pelo Fluxar, quero que o backend se recuse a subir em produção com uma configuração que deixe forjar tokens ou chamar a API de qualquer site.

**Why P1**: hoje a `SECRET_KEY` tem um fallback público e o CORS libera todas as origens quando a variável falta (SEG-03).

**Acceptance Criteria**:
1. **AUTH-37** IF o backend iniciar em produção, com `DEBUG` desligado, sem `SECRET_KEY` definida THEN o sistema SHALL interromper a inicialização com um erro que nomeie a variável.
2. **AUTH-38** IF o backend iniciar em produção sem `FRONTEND_URL` definida THEN o sistema SHALL interromper a inicialização com um erro que nomeie a variável.
3. **AUTH-39** WHEN `CORS_ALLOWED_ORIGINS` não está definida THEN o sistema SHALL não liberar nenhuma origem.

**Independent Test**: subir o backend com `DEBUG=0` sem `SECRET_KEY`, e depois sem `FRONTEND_URL`, falha com erro que nomeia cada variável; sem `CORS_ALLOWED_ORIGINS`, uma chamada vinda de outra origem não recebe cabeçalho de CORS.

---

### P1: Rotas públicas sem sessão ⭐ MVP

**User Story**: Como usuário, quero abrir o link de verificação ou de redefinição mesmo num navegador com uma sessão antiga.

**Why P1**: hoje um token vencido faz as rotas públicas responderem 401, e o link de verificação falha (FE-04, FE-05).

**Acceptance Criteria**:
1. **AUTH-40** WHEN uma rota pública de autenticação (cadastro, login, verificação, reenvio, "esqueci a senha" ou redefinição) recebe um token de acesso inválido ou vencido THEN o sistema SHALL processá-la como anônima, sem responder 401.
2. **AUTH-41** WHEN a interface chama uma rota pública de autenticação THEN o sistema SHALL enviar a requisição sem token de acesso e não redirecionar para o login por causa da resposta dela.

**Independent Test**: num navegador com um token vencido, abrir o link de verificação confirma o e-mail normalmente, e o cadastro de outra conta funciona sem redirecionar para o login.

---

### P2: Implantação e dados existentes

**User Story**: Como responsável pelo Fluxar, quero que a implantação troque a chave comprometida e acerte os e-mails já gravados.

**Why P2**: a chave original está no histórico público (SEG-03), e contas antigas podem ter e-mails com maiúsculas (SEG-11).

**Acceptance Criteria**:
1. **AUTH-42** WHEN a correção é implantada THEN o sistema SHALL passar a usar uma `SECRET_KEY` de produção nova, diferente de qualquer chave presente no histórico do repositório.
2. **AUTH-43** WHEN a correção é implantada THEN o sistema SHALL converter para minúsculas o e-mail de todas as contas cujo e-mail em minúsculas não coincide com o de outra conta.
3. **AUTH-44** IF duas ou mais contas tiverem e-mails que só diferem na caixa THEN o sistema SHALL listá-las e mantê-las como estão até uma resolução manual.

**Independent Test**: numa cópia do banco com as contas "Ana@x.com" e "bia@X.com", e também "Caio@x.com" e "caio@x.com", a correção deixa "ana@x.com" e "bia@x.com" em minúsculas e lista o par do Caio sem alterá-lo.

---

## Edge Cases

- Alguém cadastra o e-mail de outra pessoa e não verifica: o dono do e-mail usa "Esqueci a senha" e assume a conta (AUTH-20).
- Link de verificação aberto duas vezes: a primeira confirma e entra; a segunda recebe "Link inválido ou expirado." (AUTH-08, AUTH-09).
- Reenvio pedido quatro vezes em uma hora: o quarto recebe 429 (AUTH-34).
- Conta desativada pelo administrador pede "esqueci a senha": recebe a resposta neutra, e a redefinição não a reativa (AUTH-18, AUTH-20).
- Login com "ANA@X.COM": entra na conta "ana@x.com" (AUTH-02).
- Provedor principal fora do ar e SMTP funcionando: o e-mail sai pelo SMTP, e o log registra a falha do primeiro (AUTH-25, AUTH-28).
- Com o limite de 10 senhas erradas por e-mail, um atacante consegue bloquear por até uma hora o login de um e-mail que conhece; o dono ainda pode redefinir a senha (AUTH-32, AUTH-18).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | AUTH-03 a AUTH-05, AUTH-09, AUTH-21, AUTH-22 |
| Falha e falha parcial | AUTH-26, AUTH-27 |
| Idempotência, repetição e duplicidade | AUTH-06, AUTH-10, AUTH-19 |
| Autorização e rate limiting | AUTH-15, AUTH-31 a AUTH-36, AUTH-40 |
| Concorrência e ordem | AUTH-06 |
| Ciclo de vida dos dados | AUTH-09, AUTH-12, AUTH-21, AUTH-43, AUTH-44 |
| Observabilidade | AUTH-28 |
| Falha de dependência externa | AUTH-25 a AUTH-27 |
| Integridade das transições de estado | AUTH-08, AUTH-13, AUTH-16, AUTH-20 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| AUTH-01 | P1: Cadastro | - | Pending |
| AUTH-02 | P1: Cadastro | - | Pending |
| AUTH-03 | P1: Cadastro | - | Pending |
| AUTH-04 | P1: Cadastro | - | Pending |
| AUTH-05 | P1: Cadastro | - | Pending |
| AUTH-06 | P1: Cadastro | - | Pending |
| AUTH-07 | P1: Cadastro | - | Pending |
| AUTH-08 | P1: Verificação de e-mail e conta não verificada | - | Pending |
| AUTH-09 | P1: Verificação de e-mail e conta não verificada | - | Pending |
| AUTH-10 | P1: Verificação de e-mail e conta não verificada | - | Pending |
| AUTH-11 | P1: Verificação de e-mail e conta não verificada | - | Pending |
| AUTH-12 | P1: Verificação de e-mail e conta não verificada | - | Pending |
| AUTH-13 | P1: Verificação de e-mail e conta não verificada | - | Pending |
| AUTH-14 | P1: Login | - | Pending |
| AUTH-15 | P1: Login | - | Pending |
| AUTH-16 | P1: Login | - | Pending |
| AUTH-17 | P1: Login | - | Pending |
| AUTH-18 | P1: Esqueci a senha e redefinição | - | Pending |
| AUTH-19 | P1: Esqueci a senha e redefinição | - | Pending |
| AUTH-20 | P1: Esqueci a senha e redefinição | - | Pending |
| AUTH-21 | P1: Esqueci a senha e redefinição | - | Pending |
| AUTH-22 | P1: Esqueci a senha e redefinição | - | Pending |
| AUTH-23 | P1: Esqueci a senha e redefinição | - | Pending |
| AUTH-24 | P1: E-mails transacionais | - | Pending |
| AUTH-25 | P1: E-mails transacionais | - | Pending |
| AUTH-26 | P1: E-mails transacionais | - | Pending |
| AUTH-27 | P1: E-mails transacionais | - | Pending |
| AUTH-28 | P1: E-mails transacionais | - | Pending |
| AUTH-29 | P1: E-mails transacionais | - | Pending |
| AUTH-30 | P1: E-mails transacionais | - | Pending |
| AUTH-31 | P1: Limites de tentativas | - | Pending |
| AUTH-32 | P1: Limites de tentativas | - | Pending |
| AUTH-33 | P1: Limites de tentativas | - | Pending |
| AUTH-34 | P1: Limites de tentativas | - | Pending |
| AUTH-35 | P1: Limites de tentativas | - | Pending |
| AUTH-36 | P1: Limites de tentativas | - | Pending |
| AUTH-37 | P1: Configuração dos tokens | - | Pending |
| AUTH-38 | P1: Configuração dos tokens | - | Pending |
| AUTH-39 | P1: Configuração dos tokens | - | Pending |
| AUTH-40 | P1: Rotas públicas sem sessão | - | Pending |
| AUTH-41 | P1: Rotas públicas sem sessão | - | Pending |
| AUTH-42 | P2: Implantação e dados existentes | - | Pending |
| AUTH-43 | P2: Implantação e dados existentes | - | Pending |
| AUTH-44 | P2: Implantação e dados existentes | - | Pending |

**Coverage:** 44 total, 0 mapped to tasks, 44 unmapped ⚠️ (design e tasks ainda não iniciados)

---

## Success Criteria

- [ ] Um teste de ponta a ponta cobre cadastro, verificação, reenvio, login, "esqueci a senha" e redefinição nos dois repositórios, sem nenhum passo manual.
- [ ] Nenhuma rota de autenticação aceita mais tentativas do que os limites de AUTH-31 a AUTH-35.
- [ ] O backend não sobe em produção sem `SECRET_KEY` ou `FRONTEND_URL`.
