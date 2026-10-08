# Metas Specification

## Problem Statement

O valor de cada meta é um número guardado à parte, que cada caminho atualiza do seu jeito. Excluir a transferência de um aporte devolve o dinheiro à conta, mas a meta continua com o valor (FIN-09). Um aporte a partir do próprio cofrinho infla a meta (FIN-20). O rateio automático do cofrinho compartilhado credita só um lado de uma transferência entre cofrinhos (FIN-37) e deixa centavos de diferença (FIN-38). O cofrinho de trocos deposita o mesmo troco várias vezes, sempre da conta da primeira transação (FE-10).

Origem: `docs/auditoria-2026-09.md`, seção 2 (FIN-09, FIN-19, FIN-20, FIN-37 e FIN-38), seção 5 (FE-10) e seção 6 (PERF-03).

## Goals

- [ ] O valor de cada meta é sempre a soma dos aportes menos os resgates dela.
- [ ] O dinheiro de um cofrinho compartilhado nunca some nem aparece em dobro entre as metas.
- [ ] Cada troco é depositado uma vez só, a partir da conta que pagou a despesa.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Datas e valores digitados nos formulários de meta (FE-03 e FE-06) | Spec `contratos-frontend-backend` (CONTRATO-19, CONTRATO-24 e CONTRATO-25) |
| Conta de outro usuário numa meta (SEG-01) | Spec `isolamento-entre-usuarios` |
| Imagem da meta no Cloudinary e `print` com valores de aporte e resgate | Spec `lgpd` |
| Projeção de quando a meta será atingida | Fica com a previsão de gastos (PROP-04) |
| Onde os cofrinhos entram nos totais de patrimônio e de liquidez | Feature `relatorios` |
| ID numérico das metas (MAN-04) | Higiene de modelagem; o acesso já é protegido pelo isolamento |
| Troco de compras no cartão | O dinheiro só sai da conta no pagamento da fatura |
| Comando `cleanup_db`, que apaga registros de metas (FIN-43) | Ferramenta de administração; entra com o painel admin |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Como o valor da meta é contado | Aportes menos resgates registrados para ela; várias metas podem usar o mesmo cofrinho, e o que entra ou sai por fora de aporte e resgate muda só o saldo livre | Decisão do usuário (AD-028) | sim |
| Cofrinho de trocos | Corrigido: troco de cada despesa até o próximo real, lembrado depois de depositado e depositado quando o usuário manda, a partir da conta de cada despesa | Decisão do usuário | sim |
| Trava de plano | Recurso `metas` do catálogo; com a trava, as transferências comuns de e para os cofrinhos continuam liberadas (PERM-22) | Spec `permissoes-e-planos` aprovada | sim |
| Uso do saldo livre | Aporte a partir do saldo livre e resgate para o saldo livre, sem transferência | Sem isso, o dinheiro que entra no cofrinho por fora nunca chega às metas | sim |
| Aviso de cofrinho descoberto | Enquanto o saldo livre estiver negativo, a tela de metas mostra quanto falta | O valor das metas não muda sozinho, então o usuário precisa saber | sim |
| Transação de aporte excluída ou alterada | A meta acompanha na mesma operação; se ficaria negativa, a operação é recusada | Corrige FIN-09 sem deixar meta negativa | sim |
| Aporte ou resgate com transferência pendente | Só conta enquanto a transferência estiver efetivada | É a mesma regra do saldo (AD-002) | sim |
| Correção dos valores já gravados | Recálculo de todas as metas na implantação; um valor negativo vira zero, com um registro de correção e um aviso único | Hoje há metas com valores que não existem (FIN-09) | sim |
| Limites do resgate | Até o valor da meta e, para outra conta, até o saldo do cofrinho | Um resgate não pode deixar o cofrinho negativo | sim |
| Meta arquivada | Não recebe aportes; o valor continua reservado e pode ser resgatado | Arquivar não pode fazer dinheiro sumir | sim |
| Meta concluída | Continua aceitando aportes | O usuário pode passar do alvo | sim |
| Troca de cofrinho e exclusão da meta | Só com a meta zerada | É a regra de hoje, na mesma linha da AD-003 | sim |
| Cofrinho vazio depois da última meta | A interface pergunta se exclui o cofrinho também | Evita cofrinhos vazios esquecidos na lista de contas | sim |
| Cofrinho de uma meta | Só contas do tipo cofrinho, ativas e do usuário; sem escolha, um cofrinho novo | É o que o formulário já oferece | sim |
| Lista e histórico | A lista vem completa e sem histórico; o histórico vem paginado no formato de CONTRATO-02 | Hoje cada meta traz todo o histórico, e a resposta cresce sem limite (PERF-03) | sim |
| Despesas que geram troco | Despesas efetivadas com conta, fora dos cofrinhos e dos ajustes de saldo, a partir da ativação | Compras no cartão só saem da conta no pagamento da fatura | sim |
| Arredondamento | Até o próximo real inteiro; valor inteiro não gera troco | É o arredondamento do recurso atual | sim |
| Depósito dos trocos | Um aporte por conta de origem, com a soma dos trocos dela | Cada troco sai da conta que pagou a despesa (FE-10) | sim |
| Despesa alterada depois do troco | O troco pendente é recalculado ou removido; o troco já depositado fica como está | O aporte já aconteceu | sim |
| Trocos de conta excluída | Descartados no depósito, com o aviso de quantos | Conta excluída não recebe movimentação nova (AD-003) | sim |
| Meta dos trocos arquivada ou excluída | Trocos pausados até o usuário escolher outra meta | Não há onde depositar | sim |
| Desativar os trocos | Para de contar trocos novos; os pendentes continuam disponíveis para depósito | O usuário não perde o que juntou | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Valor das metas e saldo livre do cofrinho ⭐ MVP

