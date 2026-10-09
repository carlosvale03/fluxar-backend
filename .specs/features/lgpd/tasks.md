# Lgpd Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/lgpd/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: AD-033 (backend: `TestCase`/`APITestCase` em `tests/<feature>/`, Postgres), AD-034 (frontend: Vitest e Testing Library em `tests/<feature>/`), `.github/workflows/ci-backend.yml` e `ci-frontend.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Criptografia, CPF, máscaras, uploads, logs, exclusão, rotina, termos e consentimento (backend) | integration | Cada AC com status, código e mensagem exatos; migrações testadas importando o módulo; Cloudinary e e-mail simulados | `tests/lgpd/test_*.py` | `docker compose exec -T backend python manage.py test tests.lgpd --noinput` |
| Configurações, login, cadastro, termos, aceite e admin (frontend) | unit (frontend) | Cada comportamento de interface da spec, com a API simulada | `fluxar-frontend/tests/lgpd/*.test.tsx` | `npx vitest run tests/lgpd` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. O frontend tem 167 erros de lint antigos (MAN-04 e as regras novas do react-hooks): o gate confere que não aparecem erros novos.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas de backend | `docker compose exec -T backend python manage.py test tests.lgpd --noinput` |
| Full | Tarefas que mexem em rotas compartilhadas ou nas permissões | `docker compose exec -T backend python manage.py test --noinput` |
| Build | Fim das fases de backend | `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` |
| Quick (frontend) | Tarefas de frontend | `npx vitest run tests/lgpd` (em `fluxar-frontend`) |
| Build (frontend) | Fim das fases de frontend | `npx tsc --noEmit -p . --incremental false && npm test`, `npm run lint` sem erros novos e `npm run build` (em `fluxar-frontend`) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Guarda dos dados pessoais

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
```

### Phase 2: Dados pessoais fora dos logs

```
T6 → T7
```

### Phase 3: Exclusão da conta

```
T8 → T9
T9 → T10
T10 → T11
T11 → T12
```

### Phase 4: Termos e consentimento

```
T13 → T14
T14 → T15
T15 → T16
```

### Phase 5: Frontend

```
T17 → T18
T18 → T19
T19 → T20
T20 → T21
T21 → T22
T22 → T23
```

---

## Task Breakdown

### Phase 1: Guarda dos dados pessoais

#### T1: Campo criptografado e chave obrigatória

**What**: `core/criptografia.py` com `CampoCriptografado` e os subtipos de texto, data e decimal sobre `MultiFernet`; `FIELD_ENCRYPTION_KEY` por `obrigatoria_em_producao`; dependência `cryptography` no `requirements.txt`.
**Where**: `core/criptografia.py` (novo), `core/settings.py`, `requirements.txt`
**Depends on**: None
**Reuses**: `obrigatoria_em_producao`
**Requirement**: LGPD-15, LGPD-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Texto, data e decimal gravados voltam iguais na leitura, e o valor no banco não contém o texto em claro
- [x] Com DEBUG desligado e sem a variável, carregar as settings levanta `ImproperlyConfigured` com `FIELD_ENCRYPTION_KEY` na mensagem
- [x] Com duas chaves na lista, um valor gravado com a segunda ainda é lido
- [x] `None` continua `None`
- [x] Quick gate passa
- [x] Test count: 7 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `feat: cria o campo criptografado para dados pessoais`

---

#### T2: Dados pessoais do usuário criptografados

**What**: CPF, telefone, data de nascimento e renda de `User` passam aos campos criptografados, sem `unique` no CPF; migração que criptografa os valores já gravados.
**Where**: `api/models.py`, `api/migrations/`
**Depends on**: T1
**Reuses**: `CampoCriptografado`
**Requirement**: LGPD-15, LGPD-18, LGPD-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Depois de salvar o perfil, a coluna do CPF no banco não contém os dígitos, e o perfil devolve o CPF completo
- [x] A migração criptografa CPF, telefone, nascimento e renda já gravados, e os perfis devolvem os mesmos valores de antes
- [x] Dois usuários salvam o mesmo CPF válido sem erro
- [x] Build gate passa
- [x] Test count: 5 testes

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix: guarda CPF, telefone, nascimento e renda criptografados`

