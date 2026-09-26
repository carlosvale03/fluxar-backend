# STATE

## Decisions

### AD-001
- **Decision**: As specs usam em inglês os títulos de seção e os rótulos do template do tlc-spec-driven (`Problem Statement`, `Goals`, `Out of Scope`, `Assumptions & Open Questions`, `User Stories`, `Edge Cases`, `Requirement Traceability`, `Success Criteria`, `**User Story**`, `**Acceptance Criteria**:`, `**Independent Test**`, `**Open questions:**`). Todo o conteúdo fica em português, com as palavras-chave EARS em inglês.
- **Reason**: o `validate_spec.py` procura esses títulos e rótulos exatos. Traduzidos, a spec falha no gate ou os critérios de aceite deixam de ser verificados.
- **Trade-off**: a spec mistura títulos em inglês com texto em português.
- **Scope**: todas as specs em `.specs/features/`.
- **Date**: 2026-09-25
- **Status**: active

### AD-002
- **Decision**: Uma transação só altera o saldo quando está efetivada (`COMPLETED`), qualquer que seja a data dela. Toda ocorrência gerada por uma série recorrente nasce pendente, inclusive as receitas, e só passa a contar quando o usuário a efetiva.
- **Reason**: decisão do usuário. É como as despesas já funcionam, deixa com o usuário a confirmação do que realmente aconteceu e dispensa uma rotina agendada.
- **Trade-off**: o usuário precisa efetivar cada ocorrência; uma receita que já caiu, mas não foi efetivada, fica fora do saldo.
- **Scope**: saldo, faturas, importacao, relatorios e qualquer feature que crie transações.
- **Date**: 2026-09-25
- **Status**: active

### AD-003
- **Decision**: Uma conta só pode ser excluída com saldo zero e sem transações pendentes. A conta excluída não entra em nenhum total de saldo, não recebe movimentação nova e mantém as transações efetivadas no histórico, somente para leitura.
- **Reason**: decisão do usuário. Impede que dinheiro suma do patrimônio sem registro, como já acontece na exclusão de metas; as demais restrições mantêm em zero o saldo de uma conta que saiu dos totais.
- **Trade-off**: antes de excluir, o usuário precisa transferir ou ajustar o saldo restante e resolver as transações pendentes da conta.
- **Scope**: saldo, faturas (conta de pagamento do cartão), importacao, metas (cofrinhos), relatorios e painel admin.
- **Date**: 2026-09-25
- **Status**: active

### AD-004
- **Decision**: A feature `saldo` é a dona das regras de como qualquer operação altera o saldo de uma conta. As features `faturas`, `importacao` e `metas` definem quais transações criar, alterar ou excluir e seguem essas regras, sem regra de saldo própria.
- **Reason**: hoje cada caminho atualiza o saldo do seu jeito, e é daí que vêm as divergências da auditoria (FIN-02 a FIN-04 e FIN-10).
- **Trade-off**: qualquer mudança de saldo pedida por outra feature passa a depender desta spec.
- **Scope**: saldo, faturas, importacao e metas.
- **Date**: 2026-09-25
- **Status**: active

### AD-005
- **Decision**: O endpoint genérico de transações só cria `INCOME` e `EXPENSE`. `TRANSFER_IN` e `TRANSFER_OUT` nascem só da operação de transferência, `CREDIT_CARD` só da compra no cartão, e `INVOICE_PAYMENT` não é mais criado. Uma compra no cartão só é efetivada pelo pagamento da fatura.
- **Reason**: criados pelo endpoint genérico, esses tipos geram uma perna de transferência solta, uma compra que debita a conta sem passar pela fatura ou um pagamento que não paga nada (FIN-16, FIN-17 e CON-09).
- **Trade-off**: telas e integrações precisam usar a operação própria de cada tipo; o pagamento genérico que a tela de fatura usa como fallback deixa de funcionar.
- **Scope**: saldo, faturas, importacao, metas e o frontend.
- **Date**: 2026-09-25
- **Status**: active

## Handoff

- **Feature**: saldo (`.specs/features/saldo/`)
- **Phase / Task**: Specify concluída e aprovada; Design não iniciado
- **Completed**: `spec.md` (SALDO-01 a SALDO-47) e `context.md`
- **In-progress** (file:line): nenhum
- **Next step**: fazer o Design da feature saldo a partir de `spec.md`, respeitando AD-001 a AD-005.
- **Blockers**: nenhum
- **Uncommitted files**: nenhum
- **Branch**: docs/spec-saldo-contas-e-dashboard
