# Contratos frontend backend Specification

## Problem Statement

O frontend e o backend combinam formatos de jeitos diferentes em cada tela, e vários fluxos falham em silêncio. Oito rotas cortam a lista no 10º item e o frontend lê só a primeira página (CON-02), as preferências nunca são salvas porque os dois lados usam formatos diferentes (CON-04), o filtro de categoria aplica só o último ID (CON-05), os avisos de `useToast` nunca aparecem (FE-02) e datas sem hora aparecem e são salvas com um dia a menos (FE-03). Os valores em dinheiro viajam ora como texto, ora como número de ponto flutuante, e cada tela formata do seu jeito.

Origem: `docs/auditoria-2026-09.md`, seção 4 (CON-02, CON-04, CON-05, CON-07, CON-10, CON-11 e CON-12) e seção 5 (FE-02, FE-03, FE-06, FE-07, FE-08, FE-09, FE-14, FE-15 e FE-19), além de MAN-02 no que se refere à formatação de valores. A redefinição de senha e a sessão estão nas specs `autenticacao` e `sessao`.

## Goals

- [ ] Nenhuma lista da interface esconde itens que o usuário tem.
- [ ] Todo valor em dinheiro e toda data aparecem e são salvos exatamente como o usuário vê e digita.
- [ ] Todo erro chega ao usuário em português, no lugar certo, e nenhuma falha é silenciosa.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Redefinição de senha (CON-01) e sessão | Specs `autenticacao` (AUTH-23) e `sessao` |
| Detalhe da fatura com todas as compras (CON-03) e datas das faturas | Spec `faturas` (FATURA-43 e FATURA-44) |
| Ajuste de saldo com centavos (CON-06) | Spec `saldo` (SALDO-40 e SALDO-41) |
| Edição de transferência (CON-08) e pagamento sem fatura (CON-09) | Spec `saldo` (SALDO-14 e SALDO-18) |
| Cálculo dos relatórios, "Infinity%" e promessas sem tratamento na tela de relatórios (FE-18) | Feature `relatorios`; o formato dos valores que eles devolvem está nesta spec |
| Textos com `**` literal, link para `/suporte` e vitrine `/design-system` (FE-16, FE-17, FE-21) | Ajustes de interface |
| `console.log` com payloads no frontend (FE-20) | Higiene do frontend |
| Valores inventados na tela de configurações do admin (CON-10) | Painel admin; aqui só entra o formato da lista de logs |
| Cofrinho de arredondamento que repete depósitos (FE-10) | Feature `metas` |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Listas paginam ou vêm completas | Coleções pequenas (contas, cartões, faturas de um cartão, categorias, tags, orçamentos, metas e monitores de foco) vêm completas; transações e as listas de usuários e de logs do admin vêm paginadas | Decisão do usuário (AD-021) | sim |
| Filtro de categorias | Aceita várias categorias, e a categoria-pai inclui as subcategorias, igual na lista, na exportação e nos relatórios | Decisão do usuário (AD-022) | sim |
| Formato da resposta paginada | `count`, `total_pages`, `current_page`, `next`, `previous` e `results`, para todas as listas paginadas | É o formato que as transações e a tela já usam | sim |
| Tamanho da página | Padrão de 20 itens, máximo de 100 | São os valores atuais das transações | sim |
| Página além da última | HTTP 200 com `results` vazio e os totais corretos | Hoje o DRF responde 404 e a tela mostra "Erro ao carregar" (FE-07) | sim |
| Espera da busca | 300 milissegundos sem digitação | Hoje cada tecla dispara uma requisição (FE-07) | sim |
| Total do dia na lista de transações | Calculado pelo backend para o filtro inteiro | Hoje o "Saldo do Dia" soma só a página (FE-19) | sim |
| Filtro desconhecido | HTTP 400 com "Filtro desconhecido: <nome>." | Hoje um filtro que a rota não conhece é ignorado, e a tela mostra dados errados (CON-07, CON-12) | sim |
| Formato dos valores em dinheiro na API | Texto decimal com duas casas e ponto ("1234.56") em todas as rotas, inclusive nos relatórios | Hoje o CRUD envia texto e os relatórios enviam número de ponto flutuante (FIN-44) | sim |
| Exibição de valores | Um formatador único em reais, no formato brasileiro, inclusive nos eixos dos gráficos | Hoje há 21 cópias de `formatCurrency` e eixos sem formatação (MAN-02, FE-15) | sim |
| Datas | Sem hora: `AAAA-MM-DD`, tratadas como data de calendário, sem fuso. Com hora: ISO 8601 com o fuso | Evita o deslocamento de um dia no fuso de Brasília (FE-03, CON-11) | sim |
| Formato das preferências | O objeto `preferences` (moeda, tema, idioma e notificações) na leitura e na escrita | É o formato que a tela já envia e que o backend já devolve | sim |
| Idioma das mensagens da API | Português, inclusive as mensagens padrão do Django e do DRF | Hoje o backend está com `LANGUAGE_CODE = 'en-us'` | sim |
| Formato dos erros da API | O do DRF: erros de validação por campo, e `detail` com `code` nos demais | Evita mudar todas as rotas; a interface trata os dois formatos num lugar só | sim |
| Sistema de avisos | Só o Sonner | Hoje o Toaster do Radix, usado por `useToast`, nunca é montado (FE-02) | sim |
| Tempo máximo das requisições | 30 segundos; 120 segundos para importação e exportação | Hoje o axios não tem tempo máximo, e o aviso de "servidor acordando" pode travar a tela (FE-09) | sim |
| Aviso de "servidor acordando" | Pode ser fechado pelo usuário | Hoje ele cobre a tela sem saída | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Listas e paginação ⭐ MVP