---

#### T3: Validação do CPF

**What**: `validate_cpf` confere os dígitos verificadores, recusa com "CPF inválido." e guarda só os 11 dígitos.
**Where**: `api/serializers.py`
**Depends on**: T2
**Reuses**: NONE
**Requirement**: LGPD-17, LGPD-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] CPF com dígito verificador errado e sequência repetida (111.111.111-11) recebem 400 com "CPF inválido."
- [x] CPF válido com ou sem pontuação é aceito e guardado com 11 dígitos
- [x] CPF já usado por outra conta é aceito, sem nenhuma consulta à outra conta
- [x] Quick gate passa
- [x] Test count: 5 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: valida o CPF pelos dígitos verificadores`

---

#### T4: Dados pessoais mascarados no painel

**What**: `AdminUserSerializer` mostra CPF e telefone mascarados e não envia data de nascimento nem renda.
**Where**: `api/serializers.py`
**Depends on**: T3
**Reuses**: NONE
**Requirement**: LGPD-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O detalhe do usuário no admin traz `***.***.***-12` e o telefone com só os 4 últimos dígitos
- [x] A resposta do admin não tem `date_of_birth` nem `monthly_income`
- [x] O próprio usuário continua vendo os dados completos em `/auth/me`
- [x] Quick gate passa
- [x] Test count: 3 testes

**Tests**: integration
**Gate**: quick
**Status**: ✅ Complete

**Commit**: `fix: mascara CPF e telefone e esconde renda e nascimento no painel admin`

---

#### T5: Nome aleatório nas imagens

**What**: Avatar e imagem da meta são enviados ao Cloudinary com nome aleatório e `use_filename=False`.
**Where**: `api/views.py`, `goals/serializers.py`
**Depends on**: T4
**Reuses**: NONE
**Requirement**: LGPD-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Com o uploader simulado, o envio do avatar "joao-silva.jpg" não leva "joao-silva" no nome nem nas opções
- [x] O mesmo vale para a imagem de uma meta
- [x] Build gate passa
- [x] Test count: 2 testes

**Tests**: integration
**Gate**: build
**Status**: ✅ Complete

**Commit**: `fix: envia as imagens com nome aleatório`

---

### Phase 2: Dados pessoais fora dos logs

#### T6: Logs sem dados pessoais

**What**: Saem os `print` de produção, `debug_serializer.py` e `api/utils/email.py`; comandos e logs de erro passam a usar id e e-mail mascarado; `FiltroDeDadosPessoais` em todos os handlers de `LOGGING`.
**Where**: `transactions/views.py`, `debug_serializer.py`, `api/utils/email.py`, `api/signals.py`, `goals/signals.py`, `data_exchange/importacao/gravacao.py`, `accounts/management/commands/`, `core/logs.py` (novo), `core/settings.py`
**Depends on**: None
**Reuses**: `_mask_email`
**Requirement**: LGPD-21, LGPD-22, LGPD-23

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Busca no código de produção (fora de tests, migrations e scratch) não acha `print(`
- [x] Criar uma categoria não escreve o payload em nenhum log
- [x] O filtro troca um e-mail e um CPF numa mensagem de log pela forma mascarada
- [x] Erro simulado no Cloudinary loga só a classe do erro
- [x] Os comandos `audit_accounts` e `init_balances` não escrevem e-mail completo, nome de conta nem saldo junto do nome
- [x] Full gate passa
- [x] Test count: 10 testes

**Tests**: integration
**Gate**: full
**Status**: ✅ Complete

**Commit**: `fix: tira dados pessoais e financeiros dos logs`

---

#### T7: Log de auditoria sem nomes

**What**: `SystemLog.user` passa a `SET_NULL` com `usuario_ref`; descrições sem nome; `admin_name` com o e-mail mascarado; migração que mascara e-mails nas descrições e preenche `usuario_ref`.
**Where**: `api/models.py`, `api/migrations/`, `api/views.py`
**Depends on**: T6
**Reuses**: `_mask_email`
**Requirement**: LGPD-21, LGPD-22, LGPD-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Arquivar, redefinir senha e limpar dados gravam descrição sem nome e `admin_name` mascarado
- [ ] A migração troca "joao@x.com" por "jo***@x.com" nas descrições antigas e preenche `usuario_ref`
- [ ] Build gate passa
- [ ] Test count: pelo menos 4 testes

**Tests**: integration
**Gate**: build

**Commit**: `fix: identifica pessoas no log de auditoria só pelo id e pelo e-mail mascarado`

---

### Phase 3: Exclusão da conta

#### T8: Pedido de exclusão

**What**: Campos `exclusao_pedida_em` e `exclusao_agendada_para`; `POST /api/users/me/delete/` com a senha, a proteção do único admin, a desativação, o encerramento das sessões, o agendamento para 30 dias e o e-mail.
**Where**: `api/models.py`, `api/migrations/`, `api/views.py`, `api/urls.py`, `api/utils/email_service.py`
**Depends on**: None
**Reuses**: `encerrar_todas`, `garantir_admin_restante`
**Requirement**: LGPD-03, LGPD-04, LGPD-05, LGPD-06, LGPD-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Senha errada recebe 400 `{password: ["Senha incorreta."]}` e a conta não muda
- [ ] Senha certa desativa a conta, encerra as sessões de todos os aparelhos e devolve `deletion_scheduled_for` 30 dias depois
- [ ] O e-mail sai com a data e como desistir; com o envio falhando, o pedido vale igual
- [ ] O único admin ativo recebe 400 "O sistema precisa ter pelo menos um administrador ativo."
- [ ] Quick gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat: permite ao usuário pedir a exclusão da própria conta`

---

#### T9: Login durante o prazo e cancelamento

**What**: O login de conta com exclusão marcada responde `deletion_pending` com a data e um `cancel_token`; `POST /api/auth/cancel-deletion/` reativa e abre a sessão.
**Where**: `api/serializers.py`, `api/views.py`, `api/urls.py`
**Depends on**: T8
**Reuses**: `criar_sessao`, `django.core.signing`
**Requirement**: LGPD-07, LGPD-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Login com a senha certa responde 400 `{code: "deletion_pending", deletion_scheduled_for, cancel_token}` sem criar sessão
- [ ] Senha errada continua `invalid_credentials`
- [ ] O cancelamento com o token reativa a conta com todos os dados, limpa as datas e devolve o access com o refresh no cookie
- [ ] Token vencido ou adulterado recebe 400
- [ ] "Esqueci a senha" durante o prazo funciona e não cancela a exclusão
- [ ] Quick gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat: oferece cancelar a exclusão ao entrar durante o prazo`

---

#### T10: Download dos dados financeiros

**What**: `GET /api/users/me/export/` devolve um XLSX com abas de transações, contas, cartões, metas e orçamentos, liberado em todos os planos.
**Where**: `api/views.py`, `api/urls.py`, `data_exchange/services.py`
**Depends on**: T9
**Reuses**: `ExportService.generate_xls`
**Requirement**: LGPD-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Um usuário Comum com `exportacao_xlsx` travada baixa o XLSX com status 200
- [ ] O arquivo tem as cinco abas, só com os dados do próprio usuário
- [ ] Quick gate passa
- [ ] Test count: pelo menos 3 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat: permite baixar os dados financeiros em qualquer plano`

---

#### T11: Exclusão definitiva

**What**: `api/exclusao.py` com `excluir_definitivamente` (Cloudinary primeiro, depois o `atomic`), `MODELOS_DO_USUARIO`, os logs de ações de admin mantidos só com `usuario_ref` e o `RegistroDeExclusao`; o admin passa a usar o mesmo caminho.
**Where**: `api/exclusao.py` (novo), `api/models.py`, `api/migrations/`, `api/views.py`
**Depends on**: T10
**Reuses**: `cloudinary.uploader`
**Requirement**: LGPD-10, LGPD-11, LGPD-12, LGPD-13, LGPD-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Excluir um usuário com contas, cartões, faturas pagas, transações, metas com imagem, trocos, correções, orçamentos, monitores, sessões e aceites apaga tudo e destrói o avatar e as imagens das metas
- [ ] Fica só o `RegistroDeExclusao` com id, datas e quem executou; os logs de ações de admin ficam com `usuario_ref` e `user` nulo; os demais logs do usuário saem
- [ ] Com o Cloudinary falhando, nada é apagado e a conta continua desativada e marcada
- [ ] Um teste falha se existir modelo com FK para `User` fora de `MODELOS_DO_USUARIO` e das exceções
- [ ] O admin exclui na hora, inclusive conta com exclusão pendente, com o mesmo registro e sem o nome na resposta
- [ ] Depois da exclusão, o mesmo e-mail se cadastra de novo
- [ ] Full gate passa
- [ ] Test count: pelo menos 8 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat: apaga todos os dados da conta e guarda só o registro da exclusão`

---

#### T12: Rotina diária

**What**: Comando `rotina_diaria`, rota `POST /api/rotina-diaria/` com `ROTINA_DIARIA_TOKEN` e o workflow agendado do GitHub; `DEPLOY.md` com as variáveis e os segredos.
**Where**: `api/management/commands/rotina_diaria.py` (novo), `api/views.py`, `api/urls.py`, `core/settings.py`, `.github/workflows/rotina-diaria.yml` (novo), `DEPLOY.md`
**Depends on**: T11
**Reuses**: `excluir_definitivamente`
**Requirement**: LGPD-10, LGPD-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Com a data vencida simulada, a rotina apaga a conta e grava `executada_por` = ROTINA; conta com prazo futuro fica
- [ ] Uma conta que falha não impede a próxima e é apagada na execução seguinte, sem registro duplicado
- [ ] A rota sem token recebe 401, com token certo roda e responde `{excluidas, falhas}`; sem a variável configurada, 404
- [ ] Build gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: build

**Commit**: `feat: agenda a exclusão definitiva das contas vencidas`

---

### Phase 4: Termos e consentimento

#### T13: Versão dos termos e aceite no cadastro

**What**: `core/termos.py`, `GET /api/terms/`, os modelos `AceiteDosTermos` e `DecisaoDeConsentimento`, os caches no `User` e a migração que deixa todos sem o aceite da versão nova e sem o consentimento; o cadastro grava o aceite da versão vigente e o consentimento opcional.
**Where**: `core/termos.py` (novo), `api/models.py`, `api/migrations/`, `api/serializers.py`, `api/views.py`, `api/urls.py`
**Depends on**: None
**Reuses**: NONE
**Requirement**: LGPD-26, LGPD-27, LGPD-30, LGPD-33, LGPD-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `GET /api/terms/` devolve versão, data, mudanças e serviços sem login
- [ ] Cadastro sem o aceite ou com `false` recebe 400 no campo `terms_accepted`
- [ ] Cadastro aceito grava o aceite da versão vigente com data e hora; com `product_improvement_consent: true`, grava a decisão; sem o campo, o consentimento fica desligado
- [ ] Depois da migração, todo usuário existente tem `versao_dos_termos_aceita` nulo e o consentimento desligado
- [ ] Quick gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat: registra o aceite dos termos por versão e o consentimento no cadastro`

---

#### T14: Bloqueio até o aceite

**What**: `TermosMiddleware` com as rotas liberadas do design e `POST /api/terms/accept/`; `/auth/me` traz `terms` e `product_improvement_consent`.
**Where**: `api/middleware.py`, `core/settings.py`, `api/views.py`, `api/serializers.py`, `api/urls.py`
**Depends on**: T13
**Reuses**: o padrão do middleware da manutenção
**Requirement**: LGPD-28, LGPD-29, LGPD-30

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Sem o aceite da versão vigente, `/api/accounts/` recebe 403 `{code: "terms_acceptance_required"}`
- [ ] Login, renovação, `/auth/me`, logout, termos, aceite, download dos dados, pedido de exclusão, cancelamento e health continuam funcionando
- [ ] Aceitar a versão vigente libera as rotas; aceitar outra versão recebe 400; aceites anteriores continuam gravados
- [ ] Mudar `VERSAO_VIGENTE` faz o próximo pedido de quem aceitou a anterior receber 403
- [ ] Full gate passa
- [ ] Test count: pelo menos 6 testes

**Tests**: integration
**Gate**: full

**Commit**: `feat: pede o aceite da versão nova dos termos antes de liberar o app`

---

#### T15: Consentimento nas configurações

**What**: `GET` e `PUT /api/users/me/consent/` gravam cada decisão com a versão vigente e atualizam o cache.
**Where**: `api/views.py`, `api/urls.py`
**Depends on**: T14
**Reuses**: `DecisaoDeConsentimento`
**Requirement**: LGPD-34, LGPD-35

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Dar e retirar o consentimento grava duas decisões com data e versão, sem apagar a anterior
- [ ] `GET` devolve o estado atual e a data da última decisão
- [ ] Quick gate passa
- [ ] Test count: pelo menos 3 testes

**Tests**: integration
**Gate**: quick

**Commit**: `feat: permite dar e retirar o consentimento a qualquer momento`

---

#### T16: Conjunto anonimizado

**What**: `core/conjuntos.py` com `dados_para_melhoria()` e o comando `exportar_dados_de_melhoria`, só com quem consentiu, sem identificadores.
**Where**: `core/conjuntos.py` (novo), `core/management/commands/exportar_dados_de_melhoria.py` (novo)
**Depends on**: T15
**Reuses**: `normalizar_descricao`
**Requirement**: LGPD-36, LGPD-37, LGPD-38

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Usuário sem consentimento não aparece no conjunto
- [ ] Depois de retirar o consentimento, o usuário sai do próximo conjunto
- [ ] Nenhuma linha traz id de usuário, conta ou transação, nome de conta ou cartão, dia, e-mail, CPF ou dígito na descrição
- [ ] Build gate passa
- [ ] Test count: pelo menos 4 testes

**Tests**: integration
**Gate**: build

**Commit**: `feat: gera o conjunto anonimizado só com os dados de quem consentiu`

---

### Phase 5: Frontend

#### T17: Excluir minha conta

**What**: Aba "Privacidade" nas configurações com "Excluir minha conta": download do XLSX, confirmação pela senha com o erro no campo e a data da exclusão; depois, a sessão termina.
**Where**: `src/app/(app)/configuracoes/page.tsx`, `src/services/`
**Depends on**: None
**Reuses**: `tratarErro`
**Requirement**: LGPD-01, LGPD-02, LGPD-03, LGPD-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] As configurações mostram "Excluir minha conta"
- [ ] O botão de download chama `/users/me/export/` antes da confirmação
- [ ] Senha errada mostra o erro no campo; senha certa mostra a data e encerra a sessão
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: permite excluir a própria conta pelas configurações`

---

#### T18: Cancelar a exclusão no login

**What**: O login trata `deletion_pending`: mostra a data e "Cancelar exclusão", que chama `cancel-deletion` e entra.
**Where**: `src/app/auth/login/page.tsx`, `src/contexts/auth-context.tsx`
**Depends on**: T17
**Reuses**: `iniciarSessao`
**Requirement**: LGPD-07, LGPD-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `deletion_pending` mostra a data da exclusão e o botão
- [ ] "Cancelar exclusão" envia o `cancel_token` e leva ao dashboard com a sessão aberta
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: oferece cancelar a exclusão na tela de login`

