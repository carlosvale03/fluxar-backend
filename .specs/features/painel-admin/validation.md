# Painel admin Validation

**Verdict: PASS**

Verificação leve feita por um verificador independente (autor ≠ verificador): conferência das 29 ACs contra a spec e um sensor de discriminação com 8 mutações de comportamento. Nenhuma mutação sobreviveu. Os gaps abaixo são de precisão da spec, de consistência de rótulo e de cobertura fina; nenhum deles derruba uma AC.

## Diff ranges

| Repo | Branch | Range | Commits |
| ---- | ------ | ----- | ------- |
| fluxar-backend | `fix/painel-admin-dados-reais-log-e-limpeza` | `development (d3c626e)..HEAD (8c23399)` | 18 |
| fluxar-frontend | `fix/painel-admin-dados-reais-log-e-limpeza` | `development (fca1c2f)..HEAD (0ef3d3f)` | 6 |

Baseline: `tests.painel_admin` no backend com 78 testes OK (Postgres do `docker compose`); `tests/painel-admin` no frontend com 34 testes OK em 6 arquivos; a suíte inteira do frontend com 382 testes OK em 73 arquivos.

## Evidência por AC

Backend em `tests/painel_admin/`; frontend em `tests/painel-admin/`.

### Telas sem dados falsos

| AC | Evidência |
| -- | --------- |
| ADMIN-01 | frontend `detalhe-do-usuario.test.tsx:83` (500: erro na tela, nenhum dado e nenhuma ação habilitada), `:102` ("Tentar de novo" recarrega) |
| ADMIN-02 | backend `test_dashboard.py:69` (latência inteira e versão do servidor medidas), `:83` (banco com erro: `error`, sem latência nem versão); frontend `dashboard.test.tsx:55`, `:66`; `configuracoes.test.tsx:49` |
| ADMIN-03 | backend `test_dashboard.py:96`, `:102`, `:105`, `:109` (AD-051); frontend `configuracoes.test.tsx:49`, `:78` (API fora: "Sem dados", nada de "1.2.5") |
| ADMIN-04 | frontend `configuracoes.test.tsx:61` (sem "Uptime", "PostgreSQL 15.4", "Build" nem "Limpar Cache"; só manutenção, liberação e travas) |
| ADMIN-05 | backend `test_dashboard.py:46` (sem `estimated_revenue`, `conversion_rate`, "19.90"); `tests/contratos/test_dinheiro.py` ajustado; frontend `dashboard.test.tsx:76` |
| ADMIN-06 | frontend `detalhe-do-usuario.test.tsx:115` |
| ADMIN-07 | backend `test_dashboard.py:26`, `:40`, `:57`; frontend `dashboard.test.tsx:43` (rótulo "Usuários em planos pagos") |

### Log de auditoria

| AC | Evidência |
| -- | --------- |
| ADMIN-08 | backend `test_log_das_acoes.py:37` (COMMON → PREMIUM), `:45` (um registro por campo), `:55`, `:61` (status), `:69`, `:78` (arquivar, também em lote), `:94` (senha sem o valor no log), `:108` (exclusão pelas duas rotas), `:135` (exclusão que falha não deixa registro); `test_limpeza.py:83` (CLEAR_DATA) |
| ADMIN-09 | backend `test_log_das_configuracoes.py:32` (manutenção), `:41` (mesmo valor não registra), `:53` (liberação), `:60` (trava), `:70` (limite, nulo para sem limite), `:80` (aparece na API do log) |
| ADMIN-10 | backend `test_log_estruturado.py:17`, `:28` (nenhum campo com nome ou e-mail completo), `:36`; o `assert_sem_dado_pessoal` de `base.py:48` roda em todos os testes de ação |
| ADMIN-11 | backend `test_log_estruturado.py:48` (só o id interno depois da exclusão); `test_log_das_acoes.py:108`; `test_exclusao_pelo_admin.py:95` (registro da exclusão e `DELETE_ACCOUNT`) |
| ADMIN-12 | backend `test_consulta_do_log.py:46` (mais recente primeiro), `:98` (20 por página); frontend `log.test.tsx:136` (navegação mantém os filtros) |
| ADMIN-13 | backend `test_consulta_do_log.py:52`, `:63`, `:70` (dias inteiros em Brasília), `:78` (data ou admin inválido: 400 no campo), `:94`; frontend `log.test.tsx:106`, `:116`, `:126`, `:162` |
| ADMIN-14 | backend `test_consulta_do_log.py:116` (usuário excluído continua consultável), `test_log_estruturado.py:63`; frontend `log.test.tsx:198` |
| ADMIN-15 | backend `test_consulta_do_log.py:134` (POST, PUT, PATCH e DELETE nas duas rotas: 405, registro intacto) |