**User Story**: Como usuário, quero que o valor de cada meta seja sempre o que eu aportei menos o que resgatei, e ver quanto do cofrinho está livre.

**Why P1**: hoje a meta mostra dinheiro que não existe depois de uma exclusão (FIN-09), e o rateio do cofrinho compartilhado erra valores (FIN-37 e FIN-38).

**Acceptance Criteria**:
1. **META-01** WHEN o sistema calcula o valor de uma meta THEN o sistema SHALL somar os aportes e subtrair os resgates registrados para ela, contando os que têm a transferência efetivada e os que não têm transferência.
2. **META-02** WHEN o sistema calcula o saldo livre de um cofrinho THEN o sistema SHALL subtrair do saldo do cofrinho a soma dos valores de todas as metas dele, inclusive as arquivadas.
3. **META-03** WHEN entra ou sai dinheiro de um cofrinho por uma transação que não é aporte nem resgate THEN o sistema SHALL mudar só o saldo livre dele, sem mudar o valor de nenhuma meta.
4. **META-04** WHEN a interface mostra as metas THEN a interface SHALL agrupá-las por cofrinho, com o saldo do cofrinho, a soma das metas e o saldo livre.
5. **META-05** IF o saldo livre de um cofrinho ficar negativo THEN a interface SHALL mostrar o aviso "O cofrinho <nome> tem R$ <valor> a menos do que as metas somam." enquanto a diferença existir.
6. **META-06** WHEN a transferência de um aporte ou de um resgate é excluída THEN o sistema SHALL remover da meta o aporte ou o resgate na mesma operação.
7. **META-07** WHEN o valor ou a data da transferência de um aporte ou de um resgate muda THEN o sistema SHALL aplicar o mesmo valor e a mesma data ao registro da meta, na mesma operação.
8. **META-08** WHEN a transferência de um aporte deixa de ter o cofrinho da meta como destino, ou a de um resgate deixa de tê-lo como origem, THEN o sistema SHALL remover o registro da meta na mesma operação.
9. **META-09** IF a exclusão ou a mudança de uma transação deixar o valor de uma meta negativo THEN o sistema SHALL recusar com HTTP 400 e a mensagem "A meta <nome> ficaria negativa. Desfaça o resgate antes."
10. **META-10** WHEN as regras novas são implantadas THEN o sistema SHALL recalcular o valor de cada meta pela regra de META-01.
11. **META-11** IF o recálculo deixar uma meta com valor negativo THEN o sistema SHALL levá-la a zero com um registro de correção no histórico, e a interface SHALL mostrar uma vez o valor de antes e o de depois.

**Independent Test**: aportar R$ 500,00 na meta Viagem e excluir a transferência deixa a meta em R$ 0,00 na hora; uma transferência comum de R$ 200,00 para o cofrinho aumenta o saldo livre em R$ 200,00 e não muda nenhuma meta; pagar uma despesa de R$ 300,00 com um cofrinho de R$ 100,00 livres mostra o aviso de R$ 200,00 a menos.

---

### P1: Aportes e resgates ⭐ MVP

**User Story**: Como usuário, quero colocar e tirar dinheiro de uma meta, de outra conta ou do saldo livre do cofrinho, sem que o valor saia errado.

