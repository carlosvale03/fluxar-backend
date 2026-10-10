# Vínculo entre transações Specification

## Problem Statement

Hoje o usuário não consegue registrar que um gasto só aconteceu por causa de outro. No exemplo da ideia, o cinema custou R$ 50,00 em Lazer e o transporte até lá, R$ 45,00 em Transporte: o passeio custou R$ 95,00, mas o app mostra dois gastos soltos. Os campos que ligam transações têm outro significado (`invoice`, `transfer_id`, `parent_transaction` das parcelas e `recurring_source`, em `transactions/models.py:72-100`), e as tags agrupam à mão sem dizer qual gasto puxou qual.

Origem: `docs/auditoria-2026-09.md`, seção 11, PROP-03.

## Goals

- [ ] O usuário vê o custo real de um gasto, com tudo o que ele puxou.
- [ ] O vínculo nunca muda saldos nem conta um gasto duas vezes nos totais.
- [ ] O relatório mostra quanto cada categoria puxa de gastos em outras.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Vínculo nos arquivos de exportação e na importação | Decisão do usuário: o vínculo fica só no app |
| Receita ligada a despesa, como reembolso ou divisão de conta | É outro conceito, com outra regra de custo |
| Cadeias de vínculos, com dependente de dependente | Um nível só (AD-027) |
| Grupo de transações sem direção (evento) | Decisão do usuário: principal e dependentes |
| Vínculo estendido a toda a série recorrente | Só a ocorrência escolhida se liga |
| Vínculo sugerido automaticamente | Pode vir com a previsão de gastos (PROP-04) |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Modelo do vínculo | Uma transação principal e as dependentes dela, que só existiram por causa dela | Decisão do usuário (AD-027) | sim |
| O que aparece no app | Custo total na principal, filtro de vinculadas e relatório de gastos puxados | Decisão do usuário | sim |
| Como criar o vínculo | Lançando um gasto relacionado a partir da principal ou ligando depois uma transação existente | Decisão do usuário | sim |
| Exportação e importação | O vínculo fica só no app | Decisão do usuário (AD-027) | sim |
| Tipos que se ligam | Só despesas e compras no cartão | PROP-03 aprovada: transferência e pagamento de fatura não são gasto, e receita ligada a despesa é reembolso | sim |
| Profundidade | Um nível só: a dependente tem uma principal só, e a principal não é dependente | PROP-03 aprovada: evita ciclos e cadeias difíceis de mostrar | sim |
| Recorrências | Só a ocorrência escolhida se liga; as outras da série não herdam | PROP-03 aprovada | sim |
| Exclusão | Excluir a principal desfaz os vínculos das dependentes, sem apagá-las | PROP-03 aprovada | sim |
| Contagem nos totais e saldo | Cada dependente conta só na própria categoria, e o vínculo não altera saldo, fatura nem orçamento | PROP-03 aprovada | sim |
| Parcelas | A compra parcelada se liga inteira, pela primeira parcela, e o custo total usa a soma de todas as parcelas | Uma parcela só subestimaria o custo do passeio | sim |
| Filtro na exportação | A exportação aceita o filtro de vínculo, mas o arquivo não leva o vínculo | Mantém a AD-022: lista, exportação e relatórios com os mesmos filtros | sim |
| Dependente ligada a outra principal | Troca de principal | Uma dependente conta no custo de uma principal só | sim |
| Despesa vinculada que vira receita | Perde os vínculos | Receita não se vincula | sim |
| Agrupamento do relatório | Pela categoria raiz da principal e da dependente, no período pela data da dependente, com as regras dos gráficos de despesa | É o mesmo agrupamento da pizza de categorias | sim |
| Onde fica o relatório | Uma seção da tela Relatórios | Fica junto dos outros relatórios | sim |
| Busca da principal | Pela descrição, data ou valor, entre as despesas e compras no cartão do usuário | É o que identifica um gasto | sim |
| Trava de plano | Recurso `vinculos` no catálogo (AD-017). Travado, o usuário não cria nem troca vínculos, e o filtro e o relatório ficam travados; os vínculos existentes continuam e podem ser desfeitos | O administrador decide, e o usuário não perde o que já organizou | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Criar e desfazer vínculos ⭐ MVP

**User Story**: Como usuário, quero dizer que um gasto só aconteceu por causa de outro, na hora de lançar ou depois, e desfazer isso quando errar.

**Why P1**: sem o vínculo não existe custo total, filtro nem relatório.

