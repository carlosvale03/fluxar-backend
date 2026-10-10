# Gestão do salário Specification

## Problem Statement

Quando o salário cai, o usuário não tem no app um jeito de separar primeiro o que vai guardar e o que já está comprometido no mês. Hoje ele faz cada transferência e cada aporte à mão, um por um (`transactions/services.py:49-72` e `goals/services.py:43-68`). Nada marca uma receita como salário, e não existe plano de divisão, geração em lote nem forma de desfazer um lote.

Origem: `docs/auditoria-2026-09.md`, seção 11, PROP-01, com a geração em um clique, a confirmação forte e o desfazer pedidos pelo usuário. As classes de despesa (spec `classes-de-despesa`, AD-025) dão o histórico dos gastos essenciais e dispensáveis.

## Goals

- [ ] O usuário divide o salário entre contas e metas com um clique, a partir de um plano salvo.
- [ ] Nenhuma divisão gera transações em dobro ou pela metade, e um engano se desfaz de uma vez.
- [ ] Ao lançar o salário, o usuário vê na hora a opção de dividir e o que ganha com isso.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Mover dinheiro de verdade no banco, por Pix | Depende do Open Finance com iniciação de pagamento (PROP-05) |
| Reconhecer o salário pelo crédito no banco | Depende do Open Finance (PROP-05) |
| Reserva virtual dentro da mesma conta | O usuário escolheu transações efetivadas; "Fica na conta do salário" só mostra o valor, sem separar saldo |
| Orçamento ou limite de gasto por parte do plano ou por classe | O plano divide o dinheiro; controlar os gastos fica com os orçamentos |
| Mais de um plano por usuário | Um plano por usuário; valores diferentes se ajustam na revisão |
| Aviso por e-mail ou push no dia do pagamento | Não existe notificação no app, e exigiria uma rotina agendada |
| Divisão de receitas que não são salário | Só as categorias de salário entram |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Geração com um clique, confirmação forte e desfazer | Como na PROP-01 aprovada | Decisão do usuário na auditoria (AD-026) | sim |
| Transações geradas | Efetivadas na hora, depois da confirmação forte | Decisão do usuário (AD-026) | sim |
| Regras do plano | Valor fixo ou percentual do salário, em ordem de prioridade; o que sobra fica livre na conta do salário | Decisão do usuário | sim |
| Quando a divisão aparece | A tela fica disponível a qualquer momento, para simular e dividir; ao lançar ou efetivar uma receita de salário, o app abre na hora o aviso com os benefícios | Decisão do usuário | sim |
| Como o plano começa | Três modelos da literatura, do mais geral ao mais detalhado, e o Personalizado, com o histórico do usuário ao lado | Decisão do usuário | sim |
| Partes dos modelos | Pague-se primeiro (George S. Clason, *O Homem Mais Rico da Babilônia*): Guardar 10%. 50/30/20 (Elizabeth Warren e Amelia Warren Tyagi, *All Your Worth*): Essenciais 50%, Dispensáveis 30% e Guardar 20%. Seis potes (T. Harv Eker, *Os Segredos da Mente Milionária*): Necessidades 55%, Liberdade financeira 10%, Poupança para gastos futuros 10%, Educação 10%, Diversão 10% e Doações 5% | São os percentuais das obras de origem | sim |
| Destinos das partes | Conta ativa que não seja cofrinho, meta ativa ou "Fica na conta do salário" | O dinheiro de uma meta entra só nela, sem o rateio do cofrinho compartilhado | sim |
| Destino inicial nas partes dos modelos | Partes de gastar ficam na conta do salário; partes de guardar ficam sem destino até o usuário escolher | Nos três modelos, só o que se guarda costuma sair da conta | sim |
| Categorias de salário | A categoria padrão Salário e as subcategorias dela, mais as que o usuário marcar | "Salário" já vem em todo cadastro | sim |
| Um plano por usuário | Um plano salvo, aplicado a qualquer recebimento de salário | Quem tem dois salários ajusta os valores na revisão | sim |
| Valor fixo e percentual no mesmo plano | Os valores fixos saem primeiro do recebido; os percentuais valem sobre o que sobra | Alterado em 2026-10-10 a pedido do usuário: com o percentual sobre o recebido inteiro, um plano com 100% em percentuais e uma parte fixa reduzia as últimas partes a quase nada (AD-056) | sim |
| Salário menor que o plano | Quando os valores fixos passam do recebido, a última parte fixa da ordem é reduzida até zero, depois a anterior, a revisão marca cada parte reduzida, e as percentuais ficam com zero | A ordem é a prioridade que o usuário definiu | sim |
| Saídas antes da divisão | Entram todas as saídas efetivadas da conta do recebimento (despesas, transferências, aportes em metas e pagamentos de fatura) da data do recebimento até hoje, menos as geradas por divisões do salário e os ajustes de saldo | Decisão do usuário em 2026-10-10: quem divide no fim de semana já gastou parte do salário, e só o dinheiro que saiu dessa conta saiu do salário (AD-057) | sim |
| Saída maior que a parte | A parte fica sem transação, a revisão mostra quanto ela passou, e as outras partes não mudam | Decisão do usuário em 2026-10-10 | sim |
| Travas dos percentuais na edição | Só na tela, durante a edição; não são salvas no plano | Servem para montar o plano, não mudam a divisão | sim |
| Centavos | Cada parte percentual é arredondada para baixo no centavo; a diferença fica livre | A divisão nunca passa do valor recebido | sim |
| Ajuste na revisão | Vale só para aquela divisão, sem mudar o plano | Salários que variam não obrigam a mexer no plano | sim |
| Confirmação forte | Revisão com a lista completa, a marcação "Confirmo que fiz essas transferências no banco" e o botão com a quantidade e o total | As transações nascem efetivadas, então o usuário afirma que fez as transferências | sim |
| Data das transações geradas | Hoje, no fuso de Brasília (AD-008) | É o dia em que o usuário faz as transferências no banco | sim |
| Prazo e condições para desfazer | Até 7 dias depois da geração, se nenhuma transação da divisão mudou e cada meta ainda tem o valor aportado; fora disso, recusado com o item que impede | O desfazer corrige um engano logo depois; desfazer só uma parte quebraria o lote | sim |
| Recebimentos a dividir | Os efetivados do mês atual e do anterior | Cobre o salário que cai no fim do mês e é dividido no começo do seguinte | sim |
| Aviso na importação | Não abre para receitas importadas; elas entram na lista de salários a dividir | Uma importação pode trazer vários salários de uma vez | sim |
| Referências do mês | Despesas recorrentes pendentes do mês e faturas que vencem no mês; média dos 3 últimos meses completos por classe | São os gastos obrigatórios e os padrões de gasto da ideia original | sim |
| Trava de plano | Recurso `gestao_do_salario` no catálogo de travas (AD-017); travado, a tela aparece travada e o aviso ao lançar o salário não abre | O administrador decide em quais planos o recurso entra | sim |
| Recebimento editado ou excluído depois da divisão | A divisão continua como está, sem recálculo | As transferências já aconteceram no banco | sim |
| Benefícios no aviso | Guardar antes de gastar, garantir as contas do mês e saber quanto sobra livre para gastar | Resume a ideia do "pague-se primeiro" | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Plano de divisão ⭐ MVP

