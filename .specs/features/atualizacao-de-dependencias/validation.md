# Atualizacao de dependencias Validation

## Validation: atualizacao-de-dependencias (rodada 1, tier leve) - PASS ✅

**Date**: 2026-09-27
**Spec**: `.specs/features/atualizacao-de-dependencias/spec.md`
**Diff range (backend)**: `development..HEAD` na branch `chore/atualiza-dependencias`, HEAD `560096d` (`4da3466` spec, `da9e355` Django 5.2/DRF 3.18/SimpleJWT 5.5, `3c66ad2` demais pacotes, `560096d` CI).
**Diff range (frontend)**: `development..HEAD` na branch `chore/atualiza-dependencias`, HEAD `6b8dbd6` (`db8ed4f` Next 16.3.6 e axios 1.20, `6b8dbd6` CI).
**Verifier**: sub-agente independente (autor ≠ verificador), evidence-or-zero, tier leve a pedido do usuário (7 mutações, uma rodada).

Resumo: as oito ACs têm evidência. A imagem do backend e o `requirements.txt` passam no `pip-audit` sem nenhuma vulnerabilidade, o Django instalado é o 5.2.17 e os 175 testes passam sem nenhuma mudança em `tests/`. O frontend tem 0 vulnerabilidades no `npm audit --omit=dev`, 0 erros no `tsc`, os mesmos 168 erros de lint da auditoria e o build passa no Next 16.3.6. Os dois workflows disparam em `main` e `development` e têm o passo de auditoria. O sensor matou as 7 mutações. O handler de exceção novo é necessário e só restaura o corpo do 404 que o projeto tinha antes da atualização.

---

## Task Completion

Não há `tasks.md` nesta feature; a spec vai direto para Execute. Os commits do range cobrem todas as mudanças que a spec pede:

