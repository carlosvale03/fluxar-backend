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

### AD-006
- **Decision**: Quando uma regra usa um dia do mês que não existe naquele mês (29, 30 ou 31), vale o último dia do mês. O ajuste não se acumula: no mês seguinte volta o dia original.
- **Reason**: decisão do usuário. É o que os bancos fazem com fechamento e vencimento, e mantém cada data no próprio mês.
- **Trade-off**: em meses curtos o ciclo da fatura fica um ou dois dias menor.
- **Scope**: faturas (fechamento e vencimento) e qualquer regra mensal por dia, inclusive as séries recorrentes mensais.
- **Date**: 2026-09-25
- **Status**: active

### AD-007
- **Decision**: O pagamento de fatura é idempotente. Cada tentativa leva um identificador; a repetição com o mesmo identificador recebe a mesma resposta do primeiro processamento e não gera outro pagamento. Um pagamento com outro identificador, ou sem identificador, numa fatura já paga é recusado com HTTP 400.
- **Reason**: decisão do usuário. Um reenvio depois de timeout, comum no cold start do Render, não pode cobrar duas vezes nem mostrar um erro falso.
- **Trade-off**: o backend guarda o identificador de cada pagamento, e o frontend precisa gerar e reaproveitar o identificador da tentativa.
- **Scope**: faturas, saldo (SALDO-26) e o frontend.
- **Date**: 2026-09-25
- **Status**: active

### AD-008
- **Decision**: Toda regra que depende da data de hoje usa a data corrente no fuso de Brasília (`America/Sao_Paulo`).
- **Reason**: os usuários estão no Brasil e o servidor roda em UTC; depois das 21h o "hoje" do servidor já é o dia seguinte (FIN-34).
- **Trade-off**: um usuário em outro fuso vê a virada do dia no horário de Brasília.
- **Scope**: saldo (data do ajuste), faturas (fatura aberta ou fechada, próximo vencimento), relatorios e séries recorrentes.
- **Date**: 2026-09-25
- **Status**: active

### AD-009
- **Decision**: Um valor em texto no formato brasileiro é lido assim: com vírgula, a vírgula é o separador decimal e os pontos são de milhar; sem vírgula, os pontos são de milhar quando todos os grupos depois deles têm três dígitos e a parte antes do primeiro ponto não é zero, e decimal nos demais casos ("1.500" é 1500; "12.5" é 12,50; "0.50" é 0,50).
- **Reason**: é a leitura que um usuário brasileiro espera. A regra atual troca vírgula por ponto e lê "1.500" como 1,50 (FIN-22), e o mesmo erro aparece nos formulários de meta (FE-06).
- **Trade-off**: um valor escrito no formato americano com três casas decimais sem vírgula ("1.500" querendo dizer 1,5) é lido como milhar.
- **Scope**: importacao e qualquer campo que receba valor em texto, inclusive os formulários de metas.
- **Date**: 2026-09-25
- **Status**: active

### AD-010
- **Decision**: Toda relação gravável pela API só aceita objetos do usuário da requisição. Um ID de outro usuário no corpo da requisição recebe HTTP 400, com o erro no campo e a mesma mensagem de um ID inexistente; no endereço, recebe HTTP 404, também igual a um objeto inexistente.
- **Reason**: decisão do usuário. O 400 mantém o erro por campo nos formulários, e a resposta idêntica à de um ID inexistente não revela que o ID existe em outra conta.
- **Trade-off**: as views que hoje respondem 404 para um ID do corpo (aporte e resgate de meta, importação) mudam para 400.
- **Scope**: todas as features; qualquer relação nova precisa seguir esta regra.
- **Date**: 2026-09-26
- **Status**: active

## Handoff

- **Feature**: série de specs da auditoria (`.specs/features/`)
- **Phase / Task**: Specify de `saldo` (SALDO-01 a SALDO-47), `faturas` (FATURA-01 a FATURA-45), `importacao` (IMPORT-01 a IMPORT-41) e `isolamento-entre-usuarios` (ISOL-01 a ISOL-18) concluídas e aprovadas; Design de nenhuma delas iniciado
- **Completed**: `saldo`, `faturas`, `importacao` e `isolamento-entre-usuarios` (`spec.md` e `context.md` de cada uma)
- **In-progress** (file:line): nenhum
- **Next step**: especificar a feature `autenticacao` na mesma branch, com um commit próprio.
- **Blockers**: nenhum
- **Uncommitted files**: nenhum
- **Branch**: docs/specs-features-auditoria-2026-09
