# Importação completa Validation

**Verdict: PASS**
**Result**: PASS

Verificação leve feita por um verificador independente (autor ≠ verificador): conferência das 52 ACs contra a spec, uma conferência só de leitura com os arquivos reais do Mobills e um sensor de discriminação com 8 mutações de comportamento, todas mortas. As 52 ACs têm evidência em teste. Os gaps abaixo são de precisão da spec e de cobertura, nenhum quebra uma AC.

## Diff ranges

| Repo | Branch | Range | Commits |
| ---- | ------ | ----- | ------- |
| fluxar-backend | `feat/importacao-completa` | `development (03df663)..HEAD (9e25f74)` | 15 (`7ca2665` a `9e25f74`; código em `6840b4b`, `ee4366b`, `af79af2`, `56c6dc4`, `0b5692e`, `c637f3a`) |
| fluxar-frontend | `feat/importacao-completa` | `development (5dd6467)..HEAD (87a43cb)` | 7 (`1bac702`, `58fc3a3`, `afc0d59`, `fbc3e0d`, `9b580c6`, `520471e`, `87a43cb`) |

Baseline: no backend, `tests.importacao` mais `tests.permissoes.test_travas_de_recurso` com 180 testes OK (Postgres do `docker compose`, imagem temporária feita da imagem do projeto mais o `requirements.txt`, por falta do `cryptography`; apagada depois). O teste de desempenho de IMPORT-40 (`tests/importacao/test_desempenho.py:29`) passou sozinho em 26,7 s, dentro dos 30 s. No frontend, `tests/importacao` com 41 testes OK em 9 arquivos.

## Evidência por AC

Backend em `tests/importacao/` (salvo indicação); frontend em `tests/importacao/`.

### Leitura e detecção

| AC | Evidência |
| -- | --------- |
| IMPCOMP-01 | `test_abas.py:29` (quatro abas com nome, cabeçalho e linhas, na ordem), `:48` (cabeçalho na primeira linha não vazia, numeração da planilha) |
| IMPCOMP-02 | `test_abas.py:75` (CSV como aba única com o nome do arquivo), `:92` (Windows-1252 e vírgula) |
| IMPCOMP-03 | `test_abas.py:101` (duas abas de 6.000 linhas: 400 com a mensagem), `:110` (10.000 exatas passam). Ver gap 1 |
| IMPCOMP-04 | `test_deteccao.py:32`, `:39` (todos os sinônimos, sem maiúsculas, acentos e espaços extras), `:61` |
| IMPCOMP-05 | `test_deteccao.py:68` |
| IMPCOMP-06 | `test_deteccao.py:68` (data e valor; data, entrada e saída) |
| IMPCOMP-07 | `test_deteccao.py:68`, `:180` ("Colunas não reconhecidas") |
| IMPCOMP-08 | `test_deteccao.py:88` (modelo, papéis e colunas), `:113`, `:121` (não Mobills); `test_importacao_completa.py:80` |
| IMPCOMP-09 | `test_deteccao.py:144` ("Contida na aba Extrato", com rodapé e linha vazia), `:156` (duas abas iguais), `:167` (multiconjunto: uma linha que aparece duas vezes numa aba e uma vez na outra mantém a aba) |
| IMPCOMP-10 | `test_deteccao.py:196` (11 contas, quantidade, soma e período) |
| IMPCOMP-11 | `test_deteccao.py:221` ("nubank " vincula a "Nubank"; conta excluída sugere criar) |
| IMPCOMP-12 | `test_deteccao.py:244`, `:196` |
| IMPCOMP-13 | `test_deteccao.py:255`; `test_importacao_completa.py:80` (plano, linhas e resumo, sem conta nem transação nova) |
| IMPCOMP-14 | `test_deteccao.py:264` (papel, colunas e contas do plano), `:305` (aba inexistente: 400); `test_importacao_completa.py:156` |

### Interpretação das linhas

