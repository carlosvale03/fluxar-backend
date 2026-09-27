# Isolamento entre usuarios Specification

## Problem Statement

A API aceita, na escrita, IDs de objetos de outros usuários. Os campos de relação gerados pelo `ModelSerializer` usam `queryset=<Modelo>.objects.all()`, então quem souber o UUID de uma conta, cartão, categoria ou tag alheia consegue lançar transações que mudam o saldo da vítima, ler o nome desses objetos na resposta e injetar subcategorias na árvore de outra pessoa (SEG-01). As leituras por endereço já são filtradas pelo dono, mas algumas somas e listas seguem a relação sem conferir o dono, e hoje a única barreira é o UUID ser difícil de adivinhar.

Origem: SEG-01 na seção 3 de `docs/auditoria-2026-09.md`, mais as relações encontradas no código durante esta spec (monitor de foco, edição em lote de série, categorias-modelo sem dono e metas ligadas a um cofrinho).

## Goals

- [ ] Nenhuma requisição de um usuário grava uma relação com objeto de outro usuário.
- [ ] Nenhuma resposta traz dados de outro usuário, nem revela que um ID de outro usuário existe.
- [ ] Nenhuma ligação cruzada sobra nos dados já gravados.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Painel admin, que acessa todos os usuários por desenho, e a regra de quem é administrador (SEG-06) | Feature `permissoes-e-planos` |
| Rate limiting e força bruta no login, cadastro e redefinição de senha (SEG-02) | Feature `autenticacao` |
| Sessão, tokens e revogação (SEG-05) | Feature `sessao` |
| Admin do Django (`/admin/`) | Acesso restrito a staff |
| Compartilhar contas ou dados entre usuários | Não existe e não foi pedido |
| Registrar no log as tentativas de usar IDs de outro usuário | Não foi pedido; a verificação de ISOL-16 cobre os dados gravados |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Status para um ID de outro usuário no corpo da requisição | HTTP 400, com o erro no campo da relação; no endereço, 404 como hoje | Decisão do usuário (AD-010). O formulário mostra o erro no campo certo | sim |
| Resposta para um ID de outro usuário comparada à de um ID inexistente | Idêntica: mesmo status, mesmo campo, mesma mensagem | Não revela que o ID existe em outra conta | sim |
| ID de outro usuário no endereço | HTTP 404, igual a um objeto inexistente | É o comportamento atual dos viewsets, que filtram pelo dono | sim |
| Filtro de listagem, relatório ou exportação com ID de outro usuário | Resultado vazio, igual a um ID inexistente | É o comportamento atual; não revela nada | sim |
| Categorias-modelo sem dono (`is_template`, criadas pelo `populate_templates`) | Não podem ser usadas em nenhuma relação | Não aparecem para o usuário, e a cópia para novos usuários nunca é chamada | sim |
| Ligações cruzadas já gravadas | A correção desfaz cada uma e recalcula os saldos afetados | O Fluxar não tem compartilhamento entre usuários, então toda ligação cruzada é indevida | sim |
| Mensagens de erro | Em português: "Conta não encontrada.", "Cartão não encontrado.", "Categoria não encontrada." e "Tag não encontrada." | Hoje o DRF responde em inglês ("Invalid pk") | sim |

**Open questions:** none. As suposições da tabela foram aprovadas pelo usuário em 2026-09-26.

---

## User Stories

### P1: Relações só com objetos do próprio usuário ⭐ MVP

**User Story**: Como usuário, quero que ninguém consiga gravar dados ligados às minhas contas, cartões, categorias ou tags, nem eu aos de outra pessoa.

**Why P1**: hoje quem souber o UUID de uma conta alheia consegue mudar o saldo dela (SEG-01).

