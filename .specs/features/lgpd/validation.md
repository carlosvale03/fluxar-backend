# Lgpd Validation

**Verdict: PASS**

Verificação leve feita por um verificador independente (autor ≠ verificador): conferência das ACs principais contra a spec e um sensor de discriminação com 8 mutações de comportamento. Nenhuma mutação sobreviveu.

## Diff ranges

| Repo | Branch | Range | Commits |
| ---- | ------ | ----- | ------- |
| fluxar-backend | `fix/lgpd-dados-pessoais-consentimento-e-exclusao` | `development (7b4aa1b)..HEAD (7007ed4)` | 25 |
| fluxar-frontend | `fix/lgpd-dados-pessoais-consentimento-e-exclusao` | `development (6f2c944)..HEAD (2fdc8d4)` | 7 |

Baseline: `tests.lgpd` no backend com 98 testes OK (Postgres do `docker compose`); `tests/lgpd` no frontend com 34 testes OK em 8 arquivos.

## Evidência por AC

### Pedido de exclusão e cancelamento

| AC | Evidência |
| -- | --------- |
| LGPD-01 | frontend `tests/lgpd/excluir-conta.test.tsx:59` |
| LGPD-02 | backend `tests/lgpd/test_meus_dados.py:52` (plano Comum com `exportacao_xlsx` travada: export de transações 403, `/api/users/me/export/` 200 XLSX), `:65` (só os dados do próprio usuário); frontend `excluir-conta.test.tsx:65` |
| LGPD-03, LGPD-04 | backend `tests/lgpd/test_pedido_de_exclusao.py:51` (400 no campo, conta inalterada), `:59`; frontend `excluir-conta.test.tsx:77`, `:102` |
| LGPD-05 | backend `test_pedido_de_exclusao.py:68` (desativa, encerra sessões, +30 dias); frontend `excluir-conta.test.tsx:90` (mostra a data e chama `logout`) |
| LGPD-06 | backend `test_pedido_de_exclusao.py:94`, `:104` (envio falhando não derruba o pedido), `:142` (e-mail traz data e como desistir) |
| LGPD-07 | backend `tests/lgpd/test_cancelamento.py:53` (`deletion_pending`, data, `cancel_token`, sem sessão), `:67`, `:73`; frontend `tests/lgpd/cancelar-exclusao.test.tsx:55`, `:78` |
| LGPD-08 | backend `test_cancelamento.py:85` (reativa, limpa as datas, abre a sessão), `:109`, `:123`; frontend `cancelar-exclusao.test.tsx:66`, `tests/lgpd/rota-de-cancelamento.test.ts:27` |
| LGPD-09 | backend `test_pedido_de_exclusao.py:118`, `:128` |
| "Esqueci a senha" no prazo | backend `test_cancelamento.py:140` |

### Exclusão definitiva

| AC | Evidência |
| -- | --------- |
| LGPD-10 | backend `tests/lgpd/test_exclusao_definitiva.py:121` (dados e imagens no Cloudinary), `:154` (logs de admin ficam só com o id, AD-030), `:196` (completude de `MODELOS_DO_USUARIO`: todo modelo com FK para o usuário está na lista ou nas exceções) |
| LGPD-11 | backend `test_exclusao_definitiva.py:138` (só o `RegistroDeExclusao`, sem dado pessoal), `:226`, `:245` (executor admin) |
| LGPD-12 | backend `test_exclusao_definitiva.py:173`, `:186` (Cloudinary falhando ou recusando: nada é apagado), `:257` (admin recebe erro); `tests/lgpd/test_rotina_diaria.py:69` (a conta que falha não impede a próxima e sai na execução seguinte) |
| LGPD-13 | backend `test_exclusao_definitiva.py:226` (inclusive conta pendente, nas duas rotas do admin), `:245`; frontend `tests/lgpd/painel-e-imagem-da-meta.test.tsx:91`, `:103` |
| LGPD-14 | backend `test_exclusao_definitiva.py:273` |
| Rotina diária e token | backend `test_rotina_diaria.py:44`, `:61`, `:105` (sem token ou token errado: 401 e nada apagado), `:114`, `:125`, `:136` (variável ausente: 404), `:143` (roda na manutenção) |

### Guarda dos dados pessoais

| AC | Evidência |
| -- | --------- |
| LGPD-15 | backend `tests/lgpd/test_dados_pessoais.py:57` (CPF, telefone, nascimento e renda cifrados no banco e completos para o dono); `tests/lgpd/test_criptografia.py:57`, `:65`, `:75`, `:84`, `:90` (rotação de chaves) |
| LGPD-16 | backend `test_criptografia.py:105` (produção sem a chave interrompe nomeando a variável) |
| LGPD-17 | backend `tests/lgpd/test_cpf.py:26`, `:34`, `:41` |
| LGPD-18 | backend `test_cpf.py:54`; `test_dados_pessoais.py:79` |
| LGPD-19 | backend `tests/lgpd/test_painel.py:24`, `:32`, `:45`; frontend `painel-e-imagem-da-meta.test.tsx:81` |
| LGPD-20 | backend `tests/lgpd/test_uploads.py:51`, `:60`; frontend `painel-e-imagem-da-meta.test.tsx:131`, `:141` |
| LGPD-24 | backend `test_dados_pessoais.py:91`, `:116`, `:123` |

