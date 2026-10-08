# Permissoes e planos Design

**Spec**: `.specs/features/permissoes-e-planos/spec.md`
**Status**: Implemented

---

## Architecture Overview

Hoje quem é administrador e o que cada plano libera estão espalhados em vários pontos que se contradizem:

- O backend reconhece o admin pelo `is_staff` (`IsAdminUser`), e o frontend, pelo `role`.
- `IsPremium` e `IsPremiumPlus` sempre liberam.
- `PlanLimitsService` tem limites de 999.
- O limite de categorias usa um plano `FREE` que não existe.
- `usePlan` fixa o Premium Plus, a tela de relatórios tem um `isPremium = true` próprio, e as telas de contas e cartões têm limites só delas.

O design cria uma fonte única em cada lado:

| Peça | Backend | Frontend |
| ---- | ------- | -------- |
| Administrador | `core/permissions.py` (`EhAdministrador`: `role == 'ADMIN'` e conta ativa, lido do banco a cada requisição) | `admin-guard` e links pelo `user.access.is_admin` |
| Catálogo de travas | `core/travas.py` (`CATALOGO`: chave, tipo, nome, descrição e, nos limites, como contar o uso) | Recebe o catálogo pela API; nenhum plano ou limite escrito no código |
| Configuração | Modelo `TravaDePlano` (chave × plano) e a `GlobalSetting` `testing_unlock`, lidos com cache de 30 s, no mesmo padrão de `core/manutencao.py` | Painel admin: tabela de travas e chave da liberação para testes |
| Decisão por usuário | `acesso(usuario)`: admin libera tudo; liberação para testes libera tudo; senão, a configuração do plano atual do usuário | `usePlan()` lê `user.access` do `/auth/me` |
| Bloqueio | `RecursoLiberado('chave')` (permissão do DRF) e `conferir_limite(usuario, 'chave')`, que levantam 403 com `plan_locked` ou `plan_limit_reached` | `<RecursoBloqueado chave>` e `<AvisoDeLimite chave>`; `tratarErro` reconhece os dois códigos |

```mermaid
graph TD
    U[request.user: role e plan atuais do banco] --> A[acesso usuario]
    T[(TravaDePlano)] --> C[cache de 30 s em core/travas.py]
    G[(GlobalSetting testing_unlock)] --> C
    C --> A
    A --> P[RecursoLiberado e conferir_limite nas rotas]
    A --> M[/auth/me: access]
    M --> F[usePlan no frontend]
    F --> B[RecursoBloqueado e AvisoDeLimite nas telas]
    ADM[painel admin: PATCH /api/admin/plans/] --> T
    ADM --> G
    ADM --> L[(SystemLog: quem, quando, trava, plano, antes e depois)]
```

### Abordagens consideradas

| Abordagem | Prós | Contras | Decisão |
| --------- | ---- | ------- | ------- |
| Configuração das travas num JSON dentro de uma `GlobalSetting` | Sem tabela nova | Duas edições simultâneas sobrescrevem o JSON inteiro; log por trava fica manual | Recusada |
| Tabela `TravaDePlano` (uma linha por chave e plano) | Gravação por célula; "vale a última gravação" por trava (edge case); log simples | Uma tabela nova | **Escolhida** |
| Linha ausente na tabela = liberado e sem limite | O estado inicial (PERM-28) não precisa de 72 linhas; chave nova do catálogo nasce liberada | Precisa de teste para o padrão | **Escolhida** |
| Ler `plan` e `role` do token | Sem consulta | Mudança só vale quando o token vence (PERM-04) | Recusada; a autenticação já carrega o usuário do banco a cada requisição (AD-037) |
| Atualizar o acesso no frontend só no login | Simples | Uma trava fechada só aparece depois de novo login | Recusada; `/auth/me` é relido ao voltar o foco para a aba e ao receber um 403 de plano |

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --------- | -------- | ---------- |
| Cache de 30 s da manutenção | `core/manutencao.py` | Mesmo padrão (TTL, `invalidar()`) em `core/travas.py` |
| `GlobalSetting` e `SystemLog` | `api/models.py` | `testing_unlock` como `GlobalSetting`; o log de cada mudança no `SystemLog` (PERM-13) |
| `AdminSystemSettingsView` e tela de configurações do admin | `api/views.py:714`, `src/app/(admin)/admin/configuracoes/` | A chave da liberação fica junto da manutenção (suposição da spec) |
| Proteções do último admin | `api/views.py:507-517`, `:602-612`, `:649-653` | Unificadas em `garantir_admin_restante()`, com a mensagem da PERM-05 |
| Handler de exceções com `code` | `core/exceptions.py` (CONTRATO-29) | Acrescenta `feature` e `limit` às respostas de plano |
| `tratarErro` | `fluxar-frontend/src/lib/erros.ts` (AD-042) | Trata 403 `plan_locked` e `plan_limit_reached` com aviso, link para os planos e releitura do `/auth/me` |
| Padrão de bloqueio das telas de metas e importação | `metas/page.tsx:58-127`, `importar/page.tsx:281-293` | Vira o componente `<RecursoBloqueado>` |

