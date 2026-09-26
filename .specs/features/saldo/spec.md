# Saldo Specification

## Problem Statement

O saldo exibido ao usuário não é confiável. Ele é mantido por signals incrementais, e quatro caminhos do dia a dia pulam ou erram a atualização: receita recorrente gravada como efetivada (FIN-01), estorno de fatura (FIN-02), edição em lote de série (FIN-03) e edição de transferência (FIN-04). Além disso, a lista de contas e o dashboard calculam o saldo por caminhos diferentes, e o saldo total e o patrimônio somam contas excluídas (FIN-10). Num app de finanças, um saldo errado invalida todas as outras telas.

Origem: seção 2 de `docs/auditoria-2026-09.md` (FIN-01 a FIN-04 e FIN-10), mais FIN-08, FIN-16, FIN-17, FIN-18, FIN-19, FIN-29, FIN-36, FIN-39, FIN-43, CON-06 e CON-09 no que afetam o saldo. Os demais itens da seção têm destino na tabela Out of Scope.

## Goals

- [ ] Em qualquer sequência das operações desta spec, o saldo exibido de cada conta é igual ao calculado por SALDO-01.
- [ ] Todos os totais de saldo usam o mesmo valor por conta e deixam as contas excluídas de fora.
- [ ] Nenhuma operação que falha deixa um saldo alterado pela metade.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Fatura: fechamento, vencimento, parcelamento, total e composição da fatura, limite do cartão e fatura de compras editadas (FIN-05, FIN-06, FIN-07, FIN-15, FIN-27, FIN-30, FIN-31, FIN-35, FIN-41) | Feature `faturas`. Esta spec cobre só o efeito do pagamento e do estorno no saldo e quais tipos o endpoint genérico aceita |
| Importação de OFX e planilhas (FIN-11, FIN-12, FIN-21, FIN-22, FIN-23) | Feature `importacao`. As transações importadas seguem as regras desta spec (AD-004) |
| Metas: razão, aporte a partir do próprio cofrinho, transferência entre cofrinhos e arredondamento (FIN-09, FIN-20, FIN-37, FIN-38) | Feature `metas`. Aqui vale só que aporte e resgate movem saldo como transferência |
| Geração de séries: datas das ocorrências e mais de 12 ocorrências (FIN-13, FIN-14) | Regras de geração de série. Esta spec cobre o efeito das ocorrências no saldo |
| Relatórios, gráficos, exportação e score (FIN-24, FIN-25, FIN-26, FIN-32, FIN-33, FIN-44), inclusive como o ajuste de saldo e as transações de conta excluída aparecem neles | Feature `relatorios` |
| Fuso horário dos relatórios (FIN-34) | Feature `relatorios`. Aqui só a data de "hoje" nas regras de saldo segue o fuso de Brasília |
| Validação do mês do orçamento (FIN-40) | Feature de orçamentos |
| Exclusão definitiva de usuário e limpeza de dados pelo admin (FIN-28, FIN-42) | Painel admin. Os dados do usuário somem por inteiro e não resta saldo a manter |
| Impedir que um usuário movimente a conta de outro (SEG-01) | Autorização; fica numa feature de segurança |
| Performance de listagens e relatórios (PERF-01 a PERF-04) | Não muda o comportamento; fica para o design ou para uma feature própria |
| Reativar uma conta excluída | Não existe hoje e não foi pedido |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Quando uma ocorrência de série passa a contar no saldo | Só quando o usuário a efetiva. Toda ocorrência gerada nasce pendente, inclusive as receitas | Decisão do usuário (AD-002). É como as despesas já funcionam e dispensa rotina agendada | sim |
| Se uma conta excluída entra em algum total | Não entra em nenhum total de saldo, e a exclusão exige saldo zero | Decisão do usuário (AD-003). Impede que dinheiro suma do patrimônio sem registro, como já acontece com as metas | sim |
| Demais restrições da conta excluída | A exclusão também exige que não haja transações pendentes; a conta excluída não recebe movimentação nova, e o histórico dela fica somente para leitura | Qualquer uma dessas operações tiraria do zero o saldo de uma conta que já saiu dos totais. Apagar as pendentes junto com a conta apagaria compras de cartão ainda não pagas | sim |
| Tipos que o endpoint genérico de transações cria | Só `INCOME` e `EXPENSE`. Transferência, compra no cartão e pagamento de fatura nascem só das operações próprias (AD-005) | Pelo endpoint genérico, esses tipos criam uma perna de transferência solta, uma compra que debita a conta sem passar pela fatura ou um pagamento que não paga nada (FIN-16, FIN-17, CON-09) | sim |
| Status da primeira ocorrência de uma série | Segue o status escolhido pelo usuário na criação; só as ocorrências geradas nascem pendentes | O usuário está registrando a primeira agora e sabe se ela já aconteceu | sim |
| Transação efetivada com data futura, fora de série | Conta no saldo desde já | Consequência de AD-002: quem decide é o status, não a data | sim |
| Editar "todas" as ocorrências de uma série | Altera só as pendentes, com todos os campos que a tela envia; as efetivadas ficam como estão | Preserva o histórico do que já aconteceu, e nenhum campo enviado é descartado em silêncio (FIN-03) | sim |
| Excluir uma série | Exclui só as pendentes e encerra a série; as efetivadas continuam no histórico | Excluir o futuro não deve apagar o passado nem mexer no saldo (FIN-36) | sim |
| Comando de limpeza do banco (`cleanup_db`) | Não pode apagar o histórico de contas excluídas nem alterar o saldo de contas ativas | Hoje ele apaga contas excluídas em cascata e leva junto as pernas de transferência de contas ativas (FIN-43), o que contradiz AD-003 | sim |
| Dados já gravados em produção | Na implantação, as ocorrências geradas por série (exceto a primeira) que estejam efetivadas e tenham data futura voltam a pendentes, e o saldo de todas as contas é recalculado | Corrige o efeito de FIN-01 e as divergências dos outros bugs (FIN-29) sem exigir ação do usuário | sim |
| Contas já excluídas com saldo diferente de zero antes da correção | Continuam excluídas e fora dos totais | O card "Saldo em Contas" já as ignora hoje; só o saldo total e o patrimônio mudam | sim |
| Ajuste de saldo | O usuário informa o novo saldo; a diferença, calculada em decimal, vira uma transação efetivada com a data de hoje | É o fluxo atual da tela de ajuste, sem o erro de ponto flutuante (CON-06) | sim |
| Data de "hoje" | A data corrente no fuso de Brasília (`America/Sao_Paulo`) | Os usuários estão no Brasil e o servidor roda em UTC (FIN-34) | sim |
| Status das pernas de uma transferência | As duas pernas têm sempre o mesmo status | Uma perna efetivada sem a outra criaria ou destruiria dinheiro | sim |