**Acceptance Criteria**:
1. **VINCULO-01** WHEN o usuário lança um gasto relacionado a partir de uma transação principal THEN o sistema SHALL criar a nova despesa ou compra no cartão já como dependente dela.
2. **VINCULO-02** WHEN o usuário liga uma transação existente a uma principal THEN o sistema SHALL gravá-la como dependente dessa principal.
3. **VINCULO-03** WHEN o usuário procura a principal para ligar uma transação existente THEN a interface SHALL permitir buscar pela descrição, data ou valor entre as despesas e compras no cartão dele.
4. **VINCULO-04** WHEN o usuário desfaz o vínculo de uma dependente THEN o sistema SHALL remover só o vínculo, sem alterar nem excluir as transações.
5. **VINCULO-05** IF a principal ou a dependente for receita, transferência ou pagamento de fatura THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Só despesas e compras no cartão podem ser vinculadas."
6. **VINCULO-06** IF a transação escolhida como principal já for dependente de outra THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Uma transação dependente não pode ser principal."
7. **VINCULO-07** IF a transação que vai virar dependente já tiver dependentes THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Uma transação principal não pode virar dependente."
8. **VINCULO-08** IF o usuário tentar ligar uma transação a ela mesma THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Uma transação não pode ser vinculada a ela mesma."
9. **VINCULO-09** WHEN o usuário liga a outra principal uma transação que já é dependente THEN o sistema SHALL trocar a principal dela, que continua com uma principal só.
10. **VINCULO-10** WHEN o usuário liga uma dependente à principal que ela já tem THEN o sistema SHALL manter o vínculo como está, sem erro.
11. **VINCULO-11** IF a principal for de outro usuário ou não existir THEN o sistema SHALL responder HTTP 400 com o erro no campo `principal` e a mesma mensagem de um ID inexistente; IF a dependente, que vem na URL, for de outro usuário ou não existir THEN o sistema SHALL responder HTTP 404, como as outras rotas de detalhe (AD-010).
12. **VINCULO-12** WHEN o usuário escolhe uma parcela como principal ou dependente THEN o sistema SHALL vincular a compra inteira, representada pela primeira parcela.
13. **VINCULO-13** WHEN o usuário vincula uma ocorrência de série recorrente THEN o sistema SHALL ligar só essa ocorrência, sem estender o vínculo às outras da série.
14. **VINCULO-14** WHEN a transação principal é excluída THEN o sistema SHALL desfazer os vínculos das dependentes, sem excluí-las.
15. **VINCULO-15** WHEN uma dependente é excluída THEN o sistema SHALL tirá-la do custo total da principal, sem mudar a principal.
16. **VINCULO-16** WHEN uma despesa vinculada passa a ser receita THEN o sistema SHALL desfazer os vínculos dela.
17. **VINCULO-17** WHEN um vínculo é criado, trocado ou desfeito THEN o sistema SHALL manter iguais os saldos, as faturas e os orçamentos.
18. **VINCULO-18** IF a criação de um gasto relacionado falhar ao gravar o vínculo THEN o sistema SHALL deixar de criar a transação, sem nada gravado.
19. **VINCULO-19** WHILE houver pedidos simultâneos de vínculo que envolvam as mesmas transações, o sistema SHALL manter um nível só, sem ciclo.
20. **VINCULO-20** WHERE o recurso `vinculos` estiver travado no plano do usuário, o sistema SHALL recusar criar ou trocar vínculos, o filtro de vinculadas e o relatório de gastos puxados, conforme PERM-15 e PERM-19.
21. **VINCULO-21** WHILE o recurso `vinculos` estiver travado no plano do usuário, o sistema SHALL manter os vínculos que já existem e permitir desfazê-los.
22. **VINCULO-22** WHEN a conta do usuário é apagada definitivamente THEN o sistema SHALL apagar os vínculos dele junto com as transações (AD-018).
23. **VINCULO-23** WHEN o sistema registra um log de uma operação com vínculos THEN o sistema SHALL omitir descrições e valores das transações (AD-019).

**Independent Test**: a partir do cinema de R$ 50,00, lançar o transporte de R$ 45,00 como gasto relacionado cria a dependente; ligar depois a pipoca, que já existia, também funciona; tentar usar o transporte como principal da pipoca recebe 400 "Uma transação dependente não pode ser principal."; desfazer o vínculo da pipoca mantém as duas transações; os saldos das contas são os mesmos antes e depois de cada passo.

---

### P1: Custo total na principal ⭐ MVP

**User Story**: Como usuário, quero ver na transação principal quanto ela custou de verdade, com tudo o que ela puxou.

**Why P1**: é o que a ideia pede: saber que o passeio custou R$ 95,00, e não R$ 50,00.

