# Importação completa Specification

## Problem Statement

O importador de planilha só lê a primeira aba de um XLSX e aceita um tipo por envio: ou receitas e despesas, ou transferências (`data_exchange/importacao/leitura.py:163-178`). O usuário digita o nome de cada coluna à mão, e uma conta que ainda não existe no app rejeita a linha (IMPORT-21). O rodapé "Total (...)" das exportações vira "Data inválida".

O caso real é a exportação do Mobills, que tem quatro abas:

| Aba | Conteúdo |
| --- | -------- |
| "Receitas e Despesas" | 57 linhas em 11 contas |
| "Despesas" | Repete linhas da primeira |
| "Receitas" | Repete linhas da primeira |
| "Transferências" | As transferências |

Toda aba termina numa linha "Total (...)", e a situação vem como "Paga". Hoje esse arquivo exige várias importações, contas criadas antes à mão e rejeições sem sentido.

Origem: plano de importação completa preparado em 2026-10-10, com as decisões do usuário.

## Goals

- [ ] O usuário solta o arquivo do Mobills, digita os saldos atuais das contas e importa tudo de uma vez, sem mapear colunas nem criar contas antes.
- [ ] Nenhuma linha "Total (...)" e nenhuma aba repetida viram rejeição ou lançamento em dobro.
- [ ] Cada conta criada pela importação termina com o saldo atual informado pelo usuário.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Importar compras no cartão de crédito e faturas | Continua fora, como na spec `importacao` |
| Mudanças no fluxo de OFX | O OFX tem uma conta por arquivo e segue a spec `importacao` |
| Modelos reconhecidos de outros apps além do Mobills | Os demais arquivos usam a detecção genérica por sinônimos |
| Guardar a análise no servidor entre as chamadas | O fluxo é sem estado: o arquivo vai junto na análise e na importação |
| Desfazer uma importação | Não foi pedido; os repetidos já protegem a reimportação |
| Sentido dos prefixos "XMeta - " e "XC - " dos nomes de conta | Decisão do usuário: não significam nada |
| Planilhas com mais de uma linha de cabeçalho ou com cabeçalho fora da primeira linha | A primeira linha de cada aba é o cabeçalho, como hoje |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Saldo das contas criadas | O usuário informa o saldo atual; o saldo inicial gravado é o saldo atual menos o efeito das transações efetivadas importadas na conta | Decisão do usuário: o saldo bate com o banco | sim |
| Prefixos "XMeta - " e "XC - " | O nome fica como está no arquivo, editável; o tipo é sugerido só por palavras óbvias do nome | Decisão do usuário | sim |
| Origem do arquivo | Modelo Mobills reconhecido automaticamente; detecção genérica por sinônimos para os demais | Decisão do usuário | sim |
| Revisão antes de gravar | Resumo, contas e linhas, com a tabela de linhas paginada, filtro de rejeitadas, edição e exclusão | Decisão do usuário | sim |
| Fluxo | Sem estado: a análise e a importação recebem o arquivo e o plano; a análise nunca grava nada | Evita guardar arquivos no servidor e mantém a importação reproduzível a partir do plano | sim |
| Fluxo antigo | `/import/spreadsheet/`, `/import/preflight/` e `/import/ofx/` continuam funcionando enquanto a tela nova não substituir a antiga | A troca da tela vem por último | sim |
| Cabeçalho | A primeira linha não vazia de cada aba | É o formato das exportações conhecidas e da spec `importacao` | sim |
| Linha de resumo | Linha cuja primeira célula começa com "Total" e cujas colunas de descrição e de conta estão vazias | É o rodapé das exportações do Mobills, sem risco de pular um lançamento chamado "Total" | sim |
| Aba contida em outra | Aba de receitas e despesas cujas linhas (data, valor, conta e descrição, contando repetições) estão todas dentro de outra aba usada é ignorada com o motivo "Contida na aba <nome>" | Evita lançar em dobro as abas "Despesas" e "Receitas" do Mobills e de arquivos parecidos | sim |
| Situação pendente | "não paga", "a pagar", "a receber", "agendada", "pendente" e "pending" viram pendente; qualquer outro valor ou vazio vira efetivada | Amplia IMPORT-20 com os textos do Mobills e de outros apps | sim |
| Tipo sugerido das contas novas | Carteira → WALLET; poupança ou reserva → SAVINGS; investimento ou CDB → INVESTMENT; cofrinho → PIGGY_BANK; os demais → CHECKING | Palavras óbvias do nome, sem interpretar prefixos | sim |
| Correspondência de conta | Nome normalizado igual ao de uma conta ativa do usuário, como em `Interpretador.conta` | Mesma regra da importação atual | sim |
| Saldo atual informado | Qualquer valor em reais com até duas casas, inclusive zero e negativo | Uma conta corrente pode estar no negativo | sim |
| Chave das linhas no plano | `"<aba>:<número da linha>"`, com o número contado como em IMPORT-30 | A interface e o backend apontam para a mesma linha sem guardar estado | sim |
| Correção de linha | Substitui os campos informados e passa pelas mesmas validações; uma correção inválida volta como rejeição da linha | A correção não abre um caminho sem validação | sim |
| Chave de linha que não existe no arquivo | Recusa com HTTP 400 e a mensagem "Linha inexistente no arquivo: <chave>." | Evita gravar com um plano montado para outro arquivo | sim |
| Limite de contas do plano | As contas a criar contam no `limite_contas`; passando do limite, nada é gravado | Mesma regra da criação de conta pela tela (AD-044) | sim |
| Trava do recurso | As rotas novas seguem a trava `importacao_planilha`; a trava de tags vale também para as tags do plano | Mesmas travas da importação atual | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Leitura e detecção ⭐ MVP

