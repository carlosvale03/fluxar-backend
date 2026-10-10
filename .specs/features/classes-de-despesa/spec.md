# Classes de despesa Specification

## Problem Statement

Hoje o usuário não consegue ver quanto do que gasta vai para o necessário e quanto vai para o que dá para cortar. As categorias de despesa só têm a árvore de categoria-mãe e subcategoria (`transactions/models.py:5-35`), nenhum campo diz a natureza do gasto, e o único relatório parecido, o de gastos fixos e variáveis, adivinha por palavras-chave (`reports/services.py:793-845`).

Origem: `docs/auditoria-2026-09.md`, seção 11, PROP-02. A gestão do salário (PROP-01) vai usar as classes como base das sugestões de divisão.

## Goals

- [ ] O usuário vê, no dashboard e nos relatórios, quanto das despesas do período foi para cada classe.
- [ ] A soma por classe, com "Sem classe", é sempre igual à soma por categoria do mesmo período.
- [ ] A lista de transações, a exportação e os relatórios filtram por classe com o mesmo significado.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Classe em categorias de receita | Decisão do usuário; reconhecer o salário fica para a gestão do salário (PROP-01) |
| Orçamento ou limite por classe | Decisão do usuário; o orçamento continua por categoria |
| Classe própria de uma transação, diferente da classe da categoria | A classe é da categoria |
| Relatório de gastos fixos e variáveis | Continua como está: usa outro critério, a recorrência |
| Divisão por classe na aba "Avançados" dos relatórios e no monitor de foco | Recursos travados por plano (`relatorios_avancados` e `monitor_de_foco`); entram com a feature `relatorios` |
| Coluna de classe na exportação em PDF e leitura da classe na importação | Só a exportação em XLSX ganha a coluna; a importação continua sem classe |
| Uso das classes na divisão do salário | Spec da gestão do salário (PROP-01) |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Quais classes existem | Duas classes padrão, Essencial e Dispensável; o usuário cria outras a partir das sugestões ou com nome próprio | Decisão do usuário (AD-025) | sim |
| Subcategoria com classe diferente da mãe | Herda a classe da mãe e pode trocar | Decisão do usuário (AD-025) | sim |
| Classe em categorias de receita | Não existe; só categorias de despesa têm classe | Decisão do usuário (AD-025) | sim |
| Classe nos orçamentos | Não entra; o orçamento continua por categoria | Decisão do usuário | sim |
| Limite de classes | 5 por usuário, contando as duas padrão, igual em todos os planos e fora do catálogo de travas | O usuário pediu no máximo 4 ou 5; com 5 cabem as duas padrão e as três sugestões | sim |
| Sugestões de classe | Dívidas (empréstimos, financiamentos e juros), Impostos e taxas (IPVA, IPTU, imposto de renda e tarifas) e Profissional (gastos de trabalho ou do próprio negócio) | Não repetem as classes padrão nem os nomes das categorias padrão | sim |
| Classes padrão | Não podem ser excluídas nem renomeadas; a cor pode mudar | A gestão do salário (PROP-01) e a divisão dos relatórios contam com elas | sim |
| Nome das classes | De 1 a 30 caracteres, único por usuário, sem diferença de maiúsculas e acentos | Evita "Dívidas" e "dividas" lado a lado | sim |
| Cor das classes | Cada classe tem uma cor, usada nos gráficos; "Sem classe" aparece em cinza | Os gráficos de categoria já usam a cor de cada categoria | sim |
| Exclusão de uma classe criada pelo usuário | As categorias que a usavam perdem a classe própria e seguem a herança, depois de o usuário ver quantas são | Não obriga a reclassificar antes de excluir | sim |
| Classe inicial das categorias padrão | Essencial: Casa (com Aluguel e Energia), Comida, Transporte e Educação. Dispensável: Lazer, Eletrônicos, Doces, Doação e Presente | Segue o exemplo da ideia: casa, comida e transporte essenciais; doces dispensáveis | sim |
| Usuários que já existem | Recebem as duas classes padrão, e as categorias principais de despesa com o nome de uma categoria padrão recebem a classe inicial dela | Evita começar com tudo em "Sem classe", sem adivinhar as categorias criadas pelo usuário | sim |
| Classe e histórico | Os relatórios usam a classe atual da categoria, inclusive nos meses passados | A classe é da categoria, não de cada lançamento | sim |
| Onde a divisão aparece | No gráfico de despesas do dashboard e da tela Relatórios, que vêm dos gráficos simples | São recursos essenciais e ficam visíveis em qualquer plano | sim |
| Filtro "Sem classe" | Traz as despesas e compras no cartão sem classe efetiva ou sem categoria | Ajuda a achar o que falta classificar | sim |
| Categorias criadas pela importação | Sem classe própria; a subcategoria criada dentro de uma categoria com classe herda a dela | A planilha não traz classe | sim |
| Recurso essencial | Classes, classe das categorias, filtro e divisão por classe liberados em todos os planos; a coluna da exportação XLSX segue a trava `exportacao_xlsx` | Fazem parte de categorias, filtros e gráficos simples, que já são essenciais (AD-017) | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Classes do usuário ⭐ MVP

