# Lgpd Specification

## Problem Statement

O Fluxar guarda e expõe dados pessoais além do necessário. CPF, telefone, data de nascimento e renda ficam em texto puro no banco, o CPF único deixa o perfil funcionar como consulta de "este CPF está cadastrado?" e o painel admin mostra o CPF inteiro. O usuário não consegue excluir a própria conta, e a exclusão feita pelo administrador deixa a foto de perfil no Cloudinary. Os logs registram o e-mail inteiro a cada login, em todo envio de e-mail e junto de pedaços de tokens (SEG-09).

Origem: `docs/auditoria-2026-09.md`, seção 3 (SEG-09).

## Goals

- [ ] O usuário exclui a própria conta sozinho, com 30 dias para desistir, e depois disso nenhum dado pessoal ou financeiro dele fica no banco nem no Cloudinary.
- [ ] Dados pessoais que o app não usa para buscas ficam criptografados no banco e aparecem mascarados para o administrador.
- [ ] Nenhum log contém dado pessoal ou financeiro que identifique alguém.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Exportação dos dados pessoais fora do fluxo de exclusão (portabilidade) | Não foi pedida; a exportação de transações já cobre parte dela |
| Texto da política de privacidade e dos termos, gestão de consentimento e encarregado de dados | Não foi pedido |
| Dados guardados por terceiros (Resend, Brevo, Render) e backups do banco | Seguem a retenção de cada provedor |
| Logs já gravados na plataforma do Render | Ficam fora do alcance do app e expiram pela retenção do provedor |
| Foto pessoal e imagens na pasta `media/` do repositório (OPS-07) | Higiene do repositório |
| Limpeza de dados feita pelo administrador sem excluir a conta | Painel admin |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| A exclusão apaga tudo ou anonimiza | Apaga tudo; fica só um registro da exclusão, sem dados pessoais | Decisão do usuário (AD-018) | sim |
| Dados financeiros na exclusão | O usuário pode baixá-los em XLSX antes de confirmar, qualquer que seja o plano; depois são apagados junto com a conta | Decisão do usuário (AD-018) | sim |
| Prazo para desistir | 30 dias: a conta é desativada na hora, e a exclusão definitiva roda sozinha no fim do prazo | Decisão do usuário (AD-018) | sim |
| Dados criptografados no banco | CPF, telefone, data de nascimento e renda mensal, com uma chave própria obrigatória em produção (AD-020) | São dados pessoais que o app só exibe e não usa para buscar ou somar | sim |
| CPF único | Deixa de ser único e passa a ser validado pelos dígitos verificadores | A unicidade não tem uso no app e faz o perfil revelar se um CPF está cadastrado | sim |
| Dados pessoais no painel admin | CPF e telefone mascarados, com só os últimos dígitos; renda e data de nascimento ocultas | O administrador não precisa desses dados para dar suporte | sim |
| Nome das imagens enviadas | Aleatório, sem o nome original do arquivo | O nome original pode conter o nome da pessoa | sim |
| Confirmação do pedido de exclusão | Senha atual | Impede que alguém com uma sessão aberta alheia apague a conta | sim |
| Aviso do pedido de exclusão | Um e-mail com a data da exclusão definitiva e como desistir; se o envio falhar, o pedido vale mesmo assim, e a tela mostra a data | Segue AD-011: o e-mail não bloqueia a operação | sim |
| Login durante o prazo | Responde com o código `deletion_pending`, a data e a opção de cancelar, sem abrir a sessão | O usuário só volta a usar o app se cancelar a exclusão | sim |
| "Esqueci a senha" durante o prazo | Funciona, mas não cancela a exclusão | O cancelamento precisa ser uma escolha explícita | sim |
| Exclusão pelo administrador | Imediata, com a mesma limpeza e o mesmo registro | O administrador decide excluir na hora | sim |
| Falha no meio da exclusão definitiva | A conta continua desativada e marcada, e a rotina tenta de novo na execução seguinte | Nunca sobra uma conta apagada pela metade | sim |
| Registro da exclusão | Identificador interno da conta, datas do pedido e da exclusão e quem executou (usuário, rotina ou administrador) | Permite auditoria sem guardar dado pessoal | sim |
| O que nunca aparece em log | E-mail completo, nome, CPF, telefone, nascimento, renda, senha, token ou parte dele, conteúdo de requisição, e descrição, valor ou nome de conta, cartão, categoria ou meta (AD-019) | São os dados que hoje vazam em `print` e em `logger` | sim |
| Dados já gravados | Na implantação, os dados pessoais existentes são criptografados e os e-mails nas descrições do log de auditoria são mascarados | Corrige o que já está no banco sem ação do usuário | sim |**Open questions:** none. As suposições da tabela foram aprovadas pelo usuário em 2026-09-26.

