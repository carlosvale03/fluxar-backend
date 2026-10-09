# Relatórios Specification

## Problem Statement

Cada relatório escolhe as transações do seu jeito. Os gráficos simples somam as despesas pendentes junto com as efetivadas (`reports/services.py:373-376`), os orçamentos contam as compras no cartão pelo mês da fatura (`budgets/services.py:31-39`), e o score desconta pontos por todo orçamento do mês, estourado ou não (FIN-26, `reports/services.py:293-301`). O histórico de investimentos anda de 30 em 30 dias e pula ou repete meses (FIN-32), o patrimônio volta no tempo misturando pendências (FIN-33) e as horas saem em UTC (FIN-34). Os cofrinhos não entram nem no dinheiro disponível nem nos investimentos (`reports/services.py:237-238`), e a taxa de poupança só enxerga transferências para investimentos (`:248-267`). A exportação em PDF quebra com transações sem conta (FIN-24), e a tela mostra "Infinity%" quando a média é zero (FE-18).

Origem: `docs/auditoria-2026-09.md`, seção 2 (FIN-24, FIN-26, FIN-32, FIN-33, FIN-34 e FIN-44 nos cálculos), seção 5 (FE-18) e seção 6 (PERF-05), além dos itens que as specs `saldo`, `faturas` e `metas` encaminharam para cá.

## Goals

- [ ] Todo relatório conta as mesmas despesas e receitas, pelas mesmas regras.
- [ ] O patrimônio mostra o valor líquido real, com as reservas separadas do dinheiro disponível.
- [ ] Nenhum relatório mostra valor impossível, mês repetido ou hora fora do fuso.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Formato dos valores e dos eixos (FIN-44 no formato, FE-15) | Spec `contratos-frontend-backend` (CONTRATO-16 e CONTRATO-18) |
| Mesmos filtros na lista, na exportação e nos relatórios (FIN-25) | Spec `contratos-frontend-backend` (CONTRATO-13) |
| Contas excluídas nos totais de saldo (FIN-10) | Spec `saldo` (SALDO-31) |
| Data da compra no cartão (FIN-15) e limite disponível (FIN-27) | Spec `faturas` (FATURA-16 e FATURA-42) |
| Divisão por classe e gastos puxados | Specs `classes-de-despesa` e `vinculo-entre-transacoes` |
| Trava de cada relatório por plano | Catálogo da spec `permissoes-e-planos` |
| Tempo de resposta e cache dos relatórios (PERF-02) | Frente de performance, junto com PERF-01, PERF-03 e PERF-04 |
| Estatísticas do painel admin | Feature do painel admin |
| Previsões por modelo | Previsão de gastos (PROP-04) |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Despesas nos relatórios | Efetivadas na data delas e compras no cartão na data da compra, mesmo com a fatura aberta; as pendentes aparecem à parte, como "A pagar" | Decisão do usuário (AD-029) | sim |
| Patrimônio | Saldos das contas ativas menos as compras não pagas dos cartões | Decisão do usuário (AD-029) | sim |
| Cofrinhos | Entram no patrimônio como reservas e ficam fora da liquidez | Decisão do usuário (AD-029) | sim |
| Dinheiro guardado no mês | Aportes em metas e transferências para investimentos, menos resgates e retiradas | Decisão do usuário (AD-029) | sim |
| Compras parceladas | A parcela N conta N-1 meses depois da data da compra, no mesmo dia do mês, com o último dia quando ele não existe (AD-006) | Espalha o gasto pelos meses em que ele pesa, começando na data da compra | sim |
| Gasto dos orçamentos | As mesmas despesas dos relatórios, no mês do orçamento | O score e o dashboard contam orçamentos estourados pela mesma regra | sim |
| Como medir o dinheiro guardado | Pelo fluxo: o que entra nos cofrinhos e investimentos vindo das outras contas, menos o que sai deles para as outras contas | Alocar o saldo livre de um cofrinho não move dinheiro, e a mesma quantia não conta duas vezes | sim |
| Receitas nos relatórios | Só as efetivadas, na data delas, sem transferências e sem ajustes de saldo | Mesma lógica das despesas: conta o que aconteceu | sim |
| Ajustes de saldo | Fora dos gráficos de receita e de despesa; entram só no saldo e no patrimônio | São correções, não ganhos nem gastos | sim |
| Contas excluídas | As transações efetivadas delas continuam nas receitas e despesas dos períodos passados e ficam fora dos totais de saldo | O gasto aconteceu, e o saldo da conta excluída é zero (AD-003) | sim |
| Taxa de poupança sem receita | Aparece como indisponível, sem divisão por zero | Evita "Infinity%" | sim |
| Score de orçamentos | Menos 5 pontos por orçamento estourado no mês, até zerar os 20 pontos da parte | É a fórmula atual, contando só os estourados (FIN-26) | sim |
| Histórico do patrimônio | No fim de cada mês, pelas regras do patrimônio, com movimentações efetivadas até aquele dia e as compras no cartão ainda não pagas nele | Corrige FIN-33 | sim |
| Parâmetro `months` | Inteiro de 1 a 24 | Hoje não há limite, e 1.000 meses geram mil consultas (PERF-05) | sim |
| Comparação com média zero | "Sem histórico para comparar" no lugar da porcentagem | Hoje aparece "Infinity%" (FE-18) | sim |
| Falha de um bloco do relatório | Só o bloco mostra o erro, com a opção de tentar de novo | Uma falha não derruba a tela inteira | sim |
| PDF com transação sem conta | A conta fica em branco na linha | Hoje o PDF quebra (FIN-24) | sim |
| Faturas do mês no dashboard | Valor em aberto das faturas que vencem no mês atual | É o mesmo critério da gestão do salário (SALARIO-52) | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Transações que entram nos relatórios ⭐ MVP