**User Story**: Como usuário, quero ver todos os meus itens em cada lista e navegar pelas transações sem perder nada.

**Why P1**: hoje a 11ª tag, orçamento, meta ou cartão não aparece (CON-02), e trocar um filtro na página 3 mostra um erro falso (FE-07).

**Acceptance Criteria**:
1. **CONTRATO-01** WHEN a interface pede a lista de contas, cartões, faturas de um cartão, categorias, tags, orçamentos, metas ou monitores de foco THEN o sistema SHALL devolver a lista completa, sem paginação.
2. **CONTRATO-02** WHEN a interface pede a lista de transações, de usuários do admin ou de logs do admin THEN o sistema SHALL devolvê-la paginada, com os campos `count`, `total_pages`, `current_page`, `next`, `previous` e `results`.
3. **CONTRATO-03** WHEN uma lista paginada é pedida com `page_size` THEN o sistema SHALL devolver até esse número de itens, com máximo de 100 e padrão de 20 quando o parâmetro falta.
4. **CONTRATO-04** IF a página pedida passar da última THEN o sistema SHALL responder HTTP 200 com `results` vazio e os totais corretos.
5. **CONTRATO-05** WHILE uma lista for paginada, a interface SHALL mostrar o total de itens e os controles para navegar entre as páginas.
6. **CONTRATO-06** WHEN o usuário muda um filtro ou a busca de uma lista paginada THEN a interface SHALL voltar para a página 1 antes de buscar.
7. **CONTRATO-07** WHEN a interface recebe a resposta de uma busca que já foi substituída por outra mais recente THEN a interface SHALL descartá-la, sem mostrar os dados nem um erro.
8. **CONTRATO-08** WHEN o usuário digita na busca THEN a interface SHALL buscar só depois de 300 milissegundos sem digitação.
9. **CONTRATO-09** WHEN a lista de transações agrupa os lançamentos por dia THEN o sistema SHALL mostrar em cada dia o total de todas as transações daquele dia dentro do filtro, e não só as da página.

**Independent Test**: com 15 tags e 12 orçamentos, a tela de tags, o seletor de tags do formulário e a tela de orçamentos mostram todos; na lista de transações, trocar um filtro estando na página 3 mostra a página 1 do novo filtro sem erro, e o total de um dia com lançamentos em duas páginas é o mesmo nas duas.

---

### P1: Filtros ⭐ MVP

**User Story**: Como usuário, quero filtrar por várias categorias de uma vez e ver o mesmo resultado na lista, na exportação e nos relatórios.

**Why P1**: hoje o filtro aplica só a última categoria escolhida (CON-05), e a exportação de "despesas" deixa de fora as compras no cartão (FIN-25).