**User Story**: Como usuário, quero montar um plano de divisão do salário a partir de um modelo conhecido ou do zero, para não refazer a conta todo mês.

**Why P1**: sem o plano não existe a divisão em um clique, e os modelos da literatura ajudam quem não sabe por onde começar.

**Acceptance Criteria**:
1. **SALARIO-01** WHEN o usuário abre a escolha do modelo THEN a interface SHALL oferecer os modelos Pague-se primeiro, 50/30/20 e Seis potes, cada um com a obra de origem e as partes, e o modelo Personalizado.
2. **SALARIO-02** WHEN o usuário escolhe um dos três modelos THEN o sistema SHALL montar o plano com as partes e os percentuais do modelo: Pague-se primeiro com Guardar 10%; 50/30/20 com Essenciais 50%, Dispensáveis 30% e Guardar 20%; Seis potes com Necessidades 55%, Liberdade financeira 10%, Poupança para gastos futuros 10%, Educação 10%, Diversão 10% e Doações 5%.
3. **SALARIO-03** WHEN o usuário escolhe o modelo Personalizado THEN o sistema SHALL começar o plano sem partes.
4. **SALARIO-04** WHEN o usuário adiciona ou edita uma parte THEN o sistema SHALL aceitar o nome, o destino e a regra da parte, que é um valor fixo em reais ou um percentual do salário.
5. **SALARIO-05** WHEN o usuário escolhe o destino de uma parte THEN o sistema SHALL aceitar uma conta ativa dele que não seja cofrinho, uma meta ativa dele ou "Fica na conta do salário".
6. **SALARIO-06** WHEN um dos três modelos monta o plano THEN o sistema SHALL deixar as partes de gastar (Essenciais, Dispensáveis, Necessidades, Educação, Diversão e Doações) com o destino "Fica na conta do salário" e as partes de guardar (Guardar, Liberdade financeira e Poupança para gastos futuros) sem destino.
7. **SALARIO-07** WHEN o usuário muda a ordem das partes THEN o sistema SHALL gravar a nova ordem, que define quais partes são atendidas primeiro.
8. **SALARIO-08** IF a soma dos percentuais do plano passar de 100% THEN o sistema SHALL recusar com HTTP 400 e a mensagem "A soma dos percentuais passa de 100%."
9. **SALARIO-09** IF o valor fixo de uma parte for menor que R$ 0,01 ou o percentual estiver fora do intervalo de 0,01% a 100% THEN o sistema SHALL recusar com HTTP 400 e o erro no campo da regra.
10. **SALARIO-10** IF o destino de uma parte for uma conta ou meta de outro usuário ou inexistente THEN o sistema SHALL responder HTTP 400 com o erro no campo do destino e a mesma mensagem de um ID inexistente (AD-010).
11. **SALARIO-11** IF o destino de uma parte for uma conta inativa, um cofrinho ou uma meta inativa THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Escolha uma conta ativa que não seja cofrinho ou uma meta ativa." no campo do destino.
12. **SALARIO-12** WHEN o usuário salva o plano THEN o sistema SHALL guardá-lo como o plano único dele, usado nas próximas divisões.
13. **SALARIO-13** WHEN o usuário simula uma divisão com um valor de salário THEN o sistema SHALL mostrar quanto vai para cada parte e quanto fica livre, sem criar nenhuma transação.
14. **SALARIO-14** WHEN o usuário configura a gestão do salário THEN o sistema SHALL aceitar as categorias de receita que contam como salário, com a categoria padrão Salário e as subcategorias dela marcadas de início.
15. **SALARIO-15** WHERE o recurso `gestao_do_salario` estiver liberado no plano do usuário, a interface SHALL deixar a gestão do salário acessível a qualquer momento pelo menu, para simular e para dividir.
16. **SALARIO-16** WHERE o recurso `gestao_do_salario` estiver travado no plano do usuário, o sistema SHALL tratar a gestão do salário como recurso travado, conforme PERM-15 e PERM-19.
17. **SALARIO-17** WHEN a conta do usuário é apagada definitivamente THEN o sistema SHALL apagar o plano e o registro das divisões dele junto com os demais dados (AD-018).
18. **SALARIO-18** WHEN o sistema registra um log da gestão do salário THEN o sistema SHALL omitir valores e nomes de contas, metas e partes (AD-019).

