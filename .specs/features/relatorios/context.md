# Relatórios Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/relatorios/spec.md`
**Status:** Spec aprovada; implementada e verificada em 2026-10-08 (validation.md: PASS)

---

## Feature Boundary

As regras comuns a todos os relatórios e ao dashboard: quais transações entram, fuso, cálculo em decimal, patrimônio, liquidez e reservas, score e dinheiro guardado, e os erros da tela de relatórios e da exportação em PDF. Formato dos valores, filtros, divisão por classe, gastos puxados e travas por plano ficam nas specs que já tratam deles.

---

## Implementation Decisions

### Despesas nos relatórios

- Despesas efetivadas na data delas e compras no cartão na data da compra, mesmo com a fatura aberta; as pendentes aparecem à parte, como "A pagar" (AD-029).

### Patrimônio

- Saldos das contas menos as faturas em aberto (AD-029).

### Cofrinhos

- Entram no patrimônio como reservas e ficam fora do dinheiro disponível (AD-029).

### Dinheiro guardado no mês

- Aportes em metas e transferências para investimentos, descontados os resgates e as retiradas (AD-029).

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Compras parceladas e gasto dos orçamentos.
- Como medir o dinheiro guardado, receitas, ajustes de saldo e contas excluídas.
- Taxa de poupança sem receita, score de orçamentos e histórico do patrimônio.
- Parâmetro `months`, comparação com média zero, falha de um bloco, PDF sem conta e faturas do mês.

---

## Specific References

Funções de `reports/services.py`:

| Função | Linhas | O que corrigir |
| ------ | ------ | -------------- |
| `get_dashboard_summary` | 61-180 | Faturas do mês, "A pagar" e patrimônio |
| `get_financial_health_metrics` | 215-309 | Liquidez sem cofrinhos (`:237-238`), poupança só com investimentos (`:248-267`) e score de orçamentos (`:293-301`, FIN-26) |
| `get_calendar_data` | 312-363 | Despesas e compras no cartão pela REL-01 |
| `get_simple_charts` | 366-435 | Despesas pendentes somadas (`:373-376`) |
| `get_advanced_charts` | 438-987 | Patrimônio (`:461-464`, FIN-33), mapa de calor em UTC (`:485`, FIN-34), investimentos de 30 em 30 dias (`:519-525`, FIN-32), dia 28 fixo no próximo grande gasto (`:734`) e conta em ponto flutuante (`:768`, FIN-44) |
| `get_monthly_comparison` e `get_tag_insights` | 990-1069 e 1129-1218 | `months` sem limite (`reports/views.py:57` e `:66`, PERF-05) |

- O gasto dos orçamentos conta as compras no cartão pelo mês da fatura e soma as despesas pendentes (`budgets/services.py:31-39`).
- A exportação em PDF lê `tx.account.name` sem conferir se a conta existe (`data_exchange/services.py:479`, FIN-24).
- Na tela, a média zero vira "Infinity%" (`fluxar-frontend/src/app/(app)/relatorios/page.tsx:736`), e as promessas rejeitadas não são tratadas (`:454-455` e `:481-482`).

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