**Open questions:** none. As decisões dos itens marcados como suposição foram delegadas ao agente pelo usuário em 2026-09-25.

---

## User Stories

### P1: Saldo em transações avulsas ⭐ MVP

**User Story**: Como usuário, quero que o saldo de cada conta reflita exatamente as transações efetivadas, para confiar no número que vejo.

**Why P1**: é a regra de que todas as outras dependem; sem ela, nenhuma tela de saldo é confiável.

**Acceptance Criteria**:
1. **SALDO-01** WHILE uma conta estiver ativa, o sistema SHALL exibir como saldo dela o saldo inicial, mais as entradas efetivadas (`INCOME`, `TRANSFER_IN`), menos as saídas efetivadas (`EXPENSE`, `TRANSFER_OUT`, `CREDIT_CARD`, `INVOICE_PAYMENT`) lançadas nela.
2. **SALDO-02** WHILE uma transação estiver pendente, o sistema SHALL mantê-la fora do saldo da conta.
3. **SALDO-03** WHEN uma transação efetivada é criada THEN o sistema SHALL somar o valor ao saldo da conta, se for entrada, ou subtraí-lo, se for saída.
4. **SALDO-04** WHEN o usuário efetiva uma transação pendente THEN o sistema SHALL aplicar o valor dela no saldo da conta.
5. **SALDO-05** WHEN o usuário volta uma transação efetivada para pendente THEN o sistema SHALL desfazer o efeito dela no saldo da conta.
6. **SALDO-06** WHEN o valor ou o tipo de uma transação efetivada muda THEN o sistema SHALL ajustar o saldo da conta pela diferença entre o efeito novo e o antigo.
7. **SALDO-07** WHEN a conta de uma transação efetivada muda THEN o sistema SHALL retirar o efeito dela da conta antiga e aplicá-lo na conta nova.
8. **SALDO-08** WHEN uma transação efetivada é excluída THEN o sistema SHALL desfazer o efeito dela no saldo da conta.
9. **SALDO-09** IF uma transação, transferência ou pagamento de fatura receber um valor menor ou igual a zero, ou com mais de duas casas decimais na forma enviada (100,1 é aceito; 100,123 é recusado), THEN o sistema SHALL recusá-lo com HTTP 400, com o erro no campo do valor, sem alterar nenhum saldo.
10. **SALDO-10** IF qualquer etapa de uma operação que move dinheiro falhar THEN o sistema SHALL desfazer a operação inteira e deixar todos os saldos como estavam antes dela.