| AC | Evidência |
| -- | --------- |
| IMPCOMP-15 | `test_interpretacao_completa.py:50` (só o rodapé é pulado e contado; a linha com "Total" na primeira célula e descrição e conta preenchidas segue as regras comuns), `:78` (Mobills sem rejeição por "Total"); `test_abas.py:69`. Ver gap 6 |
| IMPCOMP-16 | `test_interpretacao_completa.py:104` (os seis textos, com maiúsculas, acentos e espaços variados) |
| IMPCOMP-17 | `test_interpretacao_completa.py:104` ("Paga", "Recebida", vazio, "pago"), `:78` |
| IMPCOMP-18 | `test_interpretacao_completa.py:122` |
| IMPCOMP-19 | `test_interpretacao_completa.py:134` |
| IMPCOMP-20 | `test_interpretacao_completa.py:148`, `:162` (sem destino mapeado: tipo desconhecido) |
| IMPCOMP-21 | `test_interpretacao_completa.py:173`; `test_importacao_completa.py:228` (`sheet` em `rejected_rows`), `:122` (aba, número e motivo na análise) |
| IMPCOMP-22 | `test_interpretacao_completa.py:254`, `:265` (preflight antigo); `test_importacao_completa.py:363` (rota nova, sem gravar) |

### Contas e saldo

| AC | Evidência |
| -- | --------- |
| IMPCOMP-23 | `test_importacao_completa.py:212` (dois nomes vinculados à mesma conta, saldo 915,50) |
| IMPCOMP-24 | `test_importacao_completa.py:301` (outro usuário, inexistente, excluída, `abc` e `null`: 400 `{"plano": {"contas": {"Nubank": {"id": ["Conta não encontrada."]}}}}`, sem gravar; também na análise) |
| IMPCOMP-25 | `test_contas_da_importacao.py:53`; `test_importacao_completa.py:166` |
| IMPCOMP-26 | `test_contas_da_importacao.py:73` (receita, despesa, pendente, transferência para uma vinculada e de uma vinculada: saldo 1.234,56, saldo inicial −1.225,04; conta só com pendentes: saldo inicial = saldo atual = −50,00; vinculadas só recebem o efeito das transferências), `:103`; `test_importacao_completa.py:166` (as 11 contas do Mobills, com 9 transferências entre contas criadas, terminam com o saldo informado). Ver gap 3 |
| IMPCOMP-27 | `test_contas_da_importacao.py:113` (3 contas com 2 vagas: 403 e nenhuma criada), `:126`, `:133` (`conferir_limite` sem `quantidade` igual ao de antes); `test_importacao_completa.py:256` (limite 5, 11 a criar: 403 `plan_limit_reached`, nada gravado) |
| IMPCOMP-28 | `test_importacao_completa.py:313` (nome vazio e com 101 caracteres, tipo `CREDIT_CARD`, saldo `abc` e `10.123`, campos ausentes: 400 no campo da conta, sem gravar) |
| IMPCOMP-29 | `test_contas_da_importacao.py:148`; `test_importacao_completa.py:245` (falha em `acertar_saldos`, depois das contas e das linhas: nenhuma conta nem transação) |
| IMPCOMP-30 | `test_importacao_completa.py:166` (`accounts_created` com id e nome) |

### Revisão e correção das linhas