### Logs

| AC | Evidência |
| -- | --------- |
| LGPD-21, LGPD-22 | backend `tests/lgpd/test_logs.py:75` (sem payload), `:107`, `:114`, `:117` (filtro mascara e-mail e CPF na mensagem, nos argumentos e no traceback), `:136` (filtro em todos os handlers e no raiz), `:167`, `:179` (Cloudinary loga só a classe do erro), `:217`, `:225`; `tests/lgpd/test_auditoria.py:47`, `:55`, `:64` |
| LGPD-23 | backend `test_logs.py:57` (nenhum `print` no código de produção, por AST) |
| LGPD-25 | backend `test_auditoria.py:83`, `:93`, `:106` |

### Termos e consentimento

| AC | Evidência |
| -- | --------- |
| LGPD-26 | backend `tests/lgpd/test_termos_no_cadastro.py:77` (versão vigente com data e hora), `:42` (`GET /api/terms/`) |
| LGPD-27 | backend `test_termos_no_cadastro.py:65`; frontend `tests/lgpd/consentimento-no-cadastro.test.tsx:74` |
| LGPD-28 | frontend `tests/lgpd/aceite-dos-termos.test.tsx:91` (403 leva a `/termos/aceite` guardando a página), `:109`, `:121` (mostra as mudanças, aceita e volta), `:147` (o `/auth/me` sem aceite leva à tela antes das outras), `:163` |
| LGPD-29 | backend `tests/lgpd/test_bloqueio_dos_termos.py:50` (`/api/accounts/` 403 `terms_acceptance_required`), `:54`, `:59` (rotas liberadas), `:85` (pedido de exclusão e cancelamento sem aceite), `:103`, `:137` |
| LGPD-30 | backend `test_bloqueio_dos_termos.py:111`, `:127` |
| LGPD-31, LGPD-32 | frontend `tests/lgpd/pagina-de-termos.test.tsx:40`, `:47`, `:57`, `:66`, `:76` |
| LGPD-33 | backend `test_termos_no_cadastro.py:89`, `:97`, `:103`; frontend `consentimento-no-cadastro.test.tsx:45`, `:59` |
| LGPD-34 | frontend `tests/lgpd/consentimento-nas-configuracoes.test.tsx:66`, `:78`, `:89` |
| LGPD-35 | backend `tests/lgpd/test_consentimento.py:29`, `:47`, `:63`, `:77` (valor não booleano: 400 no campo), `:86` |
| LGPD-36, LGPD-37 | backend `tests/lgpd/test_conjunto_anonimizado.py:52`, `:60`, `:95` |
| LGPD-38 | backend `test_conjunto_anonimizado.py:69` |
| LGPD-39 | backend `test_termos_no_cadastro.py:121` |

## Discrimination sensor

Backend: mutações aplicadas num worktree destacado (`../fluxar-backend-mut`, removido depois), suíte `tests.lgpd` rodada num container da imagem do projeto com `cryptography` instalada, na rede `fluxar-backend_default`. Frontend: mutação no arquivo real, `vitest run` do arquivo de teste, e `git checkout` em seguida.

| # | Repo | Mutação | Resultado | Testes que pegaram |
| - | ---- | ------- | --------- | ------------------ |
| B1 | backend | `TermosMiddleware` libera `/api/accounts/` sem o aceite | killed | 7 falhas em `test_bloqueio_dos_termos.py` (`:50`, `:54`, `:85`, `:127`, `:137`) |
| B2 | backend | `excluir_definitivamente` remove as imagens do Cloudinary só depois do `atomic` que apaga o banco | killed | `test_exclusao_definitiva.py:173`, `:186`, `:257`; `test_rotina_diaria.py:69`, `:125` |
| B3 | backend | `excluir_definitivamente` não grava o `RegistroDeExclusao` | killed | `test_exclusao_definitiva.py:138`, `:226`, `:245`; `test_rotina_diaria.py:44`, `:69`, `:114` |
| B4 | backend | `/api/users/me/export/` volta a exigir a trava `exportacao_xlsx` do plano | killed | `test_meus_dados.py:52`, `:65` |
| B5 | backend | o conjunto anonimizado ignora o consentimento (só `is_active=True`) | killed | `test_conjunto_anonimizado.py:52`, `:60`, `:95` |
| F1 | frontend | o interceptor não redireciona para `/termos/aceite` no 403 `terms_acceptance_required` | killed | `aceite-dos-termos.test.tsx:91` |
| F2 | frontend | "Excluir minha conta" não chama `logout()` depois do pedido | killed | `excluir-conta.test.tsx:90` |
| F3 | frontend | o login ignora o `deletion_pending` e não oferece cancelar | killed | `cancelar-exclusao.test.tsx:55`, `:66` |