**Acceptance Criteria**:
1. **VINCULO-24** WHEN a interface mostra uma transação principal THEN a interface SHALL mostrar o custo total, que é o valor dela mais o das dependentes, e a quantidade de dependentes; WHEN o usuário abre a principal THEN a interface SHALL mostrar a lista das dependentes com descrição, categoria e valor, que é a lista filtrada da VINCULO-31.
2. **VINCULO-25** WHEN a interface mostra uma dependente THEN a interface SHALL indicar a principal dela, com a descrição e a data.
3. **VINCULO-26** WHEN a API devolve uma transação THEN o sistema SHALL incluir a principal dela, se for dependente, e, se for principal, a quantidade de dependentes e o custo total.
4. **VINCULO-27** WHEN a principal ou uma dependente é uma compra parcelada THEN o sistema SHALL usar no custo total a soma de todas as parcelas da compra.
5. **VINCULO-28** WHEN um total ou relatório soma despesas por categoria THEN o sistema SHALL contar cada dependente só na categoria dela.

**Independent Test**: o cinema de R$ 50,00 com o transporte de R$ 45,00 mostra custo total de R$ 95,00 e a lista com o transporte; o transporte mostra "Por causa de: Cinema, 12/09/2026"; o gráfico por categoria mostra R$ 50,00 em Lazer e R$ 45,00 em Transporte, como sem o vínculo; um jantar em 3 parcelas de R$ 40,00 ligado ao cinema soma R$ 120,00 no custo total.

---

### P1: Filtro de vinculadas ⭐ MVP

**User Story**: Como usuário, quero abrir numa lista a principal com todas as dependentes, e achar todas as transações que têm vínculo.

**Why P1**: o custo total diz quanto foi; o filtro mostra em quê.

**Acceptance Criteria**:
1. **VINCULO-29** WHEN a lista de transações recebe o filtro de uma principal THEN o sistema SHALL devolver a principal e as dependentes dela.
2. **VINCULO-30** WHEN a lista de transações recebe o filtro "com vínculo" THEN o sistema SHALL devolver só as transações que são principais ou dependentes.
3. **VINCULO-31** WHEN o usuário abre a lista a partir do custo total de uma principal THEN a interface SHALL mostrar a lista filtrada por essa principal.
4. **VINCULO-32** IF o filtro de principal tiver o ID de uma transação de outro usuário ou inexistente THEN o sistema SHALL responder HTTP 400 com a mensagem "Transação inválida no filtro: <valor>."
5. **VINCULO-33** WHEN a exportação recebe o filtro de principal ou o filtro "com vínculo" THEN o sistema SHALL aplicá-lo com o mesmo significado da lista (AD-022), sem incluir o vínculo no arquivo.

**Independent Test**: clicar no custo total do cinema abre a lista com o cinema e o transporte; o filtro "com vínculo" traz só transações ligadas; exportar com o filtro do cinema gera as mesmas duas linhas, sem coluna de vínculo; o ID de uma transação de outro usuário recebe 400 "Transação inválida no filtro: <valor>."

---

### P1: Relatório de gastos puxados ⭐ MVP

**User Story**: Como usuário, quero ver quanto cada tipo de gasto puxa de outros gastos, para saber o custo real do que eu escolho fazer.

**Why P1**: mostra, por exemplo, que o lazer do mês custou também R$ 180,00 em transporte, o que ajuda a decidir o que cortar.

**Acceptance Criteria**:
1. **VINCULO-34** WHEN o usuário abre o relatório de gastos puxados de um período THEN o sistema SHALL devolver, para cada categoria raiz das principais, o total das dependentes em cada categoria raiz, com "Sem categoria" para as dependentes sem categoria.
2. **VINCULO-35** WHEN o relatório de gastos puxados é montado THEN o sistema SHALL colocar cada dependente no período pela data dela, com as mesmas regras de tipo e de período dos gráficos de despesa.
3. **VINCULO-36** WHEN a interface mostra o relatório de gastos puxados THEN a interface SHALL mostrar, para cada categoria das principais, o total puxado e a divisão por categoria, como "Lazer puxou R$ 180,00 de Transporte".
4. **VINCULO-37** WHEN o período não tem gastos vinculados THEN a interface SHALL mostrar a mensagem "Nenhum gasto vinculado no período."

**Independent Test**: com três passeios de cinema no mês, cada um com um transporte de R$ 60,00, o relatório mostra "Lazer puxou R$ 180,00 de Transporte"; um transporte do mês seguinte ligado a um cinema deste mês entra no mês seguinte; um mês sem vínculos mostra "Nenhum gasto vinculado no período."