**Independent Test**: escolher o 50/30/20 monta Essenciais 50% e Dispensáveis 30% na conta do salário e Guardar 20% sem destino; trocar Guardar para a meta "Viagem" e salvar mantém o plano ao reabrir; uma parte de 60% junto com as outras recebe 400 "A soma dos percentuais passa de 100%."; simular R$ 3.000,00 mostra R$ 600,00 para Viagem e nenhuma transação criada.

---

### P1: Aviso ao receber o salário ⭐ MVP

**User Story**: Como usuário, quero que o app me ofereça a divisão assim que eu lançar o salário, para guardar antes de começar a gastar.

**Why P1**: o momento de dividir é quando o dinheiro chega; depois, ele já começou a ser gasto.

**Acceptance Criteria**:
1. **SALARIO-19** WHEN o usuário lança uma receita efetivada numa categoria de salário, ou efetiva uma receita pendente dessa categoria, THEN a interface SHALL abrir na hora o aviso da divisão do salário, com o valor recebido e as opções "Dividir agora" e "Agora não".
2. **SALARIO-20** WHEN o aviso da divisão aparece THEN a interface SHALL mostrar os benefícios de dividir: guardar antes de gastar, garantir as contas do mês e saber quanto sobra livre para gastar.
3. **SALARIO-21** WHEN o usuário escolhe "Dividir agora" THEN a interface SHALL abrir a revisão da divisão desse recebimento, já calculada pelo plano.
4. **SALARIO-22** IF o usuário ainda não tiver plano salvo quando escolher "Dividir agora" THEN a interface SHALL abrir antes a escolha do modelo.
5. **SALARIO-23** WHEN o usuário escolhe "Agora não" THEN a interface SHALL fechar o aviso e deixar o recebimento na lista de salários a dividir.
6. **SALARIO-24** WHEN o usuário abre a gestão do salário THEN a interface SHALL listar os recebimentos de salário efetivados do mês atual e do anterior que ainda não foram divididos.
7. **SALARIO-25** WHILE o recurso `gestao_do_salario` estiver travado no plano do usuário, a interface SHALL deixar de abrir o aviso da divisão.