**User Story**: Como usuário, quero ter as classes Essencial e Dispensável prontas e poder criar outras, até 5, para separar meus gastos do meu jeito.

**Why P1**: sem as classes não existe a divisão, e o limite com sugestões evita classes repetidas ou demais.

**Acceptance Criteria**:
1. **CLASSE-01** WHEN um usuário é criado THEN o sistema SHALL criar para ele as classes Essencial e Dispensável.
2. **CLASSE-02** WHEN a interface pede as classes do usuário THEN o sistema SHALL devolver a lista completa, sem paginação.
3. **CLASSE-03** WHEN o usuário abre o gerenciamento de classes THEN a interface SHALL oferecer como sugestão as classes Dívidas, Impostos e taxas e Profissional que ele ainda não criou.
4. **CLASSE-04** WHEN o usuário cria uma classe, a partir de uma sugestão ou com nome próprio, THEN o sistema SHALL gravá-la com o nome e a cor escolhidos.
5. **CLASSE-05** IF o usuário tentar criar uma classe quando já tem 5 THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Limite de 5 classes atingido."
6. **CLASSE-06** IF o nome da classe estiver vazio ou tiver mais de 30 caracteres THEN o sistema SHALL recusar com HTTP 400 e o erro no campo do nome.
7. **CLASSE-07** IF o nome repetir o de outra classe do usuário, sem diferença de maiúsculas e acentos, THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Já existe uma classe com esse nome." no campo do nome.
8. **CLASSE-08** IF o usuário tentar excluir ou renomear Essencial ou Dispensável THEN o sistema SHALL recusar com HTTP 400 e a mensagem "As classes padrão não podem ser excluídas nem renomeadas."
9. **CLASSE-09** WHEN o usuário pede para excluir uma classe que ele criou THEN a interface SHALL mostrar quantas categorias a usam e só excluir depois da confirmação.
10. **CLASSE-10** WHEN uma classe é excluída THEN o sistema SHALL remover a classe própria das categorias que a usavam, que passam a seguir a herança de CLASSE-16.
11. **CLASSE-11** IF a exclusão de uma classe falhar no meio THEN o sistema SHALL manter a classe e as categorias como estavam.
12. **CLASSE-12** WHILE houver pedidos simultâneos de criação de classes do mesmo usuário, o sistema SHALL manter o limite de 5 classes e os nomes sem repetição.
13. **CLASSE-13** WHILE o usuário estiver em qualquer plano, o sistema SHALL manter liberados as classes, a classe das categorias, o filtro por classe e a divisão por classe dos gráficos simples, como recursos essenciais (AD-017).
14. **CLASSE-14** WHEN a conta do usuário é apagada definitivamente THEN o sistema SHALL apagar as classes dele junto com os demais dados (AD-018).
15. **CLASSE-15** WHEN o sistema registra um log de uma operação com classes THEN o sistema SHALL omitir o nome da classe, como já vale para categorias (AD-019).

**Independent Test**: um usuário novo vê Essencial e Dispensável; cria Dívidas pela sugestão e mais duas classes; a sexta recebe 400 "Limite de 5 classes atingido."; "dividas" recebe o erro de nome repetido; excluir Dívidas, usada por duas categorias, avisa que duas categorias serão afetadas e as deixa sem classe própria.

---

### P1: Classe das categorias ⭐ MVP

