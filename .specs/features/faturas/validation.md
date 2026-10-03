# Faturas Validation

**Date**: 2026-10-02
**Spec**: `.specs/features/faturas/spec.md`
**Diff range**: backend `fix/faturas` (`2799b6b..b08c365`, 23 commits); frontend `fix/faturas` (`32a49ad..b5d3639`, 5 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), nível leve, uma rodada
**Veredito**: PASS ✅

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 a T22 | ✅ Done | Todas marcadas `✅ Complete` em `tasks.md` (T1 a T17 no backend, T18 a T22 no frontend) |

---

## Gate Check

### Backend

- **Comando**: `docker compose exec -T backend sh -c "python -m compileall -q -x venv . && python manage.py makemigrations --check --dry-run && python manage.py test --noinput"`
- **Resultado**: exit 0. `compileall` sem erro; `makemigrations --check`: "No changes detected"; `Ran 629 tests in 142.802s ... OK`
- **Falhas**: nenhuma. **Skips**: nenhum
- **Contagem**: 529 antes da feature (gate da `saldo`), 629 depois: +100, todos em `tests/faturas/` (`tests.faturas` sozinho: 100 testes)
- **Testes antigos ajustados**: `tests/saldo/test_atomicidade.py:111-117` e `:129-134` (falha inesperada passa de 400 para 500, FATURA-28; o estado continua conferido por inteiro), `tests/saldo/test_fatura.py:147-157` (estorno do parcial agora junta a compra, FATURA-35, e confere que o restante sumiu) e `tests/isolamento/test_pagamento_fatura.py:106-108` (valor do pagamento igual ao total da fatura, por causa da FATURA-26). Nenhuma asserção ficou mais fraca: as três mudanças seguem a spec nova

### Frontend

| Gate | Resultado |
| ---- | --------- |
| `npm test` | 25 arquivos, 101 testes, todos passando (84 antes da feature, +17; `tests/faturas` tem 5 arquivos) |

---

## Spec-Anchored Acceptance Criteria

Testes do backend em `tests/faturas/` (repositório `fluxar-backend`); os marcados FE estão em `tests/faturas/` do `fluxar-frontend`. O cartão padrão dos testes fecha no dia 10 e vence no dia 20.

### P1: Datas de fechamento e vencimento

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-01 dia inexistente usa o último | fechamento 31 → 30/04; vencimento 30 → 28/02 ou 29/02 | `tests/faturas/test_datas.py:26-28` - `dia_no_mes(2026, 4, 31) == date(2026, 4, 30)`, `(2024, 2, 30) == 29/02`, `(2025, 2, 30) == 28/02`; `:62-63` vencimento 30 em fev/2024 e fev/2025; `:46-47` todas as combinações 1 a 31 × 2024 a 2027 | ✅ PASS |
| FATURA-02 sem herdar o ajuste | 30/04 e de novo 31/05 | `tests/faturas/test_datas.py:32-33` - `datas_da_fatura(31, 10, 5, 2026)[0] == 30/04` e `(…, 6, 2026)[0] == 31/05`; `:57-59` dia do fechamento por mês | ✅ PASS |
| FATURA-03 vencimento > fechamento → mesmo mês | fechamento no mês do vencimento | `tests/faturas/test_datas.py:66` - `datas_da_fatura(10, 20, 9, 2026) == (10/09, 20/09)`; `:50-54` em todas as combinações | ✅ PASS |
| FATURA-04 vencimento ≤ fechamento → mês seguinte | vencimento no mês seguinte ao fechamento | `tests/faturas/test_datas.py:69-70` - `(30, 7, 3, 2026) == (28/02, 07/03)` e `(15, 15, 1, 2026) == (15/12/2025, 15/01/2026)`; `:50-54` | ✅ PASS |
| FATURA-05 dia fora de 1..31 | HTTP 400 no cadastro e na edição | `tests/faturas/test_status_e_vencimento.py:132-133` - `status_code == 400`, `campo in resp.data` para 0 e 32 nos dois campos (POST); `:140-143` PATCH, cartão sem mudança | ✅ PASS |
| FATURA-06 próximo vencimento ≥ hoje | primeira data de vencimento igual ou posterior a hoje | `tests/faturas/test_status_e_vencimento.py:75-77` - `next_due_date == 20/09` em 19/09 e em 20/09; `:82` - `20/01/2027` em 21/12; `:87-89` - `30/04/2026` e `29/02/2028` com dia 31; FE `tests/faturas/tela-do-cartao.test.tsx:59` - `Vence em 07/11` vindo da API | ✅ PASS |
| FATURA-07 novos dias só nas faturas novas | existentes mantêm as datas | `tests/faturas/test_alocacao.py:34-41` - mesma `pk`, datas `(10/09, 20/09)` mantidas, nova fatura de outubro `(05/10, 15/10)` | ✅ PASS |
| FATURA-08 não paga antes do fechamento → aberta | `OPEN` | `tests/faturas/test_status_e_vencimento.py:41` - `status == 'OPEN'` em 09/09 | ✅ PASS |
| FATURA-09 não paga no fechamento ou depois → fechada | `CLOSED` | `tests/faturas/test_status_e_vencimento.py:45`, `:47` - `'CLOSED'` em 10/09 e 25/09; `:49` banco continua `OPEN`; `:62` lista do cartão | ✅ PASS |

