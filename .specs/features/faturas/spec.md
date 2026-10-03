# Faturas Specification

## Problem Statement

O ciclo da fatura tem erros de data e de composição que chegam ao usuário como faturas erradas ou erro 500. O vencimento quebra em meses curtos e derruba o dashboard (FIN-05); com fechamento entre os dias 29 e 31, duas parcelas caem na mesma fatura e um mês fica sem parcela (FIN-06, FIN-31). O pagamento não é atômico nem trava a fatura (FIN-08), o total da fatura paga fica errado depois de um pagamento parcial (FIN-07) e o estorno não desfaz a divisão da compra nem traz de volta o que foi para a fatura seguinte (FIN-02).

Origem: seção 2 de `docs/auditoria-2026-09.md` (FIN-02 na composição da fatura, FIN-05, FIN-06, FIN-07, FIN-08, FIN-15, FIN-17, FIN-27, FIN-30, FIN-31, FIN-35 e FIN-41), mais CON-03 e FE-03 nas telas de fatura.

## Goals

- [ ] Toda compra e toda parcela caem na fatura definida pelas regras de data, em qualquer combinação de dia de fechamento, dia de vencimento e mês.
- [ ] Nenhum pagamento é aplicado duas vezes, e todo estorno devolve a fatura e as compras ao estado anterior ao pagamento.
- [ ] O total de cada fatura é sempre a soma das compras ligadas a ela.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Efeito do pagamento e do estorno no saldo da conta (SALDO-23 a SALDO-27, SALDO-46) | Já está na spec `saldo` (AD-004) |
| Criação de compra no cartão pelo endpoint genérico de transações (SALDO-18) | Já está na spec `saldo` (AD-005) |
| Juros, multa, pagamento mínimo e fatura vencida | Não existem no Fluxar e não foram pedidos |
| Bloquear uma compra acima do limite disponível | Não foi pedido; esta spec só unifica o cálculo do limite exibido |
| Exclusão de cartão com faturas em aberto | Ciclo de vida do cartão; fica para uma feature de cartões |
| Relatórios e dashboard que somam faturas (faturas do mês, patrimônio) | Feature `relatorios` |
| Importação de extratos de cartão | Não existe hoje e não foi pedida; a spec `importacao` também a deixa de fora |
| Impedir que um usuário acesse o cartão de outro (SEG-01) | Feature `isolamento-entre-usuarios` |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Dia de fechamento ou de vencimento que não existe no mês | Usa o último dia daquele mês, sem acumular o ajuste nos meses seguintes | Decisão do usuário (AD-006). É o que os bancos fazem e mantém cada fatura no próprio mês | sim |
| Mesmo pagamento enviado duas vezes | Cada tentativa leva um identificador; a repetição recebe a mesma resposta de sucesso e nada é cobrado de novo. Um pagamento diferente numa fatura paga é recusado | Decisão do usuário (AD-007). Evita erro falso depois de timeout e cobrança dupla | sim |
| Melhor dia de compra | Compra feita na data de fechamento do mês, já ajustada por AD-006, vai para a fatura seguinte | É a regra atual; comparar com a data ajustada corrige FIN-31 | sim |
| Divisão do valor em parcelas | Cada parcela é arredondada para centavos, e a diferença vai para a primeira | É o comportamento atual e mantém a soma igual ao valor da compra | sim |
| Data da compra | A compra guarda a data real; o vencimento vem da fatura. Compras antigas mantêm a data gravada | Hoje a compra grava o vencimento no lugar da data (FIN-15), e a data real das compras antigas não pode ser recuperada | sim |
| Compra em fatura paga | Não pode ser editada nem excluída sem estornar o pagamento antes | Fatura paga é histórico fechado; alterá-la desalinharia o valor pago | sim |
| Excluir uma parcela | Exclui a compra inteira, com todas as parcelas | Uma parcela sozinha não existe como compra; hoje o resultado depende de qual parcela é excluída (FIN-35) | sim |
| Compra que cairia numa fatura já paga | Vai para a primeira fatura seguinte do mesmo cartão que não esteja paga | Acontece com pagamento antecipado ou compra antiga registrada depois; fatura paga não recebe compras | sim |
| Pagamento maior que o total da fatura | Recusado | O Fluxar não guarda saldo credor de cartão | sim |
| Estorno quando a fatura seguinte, que recebeu o restante, já foi paga | Recusado até o pagamento da fatura seguinte ser estornado | Desfazer fora de ordem deixaria o restante pago em duas faturas | sim |
| Mudança do dia de fechamento ou de vencimento do cartão | Vale para as faturas criadas depois; as existentes mantêm as datas | Não reescreve o histórico nem move compras já lançadas | sim |
| Status aberta e fechada | Derivado da data de hoje (AD-008) comparada à data de fechamento; paga quando recebe pagamento | Hoje o status `CLOSED` nunca é gravado | sim |
| Pedido de pagamento sem identificador | É tratado como tentativa nova | Frontend e backend sobem em momentos diferentes | sim |
| Identificador reenviado depois de um estorno | Não paga de novo e repete a resposta original | Um reenvio atrasado não deve refazer um pagamento desfeito de propósito | sim |
| Limite disponível | Limite do cartão menos as compras não pagas, na tela do cartão e no dashboard | Hoje há duas fórmulas (FIN-27); a spec `saldo` encaminhou o item para cá | sim |
| Parcelas mal alocadas já gravadas | As parcelas pendentes de compras com duas parcelas na mesma fatura são redistribuídas | Corrige nos dados atuais o efeito de FIN-06; parcelas pagas não se movem | sim |

