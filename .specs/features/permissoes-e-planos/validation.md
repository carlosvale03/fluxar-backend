# Permissoes e planos Validation

**Date**: 2026-10-08
**Spec**: `.specs/features/permissoes-e-planos/spec.md`
**Diff range**: backend `fix/permissoes-e-planos` (`129162c..9bb5807`, 17 commits: 9 de código e testes, 1 de design/tasks, 7 de marcação das tasks); frontend `fix/permissoes-e-planos` (`8fdd137..8e027b1`, 10 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve, uma rodada
**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T15 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md` (T1 a T8 no backend, T9 a T15 no frontend, mais a correção `9bb5807`/`5bd4b8d` das tags). O cabeçalho de `tasks.md` ainda diz `Status: In Progress` (observação 6) |

---

## Gate Check

### Backend

- **Comando**: `docker compose exec -T backend python manage.py test --noinput`
- **Resultado**: exit 0. `Ran 872 tests in 235.084s ... OK`
- **Falhas**: nenhuma. **Skips**: nenhum. O teste instável conhecido (`tests.importacao.test_sugestao.test_linha_com_categoria_no_arquivo_mantem_a_do_arquivo`) passou nesta rodada
- **Contagem**: 782 antes da feature (gate da `importacao`), 872 depois: +90, todos em `tests/permissoes/` (`manage.py test tests.permissoes` roda 90)
- **Migrações**: `python manage.py makemigrations --check --dry-run` → `No changes detected`

### Frontend

| Gate | Resultado |
| ---- | --------- |
| `npm test` | 51 arquivos, 270 testes, todos passando (198 antes da feature, +72 em `tests/permissoes/`) |

Testes antigos ajustados no frontend: `tests/contratos/colecoes-completas.test.tsx`, `datas-sem-hora.test.tsx`, `formatador-unico.test.tsx` e `tests/saldo/exclusao-de-conta.test.tsx`, só nos mocks do `usePlan`/`access` (de 1 a 5 linhas cada), sem tirar asserções.

---

## Spec-Anchored Acceptance Criteria

Os caminhos `tests/permissoes/*.py` são do `fluxar-backend`. Os marcados **FE** estão em `tests/permissoes/` do `fluxar-frontend`.

### P1: Quem é administrador

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| PERM-01 papel `ADMIN` = admin no backend e na interface | admin nos dois lados | `tests/permissoes/test_administrador.py:95` - admin sem `is_staff` → 200 em cada uma das 16 funções; FE `painel-de-travas.test.tsx:199-200` - `AdminGuard` mostra o painel para `ADMIN`; `:213-214` link "Painel Admin" → `/admin/dashboard` | ✅ PASS |
| PERM-02 sem o papel → 403 em cada função, mesmo com `is_staff` | HTTP 403 | `tests/permissoes/test_administrador.py:74` - `is_staff`+`is_superuser` → `403` em cada função da lista da spec, com a vítima intacta (`:76-79`); `tests/permissoes/test_painel_de_planos.py:189-195` - `GET`/`PATCH /api/admin/plans/` → 403 para comum e `is_staff` | ✅ PASS |
| PERM-03 não admin: sem links e levado ao dashboard | sem link; `push('/dashboard')` sem conteúdo | FE `painel-de-travas.test.tsx:187-188` - `push("/dashboard")` e "conteúdo do painel" ausente; `:213` - zero links "Painel Admin" para `USER` | ✅ PASS |
| PERM-04 mudança de papel/plano vale na próxima requisição pelo banco | mesma sessão, valor novo | `tests/permissoes/test_administrador.py:109-115` - mesmo token: 403 → `update(role='ADMIN')` → 200 → `update(role='USER')` → 403; `tests/permissoes/test_acesso_e_planos.py:76-81` - plano trocado → `access.plan == 'PREMIUM'` e `metas` liberado | ✅ PASS |
| PERM-05 último admin | 400, "O sistema precisa ter pelo menos um administrador ativo." | `tests/permissoes/test_ultimo_admin.py:52-53` - `400` e `detail == ULTIMO_ADMIN` (texto exato da spec) para tirar o papel, desativar, arquivar, arquivar em massa, excluir e excluir definitivamente | ✅ PASS |
| PERM-06 a própria conta pelo painel | HTTP 400 | `tests/permissoes/test_ultimo_admin.py:96-97` - `400` e `detail == PROPRIA_CONTA` (mensagem do design) nas seis ações, com outro admin ativo | ✅ PASS |
| PERM-07 primeiro admin só sem admin ativo, sem repromover | nada criado nem alterado com admin ativo | `tests/permissoes/test_primeiro_admin.py:48-50` - contagem e estado da conta do e-mail configurado iguais, papel `USER`; `:57-58` - sem admin ativo, cria `('ADMIN', True, True, 'PREMIUM_PLUS', True)`; `:69-70` - conta existente não é promovida | ✅ PASS |
| PERM-08 `/admin/` do Django exige `is_staff` | acesso recusado | `tests/permissoes/test_administrador.py:147-148` - papel `ADMIN` sem `is_staff` → 302 para `/admin/login/`; `:153` com `is_staff` → 200 | ✅ PASS |
| PERM-09 admin com tudo liberado e sem limite | todos os recursos, limites ignorados | `tests/permissoes/test_catalogo.py:109-114` - admin `COMMON` com tudo fechado: 18 recursos `True`, 6 limites `None`; `tests/permissoes/test_travas_de_recurso.py:259-260` - rotas → 200; `tests/permissoes/test_limites.py:141-143` - cria tag com limite 0 (201) | ✅ PASS |

### P1: Configuração das travas pelo administrador

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| PERM-10 painel mostra cada trava com o valor dos três planos | as 24 travas × 3 planos | `tests/permissoes/test_painel_de_planos.py:40-51` - `keys == RECURSOS + LIMITES`, nome, descrição e `values` dos três planos; FE `painel-de-travas.test.tsx:104-112` - 54 interruptores, 18 campos de limite e os valores configurados | ✅ PASS |
| PERM-11 grava e aplica em até 30 s | gravado; vale ≤ 30 s | `tests/permissoes/test_painel_de_planos.py:83-88` - PATCH → `acesso(comum)` bloqueado/limite 2 e premium intacto; linha com `atualizada_por`; `tests/permissoes/test_catalogo.py:177-181` - mudança direta no banco vale em 30,0 s e não em 29,9 s; FE `painel-de-travas.test.tsx:123-124` - envia `{key, plan, enabled}` | ✅ PASS |
| PERM-12 limite inválido | HTTP 400 | `tests/permissoes/test_painel_de_planos.py:102-103` - `-1`, `2.5`, `'abc'`, `True`, `''`, `[2]` → 400 com o campo `limit`; `:104-105` nada gravado nem logado; FE `painel-de-travas.test.tsx:157` - erro no campo | ✅ PASS |
| PERM-13 log com quem, quando, trava, plano, antigo e novo | log por mudança de valor | `tests/permissoes/test_painel_de_planos.py:141-151` - descrições exatas (`"Trava 'exportacao_pdf' no plano COMMON: liberado -> bloqueado."` etc.), `admin_name` e `timestamp`; `:160-161` mesmo valor não gera log; `:176-179` liberação ligada → desligada → ligada | ✅ PASS |
| PERM-14 essenciais sem trava | fora do catálogo | `tests/permissoes/test_catalogo.py:39-40` - o catálogo é exatamente os 18 recursos e 6 limites da spec; `:52-53` nenhuma chave essencial; `tests/permissoes/test_limites.py:182-183` - com tudo fechado, `GET /api/accounts/` segue respondendo | ✅ PASS |

### P1: Travas aplicadas em cada tela e rota

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| PERM-15 rota de recurso bloqueado | 403, `code: plan_locked`, chave | `tests/permissoes/test_travas_de_recurso.py:68-69` - `403` e corpo `== {'detail': ..., 'code': 'plan_locked', 'feature': chave}`, usado em cada uma das 15 chaves com rota (`:194-237`) | ✅ PASS |
| PERM-16 além do limite | 403, `code: plan_limit_reached`, chave e limite | `tests/permissoes/test_limites.py:32-35` - corpo `== {..., 'code': 'plan_limit_reached', 'feature': chave, 'limit': limite}`; `:109` nos 6 limites (aceita abaixo, recusa no limite) | ✅ PASS |
| PERM-17 `/auth/me` com plano real, recursos e limites com uso | `access` completo | `tests/permissoes/test_acesso_e_planos.py:37-50` - `is_admin`, `testing_unlock`, `plan: 'COMMON'`, 18 recursos, `limite_contas == {'limit': 2, 'used': 1}`, uso de categorias e `limite_subcategorias == {'limit': None}` | ✅ PASS |
| PERM-18 interface decide só pelo `/auth/me` | nenhum plano/limite no código | FE `plano-pela-api.test.tsx:35-37` - `podeUsar("metas") === false` com plano `PREMIUM_PLUS` (só o `access` decide); FE `limites-nas-telas.test.tsx:168-171` - nenhum `PREMIUM`/`COMMON`/`isPremium`/`PLAN_LIMITS` nas telas | ✅ PASS |
| PERM-19 recurso bloqueado: aviso e link, sem chamar a rota | aviso + `/planos`, rota não chamada | FE `plano-pela-api.test.tsx:77-79` - conteúdo ausente, aviso e link `/planos`; FE `travas-de-telas.test.tsx:108-111` - Metas com aviso e link, `getGoals` não chamado e nenhuma URL `/goals/` | ✅ PASS |
| PERM-20 limite atingido: uso, limite, criação desabilitada e link | "2 de 2", botão desabilitado, link | FE `limites-nas-telas.test.tsx:87-90` - "2 de 2 contas", link `/planos`, "Nova Conta" desabilitado; `:106-144` cartões, categorias, subcategorias, tags e metas | ✅ PASS |
| PERM-21 descida mantém os dados | nada apagado; só bloqueia uso e criação | `tests/permissoes/test_limites.py:180-184` - retrato igual antes e depois de descer para `COMMON` com tudo fechado; criação → `plan_limit_reached` | ✅ PASS |
| PERM-22 cofrinho e faturas existentes | transferir/ajustar cofrinho; pagar e estornar | `tests/permissoes/test_travas_de_recurso.py:380-389` - `metas` fechado: transferências 201 e ajuste para 50,00 no cofrinho; `:405-415` - `cartoes` fechado: leituras 200, `pay` → compra `COMPLETED`, `unpay` → `PENDING`; FE `travas-de-telas.test.tsx:151-155` | ✅ PASS (decisão SPEC_DEVIATION do design) |

### P1: Liberação para testes

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| PERM-23 ligada libera tudo sem mudar o plano gravado | tudo liberado, plano intacto | `tests/permissoes/test_catalogo.py:126-132` - recursos `True`, limites `None`, `plan == 'COMMON'` no banco; `tests/permissoes/test_travas_de_recurso.py:242-251` - todas as rotas do catálogo com o status normal | ✅ PASS |
| PERM-24 liga/desliga vale em até 30 s | aplicado a todos | `tests/permissoes/test_painel_de_planos.py:169-174` - PATCH `testing_unlock` → acesso muda na decisão seguinte; FE `painel-de-travas.test.tsx:169`; FE `releitura-do-acesso.test.tsx:73-75` - aba visível relê `/auth/me/` e a tela trava | ✅ PASS |
| PERM-25 perfil com plano real e o aviso | "Todos os recursos estão liberados durante a fase de testes." | FE `perfil-e-planos.test.tsx:72-73` - "Plano Comum" e o texto exato; `:81-82` sem o aviso com a liberação desligada | ✅ PASS |
| PERM-26 desligada: só as travas configuradas | cada tela e rota obedece | `tests/permissoes/test_travas_de_recurso.py:76-84` (`conferir`): fechada → 403, aberta → status normal, nas 15 chaves com rota; `tests/permissoes/test_catalogo.py:95-104`; FE telas por chave (`travas-de-telas`, `travas-de-relatorios`, `travas-de-importacao`) | ✅ PASS (observação 1) |

### P2: Página de planos e implantação

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| PERM-27 recursos e limites de cada plano, plano do usuário em destaque | da configuração atual | `tests/permissoes/test_acesso_e_planos.py:100-112` - `plan == 'PREMIUM'`, 24 travas, `exportacao_pdf` e `limite_contas` com os valores configurados; FE `perfil-e-planos.test.tsx:109-111` - "Não incluído/Incluído", "Até 2/Até 5/Sem limite"; `:122-123` uma coluna `aria-current` "Premium" | ✅ PASS |
| PERM-28 começa com a liberação ligada e tudo liberado | `testing_unlock = true`; sem linhas | `tests/permissoes/test_catalogo.py:59-60` - `value == 'true'` após as migrações; `:68` migração não sobrescreve; `:77-86` sem linhas, tudo liberado e sem limite nos três planos | ✅ PASS |
| PERM-29 lista divergências sem alterar | lista e "Contas divergentes: N" | `tests/permissoes/test_primeiro_admin.py:91-97` - última linha `'Contas divergentes: 2'`, as duas divergências com e-mail mascarado, coerentes ausentes, estados iguais | ✅ PASS |

**Status**: ✅ 29/29 ACs com evidência no valor definido pela spec; nenhuma lacuna de precisão.

### Critério de sucesso "interface mostra o aviso e a rota responde 403" (amostra de 5 chaves)

| Chave | Rota (backend) | Tela (FE) |
| ----- | -------------- | --------- |
| `metas` | `test_travas_de_recurso.py:212` (lista, aporte, resgate e histórico → `plan_locked`) | `travas-de-telas.test.tsx:103-111` |
| `calendario` | `test_travas_de_recurso.py:206` | `travas-de-relatorios.test.tsx:158-165` |
| `exportacao_pdf` | `test_travas_de_recurso.py:233` | `travas-de-importacao.test.tsx:71-83` |
| `orcamentos` | `test_travas_de_recurso.py:209` (inclusive `bulk_import`) | `travas-de-telas.test.tsx:122-128` |
| `limite_contas` | `test_limites.py:59-72` (`plan_limit_reached`, limite 2) | `limites-nas-telas.test.tsx:82-90` |

As 5 batem. `personalizar_dashboard` é só de interface (spec); `gestao_do_salario` e `vinculos` não têm rota nem tela ainda (observação 1).

---

## Edge Cases

- [x] Cofrinho de meta não conta no limite de contas (`tests/permissoes/test_catalogo.py:154`; pela rota em `tests/permissoes/test_limites.py:86-97`)
- [x] 5 contas com limite 2: as 5 ficam, só cria com menos de 2 ativas (`tests/permissoes/test_limites.py:59-84`)
- [x] Admin rebaixado perde o painel na requisição seguinte (`tests/permissoes/test_administrador.py:137`); obedecer às travas depois de rebaixado é indireto (observação 3)
- [x] Liberação desligada com a tela aberta: 403 → relê o acesso e a tela trava (FE `releitura-do-acesso.test.tsx:89-91`)
- [x] Dois admins na mesma trava: as duas gravações aparecem no log em sequência (`tests/permissoes/test_painel_de_planos.py:141-148`); simultaneidade real não testada (observação 4)
- [x] `personalizar_dashboard` só na interface (FE `travas-de-relatorios.test.tsx:199-206`)
- [x] Ocorrências de série antiga com `transacoes_recorrentes` fechado seguem editáveis (`tests/permissoes/test_travas_de_recurso.py:298-301`)

---

## Discrimination Sensor

**Isolamento no backend**: worktree descartável `../fluxar-backend-mut` (detached em `9bb5807`) e container avulso: `docker run --rm --network fluxar-backend_default --env-file <ambiente do serviço backend, lido do container do compose> -v <worktree>:/app -w /app fluxar-backend-backend python manage.py test tests.permissoes --noinput`. Os mutantes rodaram depois do gate inteiro, para não disputar o banco de teste. Sem mutação, os 90 testes passaram no worktree (B0). Cada mutação foi aplicada por um script que exige uma ocorrência única do trecho e revertida com `git checkout -- <arquivo>` no worktree, que foi conferido limpo antes da seguinte. O arquivo de ambiente ficou no scratchpad e foi apagado no fim. Uma primeira versão do mutante B4 não compilou (`SyntaxError`, o `\n` entrou literal) e foi descartada sem contar; o B4 válido foi refeito numa linha só.

**Isolamento no frontend**: sem worktree e sem junction de `node_modules`. Cada mutação foi aplicada no arquivo real, `npx vitest run tests/permissoes` rodou (72 testes), e o arquivo foi restaurado com `git checkout -- <arquivo>`. Depois de cada uma, `git diff --quiet` e `git status --porcelain` estavam vazios e `git hash-object <arquivo>` era igual a `git rev-parse HEAD:<arquivo>` (o arquivo voltou com o CRLF do `core.autocrlf=true`).

| # | File:line | Descrição | Killed? |
| - | --------- | --------- | ------- |
| B1 | `core/permissions.py:32` | `EhAdministrador` aceita `is_staff` (`role == 'ADMIN' or is_staff`) | ✅ Killed (17 falhas: as 16 funções de `test_is_staff_sem_o_papel_recebe_403_em_cada_funcao` e `test_quem_nao_e_admin_recebe_403_mesmo_com_is_staff`) |
| B2 | `core/travas.py:229` | `Acesso.livre` ignora a liberação para testes (`return self.is_admin`) | ✅ Killed (34 falhas: rotas com a liberação ligada, `/auth/me`, limites, `acesso()` e o PATCH da liberação) |
| B3 | `core/travas.py:326` | `conferir_limite` com `>` no lugar de `>=` | ✅ Killed (9 falhas: os 6 limites, limite zero, subcategorias e "só cria com menos ativas") |
| B4 | `api/views.py:500` | Último admin sem proteção (`if not ids:` → `if True:`) | ✅ Killed (7 falhas: as 6 ações sobre o último admin e "admin arquivado não conta") |
| B5 | `reports/views.py:47` | `RecursoLiberado('calendario')` retirado da rota do calendário | ✅ Killed (1 falha: `test_calendario`) |
| F1 | `src/hooks/use-plan.ts:25` (FE) | `podeUsar` sempre verdadeiro com o `access` carregado | ✅ Killed (29 falhas) |
| F2 | `src/components/planos/recurso-bloqueado.tsx:33` (FE) | `RecursoBloqueado` renderiza o conteúdo com o recurso fechado | ✅ Killed (16 falhas) |
| F3 | `src/lib/erros.ts:103` (FE) | `tratarErro` não relê o `/auth/me` no 403 de plano | ✅ Killed (3 falhas: os dois códigos em `plano-pela-api` e a releitura em `releitura-do-acesso`) |

**Verificação do isolamento**: `git status --porcelain` vazio nos dois repositórios depois do sensor, exceto este `validation.md`. `git worktree list` mostra só a árvore principal nos dois, e a pasta `fluxar-backend-mut` não existe mais. Os únicos containers no ar são `fluxar-backend-backend-1` e `fluxar-backend-db-1` do compose.

**Sensor depth**: leve (8 mutações de comportamento, 5 no backend e 3 no frontend, por decisão do usuário)
**Result**: 8/8 killed, 0 survived - PASS

---

## Code Quality (nível leve, amostragem)

| Princípio | Status |
| --------- | ------ |
| Fonte única por lado | ✅ `core/travas.py` (catálogo, cache, `acesso`, `RecursoLiberado`, `conferir_limite`) e `EhAdministrador`; no frontend, `usePlan` lê só `user.access`. Sem `IsPremium`, `PlanLimitsService`, `IsAdminUser` nem `'FREE'` fora do `venv` |
| Reuso | ✅ cache de 30 s no padrão de `core/manutencao.py`; `garantir_admin_restante` unifica as três proteções antigas; `tratarErro` ganhou os dois códigos |
| Desvios documentados | ✅ `SPEC_DEVIATION` da leitura de cartões em `accounts/views.py:90`, `:127`, `cartoes/page.tsx:53` e `cartoes/[id]/page.tsx:41`, como no design |
| Testes mapeados aos ACs | ✅ docstrings e `describe` citam os IDs; asserções no corpo exato das respostas (`assert_travada`, `assert_limite`) |
| Testes antigos ajustados | ✅ só mocks de `access` em 4 arquivos do frontend, sem asserções removidas |
| Guidelines | AD-033 e AD-034 (testes no container e no vitest) seguidos |

---

## Observações (não bloqueiam)

1. **`gestao_do_salario` e `vinculos` sem rota nem tela.** As duas chaves estão no catálogo, no painel e no `/auth/me`, mas não há rota nem tela que as aplique; o design passa a aplicação para as specs `gestao-do-salario` e `vinculo-entre-transacoes`. O critério de sucesso "para cada trava, aviso na tela e 403 na rota" fica, para elas, pendente dessas specs. `personalizar_dashboard` é só de interface por definição da spec.
2. **PERM-22 pelo design.** A leitura de cartões e faturas segue liberada com `cartoes` fechado, contra a lista de rotas do catálogo (decisão `SPEC_DEVIATION` do design, em que PERM-22 prevalece). Os testes seguem o design (`tests/permissoes/test_travas_de_recurso.py:399-405`).
3. **Admin rebaixado obedecendo às travas.** A perda do painel é testada pela rota; obedecer às travas depois do rebaixamento decorre de `acesso()` ler o papel atual (`test_catalogo.py:116-120`, admin arquivado), sem um teste de rebaixamento seguido de 403 `plan_locked`.
4. **Concorrência no painel.** "Vale a última gravação e as duas ficam no log" é testado com gravações em sequência; o `select_for_update` em `gravar_trava` não tem teste simultâneo.
5. **PERM-06 sem mensagem na spec.** A spec define só o 400; o teste confere a mensagem do design, mais forte que a spec.
6. **Artefatos desatualizados.** O cabeçalho de `tasks.md` está `Status: In Progress`, e a rastreabilidade em `spec.md` está `Implemented`, sem `Verified`.
7. **Gates reduzidos.** Rodaram a suíte inteira do backend, o `makemigrations --check` e o `npm test`. `compileall`, `tsc`, lint e build não foram repetidos.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| PERM-01 a PERM-29 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (PASS)

**Spec-anchored check**: 29/29 ACs com evidência no valor da spec; nenhuma lacuna de precisão; 7 observações menores
**Sensor**: 8/8 mutações mortas (5 no backend, 3 no frontend)
**Gate**: backend 872 OK; frontend 270 testes OK

**Próximos passos**: opcionais. Um teste de admin rebaixado recebendo `plan_locked`, a aplicação de `gestao_do_salario` e `vinculos` nas specs delas, e a atualização do cabeçalho de `tasks.md` e dos status da rastreabilidade. Nenhum deles bloqueia.
