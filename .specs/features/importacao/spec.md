# Importacao Specification

## Problem Statement

A importação informa sucesso mesmo quando nada foi gravado: um erro numa linha desfaz o arquivo inteiro, e a resposta ainda diz que as linhas entraram (FIN-11). A leitura erra valores e tipos no formato brasileiro: "Crédito" com acento vira despesa (FIN-12) e "1.500" vira R$ 1,50 (FIN-22). Linhas de conta não mapeada caem na conta padrão ou ficam sem conta (FIN-23), a detecção de repetidos descarta compras reais (FIN-21), e não há limite de tamanho para um arquivo processado dentro da requisição (OPS-03). E nada aproveita as categorias que o usuário escolhe depois de importar: a cada extrato, as mesmas descrições voltam sem categoria.

Origem: seção 2 de `docs/auditoria-2026-09.md` (FIN-11, FIN-12, FIN-21, FIN-22, FIN-23) e seção 7 (OPS-03), no que se refere à importação, e seção 11 (preparativos da PROP-04).

## Goals

- [ ] Cada linha válida de um arquivo OFX, CSV ou XLSX é gravada com o valor, a data e o tipo que o usuário vê no arquivo.
- [ ] A resposta sempre diz exatamente quantas linhas foram gravadas, ignoradas e rejeitadas, e por quê.
- [ ] Reimportar um extrato nunca duplica lançamentos.
- [ ] A categoria que o usuário escolhe para uma descrição volta sugerida nas próximas importações.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Exportação em PDF e XLSX (FIN-24, FIN-25) | Pedido do usuário; fica na feature `relatorios` |
| Efeito das transações importadas no saldo | Spec `saldo` (AD-004); as transações importadas seguem as mesmas regras |
| Importar extrato ou fatura de cartão como compras no cartão | Não existe hoje e não foi pedido |
| Sugestão de categoria por um modelo treinado com dados de vários usuários | Fica com a previsão de gastos (PROP-04); aqui a sugestão usa só as correções do próprio usuário |
| Impedir que um usuário importe para a conta de outro (SEG-01) | Feature `isolamento-entre-usuarios` |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Linha inválida | Rejeita só a linha; as válidas são gravadas, e a resposta lista cada rejeitada com o número e o motivo | Decisão do usuário | sim |
| Tamanho máximo do arquivo | 5 MB e 10.000 linhas de dados | Decisão do usuário | sim |
| Mesmo arquivo ou extrato sobreposto enviado de novo | Ignora as linhas já importadas: no OFX pelo `FITID`; na planilha por data, valor, tipo e descrição na mesma conta, contando as repetições | Decisão do usuário | sim |
| Formatos aceitos | Só `.ofx`, `.csv` e `.xlsx`; `.xls` é recusado | É o escopo pedido, e o backend não tem leitor de `.xls` instalado (só o `openpyxl`) | sim |
| CSV brasileiro | Detecta `;` ou `,` como separador e UTF-8 ou Windows-1252 como codificação | É o que o Excel em português gera | sim |
| Valores em texto | Com vírgula, a vírgula é decimal; sem vírgula, o ponto é milhar quando todos os grupos seguintes têm três dígitos e a parte inteira não é zero (AD-009) | Corrige "1.500" (FIN-22) sem quebrar "12.5" nem "0.50" | sim |
| Datas em texto | dd/mm/aaaa, dd/mm/aa (ano 20aa) e aaaa-mm-dd | São os formatos dos extratos dos bancos brasileiros | sim |
| Palavras da coluna de tipo | Receita, entrada, crédito e C viram receita; despesa, saída, débito e D viram despesa; outro valor rejeita a linha | Corrige FIN-12 e impede que um valor desconhecido vire despesa em silêncio | sim |
| Conta não mapeada ou excluída | Rejeita a linha | Hoje a linha cai na conta padrão ou fica sem conta (FIN-23); conta excluída não recebe movimentação (AD-003) | sim |
| Texto maior que o campo | Rejeita a linha (descrição acima de 255 caracteres; categoria ou tag nova acima de 50) | Hoje um texto longo derruba a importação inteira (FIN-11) | sim |
| Linhas totalmente vazias | São puladas sem contar como lidas nem rejeitadas | Planilhas costumam ter linhas vazias no fim | sim |
| OFX com mais de uma conta | Recusado, com mensagem pedindo um arquivo por conta | Cada importação tem uma única conta de destino | sim |
| Tempo de resposta | Até 30 segundos para um arquivo dentro dos limites | Cabe com folga no timeout da requisição; o design decide como atingir | sim |
| Número da linha na resposta | Como aparece na planilha, com o cabeçalho na linha 1; no OFX, a posição da transação no arquivo | Hoje a resposta usa um índice que começa em 0 e não bate com o Excel | sim |
| Coluna de status | "pendente" ou "pending" importa como pendente; qualquer outro valor, como efetivada | É o comportamento atual e segue AD-002 | sim |
| Correções de categoria | Registradas e usadas para sugerir a categoria nas próximas importações, pelo histórico do próprio usuário | Decisão do usuário (AD-031) | sim |
| O que conta como correção | Definir ou trocar a categoria de uma transação importada | É o rótulo de que um classificador de categorias precisa | sim |
| Comparação das descrições | Sem diferença de maiúsculas, acentos, espaços extras e dígitos | "UBER *TRIP 1234" e "UBER *TRIP 5678" são o mesmo estabelecimento | sim |
| Qual correção vale | A mais recente para aquela descrição | O usuário pode ter mudado de ideia | sim |
| Linhas com categoria no arquivo | Mantêm a categoria do arquivo, sem sugestão | A categoria informada pelo usuário tem prioridade | sim |
| Como a sugestão aparece | A linha é gravada com a categoria sugerida e marcada como sugerida, e o resultado diz quantas foram | Revisar linha a linha antes de gravar não cabe em arquivos com milhares de linhas | sim |
| Categoria da correção excluída | A linha fica sem sugestão | O app não sugere uma categoria que o usuário tirou | sim |
| Uso das correções sem consentimento | Só nas sugestões do próprio usuário | O uso em modelos depende do consentimento de LGPD-33 | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Arquivos aceitos e limites ⭐ MVP

