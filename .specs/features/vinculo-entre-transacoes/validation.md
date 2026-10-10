# Vínculo entre transações Validation

**Verdict: PASS**
**Result**: PASS

Verificação leve feita por um verificador independente (autor ≠ verificador): conferência das 37 ACs contra a spec e um sensor de discriminação com 8 mutações de comportamento, todas mortas. 36 ACs têm evidência. A VINCULO-03 não é cumprida por inteiro: a busca da principal só pelo valor olha apenas as 100 despesas mais recentes, e uma despesa mais antiga com o valor procurado aparece como "Nenhum gasto encontrado.". É o único motivo do FAIL; a correção é pequena (gap 1).

## Diff ranges

| Repo | Branch | Range | Commits |
| ---- | ------ | ----- | ------- |
| fluxar-backend | `feat/vinculo-entre-transacoes` | `development (9990dcb)..HEAD (8dd781c)` | 11 (`d0bfa17` a `8dd781c`; código em `e8c979b`, `c7c1b58`, `e5c386f`, `2d581fc`, `d544bc5`, `be9a6cf`) |
| fluxar-frontend | `feat/vinculo-entre-transacoes` | `development (54360e9)..HEAD (5877304)` | 4 (`925e669`, `e4c9a1c`, `a687016`, `5877304`) |

Baseline: no backend, `tests.vinculos` com 64 testes OK e `tests.permissoes.test_travas_de_recurso` mais `tests.isolamento` com 207 testes OK (Postgres do `docker compose`, imagem temporária com o `requirements.txt`). No frontend, `tests/vinculos` com 22 testes OK em 4 arquivos.

## Evidência por AC

Backend em `tests/vinculos/`; frontend em `tests/vinculos/`.

### Criar e desfazer vínculos

| AC | Evidência |
| -- | --------- |
| VINCULO-01 | backend `test_gasto_relacionado.py:55` (despesa com `principal`), `:63` (compra no cartão em 3 parcelas, ligada pela raiz); frontend `acoes.test.tsx:101` (menu abre "Nova Despesa" com "Por causa de: Cinema, 12/09/2026"), `:115` e `:134` (`principal` no corpo do POST da despesa e da compra) |
| VINCULO-02 | backend `test_rotas.py:40` (`POST /link/` devolve 200 e grava), `test_regras.py:76` (despesa e compra no cartão); frontend `acoes.test.tsx:154` (busca, "Vincular a Cinema" chama `POST /transactions/t-padaria/link/` e recarrega a lista) |
| VINCULO-03 | Parcial. Frontend `acoes.test.tsx:154` (descrição: `type=EXPENSE`, `search`, receita e a própria transação fora, compra no cartão dentro), `:187` (data em `startDate`/`endDate` e valor conferido no cliente). O valor não é filtro da API: `src/services/vinculos.ts:61-77` pede `type=EXPENSE&page_size=100` e filtra o valor nas 100 linhas devolvidas. Ver gap 1 |
| VINCULO-04 | backend `test_regras.py:128` (campos das duas transações iguais, as duas existem), `test_rotas.py:107` (`DELETE /link/` com saldos, faturas, orçamentos e campos iguais); frontend `acoes.test.tsx:227` |
| VINCULO-05 | backend `test_regras.py:47` (receita dos dois lados), `:57` (transferência), `:67` (pagamento de fatura), mensagem e 400 em `assert_recusa` (`:34`); `test_gasto_relacionado.py:105` (receita com `principal` na criação) |
| VINCULO-06 | backend `test_regras.py:87`, `test_rotas.py:59`, `test_gasto_relacionado.py:88`; frontend `acoes.test.tsx:208` (o detail vai ao toast, a janela fica aberta) |
| VINCULO-07 | backend `test_regras.py:92` |
| VINCULO-08 | backend `test_regras.py:98` (a mesma transação e duas parcelas da mesma compra), `:105` (a restrição do banco recusa) |
| VINCULO-09 | backend `test_regras.py:113`, `test_rotas.py:48` (troca pela rota, um vínculo só) |
| VINCULO-10 | backend `test_regras.py:119` (`updated_at` igual, sem erro), `test_rotas.py:48` (200 na repetição) |
| VINCULO-11 | backend `test_rotas.py:79` (principal de outro usuário e id inexistente: a mesma resposta `{'principal': ['Transação não encontrada.']}`), `test_gasto_relacionado.py:114` (nas duas rotas de criação). A dependente de outro usuário na URL recebe 404 (`test_rotas.py:90`), não 400; ver gap 2 |
| VINCULO-12 | backend `test_regras.py:142` (parcela 3 de 10 como dependente grava na raiz), `:151` (parcela como principal), `test_rotas.py:66`, `test_gasto_relacionado.py:63` |
| VINCULO-13 | backend `test_regras.py:156` (a 4ª de 12 ocorrências, só ela), `test_gasto_relacionado.py:74` |
| VINCULO-14 | backend `test_regras.py:176` (dependentes sem vínculo, não excluídas), `:185` (compra parcelada principal excluída por uma parcela) |
| VINCULO-15 | backend `test_regras.py:193` (principal igual por `values()`), `test_api.py:54` (custo de 115,00 para 70,00) |
| VINCULO-16 | backend `test_regras.py:204` (como dependente e como principal, pelo PATCH), `:219` (série pelo `bulk-update`) |
| VINCULO-17 | backend `test_regras.py:238` (saldos, totais das faturas e uso dos orçamentos iguais ao vincular parcela, trocar, vincular despesa e desfazer), `test_rotas.py:107` |
| VINCULO-18 | backend `test_gasto_relacionado.py:88` (principal que já é dependente: nem a despesa nem as 3 parcelas ficam gravadas), `:105` |
| VINCULO-19 | backend `test_concorrencia.py:61` (A em B e B em A em threads com conexões próprias: um "ok" e um 400, um vínculo só, um nível), `:68` (cadeia simultânea) |
| VINCULO-20 | backend `test_rotas.py:128` (ligar e trocar: 403), `test_gasto_relacionado.py:131` (criação com `principal`: 403, sem ela 201), `test_filtros.py:126` (filtros na lista, XLSX e PDF), `test_relatorio.py:132`; frontend `acoes.test.tsx:245`, `filtro-com-vinculo.test.tsx:116`, `gastos-puxados.test.tsx:149`, `custo-total.test.tsx:134` |
| VINCULO-21 | backend `test_rotas.py:128` (vínculo continua e `DELETE` responde 200 com o recurso travado), `test_filtros.py:126` (a lista sem filtro mostra `total_cost` 95,00); frontend `acoes.test.tsx:245` (desfazer sem `aria-disabled` e chama a rota) |
| VINCULO-22 | backend `test_regras.py:253` (as transações da Ana somem, o vínculo da Bia fica) |
| VINCULO-23 | backend `test_regras.py:266` (logs com o id, sem descrições nem valores) |

