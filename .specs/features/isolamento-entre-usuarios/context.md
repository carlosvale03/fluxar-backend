# Isolamento entre usuarios Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/isolamento-entre-usuarios/spec.md`
**Status:** Spec aprovada; implementada e verificada em 2026-09-27 (validation.md: PASS na 4ª rodada)

---

## Feature Boundary

Nenhum usuário lê, cria ou altera dados de outro enviando IDs, no corpo ou no endereço da requisição, e nenhuma soma ou lista segue uma relação para dados de outro usuário. Painel admin, rate limiting e sessão ficam fora.

---

## Implementation Decisions

### Status da resposta para ID de outro usuário

- No corpo da requisição: HTTP 400, com o erro no campo da relação e a mesma mensagem de um ID inexistente (AD-010).
- No endereço: HTTP 404, como hoje.
- Muda o comportamento atual de duas views que respondem 404 para um ID do corpo, com `get_object_or_404`: aporte e resgate de meta (`goals/views.py:48` e `:78`) e importação (`data_exchange/views.py:27` e `:90`).

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Resposta idêntica para ID de outro usuário e ID inexistente.
- 404 para ID de outro usuário no endereço.
- Resultado vazio para filtros com ID de outro usuário.
- Categorias-modelo sem dono fora de qualquer relação.
- Correção das ligações cruzadas já gravadas.
- Mensagens de erro em português.

---

## Specific References

Inventário das relações graváveis e de como cada uma está hoje:

| Relação | Onde | Hoje |
| ------- | ---- | ---- |
| Conta, cartão, categoria e tags da transação | `transactions/serializers.py:64-80` | Aceita qualquer usuário (campos automáticos do `ModelSerializer`) |
| Categoria na edição em lote de série | `transactions/views.py:192` e `:197` | Aceita qualquer usuário (`QuerySet.update()` com o valor cru) |
| Categoria-pai | `transactions/serializers.py:14` | Aceita qualquer usuário |
| Categoria do orçamento | `budgets/serializers.py:16` | Aceita qualquer usuário |
| Conta da meta | `goals/serializers.py:32` | Aceita qualquer usuário |
| Categoria e tag do monitor de foco | `reports/serializers.py:11` | Aceita qualquer usuário |
| Conta de pagamento do cartão | `accounts/serializers.py:54-78` | Filtrada pelo usuário |
| Cartão, categoria e tags da compra no cartão | `transactions/serializers.py:264-279` | Filtrada pelo usuário |
| Origem e destino da transferência | `transactions/serializers.py:248-261` | Filtrada pelo usuário |
| Conta do pagamento de fatura | `accounts/serializers.py:35-45` | Filtrada pelo usuário |
| Conta do aporte e do resgate de meta | `goals/views.py:48` e `:78` | Filtrada pelo usuário, com 404 |
| Conta e mapeamento de contas da importação | `data_exchange/views.py:27` e `:90`; `data_exchange/services.py:261` e `:271` | Filtrada pelo usuário, com 404 |
| Orçamentos de origem da importação em lote | `budgets/views.py:75-78` | Filtrada pelo usuário |
| Série e transferência na exclusão e edição em lote | `transactions/views.py:165-176` e `:194-197` | Filtrada pelo usuário |

Somas e listas que seguem a relação sem conferir o dono (ISOL-14):

- Subcategorias na árvore de categorias: `transactions/serializers.py:17-20`.
- Metas que recebem os movimentos de um cofrinho: `goals/signals.py:37`.
- Transações de uma conta no saldo: `accounts/services.py:21-33`.
- Compras de um cartão no limite: `accounts/services.py:50-54`.
- Parceira de uma transferência: `transactions/serializers.py:121` e `:210`.

Outros pontos:

- `Category.user` aceita nulo (`transactions/models.py:12`), e o `populate_templates` cria categorias-modelo sem dono (`transactions/management/commands/populate_templates.py:34`).
- Todos os viewsets filtram o `queryset` pelo dono, por isso o 404 no endereço já funciona (`core/mixins.py:6-13`, `accounts/views.py:72`, `reports/views.py:92-93`).
- O orçamento soma só transações do dono (`budgets/services.py:36-39`), então hoje não vaza gasto de outro usuário.

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