### Operações sobre usuários

| AC | Evidência |
| -- | --------- |
| ADMIN-16 | backend `test_busca_de_usuarios.py:29` (Independent Test "maria" + Premium), `:35`, `:40`, `:46`, `:53` (paginado); frontend `lista-de-usuarios.test.tsx:86`, `:94`, `:108`, `:116` |
| ADMIN-17 | backend `test_senha_do_admin.py:45` (papel), `:48` (desativar), `:51`, `:56`, `:59` (arquivar, também em lote), `:64` (limpar), `:67` (redefinir), `:73` (excluir pelas duas rotas), `:78`; frontend `confirmacoes.test.tsx:184`, `:211`, `:223`, `:248` |
| ADMIN-18 | backend `test_senha_do_admin.py` pelo `assert_recusa_sem_senha_e_com_senha_errada` (sem senha, vazia, errada: 403 `{admin_password: ["Senha do administrador incorreta."]}` e estado inalterado); frontend `confirmacoes.test.tsx:153`, `:223` (o 403 aparece no campo e a janela continua aberta) |
| ADMIN-19 | backend `test_senha_do_admin.py:91`, `:108`, `:117`; frontend `confirmacoes.test.tsx:138` (sem campo de senha e sem `admin_password` na requisição), `:236` |
| ADMIN-20 | frontend `confirmacoes.test.tsx:98` (limpar: lista do que é apagado, só com o e-mail exato e a senha), `:119` (excluir) |
| ADMIN-21 | backend `test_limpeza.py:83` (300 transações e dados em todas as partes; outro usuário intacto), `:193` (completude: todo modelo de `MODELOS_DO_USUARIO` é apagado ou mantido) |
| ADMIN-22 | backend `test_limpeza.py:83`, `:110` (duas vezes, um único padrão); `test_padrao_do_cadastro.py:53`, `:58`, `:65` |
| ADMIN-23 | backend `test_limpeza.py:118` (e-mail, senha, perfil, plano, papel, sessões, aceite e login funcionando) |
| ADMIN-24 | backend `test_limpeza.py:138` (só a imagem da meta, o avatar fica), `:145` (Cloudinary falhando ou recusando: 503 e nada apagado) |
| ADMIN-25 | backend `test_limpeza.py:161` (falha forçada no meio: 500 e as 300 transações continuam) |
| ADMIN-26 | backend `test_limpeza.py:253`, `:258` (duas threads com conexões próprias) |
| ADMIN-27 | backend `test_limpeza.py:175` |
| ADMIN-28 | backend `test_exclusao_pelo_admin.py:78` (compra parcelada, fatura paga, transferência e meta com aportes, criados pela API; pelas duas rotas), `:95` |
| ADMIN-29 | backend `test_estatisticas_financeiras.py:49` (bate com o dashboard do usuário), `:71` (sem ajuste de saldo), `:82` (sem conta excluída), `:98` (parcela pela data do relatório) |

## Discrimination sensor

Backend: mutações aplicadas num worktree destacado (`../fluxar-backend-mut`, removido depois), testes rodados num container de uma imagem temporária (a do projeto mais o `requirements.txt`, por falta do `cryptography`; apagada depois), na rede `fluxar-backend_default`. Frontend: mutação no arquivo real, `vitest run` do arquivo de teste, e `git checkout` em seguida.

| # | Repo | Mutação | Resultado | Testes que pegaram |
| - | ---- | ------- | --------- | ------------------ |
| B1 | backend | `limpar_dados` sem o `select_for_update` na linha do usuário | killed | `test_limpeza.py:258` |
| B2 | backend | `limpar_dados` sem o `transaction.atomic` (e sem a trava) | killed | `test_limpeza.py:161`, `:253`, `:258` |
| B3 | backend | mudar o papel deixa de pedir a senha (só desativar pede) | killed | `test_senha_do_admin.py:45`, `:51` (8 falhas com os subtestes) |
| B4 | backend | `registrar` grava o e-mail completo do usuário afetado | killed | `test_log_das_acoes.py:37`, `:45`, `:61`, `:69`, `:94`; `test_log_estruturado.py:17`, `:28`, `:63` |
| B5 | backend | estatísticas financeiras contam as transações de contas excluídas | killed | `test_estatisticas_financeiras.py:82` |
| F1 | frontend | mudar o plano no detalhe envia `admin_password` | killed | `confirmacoes.test.tsx:138` |
| F2 | frontend | `emailConfere` aceita qualquer texto não vazio | killed | `confirmacoes.test.tsx:98`, `:119` |
| F3 | frontend | o detalhe com erro de carga renderiza as ações habilitadas | killed | `detalhe-do-usuario.test.tsx:83` |

**Score: 8/8 killed.**