**Independent Test**: lançar R$ 3.000,00 em Salário, já efetivada, abre o aviso com o valor e os três benefícios; "Agora não" fecha o aviso, e o recebimento aparece na lista de salários a dividir; efetivar a ocorrência pendente do salário do mês seguinte abre o aviso de novo; com o recurso travado, nenhum aviso abre.

---

### P1: Geração das transações ⭐ MVP

**User Story**: Como usuário, quero revisar a divisão e gerar todas as transações do plano com um clique, sem risco de gerar em dobro.

**Why P1**: é o que tira do usuário o trabalho de lançar cada transferência e cada aporte, e é onde um erro cria várias transações indesejadas de uma vez.

**Acceptance Criteria**:
1. **SALARIO-26** WHEN o sistema calcula a divisão de um recebimento THEN o sistema SHALL atender as partes na ordem do plano, tirando primeiro do valor recebido os valores fixos e aplicando os percentuais sobre o que sobra, e deixar livre na conta do salário o que restar.
2. **SALARIO-27** IF os valores fixos passarem do valor recebido THEN o sistema SHALL reduzir primeiro a última parte fixa da ordem, até zero, e seguir para as anteriores, marcando na revisão cada parte reduzida, e deixar as partes percentuais com zero.
3. **SALARIO-28** WHEN o sistema calcula uma parte percentual THEN o sistema SHALL arredondá-la para baixo no centavo, deixando a diferença livre na conta do salário.
4. **SALARIO-29** WHEN o usuário abre a revisão de uma divisão THEN a interface SHALL mostrar cada transação que será criada, com origem, destino, valor e data, além do total e de quanto fica livre.
5. **SALARIO-30** WHEN o usuário ajusta o valor de uma parte na revisão THEN o sistema SHALL usar o valor ajustado só nessa divisão, sem mudar o plano salvo.
6. **SALARIO-31** WHEN o usuário vai gerar as transações THEN a interface SHALL exigir a marcação "Confirmo que fiz essas transferências no banco" antes de habilitar o botão, que mostra a quantidade e o total, como "Gerar 4 transações de R$ 1.200,00".
7. **SALARIO-32** WHEN o usuário confirma a geração THEN o sistema SHALL criar de uma vez, já efetivadas e com a data de hoje no fuso de Brasília (AD-008), uma transferência da conta do salário para cada parte com destino numa conta e um aporte para cada parte com destino numa meta.
8. **SALARIO-33** WHEN a geração cria um aporte numa meta THEN o sistema SHALL somá-lo só a essa meta, mesmo que a conta-cofrinho dela seja de outras metas também.
9. **SALARIO-34** WHEN uma parte fica na conta do salário, tem como destino a própria conta do recebimento ou fica com valor zero THEN o sistema SHALL deixar de criar transação para ela.
10. **SALARIO-35** WHEN a geração cria as transações THEN o sistema SHALL marcar cada uma com o identificador da divisão que a criou.
11. **SALARIO-36** IF qualquer parte da geração falhar THEN o sistema SHALL desfazer o que já tinha criado nela e responder com o erro, sem nenhuma transação gravada.
12. **SALARIO-37** WHEN um pedido de geração chega de novo com o mesmo identificador de tentativa THEN o sistema SHALL devolver a mesma resposta do primeiro processamento, sem gerar de novo, como na AD-007.
13. **SALARIO-38** IF o usuário tentar dividir um recebimento que já foi dividido e não foi desfeito THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Este salário já foi dividido."
14. **SALARIO-39** WHILE houver dois pedidos de geração simultâneos para o mesmo recebimento, o sistema SHALL criar as transações de um só e responder ao outro conforme SALARIO-37 ou SALARIO-38.
15. **SALARIO-40** IF o recebimento escolhido não for uma receita efetivada, com conta, numa categoria de salário do usuário THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Escolha um salário recebido para dividir."
16. **SALARIO-41** IF alguma parte que precisa de destino estiver sem destino THEN o sistema SHALL recusar a geração com HTTP 400 e a mensagem "Escolha o destino de todas as partes."
17. **SALARIO-42** IF o destino de uma parte não estiver mais ativo na hora da geração THEN o sistema SHALL recusar com HTTP 400 e a mensagem "O destino da parte <nome> não está mais disponível."
18. **SALARIO-43** IF nenhuma parte da divisão gerar transação THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Nenhuma parte do plano gera transação."
19. **SALARIO-44** WHEN a geração termina THEN a interface SHALL mostrar as transações criadas e a opção "Desfazer divisão".