**User Story**: Como usuário, quero definir a classe de cada categoria de despesa, com as subcategorias herdando a da mãe e podendo trocar, para classificar meus gastos uma vez só.

**Why P1**: é a classe da categoria que classifica cada gasto; sem a herança, cada subcategoria precisaria de uma classe escolhida à mão.

**Acceptance Criteria**:
1. **CLASSE-16** WHEN o sistema calcula a classe efetiva de uma categoria de despesa THEN o sistema SHALL usar a classe própria dela; sem classe própria, a classe efetiva da categoria-mãe; e "Sem classe" quando nenhuma das duas existir.
2. **CLASSE-17** WHEN o usuário cria ou edita uma categoria de despesa THEN o sistema SHALL aceitar uma classe dele ou nenhuma classe.
3. **CLASSE-18** WHEN a API devolve uma categoria de despesa THEN o sistema SHALL incluir a classe própria, a classe efetiva e se a efetiva é herdada.
4. **CLASSE-19** WHEN a interface mostra as categorias de despesa THEN a interface SHALL mostrar a classe efetiva de cada uma, com a cor da classe, e indicar quando ela é herdada da categoria-mãe.
5. **CLASSE-20** WHEN o usuário cria uma subcategoria THEN a interface SHALL deixá-la herdando a classe da mãe, com a opção de escolher outra.
6. **CLASSE-21** IF o usuário tentar dar classe a uma categoria de receita THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Categorias de receita não têm classe." no campo da classe.
7. **CLASSE-22** WHEN uma categoria de despesa passa a ser de receita THEN o sistema SHALL remover a classe própria dela.
8. **CLASSE-23** IF a classe enviada for de outro usuário ou não existir THEN o sistema SHALL responder HTTP 400 com o erro no campo da classe e a mesma mensagem de um ID inexistente (AD-010).
9. **CLASSE-24** WHEN um usuário é criado THEN o sistema SHALL dar a classe Essencial às categorias padrão Casa, Comida, Transporte e Educação, e a classe Dispensável a Lazer, Eletrônicos, Doces, Doação e Presente.
10. **CLASSE-25** WHEN as classes são implantadas THEN o sistema SHALL criar Essencial e Dispensável para cada usuário que já existe e dar a classe inicial de CLASSE-24 às categorias principais de despesa dele com o nome de uma categoria padrão, sem diferença de maiúsculas e acentos.
11. **CLASSE-26** WHEN a importação cria uma categoria THEN o sistema SHALL criá-la sem classe própria.
12. **CLASSE-27** WHILE uma categoria estiver excluída, o sistema SHALL manter a classe dela, para que as transações antigas continuem classificadas nos relatórios.

**Independent Test**: com Comida em Essencial, criar Delivery dentro dela mostra "Essencial (herdada)"; trocar Delivery para Dispensável muda só ela; tirar a classe de Delivery volta a herdar Essencial; dar classe a Salário recebe 400; o ID de uma classe de outro usuário recebe a mesma resposta de um ID inexistente.

---

### P1: Divisão das despesas por classe ⭐ MVP

**User Story**: Como usuário, quero ver no dashboard e nos relatórios quanto das minhas despesas do período foi para cada classe.

**Why P1**: é o objetivo da feature: mostrar quanto vai para o necessário e quanto vai para o que dá para cortar.

**Acceptance Criteria**:
1. **CLASSE-28** WHEN o gráfico de despesas do dashboard ou da tela Relatórios é carregado THEN o sistema SHALL devolver o total de despesas do período por classe efetiva, com "Sem classe" para as despesas sem classe efetiva ou sem categoria.
2. **CLASSE-29** WHEN o sistema monta a divisão por classe THEN o sistema SHALL usar exatamente as mesmas transações da divisão por categoria do mesmo gráfico, com o mesmo total.
3. **CLASSE-30** WHEN um relatório classifica uma despesa THEN o sistema SHALL usar a classe efetiva atual da categoria dela, inclusive nos períodos passados.
4. **CLASSE-31** WHEN a interface mostra a divisão por classe THEN a interface SHALL mostrar o valor e a porcentagem de cada classe sobre o total do período, com uma casa decimal, na cor da classe e em cinza para "Sem classe".
5. **CLASSE-32** WHEN o período não tem despesas THEN a interface SHALL mostrar a divisão por classe vazia, com a mensagem "Nenhuma despesa no período."
6. **CLASSE-33** WHEN o usuário clica numa classe do gráfico THEN a interface SHALL abrir a lista de transações filtrada por essa classe e pelo mesmo período.