### P1: Em qual fatura cai cada compra e cada parcela

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-10 antes do fechamento | fatura que fecha no mês | `tests/faturas/test_datas.py:79` - `mes_da_fatura(31, 10, 29/04/2026) == (5, 2026)`; `:91-94` véspera do fechamento em todas as combinações | ✅ PASS |
| FATURA-11 no fechamento ou depois | fatura que fecha no mês seguinte | `tests/faturas/test_datas.py:77` - `mes_da_fatura(31, 10, 30/04/2026) == (6, 2026)`; `:95-98` o próprio dia do fechamento → `mes_seguinte` | ✅ PASS |
| FATURA-12 uma parcela por fatura consecutiva | 30/01/2026, fecha 30, vence 7, 4x → mar, abr, mai, jun | `tests/faturas/test_criacao_da_compra.py:36` - meses `[(3,2026),(4,2026),(5,2026),(6,2026)]`; `:61` 12x com fechamento 29, 30, 31 sem repetir nem pular; `tests/faturas/test_alocacao.py:98` | ✅ PASS |
| FATURA-13 centavos na primeira | 100 em 3x → 33,34 / 33,33 / 33,33 | `tests/faturas/test_criacao_da_compra.py:87-90` - `[33.34, 33.33, 33.33]` pela API; `tests/faturas/test_alocacao.py:114-117`; `:120-124` soma igual ao valor | ✅ PASS |
| FATURA-14 ligada a exatamente uma fatura do mesmo cartão | `invoice.card == credit_card` | `tests/faturas/test_criacao_da_compra.py:41` - `parcela.invoice.card_id == cartao.id`; `tests/faturas/test_edicao_da_compra.py:71-72` depois de trocar o cartão | ✅ PASS |
| FATURA-15 fatura paga → primeira não paga seguinte | pula a paga, cria se faltar | `tests/faturas/test_alocacao.py:79-81` - `(10, 2026)`, `OPEN`, datas `(10/10, 20/10)`; `:108` `[(9,2026),(11,2026),(12,2026)]`; `tests/faturas/test_criacao_da_compra.py:75-79` pela API, total da paga `0.00` | ✅ PASS |
| FATURA-16 guarda e exibe a data da compra | `purchase_date` em todas as parcelas | `tests/faturas/test_criacao_da_compra.py:38` - `purchase_date == 30/01/2026` em cada parcela; `:43` resposta `['2026-01-30'] * 4`; `tests/faturas/test_data_da_compra.py:29`; FE `tests/faturas/detalhe-da-fatura.test.tsx:66-67` "01 de setembro"; FE `tests/faturas/edicao-e-exclusao-da-compra.test.tsx:146` "Compra em 15/09" | ✅ PASS |
| FATURA-17 data ou cartão mudam → realoca | 10/01/2026 → fev a mai; totais acompanham | `tests/faturas/test_edicao_da_compra.py:52` - meses `[(2..5, 2026)]`; `:57-58` totais `25.00` e junho `0.00`; `:69-77` cartão novo; FE `edicao-e-exclusao-da-compra.test.tsx:102` envia `purchase_date: "2026-09-20"` | ✅ PASS |
| FATURA-18 total = soma das compras | antiga e nova atualizadas | `tests/faturas/test_total.py:28-29` - `100.00` e `350.00` ao mover; `:37`, `:40` - `350.00` ao mudar valor e `100.00` ao excluir | ✅ PASS |
| FATURA-19 parcela em fatura paga | HTTP 400, "Estorne o pagamento da fatura antes de alterar esta compra." | `tests/faturas/test_edicao_da_compra.py:115-117` - `400`, `resp.data == {'detail': MENSAGEM}`, estado igual; `:125-127` mudar data com parte paga; `tests/faturas/test_exclusao_da_compra.py:58-62` exclusão; FE `edicao-e-exclusao-da-compra.test.tsx:122` toast com a mensagem | ✅ PASS |
| FATURA-20 excluir parcela exclui a compra | todas as parcelas saem | `tests/faturas/test_exclusao_da_compra.py:39-42` - `204`, nenhuma parcela, totais `0.00` (parcela 5/12); `:47-50` parcela 1/12; FE `edicao-e-exclusao-da-compra.test.tsx:136` aviso "Todas as parcelas desta compra serão excluídas." | ✅ PASS |