**Independent Test**: com o 50/30/20 e Guardar na meta "Viagem", dividir um salário de R$ 3.000,00 mostra na revisão um aporte de R$ 600,00 e R$ 2.400,00 livres; o botão só habilita depois da marcação e diz "Gerar 1 transação de R$ 600,00"; gerar cria o aporte efetivado, que entra só em Viagem mesmo com o cofrinho dividido com outra meta; reenviar o pedido com o mesmo identificador não cria nada novo; tentar dividir o mesmo salário de novo recebe 400 "Este salário já foi dividido."

---

### P1: Desfazer a divisão ⭐ MVP

**User Story**: Como usuário, quero desfazer de uma vez uma divisão gerada por engano, para voltar os saldos e as metas ao que eram.

**Why P1**: uma geração errada cria várias transações ao mesmo tempo, e apagar cada uma à mão não devolve o valor das metas (FIN-09).

**Acceptance Criteria**:
1. **SALARIO-45** WHEN o usuário pede para desfazer uma divisão THEN a interface SHALL mostrar as transações que serão removidas e pedir confirmação.
2. **SALARIO-46** WHEN o usuário confirma o desfazer THEN o sistema SHALL remover de uma vez todas as transações da divisão e devolver os saldos das contas e os valores das metas ao que eram antes dela.
3. **SALARIO-47** WHEN uma divisão é desfeita THEN o sistema SHALL liberar o recebimento para uma nova divisão.
4. **SALARIO-48** IF alguma transação da divisão tiver sido editada no valor, na data, no status ou na conta, ou excluída, ou uma meta não tiver mais o valor aportado pela divisão, THEN o sistema SHALL recusar o desfazer com HTTP 400 e uma mensagem que diga qual transação ou meta impede.
5. **SALARIO-49** IF o pedido de desfazer chegar mais de 7 dias depois da geração THEN o sistema SHALL recusar com HTTP 400 e a mensagem "O prazo para desfazer esta divisão acabou."
6. **SALARIO-50** IF o desfazer falhar no meio THEN o sistema SHALL manter a divisão inteira como estava.
7. **SALARIO-51** WHEN um pedido de desfazer chega para uma divisão já desfeita THEN o sistema SHALL responder que ela já foi desfeita, sem remover mais nada.

**Independent Test**: desfazer a divisão do exemplo anterior remove o aporte, e a meta Viagem e a conta do salário voltam aos valores de antes; o salário volta à lista de salários a dividir; com o aporte editado, o desfazer recebe 400 dizendo que o aporte em Viagem mudou; no 8º dia, recebe 400 "O prazo para desfazer esta divisão acabou."

---

### P1: Referências do mês e histórico ⭐ MVP

**User Story**: Como usuário, quero ver o que já está comprometido no mês e como eu costumo gastar, para escolher o modelo e ajustar o plano.

**Why P1**: é o que torna a divisão pessoal: o plano segue os gastos obrigatórios e os padrões de gasto do usuário, e não só uma regra genérica.

**Acceptance Criteria**:
1. **SALARIO-52** WHEN o usuário abre a gestão do salário THEN a interface SHALL mostrar o que está comprometido no mês: as despesas recorrentes pendentes do mês e o valor em aberto das faturas que vencem no mês.
2. **SALARIO-53** WHEN o usuário abre a gestão do salário THEN a interface SHALL mostrar a média mensal, nos 3 últimos meses completos, das receitas de salário, dos gastos por classe (AD-025) e da diferença entre as receitas de salário e o total das despesas.
3. **SALARIO-54** WHEN o usuário compara os modelos THEN a interface SHALL mostrar, ao lado de cada parte que corresponde a uma classe, a porcentagem do salário que essa classe ocupou no histórico: Essenciais e Necessidades para a classe Essencial; Dispensáveis e Diversão para a classe Dispensável.
4. **SALARIO-55** WHEN uma parte tem como destino uma meta com data-alvo THEN a interface SHALL mostrar ao lado dela quanto a meta pede por mês para chegar na data.
5. **SALARIO-56** IF o usuário tiver menos de 3 meses completos de histórico THEN a interface SHALL usar os meses que existem e avisar quantos entraram na média.