**User Story**: Como usuário, quero que todos os relatórios contem as mesmas despesas e receitas, para os números baterem de uma tela para outra.

**Why P1**: hoje cada relatório escolhe as transações de um jeito, soma pendências e usa o horário UTC (FIN-34).

**Acceptance Criteria**:
1. **REL-01** WHEN um relatório soma despesas THEN o sistema SHALL contar as despesas efetivadas na data delas e as compras no cartão na data da compra (FATURA-16), mesmo com a fatura em aberto.
2. **REL-02** WHEN um relatório soma uma compra parcelada no cartão THEN o sistema SHALL contar a parcela N no mesmo dia da data da compra, N-1 meses depois, e no último dia do mês quando esse dia não existe (AD-006).
3. **REL-03** WHEN um relatório soma despesas THEN o sistema SHALL deixar de fora as despesas pendentes, as transferências, os pagamentos de fatura e os ajustes de saldo.
4. **REL-04** WHEN o dashboard ou um relatório de despesas mostra um período THEN o sistema SHALL mostrar à parte, como "A pagar", o total das despesas pendentes do período.
5. **REL-05** WHEN um relatório soma receitas THEN o sistema SHALL contar só as receitas efetivadas, na data delas, sem transferências e sem ajustes de saldo.
6. **REL-06** WHEN o sistema calcula o gasto de um orçamento THEN o sistema SHALL usar as despesas de REL-01 a REL-03 no mês do orçamento.
7. **REL-07** WHEN um relatório mostra um período passado THEN o sistema SHALL incluir nas receitas e despesas as transações efetivadas de contas excluídas, deixando essas contas fora dos totais de saldo (SALDO-31).
8. **REL-08** WHEN um relatório usa a data de hoje ou os limites de um mês THEN o sistema SHALL usar o calendário no fuso de Brasília (AD-008).
9. **REL-09** WHEN um relatório agrupa por hora do dia THEN o sistema SHALL usar a hora no fuso de Brasília.
10. **REL-10** WHEN um relatório calcula valores em dinheiro THEN o sistema SHALL fazer todas as contas em decimal, sem ponto flutuante, e arredondar para duas casas só no resultado final.
11. **REL-11** WHEN um relatório projeta uma data num mês que não tem aquele dia THEN o sistema SHALL usar o último dia do mês (AD-006).
12. **REL-12** IF o parâmetro `months` de uma rota de relatório não for um número inteiro de 1 a 24 THEN o sistema SHALL responder HTTP 400 com a mensagem "O parâmetro months aceita de 1 a 24."

**Independent Test**: com uma despesa efetivada de R$ 100,00, uma pendente de R$ 50,00 e uma compra no cartão de R$ 80,00 feita no dia 10, com a fatura ainda aberta, o mês mostra R$ 180,00 de despesas e R$ 50,00 "A pagar", no dashboard, na pizza e na comparação mensal; uma TV de R$ 1.200,00 em 12x comprada em 31/01 conta R$ 100,00 em 31/01, 28/02, 31/03 e assim por diante; uma despesa lançada às 22h de Brasília aparece às 22h no mapa de calor; `months=1000` recebe 400.

---