| AC | Evidência |
| -- | --------- |
| IMPCOMP-31 | `test_importacao_completa.py:122` (VALIDA e REJEITADA com a chave `"<aba>:<número>"`), `:193` (tudo REPETIDA na reanálise); `test_repetidos_mistos.py:68`, `:81` |
| IMPCOMP-32 | `test_interpretacao_completa.py:202`, `:218`, `:233`; `test_importacao_completa.py:122` |
| IMPCOMP-33 | `test_interpretacao_completa.py:209` |
| IMPCOMP-34 | `test_interpretacao_completa.py:239`; `test_importacao_completa.py:122`, `:228` (fora da gravação, `excluded` 1) |
| IMPCOMP-35 | `test_importacao_completa.py:354` (análise e importação, sem gravar) |
| IMPCOMP-36 | `test_importacao_completa.py:334` (JSON malformado, papel fora da lista, campo desconhecido, tipos errados, lista no lugar do objeto) |
| IMPCOMP-37 | frontend `assistente-arquivo-e-resumo.test.tsx:61`; backend `test_importacao_completa.py:80` (o resumo) |
| IMPCOMP-38 | frontend `assistente-abas-e-colunas.test.tsx:61` (selects preenchidos, cabeçalhos reais como opções), `:79` (selo e motivo), `:88` |
| IMPCOMP-39 | frontend `assistente-contas.test.tsx:64`, `:78` (nome, tipo, instituição e saldo), `:104` (vincular a uma conta ativa) |
| IMPCOMP-40 | frontend `assistente-contas.test.tsx:119` (3 de 3: "Criar" desabilitado, clique sem efeito, aviso), `:133` (o uso soma as contas a criar). Ver gap 4 |
| IMPCOMP-41 | frontend `assistente-linhas.test.tsx:62` (colunas e filtro Rejeitadas com o motivo), `:149` (20 por página e busca) |
| IMPCOMP-42 | frontend `assistente-linhas.test.tsx:88`, `:112`, `:126` (excluir e restaurar); backend `test_importacao_completa.py:122` |
| IMPCOMP-43 | frontend `assistente-arquivo-e-resumo.test.tsx:44`, `assistente-pagina.test.tsx:41` |
| IMPCOMP-44 | frontend `assistente-abas-e-colunas.test.tsx:97` (papel), `:117` (colunas), `assistente-contas.test.tsx:78` e `:104` (ação da conta pede análise; nome, tipo e saldo não) |

### Importação e resultado

| AC | Evidência |
| -- | --------- |
| IMPCOMP-45 | `test_importacao_completa.py:166` (uma requisição: 11 contas, 57 receitas e despesas, 9 transferências, saldos acertados); frontend `assistente-resultado.test.tsx:92` |
| IMPCOMP-46 | `test_repetidos_mistos.py:47` (receita, despesa e transferência existentes ignoradas no mesmo envio), `:61` (envio misto novo grava 3, o segundo ignora 3) |
| IMPCOMP-47 | `test_importacao_completa.py:166` (totais, `by_sheet`, `summary_rows`, `excluded`, `accounts_created`), `:228` |
| IMPCOMP-48 | `test_importacao_completa.py:193` (0 gravadas, 66 ignoradas, nada novo no banco) |
| IMPCOMP-49 | frontend `assistente-resultado.test.tsx:92`, `:122` ("<aba>, linha <n>: <motivo>") |
| IMPCOMP-50 | `test_importacao_completa.py:270`; `tests/permissoes/test_travas_de_recurso.py:190` (as duas rotas no catálogo); frontend `tests/permissoes/travas-de-importacao.test.tsx:62` |
| IMPCOMP-51 | `test_importacao_completa.py:279` (coluna e correção de tags fora, nenhuma tag criada); `test_interpretacao_completa.py:244` |
| IMPCOMP-52 | `test_importacao_completa.py:378` (dois logs, sem nomes de conta, descrições, categorias, valores nem saldos) |

## Conferência com os arquivos reais

Só a análise (`completa.analisar`, a função da `ImportacaoAnaliseView`), no container `fluxar-backend-backend-1` (que monta este repositório na branch da feature), com um usuário descartável criado e desfeito numa transação revertida; nenhum usuário de verificação ficou no banco. O arquivo foi copiado para `/tmp/x.xlsx` e apagado depois de cada execução. Só contagens foram impressas.

**`RELATORIO_TRANSACOES_54a30d3f-...xlsx` (a exportação do Mobills da spec):**