---

## User Stories

### P1: Pedido de exclusão da própria conta ⭐ MVP

**User Story**: Como usuário, quero excluir minha conta pelo app, levar meus dados financeiros antes e ter um prazo para desistir.

**Why P1**: hoje o usuário não tem como excluir a própria conta (SEG-09), um direito previsto na LGPD.

**Acceptance Criteria**:
1. **LGPD-01** WHEN o usuário abre as configurações da conta THEN a interface SHALL oferecer a opção "Excluir minha conta".
2. **LGPD-02** WHEN o usuário inicia a exclusão THEN a interface SHALL oferecer o download dos dados financeiros em XLSX antes da confirmação, qualquer que seja o plano do usuário.
3. **LGPD-03** WHEN o usuário confirma a exclusão THEN o sistema SHALL exigir a senha atual.
4. **LGPD-04** IF a senha informada na confirmação estiver errada THEN o sistema SHALL recusar o pedido com HTTP 400 e o erro no campo da senha, sem mudar nada na conta.
5. **LGPD-05** WHEN a exclusão é confirmada com a senha correta THEN o sistema SHALL desativar a conta, encerrar todas as sessões dela e marcar a exclusão definitiva para 30 dias depois.
6. **LGPD-06** WHEN a exclusão é confirmada THEN o sistema SHALL enviar ao usuário um e-mail com a data da exclusão definitiva e a forma de desistir.
7. **LGPD-07** WHEN uma conta com exclusão marcada tenta entrar com a senha correta THEN o sistema SHALL responder com o código `deletion_pending`, a data da exclusão definitiva e a opção de cancelar, sem abrir a sessão.
8. **LGPD-08** WHEN o usuário cancela a exclusão dentro do prazo THEN o sistema SHALL reativar a conta com todos os dados e abrir a sessão.
9. **LGPD-09** IF o único administrador ativo pedir a exclusão da própria conta THEN o sistema SHALL recusar o pedido com HTTP 400 e a mensagem "O sistema precisa ter pelo menos um administrador ativo."

**Independent Test**: um usuário do plano Comum baixa o XLSX, confirma a exclusão com a senha e é deslogado em todos os aparelhos; ao entrar de novo, recebe `deletion_pending` com a data, cancela e volta com todos os dados.

---

### P1: Exclusão definitiva ⭐ MVP

**User Story**: Como usuário que excluiu a conta, quero ter certeza de que nada meu ficou guardado depois do prazo.

**Why P1**: hoje a exclusão pelo administrador deixa a foto de perfil no Cloudinary, e não existe exclusão agendada.

**Acceptance Criteria**:
1. **LGPD-10** WHEN a data da exclusão definitiva chega THEN a rotina diária SHALL apagar a conta e todos os dados dela: contas, cartões, faturas, transações e séries, categorias, tags, orçamentos, metas e aportes, monitores de foco, imagens no Cloudinary, tokens, registros de pagamento e o log de auditoria ligado ao usuário.
2. **LGPD-11** WHEN uma exclusão definitiva termina THEN o sistema SHALL guardar apenas um registro com o identificador interno da conta, a data do pedido, a data da exclusão e quem a executou (o usuário, a rotina ou um administrador), sem nenhum dado pessoal.
3. **LGPD-12** IF a remoção das imagens no Cloudinary ou qualquer outra etapa da exclusão definitiva falhar THEN o sistema SHALL manter a conta desativada e marcada para exclusão, sem apagar parte dos dados, e tentar de novo na execução seguinte da rotina.
4. **LGPD-13** WHEN um administrador exclui uma conta definitivamente THEN o sistema SHALL apagar, na hora, os mesmos dados de LGPD-10 e guardar o registro de LGPD-11.
5. **LGPD-14** WHEN uma exclusão definitiva termina THEN o sistema SHALL deixar o e-mail da conta livre para um novo cadastro.