### Integration Points

| System | Integration Method |
| ------ | ------------------ |
| Sessão (AD-037) | `SessaoJWTAuthentication` carrega o usuário do banco a cada requisição; as permissões usam `request.user.role` e `request.user.plan`, nunca os claims do token |
| Contratos (AD-021, AD-022, AD-042) | 403 no formato `{detail, code, feature[, limit]}`; os novos endpoints declaram parâmetros conhecidos |
| Features futuras | `gestao_do_salario` e `vinculos` já entram no catálogo e no painel; as specs `gestao-do-salario` e `vinculo-entre-transacoes` aplicam `RecursoLiberado` nas rotas delas |
| Metas e saldo | O cofrinho é uma conta comum: transferências e ajuste de saldo seguem liberados com `metas` travado (PERM-22) |
| Faturas | Pagar e estornar continuam liberados com `cartoes` travado (PERM-22); ver a decisão sobre leitura de cartões abaixo |

---

## Components

### Administrador (`core/permissions.py`, `api/views.py`)

- `EhAdministrador`: `request.user.is_authenticated and request.user.is_active and request.user.role == 'ADMIN'`. Substitui `IsAdminUser` em todas as views de administração e protege as rotas novas do painel (PERM-01, PERM-02). Quem tem `is_staff` sem o papel recebe 403.
- `garantir_admin_restante(usuario_afetado, acao)`: recusa com 400 "O sistema precisa ter pelo menos um administrador ativo." quando rebaixar, arquivar ou excluir deixaria zero admins ativos (PERM-05).
- Ação sobre a própria conta (tirar o próprio papel, arquivar ou excluir pelo painel): 400 com "Você não pode remover o próprio acesso de administrador nem arquivar ou excluir a própria conta pelo painel." (PERM-06).
- O admin do Django continua exigindo `is_staff` (comportamento padrão do `admin.site`); um teste fixa isso (PERM-08).
- O token continua levando `plan` e `role` como informação, mas nenhuma permissão os lê (PERM-04).

### Primeiro administrador e divergências

- `create_admin.py`: cria o usuário configurado só quando não existe nenhum admin ativo; se existe, não altera ninguém (PERM-07).
- Comando `python manage.py divergencias_de_admin`: lista quem tem `is_staff` sem o papel `ADMIN` e quem tem o papel sem `is_staff`, sem alterar nada, e termina com "Contas divergentes: N" (PERM-29). `DEPLOY.md` manda rodar depois do deploy, como o `check_saldos`.

### Catálogo e configuração (`core/travas.py`, `api/models.py`)