**Independent Test**: com um aluguel recorrente pendente de R$ 1.200,00 e uma fatura de R$ 450,00 vencendo no mês, a tela mostra R$ 1.650,00 comprometidos; com essenciais médios de R$ 1.860,00 sobre um salário médio de R$ 3.000,00, a parte Essenciais do 50/30/20 mostra "62,0% no seu histórico"; um usuário com um mês de histórico vê o aviso "Média de 1 mês".

---

### P1: Saídas desde o salário

**User Story**: Como usuário que divide o salário dias depois de recebê-lo, quero descontar das partes o que já saiu da conta do salário, para que as transações criadas levem só o que ainda falta separar.

**Why P1**: sem o desconto, a divisão transfere dinheiro que já foi gasto, e a conta do salário fica negativa.

**Acceptance Criteria**:
1. **SALARIO-64** WHEN o sistema monta a revisão de um recebimento THEN o sistema SHALL listar as saídas efetivadas da conta do recebimento (despesas, transferências, aportes em metas e pagamentos de fatura) com data entre a data do recebimento e hoje, menos as geradas por divisões do salário, os ajustes de saldo e as já descontadas numa divisão ativa.
2. **SALARIO-65** WHEN o sistema lista uma saída THEN o sistema SHALL sugerir a parte: para uma despesa, a primeira parte cuja referência é a classe efetiva da categoria dela (Essencial ou Dispensável); para uma transferência ou um aporte, a primeira parte cujo destino é a conta ou a meta de destino; nos demais casos, nenhuma parte.
3. **SALARIO-66** WHEN o usuário atribui saídas a uma parte THEN o sistema SHALL calcular a transação dessa parte como o valor dela pela regra de SALARIO-26 menos a soma das saídas atribuídas, sem ficar abaixo de zero.
4. **SALARIO-67** IF as saídas atribuídas a uma parte passarem do valor dela THEN o sistema SHALL deixar a parte sem transação, informar quanto ela passou e manter as outras partes como estão.
5. **SALARIO-68** WHEN a divisão é gerada THEN o sistema SHALL registrar quais saídas foram descontadas e em qual parte.
6. **SALARIO-69** IF uma saída enviada não estiver na lista de SALARIO-64 THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Saída não encontrada." no campo das saídas.
7. **SALARIO-70** WHEN uma divisão é desfeita THEN o sistema SHALL liberar as saídas descontadas nela para uma nova divisão.
8. **SALARIO-71** WHEN a interface mostra a revisão THEN a interface SHALL listar as saídas com a data, a descrição, o valor e a parte escolhida, já com a sugestão de SALARIO-65 e a opção "Não descontar", e mostrar em cada parte o valor calculado, o já gasto e o que será transferido.
9. **SALARIO-72** WHEN o sistema calcula o que fica livre THEN o sistema SHALL subtrair do recebido as transações da divisão e as saídas descontadas.

**Independent Test**: com R$ 200,00 calculados para Necessidades, com destino numa conta, e uma despesa Essencial de R$ 130,00 na conta do salário depois do recebimento, a revisão sugere a despesa em Necessidades e mostra transferência de R$ 70,00; com R$ 250,00 em saídas, a parte fica sem transação e mostra "passou R$ 50,00"; desfazer a divisão libera a despesa para a próxima.

---

### P2: Ajuda para montar o plano

**User Story**: Como usuário, quero entender cada modelo e cada parte e montar os percentuais sem fazer conta, para chegar a um plano que fecha.

**Why P2**: o plano funciona sem essa ajuda, mas quem não conhece os modelos não sabe o que é "Liberdade financeira" nem quanto sobra ao mexer num percentual.

**Acceptance Criteria**:
1. **SALARIO-57** WHEN a interface mostra um modelo ou uma parte de um modelo THEN a interface SHALL mostrar o que o modelo e a parte significam, com a obra de origem.
2. **SALARIO-58** WHEN o usuário muda o percentual de uma parte na edição THEN a interface SHALL ajustar as outras partes percentuais não travadas na proporção de cada uma, mantendo a soma dos percentuais de antes.
3. **SALARIO-59** WHEN o usuário trava uma parte percentual THEN a interface SHALL deixar o percentual dela fora dos ajustes de SALARIO-58.
4. **SALARIO-60** WHILE a soma dos percentuais passar de 100%, a interface SHALL mostrar o aviso "A soma dos percentuais passa de 100%." e impedir salvar o plano.
5. **SALARIO-61** WHEN o usuário tem um plano salvo THEN a interface SHALL permitir trocar de modelo a partir do resumo do plano, mantendo o plano salvo até o novo ser salvo.
6. **SALARIO-62** WHILE as categorias de salário já estiverem configuradas e houver salário a dividir, a interface SHALL mostrar a seção de receitas de salário recolhida, com as categorias escolhidas e a opção de abrir.
7. **SALARIO-63** WHEN o campo da simulação está preenchido THEN a interface SHALL mostrar o valor de cada parte pela regra de SALARIO-26, inclusive na edição, antes de salvar.