**User Story**: Como usuário, quero soltar o arquivo e ver as abas, as colunas e as contas já reconhecidas, para não mapear nada à mão.

**Why P1**: é o que tira do usuário o mapeamento digitado e a necessidade de várias importações.

**Acceptance Criteria**:
1. **IMPCOMP-01** WHEN o usuário envia um XLSX para análise THEN o sistema SHALL ler todas as abas do arquivo, cada uma com o nome, o cabeçalho e as linhas.
2. **IMPCOMP-02** WHEN o usuário envia um CSV para análise THEN o sistema SHALL tratá-lo como uma aba única com o nome do arquivo.
3. **IMPCOMP-03** IF a soma das linhas de dados de todas as abas passar de 10.000 THEN o sistema SHALL recusar o arquivo com HTTP 400 e a mensagem "O arquivo passa do limite de 10.000 linhas.", sem gravar nada.
4. **IMPCOMP-04** WHEN o sistema analisa uma aba THEN o sistema SHALL ligar cada cabeçalho a um campo pelos sinônimos, comparados sem diferença de maiúsculas, acentos e espaços extras: data (data, date, dt, data da transação), descrição (descrição, histórico, memo, título, lançamento), valor (valor, quantia, amount), conta (conta, banco, carteira), conta de origem (conta origem, origem, de), conta de destino (conta destino, destino, para), tipo, situação (situação, status), categoria, subcategoria, tags (tags, etiquetas), entrada (entrada, crédito) e saída (saída, débito).
5. **IMPCOMP-05** WHEN uma aba tem colunas de origem e de destino THEN o sistema SHALL dar a ela o papel de transferências.
6. **IMPCOMP-06** WHEN uma aba sem colunas de origem e de destino tem colunas de data e de valor, ou de data, entrada e saída, THEN o sistema SHALL dar a ela o papel de receitas e despesas.
7. **IMPCOMP-07** WHEN uma aba não tem as colunas de IMPCOMP-05 nem as de IMPCOMP-06 THEN o sistema SHALL dar a ela o papel de ignorada, com o motivo "Colunas não reconhecidas".
8. **IMPCOMP-08** WHEN as abas e os cabeçalhos são os da exportação do Mobills THEN o sistema SHALL reconhecer o modelo Mobills, dar o papel de receitas e despesas à aba "Receitas e Despesas" e o de transferências à aba "Transferências", e ignorar as abas "Despesas" e "Receitas".
9. **IMPCOMP-09** WHEN todas as linhas de uma aba de receitas e despesas, comparadas por data, valor, conta e descrição e contando as repetições, estão dentro de outra aba usada THEN o sistema SHALL ignorá-la com o motivo "Contida na aba <nome>".
10. **IMPCOMP-10** WHEN o sistema analisa as contas THEN o sistema SHALL listar cada nome de conta das abas usadas uma vez, com a quantidade de linhas, a soma dos valores e a primeira e a última data.
11. **IMPCOMP-11** WHEN o nome de conta do arquivo, sem diferença de maiúsculas, acentos e espaços extras, é igual ao de uma conta ativa do usuário THEN o sistema SHALL sugerir vincular a essa conta.
12. **IMPCOMP-12** WHEN o nome de conta do arquivo não corresponde a uma conta ativa do usuário THEN o sistema SHALL sugerir criar a conta, com o nome do arquivo e o tipo WALLET quando o nome tem "carteira", SAVINGS quando tem "poupança" ou "reserva", INVESTMENT quando tem "investimento" ou "CDB", PIGGY_BANK quando tem "cofrinho" e CHECKING nos demais casos.
13. **IMPCOMP-13** WHEN a análise termina THEN o sistema SHALL devolver o plano detectado, com o modelo, as abas, os papéis, as colunas e as contas, e as linhas interpretadas, sem gravar nada.
14. **IMPCOMP-14** WHEN a análise recebe um plano editado THEN o sistema SHALL usar as abas, os papéis, as colunas e as contas do plano no lugar dos detectados.

