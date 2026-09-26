# Saldo Context

**Gathered:** 2026-09-25
**Spec:** `.specs/features/saldo/spec.md`
**Status:** Spec aprovada; design não iniciado

---

## Feature Boundary

Como o saldo de cada conta muda em toda operação que move dinheiro (transação, transferência, série recorrente, ajuste de saldo, pagamento e estorno de fatura) e como os totais do dashboard somam esses saldos. Fechamento, vencimento e parcelamento de fatura ficam na feature `faturas`; importação fica em `importacao`.

---

## Implementation Decisions

### Quando uma ocorrência recorrente conta no saldo

- Só quando o usuário a efetiva (AD-002). Toda ocorrência gerada nasce pendente, inclusive as receitas.
- A tela de transações já tem a ação de efetivar: `fluxar-frontend/src/app/(app)/transacoes/page.tsx:263` envia `PATCH` com `status: "COMPLETED"`. O botão aparece só para transações pendentes que pertencem a uma série (`fluxar-frontend/src/app/(app)/transacoes/page.tsx:929`).

### Contas excluídas nos totais

- Uma conta excluída não entra em nenhum total de saldo (AD-003).
- A exclusão exige saldo zero, como já acontece na exclusão de metas (`goals/views.py:22`).

### Agent's Discretion

Em 2026-09-25 o usuário delegou ao agente as demais áreas cinzentas ("Confio em você"). As escolhas estão na tabela Assumptions & Open Questions da spec, todas marcadas como confirmadas:

- Demais restrições da conta excluída: sem transações pendentes para excluir, sem movimentação nova e histórico somente para leitura.
- Tipos que o endpoint genérico cria: só receita e despesa (AD-005).
- Status da primeira ocorrência de uma série.
- Transação efetivada com data futura, fora de série.
- Editar "todas" e excluir uma série.
- Comando de limpeza do banco preservando histórico e saldos.
- Correção dos dados já gravados em produção.
- Contas já excluídas com saldo diferente de zero.
- Forma do ajuste de saldo.
- Data de "hoje" no fuso de Brasília.
- Status das pernas de uma transferência.

### Declined / Undiscussed Gray Areas → Assumptions

Nenhuma: as áreas não discutidas foram delegadas e estão em Agent's Discretion.

---

## Specific References

- O card "Saldo em Contas" (`fluxar-frontend/src/components/dashboard/DashboardKPIs.tsx:80`) usa `total_liquid_balance`, que já soma só contas ativas dos tipos corrente, poupança e carteira (`reports/services.py:234-240`).
- `total_balance` e `net_worth` somam todas as contas, inclusive as excluídas (`reports/services.py:69-71` e `:165`), assim como as estatísticas do painel admin (`reports/services.py:1083-1084`).
- O ajuste de saldo atual calcula a diferença em ponto flutuante no navegador (`fluxar-frontend/src/components/accounts/balance-adjustment-dialog.tsx:78-97`) e procura uma categoria chamada "Reajuste", que o backend não cria.
- O pagamento de fatura só processa compras pendentes (`accounts/services.py:130-133`); uma compra efetivada antes, fora da fatura, já debitou a conta por conta própria (SALDO-46).
- A tela de pagamento de fatura cria um `INVOICE_PAYMENT` pelo endpoint genérico quando nenhuma fatura é escolhida (`fluxar-frontend/src/components/transactions/invoice-payment-dialog.tsx:196-200`); SALDO-18 passa a recusar esse caminho.
- O `cleanup_db` apaga contas excluídas em cascata (`accounts/management/commands/cleanup_db.py:23-27`), o que SALDO-47 proíbe quando isso muda histórico ou saldo.
- Já existem comandos que servem de ponto de partida para SALDO-38 e SALDO-39: `accounts/management/commands/init_balances.py` recalcula o saldo das contas ativas e `accounts/management/commands/audit_accounts.py` lista as contas, mas não compara saldos.

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