**Open questions:** none. As suposições da tabela foram aprovadas pelo usuário em 2026-09-25.

---

## User Stories

### P1: Datas de fechamento e vencimento ⭐ MVP

**User Story**: Como usuário, quero que cada fatura feche e vença nos dias do meu cartão, inclusive em meses curtos, para planejar o pagamento.

**Why P1**: hoje um vencimento no dia 30 ou 31 gera erro 500 e derruba o dashboard (FIN-05).

**Acceptance Criteria**:
1. **FATURA-01** WHEN o dia de fechamento ou de vencimento do cartão não existe no mês THEN o sistema SHALL usar o último dia daquele mês (fechamento no dia 31 cai em 30/04; vencimento no dia 30 cai em 28/02 ou 29/02).
2. **FATURA-02** WHEN o mês tem o dia cadastrado no cartão THEN o sistema SHALL usar esse dia, sem herdar o ajuste feito num mês anterior.
3. **FATURA-03** WHEN o dia de vencimento do cartão é maior que o dia de fechamento THEN o sistema SHALL marcar o vencimento de cada fatura no mesmo mês do fechamento.
4. **FATURA-04** WHEN o dia de vencimento do cartão é menor ou igual ao dia de fechamento THEN o sistema SHALL marcar o vencimento de cada fatura no mês seguinte ao do fechamento.
5. **FATURA-05** IF o cadastro ou a edição de um cartão trouxer dia de fechamento ou de vencimento fora do intervalo de 1 a 31 THEN o sistema SHALL recusá-lo com HTTP 400.
6. **FATURA-06** WHEN o próximo vencimento de um cartão é exibido THEN o sistema SHALL mostrar a primeira data de vencimento igual ou posterior a hoje, calculada por FATURA-01 a FATURA-04.
7. **FATURA-07** WHEN o usuário altera o dia de fechamento ou de vencimento de um cartão THEN o sistema SHALL aplicar os novos dias às faturas criadas depois da alteração e manter as datas das faturas existentes.
8. **FATURA-08** WHILE uma fatura não estiver paga e hoje for anterior à data de fechamento dela, o sistema SHALL exibi-la como aberta.
9. **FATURA-09** WHILE uma fatura não estiver paga e hoje for igual ou posterior à data de fechamento dela, o sistema SHALL exibi-la como fechada.

**Independent Test**: com cartões de fechamento e vencimento em todas as combinações de 1 a 31, gerar as faturas de janeiro de 2024 a dezembro de 2027 (inclui um ano bissexto); nenhuma geração falha e cada data segue FATURA-01 a FATURA-04.

---

### P1: Em qual fatura cai cada compra e cada parcela ⭐ MVP

**User Story**: Como usuário, quero que cada compra e cada parcela apareça na fatura certa, para saber quanto vou pagar em cada mês.

**Why P1**: hoje, com fechamento entre os dias 29 e 31, duas parcelas caem na mesma fatura e um mês fica sem parcela (FIN-06).