**User Story**: Como usuário, quero enviar o extrato do meu banco e saber na hora se o arquivo pode ser importado.

**Why P1**: hoje não há limite de tamanho (OPS-03), e um `.xls` falha com uma mensagem técnica.

**Acceptance Criteria**:
1. **IMPORT-01** WHEN o usuário envia um arquivo `.ofx`, `.csv` ou `.xlsx` THEN o sistema SHALL processá-lo pelas regras desta spec.
2. **IMPORT-02** IF o arquivo tiver outra extensão, inclusive `.xls`, THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "Formato não suportado. Envie um arquivo OFX, CSV ou XLSX."
3. **IMPORT-03** WHEN a interface pede o arquivo de importação THEN o sistema SHALL oferecer apenas arquivos `.ofx`, `.csv` e `.xlsx`.
4. **IMPORT-04** IF o arquivo tiver mais de 5 MB THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "O arquivo passa do limite de 5 MB.", antes de ler qualquer linha.
5. **IMPORT-05** IF o arquivo tiver mais de 10.000 linhas de dados THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "O arquivo passa do limite de 10.000 linhas.", sem gravar nenhuma linha.
6. **IMPORT-06** IF o arquivo não puder ser lido, ou não tiver as colunas mapeadas, THEN o sistema SHALL recusá-lo com HTTP 400, sem gravar nenhuma linha, com uma mensagem que diga se o arquivo está ilegível ou quais colunas faltam.
7. **IMPORT-07** IF um arquivo OFX tiver mais de uma conta THEN o sistema SHALL recusá-lo com HTTP 400 e a mensagem "O arquivo tem mais de uma conta. Exporte um arquivo por conta."
8. **IMPORT-08** WHEN um CSV é lido THEN o sistema SHALL aceitar `;` ou `,` como separador e UTF-8 ou Windows-1252 como codificação, sem pedir essa informação ao usuário.

