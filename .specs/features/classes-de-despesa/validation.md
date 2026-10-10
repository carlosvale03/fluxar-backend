# Classes de despesa Validation

**Verdict: PASS**

Verificação leve feita por um verificador independente (autor ≠ verificador): conferência das 40 ACs contra a spec e um sensor de discriminação com 9 mutações de comportamento. Uma mutação se mostrou equivalente ao código original; as outras 8 morreram. Os gaps abaixo são de cobertura fina e de precisão da spec; nenhum deles derruba uma AC.

## Diff ranges

| Repo | Branch | Range | Commits |
| ---- | ------ | ----- | ------- |
| fluxar-backend | `feat/classes-de-despesa-nas-categorias-e-relatorios` | `development (861dfe6)..HEAD (2682c39)` | 12 (`5bf5cd5` a `2682c39`) |
| fluxar-frontend | `feat/classes-de-despesa-nas-categorias-e-relatorios` | `development (ae531ce)..HEAD (802e547)` | 4 (`a7f18e7`, `1666ecb`, `b507ecf`, `802e547`) |

Baseline: `tests.classes` no backend com 61 testes OK (Postgres do `docker compose`); a suíte inteira do backend com 1263 testes e uma falha, `tests.importacao.test_desempenho.test_dez_mil_linhas_em_ate_30_segundos`, que passa sozinha (3 testes OK) e só estourou o tempo porque a suíte do frontend rodava ao mesmo tempo na máquina. No frontend, `tests/classes` com 25 testes OK em 4 arquivos, a suíte inteira com 410 testes OK em 77 arquivos e `tsc --noEmit` sem erro.

## Evidência por AC

Backend em `tests/classes/`; frontend em `tests/classes/`.

### Classes do usuário

| AC | Evidência |
| -- | --------- |
| CLASSE-01 | backend `test_padrao.py:34`, `:59` (cada usuário com as próprias classes) |
| CLASSE-02 | backend `test_api.py:24` (lista sem paginação, 5 classes, só as do usuário, com `is_default` e `categories_count`) |
| CLASSE-03 | frontend `gerenciar-classes.test.tsx:51` (só as sugestões não criadas, sem diferença de acento), `:96` (com 5 classes, nenhuma sugestão) |
| CLASSE-04 | backend `test_api.py:54`; frontend `gerenciar-classes.test.tsx:60` |
| CLASSE-05 | backend `test_api.py:65` (a sexta: 400 com a mensagem e 5 no banco), `:75` (limite por usuário); frontend `gerenciar-classes.test.tsx:85`, `:96` |
| CLASSE-06 | backend `test_api.py:82` (vazio, só espaços e 31 caracteres no campo `name`; 30 aceita) |
| CLASSE-07 | backend `test_api.py:91` ("dividas", "DÍVIDAS", " Dividas ", "essencial", "dispensavel"), `:127` (renomear para "ESSENCIAL"); frontend `gerenciar-classes.test.tsx:72` |
| CLASSE-08 | backend `test_api.py:109` (renomear), `:154` (excluir), `:117` (a cor muda); frontend `gerenciar-classes.test.tsx:111` |
| CLASSE-09 | frontend `gerenciar-classes.test.tsx:145` ("2 categorias usam esta classe.", Cancelar não chama a API, a confirmação chama) |
| CLASSE-10 | backend `test_api.py:162` (categoria principal e subcategoria perdem a classe própria; as demais não mudam); `test_implantacao.py:112` (`SET_NULL` no modelo) |
| CLASSE-11 | backend `test_api.py:179` (falha forçada no `delete`: classe e categorias intactas) |
| CLASSE-12 | backend `test_concorrencia.py:47` (duas criações com 4 classes: 201 e 400, 5 no banco), `:61` (mesmo nome sem acento: uma só) |
| CLASSE-13 | backend `test_api.py:196` (tudo fechado, plano COMMON: lista, cria, edita e exclui), `test_graficos.py:137` (divisão por classe com tudo fechado). A classe nas categorias e o filtro por classe não têm teste com o plano fechado; ver gap 4 |
| CLASSE-14 | backend `test_implantacao.py:126` (exclusão definitiva apaga as classes da Ana, as da Bia ficam) |
| CLASSE-15 | backend `test_api.py:218` (criar, renomear, nome repetido e excluir: nem log nem `SystemLog` com o nome) |