| Item | Resultado |
| ---- | --------- |
| modelo | `MOBILLS` |
| "Receitas e Despesas" | `RECEITAS_DESPESAS`, sem motivo |
| "Despesas" | `IGNORAR`, "Contida na aba Receitas e Despesas" |
| "Receitas" | `IGNORAR`, "Contida na aba Receitas e Despesas" |
| "Transferências" | `TRANSFERENCIAS`, sem motivo |
| contas | 11: 10 criar, 1 vincular (a "Carteira" que o cadastro cria) |
| estados | 66 VALIDA (57 em "Receitas e Despesas", 9 em "Transferências"); 0 rejeitadas, 0 repetidas, 0 excluídas |
| resumo | 19 receitas, 38 despesas, 9 transferências, 10 contas novas |
| summary_rows | 1 |
| motivos de rejeição | nenhum |
| situação | as 57 linhas dizem "Paga" e viraram COMPLETED |

O `summary_rows` é 1, e não 2 como no arquivo de teste: a aba "Transferências" real não tem linha "Total"; só as três abas de receitas e despesas têm (ver gap 2).

Outros dois arquivos do mesmo dia: `1c7e3957-...` (Mobills, 4 abas: 3 despesas e 1 transferência válidas, 2 contas a criar, `summary_rows` 1, nenhuma rejeição; a aba "Receitas" sem linhas ficou ignorada pelo modelo) e `9d83b5e3-...` (uma aba "Transações", detecção genérica, sem coluna de situação: 1.662 linhas válidas, 288 receitas e 1.374 despesas, 15 contas, 14 a criar e 1 a vincular, nenhuma rejeição, `summary_rows` 0).

## Discrimination sensor

Backend: mutações aplicadas num worktree destacado (`../fluxar-backend-mut`, removido depois), com `tests.importacao` (8 módulos: abas, detecção, interpretação completa, repetidos, repetidos mistos, gravação, contas e rotas; 84 testes) rodado num container da imagem temporária, na rede `fluxar-backend_default`. Frontend: mutação no arquivo real, `vitest run` do arquivo de teste e `git checkout` em seguida.

| # | Repo | Mutação | Resultado | Testes que pegaram |
| - | ---- | ------- | --------- | ------------------ |
| B1 | backend | linha de resumo = qualquer linha com "Total" na primeira célula, sem olhar descrição e conta (`leitura.py:239`) | killed | `test_interpretacao_completa.py:50` |
| B2 | backend | aba contida comparada como conjunto, sem contar as repetições (`deteccao.py:180`) | killed | `test_deteccao.py:167` |
| B3 | backend | `acertar_saldos` não acerta nada: saldo inicial fica 0 (`contas.py:401`) | killed | `test_contas_da_importacao.py:73`, `test_importacao_completa.py:166` |
| B4 | backend | limite de contas conferido como se fosse uma conta só (`contas.py:384`) | killed | `test_contas_da_importacao.py:113`, `test_importacao_completa.py:256` |
| B5 | backend | `Repetidos` volta ao `if/else`: envio com transferência carrega só as transferências (`repetidos.py:50`) | killed | 4 falhas: `test_repetidos_mistos.py:47`, `:61`, `:68`, `test_importacao_completa.py:193` |
| F1 | frontend | saldo atual enviado com vírgula ("1234,56") | killed | `assistente-contas.test.tsx:78` |
| F2 | frontend | trocar o papel de uma aba não pede nova análise | killed | `assistente-abas-e-colunas.test.tsx:97` |
| F3 | frontend | "Criar" liberado no limite de contas | killed | `assistente-contas.test.tsx:119` |

**Score: 8/8 killed.**

## Perguntas específicas