**Independent Test**: enviar um `.xls`, um CSV de 6 MB e um CSV com 10.001 linhas recebe 400 com a mensagem de cada caso; um CSV exportado pelo Excel em português, com `;` e Windows-1252, é lido sem erro.

---

### P1: Valores e datas no formato brasileiro ⭐ MVP

**User Story**: Como usuário, quero que valores e datas do meu extrato sejam lidos como estão escritos, no formato brasileiro.

**Why P1**: hoje "1.500" vira R$ 1,50 e "1.234,56" falha (FIN-22).

**Acceptance Criteria**:
1. **IMPORT-09** WHEN um valor em texto tem vírgula THEN o sistema SHALL ler a vírgula como separador decimal e os pontos como separadores de milhar ("1.234,56" é R$ 1.234,56 e "R$ -45,00" é −R$ 45,00).
2. **IMPORT-10** WHEN um valor em texto não tem vírgula THEN o sistema SHALL ler os pontos como separadores de milhar quando todos os grupos depois deles têm três dígitos e a parte antes do primeiro ponto não é zero, e como separador decimal nos demais casos ("1.500" é R$ 1.500,00, "1.500.000" é R$ 1.500.000,00, "12.5" é R$ 12,50 e "0.50" é R$ 0,50).
3. **IMPORT-11** WHEN uma célula numérica do XLSX é lida THEN o sistema SHALL usar o número da célula, sem reinterpretar pontos e vírgulas.
4. **IMPORT-12** IF um valor não puder ser lido, for zero ou tiver mais de duas casas decimais THEN o sistema SHALL rejeitar a linha com o motivo "Valor inválido".
5. **IMPORT-13** WHEN uma data em texto é lida THEN o sistema SHALL aceitar os formatos dd/mm/aaaa, dd/mm/aa e aaaa-mm-dd, com o dia antes do mês nos formatos com barra ("04/03/2026" e "04/03/26" são 4 de março de 2026).
6. **IMPORT-14** WHEN uma célula de data do XLSX é lida THEN o sistema SHALL usar a data da célula.
7. **IMPORT-15** IF uma data não puder ser lida ou não existir no calendário THEN o sistema SHALL rejeitar a linha com o motivo "Data inválida".

**Independent Test**: uma planilha com os valores "1.234,56", "1.500", "12.5", "0.50", "R$ -45,00" e "abc" e as datas "04/03/2026", "04/03/26", "2026-03-04" e "29/02/2025" grava cada valor e cada data como nos exemplos e rejeita as linhas com "abc" e "29/02/2025".

---

### P1: Tipo, status e conta de cada linha ⭐ MVP

**User Story**: Como usuário, quero que cada linha vire receita ou despesa na conta certa, e que o que não der para entender seja rejeitado em vez de adivinhado.

**Why P1**: hoje "Crédito" com acento vira despesa (FIN-12) e linhas de conta não mapeada caem na conta padrão (FIN-23).