**Acceptance Criteria**:
1. **FATURA-10** WHEN uma compra é feita antes da data de fechamento do mês THEN o sistema SHALL colocá-la na fatura que fecha nesse mês.
2. **FATURA-11** WHEN uma compra é feita na data de fechamento do mês ou depois dela THEN o sistema SHALL colocá-la na fatura que fecha no mês seguinte.
3. **FATURA-12** WHEN uma compra é parcelada em N vezes THEN o sistema SHALL colocar a primeira parcela na fatura definida por FATURA-10 e FATURA-11 e cada parcela seguinte na fatura do mês seguinte ao da anterior, uma parcela por fatura.
4. **FATURA-13** WHEN o valor de uma compra parcelada não se divide em centavos exatos THEN o sistema SHALL arredondar cada parcela para centavos e somar a diferença à primeira, de modo que a soma das parcelas seja igual ao valor da compra.
5. **FATURA-14** WHILE uma compra no cartão existir, o sistema SHALL mantê-la ligada a exatamente uma fatura do mesmo cartão.
6. **FATURA-15** IF uma compra ou parcela cair, pelas regras FATURA-10 a FATURA-12, numa fatura já paga THEN o sistema SHALL colocá-la na primeira fatura seguinte do mesmo cartão que não esteja paga.
7. **FATURA-16** WHEN uma compra no cartão é registrada THEN o sistema SHALL guardar a data da compra informada pelo usuário e exibi-la como data da compra em todas as parcelas.
8. **FATURA-17** WHEN a data da compra ou o cartão de uma compra muda THEN o sistema SHALL recolocar cada parcela pendente na fatura definida por FATURA-10 a FATURA-12 e FATURA-15.
9. **FATURA-18** WHEN uma compra entra numa fatura, sai dela ou muda de valor THEN o sistema SHALL manter o total de cada fatura afetada igual à soma das compras ligadas a ela.
10. **FATURA-19** IF uma edição ou exclusão alterar uma parcela que está numa fatura paga THEN o sistema SHALL recusá-la com HTTP 400 e a mensagem "Estorne o pagamento da fatura antes de alterar esta compra."
11. **FATURA-20** WHEN o usuário exclui uma parcela de uma compra parcelada THEN o sistema SHALL excluir todas as parcelas dessa compra.

**Independent Test**: num cartão com fechamento no dia 30 e vencimento no dia 7, uma compra de R$ 100,00 em 4x feita em 30/01/2026 fica com uma parcela em cada fatura de março, abril, maio e junho de 2026; mudar a data da compra para 10/01/2026 move as quatro parcelas para fevereiro a maio, e os totais das faturas acompanham.

---

### P1: Pagamento total e parcial ⭐ MVP

**User Story**: Como usuário, quero pagar a fatura inteira ou só uma parte e ver o restante na fatura seguinte.

**Why P1**: hoje o pagamento não é atômico (FIN-08), e o total da fatura paga fica errado depois de um pagamento parcial (FIN-07).

**Acceptance Criteria**:
1. **FATURA-21** WHEN uma fatura é paga pelo valor total THEN o sistema SHALL marcar todas as compras dela como pagas e a fatura como paga.
2. **FATURA-22** WHEN uma fatura é paga por um valor menor que o total THEN o sistema SHALL marcar como pagas as compras dela, em ordem de data da compra e depois de valor, até esgotar o valor pago.
3. **FATURA-23** WHEN o valor pago acaba no meio de uma compra THEN o sistema SHALL dividi-la em uma parte paga, com o valor que coube, e um restante pendente na primeira fatura seguinte do mesmo cartão que não esteja paga.
4. **FATURA-24** WHEN uma fatura recebe um pagamento parcial THEN o sistema SHALL mover as compras não pagas para a primeira fatura seguinte do mesmo cartão que não esteja paga e marcar a fatura como paga.
5. **FATURA-25** WHEN a fatura que deve receber o restante ainda não existe THEN o sistema SHALL criá-la com as datas definidas por FATURA-01 a FATURA-04.
6. **FATURA-26** IF o valor do pagamento for maior que o total da fatura THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "O valor pago não pode ser maior que o total da fatura."
7. **FATURA-27** WHEN uma fatura paga é consultada THEN o sistema SHALL informar o valor, a conta e a data do pagamento.
8. **FATURA-28** IF qualquer etapa de um pagamento ou de um estorno falhar THEN o sistema SHALL desfazer a operação inteira e deixar a fatura, as compras e a fatura seguinte como estavam antes dela.

**Independent Test**: numa fatura de R$ 1.000,00 com compras de R$ 400,00 e R$ 600,00, pagar R$ 700,00 deixa a fatura paga com R$ 700,00 (R$ 400,00 mais R$ 300,00 da segunda compra) e leva um restante de R$ 300,00 para a fatura seguinte, cujo total aumenta em R$ 300,00.