**Independent Test**: analisar o arquivo do Mobills reconhece o modelo, dá os papéis às abas "Receitas e Despesas" e "Transferências", ignora "Despesas" e "Receitas", lista as 11 contas com o tipo sugerido e não grava nenhuma transação nem conta.

---

### P1: Interpretação das linhas ⭐ MVP

**User Story**: Como usuário, quero que as linhas de rodapé, as situações e os formatos de outros apps sejam entendidos, para não receber rejeições sem sentido.

**Why P1**: o rodapé "Total" e a situação "Paga" aparecem em todo arquivo do Mobills.

**Acceptance Criteria**:
1. **IMPCOMP-15** WHEN a primeira célula de uma linha começa com "Total" e as colunas de descrição e de conta estão vazias THEN o sistema SHALL pular a linha como resumo, sem contá-la como lida nem como rejeitada.
2. **IMPCOMP-16** WHEN a coluna de situação diz "não paga", "a pagar", "a receber", "agendada", "pendente" ou "pending", sem diferença de maiúsculas e acentos, THEN o sistema SHALL importar a transação como pendente.
3. **IMPCOMP-17** WHEN a coluna de situação tem qualquer outro valor ou está vazia THEN o sistema SHALL importar a transação como efetivada.
4. **IMPCOMP-18** WHEN a aba tem colunas separadas de entrada e de saída THEN o sistema SHALL importar como receita a linha com a entrada preenchida e como despesa a linha com a saída preenchida.
5. **IMPCOMP-19** IF uma linha tiver entrada e saída preenchidas, ou nenhuma das duas, THEN o sistema SHALL rejeitá-la com o motivo "Valor inválido".
6. **IMPCOMP-20** WHEN uma linha de uma aba de receitas e despesas tem o tipo "transferência" e a aba tem a coluna de destino mapeada THEN o sistema SHALL importá-la como transferência da conta da linha para a conta de destino.
7. **IMPCOMP-21** WHEN uma linha é rejeitada THEN o sistema SHALL informar a aba, o número da linha e o motivo.
8. **IMPCOMP-22** IF a coluna de descrição mapeada numa aba de transferências não existir no cabeçalho THEN o sistema SHALL recusar a análise e a importação com HTTP 400 e a mensagem de IMPORT-06 com a coluna que falta.

**Independent Test**: o arquivo do Mobills não tem nenhuma rejeição por "Total" nem por situação; uma aba com colunas Entrada e Saída importa uma receita e uma despesa; uma linha com tipo "Transferência" e conta de destino vira transferência.

---

### P1: Contas e saldo ⭐ MVP

**User Story**: Como usuário, quero criar na própria importação as contas que ainda não existem, informando o saldo atual delas, para que o app fique igual ao banco.

**Why P1**: o arquivo do Mobills tem 11 contas, e criar cada uma antes, à mão, é o que mais trava a importação hoje.

