# Permissoes e planos Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/permissoes-e-planos/spec.md`
**Status:** Spec aprovada; design não iniciado

---

## Feature Boundary

Quem é administrador e o que só administrador pode fazer; como cada tela e cada funcionalidade passa pelas travas dos planos Comum, Premium e Premium Plus; e a liberação do premium para todos durante os testes, a partir de um único ponto, nos dois repositórios. Gateway de pagamento e cobrança ficam de fora.

---

## Implementation Decisions

### Campo que define o administrador

- O papel `role = ADMIN` (AD-016). O `is_staff` fica só para o admin do Django.

### O que cada plano libera

- O usuário decidiu não definir agora o que cada plano libera: as travas são configuradas pelo administrador no painel, e não pelo código (AD-017).
- A spec define o catálogo de travas, com a tela, a funcionalidade e as rotas que cada trava cobre, e a lista de recursos essenciais, que nunca travam.

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Catálogo de travas e recursos essenciais.
- Configuração inicial e lugar da liberação para testes.
- Forma do bloqueio na interface e resposta da API.
- Descida de plano, dinheiro em recursos travados e plano do administrador.
- Estado usado nas permissões, admin do Django e comando do primeiro admin.
- Divergências atuais entre `role` e `is_staff`.
- Página de planos, tempo para a mudança valer e cofrinho fora do limite de contas.

---

## Specific References

Onde o plano é checado hoje:

| Onde | O que faz hoje |
| ---- | -------------- |
| `core/permissions.py:20-28` | `IsPremiumPlus` retorna sempre verdadeiro; protege as metas (`goals/views.py:17`) |
| `reports/permissions.py:4-13` | `IsPremium` retorna sempre verdadeiro; protege relatórios avançados, monitor de foco e exportações (`reports/views.py:49` e `:89`; `data_exchange/views.py:108` e `:155`) |
| `core/services/plan_limits.py:6-53` | Limites de 999 contas e cartões em todos os planos, gráficos avançados liberados e `print` do e-mail do usuário |
| `transactions/services.py:178-215` | Limite de categorias para um plano `FREE` que não existe, então nunca vale |
| `fluxar-frontend/src/hooks/use-plan.ts:7-12` | Fixa o plano em Premium Plus |
| `fluxar-frontend/src/app/(app)/relatorios/page.tsx:55` e `:313` | `isPremium = true` próprio e bloqueio desativado |
| `fluxar-frontend/src/app/(app)/importar/page.tsx:70` e `:281-293` | Usa o plano real e bloqueia a exportação para o Comum |
| `fluxar-frontend/src/app/(app)/cartoes/page.tsx:37-59` e `contas/page.tsx:69-75` | Limites só na tela: 1, 3 e 10 cartões; 2, 5 e 20 contas |
| `fluxar-frontend/src/app/(app)/metas/page.tsx:58-127` | Bloqueia metas e o cofrinho de arredondamento pelo Premium Plus |

Onde o administrador é checado hoje:

- Frontend pelo `role`: `fluxar-frontend/src/components/auth/admin-guard.tsx:16` e `:30`, e os links em `fluxar-frontend/src/components/layout/header.tsx:205`, `:263` e `:363`.
- Backend pelo `is_staff` (`permissions.IsAdminUser`) em todas as views de administração de `api/views.py:276-679`.
- A proteção do último admin conta pelo `role` (`api/views.py:325-329`, `:409-420` e `:453-456`).
- O painel edita `plan`, `role` e `is_active`, mas não o `is_staff` (`api/serializers.py:115-121`).
- O `create_admin.py` repromove o usuário configurado a cada boot (`create_admin.py:39-57`), e o token leva `plan` e `role` como claims (`api/serializers.py:157-160`).

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