**Acceptance Criteria**:
1. **IMPORT-16** WHEN a linha tem coluna de tipo THEN o sistema SHALL importar como receita os valores "receita", "entrada", "crédito" e "C", e como despesa os valores "despesa", "saída", "débito" e "D", sem diferenciar maiúsculas nem acentos e gravando o valor sem sinal.
2. **IMPORT-17** IF a coluna de tipo tiver qualquer outro valor THEN o sistema SHALL rejeitar a linha com o motivo "Tipo desconhecido: <valor>".
3. **IMPORT-18** WHEN a linha de planilha não tem coluna de tipo, ou a transação vem de um OFX, THEN o sistema SHALL importar valor negativo como despesa e positivo como receita, gravando o valor sem sinal.
4. **IMPORT-19** WHEN uma transação de OFX é importada THEN o sistema SHALL usar como descrição o memo dela, ou o favorecido na falta do memo, ou "Sem descrição" na falta dos dois.
5. **IMPORT-20** WHEN a coluna de status da linha diz "pendente" ou "pending" THEN o sistema SHALL importar a transação como pendente; com qualquer outro valor, ou sem a coluna, SHALL importá-la como efetivada.
6. **IMPORT-21** IF a linha indicar uma conta não mapeada, ou uma conta excluída, THEN o sistema SHALL rejeitá-la com o motivo "Conta não mapeada: <nome>" ou "Conta excluída: <nome>".
7. **IMPORT-22** IF a linha não indicar conta e o usuário não tiver escolhido uma conta padrão THEN o sistema SHALL rejeitá-la com o motivo "Conta não informada".
8. **IMPORT-23** WHEN a linha traz categoria, subcategoria ou tag que o usuário ainda não tem THEN o sistema SHALL criá-la, reaproveitando uma existente com o mesmo nome sem diferenciar maiúsculas nem acentos.
9. **IMPORT-24** IF a descrição passar de 255 caracteres, ou o nome de uma categoria ou tag nova passar de 50, THEN o sistema SHALL rejeitar a linha com o motivo "Texto longo demais: <coluna>".
10. **IMPORT-25** WHEN a importação é do tipo transferência THEN o sistema SHALL criar cada linha como uma transferência entre as contas de origem e de destino mapeadas, pelas regras de transferência da spec `saldo`.
11. **IMPORT-26** IF numa linha de transferência as contas de origem e de destino forem a mesma, ou uma delas não estiver mapeada ou estiver excluída, THEN o sistema SHALL rejeitar a linha com o motivo "Origem e destino iguais", "Conta não mapeada: <nome>" ou "Conta excluída: <nome>".

**Independent Test**: uma planilha com os tipos "Crédito", "CREDITO", "Entrada", "Débito", "D" e "Transferido", mais uma linha de conta não mapeada, grava as cinco primeiras com o tipo certo e rejeita "Transferido" e a linha da conta não mapeada com os motivos indicados.

---

### P1: Resultado da importação ⭐ MVP

**User Story**: Como usuário, quero saber exatamente o que entrou, o que já existia e o que foi rejeitado, para corrigir só o necessário.

**Why P1**: hoje a resposta diz que as linhas entraram mesmo quando a importação inteira foi desfeita (FIN-11).

**Acceptance Criteria**:
1. **IMPORT-27** WHEN um arquivo é processado THEN o sistema SHALL gravar as linhas válidas e rejeitar apenas as inválidas.
2. **IMPORT-28** IF a gravação de uma linha falhar THEN o sistema SHALL rejeitar só essa linha, com o motivo do erro, e continuar com as seguintes, sem desfazer as já gravadas.
3. **IMPORT-29** WHEN a importação termina THEN o sistema SHALL responder com HTTP 200 e informar o total de linhas lidas, quantas foram gravadas de fato, quantas foram ignoradas por já existirem e quantas foram rejeitadas.
4. **IMPORT-30** WHEN a importação termina com linhas rejeitadas THEN o sistema SHALL listar cada uma com o motivo e com o número dela no arquivo: na planilha, contando o cabeçalho como linha 1; no OFX, a posição da transação.
5. **IMPORT-31** WHEN todas as linhas do arquivo já existiam THEN o sistema SHALL responder com HTTP 200 e zero linhas gravadas, e não com erro.
6. **IMPORT-32** WHEN o arquivo tem linhas totalmente vazias THEN o sistema SHALL pulá-las sem contá-las como lidas nem como rejeitadas.
7. **IMPORT-33** WHEN a interface recebe o resultado da importação THEN o sistema SHALL mostrar os quatro totais e a lista das linhas rejeitadas com o motivo de cada uma.