Observação sobre B1: só o teste do usuário sem dados (`:258`) pegou. No usuário com dados (`:253`), os `DELETE` concorrentes já se bloqueiam nas linhas das transações, então a falta da trava não aparece. A trava continua discriminada, mas por um único teste.

## Perguntas específicas

**Rótulo do plano COMMON ("Gratuito").** É uma inconsistência. O backend chama o plano de "Comum" (`api/models.py:42`, `('COMMON', 'Comum')`), a spec `permissoes-e-planos` usa "Comum" em PERM-10 e no Independent Test da liberação para testes ("Plano Comum", `spec.md:178`), a spec do painel admin diz "de Comum para Premium" no Independent Test do log, e o app usa `nomeDoPlano` de `src/hooks/use-plan.ts:7` com "Comum". O painel admin usa "Gratuito" em cinco lugares: `admin/dashboard/page.tsx:15` ("Plano Gratuito"), `admin/usuarios/page.tsx:378`, `admin/usuarios/[id]/page.tsx:65` e `:367`, e `admin/_componentes/log-de-auditoria.tsx:29`. Só o da lista existia antes desta branch; os outros quatro entraram nela. O teste `log.test.tsx:147` fixa "Antes:Gratuito". Ver gap 1.

**`tratarErro` com 403 por campo.** A ordem dos ramos é a mesma de antes (`src/lib/erros.ts`): cancelamento, sem resposta ou 5xx, `terms_acceptance_required` (volta cedo), `plan_locked`/`plan_limit_reached`, e o `detail` em texto. Só depois vem o ramo por campo, que agora aceita 400 ou 403. Um 403 com `detail` continua indo para o toast do `detail`, e os dois códigos de plano continuam antes. Nenhum teste existente perdeu cobertura: `tests/contratos/tratamento-de-erros.test.ts:65`, `tests/permissoes/plano-pela-api.test.tsx:151` e `:183`, e `tests/lgpd/aceite-dos-termos.test.tsx:109` seguem passando, e a suíte inteira do frontend fica verde (382 testes). O novo ramo é coberto só de forma indireta, por `confirmacoes.test.tsx:153` e `:223`. Ver gap 4.

**Valores fixos que sobraram no frontend do admin.** A busca por "Mock", "Uptime", "PostgreSQL", "1.2.5", "Limpar Cache", "HEALTH CHECK", "ASSINATURAS", "TRX", "29,90", "Operacional", "Online" e "Conectado" em `src/app/(admin)`, `src/components/admin` e `src/services/admin.ts` só encontra `src/components/admin/saude-do-sistema.tsx`: "Operacional" nas linhas 33 e 53 e "PostgreSQL {banco.version}" na linha 63. Os dois dependem da resposta da API ("Operacional" só com `status` `ok`, "Sem dados" sem resposta, "Com erro" com `error`; a versão vem de `health.database.version`). Não são valores fixos. Os outros termos não aparecem em nenhum lugar de `src`.

**Reativar sem a senha.** Não viola a spec. ADMIN-17 lista "desativa um usuário", não a reativação; ADMIN-19 fala só do plano. A reativação não aparece em nenhuma AC. O `design.md:147` e a T5 do `tasks.md:206` registram que reativar não pede senha, então o desvio está documentado, não escondido. O backend testa isso (`test_senha_do_admin.py:99`), e a lista no frontend reativa sem senha (`admin/usuarios/page.tsx:212-218`), mas sem teste no frontend. A spec é que está incompleta. Ver gap 2.

## Gaps (por prioridade)