### P1: Patrimônio, liquidez e reservas ⭐ MVP

**User Story**: Como usuário, quero ver quanto eu tenho de verdade, separando o dinheiro disponível das reservas, dos investimentos e do que já devo no cartão.

**Why P1**: hoje o patrimônio ignora a dívida do cartão, os cofrinhos ficam fora de tudo e o histórico repete meses (FIN-32 e FIN-33).

**Acceptance Criteria**:
1. **REL-13** WHEN o sistema calcula o patrimônio THEN o sistema SHALL somar os saldos das contas ativas e subtrair as compras não pagas de todos os cartões.
2. **REL-14** WHEN o sistema calcula o dinheiro disponível THEN o sistema SHALL somar só as contas correntes, as poupanças e as carteiras ativas.
3. **REL-15** WHEN o dashboard ou um relatório mostra o patrimônio THEN o sistema SHALL separá-lo em disponível, reservas (cofrinhos), investimentos e faturas em aberto.
4. **REL-16** WHEN o sistema monta o histórico do patrimônio THEN o sistema SHALL calcular o patrimônio no fim de cada mês pelas regras de REL-13, com as movimentações efetivadas até aquele dia e as compras no cartão ainda não pagas nele.
5. **REL-17** WHEN o sistema monta um histórico mensal THEN o sistema SHALL usar cada mês do calendário uma vez só, sem pular nem repetir meses.
6. **REL-18** WHEN o dashboard mostra as faturas do mês THEN o sistema SHALL somar o valor em aberto das faturas que vencem no mês atual.

**Independent Test**: com R$ 3.000,00 em conta corrente, R$ 800,00 num cofrinho, R$ 2.000,00 em investimento e R$ 450,00 de compras não pagas no cartão, o patrimônio é R$ 5.350,00, dividido em R$ 3.000,00 disponíveis, R$ 800,00 de reservas, R$ 2.000,00 investidos e R$ 450,00 de faturas; o histórico de seis meses a partir de 31/03/2026 mostra outubro a março, um mês de cada.

---

### P1: Score financeiro e dinheiro guardado ⭐ MVP

**User Story**: Como usuário, quero um score e uma taxa de poupança que reflitam o que eu realmente guardo e como estão meus orçamentos.

**Why P1**: hoje quatro orçamentos saudáveis tiram os 20 pontos da parte de orçamentos (FIN-26), e os aportes em metas não contam como dinheiro guardado.

**Acceptance Criteria**:
1. **REL-19** WHEN o sistema calcula a parte de orçamentos do score THEN o sistema SHALL descontar 5 pontos por orçamento do mês que passou do limite, até zerar os 20 pontos dessa parte.
2. **REL-20** WHEN o sistema calcula o dinheiro guardado no mês THEN o sistema SHALL somar o que entrou nos cofrinhos e nas contas de investimento vindo das outras contas e subtrair o que saiu deles para as outras contas.
3. **REL-21** WHEN o sistema calcula a taxa de poupança THEN o sistema SHALL dividir o dinheiro guardado no mês pelas receitas do mês (REL-05).
4. **REL-22** IF as receitas do mês forem zero THEN o sistema SHALL devolver a taxa de poupança como indisponível, sem dividir por zero.

**Independent Test**: com quatro orçamentos dentro do limite, a parte de orçamentos vale 20 pontos, e com um estourado, 15; com R$ 5.000,00 de receitas, um aporte de R$ 500,00 numa meta, uma transferência de R$ 300,00 para investimento e um resgate de R$ 100,00, o dinheiro guardado é R$ 700,00 e a taxa, 14,0%; alocar o saldo livre de um cofrinho não muda o dinheiro guardado.

---

### P1: Telas e exportação ⭐ MVP

**User Story**: Como usuário, quero que a tela de relatórios nunca mostre valores impossíveis e que a exportação funcione com qualquer transação.

**Why P1**: hoje a média zero aparece como "Infinity%", uma falha deixa a tela sem resposta (FE-18) e o PDF quebra com transações sem conta (FIN-24).

**Acceptance Criteria**:
1. **REL-23** IF a média usada numa comparação for zero THEN a interface SHALL mostrar "Sem histórico para comparar" no lugar da porcentagem.
2. **REL-24** IF um bloco do relatório falhar ao carregar THEN a interface SHALL mostrar o erro só naquele bloco, com a opção de tentar de novo, sem tirar os outros blocos da tela.
3. **REL-25** WHEN a exportação em PDF inclui transações sem conta THEN o sistema SHALL gerar o arquivo e deixar a conta em branco nessas linhas.