### Custo total na principal

| AC | Evidência |
| -- | --------- |
| VINCULO-24 | frontend `custo-total.test.tsx:71` ("Custo total R$ 95,00" e "1 gasto relacionado" na tabela e no cartão), `:107` (a lista da principal mostra a dependente com categoria e valor). A lista das dependentes é a lista filtrada, aberta pelo custo total; ver gap 3 |
| VINCULO-25 | frontend `custo-total.test.tsx:85` ("Por causa de: Cinema, 12/09/2026" nos dois layouts); backend `test_api.py:40` (`principal_detail` com descrição e data) |
| VINCULO-26 | backend `test_api.py:34` (principal), `:40` (dependente), `:49` (sem vínculo) |
| VINCULO-27 | backend `test_api.py:69` (jantar em 3 × 40 soma 120 no custo do cinema: 170,00; cada parcela mostra a principal), `:80` (compra principal em 3 parcelas: 345,00 em cada parcela) |
| VINCULO-28 | backend `test_api.py:97` (`expense_by_category` igual antes e depois: Lazer 50,00 e Transporte 45,00); `test_regras.py:238` (orçamentos). Fora do relatório de gastos puxados, nenhum código de `reports`, `budgets`, `accounts`, `core` ou `api` lê o campo `principal` |

### Filtro de vinculadas

| AC | Evidência |
| -- | --------- |
| VINCULO-29 | backend `test_filtros.py:52`, `:55` (todas as parcelas da compra principal e da compra dependente, a partir de qualquer parcela) |
| VINCULO-30 | backend `test_filtros.py:75` (principais, dependentes e as parcelas delas; sem a avulsa e a compra sem vínculo), `:87` (outro valor: 400 no campo); frontend `filtro-com-vinculo.test.tsx:65` (`linked=true` na página 1, limpar tira) |
| VINCULO-31 | frontend `custo-total.test.tsx:95` (clique leva a `/transacoes?principalId=t-cinema` sem abrir a edição), `:107` (envia `principalId` sem o período, mostra o aviso e limpa), `filtro-com-vinculo.test.tsx:106` |
| VINCULO-32 | backend `test_filtros.py:64` (outro usuário, inexistente e malformado: 400 com "Transação inválida no filtro: <valor>."), `:117` (na exportação) |
| VINCULO-33 | backend `test_filtros.py:96` (XLSX com o filtro do cinema: as duas linhas, o mesmo cabeçalho, sem coluna de vínculo; `linked=true` no XLSX; PDF 200); frontend `filtro-com-vinculo.test.tsx:85` (XLS e PDF com `linked=true`) |