| Mudança | Commit | Evidência |
| ------- | ------ | --------- |
| Faixas novas no `requirements.txt` | `da9e355`, `3c66ad2` | `requirements.txt:2`, `:4`, `:5`, `:7`, `:8`, `:9`, `:11`, `:21`, `:24` |
| pip, setuptools e wheel atualizados na imagem | `3c66ad2` | `Dockerfile:21` |
| Handler de 404 para o DRF 3.18 | `da9e355` | `core/exceptions.py:6-16`, `core/settings.py:180` |
| Auditoria no CI do backend | `560096d` | `.github/workflows/ci-backend.yml:51-55` |
| Next 16.3.6, eslint-config-next 16.3.6, axios 1.20 | `db8ed4f` | `package.json:27`, `:33`, `:51`; `package-lock.json:3839-3840`, `:6753-6754` |
| CI do frontend nos dois branches, com auditoria e tsc | `6b8dbd6` | `.github/workflows/ci-frontend.yml:3-7`, `:25-30` |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | Evidência (comando + resultado, ou file:line) | Result |
| -- | -------------------- | --------------------------------------------- | ------ |
| DEPS-01 | `pip-audit` no ambiente de produção sem vulnerabilidade | `docker run --rm fluxar-backend-backend sh -c "pip install -q pip-audit && pip-audit && pip-audit -r requirements.txt"`: `No known vulnerabilities found` nos dois, exit 0. Versões na imagem: Django 5.2.17, DRF 3.18.1, PyJWT 2.15.0, gunicorn 26.2.0, Pillow 12.3.0, sqlparse 0.6.0, soupsieve 2.10, python-dotenv 1.2.3, pip 26.2.1, setuptools 84.0.0, wheel 0.48.0. Faixas: `requirements.txt:2-24`; ferramentas: `Dockerfile:21` | ✅ PASS |
| DEPS-02 | Django 5.2, versão ≥ 5.2.17 | `docker compose exec -T backend python -c "import django; print(django.get_version())"` → `5.2.17`. Faixa `Django>=5.2.17,<5.3` em `requirements.txt:2` impede instalar versão menor ou a 6 | ✅ PASS |
| DEPS-03 | Todos os testes passam, nenhum alterado | Gate do backend: `Ran 175 tests ... OK`, exit 0. `git diff --stat development..HEAD -- tests/` vazio: nenhum arquivo de teste mudou | ✅ PASS |
| DEPS-04 | `npm audit --omit=dev` com 0 vulnerabilidades | `npm audit --omit=dev` → `found 0 vulnerabilities`, exit 0. Instalado: next 16.3.6, axios 1.20.0, eslint-config-next 16.3.6, react 19.2.1 (`npm ls --depth=0`); `package.json:27`, `:33` | ✅ PASS |
| DEPS-05 | tsc sem erros, lint sem erros novos, build passa | `npx tsc --noEmit -p . --incremental false` → exit 0, sem saída. `npm run lint` → 168 erros e 250 avisos; os erros batem regra por regra com o Apêndice A de `docs/auditoria-2026-09.md:1062-1075` (132 `no-explicit-any`, 18 `no-unescaped-entities`, 4 `prefer-const`, 4 `no-var`, 4 `ban-ts-comment`, 3 `set-state-in-effect`, 2 `no-empty-object-type`, 1 `immutability`). Os 3 avisos a mais vêm de uma regra nova do eslint-config-next 16.3 (`@next/next/no-location-assign-relative-destination`), que só gera aviso. `NEXT_PUBLIC_API_URL=http://build-check-placeholder npm run build` → `Next.js 16.3.6 (Turbopack)`, `Compiled successfully`, 30/30 páginas, exit 0 | ✅ PASS |
| DEPS-06 | CI do frontend roda em push/PR para `main` e `development`, com instalação, auditoria, lint e build | `.github/workflows/ci-frontend.yml:3-7` (push e pull_request em `[ main, development ]`, sem filtro `paths`); instalação `:22-23`; auditoria `:25-27`; tsc `:29-30`; lint `:32-35`; build `:37-41`. O `working-directory: ./fluxar-frontend` e o `cache-dependency-path` do layout antigo de monorepo saíram, então os passos rodam na raiz do repo, onde está o `package.json`. `npm ci --dry-run` local: exit 0 | ✅ PASS (ver nota 1) |
| DEPS-07 | `npm audit --omit=dev` com vulnerabilidade moderada ou pior falha o CI | `.github/workflows/ci-frontend.yml:27`: `npm audit --omit=dev --audit-level=moderate`, sem `continue-on-error`. Comando rodado localmente: exit 0. Mutações F1, F2 e F3 (abaixo): exit 1 com alta, crítica e só moderada; com `--audit-level=high`, a moderada passaria (exit 0), então o limiar `moderate` é o que pega esse caso | ✅ PASS |
| DEPS-08 | `pip-audit` com vulnerabilidade falha o CI do backend | `.github/workflows/ci-backend.yml:51-55`: `pip install pip-audit` e `pip-audit -r requirements.txt`, sem `continue-on-error`; o workflow já dispara em `main` e `development` (`:3-7`). Comando rodado localmente: exit 0. Mutações B2, B3 e B4: exit 1 | ✅ PASS |

**Status**: ✅ Todas as 8 ACs com evidência. Nenhum spec-precision gap.

---

## Handler de exceção (`core/exceptions.py`)

**É necessário.** No DRF 3.18 instalado na imagem, o `exception_handler` padrão faz `exceptions.NotFound(*(exc.args))` e repassa a mensagem do Http404. O `get_object_or_404` do DRF (`rest_framework/generics.py:13-21`) levanta um Http404 sem mensagem quando o ID não converte para o tipo da PK, e deixa passar a mensagem do Django (`No Goal matches the given query.`) quando converte. `Goal` tem PK inteira, e o `ID_INEXISTENTE` dos testes é um UUID (`tests/isolamento/base.py:79`). Por isso, a meta de B responde `No Goal matches the given query.` e o ID inexistente responde `Not found.`. A mutação B1, que remove `core/settings.py:180`, derruba `test_meta_de_b` com exatamente essa diferença (`tests/isolamento/test_endereco_filtros.py:57`, `assertEqual(resp.data, resp_inexistente.data)`). Sem o handler, o DEPS-03 cai e o ISOL-12 regride.

**Está correto.** `core/exceptions.py:14-16` troca qualquer Http404 por `NotFound()` com a mensagem padrão e delega o resto ao handler do DRF. É o corpo que o projeto tinha antes da atualização: os mesmos testes, sem mudança, passavam no `development`. 

**Não muda outro comportamento.** O handler só mexe em Http404; status, cabeçalhos, `set_rollback` e os demais `APIException` seguem pelo handler do DRF. O DRF 3.15+ também passou a repassar a mensagem do `PermissionDenied` do Django, e o handler não trata esse caso. O projeto, porém, só levanta o `PermissionDenied` do DRF (`api/views.py:450`, `:456`), que já é um `APIException` e não passa por essa conversão, então nada muda aqui. As quatro chamadas a `django.shortcuts.get_object_or_404` em `api/views.py:570`, `:593`, `:626`, `:662` (painel admin, `User`) voltam a responder `Not found.`, como antes da atualização.