**Independent Test**: com a data de uma exclusão pendente simulada como vencida, a rotina apaga a conta, os dados financeiros e as imagens no Cloudinary, e só o registro sem dados pessoais continua no banco; com o Cloudinary fora do ar, a conta continua desativada e inteira até a próxima execução.

---

### P1: Guarda dos dados pessoais ⭐ MVP

**User Story**: Como usuário, quero que meus dados pessoais fiquem protegidos mesmo que alguém tenha acesso ao banco ou ao painel admin.

**Why P1**: hoje CPF, telefone, nascimento e renda ficam em texto puro, e o painel mostra o CPF inteiro (SEG-09).

**Acceptance Criteria**:
1. **LGPD-15** WHEN CPF, telefone, data de nascimento ou renda mensal são gravados THEN o sistema SHALL guardá-los criptografados no banco.
2. **LGPD-16** IF o backend iniciar em produção sem a chave de criptografia dos dados pessoais THEN o sistema SHALL interromper a inicialização com um erro que nomeie a variável.
3. **LGPD-17** IF o CPF informado não tiver dígitos verificadores válidos THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "CPF inválido."
4. **LGPD-18** WHEN um usuário informa um CPF que outra conta já usa THEN o sistema SHALL aceitá-lo como qualquer outro, sem revelar a existência da outra conta.
5. **LGPD-19** WHEN um administrador consulta os dados de um usuário no painel THEN o sistema SHALL mostrar o CPF e o telefone mascarados, com só os últimos dígitos visíveis, e não mostrar a renda nem a data de nascimento.
6. **LGPD-20** WHEN uma foto de perfil ou uma imagem de meta é enviada THEN o sistema SHALL guardá-la com um nome aleatório, sem o nome original do arquivo.

**Independent Test**: depois de salvar o perfil, a coluna do CPF no banco não contém os dígitos em claro, o próprio usuário vê o CPF completo e o painel admin mostra `***.***.***-12`; um CPF com dígito verificador errado recebe 400, e dois usuários salvam o mesmo CPF válido sem erro.

---

### P1: Dados pessoais fora dos logs ⭐ MVP

**User Story**: Como usuário, quero que meus dados não apareçam nos logs do sistema, que mais gente acessa e que ficam guardados por terceiros.

**Why P1**: hoje o e-mail inteiro aparece a cada login e em todo envio de e-mail, junto com pedaços de tokens e payloads de requisição.

**Acceptance Criteria**:
1. **LGPD-21** WHEN o sistema escreve um log ou um registro de auditoria THEN o sistema SHALL não incluir e-mail completo, nome, CPF, telefone, data de nascimento, renda, senha, token ou parte de token, conteúdo de requisição, nem descrição, valor ou nome de conta, cartão, categoria ou meta.
2. **LGPD-22** WHEN um log ou registro de auditoria precisa identificar um usuário THEN o sistema SHALL usar o identificador interno ou o e-mail mascarado (por exemplo, `an***@x.com`).
3. **LGPD-23** WHILE o backend estiver em execução, o sistema SHALL escrever mensagens só pelo log com nível, sem nenhum `print`.

**Independent Test**: rodar toda a suíte de testes com a captura de logs ligada e procurar, na saída, e-mails completos, CPFs, tokens e valores monetários: nenhuma ocorrência.

---

### P2: Dados já gravados

**User Story**: Como responsável pelo Fluxar, quero que os dados já gravados passem a seguir as mesmas regras quando a correção entrar no ar.

**Why P2**: os usuários atuais já têm CPF e renda em texto puro, e o log de auditoria já guarda e-mails de contas apagadas.

