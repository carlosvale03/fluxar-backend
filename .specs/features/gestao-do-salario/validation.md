# Gestão do salário Validation

**Verdict: PASS** (depois da reverificação; a primeira verificação deu FAIL pelo gap 1, corrigido)

Verificação leve feita por um verificador independente (autor ≠ verificador): conferência das 56 ACs contra a spec e um sensor de discriminação com 9 mutações de comportamento, mais 2 variantes. Uma mutação se mostrou equivalente ao código original; as demais morreram. O backend cumpre as ACs com evidência. O verdict é FAIL por um gap de produto: a interface só oferece "Desfazer divisão" na tela de resultado logo depois da geração. Fechada essa tela, nenhuma API nem tela lista as divisões, e o usuário não consegue desfazer no dia seguinte, embora a spec dê 7 dias (SALARIO-45, SALARIO-46, SALARIO-49). Os demais gaps são de cobertura fina e de precisão da spec.

## Diff ranges

| Repo | Branch | Range | Commits |
| ---- | ------ | ----- | ------- |
| fluxar-backend | `feat/gestao-do-salario-plano-e-divisao` | `development (fe1849e)..HEAD (27d1efc)` | 13 (`ac53341` a `27d1efc`): código em `682e3a4`, `f968d3e`, `3721d3b`, `9f55be2`, `1b56a82`, `c708682`, `1d1ecd8`; docs nos demais |
| fluxar-frontend | `feat/gestao-do-salario-plano-e-divisao` | `development (6b6e463)..HEAD (d0a76f3)` | 5 (`4146193`, `73e3d6b`, `045f596`, `87028b2`, `d0a76f3`) |

Baseline: no backend, `tests.salario` com 89 testes OK e `tests.salario`, `tests.lgpd`, `tests.permissoes.test_travas_de_recurso` e `tests.isolamento` juntos com 393 testes OK, rodados num container de uma imagem temporária (a do projeto mais o `requirements.txt`, por falta do `cryptography`; apagada depois), na rede `fluxar-backend_default`, contra o Postgres do `docker compose`. No frontend, `tests/salario` com 36 testes OK em 5 arquivos. A suíte inteira dos dois repos e o `tsc` não foram rodados nesta verificação.

## Evidência por AC

Backend em `tests/salario/` (salvo indicação); frontend em `tests/salario/`.

### Plano de divisão

| AC | Evidência |
| -- | --------- |
| SALARIO-01 | backend `test_plano.py:37` (quatro modelos, autor, obra e partes); frontend `plano.test.tsx:75` |
| SALARIO-02 | backend `test_calculo.py:50`, `:53`, `:60` (partes e percentuais dos três modelos), `test_plano.py:37` |
| SALARIO-03 | backend `test_calculo.py:71`, `test_plano.py:98`; frontend `plano.test.tsx:214` |
| SALARIO-04 | backend `test_plano.py:69`, `:85`; frontend `plano.test.tsx:214` (nome, valor fixo), `:89` |
| SALARIO-05 | backend `test_plano.py:69` (meta), `:85` (conta); frontend `plano.test.tsx:121` (só contas ativas que não são cofrinho e metas ativas) |
| SALARIO-06 | backend `test_calculo.py:53`, `:60`, `test_plano.py:37` (gastar em `SALARY_ACCOUNT`, guardar sem destino) |
| SALARIO-07 | backend `test_plano.py:85`; frontend `plano.test.tsx:89` |
| SALARIO-08 | backend `test_plano.py:122` (400 com a mensagem, plano salvo intacto), `:133` (100% passa), `:253` (simulação); frontend `plano.test.tsx:198` |
| SALARIO-09 | backend `test_plano.py:136` (fixo 0,00), `:145` (100,01, 0,00 e -5,00 recusados; 100 e 0,01 aceitos) |
| SALARIO-10 | backend `test_plano.py:157` (conta e meta de outro usuário com a mesma resposta de um id inexistente) |
| SALARIO-11 | backend `test_plano.py:174` (cofrinho, conta inativa, meta inativa) |
| SALARIO-12 | backend `test_plano.py:69` (reabre igual), `test_geracao.py:118` (o plano salvo é o usado na geração) |
| SALARIO-13 | backend `test_plano.py:225` (sem criar transação), `:240` (partes não salvas); frontend `plano.test.tsx:145` |
| SALARIO-14 | backend `test_plano.py:195` (Salário e subcategorias de início), `:203`, `:210`; frontend `plano.test.tsx:233` |
| SALARIO-15 | frontend `pagina.test.tsx:55` (menu de recursos leva a `/salario`) |
| SALARIO-16 | backend `tests/permissoes/test_travas_de_recurso.py:253` com as 10 rotas de `:186` a `:196`, `test_plano.py:264`; frontend `pagina.test.tsx:62` |
| SALARIO-17 | backend `test_modelos.py:45` (exclusão definitiva), `:58` (limpeza); `tests/lgpd/test_exclusao_definitiva.py` com os modelos no inventário |
| SALARIO-18 | backend `test_plano.py:282`, `test_geracao.py:137`, `test_desfazer.py:122` |