**Why P1**: é a operação do dia a dia das metas, e hoje o aporte a partir do próprio cofrinho infla a meta (FIN-20).

**Acceptance Criteria**:
1. **META-12** WHEN o usuário faz um aporte a partir de outra conta THEN o sistema SHALL criar uma transferência dessa conta para o cofrinho da meta, pelas regras da spec `saldo` (SALDO-11 a SALDO-17), e registrar o aporte só nessa meta.
2. **META-13** WHEN o usuário escolhe o saldo livre do cofrinho como origem do aporte THEN o sistema SHALL registrar o aporte na meta sem criar transferência.
3. **META-14** IF o aporte a partir do saldo livre passar do saldo livre do cofrinho THEN o sistema SHALL recusar com HTTP 400 e a mensagem "O saldo livre do cofrinho é de R$ <valor>."
4. **META-15** WHEN o usuário resgata para outra conta THEN o sistema SHALL criar uma transferência do cofrinho da meta para essa conta, pelas regras da spec `saldo`, e registrar o resgate na meta.
5. **META-16** WHEN o usuário resgata para o saldo livre do cofrinho THEN o sistema SHALL registrar o resgate na meta sem criar transferência.
6. **META-17** IF o resgate passar do valor da meta THEN o sistema SHALL recusar com HTTP 400 e a mensagem "A meta tem R$ <valor> para resgatar."
7. **META-18** IF o resgate para outra conta passar do saldo do cofrinho THEN o sistema SHALL recusar com HTTP 400 e a mensagem "O cofrinho tem só R$ <valor>."
8. **META-19** IF o valor de um aporte ou de um resgate for menor que R$ 0,01 THEN o sistema SHALL recusar com HTTP 400 e o erro no campo do valor.
9. **META-20** IF a conta de origem do aporte ou de destino do resgate for de outro usuário ou não existir THEN o sistema SHALL responder HTTP 400 com o erro no campo da conta e a mesma mensagem de um ID inexistente (AD-010).
10. **META-21** IF o usuário tentar fazer um aporte numa meta arquivada THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Metas arquivadas não recebem aportes."
11. **META-22** WHILE houver resgates simultâneos na mesma meta, o sistema SHALL manter o valor dela maior ou igual a zero.
12. **META-23** WHEN uma meta atinge o valor-alvo THEN o sistema SHALL marcá-la como concluída e continuar aceitando aportes.
13. **META-24** WHEN o sistema calcula quanto guardar por mês THEN o sistema SHALL dividir o que falta pelo número de meses até a data-alvo, contados a partir de hoje no fuso de Brasília (AD-008), com mínimo de 1 mês.

**Independent Test**: com R$ 200,00 livres no cofrinho, um aporte de R$ 150,00 a partir do saldo livre sobe a meta em R$ 150,00 sem nova transação; outro de R$ 100,00 recebe 400 "O saldo livre do cofrinho é de R$ 50,00."; dois resgates simultâneos de R$ 300,00 numa meta de R$ 500,00 deixam passar só um; escolher o próprio cofrinho como conta de origem é recusado pela SALDO-17.

---

### P1: Cadastro e consulta das metas ⭐ MVP

**User Story**: Como usuário, quero criar metas num cofrinho novo ou num que já tenho, e consultar o histórico sem a tela ficar lenta.

**Why P1**: o cofrinho compartilhado depende de escolher um cofrinho existente, e hoje cada meta da lista traz todo o histórico (PERF-03).

**Acceptance Criteria**:
1. **META-25** WHEN o usuário cria uma meta sem escolher cofrinho THEN o sistema SHALL criar um cofrinho novo para ela.
2. **META-26** WHEN o usuário cria uma meta num cofrinho que já existe THEN o sistema SHALL aceitar só contas do tipo cofrinho, ativas e dele.
3. **META-27** IF o nome da meta estiver vazio ou o valor-alvo for menor que R$ 0,01 THEN o sistema SHALL recusar com HTTP 400 e o erro no campo.
4. **META-28** IF o usuário tentar trocar o cofrinho de uma meta com valor maior que zero THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Resgate o valor da meta antes de trocar o cofrinho."
5. **META-29** IF o usuário tentar excluir uma meta com valor maior que zero THEN o sistema SHALL recusar com HTTP 400 e a mensagem "Resgate o valor da meta antes de excluí-la."
6. **META-30** WHEN o usuário exclui a última meta de um cofrinho com saldo zero THEN a interface SHALL perguntar se ele quer excluir o cofrinho também.
7. **META-31** WHEN a interface pede a lista de metas THEN o sistema SHALL devolvê-la completa, sem o histórico de aportes e resgates.
8. **META-32** WHEN a interface pede o histórico de uma meta THEN o sistema SHALL devolvê-lo paginado no formato de CONTRATO-02, do mais recente para o mais antigo, com o tipo, o valor, a data, a conta e a transação de cada registro.
9. **META-33** WHERE o recurso `metas` estiver travado no plano do usuário, o sistema SHALL tratar as metas como recurso travado, conforme PERM-15 e PERM-19, e manter liberadas as transferências comuns de e para os cofrinhos (PERM-22).
10. **META-34** WHEN a conta do usuário é apagada definitivamente THEN o sistema SHALL apagar as metas e os aportes e resgates registrados junto com os demais dados (AD-018).

