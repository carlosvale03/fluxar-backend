# Metas Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/metas/spec.md`
**Status:** Spec aprovada; design não iniciado

---

## Feature Boundary

O valor das metas e o saldo livre dos cofrinhos, aportes e resgates, o cadastro e o histórico das metas e o cofrinho de trocos. Formatos de data e valor nos formulários, isolamento e dados pessoais já estão nas specs `contratos-frontend-backend`, `isolamento-entre-usuarios` e `lgpd`.

---

## Implementation Decisions

### Como o valor da meta é contado

- Cofrinho compartilhado, e cada meta muda só por aporte e resgate. O que entra ou sai do cofrinho por outro caminho fica como saldo livre, e o app avisa quando o cofrinho tem menos do que as metas somam (AD-028).

### Cofrinho de trocos

- Corrigido: o app calcula o troco de cada despesa até o próximo real, lembra o que já foi depositado e, quando o usuário manda, deposita a partir da conta de cada despesa.

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Uso do saldo livre, aviso de cofrinho descoberto, transação de aporte alterada e transferência pendente.
- Correção dos valores já gravados e limites do resgate.
- Meta arquivada, meta concluída, troca de cofrinho, exclusão da meta e cofrinho vazio.
- Lista e histórico.
- Regras dos trocos: despesas que contam, arredondamento, depósito por conta, despesa alterada, conta excluída, meta dos trocos e desativação.

---

## Specific References

- `Goal` guarda `current_amount` como um número à parte (`goals/models.py:6-20`), e `GoalDeposit` registra aportes e resgates com um `transaction_id` solto, sem chave estrangeira (`goals/models.py:22-41`).
- O aporte e o resgate criam uma transferência e somam ou subtraem `current_amount` (`goals/services.py:11-135`); o resgate só confere o valor da meta, não o saldo do cofrinho (`:93-96`). O valor mostrado vem de `current_amount` (`goals/services.py:137-170`), e a sugestão mensal usa a data do servidor (`:158`).
- Toda transação nova numa conta-cofrinho é repartida entre as metas ativas dela, com arredondamento por meta e piso em zero nas saídas (`goals/signals.py:11-90`). Excluir uma transação apaga o `GoalDeposit` sem mexer em `current_amount` (`goals/signals.py:92-102`); o comando `sync_goals` reconstrói o valor à mão (`goals/management/commands/sync_goals.py:9-39`).
- A exclusão da meta é bloqueada com valor diferente de zero (`goals/views.py:19-27`). Aporte e resgate respondem 404 para uma conta de outro usuário e erros no formato `{'error': ...}` (`goals/views.py:33-89`), e o histórico vem sem paginação (`:91-96`).
- Cada meta da lista embute todo o histórico (`goals/serializers.py:21`, PERF-03), e uma meta sem conta ganha um cofrinho novo (`goals/serializers.py:87-104`).
- Na interface, o formulário da meta oferece um cofrinho novo ou um existente (`fluxar-frontend/src/components/goals/GoalForm.tsx:88-89` e `:162-166`), o de aporte lista inclusive o próprio cofrinho (`fluxar-frontend/src/components/goals/GoalDepositForm.tsx:89` e `:101-103`), e o texto de ajuda explica o rateio do cofrinho compartilhado (`fluxar-frontend/src/app/(app)/metas/page.tsx:156-172`).
- O cofrinho de trocos é calculado no navegador a partir das 20 últimas transações e deposita tudo da conta da primeira (`fluxar-frontend/src/components/goals/SpareChangeBank.tsx:46-113`).

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
