# Painel admin Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/painel-admin/spec.md`
**Status:** Spec aprovada; design não iniciado

---

## Feature Boundary

As telas do painel sem dados falsos, o log de auditoria das ações de administradores e as operações sobre usuários: busca, mudança de plano, papel e status, redefinição de senha, limpeza de dados e exclusão definitiva. Quem é administrador, as travas dos planos, o modo manutenção e a exclusão pela LGPD já estão nas specs `permissoes-e-planos`, `sessao` e `lgpd`.

---

## Implementation Decisions

### Receita e assinatura

- Saem do painel até existir cobrança; "Assinaturas ativas" vira "Usuários em planos pagos".

### Limpar dados

- Tudo ou nada, e o usuário fica como um cadastro novo, com categorias padrão, classes e a conta Carteira.

### Log de auditoria

- Registra todas as ações de administradores, com quem, quando, o quê e o usuário afetado (AD-030).

### Senha do administrador

- Pedida só nas ações sensíveis: excluir, limpar dados, redefinir senha, mudar papel e desativar conta.

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Saúde e versão do sistema.
- Identificação no log, log depois da exclusão da conta, filtros e log somente leitura.
- Confirmação por e-mail digitado, o que a limpeza mantém e as imagens das metas.
- Busca de usuários, estatísticas financeiras e limpeza dos próprios dados.

---

## Specific References

- A tela de detalhes do usuário cai num usuário de exemplo quando a API falha (`fluxar-frontend/src/services/admin.ts:107-109`, SEG-07).
- A tela de configurações espera uma lista e recebe o log paginado (`fluxar-frontend/src/app/(admin)/admin/configuracoes/page.tsx:32`), mostra "Uptime: 99.9% (30d)" e "PostgreSQL 15.4" fixos (`:135` e `:165`) e tem um "Limpar Cache" que só espera 2 segundos (`:69-71` e `:221`).
- O dashboard do admin mostra "ASSINATURAS ATIVAS" para os usuários Premium e Premium Plus e "API HEALTH CHECK OK" fixo (`fluxar-frontend/src/app/(admin)/admin/dashboard/page.tsx:71` e `:87`). O backend já mede o banco, mas devolve `status` "Operacional" e `api_version` "1.2.5" fixos, além da receita estimada com R$ 19,90 e R$ 39,90 (`api/views.py:467-514`).
- A aba "Assinatura" do usuário é simulada, com "R$ 29,90" e "#TRX-9902" (`fluxar-frontend/src/app/(admin)/admin/usuarios/[id]/page.tsx:467-511`).
- O "Limpar dados" apaga nove tipos de dado em sequência, sem transação, e não recria o padrão do cadastro (`api/views.py:618-653`, FIN-42).
- `SystemLog` guarda o nome do administrador e é apagado em cascata com o usuário (`api/models.py:111-124`); o log de um usuário vem sem paginação (`api/views.py:574-584`), e a exclusão definitiva não grava log (`api/views.py:655-679`).
- A lista de usuários já busca por nome e e-mail e filtra por papel, plano e status (`api/views.py:276-300`).

---

## Deferred Ideas

- Receita real, assinaturas e pagamentos no painel: com a spec de cobrança dos planos.
- Eventos de segurança dos usuários no log, como logins com falha e trocas de senha.