### Aviso ao receber o salário

| AC | Evidência |
| -- | --------- |
| SALARIO-19 | frontend `aviso.test.tsx:120` (lançar efetivada em Salário), `:169` (efetivar pendente na lista), `:143` (outra categoria não abre). Efetivar pela edição do formulário não abre o aviso; ver gap 3 |
| SALARIO-20 | frontend `aviso.test.tsx:120` (os três benefícios, na ordem) |
| SALARIO-21 | frontend `aviso.test.tsx:134` (`/salario?dividir=<id>`), `revisao.test.tsx:230` (o parâmetro abre a revisão daquele salário) |
| SALARIO-22 | frontend `revisao.test.tsx:242` (sem plano, escolha do modelo e, salvo o plano, a revisão), `pagina.test.tsx:71` |
| SALARIO-23 | frontend `aviso.test.tsx:134` (fecha); o recebimento continua em `pending` porque nada é gravado (backend `test_revisao.py:27`) |
| SALARIO-24 | backend `test_revisao.py:27` (mês atual e anterior, importado entra, pendente, outra categoria, outro usuário e dividido ficam de fora), `:47`, `:59`, `:66` (virada do ano); frontend `pagina.test.tsx:71`, `:87` |
| SALARIO-25 | frontend `aviso.test.tsx:160` (travado: nem lê o plano) |

### Geração das transações

| AC | Evidência |
| -- | --------- |
| SALARIO-26 | backend `test_calculo.py:80`, `:109` |
| SALARIO-27 | backend `test_calculo.py:115`, `:122` (zera a última e reduz a anterior), `:142`, `test_revisao.py:135`, `test_plano.py:240`; frontend `revisao.test.tsx:138` (selo "Reduzida") |
| SALARIO-28 | backend `test_calculo.py:96` (33,33% de 1.000,00 = 333,30), `:102` (123,459 vira 123,45) |
| SALARIO-29 | backend `test_revisao.py:87`; frontend `revisao.test.tsx:113` |
| SALARIO-30 | backend `test_calculo.py:131`, `:142`, `test_revisao.py:119`, `test_geracao.py:118`; frontend `revisao.test.tsx:158` |
| SALARIO-31 | frontend `revisao.test.tsx:128` (desabilitado até a marcação, "Gerar 1 transação de R$ 600,00"), `:138` (plural) |
| SALARIO-32 | backend `test_geracao.py:47` (efetivadas, data de hoje), `:80`; `test_revisao.py:111` (a data da revisão segue Brasília à noite). A geração em si não tem o caso da virada UTC; ver gap 5 |
| SALARIO-33 | backend `test_geracao.py:47` (cofrinho dividido com o Carro: só Viagem recebe) |
| SALARIO-34 | backend `test_calculo.py:156`, `test_geracao.py:102` |
| SALARIO-35 | backend `test_geracao.py:80` (as 4 pernas levam o id da divisão e só elas), `test_modelos.py:123` |
| SALARIO-36 | backend `test_geracao.py:165` (falha inesperada no segundo item), `:183` (recusa no segundo item) |
| SALARIO-37 | backend `test_geracao.py:200`, `:213` (mesmo com o recebimento excluído), `:239`, `test_concorrencia.py:75`; frontend `revisao.test.tsx:178` |
| SALARIO-38 | backend `test_geracao.py:227` (com outra chave e sem chave), `test_revisao.py:165` |
| SALARIO-39 | backend `test_concorrencia.py:67` (chaves diferentes: 201 e 400), `:75` (mesma chave: duas 201 iguais), com threads e conexões próprias |
| SALARIO-40 | backend `test_geracao.py:300` (pendente, de outro usuário), `test_revisao.py:149` (pendente, outra categoria, outro usuário, inexistente). Receita sem conta não tem teste |
| SALARIO-41 | backend `test_geracao.py:253` |
| SALARIO-42 | backend `test_geracao.py:262` (meta arquivada, meta excluída, conta inativa) |
| SALARIO-43 | backend `test_geracao.py:290` (plano vazio e plano só na conta do salário) |
| SALARIO-44 | frontend `revisao.test.tsx:214` |

