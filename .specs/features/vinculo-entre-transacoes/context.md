# Vínculo entre transações Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/vinculo-entre-transacoes/spec.md`
**Status:** Spec aprovada; design não iniciado

---

## Feature Boundary

O vínculo entre uma despesa principal e as despesas que só existiram por causa dela: criar, trocar e desfazer o vínculo, o custo total na principal, o filtro de vinculadas e o relatório de gastos puxados. O vínculo fica só no app, fora dos arquivos de exportação e importação.

---

## Implementation Decisions

### Modelo do vínculo

- Principal e dependentes, num nível só (AD-027).

### O que aparece no app

- O custo total na principal, o filtro de vinculadas e o relatório de quanto cada categoria puxa de outras.

### Como criar

- Das duas formas: lançando um gasto relacionado a partir da principal ou ligando depois uma transação existente.

### Exportação e importação

- O vínculo fica só no app (AD-027).

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Parcelas no custo total, filtro na exportação, troca de principal e despesa que vira receita.
- Agrupamento e lugar do relatório, busca da principal e trava de plano.

---

## Specific References

- `Transaction` não tem vínculo genérico. `parent_transaction` é a ligação das parcelas, com exclusão em cascata (`transactions/models.py:97`), e não pode ser reaproveitado; `transfer_id` junta as pontas de uma transferência (`:91`), `recurring_source` aponta para a série (`:100`) e `invoice`, para a fatura (`:72`).
- A compra parcelada nasce em `create_credit_card_expense`: a primeira parcela é a raiz, e as outras apontam para ela (`transactions/services.py:74-137`).
- O serializer de transações não expõe `parent_transaction` (`transactions/serializers.py:66-80`), e os filtros da lista ficam em `transactions/views.py:67-116`.
- As tags são uma ligação M2M simples (`transactions/models.py:38-50` e `:76`) e não dizem qual gasto puxou qual.
- Os gráficos de despesa agrupam pela categoria raiz, com os tipos `EXPENSE` e `CREDIT_CARD` (`reports/services.py:366-435`).

---

## Deferred Ideas

- Reembolso ou divisão de conta, com uma receita ligada à despesa que ela devolve.
- Sugestão automática de vínculo, como o transporte logo antes ou depois de um gasto de lazer (PROP-04).