### Classe das categorias

| AC | Evidência |
| -- | --------- |
| CLASSE-16 | backend `test_categorias.py:34` (subcategoria nova herda), `:55` (troca só ela e volta a herdar), `:72` (mãe sem classe, filha com classe), `:142` (subcategoria movida herda da nova mãe), `:166` (neta herda pela avó, receita sem classe, ciclo A↔B sem travar) |
| CLASSE-17 | backend `test_categorias.py:79`, `:55`; frontend `classe-das-categorias.test.tsx:190` |
| CLASSE-18 | backend `test_categorias.py:34` (na resposta da criação e na lista aninhada), `:55` |
| CLASSE-19 | frontend `classe-das-categorias.test.tsx:119` (classe efetiva com a cor, "(herdada)", "Sem classe" em cinza) |
| CLASSE-20 | frontend `classe-das-categorias.test.tsx:136` ("Herdar da categoria-mãe (Essencial)" e `expense_class: null`), `:155` (escolhe outra), `:211` (volta a herdar na edição) |
| CLASSE-21 | backend `test_categorias.py:96` (edição e criação de receita: 400 no campo `expense_class`); frontend `classe-das-categorias.test.tsx:170` (a seleção some e nada é enviado) |
| CLASSE-22 | backend `test_categorias.py:113` |
| CLASSE-23 | backend `test_categorias.py:126` (classe da Bia, UUID inexistente e texto qualquer: a mesma resposta "Classe não encontrada.") |
| CLASSE-24 | backend `test_padrao.py:39`, `:50` (subcategorias de Casa e receitas sem classe própria) |
| CLASSE-25 | backend `test_implantacao.py:53`, `:60` ("comida", "  ELETRONICOS ", "Educação"; "Mercado" fica sem classe), `:79` (subcategorias e receitas ficam de fora), `:93` (a classe é a do próprio usuário). Rodar duas vezes não tem teste; ver gap 3 |
| CLASSE-26 | backend `test_categorias.py:204` (categoria e subcategoria da importação sem classe própria; a subcategoria em Comida herda Essencial) |
| CLASSE-27 | backend `test_categorias.py:154` (mapa mantém a classe da excluída e da filha), `test_graficos.py:108` |

### Divisão das despesas por classe

| AC | Evidência |
| -- | --------- |
| CLASSE-28 | backend `test_graficos.py:50` (Independent Test: 600, 300 e 100 com "Sem classe" e `class_id` nulo), `:64`, `:116` (período vazio: lista vazia), `:121` (só as despesas da usuária) |
| CLASSE-29 | backend `test_graficos.py:62` e `:85` (soma por classe igual à soma por categoria, com parcela de cartão, cartão sem categoria, subcategoria, categoria sem classe, pendente, receita) |
| CLASSE-30 | backend `test_graficos.py:93` (trocar a classe de Doces muda agosto) |
| CLASSE-31 | frontend `grafico-por-classe.test.tsx:110` (valor, 60,0%, 30,0%, 10,0%, cor de cada classe e cinza no "Sem classe"), `:125` (centavos, 33,3% e 66,7%, total zero) |
| CLASSE-32 | frontend `grafico-por-classe.test.tsx:140` (lista vazia e só zeros: "Nenhuma despesa no período.") |
| CLASSE-33 | frontend `grafico-por-classe.test.tsx:149` (`classId` e o período; `sem_classe`), `:161` (Relatórios sem os avançados), `:171` (dashboard); `filtro-por-classe.test.tsx:84`, `:95` (a lista lê `classId`, `startDate` e `endDate` da URL) |

### Filtro e exportação por classe