### Desfazer a divisão

| AC | Evidência |
| -- | --------- |
| SALARIO-45 | frontend `desfazer.test.tsx:98` (a confirmação lista as transações). Só alcançável na tela de resultado logo depois de gerar; ver gap 1 |
| SALARIO-46 | backend `test_desfazer.py:63` (saldos e metas de volta, inclusive a meta que divide o cofrinho); frontend `desfazer.test.tsx:114` |
| SALARIO-47 | backend `test_desfazer.py:77`; frontend `desfazer.test.tsx:114` |
| SALARIO-48 | backend `test_desfazer.py:143` (aporte editado), `:151` (transferência excluída), `:156` (voltou a pendente), `:163` (meta sem o valor) |
| SALARIO-49 | backend `test_desfazer.py:88` (7º dia desfaz), `:93` (8º dia recusa e nada muda); frontend `desfazer.test.tsx:128`. Na prática, a interface não deixa pedir o desfazer depois de fechar o resultado; ver gap 1 |
| SALARIO-50 | backend `test_desfazer.py:168` (falha forçada na segunda exclusão: tudo como estava) |
| SALARIO-51 | backend `test_desfazer.py:102` (400 "Esta divisão já foi desfeita." sem remover nada, mesmo com uma nova divisão ativa) |

### Referências do mês e histórico

| AC | Evidência |
| -- | --------- |
| SALARIO-52 | backend `test_referencias.py:41` (recorrente pendente do mês e fatura: 1.650,00; fora do mês, paga e avulsa ficam de fora); frontend `pagina.test.tsx:94` |
| SALARIO-53 | backend `test_referencias.py:70`, `:130`; frontend `pagina.test.tsx:94` |
| SALARIO-54 | frontend `plano.test.tsx:75` (na escolha do modelo), `:111` ("62,0% no seu histórico") |
| SALARIO-55 | backend `test_plano.py:106`; frontend `plano.test.tsx:135` |
| SALARIO-56 | backend `test_referencias.py:95`, `:106`, `:115`; frontend `pagina.test.tsx:107`, `:114` |

## Discrimination sensor

Backend: mutações aplicadas num worktree destacado (`../fluxar-backend-mut`, removido depois), `tests.salario` rodado no container da imagem temporária. Frontend: mutação no arquivo real, `vitest run` do arquivo de teste e `git checkout` em seguida.