**Independent Test**: numa conta com saldo inicial de R$ 1.000,00, criar, efetivar, editar, mover para outra conta e excluir transações; depois de cada passo, o saldo exibido é igual ao calculado por SALDO-01.

---

### P1: Transferências ⭐ MVP

**User Story**: Como usuário, quero transferir dinheiro entre minhas contas e editar ou excluir a transferência sem que dinheiro apareça ou suma.

**Why P1**: aportes e resgates de metas também são transferências, e hoje a edição de uma transferência perde dinheiro (FIN-04).

**Acceptance Criteria**:
1. **SALDO-11** WHEN uma transferência é criada THEN o sistema SHALL registrar a saída na conta de origem e a entrada na conta de destino na mesma operação.
2. **SALDO-12** WHEN uma transferência é criada, editada ou excluída THEN o sistema SHALL manter inalterada a soma dos saldos de todas as contas do usuário.
3. **SALDO-13** WHEN o valor de uma transferência muda THEN o sistema SHALL aplicar o novo valor às duas pernas e ajustar o saldo da origem e do destino pela diferença.
4. **SALDO-14** WHEN a conta de origem ou de destino de uma transferência muda THEN o sistema SHALL mover o efeito da perna alterada da conta antiga para a nova.
5. **SALDO-15** WHEN o status de uma perna de transferência muda THEN o sistema SHALL aplicar o mesmo status à outra perna.
6. **SALDO-16** WHEN uma perna de transferência é excluída THEN o sistema SHALL excluir as duas pernas e desfazer o efeito nas duas contas.
7. **SALDO-17** IF a conta de origem for a mesma de destino THEN o sistema SHALL recusar a transferência com HTTP 400.
8. **SALDO-18** IF o endpoint genérico de transações receber a criação de uma transação `TRANSFER_IN`, `TRANSFER_OUT`, `CREDIT_CARD` ou `INVOICE_PAYMENT` THEN o sistema SHALL recusá-la com HTTP 400; esses tipos só nascem das operações de transferência, compra no cartão e pagamento de fatura.
9. **SALDO-19** IF uma edição tentar mudar o tipo de uma transação para `TRANSFER_IN`, `TRANSFER_OUT`, `CREDIT_CARD` ou `INVOICE_PAYMENT`, ou a partir de um desses tipos, THEN o sistema SHALL recusá-la com HTTP 400.

**Independent Test**: transferir R$ 100,00 de A para B, editar o valor para R$ 150,00, trocar o destino para C e excluir; em cada passo, A, B e C batem com SALDO-01 e a soma de todas as contas não muda.

---

### P1: Séries recorrentes ⭐ MVP

**User Story**: Como usuário, quero cadastrar uma receita ou despesa recorrente sem que os meses futuros entrem no saldo de hoje.

**Why P1**: hoje um salário recorrente soma 12 meses de uma vez ao saldo (FIN-01).

**Acceptance Criteria**:
1. **SALDO-20** WHEN uma série recorrente é criada THEN o sistema SHALL gravar a primeira ocorrência com o status escolhido pelo usuário e todas as ocorrências geradas como pendentes, inclusive as de receita.
2. **SALDO-21** WHEN o usuário altera todas as ocorrências de uma série THEN o sistema SHALL aplicar às ocorrências pendentes, e só a elas, cada campo enviado entre descrição, valor, categoria, conta e tipo.
3. **SALDO-22** WHEN o usuário exclui uma série THEN o sistema SHALL excluir as ocorrências pendentes, encerrar a série (ela deixa de gerar ocorrências) e manter as ocorrências efetivadas no histórico.

**Independent Test**: criar um salário mensal de R$ 5.000,00 com a primeira ocorrência efetivada: o saldo sobe exatamente R$ 5.000,00 e as 11 ocorrências seguintes aparecem pendentes. Efetivar a segunda soma mais R$ 5.000,00; alterar "todas" para R$ 5.500,00 e para outra conta muda só as pendentes; excluir a série remove só as pendentes.