---

## Discrimination Sensor

Todas as mutações rodaram só em cópias descartáveis (`git worktree add --detach <scratchpad>/wt-back HEAD` e `.../wt-front HEAD`), removidas depois com `git worktree remove --force` e `git worktree prune`. Nenhuma usou `git stash`.

| # | Alvo | Mutação | Comando | Resultado | Killed? |
| - | ---- | ------- | ------- | --------- | ------- |
| B1 | `core/settings.py:180` | Remove `'EXCEPTION_HANDLER'` | `docker run --rm --network fluxar-backend_default --env-file .env -e DB_HOST=db -v <wt-back>:/app fluxar-backend-backend python manage.py test tests.isolamento --noinput` | `FAILED (failures=1)`: `test_meta_de_b`, `No Goal matches the given query.` ≠ `Not found.` | ✅ Killed |
| B2 | `requirements.txt:2` | `Django>=5.2.17,<5.3` → `Django==5.1.15` | `pip-audit -r req-b2.txt` em container avulso | exit 1, 7 achados (PYSEC-2026-199 a PYSEC-2026-3717) | ✅ Killed |
| B3 | `requirements.txt:9` | `sqlparse>=0.6.0,<0.7` → `sqlparse==0.5.4` | `pip-audit -r req-b3.txt` | exit 1, 9 achados (PYSEC-2026-3696 a 3923) | ✅ Killed |
| B4 | `requirements.txt:11` | `gunicorn>=22.0,<27.0` → `gunicorn>=21.2,<22.0` (faixa antiga) | `pip-audit -r req-b4.txt` | exit 1, 4 achados (PYSEC-2026-1433 e 1434) | ✅ Killed |
| F1 | `package.json:27` + lockfile | axios → 1.13.2 (`npm install axios@1.13.2 --package-lock-only`) | `npm audit --omit=dev --audit-level=moderate` | exit 1, `1 high severity vulnerability` (axios 1.0.0 - 1.17.0) | ✅ Killed |
| F2 | `package.json:33` + lockfile | next → 16.0.10 | `npm audit --omit=dev --audit-level=moderate` | exit 1, `3 vulnerabilities (2 high, 1 critical)` (next até 16.3.2, sharp) | ✅ Killed |
| F3 | `package.json` + lockfile | Adiciona `follow-redirects@1.15.11` (só moderada) | `npm audit --omit=dev --audit-level=moderate` | exit 1, `1 moderate severity vulnerability`; controle com `--audit-level=high`: exit 0 | ✅ Killed |

Controles sem mutação: `pip-audit -r requirements.txt` exit 0; `npm audit --omit=dev --audit-level=moderate` exit 0 na cópia.

**Sensor depth**: leve (tier pedido pelo usuário).
**Result**: 7/7 killed - PASS ✅

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ O único código novo é o handler de 16 linhas, exigido pelo DRF 3.18 (ver acima) |
| Surgical changes | ✅ Só arquivos de dependência, Dockerfile, workflows, settings e o handler |
| No scope creep | ✅ Nenhum pacote sem vulnerabilidade foi atualizado; React ficou em 19.2.1, como a spec pede |
| Matches patterns | ✅ Faixas no mesmo formato do `requirements.txt`; comentários em português como no resto |
| Spec-anchored outcome check | ✅ Cada AC conferida contra o comando ou valor da spec |
| Per-layer Coverage Expectation | ✅ n/a para testes novos (a spec proíbe mudar os testes); gates e sensor cobrem as ACs |
| Every test maps to a spec requirement | ✅ Nenhum teste novo |
| Documented guidelines followed | ✅ `.specs/` e `docs/auditoria-2026-09.md` |

---

## Edge Cases

- [x] Uma vulnerabilidade publicada depois do merge faz o CI falhar sem mudança no código: os dois passos de auditoria rodam a cada push/PR, sem cache de resultado e sem `continue-on-error` (`ci-backend.yml:51-55`, `ci-frontend.yml:25-27`). As mutações B2 a B4 e F1 a F3 mostram que os comandos saem com código diferente de 0 quando há achado.
- [x] Vulnerabilidade sem versão corrigida: não apareceu nenhuma; os dois comandos rodam sem `--ignore-vuln` nem exceção, o que está coerente com isso.