| # | Repo | Mutação | Resultado | Testes que pegaram |
| - | ---- | ------- | --------- | ------------------ |
| B1 | backend | percentual arredondado com `ROUND_HALF_UP` no lugar de `ROUND_DOWN` (`calculo.py:58`) | killed | `test_calculo.py:102` |
| B2 | backend | redução começa pela primeira parte (`for item in itens` no lugar de `reversed`) | killed | `test_calculo.py:115`, `:122`; `test_revisao.py:135`; `test_plano.py:240` |
| B3 | backend | geração sem o `select_for_update` no recebimento (`divisao.py:326`) | equivalente | nenhum, em 3 rodadas de `test_concorrencia`; as duas restrições únicas parciais e o `except IntegrityError` no savepoint dão a mesma resposta sem a trava |
| B3b | backend | sem a trava e sem tratar o `IntegrityError` do savepoint | killed | `test_concorrencia.py:67`, `:75` (nas 2 rodadas): a corrida acontece de verdade no teste |
| B4 | backend | idempotência ignora a chave (atalho da view e `pela_chave` desligados) | killed | `test_geracao.py:200`, `:213`, `:239`; `test_concorrencia.py:75` |
| B5 | backend | desfazer sem conferir o prazo | killed | `test_desfazer.py:93` |
| B5b | backend | prazo com `>=` (recusa já no 7º dia) | killed | `test_desfazer.py:88` |
| B6 | backend | desfazer com `Transaction.objects.filter(divisao_do_salario=...).delete()` | killed | só `test_desfazer.py:168`, que depende de `Transaction.delete` por instância; `:63` continua passando porque o `QuerySet.delete` também dispara os sinais por objeto |
| F1 | frontend | botão de gerar habilitado sem a marcação | killed | `revisao.test.tsx:128` |
| F2 | frontend | chave nova a cada tentativa de geração | killed | `revisao.test.tsx:178` |
| F3 | frontend | aviso abre para receita pendente | killed | `aviso.test.tsx:151` |
| F4 | frontend | aviso abre com o recurso travado | killed | `aviso.test.tsx:160` |

**Score: 11/11 killed** (12 mutações aplicadas, 1 equivalente).

## Perguntas específicas

**SALARIO-45, SALARIO-46 e SALARIO-49: dá para desfazer no dia seguinte?** Não. O botão "Desfazer divisão" existe só no `ResultadoDaDivisao`, dentro do diálogo da revisão, com a divisão que a geração acabou de devolver (`RevisaoDaDivisao.tsx`, `GestaoDoSalario.tsx`: `onDesfazer={setParaDesfazer}`). O backend tem `GET /salary/divisions/<id>/` e `POST .../undo/`, mas não lista as divisões do usuário, e as transações não expõem a divisão de origem na lista de transações. Fechado o diálogo ou recarregada a página, o id se perde, e a única saída é apagar cada transação à mão, o que a própria spec diz que não devolve o valor das metas (FIN-09). O prazo de 7 dias, a mensagem de prazo acabado e a tela "Você pode desfazer até ..." prometem algo que a interface não entrega. Isso derruba a história "Desfazer a divisão" como a spec a descreve. Correção no gap 1.

**SALARIO-36 e SALARIO-39: tudo ou nada e concorrência.** `gerar` (`salario/divisao.py:316`) é `@transaction.atomic` dentro do `ATOMIC_REQUESTS`; qualquer exceção no laço dos itens desfaz o lote (`test_geracao.py:165`, `:183`). O recebimento é travado com `select_for_update` (`:326`), a chave é conferida de novo depois da trava (`:329`) e a criação da divisão fica num savepoint (`:339`) com duas restrições únicas parciais: `(user, chave)` com chave não nula e `recebimento_ref` com `desfeita_em` nulo (`models.py:94-102`). O `IntegrityError` vira a divisão da mesma chave ou "Este salário já foi dividido.". B3 mostra que a trava é redundante com as restrições; B3b mostra que a corrida acontece no teste e que as restrições com o tratamento seguram.

**SALARIO-37: a repetição da mesma chave.** A view responde antes de validar (`views.py:285-288`) com `divisao_em_json` remontado do registro, e `gerar` confere a chave antes e depois da trava. `test_geracao.py:200` compara o corpo inteiro das duas respostas e a contagem de transações; `:213` cobre o recebimento excluído entre as duas; `test_concorrencia.py:75`, as duas ao mesmo tempo. B4 morreu.