### Relatório de gastos puxados

| AC | Evidência |
| -- | --------- |
| VINCULO-34 | backend `test_relatorio.py:54` (três cinemas: Lazer puxa 180,00 de Transporte), `:71` ("Sem categoria", subcategoria e neta pela raiz, Lazer puxando Lazer), `:90` (ordem por total), `:123` (outro usuário fora) |
| VINCULO-35 | backend `test_relatorio.py:63` (transporte de 1º de outubro ligado a cinema de 30 de setembro entra em outubro), `:105` (cada parcela no mês dela; pendente fora), `:118` (mês vazio) |
| VINCULO-36 | frontend `gastos-puxados.test.tsx:103` ("Lazer puxou R$ 180,00 de Transporte", total do grupo, ordem), `:138` (na tela Relatórios, segue o período) |
| VINCULO-37 | frontend `gastos-puxados.test.tsx:119` |

## Discrimination sensor

Backend: mutações aplicadas num worktree destacado (`../fluxar-backend-mut`, removido depois), `tests.vinculos` rodado num container de uma imagem temporária (a do projeto mais o `requirements.txt`, por falta do `cryptography`; apagada depois), na rede `fluxar-backend_default`. Frontend: mutação no arquivo real, `vitest run` do arquivo de teste e `git checkout` em seguida.

| # | Repo | Mutação | Resultado | Testes que pegaram |
| - | ---- | ------- | --------- | ------------------ |
| B1 | backend | `vincular` sem a recusa da principal que já é dependente | killed | 5 falhas: `test_regras.py:87`, `test_rotas.py:59`, `test_gasto_relacionado.py:88`, `test_concorrencia.py:61`, `:68` |
| B2 | backend | o vínculo gravado na parcela escolhida, não na raiz da compra | killed | 8 falhas, entre elas `test_regras.py:142`, `test_rotas.py:66`, `test_api.py:69` |
| B3 | backend | `total_cost` soma só a primeira parcela de cada compra | killed | 4 falhas, entre elas `test_api.py:69`, `:80` |
| B4 | backend | relatório de gastos puxados pela data da principal, não pela da dependente | killed | `test_relatorio.py:63`, `:105` (outubro) |
| B5 | backend | `DELETE /link/` exige o recurso `vinculos` | killed | `test_rotas.py:128` |
| F1 | frontend | "Custo total" mostra o valor da principal, não o `total_cost` | killed | `custo-total.test.tsx:71`, `:95`, `:134` |
| F2 | frontend | "Vincular a um gasto" liberado com o recurso travado | killed | `acoes.test.tsx:245` |
| F3 | frontend | "Com vínculo" não envia `linked=true` na lista | killed | `filtro-com-vinculo.test.tsx:65` |

**Score: 8/8 killed.**

## Perguntas específicas

**VINCULO-03: busca pelo valor.** Não cumpre a AC por inteiro. `buscarGastos` (`src/services/vinculos.ts:61`) pede `/transactions/?type=EXPENSE&page_size=100`, com `search` e o dia quando preenchidos, e confere o valor nas linhas que voltam. O `max_page_size` é 100 (`core/pagination.py:30`), e a API não tem filtro de valor (`transactions/filtros.py`). Numa busca só pelo valor, uma despesa mais antiga que as 100 mais recentes nunca aparece, e a tela responde "Nenhum gasto encontrado." para um gasto que existe; para quem lança uns 3 gastos por dia, isso é pouco mais de um mês. Com descrição ou data a janela fica estreita e o problema quase some. Dois detalhes do mesmo trecho: numa compra parcelada o valor comparado é o da parcela, não o da compra, e cada parcela aparece como um resultado. Correção no gap 1.

**VINCULO-19: concorrência.** `vincular` (`transactions/vinculos.py:53`) roda em `atomic` e trava as duas raízes com `select_for_update().order_by('pk')`; as regras são conferidas depois da trava, sobre as linhas recém-lidas (`alvo.principal_id`) e com uma consulta nova para "já tem dependentes" (`:83`). Em A→B e B→A os dois pedidos disputam as mesmas duas linhas na mesma ordem, então não há deadlock e o segundo enxerga o vínculo gravado pelo primeiro e recebe "Uma transação dependente não pode ser principal.". Na cadeia (pipoca em transporte e transporte em cinema) os dois travam o transporte, e o segundo enxerga o primeiro. `test_concorrencia.py:61` e `:68` usam `TransactionTestCase` com threads e conexões próprias; B1 morreu nos dois. A retirada da trava não entrou no sensor.