---

### P1: Pagamento repetido ⭐ MVP

**User Story**: Como usuário, quero que um pagamento reenviado por timeout ou por duas abas seja aplicado uma única vez, sem me mostrar um erro falso.

**Why P1**: hoje nada impede um segundo processamento simultâneo (FIN-08), e o Render pode demorar a responder depois de um cold start.

**Acceptance Criteria**:
1. **FATURA-29** WHEN o usuário confirma o pagamento de uma fatura THEN a interface SHALL enviar um identificador da tentativa e reaproveitá-lo em todo reenvio feito no mesmo diálogo até o sucesso.
2. **FATURA-30** WHEN um pedido de pagamento chega com um identificador de tentativa já processado THEN o sistema SHALL responder com o mesmo resultado do primeiro processamento, sem pagar de novo.
3. **FATURA-31** WHEN dois pedidos com o mesmo identificador chegam ao mesmo tempo THEN o sistema SHALL processar o pagamento uma única vez e responder aos dois com o mesmo resultado.
4. **FATURA-32** IF um identificador já usado chegar com outra fatura, outro valor, outra conta ou outra data THEN o sistema SHALL recusar o pedido com HTTP 400 e a mensagem "Este identificador de pagamento já foi usado com outros dados.", sem pagar.
5. **FATURA-33** IF uma fatura já paga receber um pedido de pagamento com identificador novo, ou sem identificador, THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "Fatura já está paga."

**Independent Test**: enviar dez vezes o mesmo pedido de pagamento, com o mesmo identificador, sendo dois ao mesmo tempo: todas as respostas são iguais e existe um único pagamento. Um pedido com identificador novo para a mesma fatura recebe 400.

---

### P1: Estorno do pagamento ⭐ MVP

**User Story**: Como usuário, quero estornar o pagamento de uma fatura e vê-la exatamente como estava antes.

**Why P1**: hoje o estorno só troca o status e não desfaz a divisão da compra nem o que foi para a fatura seguinte (FIN-02).

**Acceptance Criteria**:
1. **FATURA-34** WHEN o pagamento de uma fatura é estornado THEN o sistema SHALL voltar para pendentes, na fatura original e sem data de pagamento, as compras que esse pagamento quitou.
2. **FATURA-35** WHEN o estorno alcança uma compra que o pagamento dividiu THEN o sistema SHALL juntar a parte paga e o restante numa única compra pendente, com o valor e a descrição originais, na fatura original.
3. **FATURA-36** WHEN o pagamento estornado era parcial THEN o sistema SHALL trazer de volta para a fatura original as compras que ele moveu para a fatura seguinte.
4. **FATURA-37** WHEN um estorno termina THEN o sistema SHALL deixar a fatura aberta ou fechada conforme FATURA-08 e FATURA-09, com o total igual à soma das compras dela.
5. **FATURA-38** IF a fatura que recebeu o restante do pagamento já estiver paga THEN o sistema SHALL recusar o estorno com HTTP 400 e a mensagem "Estorne primeiro o pagamento da fatura seguinte."

**Independent Test**: pagar R$ 700,00 da fatura do teste anterior e estornar: a fatura volta a ter as compras de R$ 400,00 e R$ 600,00 pendentes e o total de R$ 1.000,00, e a fatura seguinte volta ao total que tinha antes do pagamento.

---

### P1: Correção dos dados existentes ⭐ MVP

**User Story**: Como usuário que já usa o Fluxar, quero que as faturas erradas de hoje sejam corrigidas quando a correção entrar no ar.

**Why P1**: os bugs já gravaram compras sem fatura (FIN-17), parcelas na fatura errada (FIN-06) e totais desatualizados (FIN-07).

**Acceptance Criteria**:
1. **FATURA-39** WHEN a correção é implantada THEN o sistema SHALL ligar à fatura definida por FATURA-10 a FATURA-12 toda compra no cartão que esteja sem fatura.
2. **FATURA-40** WHEN a correção é implantada THEN o sistema SHALL recolocar, pelas regras FATURA-12 e FATURA-15, as parcelas pendentes de compras que tenham mais de uma parcela na mesma fatura.
3. **FATURA-41** WHEN a correção é implantada THEN o sistema SHALL recalcular o total de cada fatura como a soma das compras ligadas a ela.