### P1: Pagamento total e parcial

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-21 pagamento total | todas as compras e a fatura pagas | `tests/faturas/test_pagamento.py:123-130` - `PAID`, total `1000.00`, cada compra `COMPLETED` com conta e data; `tests/faturas/test_fluxo_completo.py:90-93` | ✅ PASS |
| FATURA-22 ordem data da compra, depois valor | 02/09 R$ 50 e R$ 70 antes de 03/09 R$ 30 | `tests/faturas/test_pagamento.py:147-150` - `cedo_menor` e `cedo_maior` `COMPLETED`, `tarde` `PENDING` fora de setembro | ✅ PASS |
| FATURA-23 divide a compra | parte paga + restante pendente na seguinte não paga | `tests/faturas/test_pagamento.py:77-88` - `('COMPLETED', 300.00, 'Loja (Parcial)', …)` e restante `('PENDING', 300.00, outubro, 20/10, …)` | ✅ PASS |
| FATURA-24 parcial move as não pagas e marca paga | movidas para a primeira não paga; fatura `PAID` | `tests/faturas/test_pagamento.py:179-186` - movida `PENDING` em novembro (outubro paga é pulada), setembro `PAID`, totais `100.00`/`200.00` | ✅ PASS |
| FATURA-25 fatura do restante criada | datas por FATURA-01 a 04 | `tests/faturas/test_pagamento.py:177` - novembro `(10/11/2026, 20/11/2026)`; `tests/faturas/test_alocacao.py:81` | ✅ PASS |
| FATURA-26 valor > total | HTTP 400, "O valor pago não pode ser maior que o total da fatura." | `tests/faturas/test_pagamento.py:219-221` - `400`, `resp.data == {'detail': VALOR_MAIOR}`, estado igual (R$ 1.050,01 contra R$ 1.050,00) | ✅ PASS |
| FATURA-27 fatura paga informa pagamento | valor, conta e data | `tests/faturas/test_api.py:88-91` - `payment == {'amount': '400.00', 'account_id', 'account_name', 'date': '2026-09-15'}`; `:97` nulo depois do estorno; FE `tests/faturas/datas-da-fatura.test.tsx:102` "Pago R$ 700,00 em 05/09/2026 · Banco Azul" | ✅ PASS |
| FATURA-28 falha desfaz tudo | fatura, compras e seguinte como antes | `tests/faturas/test_pagamento.py:240-243` - `500`, `estado() == antes`, outubro não criada; `tests/faturas/test_estorno.py:173-174` estorno | ✅ PASS |