**Acceptance Criteria**:
1. **CONTRATO-10** WHEN a lista de transações recebe várias categorias no filtro THEN o sistema SHALL devolver as transações de qualquer uma delas.
2. **CONTRATO-11** WHEN o filtro inclui uma categoria-pai THEN o sistema SHALL incluir também as transações de todas as subcategorias dela.
3. **CONTRATO-12** WHEN a interface envia um filtro com vários valores THEN a interface SHALL repetir o parâmetro para cada valor (`categoryId=a&categoryId=b`).
4. **CONTRATO-13** WHEN a lista de transações, a exportação e os relatórios recebem o mesmo filtro THEN o sistema SHALL aplicar o mesmo significado nos três, como "despesas" incluir as compras no cartão.
5. **CONTRATO-14** IF uma rota receber um parâmetro de filtro que não conhece THEN o sistema SHALL responder HTTP 400 com a mensagem "Filtro desconhecido: <nome>."
6. **CONTRATO-15** WHEN a tela Recorrentes carrega THEN o sistema SHALL listar só as transações que pertencem a uma série recorrente.

**Independent Test**: filtrar por "Alimentação" (pai de "Restaurante" e "Mercado") e por "Transporte" mostra as transações das quatro categorias; exportar com o mesmo filtro gera o mesmo conjunto de linhas; um `?limit=50` recebe 400 "Filtro desconhecido: limit."

---

### P1: Valores em dinheiro ⭐ MVP

**User Story**: Como usuário, quero que todo valor apareça e seja salvo exatamente como eu vejo e digito, no formato brasileiro.

**Why P1**: hoje o frontend faz conta em ponto flutuante antes de enviar, os formulários de meta leem "1.500" como R$ 1,50 (FE-06) e o campo de valor não aceita negativo nem colagem (FE-14).

**Acceptance Criteria**:
1. **CONTRATO-16** WHEN a API envia ou recebe um valor em dinheiro THEN o sistema SHALL usá-lo como texto decimal com duas casas e ponto como separador ("1234.56"), em todas as rotas, inclusive nos relatórios.
2. **CONTRATO-17** WHEN a interface calcula um valor que vai ser enviado à API THEN a interface SHALL calcular sem ponto flutuante e enviar o resultado com exatamente duas casas.
3. **CONTRATO-18** WHEN a interface exibe um valor em dinheiro THEN a interface SHALL usar um formatador único em reais, no formato brasileiro ("R$ 1.234,56"), inclusive nos eixos dos gráficos.
4. **CONTRATO-19** WHEN o usuário digita um valor em dinheiro THEN a interface SHALL lê-lo pela regra de AD-009 ("1.500" é R$ 1.500,00; "12,5" é R$ 12,50).
5. **CONTRATO-20** WHERE o campo aceitar valor negativo, como o novo saldo no ajuste de saldo, a interface SHALL permitir digitar o sinal de menos.
6. **CONTRATO-21** WHEN o usuário cola um valor num campo de dinheiro THEN a interface SHALL interpretá-lo pela mesma regra da digitação ("100" colado vira R$ 100,00).

**Independent Test**: um aporte de "1.500" numa meta grava 1500.00; os relatórios devolvem "1234.56" em vez de 1234.56; o ajuste para "-50,00" é aceito; os eixos dos gráficos mostram "R$ 800,00".

---

### P1: Datas ⭐ MVP

**User Story**: Como usuário, quero ver e salvar as datas exatamente como escolho, sem perder um dia no caminho.

**Why P1**: hoje a data-alvo de uma meta recua um dia a cada edição (FE-03), e a exportação de setembro inclui o dia 1º de outubro (CON-11).

**Acceptance Criteria**:
1. **CONTRATO-22** WHEN a API envia ou recebe uma data sem hora THEN o sistema SHALL usar o formato `AAAA-MM-DD` e tratá-la como data de calendário, sem fuso.
2. **CONTRATO-23** WHEN a API envia uma data com hora THEN o sistema SHALL usar ISO 8601 com o fuso.
3. **CONTRATO-24** WHEN a interface exibe ou edita uma data sem hora THEN a interface SHALL mostrar o mesmo dia, mês e ano recebidos, em qualquer fuso do navegador ("2026-12-31" aparece como 31/12/2026 e é salvo como "2026-12-31").
4. **CONTRATO-25** WHEN a interface envia um filtro de período ou a data de um aporte, resgate ou pagamento THEN a interface SHALL enviá-la como `AAAA-MM-DD`, sem hora.