**Independent Test**: com R$ 600,00 em Comida (Essencial), R$ 300,00 em Doces (Dispensável) e R$ 100,00 sem categoria no mês, o gráfico mostra Essencial R$ 600,00 (60,0%), Dispensável R$ 300,00 (30,0%) e Sem classe R$ 100,00 (10,0%), com o mesmo total do gráfico por categoria; passar Doces para Essencial muda também os meses anteriores.

---

### P1: Filtro e exportação por classe ⭐ MVP

**User Story**: Como usuário, quero filtrar as transações por classe e levar a classe na exportação.

**Why P1**: sem o filtro, o usuário vê o total da classe, mas não chega aos lançamentos que o formam.

**Acceptance Criteria**:
1. **CLASSE-34** WHEN a lista de transações recebe uma ou mais classes no filtro THEN o sistema SHALL devolver as despesas e compras no cartão cuja classe efetiva é uma delas.
2. **CLASSE-35** WHEN o filtro de classe inclui "Sem classe" THEN o sistema SHALL incluir as despesas e compras no cartão sem classe efetiva ou sem categoria.
3. **CLASSE-36** WHILE o filtro de classe estiver ativo, o sistema SHALL deixar de fora receitas, transferências e pagamentos de fatura.
4. **CLASSE-37** WHEN o filtro de classe é usado junto com o de categoria THEN o sistema SHALL devolver só as transações que atendem aos dois.
5. **CLASSE-38** IF o filtro de classe tiver um valor que não seja uma classe do usuário nem o valor de "Sem classe" THEN o sistema SHALL responder HTTP 400 com a mensagem "Classe inválida no filtro: <valor>."
6. **CLASSE-39** WHEN a exportação ou um relatório que aceita o filtro de categoria recebe o filtro de classe THEN o sistema SHALL aplicá-lo com o mesmo significado da lista de transações (AD-022).
7. **CLASSE-40** WHEN o usuário exporta as transações em XLSX THEN o sistema SHALL incluir a coluna "Classe", com a classe efetiva de cada despesa e compra no cartão, "Sem classe" quando não houver e vazia nas demais transações.

**Independent Test**: filtrar por Dispensável traz as despesas de Doces, inclusive as compras no cartão, e nenhuma receita; "Sem classe" traz a despesa sem categoria; Dispensável com a categoria Comida não traz nada; exportar em XLSX com o mesmo filtro gera as mesmas linhas, com a coluna Classe preenchida.

---

## Edge Cases