**Score: 8/8 killed.**

Observação sobre B2: uma variante anterior, que chamava o Cloudinary dentro do mesmo `atomic` depois dos deletes, só foi pega por `test_exclusao_definitiva.py:121`, porque o `rollback` ainda deixa o banco inteiro. Essa variante não viola LGPD-12, então não conta como sobrevivente.

## Perguntas específicas

**`VERSAO_VIGENTE = '2.0'` contra o "2" do design.** Nem a spec nem o `design.md` fixam o literal: o design só cita `VERSAO_VIGENTE` (`design.md:159`), e o "publicar a versão 2" da spec (`spec.md:163`) é narrativo. A versão é opaca de ponta a ponta: o backend compara por igualdade (`core/termos.py:78`), o frontend compara `accepted_version` com `current_version` vindos do `/auth/me`, e a migração `0019` zera o aceite de todos (`api/migrations/0019_termos_por_versao_e_consentimento.py:17`). O formato não muda o comportamento, então não é desvio de conformidade.

**Toast antes do redirecionamento no 403 `terms_acceptance_required`.** O interceptor (`fluxar-frontend/src/services/apiClient.ts:137-145`) grava a página, faz `window.location.href = "/termos/aceite"` e rejeita a promise. Quem chamou e trata o erro com `tratarErro` cai no ramo do `detail` (`src/lib/erros.ts:107-110`) e mostra `toast.error` com "Os termos de uso e a política de privacidade mudaram...". Esse toast aparece um instante e some, porque a navegação recarrega a página. A spec não fala desse toast: LGPD-28 pede só que a interface mostre o que mudou e peça o aceite, e isso é cumprido. É um ruído visual, não uma falha de conformidade (ver gap 3).

## Gaps (por prioridade)

1. **A lista de rotas liberadas na spec está incompleta (precisão da spec).** LGPD-29 lista login, renovação, `/auth/me`, logout, o aceite, o download, o pedido de exclusão e o health check. A implementação também libera `/api/terms/` (o `GET` com as mudanças, necessário para LGPD-28), `/api/auth/cancel-deletion/` (necessário para LGPD-08) e `/api/rotina-diaria/` (`api/middleware.py:44-56`). São necessárias e coerentes, mas não estão na AC. Correção: acrescentar as três à LGPD-29 da spec.
2. **O Independent Test de LGPD-21 não está automatizado na suíte inteira.** A spec pede a suíte toda com captura de logs e uma busca por e-mails, CPFs, tokens e valores. A cobertura atual combina o filtro global (`test_logs.py:107-136`) com testes pontuais. Correção: um teste ou script de CI que rode a suíte com um handler raiz que falhe ao ver regex de e-mail completo, CPF, JWT ou valor monetário. O `CapturaDeTudo` de `test_logs.py:28` serve de base.
3. **Um toast de erro aparece por um instante antes de ir para `/termos/aceite`.** Correção trivial: em `tratarErro` (`src/lib/erros.ts`), voltar cedo quando `resposta.status === 403 && dados.code === "terms_acceptance_required"`, como já é feito com `axios.isCancel`.
4. **A falha parcial no Cloudinary é tolerada, mas a spec não a descreve.** Se a primeira imagem sai e a segunda falha, o banco fica inteiro (LGPD-12), mas a primeira imagem já foi apagada. A nova tentativa aceita `not found` (`api/exclusao.py:83-84`), então converge. A frase "sem apagar parte dos dados" de LGPD-12 pode ser lida como "nem no Cloudinary". Correção: deixar claro na spec que a garantia vale para o banco, e que as imagens são removidas de forma idempotente até a exclusão terminar.
5. **O executor de testes mascara o aceite.** `tests/executor.py` faz todo `create_user` nascer com o aceite vigente. Isso é útil, mas esconde se caminhos de produção que criam usuários fora do cadastro (por exemplo `create_admin.py`) deixam a conta bloqueada até o aceite. Esse é o comportamento esperado pela spec, mas não há teste explícito. Correção opcional: um teste que crie o admin pelo comando e confirme o 403 até o aceite.

## Correções após a verificação

- Gap 1: LGPD-29 da spec passou a listar o cancelamento da exclusão, o `GET /api/terms/` e a rotina diária entre as rotas liberadas.
- Gap 3: `tratarErro` volta cedo no 403 `terms_acceptance_required` (`fluxar-frontend/src/lib/erros.ts:94`), com teste em `tests/lgpd/aceite-dos-termos.test.tsx`; a mutação da condição derrubou o teste novo. Commit `16877cd` no frontend.
- Gap 4: LGPD-12 da spec deixa claro que a garantia vale para o banco e que as imagens já removidas contam como removidas na nova tentativa.
- Gaps 2 e 5 ficam anotados no Handoff, fora desta entrega.