**VINCULO-17 e VINCULO-28: saldos, faturas, orçamentos e totais por categoria.** Há testes: `test_regras.py:238` fotografa saldos das contas, totais das faturas e uso dos orçamentos antes e depois de vincular, trocar e desfazer, com compra parcelada no cartão; `test_rotas.py:107` faz o mesmo pelo `DELETE`; `test_api.py:97` confere o gráfico por categoria igual com e sem vínculo. O vínculo é gravado com `update()`, sem os signals de saldo e fatura (`vinculos.py:89`), e nenhum cálculo fora do relatório novo lê o campo.

**VINCULO-12 e VINCULO-27: parcelas.** O vínculo vai sempre para `raiz_da_compra` (`parent_transaction_id or pk`), dos dois lados. O `total_cost` soma, numa consulta agregada por `Coalesce('parent_transaction_id', 'pk')`, todas as parcelas da compra principal e de cada compra dependente (`vinculos.py:141-149`). O `principalId` resolve a raiz de qualquer parcela e devolve a raiz, as parcelas dela, as dependentes e as parcelas das dependentes (`filtros.py:184-188`); `test_filtros.py:55` confere o conjunto exato a partir da 1ª e da 3ª parcela. B2 e B3 morreram.

**VINCULO-21: desfazer com o recurso travado.** No backend, `link` só chama `exigir_recurso` no `POST` (`transactions/views.py:307`); `test_rotas.py:128` desfaz com o recurso fechado. No frontend, "Desfazer vínculo" não depende de `liberado` (`vincular-transacao.tsx:112`), e `acoes.test.tsx:245` desfaz com o plano travado. B5 morreu.

**VINCULO-35: data da dependente.** `gastos_puxados` (`reports/services.py:96`) parte de `regras.despesas(user, inicio, fim)`, que filtra pela `report_date` da própria dependente com as regras dos gráficos de despesa (efetivadas e compras no cartão, sem ajustes de saldo), e só depois agrupa pela categoria raiz da principal. `test_relatorio.py:63` e `:105` pegaram B4.

**Desempenho da lista.** `ListaComVinculos` (`vinculos.py:167`) calcula os campos de todas as linhas da página de uma vez em `dados_dos_vinculos`, com até quatro consultas fixas. `test_api.py:115` conta as consultas em `transactions_transaction` com 2 e com 20 linhas vinculadas e exige o mesmo número, além de conferir 19 dependentes e 113,00 no cinema.

## Gaps (por prioridade)

1. **VINCULO-03: a busca pelo valor só vê as 100 despesas mais recentes (motivo do FAIL).** Correção mínima: um filtro `amount` em `filtrar_transacoes` (`transactions/filtros.py`), com o texto decimal validado como no `amount` da criação (400 no campo para valor inválido) e `qs.filter(amount=valor)`; somar `amount` a `parametros_permitidos` em `transactions/views.py:177` (e a `PARAMETROS_DA_EXPORTACAO` se quiser manter a AD-022). No frontend, `buscarGastos` envia `amount` e deixa de filtrar no cliente. Testes: no backend, `tests/vinculos/test_filtros.py` com `amount=50.00` trazendo uma despesa antiga entre mais de 100 recentes e `amount=abc` com 400; no frontend, `acoes.test.tsx:187` passa a conferir `amount=50.00` na URL. Opcional: comparar também com a soma das parcelas da compra, ou mostrar uma linha por compra.
2. **VINCULO-11 diz 400 também para a dependente de outro usuário (precisão da spec).** A dependente vem na URL (`/transactions/{id}/link/`), e o código responde 404, como toda rota de detalhe (AD-010); `test_rotas.py:90` fixa o 404. Correção: escrever na VINCULO-11 "IF a principal for de outro usuário ou não existir THEN 400 no campo `principal` ...; a dependente de outro usuário ou inexistente na URL recebe 404".
3. **VINCULO-24 pede a lista das dependentes na interface da principal (precisão da spec).** A principal mostra o custo total e a quantidade; a lista com descrição, categoria e valor é a lista filtrada que o custo total abre (VINCULO-31, `custo-total.test.tsx:107`). Correção: ajustar a VINCULO-24 para "o custo total e a quantidade de dependentes, com acesso à lista delas (VINCULO-31)", ou mostrar as dependentes num detalhe da principal com teste.
4. **A trava de `vincular` não entrou no sensor.** Os testes de concorrência existem e pegam a falta da regra (B1), mas a retirada do `select_for_update` não foi mutada. Correção opcional: rodar a mutação em `vinculos.py:68` e, se sobreviver, deixar `test_concorrencia.py:61` repetir a disputa algumas vezes.