**Independent Test**: uma planilha com 10 linhas de dados, em que as linhas 3 e 6 têm data inválida e a linha 9 tem uma descrição de 300 caracteres (contando o cabeçalho como linha 1), grava 7 linhas e responde 200 com os totais 10, 7, 0 e 3. A lista traz as linhas 3 e 6 com "Data inválida" e a linha 9 com "Texto longo demais: descrição", e as 7 linhas continuam gravadas.

---

### P1: Linhas já importadas ⭐ MVP

**User Story**: Como usuário, quero reimportar um extrato que cresceu sem duplicar o que já entrou.

**Why P1**: hoje duas compras iguais no mesmo dia viram uma só, e reimportar um OFX depois de editar uma descrição duplica o lançamento (FIN-21).

**Acceptance Criteria**:
1. **IMPORT-34** WHEN uma transação de OFX tem identificador (`FITID`) THEN o sistema SHALL ignorá-la se a mesma conta já tiver uma transação importada com esse identificador.
2. **IMPORT-35** WHEN uma transação de OFX não tem identificador, ou é comparada com transações importadas antes de o identificador passar a ser guardado, THEN o sistema SHALL considerá-la repetida se a conta já tiver uma transação com a mesma data, o mesmo valor, o mesmo tipo e a mesma descrição.
3. **IMPORT-36** WHEN uma linha de receita ou despesa vem de planilha THEN o sistema SHALL considerá-la repetida se a conta já tiver uma transação com a mesma data, o mesmo valor, o mesmo tipo e a mesma descrição.
4. **IMPORT-37** WHEN uma linha de transferência vem de planilha THEN o sistema SHALL considerá-la repetida se já existir uma transferência com a mesma origem, o mesmo destino, a mesma data e o mesmo valor.
5. **IMPORT-38** WHEN o arquivo tem N linhas iguais entre si e a conta já tem M transações iguais a elas THEN o sistema SHALL gravar N − M dessas linhas, ou nenhuma quando M for maior ou igual a N, e contar as demais como ignoradas.
6. **IMPORT-39** WHEN duas importações do mesmo arquivo rodam ao mesmo tempo THEN o sistema SHALL gravar cada linha uma única vez.

**Independent Test**: importar um extrato de janeiro a março e depois o de janeiro a abril grava só as linhas de abril; um arquivo com duas compras iguais de R$ 5,00 no mesmo dia grava as duas, e reimportá-lo não grava nenhuma.

---

### P2: Tempo de processamento

**User Story**: Como usuário, quero que a importação termine rápido e que ela não deixe o app lento para os outros.

**Why P2**: hoje tudo roda dentro da requisição, num único worker, e um arquivo grande pode passar do timeout (OPS-03).

**Acceptance Criteria**:
1. **IMPORT-40** WHEN um arquivo dentro dos limites de IMPORT-04 e IMPORT-05 é enviado THEN o sistema SHALL concluir a importação e responder em até 30 segundos.
2. **IMPORT-41** WHILE uma importação estiver em processamento, o sistema SHALL continuar atendendo as requisições dos demais usuários.

**Independent Test**: importar um CSV de 10.000 linhas termina em até 30 segundos e, durante a importação, outra sessão consegue abrir o dashboard.

---

### P2: Correções de categoria

**User Story**: Como usuário, quero que a categoria que eu escolho para uma descrição volte sugerida nas próximas importações, para não classificar os mesmos gastos todo mês.

**Why P2**: a importação funciona sem isso, mas hoje cada extrato traz de novo as mesmas descrições sem categoria, e essas escolhas são o dado de que um classificador futuro precisa (PROP-04).

