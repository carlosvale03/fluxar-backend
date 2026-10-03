# Faturas Context

**Gathered:** 2026-09-25
**Spec:** `.specs/features/faturas/spec.md`
**Status:** Spec aprovada; design e tasks aprovados em 2026-10-02

---

## Feature Boundary

O ciclo da fatura do cartão: fechamento e vencimento, em qual fatura cai cada compra e cada parcela, pagamento total e parcial (o restante vai para a fatura seguinte) e estorno do pagamento. O efeito do pagamento e do estorno no saldo da conta fica na spec `saldo`.

---

## Implementation Decisions

### Dia de fechamento ou de vencimento que não existe no mês

- Vale o último dia do mês, sem acumular o ajuste nos meses seguintes (AD-006).
- A criação de fatura já faz isso (`transactions/services.py:139-157`); o cálculo que quebra é o de `CreditCardService.calculate_due_date` (`accounts/services.py:112-113`), e o ajuste precisa valer também para a comparação do melhor dia de compra (`accounts/services.py:97`).

### Mesmo pagamento enviado duas vezes

- Pagamento idempotente por identificador da tentativa (AD-007). A repetição recebe a mesma resposta de sucesso, sem cobrar de novo.
- A SALDO-26 foi ajustada para deixar a repetição da mesma tentativa com FATURA-30.
- O botão do diálogo de pagamento já fica desabilitado durante o envio (`fluxar-frontend/src/components/transactions/invoice-payment-dialog.tsx:610`), mas isso não cobre timeout nem duas abas.

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-25.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Melhor dia de compra comparado com o fechamento ajustado.
- Divisão do valor em parcelas.
- Data real da compra e compras antigas.
- Compra em fatura paga e exclusão de parcela.
- Compra que cairia numa fatura já paga.
- Pagamento maior que o total.
- Estorno quando a fatura seguinte já foi paga.
- Mudança dos dias do cartão.
- Status aberta e fechada derivado da data.
- Pedido sem identificador e identificador reenviado depois de um estorno.
- Limite disponível com uma única fórmula.
- Redistribuição das parcelas mal alocadas já gravadas.

---

## Specific References

- O pagamento processa as compras pendentes em ordem de data e valor, divide a compra em que o dinheiro acaba em "(Parcial)" e "(Restante)" e move o resto para a fatura seguinte (`accounts/services.py:130-224`).
- O estorno só volta as compras pagas para pendentes com `QuerySet.update()` e reabre a fatura (`accounts/services.py:226-244`); não desfaz a divisão nem traz de volta o que foi movido.
- A compra no cartão grava o vencimento no campo `date` (`transactions/services.py:118`), e a edição pela tela usa `PUT /transactions/{id}/` sem alterar a fatura (`fluxar-frontend/src/components/transactions/card-expense-form-dialog.tsx:188`).
- O limite disponível usa limite menos compras pendentes na tela do cartão (`accounts/services.py:50-56`) e limite menos faturas não pagas no dashboard (`reports/services.py:137`).
- O estorno é chamado pelo botão "Estornar" da lista de faturas (`fluxar-frontend/src/components/cards/invoice-list.tsx:191`, `fluxar-frontend/src/app/(app)/cartoes/[id]/page.tsx:91`).

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