- `PLANOS = ('COMMON', 'PREMIUM', 'PREMIUM_PLUS')`.
- `CATALOGO`: as 18 chaves de recurso e as 6 de limite da spec, cada uma com `tipo` (`recurso` ou `limite`), `nome` e `descricao` em português (usados pelo painel e pela página de planos) e, nos limites, a função que conta o uso:
  - `limite_contas`: contas ativas, exceto as que são cofrinho de meta;
  - `limite_cartoes`: cartões ativos;
  - `limite_categorias`: categorias principais ativas;
  - `limite_subcategorias`: subcategorias ativas da categoria-pai informada;
  - `limite_tags`: tags;
  - `limite_metas`: metas ativas.
- Os recursos essenciais não entram no catálogo, então não há como travá-los (PERM-14).
- Modelo `TravaDePlano(chave, plano, liberado: bool | null, limite: int | null, atualizada_em, atualizada_por)` com `unique(chave, plano)`. Sem linha, o recurso fica liberado e o limite fica sem limite (PERM-28). `limite = null` significa sem limite.
- `testing_unlock` em `GlobalSetting`: a migração grava `'true'` (PERM-28); sem a linha, também vale ligada, para manter o comportamento atual.
- `configuracao()`: lê todas as linhas e a chave no máximo uma vez a cada 30 s por processo; `invalidar()` é chamado pelo painel (PERM-11, PERM-24).
- `acesso(usuario) -> Acesso`:
  - admin: tudo liberado, sem limite (PERM-09);
  - `testing_unlock`: tudo liberado, sem limite, com o plano real do usuário (PERM-23);
  - senão: a configuração do plano atual do usuário (PERM-26).
  
  `Acesso` tem `recurso_liberado(chave)` e `limite(chave)`.

### Bloqueio nas rotas (`core/travas.py`, `core/exceptions.py`)

- `PlanoBloqueado(APIException)`: 403, `default_code = 'plan_locked'`, com `feature`. `LimiteDoPlano(APIException)`: 403, `default_code = 'plan_limit_reached'`, com `feature` e `limit`. O handler devolve `{detail, code, feature[, limit]}` (PERM-15, PERM-16).
- `RecursoLiberado(chave, metodos=None)`: fábrica de permissão do DRF que levanta `PlanoBloqueado`.
- `conferir_limite(usuario, chave, **contexto)`: chamada na criação; recusa quando o uso atual é maior ou igual ao limite. Itens já existentes nunca são apagados nem bloqueados por limite (PERM-21).
- Aplicação por trava:

| Chave | Onde |
| ----- | ---- |
| `relatorios_avancados`, `comparacao_mensal`, `analise_por_tag`, `calendario` | Ações de `ReportViewSet` (substitui `IsPremium`) |
| `monitor_de_foco` | `FocusedMonitorViewSet` |
| `orcamentos` | `BudgetViewSet`, inclusive `bulk_import` |
| `metas` | `GoalViewSet` e as ações `deposit`, `withdraw` e `history` (substitui `IsPremiumPlus`) |
| `cartoes` | Criar, editar e excluir cartão; `GET /api/invoices/` (lista geral); `POST /transactions/credit-card-expense/` |
| `compras_parceladas` | `credit-card-expense` com `installments > 1` |
| `transacoes_recorrentes` | `POST /transactions/` com `is_recurring`; `bulk-update`; `bulk-delete` com `recurring_source` (`transfer_id` segue liberado) |
| `tags` | `TagViewSet`; transação criada ou editada com `tags` não vazio |
| `importacao_ofx`, `importacao_planilha` | Views de importação (a planilha inclui o preflight) |
| `exportacao_pdf`, `exportacao_xlsx` | Views de exportação (substitui `IsPremium`) |
| Limites | `AccountSerializer`, `CreditCardSerializer`, `CategoryService` (substitui `check_limits`), `TagViewSet.perform_create`, `GoalViewSet` (substitui `PlanLimitsService`, que sai) |