### P1: Pagamento repetido

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-29 interface envia e reaproveita a chave | mesma chave em todo reenvio do mesmo diálogo | FE `tests/faturas/pagamento-com-identificador.test.tsx:87-88` - `chaveDoEnvio(0)` é UUID e `chaveDoEnvio(1) === chaveDoEnvio(0)` depois de timeout; `:105-107` chave nova ao reabrir | ✅ PASS |
| FATURA-30 chave já processada | mesma resposta, sem pagar de novo | `tests/faturas/test_pagamento_repetido.py:50-64` - 10 × `200`, respostas iguais, um `PagamentoDeFatura`, saldo `600.00`; `:122-127` depois do estorno: mesma resposta, saldo `1000.00`, fatura `OPEN` | ✅ PASS |
| FATURA-31 mesma chave ao mesmo tempo | um processamento, mesma resposta aos dois | `tests/faturas/test_concorrencia.py:88-92` - `[200, 200]`, dados iguais, 1 pagamento, saldo `600.00` (threads reais, `TransactionTestCase`) | ✅ PASS |
| FATURA-32 chave com outros dados | HTTP 400, "Este identificador de pagamento já foi usado com outros dados.", sem pagar | `tests/faturas/test_pagamento_repetido.py:67-71` com `:76-78` - valor, conta e data; `:85-88` outra fatura; `tests/faturas/test_concorrencia.py:110-121` ao mesmo tempo em duas faturas | ✅ PASS |
| FATURA-33 fatura paga com chave nova ou sem chave | HTTP 400, "Fatura já está paga." | `tests/faturas/test_pagamento_repetido.py:98-101` - chave nova e `None`; `:110-112` sem o campo | ✅ PASS |

### P1: Estorno do pagamento

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-34 quitadas voltam a pendentes | na fatura original, sem data de pagamento | `tests/faturas/test_estorno.py:91` - c400 `('PENDING', 400.00, 'Mercado', setembro, 20/09, conta, None)` | ✅ PASS |
| FATURA-35 junta parte paga e restante | uma compra pendente, valor e descrição originais | `tests/faturas/test_estorno.py:92-93` - c600 `('PENDING', 600.00, 'Loja', setembro, …)` e restante excluído; `tests/saldo/test_fatura.py:149-157` | ✅ PASS |
| FATURA-36 parcial traz de volta as movidas | movidas voltam à original | `tests/faturas/test_estorno.py:135-138` - c600 de volta a setembro, totais `1000.00` e `200.00` | ✅ PASS |
| FATURA-37 status e total depois do estorno | aberta/fechada por 08/09; total = soma | `tests/faturas/test_estorno.py:188-193` - banco `OPEN`, exibida `OPEN` em 09/09 e `CLOSED` em 10/09, total `1000.00` | ✅ PASS |
| FATURA-38 seguinte já paga | HTTP 400, "Estorne primeiro o pagamento da fatura seguinte." | `tests/faturas/test_estorno.py:160-162` - `400`, `resp.data == {'detail': ESTORNE_A_SEGUINTE}`, `tudo() == antes` | ✅ PASS |

### P1: Correção dos dados existentes

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-39 compra sem fatura ganha fatura | fatura por FATURA-10 a 12 | `tests/faturas/test_migracao.py:83-92` - 15/03 → abril (`07/04`); 31/03 → junho (maio paga pulada); `:171` com o registro histórico de models | ✅ PASS |
| FATURA-40 parcelas repetidas realocadas | uma por fatura consecutiva, pagas não se movem | `tests/faturas/test_migracao.py:102-106` - `[3,4,5,6]`, datas no vencimento, totais `25.00`; `:116-118` paga fica em março, maio paga pulada | ✅ PASS |
| FATURA-41 total recalculado | soma das compras | `tests/faturas/test_migracao.py:152-153` - `75.50` (sem a compra de B) e `0.00` | ✅ PASS |

### P2: Limite disponível

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-42 limite − não pagas, nas duas telas | R$ 5.000 − R$ 1.200 = R$ 3.800 | `tests/faturas/test_limite.py:34` - `(3800.00, 3800.00)` cartão e dashboard; `:43` - `(4500.00, 4500.00)` depois do parcial; FE `tests/faturas/tela-do-cartao.test.tsx:61` "R$ 3.800,00", `:67` "Utilizado: R$ 1.200,00" | ✅ PASS |

### P2: Faturas na interface e na API