| AC | Evidência |
| -- | --------- |
| CLASSE-34 | backend `test_filtro.py:89` (despesa e compra no cartão), `:103` (duas classes), `:113` (subcategoria pela classe herdada), `:119`; frontend `filtro-por-classe.test.tsx:103` (três `classId` repetidos) |
| CLASSE-35 | backend `test_filtro.py:92` (sem categoria, categoria sem classe, cartão sem categoria), `:97` (com uma classe) |
| CLASSE-36 | backend `test_filtro.py:50` a `:54` (receita, receita sem categoria, transferência e pagamento de fatura nunca aparecem nas asserções de `:89` a `:122`) |
| CLASSE-37 | backend `test_filtro.py:109` |
| CLASSE-38 | backend `test_filtro.py:124` (classe de outro usuário), `:129` (texto qualquer, também junto de uma classe válida), na lista e nas duas exportações |
| CLASSE-39 | backend `test_filtro.py:75` (`assert_traz` confere lista, PDF e XLS com os mesmos ids em todos os casos); frontend `filtro-por-classe.test.tsx:116`, `:132`. Nenhum relatório aceita o filtro de categoria hoje (`design.md:155`) |
| CLASSE-40 | backend `test_exportacao.py:68` (Dispensável, Essencial herdada, "Sem classe", vazia em receita e nas pernas da transferência), `:94` (com o filtro), `:101` (planilha da LGPD) |

## Discrimination sensor

Backend: mutações aplicadas num worktree destacado (`../fluxar-backend-mut`, removido depois), `tests.classes` rodado num container de uma imagem temporária (a do projeto mais o `requirements.txt`, por falta do `cryptography`; apagada depois), na rede `fluxar-backend_default`. Frontend: mutação no arquivo real, `vitest run` do arquivo de teste, e `git checkout` em seguida.

| # | Repo | Mutação | Resultado | Testes que pegaram |
| - | ---- | ------- | --------- | ------------------ |
| B1 | backend | `classes_efetivas` não sobe para a mãe (para na própria categoria) | killed | 11 falhas: `test_categorias.py:34`, `:55`, `:142`, `:154`, `:166`, `:204`; `test_exportacao.py:68`, `:94`, `:101`; `test_filtro.py:113`; `test_graficos.py:64` |
| B2 | backend | limite com `>` no lugar de `>=` (aceita a sexta classe) | killed | `test_api.py:65`, `test_concorrencia.py:47` |
| B3 | backend | nome normalizado só com `lower().strip()`, sem tirar acentos | killed | `test_api.py:91`, `:127`, `test_concorrencia.py:61` |
| B4 | backend | `sem_classe` sem o `Q(category__isnull=True)` | equivalente | nenhum, e não precisa: o Django traduz `~Q(category_id__in=...)` para `NOT (category_id IN (...) AND category_id IS NOT NULL)`, que já inclui as sem categoria |
| B5 | backend | criação sem o `select_for_update` na linha do usuário | killed | `test_concorrencia.py:47` |
| B6 | backend | filtro por classe sem o `type__in=TIPOS_DE_DESPESA` | killed | `test_filtro.py:92`, `:97` |
| F1 | frontend | porcentagem arredondada ao inteiro ("33,0%") | killed | `grafico-por-classe.test.tsx:125` |
| F2 | frontend | o clique no gráfico não leva `startDate` e `endDate` | killed | `grafico-por-classe.test.tsx:149`, `:161`, `:171` |
| F3 | frontend | a subcategoria nova começa com a classe da mãe copiada como própria | killed | `classe-das-categorias.test.tsx:136` |

**Score: 8/8 killed** (9 mutações aplicadas, 1 equivalente).

Observação sobre B5: só `test_concorrencia.py:47` pega a falta da trava, e o nome repetido simultâneo continua protegido pela restrição única do banco mesmo sem ela.

## Perguntas específicas