**SALARIO-48: edição, exclusão e meta.** `_item_mudou` (`divisao.py:391`) recusa se alguma perna sumiu ou mudou de valor, data, status, conta, `transfer_id` ou marca, e no aporte se o `GoalDeposit` do valor com aquela perna de entrada não existe mais. Depois, cada meta precisa ter pelo menos a soma aportada pela divisão (`:471-474`). Mudanças só de descrição ou categoria não contam como edição; ver gap 6. A exclusão é uma a uma, pela perna de saída, e o `sync_transfer_delete` leva a parceira (`:476-478`). B6 mostra que trocar por `QuerySet.delete` passa nos testes de comportamento: o Django também envia os sinais por objeto nesse caso, então os saldos e as metas voltam igual; só o teste com o `mock` de `Transaction.delete` pega.

**SALARIO-27 e SALARIO-28: ordem da redução e centavos.** `dividir` (`calculo.py:71`) calcula cada parte, soma o excesso e reduz de trás para frente, pulando as ajustadas, marcando `reduzida`; o percentual usa `quantize(CENTAVO, ROUND_DOWN)` (`:58`). B1 e B2 morreram. B1 só é pego por `test_calculo.py:102`; `:96` (333,30) não distingue `ROUND_DOWN` de `ROUND_HALF_UP`.

**SALARIO-19 e SALARIO-25: quando o aviso abre.** `useAvisoDoSalario` (`AvisoDoSalario.tsx:88`) só segue com receita `INCOME`, `COMPLETED`, sem `import_batch`, com `podeUsar("gestao_do_salario") === true`, e só abre se a categoria está nas `salary_categories` do plano lido na hora. É chamado no `onSuccess` do formulário de criação no dashboard e na lista de transações, e no `handleConfirm` do botão "Efetivar" da lista, com a transação devolvida pelo `PATCH`. F3 e F4 morreram. Dois caminhos ficam de fora: a edição de uma receita pendente pelo formulário com o status trocado para efetivada (o formulário passa `criada` só na criação) e um eventual "Efetivar" fora da página de transações, que hoje não existe. Ver gap 3.

## Gaps (por prioridade)

1. **Não dá para desfazer uma divisão depois de fechar a tela de resultado (FAIL; SALARIO-45, SALARIO-46, SALARIO-49).** Correção mínima:
   - Backend: `GET /api/salary/divisions/?undoable=true` em `SalaryDivisionsView.get`, com a mesma trava, devolvendo as divisões do usuário com `desfeita_em` nulo e `hoje() <= prazo_para_desfazer(divisao)`, da mais recente para a mais antiga, no formato de `divisao_em_json`. Testes em `tests/salario/test_desfazer.py`: lista a divisão no 7º dia e não no 8º, some depois de desfeita, não traz as de outro usuário e responde 403 com o recurso travado (incluir a rota em `test_travas_de_recurso.py:186`).
   - Frontend: `salarioService.getDivisoesRecentes()` e uma seção "Divisões recentes" em `GestaoDoSalario`, com o salário, a data, o total, "Você pode desfazer até dd/MM/yyyy" e o botão "Desfazer divisão", que abre o `DesfazerDivisao` já existente; recarregar a lista depois de gerar e de desfazer. Teste em `tests/salario/desfazer.test.tsx`: abrir a página com uma divisão na lista, desfazer por ela, e a lista e os salários a dividir são relidos.