**Independent Test**: numa cópia do banco de produção, aplicar a correção; nenhuma compra no cartão fica sem fatura, nenhuma compra tem duas parcelas pendentes na mesma fatura e o total de cada fatura bate com a soma das compras dela.

---

### P2: Limite disponível

**User Story**: Como usuário, quero ver o mesmo limite disponível na tela do cartão e no dashboard.

**Why P2**: hoje as duas telas usam fórmulas diferentes e divergem depois de um pagamento parcial, de uma rolagem ou de um estorno (FIN-27).

**Acceptance Criteria**:
1. **FATURA-42** WHEN o limite disponível de um cartão é exibido, na tela do cartão ou no dashboard, THEN o sistema SHALL mostrar o limite do cartão menos a soma das compras não pagas desse cartão, em todas as faturas.

**Independent Test**: num cartão de R$ 5.000,00 com R$ 1.200,00 em compras não pagas, a tela do cartão e o dashboard mostram R$ 3.800,00, antes e depois de um pagamento parcial e do estorno dele.

---

### P2: Faturas na interface e na API

**User Story**: Como usuário, quero ver as datas certas e todas as compras de cada fatura.

**Why P2**: hoje o vencimento aparece um dia antes (FE-03), o detalhe mostra no máximo 20 compras (CON-03) e a API aceita um `POST` que gera erro 500 (FIN-41).

**Acceptance Criteria**:
1. **FATURA-43** WHEN a interface exibe a data de fechamento ou de vencimento de uma fatura THEN o sistema SHALL mostrar o mesmo dia e o mesmo mês gravados, sem deslocamento de fuso (um vencimento em 01/10 aparece como 01/10, em outubro).
2. **FATURA-44** WHEN o usuário abre os detalhes de uma fatura THEN o sistema SHALL listar todas as compras ligadas a ela, qualquer que seja a quantidade.
3. **FATURA-45** IF um pedido tentar criar, editar ou excluir uma fatura diretamente pela API THEN o sistema SHALL responder com HTTP 405.

**Independent Test**: uma fatura com 35 compras e vencimento em 01/10 mostra as 35 compras e o vencimento 01/10 no fuso de Brasília; um `POST /api/invoices/` recebe 405.

---

## Edge Cases