**Acceptance Criteria**:
1. **IMPCOMP-23** WHEN o plano marca uma conta do arquivo para vincular THEN o sistema SHALL gravar as linhas dessa conta na conta escolhida.
2. **IMPCOMP-24** IF a conta escolhida para vincular for de outro usuário, não existir ou estiver excluída THEN o sistema SHALL recusar a importação com HTTP 400, com o erro na conta do plano e a mesma mensagem de um ID inexistente (AD-010), sem gravar nada.
3. **IMPCOMP-25** WHEN o plano marca uma conta do arquivo para criar THEN o sistema SHALL criar a conta com o nome, o tipo, a instituição e a cor do plano.
4. **IMPCOMP-26** WHEN a importação termina THEN o sistema SHALL deixar cada conta criada com o saldo igual ao saldo atual informado no plano.
5. **IMPCOMP-27** IF as contas a criar fizerem o usuário passar do limite `limite_contas` do plano dele THEN o sistema SHALL recusar a importação com HTTP 403 `plan_limit_reached`, sem gravar nenhuma conta nem transação.
6. **IMPCOMP-28** IF uma conta a criar tiver o nome vazio, um tipo fora dos tipos de conta do app ou um saldo atual que não seja um valor em reais com até duas casas THEN o sistema SHALL recusar a importação com HTTP 400 e o erro no campo dessa conta do plano, sem gravar nada.
7. **IMPCOMP-29** IF a importação falhar depois de criar as contas THEN o sistema SHALL desfazer a criação das contas, sem nenhuma conta nem transação gravada.
8. **IMPCOMP-30** WHEN a importação termina THEN o sistema SHALL informar as contas criadas, com o id e o nome.

**Independent Test**: importar o arquivo do Mobills com as 11 contas marcadas para criar e um saldo atual para cada uma cria as 11 contas, e o saldo de cada uma é o informado; com o limite de contas em 5, nada é gravado e a resposta é 403.

---

### P1: Revisão e correção das linhas ⭐ MVP

**User Story**: Como usuário, quero revisar as linhas antes de gravar, corrigir as rejeitadas e excluir as que não quero, numa tela só.

**Why P1**: sem a revisão, o usuário só descobre o erro depois de gravar.

**Acceptance Criteria**:
1. **IMPCOMP-31** WHEN a análise devolve as linhas THEN o sistema SHALL marcar cada uma como válida, rejeitada com o motivo ou repetida, pelas regras de repetidos da spec `importacao`, com a chave `"<aba>:<número>"`.
2. **IMPCOMP-32** WHEN o plano corrige campos de uma linha THEN o sistema SHALL interpretar a linha com os campos corrigidos, pelas mesmas validações das demais.
3. **IMPCOMP-33** IF a correção de uma linha for inválida THEN o sistema SHALL devolver a linha como rejeitada, com o motivo da validação.
4. **IMPCOMP-34** WHEN o plano exclui uma linha THEN o sistema SHALL deixar de gravá-la e contá-la como excluída.
5. **IMPCOMP-35** IF o plano tiver uma chave de linha que não existe no arquivo THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Linha inexistente no arquivo: <chave>."
6. **IMPCOMP-36** IF o plano não for um JSON válido ou não seguir o formato esperado THEN o sistema SHALL recusar com HTTP 400 e o erro no campo do plano.
7. **IMPCOMP-37** WHEN a interface mostra a revisão THEN a interface SHALL mostrar o resumo com as linhas válidas, rejeitadas, repetidas e excluídas, as contas novas e os totais de receitas, despesas e transferências.
8. **IMPCOMP-38** WHEN a interface mostra as abas THEN a interface SHALL mostrar, para cada aba, o papel e as colunas já preenchidos, com os cabeçalhos reais como opções, o selo "Modelo Mobills reconhecido" quando houver e o motivo das abas ignoradas.
9. **IMPCOMP-39** WHEN a interface mostra as contas THEN a interface SHALL permitir, para cada conta do arquivo, vincular a uma conta ativa ou criar, editando o nome, o tipo, a instituição e o saldo atual.
10. **IMPCOMP-40** WHILE as contas a criar estiverem no limite `limite_contas` do plano do usuário, a interface SHALL impedir marcar mais contas para criar e mostrar o aviso do limite.
11. **IMPCOMP-41** WHEN a interface mostra as linhas THEN a interface SHALL mostrar a tabela paginada com a aba, o número, a data, a descrição, a conta, o tipo, a categoria, o valor e a situação, com os filtros Todas, Rejeitadas, Repetidas e Excluídas e a busca.
12. **IMPCOMP-42** WHEN o usuário corrige um campo de uma linha ou a exclui ou restaura THEN a interface SHALL mandar a correção no plano e mostrar a linha reanalisada.
13. **IMPCOMP-43** WHEN o usuário escolhe o arquivo THEN a interface SHALL pedir a análise na hora, sem um botão de avançar.
14. **IMPCOMP-44** WHEN o usuário muda o papel ou as colunas de uma aba, ou a ação de uma conta, THEN a interface SHALL pedir uma nova análise com o plano editado.