| Critério | Resultado definido pela spec | `file:line` + asserção | Resultado |
| -------- | ---------------------------- | ---------------------- | --------- |
| FATURA-43 datas sem deslocamento de fuso | 01/10 aparece 01/10, em outubro | FE `tests/faturas/datas-da-fatura.test.tsx:70-73` - o ambiente reproduz o bug (`getDate() == 30`) e `lerData` dá `[2026, 10, 1]`; `:79-80` diálogo "01/10/2026" e "outubro de 2026"; `:92-95` lista num dia 31 | ✅ PASS |
| FATURA-44 todas as compras no detalhe | 35 compras listadas | `tests/faturas/test_api.py:59-62` - lista sem paginação, 35 itens em ordem de data da compra; FE `tests/faturas/detalhe-da-fatura.test.tsx:55-57` - 35 linhas e GET em `/invoices/fatura-1/transactions/` | ✅ PASS |
| FATURA-45 escrita direta | HTTP 405 | `tests/faturas/test_api.py:40-44` - POST, PUT, PATCH e DELETE `405`; fatura sem mudança | ✅ PASS |

**Status**: ✅ 45/45 ACs com evidência `file:line` e asserção no valor da spec. As mensagens das FATURA-19, 26, 32, 33 e 38 são conferidas literalmente com `resp.data == {'detail': ...}`.

---

## Edge Cases

- [x] Fechamento no dia 31 e compra em 30/04 vai para a fatura seguinte: `tests/faturas/test_datas.py:77`
- [x] Vencimento no dia 30 em fevereiro bissexto vence em 29/02: `tests/faturas/test_datas.py:62`
- [x] Fechamento 30, vencimento 7, 4x em 30/01/2026: março a junho: `tests/faturas/test_criacao_da_compra.py:36`
- [x] R$ 100,00 em 3x: `tests/faturas/test_criacao_da_compra.py:87-90`
- [x] Pagamento antecipado seguido de compra no mesmo ciclo / compra antiga em fatura paga vai para a primeira não paga: `tests/faturas/test_alocacao.py:79`, `tests/faturas/test_migracao.py:87-92`
- [x] Dois pagamentos com chaves diferentes ao mesmo tempo: só um passa (SALDO-26, já coberto em `tests/saldo/test_concorrencia.py`); fatura paga com chave nova recusada: `tests/faturas/test_pagamento_repetido.py:98-99`
- [x] Reenvio da chave depois do estorno: `tests/faturas/test_pagamento_repetido.py:122-127`
- [x] Estorno de fatura não paga recusado (SALDO-27): `tests/saldo/test_fatura.py` (`test_estornar_fatura_nao_paga_recebe_400_sem_mudar_saldo`)
- [x] Cartão sem conta de pagamento continua aceito: `tests/faturas/test_criacao_da_compra.py:106-111`

---

## Discrimination Sensor

Isolamento: o serviço `backend` do compose monta o diretório do repositório (`.:/app`), então um `docker compose cp` para dentro do container gravaria no arquivo real do host. Por isso os mutantes rodaram num worktree descartável `../fluxar-backend-mut` (detached em `b08c365`) com um container avulso `docker run --rm -v <worktree>:/app --network fluxar-backend_default fluxar-backend-backend`, depois que o gate terminou (para não disputar o banco de teste). Sem mutação, `tests.faturas` passou no worktree (100 testes OK). No frontend, worktree `../fluxar-frontend-mut` (detached em `b5d3639`, `node_modules` por junction, removida antes do worktree). Cada mutação foi revertida com `git checkout -- accounts/faturas.py` antes da seguinte.