**Independent Test**: um monitor de foco numa categoria sem gastos nos 6 meses anteriores mostra "Sem histórico para comparar"; com a rota da comparação mensal fora do ar, só esse gráfico mostra o erro, e os demais carregam; exportar em PDF um período com uma transação sem conta gera o arquivo.

---

## Edge Cases

- Despesa pendente de um mês passado, nunca efetivada: continua em "A pagar" daquele mês e fora das despesas (REL-03, REL-04).
- Transferência entre um cofrinho e uma conta de investimento: não muda o dinheiro guardado, porque as duas contas são de reserva ou investimento (REL-20).
- Pagamento de fatura: não entra nas despesas, porque as compras já contaram na data delas (REL-03).
- Ajuste de saldo de R$ 0,20 para baixo: muda o saldo e o patrimônio, mas não aparece nas despesas (REL-03).
- Projeção para o dia 31 de fevereiro: vira 28 ou 29 de fevereiro, e o mês seguinte volta ao dia 31 (REL-11).
- Orçamento de Comida com uma compra parcelada: cada mês do orçamento recebe só a parcela daquele mês (REL-02, REL-06).
- Mês sem nenhuma receita: a taxa de poupança aparece como indisponível (REL-22).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | REL-12 |
| Falha e falha parcial | REL-24, REL-25 |
| Idempotência, repetição e duplicidade | N/A because os relatórios só leem dados |
| Autorização e rate limiting | N/A because o acesso segue o isolamento e as travas do catálogo (specs `isolamento-entre-usuarios` e `permissoes-e-planos`) |
| Concorrência e ordem | N/A because os relatórios só leem dados |
| Ciclo de vida dos dados | REL-07 |
| Observabilidade | N/A because os relatórios não têm log próprio; os logs seguem a AD-019 |
| Falha de dependência externa | N/A because os relatórios não chamam serviços externos |
| Integridade das transições de estado | N/A because os relatórios não têm estados |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| REL-01 | P1: Transações que entram nos relatórios | T1, T2 | In Progress |
| REL-02 | P1: Transações que entram nos relatórios | T1, T2 | In Progress |
| REL-03 | P1: Transações que entram nos relatórios | T1, T2 | In Progress |
| REL-04 | P1: Transações que entram nos relatórios | T2, T4 | In Progress |
| REL-05 | P1: Transações que entram nos relatórios | T2 | In Progress |
| REL-06 | P1: Transações que entram nos relatórios | - | Pending |
| REL-07 | P1: Transações que entram nos relatórios | T2 | In Progress |
| REL-08 | P1: Transações que entram nos relatórios | T2, T4 | Implemented |
| REL-09 | P1: Transações que entram nos relatórios | - | Pending |
| REL-10 | P1: Transações que entram nos relatórios | T2 | In Progress |
| REL-11 | P1: Transações que entram nos relatórios | T1 | In Progress |
| REL-12 | P1: Transações que entram nos relatórios | T3 | Implemented |
| REL-13 | P1: Patrimônio, liquidez e reservas | T2, T4 | In Progress |
| REL-14 | P1: Patrimônio, liquidez e reservas | T2, T5 | Implemented |
| REL-15 | P1: Patrimônio, liquidez e reservas | T4 | In Progress |
| REL-16 | P1: Patrimônio, liquidez e reservas | T2 | In Progress |
| REL-17 | P1: Patrimônio, liquidez e reservas | T2 | In Progress |
| REL-18 | P1: Patrimônio, liquidez e reservas | T2, T4 | In Progress |
| REL-19 | P1: Score financeiro e dinheiro guardado | T5 | Implemented |
| REL-20 | P1: Score financeiro e dinheiro guardado | T2 | In Progress |
| REL-21 | P1: Score financeiro e dinheiro guardado | T5 | Implemented |
| REL-22 | P1: Score financeiro e dinheiro guardado | T5 | In Progress |
| REL-23 | P1: Telas e exportação | - | Pending |
| REL-24 | P1: Telas e exportação | - | Pending |
| REL-25 | P1: Telas e exportação | - | Pending |

**Coverage:** 25 total, 25 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] O total de despesas do mês é o mesmo no dashboard, na pizza por categoria, na divisão por classe, na comparação mensal e nos orçamentos.
- [ ] Nenhum relatório mostra "Infinity%", mês repetido ou dia deslocado pelo fuso.
- [ ] O patrimônio bate com a soma das contas ativas menos as compras não pagas dos cartões.