**Acceptance Criteria**:
1. **IMPORT-42** WHEN o usuário define ou troca a categoria de uma transação importada THEN o sistema SHALL registrar a correção com a descrição, a conta, a categoria de antes, a de depois e a data.
2. **IMPORT-43** WHEN uma linha importada sem categoria tem uma descrição que já recebeu correção do mesmo usuário, comparada sem diferença de maiúsculas, acentos, espaços extras e dígitos, THEN o sistema SHALL sugerir a categoria da correção mais recente para essa descrição.
3. **IMPORT-44** WHEN o sistema sugere uma categoria THEN o sistema SHALL gravar a linha com ela e marcá-la como sugerida.
4. **IMPORT-45** WHEN a importação termina THEN a interface SHALL mostrar quantas linhas receberam categoria sugerida, com um atalho para a lista de transações filtrada por elas.
5. **IMPORT-46** WHEN a interface mostra uma transação com categoria sugerida THEN a interface SHALL indicar que a categoria veio do histórico do usuário.
6. **IMPORT-47** IF a categoria da correção mais recente tiver sido excluída THEN o sistema SHALL deixar a linha sem sugestão.
7. **IMPORT-48** WHEN a conta do usuário é apagada definitivamente THEN o sistema SHALL apagar as correções dele junto com os demais dados (AD-018).
8. **IMPORT-49** WHILE o usuário não tiver dado o consentimento de LGPD-33, o sistema SHALL usar as correções dele só nas sugestões dele mesmo.

**Independent Test**: depois de trocar para Transporte a categoria de uma transação importada "UBER *TRIP 1234", a próxima importação traz "UBER *TRIP 5678" já em Transporte, marcada como sugerida, e o resultado diz "1 linha com categoria sugerida"; uma linha da planilha que já vem com categoria mantém a do arquivo.

---

## Edge Cases