- Categoria-mãe sem classe com uma subcategoria que tem classe própria: a subcategoria usa a dela, e as despesas lançadas na mãe ficam em "Sem classe" (CLASSE-16).
- Subcategoria movida para outra categoria-mãe: sem classe própria, passa a herdar a da nova mãe (CLASSE-16).
- Classe excluída que só as subcategorias usavam: elas voltam a herdar a classe da mãe (CLASSE-10, CLASSE-16).
- Compra parcelada no cartão: cada parcela entra na classe da categoria da compra, no mesmo período em que o gráfico por categoria a conta (CLASSE-29).
- Filtro com uma classe e "Sem classe" juntos: traz os dois grupos (CLASSE-34, CLASSE-35).
- Usuário existente com a categoria "comida", em minúsculas: recebe Essencial na implantação (CLASSE-25).
- Usuário existente que renomeou "Comida" para "Mercado": a categoria fica sem classe, e ele escolhe a classe (CLASSE-25).
- Porcentagens arredondadas com uma casa: a soma pode dar 99,9% ou 100,1% (CLASSE-31).
- Valores da divisão por classe: texto decimal com duas casas, como em todo relatório (CONTRATO-16).
- Criar uma classe com o nome de uma sugestão já criada: recebe o erro de nome repetido (CLASSE-07).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | CLASSE-05, CLASSE-06, CLASSE-07, CLASSE-21, CLASSE-38 |
| Falha e falha parcial | CLASSE-11 |
| Idempotência, repetição e duplicidade | CLASSE-07: criar de novo a mesma classe é recusado como nome repetido; as demais operações repetidas dão o mesmo resultado |
| Autorização e rate limiting | CLASSE-13, CLASSE-23, CLASSE-38 |
| Concorrência e ordem | CLASSE-12 |
| Ciclo de vida dos dados | CLASSE-10, CLASSE-14, CLASSE-27 |
| Observabilidade | CLASSE-15 |
| Falha de dependência externa | N/A because a feature não chama serviços externos |
| Integridade das transições de estado | CLASSE-10, CLASSE-22 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CLASSE-01 | P1: Classes do usuário | T2 | Implemented |
| CLASSE-02 | P1: Classes do usuário | T3 | Implemented |
| CLASSE-03 | P1: Classes do usuário | - | Pending |
| CLASSE-04 | P1: Classes do usuário | T3 | In Progress |
| CLASSE-05 | P1: Classes do usuário | T3 | In Progress |
| CLASSE-06 | P1: Classes do usuário | T3 | Implemented |
| CLASSE-07 | P1: Classes do usuário | T3 | In Progress |
| CLASSE-08 | P1: Classes do usuário | T3 | In Progress |
| CLASSE-09 | P1: Classes do usuário | - | Pending |
| CLASSE-10 | P1: Classes do usuário | T3 | Implemented |
| CLASSE-11 | P1: Classes do usuário | T3 | Implemented |
| CLASSE-12 | P1: Classes do usuário | T3 | Implemented |
| CLASSE-13 | P1: Classes do usuário | T3, T5 | Implemented |
| CLASSE-14 | P1: Classes do usuário | T1 | Implemented |
| CLASSE-15 | P1: Classes do usuário | T3 | Implemented |
| CLASSE-16 | P1: Classe das categorias | T4 | Implemented |
| CLASSE-17 | P1: Classe das categorias | T4 | In Progress |
| CLASSE-18 | P1: Classe das categorias | T4 | Implemented |
| CLASSE-19 | P1: Classe das categorias | - | Pending |
| CLASSE-20 | P1: Classe das categorias | - | Pending |
| CLASSE-21 | P1: Classe das categorias | T4 | Implemented |
| CLASSE-22 | P1: Classe das categorias | T4 | Implemented |
| CLASSE-23 | P1: Classe das categorias | T4 | Implemented |
| CLASSE-24 | P1: Classe das categorias | T2 | Implemented |
| CLASSE-25 | P1: Classe das categorias | T1 | Implemented |
| CLASSE-26 | P1: Classe das categorias | T4 | Implemented |
| CLASSE-27 | P1: Classe das categorias | T4 | Implemented |
| CLASSE-28 | P1: Divisão das despesas por classe | T5 | Implemented |
| CLASSE-29 | P1: Divisão das despesas por classe | T5 | Implemented |
| CLASSE-30 | P1: Divisão das despesas por classe | T5 | Implemented |
| CLASSE-31 | P1: Divisão das despesas por classe | - | Pending |
| CLASSE-32 | P1: Divisão das despesas por classe | - | Pending |
| CLASSE-33 | P1: Divisão das despesas por classe | - | Pending |
| CLASSE-34 | P1: Filtro e exportação por classe | T6 | In Progress |
| CLASSE-35 | P1: Filtro e exportação por classe | T6 | In Progress |
| CLASSE-36 | P1: Filtro e exportação por classe | T6 | Implemented |
| CLASSE-37 | P1: Filtro e exportação por classe | T6 | Implemented |
| CLASSE-38 | P1: Filtro e exportação por classe | T6 | Implemented |
| CLASSE-39 | P1: Filtro e exportação por classe | T6 | In Progress |
| CLASSE-40 | P1: Filtro e exportação por classe | T7 | Implemented |

**Coverage:** 40 total, 33 mapped to tasks, 7 unmapped ⚠️ (backend em andamento)

---

## Success Criteria

- [ ] Um usuário novo abre o dashboard e já vê a divisão entre Essencial e Dispensável, sem configurar nada.
- [ ] Em qualquer período e filtro, a soma por classe é igual à soma por categoria.
- [ ] Nenhuma despesa fica fora da divisão: o que não tem classe aparece em "Sem classe".