**Acceptance Criteria**:
1. **ISOL-01** WHILE um registro existir, o sistema SHALL mantê-lo ligado apenas a objetos do mesmo usuário (conta, cartão, fatura, categoria, categoria-pai, tag ou meta), ou a nenhum.
2. **ISOL-02** IF uma transação for criada ou editada com conta, cartão, categoria ou tag de outro usuário THEN o sistema SHALL recusá-la conforme ISOL-11, sem gravar nada.
3. **ISOL-03** IF a edição em lote de uma série trouxer uma categoria de outro usuário THEN o sistema SHALL recusá-la conforme ISOL-11, sem alterar nenhuma ocorrência.
4. **ISOL-04** IF uma categoria for criada ou editada com categoria-pai de outro usuário THEN o sistema SHALL recusá-la conforme ISOL-11.
5. **ISOL-05** IF um orçamento for criado ou editado com categoria de outro usuário THEN o sistema SHALL recusá-lo conforme ISOL-11.
6. **ISOL-06** IF uma meta for criada ou editada com conta de outro usuário THEN o sistema SHALL recusá-la conforme ISOL-11.
7. **ISOL-07** IF um monitor de foco for criado com categoria ou tag de outro usuário THEN o sistema SHALL recusá-lo conforme ISOL-11.
8. **ISOL-08** IF um cartão for criado ou editado com conta de pagamento de outro usuário THEN o sistema SHALL recusá-lo conforme ISOL-11.
9. **ISOL-09** IF uma compra no cartão, uma transferência, um pagamento de fatura, um aporte ou resgate de meta ou uma importação indicar no corpo da requisição um cartão, conta, categoria ou tag de outro usuário THEN o sistema SHALL recusá-la conforme ISOL-11.
10. **ISOL-10** IF uma relação indicar uma categoria-modelo sem dono THEN o sistema SHALL recusá-la conforme ISOL-11, como se a categoria não existisse.
11. **ISOL-11** WHEN o sistema recusa um ID enviado no corpo da requisição por não pertencer ao usuário THEN o sistema SHALL responder HTTP 400, com o erro no campo da relação e a mesma mensagem dada a um ID inexistente ("Conta não encontrada.", "Cartão não encontrado.", "Categoria não encontrada." ou "Tag não encontrada.").

**Independent Test**: com dois usuários, A tenta criar uma transação na conta de B, um orçamento na categoria de B, uma meta na conta de B, uma subcategoria sob a categoria de B e um monitor de foco na tag de B. Todas as tentativas recebem 400 com o erro no campo, iguais às respostas para um UUID que não existe, e nada é gravado.

---

### P1: Leitura restrita ao dono ⭐ MVP

**User Story**: Como usuário, quero que nenhuma resposta da API mostre dados de outra pessoa nem confirme que um ID dela existe.

**Why P1**: hoje uma transação ligada à conta de outro usuário devolve o nome dessa conta, e algumas somas seguem a relação sem conferir o dono.

**Acceptance Criteria**:
1. **ISOL-12** IF um pedido de leitura, edição ou exclusão indicar no endereço um objeto de outro usuário THEN o sistema SHALL responder HTTP 404, com a mesma resposta dada a um objeto inexistente.
2. **ISOL-13** WHEN uma listagem, um relatório ou uma exportação é filtrado por um ID de outro usuário (conta, cartão, fatura, categoria ou tag) THEN o sistema SHALL devolver o resultado vazio, como para um ID inexistente.
3. **ISOL-14** WHEN o sistema lista ou soma dados ligados a um objeto (subcategorias de uma categoria, transações de uma conta, compras de um cartão, metas de um cofrinho ou a parceira de uma transferência) THEN o sistema SHALL considerar só os dados do dono desse objeto.
4. **ISOL-15** WHEN uma resposta inclui dados de objetos relacionados (nome da conta, categoria, subcategorias, tags ou conta da meta) THEN o sistema SHALL incluir só objetos do próprio usuário.

**Independent Test**: com os dados do teste anterior gravados à força no banco, A pede `/api/accounts/{conta de B}/` e recebe 404; filtra transações por `?accountId={conta de B}` e recebe a lista vazia; lista as categorias e não vê a subcategoria que B pendurou numa categoria de A; e B não vê movimentos do cofrinho de A na meta ligada a ele.

---

### P1: Correção dos dados existentes ⭐ MVP

**User Story**: Como usuário que já usa o Fluxar, quero que qualquer ligação indevida gravada antes da correção seja encontrada e desfeita.

**Why P1**: sem limpeza, uma ligação cruzada gravada antes da correção continuaria mudando saldos e mostrando dados de outra pessoa.

**Acceptance Criteria**:
1. **ISOL-16** WHEN a verificação de isolamento é executada THEN o sistema SHALL listar cada registro ligado a um objeto de outro usuário, com o tipo do registro, o identificador dele e a relação cruzada.
2. **ISOL-17** WHEN a correção é implantada THEN o sistema SHALL desfazer cada ligação cruzada: tirar da transação a conta, o cartão, a categoria ou a tag de outro usuário; tirar da categoria a categoria-pai e da meta a conta de outro usuário; e excluir os orçamentos, os monitores de foco e os registros de aporte ligados a objetos de outro usuário.
3. **ISOL-18** WHEN a correção termina THEN o sistema SHALL recalcular, pela regra SALDO-01, o saldo das contas que deixaram de ter transações de outro usuário.