---

## Gate Check

- **Backend**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"` → exit 0, `Ran 175 tests in 21.902s`, `OK`. 0 falhas, 0 pulados.
- **Test count antes / depois**: 175 / 175 (a spec cita 175; `tests/` sem diff). Delta 0.
- **Frontend**: `npm audit --omit=dev` 0 vulnerabilidades; `tsc` exit 0; lint 168 erros (igual ao baseline, exit 1 esperado); build exit 0.
- **Porcelain**: `git status --porcelain` vazio nos dois repositórios antes da verificação, depois do build (o `.next/` é ignorado pelo git) e depois do sensor. A única mudança no fim é este arquivo.

---

## Notas (não bloqueiam)

1. **Lint com `continue-on-error` (`ci-frontend.yml:32-35`).** O DEPS-06 pede que o CI rode o lint, e ele roda. Mas, como o passo não bloqueia, o CI não barra erro de lint novo; o "sem erros novos" do DEPS-05 só foi conferido nesta verificação, à mão. É uma decisão consciente enquanto os 168 erros do MAN-04 não saem, e o comentário na linha 33 registra isso. Quando o MAN-04 for resolvido, vale tirar o `continue-on-error`.
2. **`pip-audit -r` resolve de novo as dependências.** No CI e no sensor, `pip-audit -r requirements.txt` monta um ambiente temporário com as versões mais novas dentro das faixas, e não confere o ambiente instalado. Os pisos dos transitivos (sqlparse, soupsieve) importam para a instalação, não para esse comando. O ambiente real foi conferido à parte, com `pip-audit` sem `-r` na imagem (DEPS-01). O pip, o setuptools e o wheel do runner do CI também ficam fora do `-r`; o Dockerfile cuida deles na imagem.
3. **O corpo `Not found.` não está fixado em teste.** Os testes do ISOL-12 comparam a resposta do ID de B com a do ID inexistente (`test_endereco_filtros.py:57`), não com o texto literal. Uma mutação que trocasse a mensagem por outra constante passaria nos testes; não rodei essa mutação porque nenhuma AC desta spec fixa o texto. Só importa se o frontend depender da string.
4. **Três avisos novos de lint** (`@next/next/no-location-assign-relative-destination`, uso de `window.location.href` para páginas internas) vêm do eslint-config-next 16.3.6. São só avisos e não contam para o DEPS-05.
5. **Node no CI.** O `setup-node` usa `node-version: '20'` (`ci-frontend.yml:19`), e o Next 16.3.6 exige `>=20.9.0` (`node_modules/next/package.json:136-137`). A última versão da linha 20 atende.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| DEPS-01 | Pending | ✅ Verified |
| DEPS-02 | Pending | ✅ Verified |
| DEPS-03 | Pending | ✅ Verified |
| DEPS-04 | Pending | ✅ Verified |
| DEPS-05 | Pending | ✅ Verified |
| DEPS-06 | Pending | ✅ Verified |
| DEPS-07 | Pending | ✅ Verified |
| DEPS-08 | Pending | ✅ Verified |

(O verificador não edita a `spec.md`; a atualização dos status fica para o orquestrador.)

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 8/8 ACs com evidência, 0 spec-precision gaps
**Sensor**: 7/7 mutações mortas
**Gate**: backend 175 passando; frontend audit 0, tsc 0, lint 168 (= baseline), build OK

**What works**: backend sem vulnerabilidade no Django 5.2.17 LTS, com a suíte intacta; frontend sem vulnerabilidade no Next 16.3.6; os dois CIs disparam em `main` e `development` e falham com vulnerabilidade.

**Issues found**: nenhum bloqueante. Notas 1 a 5 acima.

**Next steps**: atualizar os status na `spec.md` e abrir os PRs. Quando o MAN-04 for resolvido, tirar o `continue-on-error` do lint.

**Lessons**: PASS limpo, sem mutante sobrevivente, AC sem cobertura ou spec-precision gap; nenhuma lição registrada.

---

## validate_state

`python "C:/Users/Carlos Vale/.claude/skills/tlc-spec-driven/scripts/validate_state.py" atualizacao-de-dependencias --root "C:/Users/Carlos Vale/projetos/my_projects/fluxar/fluxar-backend"` → `validate_state: 0 error(s) across [atualizacao-de-dependencias]`, exit 0.