## Correções após a verificação

Feitas pelo autor depois deste relatório, na mesma branch. O Verdict e o Result do topo continuam os da verificação; o gap 1, motivo do FAIL, está corrigido, e o veredito pode ser revisto.

| Gap | Correção | Commit |
| --- | -------- | ------ |
| 1. VINCULO-03, busca pelo valor (FAIL) | Backend: filtro `amount` em `filtrar_transacoes` (`filtrar_por_valor` em `transactions/filtros.py`), lido por `ler_valor` de `core/valores.py` como o `amount` da criação; ilegível, zero, negativo ou com mais de duas casas recebe 400 `{"amount": ["Valor inválido no filtro: <valor>."]}`. Traz as transações com esse valor e as compras parceladas cujo total (soma das parcelas agrupadas pela raiz) é esse valor, com a raiz e todas as parcelas, como no `principalId`; a compra parcelada também aparece pelo valor de uma parcela. `amount` entrou em `parametros_permitidos` da lista e em `PARAMETROS_DA_EXPORTACAO` (AD-022). Testes em `tests/vinculos/test_filtros.py` (`ValorTests`): despesa antiga achada atrás de 120 recentes, `abc`/`0`/`-5.00`/`1.234` com 400 (também no XLSX), compra de 300,00 em 3 parcelas achada por `300.00` e por `100.00`, sem a compra igual de outro usuário | backend `4b2a115` (`feat: filtra as transações pelo valor`) |
| 1. VINCULO-03, frontend | `buscarGastos` (`src/services/vinculos.ts`) envia `amount` no formato da API ("50.00") e deixa de conferir o valor no cliente; a própria transação continua fora. Sem agrupar as parcelas numa linha por compra: a API da lista não expõe a raiz da compra (`parent_transaction`), e agrupar pela descrição seria um palpite. `tests/vinculos/acoes.test.tsx` confere `amount=50.00` na URL, mostra a parcela de outro valor que a API devolveu e não envia `amount` sem valor | frontend `71b6898` (`fix: busca o gasto principal pelo valor no servidor`) |
| 2. VINCULO-11 | Spec: principal de outro usuário ou inexistente recebe 400 no campo `principal` com a mesma mensagem de um id inexistente; a dependente da URL de outro usuário ou inexistente recebe 404 (AD-010) | backend `761df5a` (`docs: ajusta a VINCULO-11 e a VINCULO-24 depois da verificação`) |
| 3. VINCULO-24 | Spec: a principal mostra o custo total e a quantidade de dependentes; ao abri-la, a lista das dependentes com descrição, categoria e valor é a lista filtrada da VINCULO-31 | backend `761df5a` |
| 4. Trava de `vincular` no sensor | Não tratado (opcional) | — |

Gates depois das correções: backend `tests.vinculos` com 67 testes OK; suíte completa com 1431 testes, uma falha só em `tests.importacao.test_desempenho` (42,2 s com a suíte do frontend rodando junto), que passou sozinho (3 testes OK). Frontend: `tsc --noEmit` sem erros, `npm test` com 477 testes OK em 87 arquivos, `eslint .` com 149 erros (o mesmo teto), `npm run build` OK.

## Reverificação

Feita pelo orquestrador depois das correções, com o sensor focado no gap 1 e na trava do `vincular` (gap 4):

| # | Mutação | Resultado | Pego por |
|---|---------|-----------|----------|
| R1 | `filtrar_por_valor` só pelo valor da transação, sem o total da compra parcelada | morta | `tests/vinculos/test_filtros.py` `test_compra_parcelada_aparece_pelo_total` |
| R2 | `filtrar_por_valor` devolve a lista sem filtrar | morta | `test_valor_acha_uma_despesa_antiga_atras_de_mais_de_100_recentes` e `test_compra_parcelada_aparece_pelo_total` |
| R3 | `vincular` sem `select_for_update` | morta | `tests/vinculos/test_concorrencia.py` (os 2 testes) |
| R4 | A busca da tela deixa de enviar `amount` | morta | `tests/vinculos/acoes.test.tsx` |

Com o gap 1 corrigido e as quatro mutações mortas, o verdict passa a PASS. Fica anotado que a busca mostra cada parcela de uma compra como um resultado, porque a lista não devolve `parent_transaction`.