- Extrato que cresceu (janeiro a março e depois janeiro a abril): só as linhas de abril entram (IMPORT-34 a IMPORT-38).
- Duas compras iguais no mesmo dia, no mesmo arquivo: as duas entram (IMPORT-38).
- "Crédito" e "CREDITO" na coluna de tipo: as duas viram receita (IMPORT-16).
- "1.500" numa célula de texto e 1500 numa célula numérica: as duas são R$ 1.500,00 (IMPORT-10, IMPORT-11).
- "29/02/2025": data inválida, linha rejeitada (IMPORT-15).
- Valor "0,00": linha rejeitada (IMPORT-12).
- Arquivo só com o cabeçalho: responde 200 com zero linhas (IMPORT-29).
- A etapa de mapeamento de contas, que lê o arquivo antes da importação, aplica os mesmos formatos e limites (IMPORT-02, IMPORT-04 a IMPORT-06).
- OFX importado antes desta mudança e reimportado depois: as transações antigas são reconhecidas pela data, valor, tipo e descrição (IMPORT-35).
- Linha de uma conta excluída depois do mapeamento: rejeitada (IMPORT-21).
- Descrição corrigida para duas categorias diferentes em momentos diferentes: vale a correção mais recente (IMPORT-43).
- Transação com categoria sugerida que o usuário troca: a troca vira uma correção nova (IMPORT-42).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | IMPORT-02 a IMPORT-07, IMPORT-12, IMPORT-15, IMPORT-17, IMPORT-21, IMPORT-22, IMPORT-24, IMPORT-26 |
| Falha e falha parcial | IMPORT-27, IMPORT-28 |
| Idempotência, repetição e duplicidade | IMPORT-34 a IMPORT-39 |
| Autorização e rate limiting | IMPORT-43 e IMPORT-49 (as correções servem só ao próprio usuário); a posse dos dados fica na feature `isolamento-entre-usuarios` (SEG-01), e o rate limiting (SEG-02), na feature `autenticacao` |
| Concorrência e ordem | IMPORT-39, IMPORT-41 |
| Ciclo de vida dos dados | IMPORT-23, IMPORT-35, IMPORT-47, IMPORT-48 |
| Observabilidade | IMPORT-29, IMPORT-30 |
| Falha de dependência externa | N/A because a importação lê um arquivo enviado pelo usuário e não chama serviço externo |
| Integridade das transições de estado | IMPORT-20 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| IMPORT-01 | P1: Arquivos aceitos e limites | T2 | Implemented |
| IMPORT-02 | P1: Arquivos aceitos e limites | T2 | Implemented |
| IMPORT-03 | P1: Arquivos aceitos e limites | T12 | Implemented |
| IMPORT-04 | P1: Arquivos aceitos e limites | T2 | Implemented |
| IMPORT-05 | P1: Arquivos aceitos e limites | T2 | Implemented |
| IMPORT-06 | P1: Arquivos aceitos e limites | T2 | Implemented |
| IMPORT-07 | P1: Arquivos aceitos e limites | T2 | Implemented |
| IMPORT-08 | P1: Arquivos aceitos e limites | T2 | Implemented |
| IMPORT-09 | P1: Valores e datas no formato brasileiro | T1 | Implemented |
| IMPORT-10 | P1: Valores e datas no formato brasileiro | T1 | Implemented |
| IMPORT-11 | P1: Valores e datas no formato brasileiro | T2 | Implemented |
| IMPORT-12 | P1: Valores e datas no formato brasileiro | T1 | Implemented |
| IMPORT-13 | P1: Valores e datas no formato brasileiro | T1 | Implemented |
| IMPORT-14 | P1: Valores e datas no formato brasileiro | T2 | Implemented |
| IMPORT-15 | P1: Valores e datas no formato brasileiro | T1 | Implemented |
| IMPORT-16 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-17 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-18 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-19 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-20 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-21 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-22 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-23 | P1: Tipo, status e conta de cada linha | T7 | Implemented |
| IMPORT-24 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-25 | P1: Tipo, status e conta de cada linha | T7 | Implemented |
| IMPORT-26 | P1: Tipo, status e conta de cada linha | T3 | Implemented |
| IMPORT-27 | P1: Resultado da importação | T7 | Implemented |
| IMPORT-28 | P1: Resultado da importação | T7 | Implemented |
| IMPORT-29 | P1: Resultado da importação | T7 | Implemented |
| IMPORT-30 | P1: Resultado da importação | T7 | Implemented |
| IMPORT-31 | P1: Resultado da importação | T7 | Implemented |
| IMPORT-32 | P1: Resultado da importação | T2 | Implemented |
| IMPORT-33 | P1: Resultado da importação | T12 | Implemented |
| IMPORT-34 | P1: Linhas já importadas | T4, T5 | Implemented |
| IMPORT-35 | P1: Linhas já importadas | T5 | Implemented |
| IMPORT-36 | P1: Linhas já importadas | T5 | Implemented |
| IMPORT-37 | P1: Linhas já importadas | T5 | Implemented |
| IMPORT-38 | P1: Linhas já importadas | T5 | Implemented |
| IMPORT-39 | P1: Linhas já importadas | T8 | Implemented |
| IMPORT-40 | P2: Tempo de processamento | T6, T9 | Implemented |
| IMPORT-41 | P2: Tempo de processamento | T9 | Implemented |
| IMPORT-42 | P2: Correções de categoria | T4, T10 | Implemented |
| IMPORT-43 | P2: Correções de categoria | T11 | Implemented |
| IMPORT-44 | P2: Correções de categoria | T11 | Implemented |
| IMPORT-45 | P2: Correções de categoria | T10, T12, T13 | Implemented |
| IMPORT-46 | P2: Correções de categoria | T10, T13 | Implemented |
| IMPORT-47 | P2: Correções de categoria | T11 | Implemented |
| IMPORT-48 | P2: Correções de categoria | T4, T10 | Implemented |
| IMPORT-49 | P2: Correções de categoria | T10, T11 | Implemented |

**Coverage:** 49 total, 49 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Um arquivo de teste com todos os formatos de valor e de data desta spec grava cada linha com o valor, a data e o tipo esperados.
- [ ] Importar o mesmo extrato duas vezes grava cada lançamento uma única vez.
- [ ] Um arquivo de 10.000 linhas é importado em até 30 segundos sem atrasar as requisições de outros usuários.
- [ ] Depois de corrigir uma vez a categoria de uma descrição, as próximas importações trazem essa descrição já na categoria escolhida, marcada como sugerida.