---

## Edge Cases

- Principal com dez dependentes: o custo total soma todas (VINCULO-24).
- Dependente em outra conta ou num cartão: pode ser ligada normalmente (VINCULO-02).
- Dependente em outra data, como o transporte de volta no dia seguinte: pode ser ligada, e o relatório usa a data dela (VINCULO-35).
- Parcela 3 de 10 escolhida como dependente: a compra inteira é ligada (VINCULO-12).
- Série recorrente excluída com uma ocorrência principal: as dependentes perdem o vínculo e continuam existindo (VINCULO-14).
- Pedidos simultâneos para ligar A a B e B a A: só um passa (VINCULO-19).
- Dependente na mesma categoria da principal, como Lazer puxando Lazer: aparece no relatório na própria categoria (VINCULO-34).
- Valores do relatório: texto decimal com duas casas, como em todo relatório (CONTRATO-16).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | VINCULO-05, VINCULO-06, VINCULO-07, VINCULO-08, VINCULO-11, VINCULO-32 |
| Falha e falha parcial | VINCULO-18 |
| Idempotência, repetição e duplicidade | VINCULO-10 |
| Autorização e rate limiting | VINCULO-11, VINCULO-20, VINCULO-32 |
| Concorrência e ordem | VINCULO-19 |
| Ciclo de vida dos dados | VINCULO-14, VINCULO-15, VINCULO-22 |
| Observabilidade | VINCULO-23 |
| Falha de dependência externa | N/A because a feature não chama serviços externos |
| Integridade das transições de estado | VINCULO-09, VINCULO-16, VINCULO-21 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| VINCULO-01 | P1: Criar e desfazer vínculos | T3, T8 | Implemented |
| VINCULO-02 | P1: Criar e desfazer vínculos | T2, T8 | Implemented |
| VINCULO-03 | P1: Criar e desfazer vínculos | T8 | Implemented |
| VINCULO-04 | P1: Criar e desfazer vínculos | T1, T2, T8 | Implemented |
| VINCULO-05 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-06 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-07 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-08 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-09 | P1: Criar e desfazer vínculos | T1, T2 | Implemented |
| VINCULO-10 | P1: Criar e desfazer vínculos | T1, T2 | Implemented |
| VINCULO-11 | P1: Criar e desfazer vínculos | T2 | Implemented |
| VINCULO-12 | P1: Criar e desfazer vínculos | T1, T3 | Implemented |
| VINCULO-13 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-14 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-15 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-16 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-17 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-18 | P1: Criar e desfazer vínculos | T3 | Implemented |
| VINCULO-19 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-20 | P1: Criar e desfazer vínculos | T2, T3, T5, T6, T8 | Implemented |
| VINCULO-21 | P1: Criar e desfazer vínculos | T2, T8 | Implemented |
| VINCULO-22 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-23 | P1: Criar e desfazer vínculos | T1 | Implemented |
| VINCULO-24 | P1: Custo total na principal | T7 | Implemented |
| VINCULO-25 | P1: Custo total na principal | T7 | Implemented |
| VINCULO-26 | P1: Custo total na principal | T4 | Implemented |
| VINCULO-27 | P1: Custo total na principal | T4 | Implemented |
| VINCULO-28 | P1: Custo total na principal | T4 | Implemented |
| VINCULO-29 | P1: Filtro de vinculadas | T5 | Implemented |
| VINCULO-30 | P1: Filtro de vinculadas | T5, T9 | Implemented |
| VINCULO-31 | P1: Filtro de vinculadas | T7, T9 | Implemented |
| VINCULO-32 | P1: Filtro de vinculadas | T5 | Implemented |
| VINCULO-33 | P1: Filtro de vinculadas | T5, T9 | Implemented |
| VINCULO-34 | P1: Relatório de gastos puxados | T6 | Implemented |
| VINCULO-35 | P1: Relatório de gastos puxados | T6 | Implemented |
| VINCULO-36 | P1: Relatório de gastos puxados | T10 | Implemented |
| VINCULO-37 | P1: Relatório de gastos puxados | T10 | Implemented |

**Coverage:** 37 total, 37 mapped to tasks, 0 unmapped; 37 implemented, 0 in progress, 0 pending

---

## Success Criteria

- [ ] Ligar um gasto existente a uma principal leva no máximo três cliques a partir da transação.
- [ ] Em qualquer período, a soma por categoria é a mesma com e sem vínculos.
- [ ] Nenhum vínculo vira dois níveis ou ciclo, nem com pedidos simultâneos.