**CLASSE-29: mesmas transações nas duas divisões.** As duas partem de `regras.despesas(user, start_date, end_date)` (`reports/services.py:343` e `:400`). A divisão por categoria agrupa pela categoria da própria transação, com `_categoria_do_usuario` (nome nulo vira "Sem Categoria"); a divisão por classe agrupa por `category_id` e resolve a classe pelo `mapa_de_classes`, que sobe a árvore inteira. Como as duas somam todas as linhas do mesmo queryset e nenhuma descarta grupo, os totais batem em qualquer caso: transação sem categoria vai para "Sem Categoria" e "Sem classe"; transação com categoria de outro usuário (dado antigo, ISOL) não está no mapa (`Category.objects.filter(user=usuario)`) e vai para "Sem classe", como vai para "Sem Categoria" na outra; categoria excluída continua no mapa (sem filtro de `is_active`) e na divisão por categoria. Os testes cobrem sem categoria, excluída, subcategoria e cartão; o caso da categoria de outro usuário não tem teste. Ver gap 2.

**CLASSE-16: herança em vários níveis e ciclos.** `classes_efetivas` (`transactions/classes.py`) sobe de mãe em mãe até achar uma classe própria, uma categoria já resolvida, uma categoria de receita, uma categoria fora do mapa ou uma já vista no caminho (ciclo); todas as do caminho sem classe própria recebem a classe encontrada. A neta herda da avó (`test_categorias.py:166`, Condomínio → Aluguel → Casa) e o ciclo A↔B termina sem classe e sem travar (mesmo teste). B1 confirma que a herança é discriminada.

**CLASSE-12: concorrência.** A criação trava a linha do usuário com `select_for_update` (`transactions/views.py:75`) dentro da transação da requisição (`ATOMIC_REQUESTS`, `core/settings.py:157`), então a contagem do limite (`:76`) é feita uma requisição depois da outra. O nome tem a restrição única `classe_nome_unico_por_usuario` em `(user, nome_normalizado)`; o `IntegrityError` vira 400 no campo `name`, também na edição. As duas proteções são exercidas por `test_concorrencia.py` com duas threads e conexões próprias; B2, B3 e B5 morreram nesses testes.

**CLASSE-25: a migração.** `implantar` (`transactions/migrations/0013_classes_de_despesa.py:48`) cria Essencial e Dispensável com `get_or_create` por `(user, nome_normalizado)` e só olha categorias `type='EXPENSE'`, `parent__isnull=True` e `classe__isnull=True`, comparando o nome normalizado sem acentos, maiúsculas e espaços nas pontas. Rodar de novo não duplica classes nem sobrescreve uma classe já escolhida pelo usuário, mas não há teste disso (gap 3). As categorias principais excluídas com nome padrão também recebem a classe, o que a spec não diz mas combina com CLASSE-27.

**Layout do dashboard (`getInitialConfig`).** O código (`src/components/dashboard/dashboard-customizer.tsx:289`) monta a configuração só com os módulos de `DEFAULT_CONFIG` que estão no layout salvo, na ordem salva, e depois insere cada módulo novo logo depois do anterior a ele no layout padrão. Simulei a função com layouts salvos: antigo sem `CLASS_DISTRIBUTION` em ordem invertida e tudo oculto, com `EXPENSE_DISTRIBUTION` oculto, com id repetido e id desconhecido, sem o primeiro módulo, e vazio. Em todos saíram os 11 módulos, sem repetição, com a visibilidade salva mantida e o gráfico por classe logo depois da distribuição de despesas. Ids desconhecidos são descartados, como antes. Dois detalhes: um módulo novo que seja o primeiro do padrão vai para o fim, não para o começo; e o módulo novo entra visível mesmo que o vizinho esteja oculto. Nenhum dos dois perde ou duplica módulo. A função não tem teste; ver gap 1.

## Gaps (por prioridade)