---

### P1: Pagamento e estorno de fatura ⭐ MVP

**User Story**: Como usuário, quero pagar e estornar uma fatura e ver a conta de pagamento voltar exatamente ao valor anterior.

**Why P1**: hoje o estorno não devolve o dinheiro, e pagar de novo debita duas vezes (FIN-02).

**Acceptance Criteria**:
1. **SALDO-23** WHEN uma fatura é paga com o valor V a partir de uma conta THEN o sistema SHALL diminuir o saldo dessa conta exatamente em V.
2. **SALDO-24** WHEN o pagamento de uma fatura é estornado THEN o sistema SHALL somar de volta à conta de pagamento exatamente o valor pago.
3. **SALDO-25** WHEN uma fatura é paga, estornada e paga de novo com o mesmo valor THEN o sistema SHALL deixar a conta de pagamento com um único débito desse valor.
4. **SALDO-26** IF uma fatura já paga, ou com um pagamento em andamento, receber outro pedido de pagamento THEN o sistema SHALL processar um único pagamento e recusar os demais com HTTP 400 e a mensagem "Fatura já está paga."
5. **SALDO-27** IF o usuário pedir o estorno de uma fatura que não está paga THEN o sistema SHALL recusá-lo com HTTP 400, sem alterar nenhum saldo.
6. **SALDO-46** IF o usuário tentar efetivar uma compra no cartão fora do pagamento da fatura THEN o sistema SHALL recusar a operação com HTTP 400.

**Independent Test**: numa conta com R$ 3.000,00, pagar uma fatura de R$ 1.000,00 (saldo em R$ 2.000,00), estornar (volta a R$ 3.000,00) e pagar de novo (R$ 2.000,00). Em seguida, disparar dois pagamentos simultâneos de outra fatura e ver só um deles debitar; tentar efetivar uma compra dessa fatura pela lista de transações retorna 400.

---

### P1: Totais do dashboard e contas excluídas ⭐ MVP

**User Story**: Como usuário, quero que o dashboard some exatamente os saldos das minhas contas ativas, com o mesmo valor que vejo na lista de contas.

**Why P1**: hoje o saldo total e o patrimônio somam contas excluídas e usam um cálculo diferente do da lista de contas (FIN-10).

**Acceptance Criteria**:
1. **SALDO-28** WHEN o saldo de uma conta é usado em qualquer tela ou total THEN o sistema SHALL usar o mesmo valor exibido para essa conta na lista de contas.
2. **SALDO-29** WHEN o dashboard é carregado THEN o sistema SHALL exibir em "Saldo em Contas" a soma dos saldos das contas ativas dos tipos corrente, poupança e carteira.
3. **SALDO-30** WHEN o resumo do dashboard é calculado THEN o sistema SHALL usar como saldo total (`total_balance`, base do patrimônio) a soma dos saldos de todas as contas ativas, de qualquer tipo.
4. **SALDO-31** IF uma conta estiver excluída THEN o sistema SHALL deixá-la fora de todos os totais de saldo: "Saldo em Contas", saldo total, patrimônio, saldo de investimentos e estatísticas financeiras do painel admin.
5. **SALDO-32** IF o usuário tentar excluir uma conta com saldo diferente de zero THEN o sistema SHALL recusar a exclusão com HTTP 400 e a mensagem "Zere o saldo antes de excluir a conta: transfira ou ajuste o valor restante."
6. **SALDO-33** IF o usuário tentar excluir uma conta com transações pendentes THEN o sistema SHALL recusar a exclusão com HTTP 400 e a mensagem "Resolva as transações pendentes antes de excluir a conta: efetive, mova ou exclua cada uma."
7. **SALDO-34** WHEN o usuário exclui uma conta com saldo zero e sem transações pendentes THEN o sistema SHALL retirá-la da lista de contas e manter as transações efetivadas dela no histórico.
8. **SALDO-35** IF uma nova transação, transferência, ajuste de saldo ou pagamento de fatura indicar uma conta excluída THEN o sistema SHALL recusar a operação com HTTP 400.
9. **SALDO-36** IF o usuário tentar editar ou excluir uma transação de uma conta excluída, ou uma transferência que envolva uma conta excluída, THEN o sistema SHALL recusar a operação com HTTP 400.
10. **SALDO-47** WHEN o comando de limpeza do banco (`cleanup_db`) é executado THEN o sistema SHALL manter sem alteração o histórico das contas excluídas e o saldo de todas as contas ativas.