**Independent Test**: uma linha com data inválida aparece como rejeitada no filtro Rejeitadas; corrigir a data a torna válida; excluir uma linha válida a tira da gravação e a conta como excluída.

---

### P1: Importação e resultado ⭐ MVP

**User Story**: Como usuário, quero confirmar a revisão e ver o que foi gravado, por aba.

**Why P1**: fecha o fluxo e mostra que nada foi perdido nem gravado em dobro.

**Acceptance Criteria**:
1. **IMPCOMP-45** WHEN o usuário confirma a importação THEN o sistema SHALL criar as contas novas, gravar as receitas, as despesas e as transferências de todas as abas usadas e ajustar o saldo das contas criadas, numa única requisição.
2. **IMPCOMP-46** WHEN um envio mistura receitas, despesas e transferências THEN o sistema SHALL aplicar a regra de repetidos de IMPORT-36 às receitas e despesas e a de IMPORT-37 às transferências.
3. **IMPCOMP-47** WHEN a importação termina THEN o sistema SHALL responder com os totais de IMPORT-29, as contas criadas, os totais por aba (gravadas, ignoradas e rejeitadas) e a quantidade de linhas de resumo puladas.
4. **IMPCOMP-48** WHEN o mesmo arquivo é importado de novo com o mesmo plano, com as contas agora vinculadas THEN o sistema SHALL gravar zero linhas e contar todas como ignoradas.
5. **IMPCOMP-49** WHEN a interface mostra o resultado THEN a interface SHALL mostrar os quatro totais, as contas criadas, os totais por aba e as linhas rejeitadas com a aba, o número e o motivo.
6. **IMPCOMP-50** WHERE o recurso `importacao_planilha` estiver travado no plano do usuário, o sistema SHALL recusar a análise e a importação com HTTP 403 `plan_locked`.
7. **IMPCOMP-51** WHERE o recurso `tags` estiver travado no plano do usuário, o sistema SHALL importar as linhas sem as tags, também quando elas vierem de uma correção do plano.
8. **IMPCOMP-52** WHEN o sistema registra um log da análise ou da importação THEN o sistema SHALL omitir nomes de contas, descrições e valores (AD-019).

**Independent Test**: importar o arquivo do Mobills grava 57 receitas e despesas e 9 transferências, cria as contas e responde com os totais por aba; importar de novo grava zero e ignora tudo.

---

## Edge Cases