1. **A mescla do layout salvo do dashboard não tem teste.** É a única mudança de comportamento fora da feature que mexe em dado salvo do usuário (o `localStorage` com o layout). Correção: um teste em `tests/classes/grafico-por-classe.test.tsx` ou num arquivo próprio que grava no `localStorage` um layout antigo sem `CLASS_DISTRIBUTION`, com ordem trocada e módulos ocultos, e confere que `getInitialConfig()` devolve os 11 módulos sem repetição, com a ordem e a visibilidade salvas e `CLASS_DISTRIBUTION` logo depois de `EXPENSE_DISTRIBUTION`. Opcional: com `posicao === -1` e `index === 0`, inserir no começo (`dashboard-customizer.tsx:307-308`).
2. **CLASSE-29 sem o caso da transação com categoria de outro usuário.** Pelo código os totais batem, mas nenhum teste fixa isso. Correção: em `test_graficos.py:64`, criar uma despesa da Ana apontando para uma categoria da Bia (via `Transaction.objects.create`) e conferir que ela entra em "Sem classe" e que as somas continuam iguais.
3. **A implantação não é testada rodando duas vezes.** Correção: em `test_implantacao.py`, chamar `implantar` duas vezes, trocar a classe de uma categoria entre as duas chamadas e conferir que cada usuário continua com duas classes padrão e que a classe trocada não volta.
4. **CLASSE-13 cobre as classes e a divisão, mas não a classe das categorias nem o filtro com o plano fechado.** Correção: em `test_api.py:196`, no mesmo cenário com tudo fechado, `PATCH /api/categories/<id>/` com `expense_class` (200) e `GET /api/transactions/?classId=<id>` (200).
5. **CLASSE-09 diz "quantas categorias a usam" (precisão da spec).** O número mostrado é o de categorias ativas com essa classe própria (`categories_count`); as subcategorias que herdam a classe de uma mãe com ela não entram na conta, embora a classe efetiva delas também mude com a exclusão. Correção: escrever na CLASSE-09 "quantas categorias têm essa classe própria", que é o que o código e o `test_api.py:24` fazem, ou somar as que herdam.
6. **O `Q(category__isnull=True)` de `transactions/filtros.py:84` é redundante (B4).** O Django já inclui os nulos na negação do `__in`. Não é defeito; pode ficar como documentação. Se preferir que o sensor discrimine, troque por `Q(category__isnull=True) | Q(category_id__in=sem_classe_efetiva)` com a lista das categorias sem classe, e aí o teste `test_filtro.py:92` passa a depender dele.

## Correções após a verificação

1. **Mescla do layout salvo do dashboard** (frontend `5c9119a`): `tests/classes/layout-do-dashboard.test.ts` grava no `localStorage` um layout antigo sem `CLASS_DISTRIBUTION`, com ordem trocada e módulos ocultos, e confere os 11 módulos sem repetição, a ordem e a visibilidade salvas e `CLASS_DISTRIBUTION` logo depois de `EXPENSE_DISTRIBUTION`. O detalhe do primeiro módulo também foi corrigido em `getInitialConfig`: um módulo que falta no layout salvo e é o primeiro do padrão agora entra no começo, com teste.
2. **CLASSE-29 com categoria de outro usuário** (backend `d4767a2`): `test_graficos.py` lança uma despesa da Ana na categoria da Bia e confere que ela entra em "Sem classe" e que as somas por classe e por categoria batem.
3. **Implantação rodando duas vezes** (backend `d4767a2`): `test_implantacao.py` chama `implantar` duas vezes, com a troca da classe de uma categoria e uma classe criada pela usuária entre as rodadas, e confere que as classes não se repetem e a escolha da usuária fica.
4. **CLASSE-13 com a classe das categorias e o filtro** (backend `d4767a2`): no teste com tudo fechado, `PATCH /api/categories/<id>/` com `expense_class` responde 200 e grava a classe, e `GET /api/transactions/?classId=<id>` responde 200.
5. **Texto da CLASSE-09** (backend `f19f450`): a spec agora diz "quantas categorias têm essa classe como classe própria"; as subcategorias que a herdam seguem a herança (CLASSE-10).
6. Sem mudança: o `Q(category__isnull=True)` redundante fica como documentação.

Depois das correções: `tests.classes` com 63 testes OK; suíte completa do backend com 1265 testes OK; frontend com 78 arquivos e 413 testes OK, `tsc` limpo e `eslint` com 149 erros (sem aumento).