**Independent Test**: com o navegador no fuso de Brasília e depois no de Lisboa, editar só o nome de uma meta com data-alvo 31/12/2026 mantém "2026-12-31"; exportar setembro envia `2026-09-30` como fim do período e não inclui 1º de outubro.

---

### P1: Preferências ⭐ MVP

**User Story**: Como usuário, quero que as minhas preferências continuem salvas quando eu volto ao app.

**Why P1**: hoje a tela mostra "salvo", mas o backend ignora o objeto enviado, e o tema volta ao anterior (CON-04).

**Acceptance Criteria**:
1. **CONTRATO-26** WHEN o usuário salva as preferências THEN o sistema SHALL aceitar e devolver o mesmo formato, com o objeto `preferences` (moeda, tema, idioma e notificações).
2. **CONTRATO-27** WHEN o usuário recarrega a página depois de salvar THEN a interface SHALL mostrar as preferências salvas, inclusive o tema.
3. **CONTRATO-28** IF uma preferência tiver um valor inválido, como um tema diferente de claro, escuro ou sistema, THEN o sistema SHALL recusá-la com HTTP 400 e o erro no campo.

**Independent Test**: salvar o tema escuro e desligar as notificações por e-mail, recarregar e ver os dois valores mantidos; enviar o tema "roxo" recebe 400 no campo do tema.

---

### P1: Erros e avisos ⭐ MVP

**User Story**: Como usuário, quero entender o que deu errado, em português e no lugar certo, e poder tentar de novo.

**Why P1**: hoje nove telas perdem as mensagens de erro (FE-02), os erros de campo são descartados (FE-08) e uma requisição travada bloqueia a tela (FE-09).

**Acceptance Criteria**:
1. **CONTRATO-29** WHEN a API devolve um erro THEN o sistema SHALL escrever a mensagem em português, inclusive as mensagens padrão do Django e do DRF.
2. **CONTRATO-30** WHEN a API devolve erros de validação THEN o sistema SHALL mantê-los por campo, e a interface SHALL mostrar cada um no campo correspondente do formulário.
3. **CONTRATO-31** WHEN a API devolve um erro que não é de campo THEN a interface SHALL mostrar a mensagem `detail` num aviso do Sonner.
4. **CONTRATO-32** WHILE a interface estiver em uso, a interface SHALL usar um único sistema de avisos, o Sonner, em todas as telas.
5. **CONTRATO-33** IF uma requisição falhar por erro de rede, resposta 5xx ou tempo esgotado THEN a interface SHALL mostrar uma mensagem com a opção de tentar de novo, sem nenhuma falha silenciosa.
6. **CONTRATO-34** WHEN uma requisição passa do tempo máximo (30 segundos, ou 120 segundos para importação e exportação) THEN a interface SHALL cancelá-la e tratá-la conforme CONTRATO-33.
7. **CONTRATO-35** WHILE o aviso de "servidor acordando" estiver na tela, a interface SHALL permitir que o usuário o feche.

**Independent Test**: salvar um orçamento duplicado mostra a mensagem em português no campo da categoria; com o backend parado, abrir a tela de tags mostra o aviso do Sonner com "tentar de novo"; uma requisição que não responde é cancelada em 30 segundos com a mesma mensagem.

---

## Edge Cases