- Aba vazia, só com o cabeçalho: fica ignorada com o motivo "Colunas não reconhecidas" ou sem linhas, sem erro (IMPCOMP-07).
- Duas abas iguais: a segunda fica contida na primeira e é ignorada (IMPCOMP-09).
- Lançamento chamado "Total" com conta e descrição preenchidas: é importado normalmente (IMPCOMP-15).
- Transferência entre uma conta criada e uma vinculada: entra no saldo das duas, e a conta criada termina com o saldo atual informado (IMPCOMP-26).
- Conta criada só com transações pendentes: o saldo inicial é o saldo atual, porque pendentes não mexem no saldo (IMPCOMP-26).
- Conta do arquivo que corresponde a uma conta excluída: a sugestão é criar (IMPCOMP-12).
- Dois nomes no arquivo vinculados à mesma conta existente: as linhas dos dois vão para ela (IMPCOMP-23).
- Linha excluída no plano que depois é restaurada: volta a ser interpretada (IMPCOMP-42).
- Arquivo com uma aba só: segue o mesmo fluxo, com uma linha na tabela de abas (IMPCOMP-01).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | IMPCOMP-03, IMPCOMP-22, IMPCOMP-24, IMPCOMP-27, IMPCOMP-28, IMPCOMP-35, IMPCOMP-36 |
| Falha e falha parcial | IMPCOMP-29; as linhas inválidas seguem IMPORT-27 e IMPORT-28 |
| Idempotência, repetição e duplicidade | IMPCOMP-09, IMPCOMP-46, IMPCOMP-48 |
| Autorização e rate limiting | IMPCOMP-24, IMPCOMP-27, IMPCOMP-50, IMPCOMP-51 |
| Concorrência e ordem | IMPORT-39 vale para a importação nova; a análise não grava nada |
| Ciclo de vida dos dados | As contas criadas seguem as regras de conta; nada da análise é guardado (fluxo sem estado) |
| Observabilidade | IMPCOMP-52 |
| Falha de dependência externa | N/A because a importação não chama serviços externos |
| Integridade das transições de estado | IMPCOMP-29 (contas e transações gravadas juntas ou nada) |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| IMPCOMP-01 | P1: Leitura e detecção | T1 | Implemented |
| IMPCOMP-02 | P1: Leitura e detecção | T1 | Implemented |
| IMPCOMP-03 | P1: Leitura e detecção | T1 | Implemented |
| IMPCOMP-04 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-05 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-06 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-07 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-08 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-09 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-10 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-11 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-12 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-13 | P1: Leitura e detecção | T6, T7 | Implemented |
| IMPCOMP-14 | P1: Leitura e detecção | T2 | Implemented |
| IMPCOMP-15 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-16 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-17 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-18 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-19 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-20 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-21 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-22 | P1: Interpretação das linhas | T3 | Implemented |
| IMPCOMP-23 | P1: Contas e saldo | T6 | Implemented |
| IMPCOMP-24 | P1: Contas e saldo | T6 | Implemented |
| IMPCOMP-25 | P1: Contas e saldo | T5 | Implemented |
| IMPCOMP-26 | P1: Contas e saldo | T5 | Implemented |
| IMPCOMP-27 | P1: Contas e saldo | T5 | Implemented |
| IMPCOMP-28 | P1: Contas e saldo | T6 | Implemented |
| IMPCOMP-29 | P1: Contas e saldo | T5 | Implemented |
| IMPCOMP-30 | P1: Contas e saldo | T6 | Implemented |
| IMPCOMP-31 | P1: Revisão e correção das linhas | T4 | Implemented |
| IMPCOMP-32 | P1: Revisão e correção das linhas | T3 | Implemented |
| IMPCOMP-33 | P1: Revisão e correção das linhas | T3 | Implemented |
| IMPCOMP-34 | P1: Revisão e correção das linhas | T3 | Implemented |
| IMPCOMP-35 | P1: Revisão e correção das linhas | T6 | Implemented |
| IMPCOMP-36 | P1: Revisão e correção das linhas | T6 | Implemented |
| IMPCOMP-37 | P1: Revisão e correção das linhas | T8 | Pending |
| IMPCOMP-38 | P1: Revisão e correção das linhas | T9 | Pending |
| IMPCOMP-39 | P1: Revisão e correção das linhas | T10 | Pending |
| IMPCOMP-40 | P1: Revisão e correção das linhas | T10 | Pending |
| IMPCOMP-41 | P1: Revisão e correção das linhas | T11 | Pending |
| IMPCOMP-42 | P1: Revisão e correção das linhas | T11 | Pending |
| IMPCOMP-43 | P1: Revisão e correção das linhas | T8, T13 | Pending |
| IMPCOMP-44 | P1: Revisão e correção das linhas | T9, T10 | Pending |
| IMPCOMP-45 | P1: Importação e resultado | T6, T7 | Implemented |
| IMPCOMP-46 | P1: Importação e resultado | T4 | Implemented |
| IMPCOMP-47 | P1: Importação e resultado | T6 | Implemented |
| IMPCOMP-48 | P1: Importação e resultado | T6 | Implemented |
| IMPCOMP-49 | P1: Importação e resultado | T12 | Pending |
| IMPCOMP-50 | P1: Importação e resultado | T6, T13 | In Progress |
| IMPCOMP-51 | P1: Importação e resultado | T6 | Implemented |
| IMPCOMP-52 | P1: Importação e resultado | T6 | Implemented |

**Coverage:** 52 total, 52 mapped to tasks, 0 unmapped; 42 implemented, 1 in progress, 9 pending

---

## Success Criteria

- [ ] O arquivo do Mobills é importado em uma única passada: soltar o arquivo, digitar os saldos atuais e clicar em Importar.
- [ ] A importação do Mobills grava 57 receitas e despesas e 9 transferências, sem nenhuma rejeição por "Total".
- [ ] Cada conta criada termina com o saldo igual ao informado, e reimportar o arquivo não grava nada novo.