| # | File:line | Descrição | Killed? |
| - | --------- | --------- | ------- |
| 1 | `accounts/faturas.py:22` | Último dia do mês errado: dia inexistente vira o penúltimo (`ultimo - 1`) | ✅ Killed (11 falhas: `test_datas` ×6, `test_alocacao` ×2, `test_criacao_da_compra` 12x, próximo vencimento) |
| 2 | `accounts/faturas.py:59` | Melhor dia de compra: `data_compra >= fechamento` → `>` | ✅ Killed (26 falhas e 1 erro: `test_datas`, `test_alocacao`, `test_criacao_da_compra`, `test_edicao_da_compra`) |
| 3 | `accounts/faturas.py:111` | `primeira_nao_paga` não pula a fatura paga (`while False`) | ✅ Killed (3 falhas e 1 erro: `test_alocacao` ×2, `test_criacao_da_compra`, rolagem em `test_pagamento`) |
| 4 | `accounts/faturas.py:291-292` | Chave de idempotência compara fatura, valor e conta, mas não a data | ✅ Killed (`test_mesma_chave_com_outro_valor_conta_ou_data_e_recusada`, subteste da data) |
| 5 | `accounts/faturas.py:433` | Estorno da compra dividida não soma o restante (`compra.amount += restante.amount` removido) | ✅ Killed (3 falhas: `test_pagar_700_e_estornar_volta_tudo_como_antes`, `test_restante_editado_…`, fluxo completo) |
| 6 | `accounts/faturas.py:419` | Recusa da FATURA-38 removida | ✅ Killed (`test_fatura_seguinte_paga_recebe_400_e_nada_muda`) |
| 7 | `accounts/faturas.py:147` | `colocar` não grava `date` igual ao vencimento da fatura | ✅ Killed (5 falhas e 8 erros: `ColocarTests`, edição, rolagem, estorno, limite, fluxo completo) |
| 8 | `src/components/transactions/invoice-payment-dialog.tsx:202` (frontend) | Cada envio gera uma chave nova (`crypto.randomUUID()` no `onSubmit`) | ✅ Killed (`pagamento-com-identificador.test.tsx:88`, "reenvia com a mesma chave depois de um timeout") |

**Verificação do isolamento**: `git status --porcelain` vazio antes e depois nos dois repositórios; worktrees removidos (`git worktree list` só com o principal); `sha256sum` de `accounts/faturas.py` igual no host e em `/app` do container (`cc679739…445b`); `node_modules` do frontend intacto.

**Sensor depth**: leve (8 mutações de comportamento nos pontos de maior risco, pedido do usuário)
**Result**: 8/8 killed, 0 survived - PASS

---

## Code Quality (nível leve, amostragem)

| Princípio | Status |
| --------- | ------ |
| Uma regra de datas e de alocação | ✅ `accounts/faturas.py` concentra datas, alocação, total, limite, pagamento e estorno; `TransactionService._get_or_create_invoice` delega a `obter_fatura` |
| `date` e `invoice` gravados juntos | ✅ `colocar` (`accounts/faturas.py:141`); a criação grava `date=fatura.due_date` (`transactions/services.py:237`) |
| Atomicidade e trava | ✅ `pagar` e `estornar` em `transaction.atomic()` com `select_for_update` da fatura; savepoint no `IntegrityError` da chave |
| Testes mapeados aos ACs | ✅ cada arquivo de `tests/faturas/` cita os IDs que cobre |
| Asserções no valor da spec | ✅ mensagens exatas e valores do Independent Test conferidos literalmente |
| Guidelines | AD-033 e AD-034 (local e ferramentas de teste) seguidos |

---

## Observações (não bloqueiam)

1. **FATURA-35 com o restante editado.** Se o usuário mudou o valor do restante antes do estorno, a compra volta com a parte paga mais o valor atual do restante (`tests/faturas/test_estorno.py:109`, R$ 550,00), não com o valor original de R$ 600,00. A spec diz "valor original"; o design (`design.md:162`) registra a escolha. Com o restante intacto, o resultado é o original, como a spec pede.
2. **FATURA-15 com duas faturas pagas seguidas.** Os testes têm sempre uma única fatura paga no caminho. Um mutante que trocasse o `while` de `primeira_nao_paga` por `if` provavelmente sobreviveria. O código usa `while`, então o comportamento está certo; falta só a evidência.
3. **Gate do frontend reduzido.** Por instrução desta rodada, só `npm test` rodou no frontend; `tsc`, lint e build não foram repetidos pelo Verifier.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| FATURA-01 a FATURA-45 | Implemented | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (PASS)

**Spec-anchored check**: 45/45 ACs com evidência; 2 observações menores (restante editado na FATURA-35, faturas pagas seguidas na FATURA-15)
**Sensor**: 8/8 mutações mortas (7 no backend, 1 no frontend)
**Gate**: backend 629 OK (compileall e `makemigrations --check` limpos); frontend 101 testes OK

**Próximos passos**: opcional, um teste com duas faturas pagas seguidas no caminho de uma compra parcelada. Não bloqueia.