**Independent Test**: criar duas metas no mesmo cofrinho mostra as duas no grupo dele; escolher uma conta corrente como cofrinho recebe 400; excluir uma meta com R$ 10,00 recebe 400 "Resgate o valor da meta antes de excluí-la."; a lista de metas não traz o histórico, e o histórico de uma meta com 45 registros vem em páginas de 20.

---

### P1: Cofrinho de trocos ⭐ MVP

**User Story**: Como usuário, quero juntar o troco das minhas despesas numa meta e depositar quando eu quiser, sem depositar o mesmo troco duas vezes.

**Why P1**: hoje o troco é recalculado a cada abertura da tela, pode ser depositado várias vezes e sai todo da conta da primeira transação (FE-10).

**Acceptance Criteria**:
1. **META-35** WHEN o usuário ativa os trocos THEN o sistema SHALL guardar a meta que vai recebê-los e contar só as despesas efetivadas depois da ativação.
2. **META-36** WHEN uma despesa com conta é efetivada com os trocos ativos THEN o sistema SHALL calcular o troco dela como a diferença até o próximo real inteiro, e zero quando o valor já for inteiro.
3. **META-37** WHEN o usuário abre os trocos THEN a interface SHALL mostrar o total pendente e quantas despesas ele junta.
4. **META-38** WHEN o usuário manda depositar os trocos THEN o sistema SHALL criar, para cada conta de origem, um aporte na meta dos trocos com a soma dos trocos pendentes das despesas dessa conta, e marcar cada troco como depositado.
5. **META-39** WHEN o pedido de depósito dos trocos chega de novo THEN o sistema SHALL depositar só os trocos ainda pendentes, sem repetir nenhum.
6. **META-40** WHILE houver pedidos simultâneos de depósito dos trocos, o sistema SHALL depositar cada troco uma vez só.
7. **META-41** WHEN uma despesa com troco pendente é editada ou excluída THEN o sistema SHALL recalcular ou remover o troco pendente dela.
8. **META-42** WHEN uma despesa com troco já depositado é editada ou excluída THEN o sistema SHALL manter o aporte dos trocos como está.
9. **META-43** IF a conta de origem de trocos pendentes estiver excluída na hora do depósito THEN o sistema SHALL descartar esses trocos, e a interface SHALL dizer quantos foram descartados.
10. **META-44** WHILE a meta dos trocos estiver arquivada ou tiver sido excluída, o sistema SHALL pausar os trocos até o usuário escolher outra meta.
11. **META-45** WHEN o usuário desativa os trocos THEN o sistema SHALL parar de contar trocos novos e manter os pendentes disponíveis para depósito.

**Independent Test**: com os trocos ativos, despesas de R$ 12,30 na conta A e de R$ 7,60 na conta B juntam R$ 1,10; depositar cria um aporte de R$ 0,70 a partir de A e outro de R$ 0,40 a partir de B; reenviar o pedido não deposita nada; uma despesa de R$ 12,00 não gera troco.

---

## Edge Cases