- Fechamento no dia 31 e compra em 30/04: vai para a fatura seguinte, porque 30/04 é o fechamento de abril (FATURA-01, FATURA-11).
- Vencimento no dia 30 em fevereiro de ano bissexto: vence em 29/02 (FATURA-01).
- Fechamento no dia 30, vencimento no dia 7 e compra em 4x em 30/01/2026: parcelas nas faturas de março, abril, maio e junho (FATURA-11, FATURA-12).
- Compra de R$ 100,00 em 3x: parcelas de R$ 33,34, R$ 33,33 e R$ 33,33 (FATURA-13).
- Pagamento antecipado, antes do fechamento, seguido de uma nova compra no mesmo ciclo: a compra vai para a fatura seguinte (FATURA-15).
- Compra antiga registrada depois que a fatura dela foi paga: vai para a primeira fatura não paga (FATURA-15).
- Dois pagamentos com identificadores diferentes enviados ao mesmo tempo para a mesma fatura: só um é processado (SALDO-26, FATURA-33).
- Reenvio de um identificador depois de um estorno: não paga de novo e repete a resposta original (FATURA-30).
- Estorno de uma fatura que não está paga: recusado (SALDO-27).
- Cartão sem conta de pagamento: as compras continuam ligadas às faturas, e a conta é escolhida no pagamento (SALDO-23).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | FATURA-05, FATURA-26, FATURA-32, SALDO-09 |
| Falha e falha parcial | FATURA-28 |
| Idempotência, repetição e duplicidade | FATURA-29 a FATURA-33 |
| Autorização e rate limiting | N/A because a posse dos dados fica na feature `isolamento-entre-usuarios` (SEG-01) e o rate limiting (SEG-02) na feature `autenticacao` |
| Concorrência e ordem | FATURA-31, SALDO-26 |
| Ciclo de vida dos dados | FATURA-07, FATURA-19, FATURA-20, FATURA-39 a FATURA-41 |
| Observabilidade | FATURA-27 |
| Falha de dependência externa | N/A because o ciclo da fatura não depende de nenhum serviço externo |
| Integridade das transições de estado | FATURA-08, FATURA-09, FATURA-21, FATURA-24, FATURA-37, FATURA-38 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| FATURA-01 | P1: Datas de fechamento e vencimento | T1 | Implemented |
| FATURA-02 | P1: Datas de fechamento e vencimento | T1 | Implemented |
| FATURA-03 | P1: Datas de fechamento e vencimento | T1 | Implemented |
| FATURA-04 | P1: Datas de fechamento e vencimento | T1 | Implemented |
| FATURA-05 | P1: Datas de fechamento e vencimento | T3 | Implemented |
| FATURA-06 | P1: Datas de fechamento e vencimento | T3 | Implemented |
| FATURA-07 | P1: Datas de fechamento e vencimento | T2 | Implemented |
| FATURA-08 | P1: Datas de fechamento e vencimento | T3 | Implemented |
| FATURA-09 | P1: Datas de fechamento e vencimento | T3 | Implemented |
| FATURA-10 | P1: Em qual fatura cai cada compra e cada parcela | T1 | Implemented |
| FATURA-11 | P1: Em qual fatura cai cada compra e cada parcela | T1 | Implemented |
| FATURA-12 | P1: Em qual fatura cai cada compra e cada parcela | T2, T6 | Implemented |
| FATURA-13 | P1: Em qual fatura cai cada compra e cada parcela | T2, T6 | Implemented |
| FATURA-14 | P1: Em qual fatura cai cada compra e cada parcela | T6, T7 | Implemented |
| FATURA-15 | P1: Em qual fatura cai cada compra e cada parcela | T2, T6 | Implemented |
| FATURA-16 | P1: Em qual fatura cai cada compra e cada parcela | T5, T6 | Implemented |
| FATURA-17 | P1: Em qual fatura cai cada compra e cada parcela | T8 | Implemented |
| FATURA-18 | P1: Em qual fatura cai cada compra e cada parcela | T7 | Implemented |
| FATURA-19 | P1: Em qual fatura cai cada compra e cada parcela | T8, T9 | Implemented |
| FATURA-20 | P1: Em qual fatura cai cada compra e cada parcela | T9 | Implemented |
| FATURA-21 | P1: Pagamento total e parcial | - | Pending |
| FATURA-22 | P1: Pagamento total e parcial | - | Pending |
| FATURA-23 | P1: Pagamento total e parcial | - | Pending |
| FATURA-24 | P1: Pagamento total e parcial | - | Pending |
| FATURA-25 | P1: Pagamento total e parcial | T2 | Implemented |
| FATURA-26 | P1: Pagamento total e parcial | - | Pending |
| FATURA-27 | P1: Pagamento total e parcial | - | Pending |
| FATURA-28 | P1: Pagamento total e parcial | - | Pending |
| FATURA-29 | P1: Pagamento repetido | - | Pending |
| FATURA-30 | P1: Pagamento repetido | - | Pending |
| FATURA-31 | P1: Pagamento repetido | - | Pending |
| FATURA-32 | P1: Pagamento repetido | - | Pending |
| FATURA-33 | P1: Pagamento repetido | - | Pending |
| FATURA-34 | P1: Estorno do pagamento | - | Pending |
| FATURA-35 | P1: Estorno do pagamento | - | Pending |
| FATURA-36 | P1: Estorno do pagamento | - | Pending |
| FATURA-37 | P1: Estorno do pagamento | - | Pending |
| FATURA-38 | P1: Estorno do pagamento | - | Pending |
| FATURA-39 | P1: Correção dos dados existentes | - | Pending |
| FATURA-40 | P1: Correção dos dados existentes | - | Pending |
| FATURA-41 | P1: Correção dos dados existentes | - | Pending |
| FATURA-42 | P2: Limite disponível | T4 | Implemented |
| FATURA-43 | P2: Faturas na interface e na API | - | Pending |
| FATURA-44 | P2: Faturas na interface e na API | - | Pending |
| FATURA-45 | P2: Faturas na interface e na API | - | Pending |

**Coverage:** 45 total, 0 mapped to tasks, 45 unmapped ⚠️ (design e tasks ainda não iniciados)

---

## Success Criteria

- [ ] Um teste com todos os dias de fechamento e de vencimento, de 1 a 31, e todos os meses de 2024 a 2027 não gera erro e coloca cada parcela numa fatura diferente e consecutiva.
- [ ] Pagar, estornar e pagar de novo deixa faturas, compras e totais idênticos aos de um único pagamento.
- [ ] Reenviar o mesmo pagamento dez vezes resulta num único pagamento.