**IMPCOMP-26: saldo da conta criada.** `criar_contas` cria com saldo inicial zero (`contas.py:386`). Depois da gravação, `acertar_saldos` (`contas.py:394`) calcula o efeito como `calcular(conta) - initial_balance`, que soma só as transações COMPLETED de entrada (`INCOME`, `TRANSFER_IN`) e de saída, com as pernas das transferências de e para outras contas, e grava `saldo_atual - efeito` com `update()` antes do `recalcular`. Pendentes não entram em `calcular` (`accounts/saldo.py:44`). `test_contas_da_importacao.py:73` cobre efetivadas, pendente, transferência para uma vinculada e de uma vinculada, e a conta só com pendentes; `test_importacao_completa.py:166` cobre o fluxo inteiro com transferências entre contas criadas. B3 morreu nos dois. **Ordem:** `completa.importar` chama `acertar_saldos` na linha 588, depois que `Gravacao.importar` voltou (`completa.py:587`), e o `recalculo_adiado` é aberto e fechado dentro de `Gravacao.importar` (`gravacao.py:74`); não há outro `recalculo_adiado` em volta, então o recálculo adiado já rodou quando o acerto começa. A ordem não entrou no sensor porque, dentro do adiamento, o resultado seria o mesmo: `calcular` lê o banco direto e a saída do contexto recalcularia as contas anotadas.

**IMPCOMP-27 e IMPCOMP-29: limite e desfazer.** `criar_contas` chama `conferir_limite(usuario, 'limite_contas', quantidade=len(novas))` uma vez, antes de criar qualquer conta (`contas.py:384`); `conferir_limite` recusa quando `uso + quantidade > limite` e trava a linha do usuário com `select_for_update` (`core/travas.py:329-330`). B4 morreu. Toda a importação roda num `transaction.atomic()` próprio (`completa.py:580`), dentro do `ATOMIC_REQUESTS` (`core/settings.py:158`). `ImportacaoView` e `ImportacaoAnaliseView` (`data_exchange/views.py:106-137`) não usam `non_atomic_requests` nem o mixin de `api/views.py:85`. `test_importacao_completa.py:245` faz `acertar_saldos` falhar depois das contas e das linhas e confere zero contas e transações novas.

**IMPCOMP-46: contadores do envio misto.** `Repetidos.__init__` carrega as transferências quando há alguma e as receitas e despesas quando há alguma (`repetidos.py:48-58`), dois `if` independentes. A chave das receitas e despesas inclui o tipo, então as pernas `TRANSFER_OUT`/`TRANSFER_IN` da consulta não colidem com elas. B5 morreu em 4 testes.

**IMPCOMP-15: "Total" de verdade.** `linha_de_resumo` (`leitura.py:233`) exige a primeira célula começando com "Total" e as colunas mapeadas de descrição e de conta vazias. `test_interpretacao_completa.py:50` tem uma linha com "Total" na primeira célula (a data), "Total" na descrição e conta preenchida: ela não é pulada e segue as regras comuns (rejeitada por "Data inválida", porque a data é o texto "Total"); outra, com "Total da fatura" na descrição, é importada. B1 morreu.

**IMPCOMP-09: multiconjunto.** `abas_contidas` (`deteccao.py:160`) monta um `Counter` de assinaturas por aba e exige `linhas_da_outra[k] >= n` para cada chave. `test_deteccao.py:167` tem a aba "Repetida" com a mesma linha duas vezes, presente uma vez em "Extrato", e a aba fica usada. B2 (conjunto) morreu.

**Rotas antigas e desempenho.** `/import/spreadsheet/`, `/import/spreadsheet/preflight/` e `/import/ofx/` continuam em `data_exchange/urls.py` e passam nos testes antigos de `tests.importacao` (`test_gravacao.py`, `test_concorrencia.py`, `test_interpretacao_completa.py:265` para o preflight) e em `test_travas_de_recurso.py`. O teste de IMPORT-40 passou sozinho em 26,7 s (o limite é 30 s).

