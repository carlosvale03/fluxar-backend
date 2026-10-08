# Permissoes e planos Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/permissoes-e-planos/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Permissões, travas, limites, painel e `/auth/me` (backend) | integration | Cada AC com status, código e mensagem exatos; uma verificação por chave do catálogo, com a trava fechada e aberta | `tests/permissoes/test_*.py` | `docker compose exec -T backend python manage.py test tests.permissoes --noinput` |
| Hook, componentes, painel e telas (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada; uma verificação por chave do catálogo nas telas | `fluxar-frontend/tests/permissoes/*.test.tsx` | `npx vitest run tests/permissoes` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 171 erros de lint antigos (MAN-04 e as regras novas do react-hooks): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.permissoes --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/permissoes` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Administrador

```
T1 → T2
T2 → T3
```

### Phase 2: Travas no backend

```
T4 → T5
T5 → T6
T6 → T7
T7 → T8
```

### Phase 3: Base do frontend

```
T9 → T10
T10 → T11
```

### Phase 4: Travas nas telas

```
T12 → T13
T13 → T14
T14 → T15
```

---

## Task Breakdown

### Phase 1: Administrador

#### T1: Administrador pelo papel

**What**: `EhAdministrador` em `core/permissions.py`, pelo `role` atual no banco e conta ativa, no lugar de `IsAdminUser` em todas as views de administração.
**Where**: `core/permissions.py`, `api/views.py`
**Depends on**: None
**Reuses**: `SessaoJWTAuthentication` (usuário lido do banco)
**Requirement**: PERM-01, PERM-02, PERM-04, PERM-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Usuário com `is_staff` e sem o papel `ADMIN` recebe 403 em cada função de administração da PERM-02
- [x] Usuário `ADMIN` sem `is_staff` acessa todas elas
- [x] Promovido no banco, o mesmo token passa a acessar na requisição seguinte; rebaixado, perde o acesso na seguinte
- [x] `ADMIN` sem `is_staff` não entra no `/admin/` do Django
- [x] Full gate passa
- [x] Test count: 8 testes (mínimo 6)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix(api): reconhece o administrador só pelo papel atual`

---

#### T2: Último administrador e a própria conta

**What**: `garantir_admin_restante` nas mudanças de papel, arquivamento e exclusão, com a mensagem da PERM-05, e a recusa de ações do admin sobre a própria conta.
**Where**: `api/views.py`
**Depends on**: T1
**Reuses**: as proteções atuais do último admin
**Requirement**: PERM-05, PERM-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Rebaixar, arquivar ou excluir o último admin ativo recebe 400 com "O sistema precisa ter pelo menos um administrador ativo."
- [x] Com dois admins ativos, rebaixar um é aceito
- [x] Admin tirando o próprio papel, arquivando ou excluindo a própria conta recebe 400
- [x] Quick gate passa
- [x] Test count: 6 testes (mínimo 6)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix(api): impede ficar sem administrador e mexer na própria conta pelo painel`

---

#### T3: Primeiro administrador e divergências

**What**: `create_admin.py` só cria um admin quando não existe nenhum ativo e não altera contas; comando `divergencias_de_admin` lista `role` e `is_staff` divergentes; `DEPLOY.md` registra o comando.
**Where**: `create_admin.py`, `api/management/commands/divergencias_de_admin.py` (novo), `DEPLOY.md`
**Depends on**: T2
**Reuses**: NONE
**Requirement**: PERM-07, PERM-29

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com um admin ativo, o script não cria nem promove ninguém, nem o e-mail configurado
- [x] Sem admin ativo, o script cria o admin configurado
- [x] O comando lista quem tem `is_staff` sem o papel e quem tem o papel sem `is_staff`, termina com "Contas divergentes: N" e não altera nenhuma conta
- [x] Build gate passa
- [x] Test count: 5 testes (mínimo 4)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix(api): cria o primeiro admin sem repromover e lista divergências de papel`

---

### Phase 2: Travas no backend

#### T4: Catálogo, configuração e acesso

**What**: `core/travas.py` com `PLANOS`, `CATALOGO` (18 recursos e 6 limites, com nome, descrição e contagem de uso), cache de 30 s e `acesso(usuario)`; modelo `TravaDePlano` e migração que grava `testing_unlock = 'true'`.
**Where**: `core/travas.py` (novo), `api/models.py`, `api/migrations/`
**Depends on**: None
**Reuses**: o padrão de `core/manutencao.py`
**Requirement**: PERM-09, PERM-14, PERM-23, PERM-28

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Sem nenhuma linha, todo recurso está liberado e todo limite sem limite nos três planos, e `testing_unlock` está ligada depois da migração
- [x] Admin tem tudo liberado e sem limite mesmo com tudo travado no plano dele
- [x] Com a liberação ligada, um Comum com tudo travado tem tudo liberado, e o plano gravado não muda
- [x] Nenhuma chave essencial (cadastro, contas, transações, transferências, categorias, dashboard simples) existe no catálogo
- [x] A contagem de `limite_contas` ignora o cofrinho de uma meta
- [x] Mudanças no banco aparecem em até 30 s, ou na hora depois de `invalidar()`
- [x] Quick gate passa
- [x] Test count: 15 testes (mínimo 8)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(planos): cria o catálogo de travas e a decisão de acesso por usuário`

---

#### T5: Configuração das travas no painel

**What**: `GET` e `PATCH /api/admin/plans/` com validação, gravação, log de cada mudança e `invalidar()`; `testing_unlock` deixa de mudar pela rota genérica de configurações.
**Where**: `api/views.py`, `api/serializers.py`, `api/urls.py`
**Depends on**: T4
**Reuses**: `SystemLog`, `EhAdministrador`
**Requirement**: PERM-10, PERM-11, PERM-12, PERM-13, PERM-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `GET` devolve as 24 travas com os valores dos três planos e `testing_unlock`
- [x] Desligar `exportacao_pdf` no Comum e pôr `limite_contas` = 2 no Comum grava e vale na requisição seguinte
- [x] Limite -1, 2.5 ou "abc" recebe 400 em `limit`; chave fora do catálogo recebe 400
- [x] Cada mudança grava no log quem, quando, a trava, o plano e os valores antigo e novo; gravar o mesmo valor não gera log
- [x] Ligar e desligar a liberação grava no log e vale na requisição seguinte
- [x] Não admin recebe 403
- [x] Quick gate passa
- [x] Test count: 12 testes (mínimo 8)

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat(planos): permite ao admin configurar as travas e a liberação para testes`

---

#### T6: Travas de recurso nas rotas

**What**: `PlanoBloqueado` e `RecursoLiberado`; cada rota do catálogo passa a exigir a trava; `IsPremium` e `IsPremiumPlus` saem; leitura de cartões e faturas, `pay` e `unpay` seguem liberados.
**Where**: `core/travas.py`, `core/exceptions.py`, views de `reports`, `budgets`, `goals`, `accounts`, `transactions` e `data_exchange`
**Depends on**: T5
**Reuses**: `acesso`
**Requirement**: PERM-15, PERM-22, PERM-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Para cada uma das 16 chaves de recurso com rota, com a liberação desligada e a trava fechada no Comum, a rota responde 403 `{code: "plan_locked", feature: <chave>}`; com a trava aberta, responde normalmente
- [x] `compras_parceladas` fechada recusa só `installments > 1`; `transacoes_recorrentes` fechada recusa `is_recurring`, `bulk-update` e `bulk-delete` por série, mas não por `transfer_id`; `tags` fechada recusa transação com tags
- [x] Com `metas` fechada, o cofrinho continua recebendo transferências e ajuste de saldo
- [x] Com `cartoes` fechada, ler cartões e faturas, pagar e estornar continuam funcionando, e criar cartão ou compra no cartão recebe 403
- [x] Com a liberação ligada, nenhuma rota do catálogo é travada
- [x] Full gate passa
- [x] Test count: 27 testes (mínimo 24)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat(planos): aplica as travas de recurso em cada rota do catálogo`

---

#### T7: Limites dos planos

**What**: `LimiteDoPlano` e `conferir_limite` na criação de contas, cartões, categorias, subcategorias, tags e metas; `PlanLimitsService` e `CategoryService.check_limits` saem.
**Where**: `core/travas.py`, `accounts/serializers.py`, `transactions/services.py`, `transactions/views.py`, `goals/views.py`, `core/services/plan_limits.py`
**Depends on**: T6
**Reuses**: `acesso`
**Requirement**: PERM-16, PERM-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com `limite_contas` = 2 e 5 contas, as 5 continuam e criar a sexta recebe 403 `{code: "plan_limit_reached", feature: "limite_contas", limit: 2}`
- [x] Cada um dos 6 limites recusa a criação no limite e aceita abaixo dele
- [x] `limite_subcategorias` conta por categoria-pai
- [x] Criar uma meta com cofrinho não conta no limite de contas
- [x] Fechar uma trava ou baixar o plano não apaga nem altera nenhum dado
- [x] Full gate passa
- [x] Test count: 9 testes (mínimo 9)

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `feat(planos): aplica os limites de cada plano na criação de itens`

---

#### T8: Acesso no /auth/me e planos públicos

**What**: `access` no `/auth/me` (admin, liberação, plano, recursos e limites com uso) e `GET /api/plans/` com o catálogo e os valores dos três planos.
**Where**: `api/serializers.py`, `api/views.py`, `api/urls.py`
**Depends on**: T7
**Reuses**: `acesso`, `CATALOGO`
**Requirement**: PERM-17, PERM-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `/auth/me` de um Comum com `limite_contas` = 2 e 1 conta traz `limits.limite_contas` = `{limit: 2, used: 1}` e `features` com cada chave
- [x] Com a liberação ligada, `access.testing_unlock` é verdadeiro, tudo vem liberado e `plan` é o plano real
- [x] `/api/plans/` devolve as 24 travas com nome, descrição e os valores dos três planos, e o plano do usuário
- [x] Build gate passa
- [x] Test count: 7 testes (mínimo 5)

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `feat(planos): informa o acesso do usuário e o que cada plano libera`

---

### Phase 3: Base do frontend

#### T9: Plano a partir da API

**What**: `usePlan` lê `user.access`; componentes `RecursoBloqueado` e `AvisoDeLimite`; `tratarErro` trata `plan_locked` e `plan_limit_reached` com aviso e link e relê o `/auth/me`, que também é relido quando a aba volta ao foco.
**Where**: `src/hooks/use-plan.ts`, `src/components/planos/` (novos), `src/lib/erros.ts`, `src/contexts/auth-context.tsx`, `src/types/`
**Depends on**: None
**Reuses**: `tratarErro`
**Requirement**: PERM-18, PERM-19, PERM-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `usePlan().podeUsar("metas")` segue `access.features.metas`; nenhum plano fixo em `use-plan.ts`
- [ ] `RecursoBloqueado` mostra o aviso e o link para `/planos` sem renderizar o conteúdo
- [ ] `AvisoDeLimite` mostra "uso de limite" e desabilita a criação no limite
- [ ] Um 403 `plan_locked` mostra o aviso com link e relê o `/auth/me`
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 6 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat(frontend): decide o que mostrar pelo acesso que a API informa`

---

#### T10: Painel do administrador

**What**: Seção "Planos e travas" nas configurações do admin: chave da liberação para testes junto da manutenção e tabela do catálogo com interruptores e limites por plano; testes do guard e dos links por papel.
**Where**: `src/app/(admin)/admin/configuracoes/page.tsx`, `src/services/admin.ts`, `src/components/auth/admin-guard.tsx`, `src/components/layout/header.tsx`
**Depends on**: T9
**Reuses**: `tratarErro`
**Requirement**: PERM-03, PERM-10, PERM-11, PERM-12, PERM-13, PERM-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A tabela mostra as 24 travas com os valores dos três planos
- [ ] Desligar um recurso ou mudar um limite envia o `PATCH` certo; limite inválido mostra o erro no campo
- [ ] A chave da liberação para testes envia `{testing_unlock}`
- [ ] Usuário sem o papel não vê os links do painel e é levado ao dashboard ao abrir uma página do painel
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 6 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat(frontend): configura as travas e a liberação para testes no painel`

---

#### T11: Perfil e página de planos

**What**: Perfil com o plano real e o aviso da liberação para testes; página `/planos` com recursos e limites de cada plano e o plano do usuário em destaque; "Seja Premium Agora" leva a ela.
**Where**: `src/app/(app)/perfil/page.tsx`, `src/app/(app)/planos/page.tsx` (nova), `src/components/layout/header.tsx`
**Depends on**: T10
**Reuses**: `usePlan`
**Requirement**: PERM-25, PERM-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Com a liberação ligada, o perfil de um Comum mostra "Plano Comum" e "Todos os recursos estão liberados durante a fase de testes."
- [ ] A página de planos mostra cada trava com o valor dos três planos, vindos de `/api/plans/`, e destaca o plano do usuário
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `feat(frontend): mostra o plano no perfil e o que cada plano libera`

---

### Phase 4: Travas nas telas

#### T12: Relatórios, dashboard, calendário e monitor

**What**: `relatorios_avancados`, `comparacao_mensal`, `analise_por_tag`, `monitor_de_foco`, `calendario` e `personalizar_dashboard` nas telas, sem chamar as rotas travadas; o `isPremium` próprio dos relatórios sai.
**Where**: `src/app/(app)/relatorios/page.tsx`, `src/app/(app)/dashboard/page.tsx`, `src/app/(app)/calendario/page.tsx` e componentes dos gráficos
**Depends on**: None
**Reuses**: `RecursoBloqueado`
**Requirement**: PERM-19, PERM-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Para cada uma das 6 chaves fechada, a tela mostra o aviso e nenhuma chamada à rota travada é feita
- [ ] Com cada chave aberta, a tela carrega normalmente
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 8 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat(frontend): aplica as travas de relatórios, dashboard e calendário`

---

#### T13: Orçamentos, metas, tags, cartões, parcelado e recorrente

**What**: `orcamentos`, `metas`, `tags` (tela e campo), `cartoes` (aviso com as faturas em aberto e o pagamento), `compras_parceladas` e `transacoes_recorrentes` nas telas e formulários.
**Where**: telas de orçamentos, metas, tags e cartões; `card-expense-form-dialog.tsx`, `transaction-form-dialog.tsx`, `TagSelector.tsx` e ações de série na tela de transações
**Depends on**: T12
**Reuses**: `RecursoBloqueado`
**Requirement**: PERM-19, PERM-22

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Com `metas` fechada, a tela Metas mostra o aviso sem chamar `/api/goals/`
- [ ] Com `cartoes` fechada, a tela Cartões mostra o aviso e as faturas em aberto com o botão de pagar
- [ ] Com `compras_parceladas` fechada, o parcelamento fica limitado a 1x com o aviso; com `transacoes_recorrentes` fechada, a opção recorrente e as ações de série mostram o aviso
- [ ] Com `tags` fechada, a tela Tags mostra o aviso e o campo de tags some dos formulários
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 8 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat(frontend): aplica as travas de orçamentos, metas, tags e cartões`

---

#### T14: Importação e exportação

**What**: `importacao_ofx`, `importacao_planilha`, `exportacao_pdf` e `exportacao_xlsx` na tela de importar; o bloqueio próprio pelo plano sai.
**Where**: `src/app/(app)/importar/page.tsx`, `src/components/transactions/import-dialog.tsx`
**Depends on**: T13
**Reuses**: `RecursoBloqueado`
**Requirement**: PERM-19, PERM-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Cada uma das 4 chaves fechada mostra o aviso no botão correspondente, sem chamar a rota
- [ ] Nenhuma comparação com o nome de um plano sobra na tela
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat(frontend): aplica as travas de importação e exportação`

---

#### T15: Limites nas telas

**What**: `AvisoDeLimite` em contas, cartões, categorias, subcategorias, tags e metas, com os limites e o uso da API; os limites escritos nas telas de contas e cartões saem.
**Where**: telas de contas, cartões, categorias, tags e metas
**Depends on**: T14
**Reuses**: `AvisoDeLimite`
**Requirement**: PERM-18, PERM-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Com `limite_contas` = `{limit: 2, used: 2}`, a tela de contas mostra "2 de 2", desabilita "Nova conta" e mostra o link para os planos
- [ ] Cada um dos 6 limites desabilita a criação quando atingido
- [ ] Busca no código: nenhum número de limite nem nome de plano usado para decidir acesso em `src` (fora de `use-plan.ts` e da página de planos, que só exibem)
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 7 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `feat(frontend): mostra os limites do plano vindos da API`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T8, backend), lote 2 com as fases 3 e 4 (T9 a T15, frontend).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Administrador pelo papel | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T2: Último administrador e a própria conta | um componente | ✅ Granular |
| T3: Primeiro administrador e divergências | um componente | ✅ Granular |
| T4: Catálogo, configuração e acesso | um componente | ✅ Granular |
| T5: Configuração das travas no painel | um componente | ✅ Granular |
| T6: Travas de recurso nas rotas | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T7: Limites dos planos | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T8: Acesso no /auth/me e planos públicos | um componente | ✅ Granular |
| T9: Plano a partir da API | um componente | ✅ Granular |
| T10: Painel do administrador | um componente | ✅ Granular |
| T11: Perfil e página de planos | um componente | ✅ Granular |
| T12: Relatórios, dashboard, calendário e monitor | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T13: Orçamentos, metas, tags, cartões, parcelado e recorrente | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T14: Importação e exportação | um componente | ✅ Granular |
| T15: Limites nas telas | uma regra aplicada em vários arquivos | ⚠️ Coeso |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | None | sem seta dentro da fase | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |
| T9 | None | sem seta dentro da fase | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | None | sem seta dentro da fase | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Administrador pelo papel | Backend | integration | integration | ✅ OK |
| T2: Último administrador e a própria conta | Backend | integration | integration | ✅ OK |
| T3: Primeiro administrador e divergências | Backend | integration | integration | ✅ OK |
| T4: Catálogo, configuração e acesso | Backend | integration | integration | ✅ OK |
| T5: Configuração das travas no painel | Backend | integration | integration | ✅ OK |
| T6: Travas de recurso nas rotas | Backend | integration | integration | ✅ OK |
| T7: Limites dos planos | Backend | integration | integration | ✅ OK |
| T8: Acesso no /auth/me e planos públicos | Backend | integration | integration | ✅ OK |
| T9: Plano a partir da API | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T10: Painel do administrador | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T11: Perfil e página de planos | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T12: Relatórios, dashboard, calendário e monitor | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T13: Orçamentos, metas, tags, cartões, parcelado e recorrente | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T14: Importação e exportação | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T15: Limites nas telas | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
