# Atualizacao de dependencias Specification

## Problem Statement

O backend roda o Django 5.1, sem correções de segurança desde dezembro de 2025, e o `pip-audit` de 2026-09-27 aponta vulnerabilidades em 12 pacotes instalados: Django, DRF, SimpleJWT, PyJWT, gunicorn, Pillow, python-dotenv, sqlparse, soupsieve, pip, setuptools e wheel. O frontend tem 7 vulnerabilidades no `npm audit --omit=dev` (1 crítica, 5 altas e 1 moderada): a crítica é no Next 16.0.10, com execução remota de código no Image Optimization, e as altas incluem o axios 1.13.2. O CI do frontend, como o do backend antes da feature de isolamento, nunca dispara (OPS-02), e nenhum dos dois confere vulnerabilidades.

Origem: SEG-04 na seção 3 de `docs/auditoria-2026-09.md` e o CI do frontend citado em OPS-02.

## Goals

- [ ] Nenhuma vulnerabilidade conhecida nas dependências de produção dos dois repositórios.
- [ ] Backend no Django 5.2 LTS, suportado até abril de 2028.
- [ ] Os dois CIs rodam em `main` e `development` e falham se aparecer vulnerabilidade nova.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Django 6 | Exige Python 3.12; o backend roda Python 3.11 no Dockerfile, no Render e no CI |
| Fixar versões exatas com `pip-tools` ou lockfile no backend | Muda o processo de build; as faixas passam a começar na versão corrigida |
| Atualizar pacotes sem vulnerabilidade | Sem ganho de segurança e com risco de quebra |
| `DEFAULT_FILE_STORAGE`, que o Django ignora desde a 5.1 | Não muda com esta atualização; fica registrado como achado |
| Testes automatizados no frontend | O frontend não tem testes; os gates são auditoria, TypeScript, lint e build |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Faixas no `requirements.txt` | Mínimo na versão corrigida e teto na próxima versão menor ou maior, conforme o pacote | Mantém o formato atual do arquivo e impede instalar uma versão vulnerável | padrão do agente |
| Pacotes transitivos com vulnerabilidade (sqlparse, soupsieve) | Declarados no `requirements.txt` com o mínimo corrigido | Sem lockfile, é o único jeito de impedir a versão vulnerável | padrão do agente |
| pip, setuptools e wheel | Atualizados no Dockerfile antes da instalação | São ferramentas da imagem, não dependências da aplicação | padrão do agente |
| Versão do Next | 16.3.6, a sugerida pelo `npm audit fix --force`, e o `eslint-config-next` na mesma versão | Menor salto que resolve a crítica | padrão do agente |
| React | Mantido em 19.2.1 | O `npm audit` não aponta nada nele, e o Next 16.3.6 aceita React 19 | padrão do agente |
| Auditoria no CI | `pip-audit -r requirements.txt` no backend e `npm audit --omit=dev --audit-level=moderate` no frontend | Falha o CI com qualquer vulnerabilidade moderada ou pior nas dependências de produção | padrão do agente |

**Open questions:** none. O usuário pediu a atualização em 2026-09-27 e autorizou seguir no automático; as suposições são padrões do agente, a partir da correção sugerida no SEG-04.

---

## User Stories

### P1: Dependências sem vulnerabilidades conhecidas ⭐ MVP

**User Story**: Como mantenedor do Fluxar, quero as dependências dos dois repositórios sem vulnerabilidades conhecidas e em versões suportadas.

**Why P1**: há uma vulnerabilidade crítica de execução remota no Next e o framework do backend está fora de suporte (SEG-04).

**Acceptance Criteria**:
1. **DEPS-01** WHEN o `pip-audit` roda sobre o ambiente de produção do backend THEN o sistema SHALL não apresentar nenhuma vulnerabilidade conhecida.
2. **DEPS-02** WHILE o backend estiver em produção, o sistema SHALL rodar numa versão do Django 5.2 igual ou superior à 5.2.17.
3. **DEPS-03** WHEN a suíte de testes do backend roda depois da atualização THEN o sistema SHALL passar em todos os testes, sem alterar nenhum deles.
4. **DEPS-04** WHEN o `npm audit --omit=dev` roda no frontend THEN o sistema SHALL não apresentar nenhuma vulnerabilidade.
5. **DEPS-05** WHEN o frontend é verificado depois da atualização THEN o sistema SHALL passar no TypeScript sem erros, no lint sem erros novos e no build.

**Independent Test**: rodar `pip-audit` na imagem do backend e `npm audit --omit=dev` no frontend, os dois sem vulnerabilidades; a suíte do backend passa e o build do frontend termina.

---

### P1: CI que confere as dependências ⭐ MVP

**User Story**: Como mantenedor, quero que os dois CIs rodem em todo PR e falhem se uma dependência vulnerável entrar.

**Why P1**: o CI do frontend nunca dispara, e nenhum dos dois confere vulnerabilidades (OPS-02, SEG-04).

**Acceptance Criteria**:
1. **DEPS-06** WHEN um push ou PR chega a `main` ou `development` no frontend THEN o sistema SHALL rodar o CI do frontend, com instalação, auditoria, lint e build.
2. **DEPS-07** IF o `npm audit --omit=dev` do frontend encontrar vulnerabilidade moderada ou pior THEN o sistema SHALL falhar o CI do frontend.
3. **DEPS-08** IF o `pip-audit` do backend encontrar vulnerabilidade THEN o sistema SHALL falhar o CI do backend.

**Independent Test**: os workflows dos dois repositórios disparam em `development`, têm o passo de auditoria e os comandos desse passo, rodados localmente, terminam sem erro.

---

## Edge Cases

- Uma vulnerabilidade publicada depois do merge faz o CI falhar sem mudança no código: é o comportamento esperado de DEPS-07 e DEPS-08.
- Vulnerabilidade sem versão corrigida: fica registrada no PR e, se preciso, ignorada no CI com o ID e o motivo.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| DEPS-01 | P1: Dependências sem vulnerabilidades conhecidas | Execute | Pending |
| DEPS-02 | P1: Dependências sem vulnerabilidades conhecidas | Execute | Pending |
| DEPS-03 | P1: Dependências sem vulnerabilidades conhecidas | Execute | Pending |
| DEPS-04 | P1: Dependências sem vulnerabilidades conhecidas | Execute | Pending |
| DEPS-05 | P1: Dependências sem vulnerabilidades conhecidas | Execute | Pending |
| DEPS-06 | P1: CI que confere as dependências | Execute | Pending |
| DEPS-07 | P1: CI que confere as dependências | Execute | Pending |
| DEPS-08 | P1: CI que confere as dependências | Execute | Pending |

**Coverage:** 8 total, 8 mapped to Execute, 0 unmapped

---

## Success Criteria

- [ ] `pip-audit` e `npm audit --omit=dev` sem vulnerabilidades.
- [ ] 175 testes do backend passando no Django 5.2.
- [ ] Build do frontend passando no Next 16.3.6.