---

#### T19: Cadastro e textos de segurança

**What**: Cadastro com a caixa de consentimento desmarcada e enviada como `product_improvement_consent`; textos de segurança do cadastro e da página Sobre só com o que o app faz.
**Where**: `src/app/auth/register/page.tsx`, `src/app/sobre/page.tsx`
**Depends on**: T18
**Reuses**: NONE
**Requirement**: LGPD-26, LGPD-32, LGPD-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A caixa de consentimento começa desmarcada e o cadastro passa sem ela
- [ ] Marcada, envia `product_improvement_consent: true`
- [ ] Nenhum texto do cadastro e da página Sobre fala em ponta a ponta nem em padrões bancários
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: oferece o consentimento opcional no cadastro`

---

#### T20: Página de termos e política

**What**: A página mostra a versão e a data vindas de `GET /api/terms/`, as finalidades (inclusive melhoria do produto e treino de modelos), os serviços e a segurança só com o que o app faz.
**Where**: `src/app/termos/page.tsx`, `src/services/`
**Depends on**: T19
**Reuses**: NONE
**Requirement**: LGPD-31, LGPD-32

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] A página mostra a versão e a data da API
- [ ] As finalidades citam a melhoria do produto e o treino de modelos, opcionais
- [ ] Os serviços de hospedagem da API e do banco, do site, de e-mail e de imagens aparecem
- [ ] Não aparece "ponta a ponta"
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 4 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `docs: atualiza os termos com versão, finalidades e serviços`

---

#### T21: Aceite da versão nova

**What**: O interceptor leva o 403 `terms_acceptance_required` à nova tela de aceite, que mostra as mudanças, chama `POST /terms/accept/` e oferece baixar os dados e pedir a exclusão.
**Where**: `src/services/apiClient.ts`, `src/app/termos/aceite/page.tsx` (nova), `src/contexts/auth-context.tsx`
**Depends on**: T20
**Reuses**: NONE
**Requirement**: LGPD-28, LGPD-29

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Um 403 `terms_acceptance_required` leva à tela de aceite
- [ ] A tela mostra as mudanças da versão e, ao aceitar, volta ao app
- [ ] Ao carregar o usuário com `terms.accepted_version` diferente de `current_version`, a tela de aceite aparece antes das outras
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 3 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: pede o aceite da versão nova dos termos ao entrar`