**Acceptance Criteria**:
1. **LGPD-24** WHEN a correção é implantada THEN o sistema SHALL criptografar o CPF, o telefone, a data de nascimento e a renda já gravados.
2. **LGPD-25** WHEN a correção é implantada THEN o sistema SHALL mascarar os e-mails já gravados nas descrições do log de auditoria.

**Independent Test**: numa cópia do banco de produção, depois da correção, nenhuma linha de usuário tem esses quatro dados em claro, os perfis mostram os mesmos valores de antes e nenhuma descrição do log de auditoria contém um e-mail completo.

---

## Edge Cases

- Pedido de exclusão com sessão aberta em outro aparelho: todas as sessões terminam (LGPD-05, SESSAO-17).
- Cadastro com o e-mail de uma conta em exclusão: recusado como em AUTH-03; o dono pode entrar e cancelar a exclusão (LGPD-07).
- "Esqueci a senha" durante o prazo: funciona, mas não cancela a exclusão; depois de redefinir a senha, o login mostra a opção de cancelar (LGPD-07).
- Exportação travada pelo plano: o download do XLSX dentro do fluxo de exclusão continua liberado (LGPD-02).
- Rotina diária fora do ar por alguns dias: a exclusão acontece na primeira execução seguinte (LGPD-10, LGPD-12).
- Administrador exclui uma conta que já estava em exclusão pendente: ela é apagada na hora (LGPD-13).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | LGPD-04, LGPD-17 |
| Falha e falha parcial | LGPD-12 |
| Idempotência, repetição e duplicidade | LGPD-12 (a rotina retoma a mesma exclusão sem duplicar o registro) |
| Autorização e rate limiting | LGPD-03, LGPD-04, LGPD-09, LGPD-19; o limite de tentativas do login segue AUTH-31 e AUTH-32 |
| Concorrência e ordem | N/A because uma conta com exclusão marcada não consegue abrir sessão para pedir outra exclusão |
| Ciclo de vida dos dados | LGPD-05, LGPD-10, LGPD-11, LGPD-14, LGPD-24 |
| Observabilidade | LGPD-11, LGPD-21 a LGPD-23 |
| Falha de dependência externa | LGPD-06 (e-mail), LGPD-12 (Cloudinary) |
| Integridade das transições de estado | LGPD-05, LGPD-07, LGPD-08, LGPD-10 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| LGPD-01 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-02 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-03 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-04 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-05 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-06 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-07 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-08 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-09 | P1: Pedido de exclusão da própria conta | - | Pending |
| LGPD-10 | P1: Exclusão definitiva | - | Pending |
| LGPD-11 | P1: Exclusão definitiva | - | Pending |
| LGPD-12 | P1: Exclusão definitiva | - | Pending |
| LGPD-13 | P1: Exclusão definitiva | - | Pending |
| LGPD-14 | P1: Exclusão definitiva | - | Pending |
| LGPD-15 | P1: Guarda dos dados pessoais | - | Pending |
| LGPD-16 | P1: Guarda dos dados pessoais | - | Pending |
| LGPD-17 | P1: Guarda dos dados pessoais | - | Pending |
| LGPD-18 | P1: Guarda dos dados pessoais | - | Pending |
| LGPD-19 | P1: Guarda dos dados pessoais | - | Pending |
| LGPD-20 | P1: Guarda dos dados pessoais | - | Pending |
| LGPD-21 | P1: Dados pessoais fora dos logs | - | Pending |
| LGPD-22 | P1: Dados pessoais fora dos logs | - | Pending |
| LGPD-23 | P1: Dados pessoais fora dos logs | - | Pending |
| LGPD-24 | P2: Dados já gravados | - | Pending |
| LGPD-25 | P2: Dados já gravados | - | Pending |

**Coverage:** 25 total, 0 mapped to tasks, 25 unmapped ⚠️ (design e tasks ainda não iniciados)

---

## Success Criteria

- [ ] Um usuário consegue excluir a própria conta sem ajuda, e 30 dias depois nenhuma linha do banco nem arquivo no Cloudinary contém dados dele, além do registro sem dados pessoais.
- [ ] Nenhum log gerado durante a suíte de testes contém e-mail completo, CPF, token ou valor monetário.
- [ ] Nenhum dos quatro dados pessoais fica em claro no banco.