**Independent Test**: com uma conta corrente de R$ 1.000,00, uma de investimento de R$ 500,00 e uma conta excluída, o "Saldo em Contas" mostra R$ 1.000,00 e o saldo total R$ 1.500,00. Tentar excluir a conta corrente com saldo retorna 400; depois de zerá-la por transferência, a exclusão funciona e nenhum total muda. Rodar o `cleanup_db` não altera nenhum saldo nem o histórico da conta excluída.

---

### P1: Correção dos saldos existentes ⭐ MVP

**User Story**: Como usuário que já usa o Fluxar, quero que os saldos errados de hoje sejam corrigidos quando a correção entrar no ar, sem precisar refazer lançamentos.

**Why P1**: os bugs já gravaram saldos e ocorrências errados em produção; corrigir só o código deixaria os números antigos errados.

**Acceptance Criteria**:
1. **SALDO-37** WHEN a correção é implantada THEN o sistema SHALL voltar para pendente toda ocorrência gerada por série, exceto a primeira, que esteja efetivada e tenha data posterior à data da implantação.
2. **SALDO-38** WHEN a correção é implantada THEN o sistema SHALL recalcular o saldo de todas as contas pela regra de SALDO-01.
3. **SALDO-39** WHEN a verificação de consistência é executada THEN o sistema SHALL listar cada conta cujo saldo exibido difere do calculado por SALDO-01, com o identificador da conta e os dois valores.

**Independent Test**: numa cópia do banco de produção, aplicar a correção; as receitas recorrentes com data futura aparecem pendentes e a verificação de consistência não lista nenhuma conta.

---

### P2: Ajuste de saldo

**User Story**: Como usuário, quero informar o saldo real da conta e ver o Fluxar registrar a diferença, para acertar o saldo quando ele divergir do banco.

**Why P2**: hoje o ajuste falha quando há centavos (CON-06), mas o usuário ainda consegue acertar o saldo com uma transação manual.

**Acceptance Criteria**:
1. **SALDO-40** WHEN o usuário informa um novo saldo diferente do atual THEN o sistema SHALL registrar uma transação efetivada, com a data de hoje, no valor da diferença: entrada se o novo saldo for maior, saída se for menor.
2. **SALDO-41** WHEN um ajuste de saldo é registrado THEN o sistema SHALL deixar o saldo da conta exatamente igual ao valor informado, inclusive com centavos (de R$ 1.000,10 para R$ 999,90, uma saída de R$ 0,20).
3. **SALDO-42** WHEN o usuário informa um novo saldo igual ao atual THEN o sistema SHALL não registrar nenhuma transação.
4. **SALDO-43** WHEN o saldo inicial de uma conta é alterado THEN o sistema SHALL mudar o saldo atual pela mesma diferença.

**Independent Test**: ajustar uma conta de R$ 1.000,10 para R$ 999,90 e ver uma saída de R$ 0,20 com a data de hoje e o saldo em R$ 999,90.

---

### P2: Operações simultâneas

**User Story**: Como usuário, quero que dois lançamentos feitos ao mesmo tempo na mesma conta, por exemplo em duas abas, deixem o saldo certo.

**Why P2**: acontece pouco no uso individual, mas, quando acontece, o erro é silencioso (FIN-19).

**Acceptance Criteria**:
1. **SALDO-44** WHEN duas operações alteram o saldo da mesma conta ao mesmo tempo THEN o sistema SHALL chegar ao mesmo saldo final que teria com as operações feitas em sequência.
2. **SALDO-45** WHEN duas requisições simultâneas efetivam a mesma transação pendente THEN o sistema SHALL aplicar o valor dela no saldo uma única vez.

**Independent Test**: disparar em paralelo 20 criações de R$ 10,00 na mesma conta e duas efetivações da mesma transação pendente; o saldo final bate com SALDO-01.

---

## Edge Cases