2. **SALARIO-28 tem um só caso que distingue o arredondamento (B1).** `test_calculo.py:96` não distingue `ROUND_DOWN` de `ROUND_HALF_UP`. Só `:102` pega a mutação. Correção: somar na simulação ou na revisão (API) um caso que arredonde para cima no `HALF_UP`, como 10% de 1.234,55 (123,455 vira 123,45 e o livre 1.111,10), para o arredondamento ficar fixado também fora da função pura.
3. **SALARIO-19 sem o caminho da edição.** Efetivar uma receita pendente pelo formulário de edição, trocando o status, não abre o aviso: `transaction-form-dialog.tsx` só passa `criada` na criação. Correção: no ramo de edição, quando o status anterior era `PENDING` e o novo é `COMPLETED`, passar a transação devolvida pelo `PATCH`/`PUT` ao `onSuccess`; teste em `aviso.test.tsx`. Se a decisão for deixar só o botão "Efetivar", escrever isso na SALARIO-19.
4. **B6: a exclusão uma a uma só é protegida por um teste acoplado à implementação.** A AD-053 justifica a exclusão por instância com os sinais das metas, mas o `QuerySet.delete` também dispara os sinais. Correção: um teste de comportamento que mostre a diferença que a AD-053 quer garantir (por exemplo, o sinal da meta recusando valor negativo no meio do desfazer e tudo voltando), ou registrar na AD-053 que a escolha é de clareza, não de comportamento.
5. **SALARIO-32 sem o caso da virada do dia na geração.** `test_revisao.py:111` cobre a revisão às 23h30 de Brasília; a geração usa o mesmo `hoje()`, mas o prazo de desfazer é calculado de `criada_em` em Brasília. Correção: em `test_geracao.py`, gerar às 02h30 UTC do dia 11 e conferir a data 10 nas pernas e `can_undo_until` igual a 17.
6. **SALARIO-48 diz "editada" sem dizer o quê (precisão da spec).** O código só recusa mudanças de valor, data, status, conta, `transfer_id` e marca; trocar a descrição ou a categoria de uma perna não impede o desfazer. Correção: escrever na SALARIO-48 "editada no valor, na data, no status ou na conta", que é o que o código e os testes `test_desfazer.py:143` a `:163` fazem.
7. **SALARIO-40 sem o caso "sem conta".** Correção: em `test_revisao.py:149`, uma receita de Salário efetivada com `account=None` recebe o mesmo 400.
8. **A trava do recebimento é redundante (B3).** Não é defeito: as restrições únicas e o tratamento do `IntegrityError` dão a mesma resposta. Pode ficar como defesa em profundidade; se preferir que o sensor discrimine, documentar na AD-053 que a garantia vem das restrições.

## Correções após a verificação

Feitas pelo autor, na mesma branch `feat/gestao-do-salario-plano-e-divisao` dos dois repositórios. O gap 1, que deu o FAIL, está corrigido; o verdict pode ser revisto por uma nova verificação.

| Gap | Correção | Commits |
| --- | -------- | ------- |
| 1 (FAIL) | Backend: `GET /api/salary/divisions/?undoable=true`, com a trava `gestao_do_salario`, lista as divisões do usuário não desfeitas e com `hoje() <= can_undo_until`, da mais recente para a mais antiga, no formato do detalhe. Sem `undoable=true` responde 400; outro parâmetro recebe o 400 de filtro desconhecido (`ParametrosConhecidosMixin`). Testes em `tests/salario/test_desfazer.py` (`DivisoesQueAindaPodemSerDesfeitasTests`: listada no 7º dia e igual ao detalhe, fora no 8º, fora depois de desfeita, ordem e sem as de outro usuário, 400 sem o parâmetro, 403 travado) e a rota no catálogo de `tests/permissoes/test_travas_de_recurso.py`. Frontend: seção "Divisões recentes" na página, com o salário, a data de recebimento, a data da divisão, o total e "Você pode desfazer até dd/MM/yyyy", e o botão "Desfazer divisão", que abre o `DesfazerDivisao` existente; a lista é relida depois de gerar e de desfazer; sem divisões no prazo, a seção não aparece. Testes em `tests/salario/desfazer.test.tsx` (`Divisões recentes`, mais "gerar relê as divisões recentes") | backend `0f4a8ea`; frontend `3ebc0a5` |
| 2 | `test_plano.py`: simulação de 10% de 1.234,55 = 123,45, total 123,45 e livre 1.111,10; o `ROUND_HALF_UP` daria 123,46 | backend `8005148` |
| 3 | `TransactionFormDialog` passa ao `onSuccess` a transação devolvida pelo `PUT` quando a receita era `PENDING` e voltou `COMPLETED`; nas outras edições continua sem nada. Teste em `aviso.test.tsx` (edição de uma já efetivada não abre; pendente que volta efetivada abre com o id dela). Ressalva: o formulário de edição não tem campo de status nem o envia, e o backend não muda o status pela data, então pela interface de hoje o `PUT` de uma pendente volta pendente e o caminho só dispara se um campo de status for acrescentado ao formulário. Na prática, efetivar continua sendo pelo botão "Efetivar" da lista; se o usuário preferir, a SALARIO-19 pode dizer isso | frontend `0ec5d68` |
| 4 | Não feito como teste. Nenhum comportamento observável distingue a exclusão uma a uma do `QuerySet.delete`: os sinais por objeto rodam nos dois casos, e a única diferença (o `ao_excluir` só recusa meta negativa quando a origem é uma instância) não é alcançável, porque o desfazer já recusa antes uma meta com `current_amount` menor que o aportado, e o `current_amount` é sempre o recalculado dos registros. Registrado na AD-053 que a escolha é de clareza e de defesa a mais. O título do commit de testes cita a exclusão uma a uma, mas ele não traz esse teste | backend `c634905` (AD-053) |
| 5 | `test_geracao.py`: geração às 02h30 UTC do dia 11 com as pernas, a resposta e a transação na data 10 e `can_undo_until` 17 | backend `8005148` |
| 6 | SALARIO-48 diz "editada no valor, na data, no status ou na conta" | backend `c634905` |
| 7 | Receita de Salário efetivada sem conta recebe o 400 "Escolha um salário recebido para dividir." na revisão (`test_revisao.py`) e na geração (`test_geracao.py`) | backend `8005148` |
| 8 | AD-053 registra que a garantia do "já dividido" vem das restrições únicas parciais e do savepoint, e que a trava do recebimento é defesa a mais; menciona também a nova rota de listagem, que entrou no design.md (seção "Desfazer") | backend `c634905` |