**Frontend.** O plano vai como texto JSON no campo `plano` do multipart (`src/services/import-export.ts:88-92`), sem `modelo`, `motivo`, `cabecalho` e `arquivo` (`assistente-servico.test.tsx:39`). Papel e colunas pedem nova análise com o plano editado (`RevisaoDeAbas.tsx:74`, `AssistenteDePlanilha.tsx:179`); vincular, criar e trocar a conta vinculada pedem, e nome, tipo, instituição e saldo não (`RevisaoDeContas.tsx:65-89`). No limite, `criar` sai cedo e o botão "Criar" fica desabilitado (`RevisaoDeContas.tsx:78`, `:131`), com o uso somando as contas já marcadas para criar (`:60-63`). F1, F2 e F3 morreram.

## Gaps (por prioridade)

1. **IMPCOMP-03 conta as abas ignoradas e os rodapés no limite de 10.000 (precisão da spec).** `ler_abas` conta as linhas de dados de todas as abas antes da detecção (`leitura.py:222`), como a AC diz. Na exportação do Mobills, as abas "Despesas" e "Receitas" repetem a primeira, então o teto real fica perto de 5.000 lançamentos. Correção: decidir na spec. Se o limite for de lançamentos, contar depois da detecção só as linhas das abas usadas, sem os rodapés (mantendo um teto bruto maior, por exemplo 30.000, para proteger a leitura), com teste de um Mobills de 6.000 linhas na aba principal. Se for de leitura, escrever na IMPCOMP-03 que as abas ignoradas também contam.
2. **A aba "Transferências" real não tem linha "Total" (precisão da spec e do arquivo de teste).** O Problem Statement diz que toda aba termina num "Total", e `tests/importacao/mobills.py:78` põe um rodapé em "Transferências"; o arquivo real só tem rodapé nas três abas de receitas e despesas (`summary_rows` 1 no real, 2 no teste). O código trata os dois casos. Correção: tirar o rodapé de "Transferências" em `abas_do_mobills` (ou acrescentar uma variante sem ele), ajustar `test_importacao_completa.py:106` e `:180` para `summary_rows` 1 e corrigir o texto da spec.
3. **IMPCOMP-26 com pendente e transferência para conta vinculada só é testado por unidade.** `test_contas_da_importacao.py:73` chama `Gravacao.importar` e `acertar_saldos` direto; o teste de rota (`test_importacao_completa.py:166`) usa só linhas "Paga" e transferências entre contas criadas. Correção: um teste em `test_importacao_completa.py` que importe um CSV com uma linha "A pagar" e uma transferência entre uma conta a criar e `self.a.conta` (vinculada) e confira o saldo da criada igual ao `saldo_atual` e o da vinculada só com o efeito da transferência.
4. **A detecção pode sugerir mais contas a criar do que o limite permite (IMPCOMP-40, precisão).** A tela impede marcar mais uma e mostra o aviso, mas o botão Importar continua liberado, e a importação recebe o 403 de IMPCOMP-27 (tratado em `assistente-resultado.test.tsx:153`). Cumpre a AC. Correção opcional: desabilitar Importar com `aCriar + uso > limite` e dizer no aviso quantas contas trocar para vincular, ou registrar na spec que a recusa vem só na importação.
5. **Margem do IMPORT-40.** O teste passou em 26,7 s com a máquina parada; a validação do `vinculo-entre-transacoes` já registrou 42,2 s com a suíte do frontend rodando junto. A feature não mexe no caminho antigo além do `if` dos repetidos. Correção opcional: rodar `test_desempenho` isolado no gate, ou medir o tempo da gravação sem a criação do arquivo.
6. **IMPCOMP-15 numa aba sem colunas de descrição e de conta mapeadas (precisão).** Com as duas colunas ausentes, a condição "vazias" é sempre verdadeira, e qualquer linha cuja primeira célula começa com "Total" vira resumo (`leitura.py:239`, `all` sobre uma lista vazia). Risco baixo: sem descrição nem conta mapeadas, a linha só seria importada com a primeira célula como data. Correção: escrever na IMPCOMP-15 "as colunas de descrição e de conta mapeadas estão vazias" e cobrir o caso num teste.