**Independent Test**: numa cópia do banco com ligações cruzadas criadas para o teste, a verificação lista cada uma; depois da correção, a verificação não lista nenhuma, e o saldo da conta que recebia transações de outro usuário bate com SALDO-01.

---

## Edge Cases

- ID inexistente e ID de outro usuário: as respostas são idênticas, no corpo (ISOL-11) e no endereço (ISOL-12).
- Uma tag de outro usuário no meio de tags próprias: a transação inteira é recusada (ISOL-02).
- Transferência com origem própria e destino de outro usuário: recusada (ISOL-09).
- Conta própria excluída indicada numa transação: recusada pela regra de conta excluída (SALDO-35), não por esta spec.
- Mapeamento de importação que aponta para uma conta de outro usuário: a linha é rejeitada como "Conta não mapeada" (IMPORT-21); a conta padrão de outro usuário recusa a importação inteira (ISOL-09).
- Edição de uma transação própria que já estava ligada à conta de outro usuário antes da correção: a gravação é recusada até a ligação cruzada ser desfeita (ISOL-02, ISOL-17).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | ISOL-02 a ISOL-11 |
| Falha e falha parcial | ISOL-02, ISOL-03 (a recusa não grava nada) |
| Idempotência, repetição e duplicidade | N/A because uma recusa não tem efeito; repetir a requisição devolve a mesma recusa |
| Autorização e rate limiting | ISOL-01 a ISOL-15; o rate limiting fica fora (SEG-02) |
| Concorrência e ordem | N/A because a posse de um objeto nunca muda de usuário |
| Ciclo de vida dos dados | ISOL-16 a ISOL-18 |
| Observabilidade | ISOL-16 |
| Falha de dependência externa | N/A because o isolamento não depende de nenhum serviço externo |
| Integridade das transições de estado | N/A because o isolamento não envolve mudança de estado; a posse de um objeto é fixa |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| ISOL-01 | P1: Relações só com objetos do próprio usuário | T14 | Pending |
| ISOL-02 | P1: Relações só com objetos do próprio usuário | T4, T31 | Pending |
| ISOL-03 | P1: Relações só com objetos do próprio usuário | T7 | Pending |
| ISOL-04 | P1: Relações só com objetos do próprio usuário | T5 | Pending |
| ISOL-05 | P1: Relações só com objetos do próprio usuário | T8 | Pending |
| ISOL-06 | P1: Relações só com objetos do próprio usuário | T9 | Pending |
| ISOL-07 | P1: Relações só com objetos do próprio usuário | T11 | Pending |
| ISOL-08 | P1: Relações só com objetos do próprio usuário | T12 | Pending |
| ISOL-09 | P1: Relações só com objetos do próprio usuário | T6, T10, T12, T13 | Pending |
| ISOL-10 | P1: Relações só com objetos do próprio usuário | T3, T5 | Pending |
| ISOL-11 | P1: Relações só com objetos do próprio usuário | T3, T4, T6, T10, T31 | Pending |
| ISOL-12 | P1: Leitura restrita ao dono | T19, T20 | Pending |
| ISOL-13 | P1: Leitura restrita ao dono | T20 | Pending |
| ISOL-14 | P1: Leitura restrita ao dono | T15 a T19, T25, T28, T30 | Pending |
| ISOL-15 | P1: Leitura restrita ao dono | T9, T11, T12, T15, T16, T26, T27, T29 | Pending |
| ISOL-16 | P1: Correção dos dados existentes | T21, T23 | Pending |
| ISOL-17 | P1: Correção dos dados existentes | T22, T24 | Pending |
| ISOL-18 | P1: Correção dos dados existentes | T22, T24 | Pending |

**Coverage:** 18 total, 18 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Um teste automatizado percorre todas as relações graváveis da API com IDs de outro usuário e recebe 400 em todas, com o mesmo corpo de resposta de um ID inexistente.
- [ ] Depois da correção em produção, a verificação de isolamento (ISOL-16) não lista nenhum registro.
- [ ] Nenhum endpoint devolve dado de outro usuário no teste com dois usuários.