---

#### T22: Consentimento nas configurações

**What**: Na aba "Privacidade", o interruptor do consentimento mostra o estado e grava pela API.
**Where**: `src/app/(app)/configuracoes/page.tsx`
**Depends on**: T21
**Reuses**: `tratarErro`
**Requirement**: LGPD-34

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O interruptor mostra o estado de `product_improvement_consent`
- [ ] Ligar e desligar chama `PUT /users/me/consent/`
- [ ] Quick gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: quick

**Commit**: `feat: permite dar e retirar o consentimento nas configurações`

---

#### T23: Painel admin e nome da imagem da meta

**What**: O painel mostra CPF e telefone mascarados como vêm da API; a imagem da meta é enviada com nome genérico.
**Where**: `src/app/(admin)/admin/usuarios/[id]/page.tsx`, `src/services/goals.ts`
**Depends on**: T22
**Reuses**: NONE
**Requirement**: LGPD-19, LGPD-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] O detalhe do usuário mostra o CPF mascarado e não mostra renda nem nascimento
- [ ] A imagem da meta vai no `FormData` com nome genérico
- [ ] Build gate (frontend) passa
- [ ] Test count: pelo menos 2 testes

**Tests**: unit (frontend)
**Gate**: build

**Commit**: `fix: mostra os dados pessoais mascarados no painel e envia a imagem da meta sem o nome original`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

