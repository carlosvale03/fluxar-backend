# Lgpd Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/lgpd/spec.md`
**Status:** Spec aprovada; design não iniciado

---

## Feature Boundary

Como os dados pessoais são guardados, a exclusão da própria conta pelo usuário e o que pode ou não aparecer nos logs.

---

## Implementation Decisions

### Apagar tudo ou anonimizar

- Apaga tudo; fica só um registro da exclusão sem dados pessoais (AD-018).

### Dados financeiros na exclusão

- O usuário pode baixá-los em XLSX antes de confirmar, qualquer que seja o plano, e depois eles são apagados. A exportação dentro do fluxo de exclusão entra nos recursos essenciais da spec `permissoes-e-planos`.

### Prazo para desistir

- 30 dias, com a conta desativada na hora e a exclusão definitiva feita por uma rotina diária agendada.

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Quais dados ficam criptografados e o fim da unicidade do CPF.
- Máscaras no painel admin e nome aleatório das imagens.
- Confirmação por senha, e-mail do pedido, login e "esqueci a senha" durante o prazo.
- Exclusão pelo administrador, falha no meio da exclusão e conteúdo do registro.
- O que nunca aparece em log.
- Correção dos dados já gravados.

---

## Specific References

- CPF, telefone, data de nascimento e renda ficam em texto puro, e o CPF é único (`api/models.py:46-56`); a validação só confere 11 dígitos (`api/serializers.py:77-85`).
- O painel admin mostra o CPF inteiro (`fluxar-frontend/src/app/(admin)/admin/usuarios/[id]/page.tsx:380`), e o `AdminUserSerializer` herda todos os campos do perfil (`api/serializers.py:115-121`).
- Não existe rota de exclusão da própria conta em `api/urls.py`; a exclusão pelo administrador apaga em cascata (`api/views.py:422-430` e `:661-679`).
- A foto de perfil só é removida do Cloudinary quando é trocada (`api/signals.py:9-30`); as imagens de meta são removidas quando a meta é apagada (`goals/signals.py:106-114`).
- O `SystemLog` apaga em cascata junto com o usuário (`api/models.py:113`), e a limpeza de contas grava até 10 e-mails na descrição (`api/management/commands/cleanup_inactive_users.py:32-36`).

Onde há dado pessoal ou financeiro em log hoje:

| Onde | O que vaza |
| ---- | ---------- |
| `core/services/plan_limits.py:32` e `:40` | `print` com o e-mail do usuário a cada login (`:32`) e com a contagem de contas (`:40`) |
| `api/views.py:60-64` e `:146-150` | E-mail completo e os 8 primeiros caracteres do token de verificação e de redefinição |
| `api/views.py:153-156` | E-mail não cadastrado pedido no "esqueci a senha" |
| `api/utils/email_service.py:67`, `:82`, `:138`, `:275` e `:352` | E-mail completo em cada envio e em cada falha |
| `transactions/views.py:40`, `:44` e `:46` | `print` com o payload inteiro da criação de categoria |
| `goals/views.py:52` e `:82` | `print` com o valor do aporte e do resgate |
| `transactions/services.py:166` | `print` com o nome do cartão |

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