- **Decisão: leitura de cartões e faturas com `cartoes` travado.** A spec lista `/api/credit-cards/` entre as rotas da trava, mas PERM-22 exige pagar e estornar faturas existentes, e o fluxo de pagamento precisa ler os cartões e as faturas deles. Com a trava fechada, ficam liberados só a leitura de cartões (`GET /credit-cards/` e o detalhe), as faturas de um cartão (`GET /credit-cards/{id}/invoices/`), o detalhe e as compras de uma fatura, e `pay` e `unpay`. Todo o resto da trava é bloqueado. Na interface, a tela de Cartões travada mostra o aviso do plano e, abaixo, as faturas em aberto dos cartões existentes com o botão de pagar. A marcação no código fica como `SPEC_DEVIATION`.
- Importação com coluna de tags e `tags` travado: as tags da linha são ignoradas e a linha é gravada. Não vale rejeitar uma linha válida por um recurso acessório.

### Painel admin (`api/views.py`)

- `GET /api/admin/plans/` → `{testing_unlock, catalog: [{key, type, name, description, values: {COMMON: ..., PREMIUM: ..., PREMIUM_PLUS: ...}}]}`. O valor é `true` ou `false` para recurso e `{limit: int | null}` para limite (PERM-10).
- `PATCH /api/admin/plans/` com `{testing_unlock: bool}` ou `{key, plan, enabled}` ou `{key, plan, limit}`. As validações:
  - chave fora do catálogo, plano desconhecido ou campo errado para o tipo da trava dão 400 no campo;
  - limite que não é inteiro ≥ 0 nem `null` dá 400 em `limit` (PERM-12).
- Grava, e só quando o valor muda grava também o `SystemLog` `UPDATE_PLAN_LOCK` ou `UPDATE_TESTING_UNLOCK`, com quem, quando, a chave, o plano e os valores antigo e novo; depois chama `invalidar()` (PERM-13).
- `AdminSystemSettingsView` deixa de aceitar `testing_unlock` como chave livre; a chave muda só pela rota de planos, para ficar no log certo.

### `/auth/me` e página de planos

- `UserProfileSerializer` ganha `access`: `{is_admin, testing_unlock, plan, features: {chave: bool}, limits: {chave: {limit: int | null, used: int}}}`. `used` só aparece para limites sem contexto; `limite_subcategorias` informa só o limite, e o uso por categoria vem na tela de categorias (PERM-17).
- `GET /api/plans/` (autenticado): o catálogo com os valores dos três planos e o plano do usuário (PERM-27).

### Frontend

| Arquivo | Mudança | Requisitos |
| ------- | ------- | ---------- |
| `src/hooks/use-plan.ts` | Lê `user.access`: `podeUsar(chave)`, `limite(chave)`, `plano`, `liberacaoDeTestes`, `nomeDoPlano`; nenhum plano fixo | PERM-17, PERM-18 |
| `src/components/planos/recurso-bloqueado.tsx` e `aviso-de-limite.tsx` (novos) | Aviso do plano com link para `/planos`; uso e limite com a criação desabilitada | PERM-19, PERM-20 |
| `src/lib/erros.ts` e `auth-context.tsx` | 403 `plan_locked` e `plan_limit_reached`: aviso com link para os planos e releitura do `/auth/me`; o `/auth/me` também é relido quando a aba volta ao foco | PERM-11, PERM-15, PERM-16, PERM-24 |
| `admin-guard.tsx` e `header.tsx` | Testes da regra pelo `role` | PERM-03 |
| `src/app/(admin)/admin/configuracoes/` | Seção "Planos e travas": chave da liberação para testes junto da manutenção; tabela do catálogo com interruptores e limites por plano | PERM-10 a PERM-13, PERM-24 |
| `src/app/(app)/perfil/page.tsx` | Plano real e o aviso "Todos os recursos estão liberados durante a fase de testes." | PERM-25 |
| `src/app/(app)/planos/page.tsx` (nova) e o botão "Seja Premium Agora" | Recursos e limites de cada plano, com o plano do usuário destacado | PERM-27 |
| Relatórios, dashboard, calendário e monitor de foco | `relatorios_avancados`, `comparacao_mensal`, `analise_por_tag`, `monitor_de_foco`, `calendario` e `personalizar_dashboard`; o `isPremium = true` próprio sai | PERM-19, PERM-26 |
| Orçamentos, metas, tags, cartões, formulários de transação e de compra no cartão | `orcamentos`, `metas`, `tags` (tela e campo), `cartoes` (com as faturas em aberto), `compras_parceladas` e `transacoes_recorrentes` | PERM-19, PERM-22 |
| Importar e exportar | `importacao_ofx`, `importacao_planilha`, `exportacao_pdf` e `exportacao_xlsx` | PERM-19 |
| Contas, cartões, categorias, tags e metas | `<AvisoDeLimite>` com os limites da API; os limites próprios das telas saem | PERM-20 |