1. **O painel chama o plano COMMON de "Gratuito"; o resto do sistema chama de "Comum".** Correção: trocar os rótulos locais por `nomeDoPlano` de `src/hooks/use-plan.ts` em `admin/dashboard/page.tsx:15` ("Plano Comum"), `admin/usuarios/page.tsx:378`, `admin/usuarios/[id]/page.tsx:65` e `:367`, e `admin/_componentes/log-de-auditoria.tsx:29`, e atualizar `tests/painel-admin/log.test.tsx:147` para "Antes:Comum".
2. **A reativação não está na spec (precisão da spec).** Correção: acrescentar à ADMIN-19 "ou reativa a conta de um usuário", que é o que o `design.md:147` e o código fazem. Opcional: um teste no frontend que confirme que a restauração na lista envia `{ is_active: true }` sem `admin_password`.
3. **ADMIN-21 e ADMIN-22 estão marcadas como Implemented, mas dependem de modelos que ainda não existem (precisão da spec).** As classes Essencial e Dispensável (CLASSE-01, CLASSE-24), o plano da gestão do salário e os vínculos entre transações não existem no código; `criar_padrao_do_cadastro` (`transactions/padrao.py:39`) cria só as categorias e a Carteira. O `design.md:158` e `:275` explicam que eles entram pela estrutura (`MODELOS_DO_USUARIO` e a função única do padrão), e o teste de completude (`test_limpeza.py:193`) garante a limpeza. Correção: na rastreabilidade da spec, marcar ADMIN-21 e ADMIN-22 como "Implemented (classes, salário e vínculos entram com as specs classes-de-despesa, gestao-do-salario e vinculo-entre-transacoes)", e lembrar nessas specs de acrescentar a recriação das classes em `criar_padrao_do_cadastro` com um teste de limpeza.
4. **O ramo novo do `tratarErro` não tem teste unitário próprio.** Correção: em `tests/contratos/tratamento-de-erros.test.ts`, um caso de 403 `{admin_password: [...]}` com `form` e `campos` (vai para o campo, sem toast) e um de 403 com `detail` e campos juntos (continua no toast do `detail`). Efeito colateral a registrar: um 403 sem `detail` e sem campo do formulário, por exemplo `{code: "x"}`, agora mostra o texto do código no toast em vez da mensagem padrão; o DRF sempre manda `detail` no 403, então é teórico.
5. **O registro `CLEAR_DATA` é gravado fora da transação da limpeza.** `AdminClearUserDataView` fica fora da transação por requisição e chama `registrar` depois de `limpar_dados` terminar (`api/views.py`, `AdminClearUserDataView.post`). Se a gravação do log falhar, os dados já foram limpos sem registro, o que contraria a meta "toda ação de administrador fica registrada". Correção: passar o administrador para `limpar_dados` e gravar o `CLEAR_DATA` dentro do mesmo `atomic`, depois de `criar_padrao_do_cadastro`.
6. **O filtro de administrador do log só lista administradores ativos, até 100.** `getAdministradores` busca `/admin/users/?role=ADMIN&page_size=100`, e a lista do admin mostra só contas ativas. Registros de um administrador arquivado, rebaixado ou excluído não podem ser filtrados pela tela, embora o backend aceite qualquer id. Correção: alimentar o seletor com os `admin_ref` distintos do próprio log (uma rota pequena) ou aceitar um id digitado.
7. **A trava da limpeza é discriminada por um único teste (B1).** Correção opcional: no teste `:253`, fazer `criar_devagar` dormir antes dos `DELETE` (por exemplo, simulando atraso em `modelos_da_limpeza`), para que a sobreposição aconteça também com um usuário com dados.

## Correções após a verificação

| Gap | Situação | Commit |
| --- | -------- | ------ |
| 1. Rótulo "Gratuito" | Corrigido: o painel usa `nomeDoPlano` ("Comum") no dashboard, na lista, no detalhe e no log; os seletores em caixa alta dizem "COMUM"; `log.test.tsx` espera "Antes:Comum" e `dashboard.test.tsx` o card "Plano Comum" | frontend `c46695b` |
| 2. Reativação fora da spec | Corrigido: ADMIN-19 passa a incluir a reativação da conta; teste no frontend (`confirmacoes.test.tsx`) confirma que restaurar um arquivado na lista envia só `{ is_active: true }`, sem `admin_password` e sem campo de senha | backend `c03e1db` (spec), frontend `c46695b` (teste) |
| 3. ADMIN-21 e ADMIN-22 dependem de modelos futuros | Corrigido: nota abaixo da rastreabilidade da spec diz que classes, plano do salário e vínculos entram com `classes-de-despesa`, `gestao-do-salario` e `vinculo-entre-transacoes` (AD-050), e que a `classes-de-despesa` acrescenta as classes a `criar_padrao_do_cadastro` com um teste de limpeza | backend `c03e1db` |
| 4. Ramo 403 por campo do `tratarErro` sem teste próprio | Corrigido: `tests/contratos/tratamento-de-erros.test.ts` cobre o 403 `{admin_password: [...]}` indo para o campo sem toast e o 403 com `detail` e campos indo para o toast do `detail` | frontend `dfd0e55` |
| 5. `CLEAR_DATA` fora da transação | Corrigido: `limpar_dados(usuario, admin)` grava o registro dentro do próprio `atomic`, depois de `criar_padrao_do_cadastro`; a view não registra mais depois; novo teste em `test_limpeza.py` (falha ao gravar o log: 500, dados intactos, nenhum `CLEAR_DATA`) | backend `6d5bf33` |
| 6. Filtro de administrador do log | Fica para depois | — |
| 7. Trava da limpeza discriminada por um único teste | Fica para depois | — |

Depois das correções: `tests.painel_admin` com 79 testes OK e a suíte inteira do backend com 1202 testes OK; a suíte inteira do frontend com 385 testes OK em 73 arquivos, `tsc --noEmit` sem erro e o ESLint com 152 erros (nenhum novo).