Gates depois das correções: backend, suíte inteira no container do `docker compose` com 1363 testes e 1 falha, `tests.importacao.test_desempenho.test_dez_mil_linhas_em_ate_30_segundos`, o teste de desempenho já anotado como sensível à máquina carregada (rodou junto com a suíte do frontend); sozinho, o módulo passou (3 de 3, em 28 s); frontend, `tsc --noEmit` sem erros, `npm test` com 454 testes em 83 arquivos (no primeiro `npm test`, com a suíte do backend rodando ao mesmo tempo, `tests/painel-admin/confirmacoes.test.tsx` estourou o tempo; sozinho passou, 12 de 12, e a suíte com `--maxWorkers=8` passou inteira), `eslint .` com 149 erros (o mesmo teto de antes) e `npm run build` OK.

O que fica: uma nova verificação para rever o verdict; a decisão sobre a ressalva do gap 3 (campo de status no formulário ou a SALARIO-19 restrita ao botão "Efetivar").

## Reverificação

Feita pelo orquestrador depois das correções, com o sensor focado no gap 1:

| # | Mutação | Resultado | Pego por |
|---|---------|-----------|----------|
| R1 | `desfaziveis` sem o filtro do prazo (`criada_em__gte`) | morta | `tests/salario/test_desfazer.py` `test_no_oitavo_dia_a_divisao_sai_da_lista` |
| R2 | `desfaziveis` sem o filtro das já desfeitas (`desfeita_em__isnull`) | morta | `tests/salario/test_desfazer.py` `test_divisao_desfeita_sai_da_lista` |
| R3 | `DivisoesRecentes` nunca mostra a lista | morta | `tests/salario/desfazer.test.tsx` (8 falhas) |

Com o gap 1 corrigido e as três mutações mortas, o verdict passa a PASS.

Sobre o gap 3: o formulário de edição não tem o campo de status, então efetivar pela edição não acontece pela interface atual. SALARIO-19 é atendida pelo botão "Efetivar"; o `onSuccess` da edição já passa a transação efetivada e fica pronto para quando o formulário ganhar o status. Sobre o gap 4: nenhum comportamento observável separa a exclusão uma a uma da exclusão em lote, porque o desfazer recusa antes quando a meta não tem o valor; a decisão ficou registrada na AD-053.