- Transação efetivada com data futura, fora de série: entra no saldo desde já (SALDO-01, AD-002).
- Série com início no passado: as ocorrências geradas nascem pendentes mesmo com data já passada, e o usuário efetiva as que aconteceram (SALDO-20).
- Série criada com a primeira ocorrência pendente: nenhuma ocorrência afeta o saldo até ser efetivada (SALDO-02, SALDO-20).
- Estorno de um pagamento parcial: devolve só o valor pago (SALDO-24).
- Compra no cartão ainda não paga: fica pendente e só afeta o saldo quando a fatura é paga (SALDO-02, SALDO-23, SALDO-46).
- Pagamento registrado pela lista de transações, sem fatura escolhida (CON-09): recusado (SALDO-18).
- Conta com saldo negativo: a exclusão também é recusada (SALDO-32).
- Ajuste para um saldo negativo: é permitido, e a diferença vira saída (SALDO-40).
- Transferência entre uma conta ativa e uma excluída: não pode ser criada, editada nem excluída (SALDO-35, SALDO-36).
- Aporte e resgate de meta: seguem as regras de transferência (SALDO-11 a SALDO-17), inclusive a recusa de origem igual ao destino.
- Conta excluída com saldo diferente de zero antes da correção: continua fora dos totais (SALDO-31).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | SALDO-09, SALDO-17, SALDO-18, SALDO-19, SALDO-35 |
| Falha e falha parcial | SALDO-10 |
| Idempotência, repetição e duplicidade | SALDO-26, SALDO-27, SALDO-45 |
| Autorização e rate limiting | N/A because a posse das contas (SEG-01) e o rate limiting (SEG-02) ficam na feature de segurança |
| Concorrência e ordem | SALDO-26, SALDO-44, SALDO-45 |
| Ciclo de vida dos dados | SALDO-32 a SALDO-38, SALDO-47 |
| Observabilidade | SALDO-39 |
| Falha de dependência externa | N/A because o saldo não depende de nenhum serviço externo |
| Integridade das transições de estado | SALDO-04, SALDO-05, SALDO-15, SALDO-22, SALDO-27, SALDO-34, SALDO-46 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SALDO-01 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-02 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-03 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-04 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-05 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-06 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-07 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-08 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-09 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-10 | P1: Saldo em transações avulsas | - | Pending |
| SALDO-11 | P1: Transferências | - | Pending |
| SALDO-12 | P1: Transferências | - | Pending |
| SALDO-13 | P1: Transferências | - | Pending |
| SALDO-14 | P1: Transferências | - | Pending |
| SALDO-15 | P1: Transferências | - | Pending |
| SALDO-16 | P1: Transferências | - | Pending |
| SALDO-17 | P1: Transferências | - | Pending |
| SALDO-18 | P1: Transferências | - | Pending |
| SALDO-19 | P1: Transferências | - | Pending |
| SALDO-20 | P1: Séries recorrentes | - | Pending |
| SALDO-21 | P1: Séries recorrentes | - | Pending |
| SALDO-22 | P1: Séries recorrentes | - | Pending |
| SALDO-23 | P1: Pagamento e estorno de fatura | - | Pending |
| SALDO-24 | P1: Pagamento e estorno de fatura | - | Pending |
| SALDO-25 | P1: Pagamento e estorno de fatura | - | Pending |
| SALDO-26 | P1: Pagamento e estorno de fatura | - | Pending |
| SALDO-27 | P1: Pagamento e estorno de fatura | - | Pending |
| SALDO-46 | P1: Pagamento e estorno de fatura | - | Pending |
| SALDO-28 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-29 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-30 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-31 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-32 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-33 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-34 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-35 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-36 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-47 | P1: Totais do dashboard e contas excluídas | - | Pending |
| SALDO-37 | P1: Correção dos saldos existentes | - | Pending |
| SALDO-38 | P1: Correção dos saldos existentes | - | Pending |
| SALDO-39 | P1: Correção dos saldos existentes | - | Pending |
| SALDO-40 | P2: Ajuste de saldo | - | Pending |
| SALDO-41 | P2: Ajuste de saldo | - | Pending |
| SALDO-42 | P2: Ajuste de saldo | - | Pending |
| SALDO-43 | P2: Ajuste de saldo | - | Pending |
| SALDO-44 | P2: Operações simultâneas | - | Pending |
| SALDO-45 | P2: Operações simultâneas | - | Pending |

**Coverage:** 47 total, 0 mapped to tasks, 47 unmapped ⚠️ (design e tasks ainda não iniciados)

---

## Success Criteria

- [ ] Nos testes que percorrem todas as operações desta spec, o saldo exibido de cada conta é igual ao calculado por SALDO-01 depois de cada passo.
- [ ] Depois da correção em produção, a verificação de consistência (SALDO-39) não lista nenhuma conta.
- [ ] Excluir uma conta nunca muda o "Saldo em Contas", o saldo total nem o patrimônio.