Execution is strictly sequential - there is no intra-phase parallelism.

Lotes para os sub-agentes: lote 1 com as fases 1 e 2 (T1 a T7), lote 2 com as fases 3 e 4 (T8 a T16), lote 3 com a fase 5 (T17 a T23).

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Campo criptografado e chave obrigatória | um componente | ✅ Granular |
| T2: Dados pessoais do usuário criptografados | um componente | ✅ Granular |
| T3: Validação do CPF | um componente | ✅ Granular |
| T4: Dados pessoais mascarados no painel | um componente | ✅ Granular |
| T5: Nome aleatório nas imagens | um componente | ✅ Granular |
| T6: Logs sem dados pessoais | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T7: Log de auditoria sem nomes | um componente | ✅ Granular |
| T8: Pedido de exclusão | um componente | ✅ Granular |
| T9: Login durante o prazo e cancelamento | um componente | ✅ Granular |
| T10: Download dos dados financeiros | um componente | ✅ Granular |
| T11: Exclusão definitiva | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T12: Rotina diária | um componente | ✅ Granular |
| T13: Versão dos termos e aceite no cadastro | um componente | ✅ Granular |
| T14: Bloqueio até o aceite | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T15: Consentimento nas configurações | um componente | ✅ Granular |
| T16: Conjunto anonimizado | um componente | ✅ Granular |
| T17: Excluir minha conta | um componente | ✅ Granular |
| T18: Cancelar a exclusão no login | um componente | ✅ Granular |
| T19: Cadastro e textos de segurança | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T20: Página de termos e política | uma regra aplicada em vários arquivos | ⚠️ Coeso |
| T21: Aceite da versão nova | um componente | ✅ Granular |
| T22: Consentimento nas configurações | um componente | ✅ Granular |
| T23: Painel admin e nome da imagem da meta | um componente | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | sem seta dentro da fase | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | None | sem seta dentro da fase | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | None | sem seta dentro da fase | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T9 | T9 → T10 | ✅ Match |
| T11 | T10 | T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | None | sem seta dentro da fase | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14 | T14 → T15 | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |
| T17 | None | sem seta dentro da fase | ✅ Match |
| T18 | T17 | T17 → T18 | ✅ Match |
| T19 | T18 | T18 → T19 | ✅ Match |
| T20 | T19 | T19 → T20 | ✅ Match |
| T21 | T20 | T20 → T21 | ✅ Match |
| T22 | T21 | T21 → T22 | ✅ Match |
| T23 | T22 | T22 → T23 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: Campo criptografado e chave obrigatória | Backend | integration | integration | ✅ OK |
| T2: Dados pessoais do usuário criptografados | Backend | integration | integration | ✅ OK |
| T3: Validação do CPF | Backend | integration | integration | ✅ OK |
| T4: Dados pessoais mascarados no painel | Backend | integration | integration | ✅ OK |
| T5: Nome aleatório nas imagens | Backend | integration | integration | ✅ OK |
| T6: Logs sem dados pessoais | Backend | integration | integration | ✅ OK |
| T7: Log de auditoria sem nomes | Backend | integration | integration | ✅ OK |
| T8: Pedido de exclusão | Backend | integration | integration | ✅ OK |
| T9: Login durante o prazo e cancelamento | Backend | integration | integration | ✅ OK |
| T10: Download dos dados financeiros | Backend | integration | integration | ✅ OK |
| T11: Exclusão definitiva | Backend | integration | integration | ✅ OK |
| T12: Rotina diária | Backend | integration | integration | ✅ OK |
| T13: Versão dos termos e aceite no cadastro | Backend | integration | integration | ✅ OK |
| T14: Bloqueio até o aceite | Backend | integration | integration | ✅ OK |
| T15: Consentimento nas configurações | Backend | integration | integration | ✅ OK |
| T16: Conjunto anonimizado | Backend | integration | integration | ✅ OK |
| T17: Excluir minha conta | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T18: Cancelar a exclusão no login | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T19: Cadastro e textos de segurança | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T20: Página de termos e política | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T21: Aceite da versão nova | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T22: Consentimento nas configurações | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
| T23: Painel admin e nome da imagem da meta | Frontend | unit (frontend) | unit (frontend) | ✅ OK |