- Aporte com o próprio cofrinho como conta de origem: a transferência é recusada (SALDO-17); para usar o dinheiro do cofrinho, a origem é o saldo livre (META-13).
- Transferência comum entre dois cofrinhos: muda o saldo livre dos dois, sem mudar as metas (META-03).
- Mover dinheiro entre duas metas do mesmo cofrinho: resgate para o saldo livre e aporte a partir dele (META-16, META-13).
- Despesa paga com o dinheiro de um cofrinho: reduz o saldo livre e, se ele ficar negativo, a tela mostra o aviso (META-03, META-05).
- Meta com R$ 500,00 num cofrinho que tem R$ 300,00: o resgate para outra conta vai até R$ 300,00 (META-18).
- Divisão do salário com destino numa meta: é um aporte comum, e desfazer a divisão remove o aporte na mesma operação (META-06, SALARIO-46).
- Despesa de R$ 12,30 editada para R$ 12,80 antes do depósito: o troco pendente passa de R$ 0,70 para R$ 0,20 (META-41).
- Registros antigos do rateio automático: continuam no histórico e entram no recálculo (META-10).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | META-14, META-17, META-18, META-19, META-21, META-27 |
| Falha e falha parcial | META-06, META-07, META-08 |
| Idempotência, repetição e duplicidade | META-39 |
| Autorização e rate limiting | META-20, META-26, META-33 |
| Concorrência e ordem | META-22, META-40 |
| Ciclo de vida dos dados | META-10, META-11, META-29, META-34 |
| Observabilidade | N/A because os logs de metas seguem a AD-019, e os `print` com valores já estão na spec `lgpd` |
| Falha de dependência externa | N/A because a feature não chama serviços externos; a imagem no Cloudinary está na spec `lgpd` |
| Integridade das transições de estado | META-21, META-23, META-28, META-44 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| META-01 | P1: Valor das metas e saldo livre do cofrinho | T1 | Implemented |
| META-02 | P1: Valor das metas e saldo livre do cofrinho | T1, T5 | Implemented |
| META-03 | P1: Valor das metas e saldo livre do cofrinho | T2 | Implemented |
| META-04 | P1: Valor das metas e saldo livre do cofrinho | T5, T11 | Implemented |
| META-05 | P1: Valor das metas e saldo livre do cofrinho | T11 | Implemented |
| META-06 | P1: Valor das metas e saldo livre do cofrinho | T2 | Implemented |
| META-07 | P1: Valor das metas e saldo livre do cofrinho | T2 | Implemented |
| META-08 | P1: Valor das metas e saldo livre do cofrinho | T2 | Implemented |
| META-09 | P1: Valor das metas e saldo livre do cofrinho | T2 | Implemented |
| META-10 | P1: Valor das metas e saldo livre do cofrinho | T3 | Implemented |
| META-11 | P1: Valor das metas e saldo livre do cofrinho | T3 | In Progress |
| META-12 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-13 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-14 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-15 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-16 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-17 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-18 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-19 | P1: Aportes e resgates | T4 | Implemented |
| META-20 | P1: Aportes e resgates | T4 | Implemented |
| META-21 | P1: Aportes e resgates | T4, T12 | Implemented |
| META-22 | P1: Aportes e resgates | T4 | Implemented |
| META-23 | P1: Aportes e resgates | T5 | Implemented |
| META-24 | P1: Aportes e resgates | T5 | Implemented |
| META-25 | P1: Cadastro e consulta das metas | T6 | In Progress |
| META-26 | P1: Cadastro e consulta das metas | T6 | In Progress |
| META-27 | P1: Cadastro e consulta das metas | T6 | In Progress |
| META-28 | P1: Cadastro e consulta das metas | T6 | In Progress |
| META-29 | P1: Cadastro e consulta das metas | T6 | In Progress |
| META-30 | P1: Cadastro e consulta das metas | T6 | In Progress |
| META-31 | P1: Cadastro e consulta das metas | T6 | Implemented |
| META-32 | P1: Cadastro e consulta das metas | T7 | In Progress |
| META-33 | P1: Cadastro e consulta das metas | T7 | Implemented |
| META-34 | P1: Cadastro e consulta das metas | T7 | Implemented |
| META-35 | P1: Cofrinho de trocos | T8 | In Progress |
| META-36 | P1: Cofrinho de trocos | T9 | Implemented |
| META-37 | P1: Cofrinho de trocos | - | Pending |
| META-38 | P1: Cofrinho de trocos | T10 | Implemented |
| META-39 | P1: Cofrinho de trocos | T10 | Implemented |
| META-40 | P1: Cofrinho de trocos | T10 | Implemented |
| META-41 | P1: Cofrinho de trocos | T9 | Implemented |
| META-42 | P1: Cofrinho de trocos | T9 | Implemented |
| META-43 | P1: Cofrinho de trocos | T10 | In Progress |
| META-44 | P1: Cofrinho de trocos | T8 | In Progress |
| META-45 | P1: Cofrinho de trocos | T8 | In Progress |

**Coverage:** 45 total, 45 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Depois da implantação, o valor de toda meta é igual à soma dos aportes menos os resgates registrados.
- [ ] Excluir ou editar a transação de um aporte muda a meta na mesma hora, sem depender do comando `sync_goals`.
- [ ] Nenhum troco é depositado duas vezes.