---

## Data Models

```python
# api/models.py
class TravaDePlano(models.Model):
    id = UUIDField(primary_key=True)
    chave = CharField(max_length=50)
    plano = CharField(max_length=20, choices=User.PLAN_CHOICES)
    liberado = BooleanField(null=True)       # recursos
    limite = PositiveIntegerField(null=True) # limites; null = sem limite
    atualizada_em = DateTimeField(auto_now=True)
    atualizada_por = FK(User, SET_NULL, null=True, related_name='+')

    class Meta:
        constraints = [UniqueConstraint(fields=['chave', 'plano'], name='trava_unica_por_plano')]
```

Migração `api/00xx_travadeplano` mais uma migração de dados que grava `testing_unlock = 'true'` se a chave não existir (PERM-28).

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| -------------- | -------- | ----------- |
| Rota de recurso travado | 403 `{detail: "Este recurso não está disponível no seu plano.", code: "plan_locked", feature}` | Aviso com link para os planos; a tela relê o acesso e mostra o bloqueio |
| Criação além do limite | 403 `{detail: "Você atingiu o limite do seu plano.", code: "plan_limit_reached", feature, limit}` | Aviso com uso, limite e link |
| Não admin numa rota de administração | 403 padrão | O painel não aparece; quem digitar a URL é levado ao dashboard |
| Último admin | 400 com a mensagem da PERM-05 | Toast no painel |
| Admin sobre a própria conta | 400 com a mensagem da PERM-06 | Toast no painel |
| Limite inválido no painel | 400 no campo `limit` | Mensagem no campo |

---

## Risks & Concerns

| Risk | Likelihood | Impact | Mitigation |
| ---- | ---------- | ------ | ---------- |
| Uma rota do catálogo fica sem a trava | Média | Alto | Um teste por chave: trava fechada → 403 com a chave; liberação ligada → acesso |
| Desligar a liberação trava usuários de surpresa | Média | Médio | A migração começa ligada e com tudo liberado; o painel mostra a configuração antes de desligar |
| Cache de 30 s por processo com 2 workers e 4 threads | Baixa | Baixo | Cada processo relê em até 30 s (mesmo padrão da manutenção); o processo que grava invalida na hora |
| Admin rebaixado por engano | Baixa | Alto | PERM-05 e PERM-06; `create_admin.py` cria um admin se nenhum sobrar |
| Contagem do limite de contas inclui o cofrinho | Média | Médio | Contagem exclui as contas ligadas a uma meta; teste do edge case |

---

## Tech Decisions

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Configuração das travas | Tabela `TravaDePlano` com cache de 30 s; linha ausente = liberado e sem limite (AD-044) | Gravação por célula, log simples, estado inicial sem semente |
| Resposta de trava | 403 com `plan_locked` ou `plan_limit_reached`, `feature` e `limit` | A interface distingue do erro comum (suposição da spec) |
| Administrador | `EhAdministrador` pelo `role` atual no banco | AD-016; PERM-04 |
| Leitura de cartões com `cartoes` travado | Leitura de cartões e faturas e `pay`/`unpay` seguem liberados | PERM-22 prevalece sobre a lista de rotas da trava |