**Independent Test**: no 50/30/20, mudar Essenciais para 60% deixa Dispensáveis com 24% e Guardar com 16%; travar Guardar e mudar Essenciais para 60% deixa Dispensáveis com 20%; uma parte fixa de R$ 500,00 com salário simulado de R$ 3.000,00 mostra as partes percentuais sobre R$ 2.500,00; passar de 100% mostra o aviso e desabilita "Salvar plano".

---

## Edge Cases

- Dois salários no mês: cada recebimento é dividido pelo plano inteiro, e os valores fixos entram nas duas divisões se o usuário não ajustar na revisão (SALARIO-26, SALARIO-30).
- Parte com destino na própria conta do recebimento: não gera transação (SALARIO-34).
- Salário de R$ 1.000,00 com partes fixas que somam R$ 1.200,00: a última parte fixa é reduzida até zero, depois a anterior (SALARIO-27).
- Salário de R$ 3.000,00 com uma parte fixa de R$ 500,00 e partes de 50%, 30% e 20%: os percentuais valem sobre R$ 2.500,00 (R$ 1.250,00, R$ 750,00 e R$ 500,00), e nada fica livre (SALARIO-26).
- Parte de 33,33% sobre R$ 1.000,00: R$ 333,30, e a diferença fica livre (SALARIO-28).
- Meta concluída ou excluída depois de entrar no plano: a geração é recusada até o usuário trocar o destino (SALARIO-42).
- Plano só com partes que ficam na conta do salário: a geração é recusada, e a simulação continua mostrando a divisão (SALARIO-13, SALARIO-43).
- Receita de salário ainda pendente: pode ser simulada, mas não dividida (SALARIO-40).
- Recebimento de outro usuário: recebe a mesma resposta de um recebimento que não existe (SALARIO-40, AD-010).
- Salário importado por planilha: não abre o aviso e entra na lista de salários a dividir (SALARIO-24).
- Recebimento excluído depois da divisão: a divisão continua, e o desfazer segue as regras de SALARIO-48 e SALARIO-49.

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | SALARIO-08, SALARIO-09, SALARIO-11, SALARIO-40, SALARIO-41, SALARIO-42, SALARIO-43 |
| Falha e falha parcial | SALARIO-36, SALARIO-50 |
| Idempotência, repetição e duplicidade | SALARIO-37, SALARIO-38, SALARIO-51 |
| Autorização e rate limiting | SALARIO-10, SALARIO-16, SALARIO-40 |
| Concorrência e ordem | SALARIO-39 |
| Ciclo de vida dos dados | SALARIO-17, SALARIO-47, SALARIO-49 |
| Observabilidade | SALARIO-18 |
| Falha de dependência externa | N/A because a feature não chama serviços externos |
| Integridade das transições de estado | SALARIO-38, SALARIO-47, SALARIO-48 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SALARIO-01 | P1: Plano de divisão | T3, T9 | Verified |
| SALARIO-02 | P1: Plano de divisão | T2 | Verified |
| SALARIO-03 | P1: Plano de divisão | T2 | Verified |
| SALARIO-04 | P1: Plano de divisão | T3, T9 | Verified |
| SALARIO-05 | P1: Plano de divisão | T3, T9 | Verified |
| SALARIO-06 | P1: Plano de divisão | T2 | Verified |
| SALARIO-07 | P1: Plano de divisão | T3, T9 | Verified |
| SALARIO-08 | P1: Plano de divisão | T3 | Verified |
| SALARIO-09 | P1: Plano de divisão | T3 | Verified |
| SALARIO-10 | P1: Plano de divisão | T3 | Verified |
| SALARIO-11 | P1: Plano de divisão | T3 | Verified |
| SALARIO-12 | P1: Plano de divisão | T3 | Verified |
| SALARIO-13 | P1: Plano de divisão | T3, T9 | Verified |
| SALARIO-14 | P1: Plano de divisão | T3, T9 | Verified |
| SALARIO-15 | P1: Plano de divisão | T8 | Verified |
| SALARIO-16 | P1: Plano de divisão | T3, T8 | Verified |
| SALARIO-17 | P1: Plano de divisão | T1 | Verified |
| SALARIO-18 | P1: Plano de divisão | T3 | Verified |
| SALARIO-19 | P1: Aviso ao receber o salário | T12 | Verified |
| SALARIO-20 | P1: Aviso ao receber o salário | T12 | Verified |
| SALARIO-21 | P1: Aviso ao receber o salário | T10, T12 | Verified |
| SALARIO-22 | P1: Aviso ao receber o salário | T10 | Verified |
| SALARIO-23 | P1: Aviso ao receber o salário | T12 | Verified |
| SALARIO-24 | P1: Aviso ao receber o salário | T4, T8 | Verified |
| SALARIO-25 | P1: Aviso ao receber o salário | T12 | Verified |
| SALARIO-26 | P1: Geração das transações | T2 | Verified |
| SALARIO-27 | P1: Geração das transações | T2 | Verified |
| SALARIO-28 | P1: Geração das transações | T2 | Verified |
| SALARIO-29 | P1: Geração das transações | T4, T10 | Verified |
| SALARIO-30 | P1: Geração das transações | T2, T4, T10 | Verified |
| SALARIO-31 | P1: Geração das transações | T10 | Verified |
| SALARIO-32 | P1: Geração das transações | T5 | Verified |
| SALARIO-33 | P1: Geração das transações | T5 | Verified |
| SALARIO-34 | P1: Geração das transações | T2 | Verified |
| SALARIO-35 | P1: Geração das transações | T5 | Verified |
| SALARIO-36 | P1: Geração das transações | T5 | Verified |
| SALARIO-37 | P1: Geração das transações | T5 | Verified |
| SALARIO-38 | P1: Geração das transações | T5 | Verified |
| SALARIO-39 | P1: Geração das transações | T5 | Verified |
| SALARIO-40 | P1: Geração das transações | T4 | Verified |
| SALARIO-41 | P1: Geração das transações | T5 | Verified |
| SALARIO-42 | P1: Geração das transações | T5 | Verified |
| SALARIO-43 | P1: Geração das transações | T5 | Verified |
| SALARIO-44 | P1: Geração das transações | T10 | Verified |
| SALARIO-45 | P1: Desfazer a divisão | T11 | Verified |
| SALARIO-46 | P1: Desfazer a divisão | T6 | Verified |
| SALARIO-47 | P1: Desfazer a divisão | T6 | Verified |
| SALARIO-48 | P1: Desfazer a divisão | T6 | Verified |
| SALARIO-49 | P1: Desfazer a divisão | T6 | Verified |
| SALARIO-50 | P1: Desfazer a divisão | T6 | Verified |
| SALARIO-51 | P1: Desfazer a divisão | T6 | Verified |
| SALARIO-52 | P1: Referências do mês e histórico | T7, T8 | Verified |
| SALARIO-53 | P1: Referências do mês e histórico | T7, T8 | Verified |
| SALARIO-54 | P1: Referências do mês e histórico | T9 | Verified |
| SALARIO-55 | P1: Referências do mês e histórico | T9 | Verified |
| SALARIO-56 | P1: Referências do mês e histórico | T7, T8 | Verified |
| SALARIO-64 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-65 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-66 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-67 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-68 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-69 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-70 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-71 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-72 | P1: Saídas desde o salário | refactor | Pending |
| SALARIO-57 | P2: Ajuda para montar o plano | refactor | Pending |
| SALARIO-58 | P2: Ajuda para montar o plano | refactor | Pending |
| SALARIO-59 | P2: Ajuda para montar o plano | refactor | Pending |
| SALARIO-60 | P2: Ajuda para montar o plano | refactor | Pending |
| SALARIO-61 | P2: Ajuda para montar o plano | refactor | Pending |
| SALARIO-62 | P2: Ajuda para montar o plano | refactor | Pending |
| SALARIO-63 | P2: Ajuda para montar o plano | refactor | Pending |

**Coverage:** 56 total, 56 mapped to tasks, 0 unmapped; 56 implemented, 0 in progress, 0 pending

---

## Success Criteria

- [ ] Um usuário com o plano salvo vai do aviso à geração das transações em menos de 1 minuto.
- [ ] Nenhuma geração repetida, nem depois de timeout e reenvio, cria transações em dobro.
- [ ] Todo desfazer dentro das condições devolve saldos e metas exatamente aos valores de antes.