- Um usuário com mais de 100 tags: a lista completa vem inteira, porque coleções pequenas não paginam (CONTRATO-01).
- Filtro com uma subcategoria e a categoria-pai dela: cada transação aparece uma vez (CONTRATO-10, CONTRATO-11).
- Categoria-pai sem subcategorias: o filtro traz só as transações dela (CONTRATO-11).
- Relatório com valor zero: vem como "0.00" (CONTRATO-16).
- Data de 29/02 em ano bissexto: aparece e é salva como 29/02, sem mudar de dia (CONTRATO-24).
- Exportação que demora 90 segundos: termina normalmente, porque o tempo máximo dela é de 120 segundos (CONTRATO-34).
- Resposta 403 de trava de plano: segue PERM-19, com o aviso do plano, e não o aviso genérico de erro.

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | CONTRATO-03, CONTRATO-14, CONTRATO-28 |
| Falha e falha parcial | CONTRATO-33, CONTRATO-34 |
| Idempotência, repetição e duplicidade | N/A because o contrato não cria operações novas; repetir uma leitura devolve o mesmo resultado |
| Autorização e rate limiting | N/A because o contrato não muda quem acessa o quê; isso está nas specs `isolamento-entre-usuarios`, `autenticacao` e `permissoes-e-planos` |
| Concorrência e ordem | CONTRATO-07 |
| Ciclo de vida dos dados | N/A because o contrato não guarda nem apaga dados |
| Observabilidade | N/A because o contrato trata do que a tela mostra; os logs seguem AD-019 |
| Falha de dependência externa | CONTRATO-33 a CONTRATO-35 |
| Integridade das transições de estado | N/A because o contrato não tem estados |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CONTRATO-01 | P1: Listas e paginação | T1 | In Progress |
| CONTRATO-02 | P1: Listas e paginação | T1 | In Progress |
| CONTRATO-03 | P1: Listas e paginação | T1 | Implemented |
| CONTRATO-04 | P1: Listas e paginação | T1 | Implemented |
| CONTRATO-05 | P1: Listas e paginação | - | Pending |
| CONTRATO-06 | P1: Listas e paginação | - | Pending |
| CONTRATO-07 | P1: Listas e paginação | - | Pending |
| CONTRATO-08 | P1: Listas e paginação | - | Pending |
| CONTRATO-09 | P1: Listas e paginação | T4 | In Progress |
| CONTRATO-10 | P1: Filtros | T3 | In Progress |
| CONTRATO-11 | P1: Filtros | T3 | Implemented |
| CONTRATO-12 | P1: Filtros | - | Pending |
| CONTRATO-13 | P1: Filtros | T3 | Implemented |
| CONTRATO-14 | P1: Filtros | T2 | Implemented |
| CONTRATO-15 | P1: Filtros | T3 | In Progress |
| CONTRATO-16 | P1: Valores em dinheiro | T5 | In Progress |
| CONTRATO-17 | P1: Valores em dinheiro | - | Pending |
| CONTRATO-18 | P1: Valores em dinheiro | - | Pending |
| CONTRATO-19 | P1: Valores em dinheiro | - | Pending |
| CONTRATO-20 | P1: Valores em dinheiro | - | Pending |
| CONTRATO-21 | P1: Valores em dinheiro | - | Pending |
| CONTRATO-22 | P1: Datas | T3, T6 | Implemented |
| CONTRATO-23 | P1: Datas | T6 | Implemented |
| CONTRATO-24 | P1: Datas | - | Pending |
| CONTRATO-25 | P1: Datas | T6 | In Progress |
| CONTRATO-26 | P1: Preferências | T7 | In Progress |
| CONTRATO-27 | P1: Preferências | - | Pending |
| CONTRATO-28 | P1: Preferências | T7 | Implemented |
| CONTRATO-29 | P1: Erros e avisos | T8 | Implemented |
| CONTRATO-30 | P1: Erros e avisos | T8 | In Progress |
| CONTRATO-31 | P1: Erros e avisos | - | Pending |
| CONTRATO-32 | P1: Erros e avisos | - | Pending |
| CONTRATO-33 | P1: Erros e avisos | - | Pending |
| CONTRATO-34 | P1: Erros e avisos | - | Pending |
| CONTRATO-35 | P1: Erros e avisos | - | Pending |

**Coverage:** 35 total, 0 mapped to tasks, 35 unmapped ⚠️ (design e tasks ainda não iniciados)

---

## Success Criteria

- [ ] Nenhuma tela lê só a primeira página de uma lista, e nenhuma lista corta itens.
- [ ] Não existe nenhuma conta com valor em dinheiro feita em ponto flutuante no frontend, nem cópia local de formatação de moeda.
- [ ] Um teste de ponta a ponta no fuso de Lisboa e no de Brasília mostra e grava as mesmas datas.
