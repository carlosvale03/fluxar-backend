# Auditoria técnica do Fluxar — setembro de 2026

Levantamento de integridade financeira, segurança, contratos entre frontend e backend, performance, operação e manutenibilidade dos repositórios `fluxar-backend` e `fluxar-frontend`.

| | |
|---|---|
| Data da análise | 23/09/2026 |
| Backend | `fluxar-backend`, branch `development`, commit `f85219f` (mesmo conteúdo da `main`) |
| Frontend | `fluxar-frontend`, branch `development`, commit `f2c74d5` (mesmo conteúdo da `main`) |
| Método | Leitura do código não gerado (~7,3 mil linhas de Python e ~28 mil de TS/TSX), execução isolada das funções de cálculo, `npm audit --omit=dev`, `tsc --noEmit` e `npm run lint` |

## Como ler este documento

**Severidade**

- **CRÍTICO**: quebra um fluxo essencial ou corrompe saldos no uso normal.
- **ALTO**: falha de segurança explorável, erro financeiro em casos comuns ou risco operacional sério.
- **MÉDIO**: erro em casos específicos, degradação ou dívida técnica com risco concreto.
- **BAIXO**: problema pontual, cosmético ou de higiene.

**Referências**: `arquivo:linha` vale para os commits acima e muda conforme o código evolui. Caminhos sem prefixo são do backend; caminhos que começam com `fluxar-frontend/` são do frontend.

**Marcações**

- Sem marcação: confirmado lendo o código (dos dois lados, quando envolve contrato entre frontend e backend).
- **[executado]**: reproduzido executando a função isoladamente.
- **[inferido]**: deduzido do código e do comportamento do framework, sem execução.

## Índice

1. [Visão geral do projeto](#1-visão-geral-do-projeto)
2. [Integridade financeira](#2-integridade-financeira)
3. [Segurança e privacidade](#3-segurança-e-privacidade)
4. [Contratos entre frontend e backend](#4-contratos-entre-frontend-e-backend)
5. [Frontend: sessão, robustez e experiência](#5-frontend-sessão-robustez-e-experiência)
6. [Performance](#6-performance)
7. [Operação, CI/CD e processo](#7-operação-cicd-e-processo)
8. [Manutenibilidade](#8-manutenibilidade)
9. [Pontos positivos](#9-pontos-positivos)
10. [Plano de ação sugerido](#10-plano-de-ação-sugerido)
- [Apêndice A — Resultados de ferramentas](#apêndice-a--resultados-de-ferramentas)
- [Apêndice B — Histórico e segredos](#apêndice-b--histórico-e-segredos)

## Sumário executivo

O Fluxar é um SaaS de finanças pessoais funcional e com escopo amplo, mas ainda não é confiável no ponto que mais importa para esse tipo de produto: **o saldo exibido ao usuário**. O saldo de cada conta é um campo atualizado por signals, e vários fluxos do dia a dia (recorrência de receita, estorno de fatura, edição em lote e edição de transferência) pulam ou erram essa atualização. Como o dashboard recalcula o saldo por outro caminho, as telas passam a divergir.

Além disso, há fluxos essenciais quebrados por divergência de contrato entre frontend e backend (a redefinição de senha nunca funciona), falhas de autorização entre usuários na escrita de chaves estrangeiras, ausência de rate limiting e dependências com vulnerabilidades conhecidas. Não há testes automatizados nos dois repositórios e as duas pipelines de CI nunca disparam, então nada disso é detectado automaticamente.

| Severidade | Itens |
|---|---|
| CRÍTICO | 5 |
| ALTO | 25 |
| MÉDIO | 41 |
| BAIXO | 41 |
| **Total** | **112** |

As cinco ações de maior retorno imediato:

1. Corrigir o payload da redefinição de senha ([CON-01](#con-01--crítico--redefinição-de-senha-nunca-funciona)).
2. Restringir ao usuário logado os querysets das chaves estrangeiras de escrita ([SEG-01](#seg-01--alto--escrita-de-chaves-estrangeiras-sem-checagem-de-dono-idor)).
3. Fazer `SECRET_KEY` e CORS falharem no boot em produção e adicionar rate limiting ([SEG-02](#seg-02--alto--sem-rate-limiting-e-com-html-injetável-nos-e-mails), [SEG-03](#seg-03--alto--configuração-de-produção-que-falha-aberta)).
4. Corrigir o status das recorrências futuras e o cálculo de vencimento ([FIN-01](#fin-01--crítico--receita-recorrente-lança-12-meses-no-saldo-de-uma-vez), [FIN-05](#fin-05--alto--cálculo-de-vencimento-quebra-em-meses-curtos-e-derruba-o-dashboard-executado)).
5. Consertar as pipelines de CI e começar os testes pelos cálculos financeiros ([OPS-01](#ops-01--alto--nenhum-teste-automatizado), [OPS-02](#ops-02--alto--as-duas-pipelines-de-ci-nunca-disparam)).

---

## 1. Visão geral do projeto

O Fluxar é um SaaS de finanças pessoais no modelo freemium (planos Comum, Premium e Premium Plus), com arquitetura desacoplada: uma API REST em Django e uma SPA em Next.js.

| | Backend (`fluxar-backend`) | Frontend (`fluxar-frontend`) |
|---|---|---|
| Stack | Python 3.11, Django 5, Django REST Framework, SimpleJWT, PostgreSQL 15 | Next.js 16 (App Router), React 19, TypeScript em modo strict, Tailwind CSS v4, Radix/shadcn, Recharts, axios, react-hook-form e zod |
| Infraestrutura | Render (Gunicorn e WhiteNoise), Cloudinary para imagens, e-mail via Resend com Brevo (SMTP) e EmailJS como fallback | Vercel |
| Tamanho | ~7,3 mil linhas de Python, sem contar migrações | 139 arquivos `.ts`/`.tsx`, ~28 mil linhas |
| Renderização | — | Tudo no cliente: todas as páginas, exceto `/`, são `"use client"` e buscam dados com axios em `useEffect`, sem cache nem deduplicação |

**Funcionalidades**

- Contas (corrente, poupança, carteira, investimento e cofrinho) e cartões de crédito com faturas: parcelamento, pagamento parcial com rolagem do restante para a fatura seguinte e estorno.
- Transações: receita, despesa, transferência, compra no cartão e recorrência.
- Categorias em árvore e tags.
- Orçamentos mensais por categoria.
- Metas com cofrinhos, aportes, resgates e cofrinho de arredondamento.
- Dashboard, calendário, relatórios e gráficos avançados, score financeiro e monitoramento de foco.
- Importação de OFX, CSV e XLSX com mapeamento de colunas e contas; exportação em PDF e XLSX.
- Backoffice administrativo: usuários, planos, papéis, logs, redefinição de senha, limpeza de dados e modo manutenção.

**Estágio**: MVP em fase de testes. Todos os recursos premium estão liberados para qualquer usuário autenticado, não há gateway de pagamento (a receita exibida no painel admin é estimada a partir dos planos) e não existe nenhum teste automatizado.

### 1.1 Mapa do domínio (backend)

| App | Modelos principais | Endpoints principais (`/api/...`) |
|---|---|---|
| `api` | `User` (UUID, login por e-mail, `plan`, `role`, `monthly_income`), tokens de verificação e de redefinição, `SystemLog`, `GlobalSetting` | `auth/register`, `auth/login`, `auth/refresh`, `auth/verify-email`, `auth/forgot-password`, `auth/reset-password`, `auth/me`, `users/me/...`, `token/`, `admin/...`, `health/` |
| `accounts` | `Account` (tipo, `initial_balance`, `balance` armazenado, exclusão lógica por `is_active`), `CreditCard` (`limit`, `closing_day`, `due_day`, conta de pagamento), `CreditCardInvoice` (mês e ano de vencimento, status, `total_amount` em cache) | `accounts/`, `credit-cards/` e `{id}/invoices/`, `invoices/` com `{id}/pay/` e `{id}/unpay/` |
| `transactions` | `Category` (árvore via `parent`), `Tag`, `Transaction` (tipo, status, `amount` decimal, parcelas, `transfer_id`, `invoice`, `recurring_source`), `RecurringTransaction` | `transactions/` com `transfer/`, `credit-card-expense/`, `bulk-delete/` e `bulk-update/`; `categories/`; `tags/` |
| `budgets` | `Budget` (categoria, mês, ano e limite; único por usuário, categoria e período) | `budgets/` com `bulk_import/` |
| `goals` | `Goal` (`target_amount`, `current_amount` armazenado, conta-cofrinho), `GoalDeposit` (aporte ou resgate) | `goals/` com `{id}/deposit/`, `withdraw/` e `history/` |
| `reports` | `FocusedMonitorItem` (categoria ou tag) | `reports/dashboard/`, `calendar/`, `charts/simple/`, `charts/advanced/`, `charts/monthly-comparison/`, `charts/tag-insights/`, `charts/tag-distribution/`; `focused-monitors/` |
| `data_exchange` | — | `import/ofx/`, `import/spreadsheet/` (e `preflight/`), `export/transactions/pdf/`, `export/transactions/xls/` |

**Como os números são calculados hoje**

- **Saldo**: `transactions/signals.py` mantém `Account.balance` com incrementos `F()` em `post_save` e `post_delete`. Só transações `COMPLETED` com conta afetam o saldo (entradas: `INCOME` e `TRANSFER_IN`; saídas: `EXPENSE`, `TRANSFER_OUT`, `INVOICE_PAYMENT` e `CREDIT_CARD`). Em paralelo, `AccountService.get_balance()` recalcula do zero com as mesmas regras e sem filtro de data; o dashboard e os relatórios usam esse segundo caminho.
- **Faturas**: uma compra parcelada gera N transações `PENDING` com `account` igual à conta de pagamento do cartão e `date` igual ao vencimento da fatura correspondente (a data real da compra não é guardada). `pay_invoice` marca os itens como `COMPLETED` na conta escolhida; o item em que o valor pago acaba é dividido em "(Parcial)" e "(Restante)", e o restante vai para a fatura seguinte. O status `CLOSED` nunca é atribuído.
- **Transferências**: duas transações com o mesmo `transfer_id`, criadas em `create_transfer`. A edição copia data e valor para a outra ponta; excluir uma ponta exclui a outra.
- **Recorrência**: gerada apenas na criação, dentro de `TransactionSerializer.create`: o modelo e mais 11 ocorrências. Não existe tarefa agendada nem comando que gere as seguintes.
- **Orçamentos**: calculados na leitura (despesas pelo mês da transação e compras de cartão pelo mês da fatura, incluindo `PENDING`).
- **Metas**: `current_amount` é um razão armazenado; o aporte manual é uma transferência real para o cofrinho mais um `GoalDeposit`. O comando `sync_goals` reconstrói o razão.
- **Relatórios**: calculados a cada requisição, com agregações do ORM e laços em Python, sem cache. Valores monetários saem como `float`.

---

## 2. Integridade financeira

### FIN-01 · CRÍTICO · Receita recorrente lança 12 meses no saldo de uma vez

**Onde:** `transactions/serializers.py:195`

```python
status='PENDING' if transaction.type in ['EXPENSE', 'CREDIT_CARD'] else 'COMPLETED',
```

**Cenário:** um salário mensal de R$ 5.000 marcado como recorrente gera 12 receitas `COMPLETED`. O saldo, tanto o armazenado quanto o recalculado, sobe R$ 60.000 na hora; 11 dessas receitas são de meses futuros.

**Correção sugerida:** criar as ocorrências futuras sempre como `PENDING` e efetivá-las na data, por confirmação do usuário ou por um comando agendado.

### FIN-02 · CRÍTICO · Estorno de fatura não devolve o dinheiro à conta

**Onde:** `accounts/services.py:240`

```python
paid_txs.update(status='PENDING')
```

**Cenário:** pagar uma fatura de R$ 1.000 debita R$ 1.000 da conta. No estorno, `QuerySet.update()` não dispara os signals e o saldo armazenado continua em −R$ 1.000; pagar de novo leva a −R$ 2.000, enquanto o saldo recalculado mostra −R$ 1.000. A conta usada, a `payment_date`, a divisão "(Parcial)/(Restante)" e os itens rolados para a fatura seguinte também não são revertidos.

**Correção sugerida:** registrar cada pagamento num modelo próprio (por exemplo, `InvoicePayment`) com tudo o que foi alterado e fazer o estorno desfazer esse registro dentro de `transaction.atomic`, salvando item a item ou recalculando o saldo das contas afetadas ao final.

### FIN-03 · CRÍTICO · Edição em lote de uma série ignora saldo e validação

**Onde:** `transactions/views.py:192` e `:197`

```python
update_data = {k: v for k, v in request.data.items() if k in ['description', 'amount', 'category']}
).update(**update_data)
```

**Cenário:** mudar um salário recorrente de R$ 5.000 para R$ 5.500 com o escopo "todas" reescreve as 12 transações `COMPLETED` sem alterar o saldo; a lista de contas e o dashboard passam a divergir em R$ 6.000. Os campos `account` e `type`, que a interface também envia, são descartados em silêncio, e os valores chegam ao banco sem validação, inclusive uma `category` de outro usuário.

**Correção sugerida:** validar o payload com um serializer, restringir `category` ao usuário e aplicar a alteração com `save()` item a item dentro de `transaction.atomic`, ou recalcular o saldo das contas afetadas depois do `update()`.

### FIN-04 · CRÍTICO · Editar uma transferência desalinha a conta de destino

**Onde:** `transactions/signals.py:111-113`

```python
).update(
    date=instance.date,
    amount=instance.amount,
```

**Cenário:** ao editar uma transferência de R$ 100 de A para B para R$ 150, a conta A é debitada em mais R$ 50, mas a outra ponta é alterada por `update()` e o saldo de B não muda: R$ 50 somem. Mudanças de status numa ponta nunca são copiadas para a outra.

**Correção sugerida:** atualizar a ponta parceira com `save()` usando uma flag que evite a recursão do signal, ou ajustar explicitamente o saldo da conta parceira pela diferença.

### FIN-05 · ALTO · Cálculo de vencimento quebra em meses curtos e derruba o dashboard [executado]

**Onde:** `accounts/services.py:112-113`, chamado por `transactions/services.py:96` e `reports/services.py:131`

```python
else:
    due_date = date(closing_year, closing_month, card.due_day)
```

**Cenário:** num cartão que fecha no dia 20 e vence no dia 30, qualquer compra entre 20/jan e 19/fev gera `ValueError: day is out of range for month` (erro 500). Como o dashboard chama essa função com a data de hoje para cada cartão, ele fica fora do ar para esse usuário durante todo o período; com vencimento no dia 31, isso acontece cinco vezes por ano. O outro ramo da mesma função já trata o fim de mês corretamente.

**Correção sugerida:** usar `relativedelta(day=card.due_day)` também nesse ramo, ou limitar o dia com `calendar.monthrange`.

### FIN-06 · ALTO · Parcelas duplicadas numa fatura e mês pulado com fechamento entre 29 e 31 [executado]

**Onde:** `transactions/services.py:93` e `:96`

```python
purchase_date_virtual = date + relativedelta(months=i)
due_date = CreditCardService.calculate_due_date(card, purchase_date_virtual)
```

**Cenário:** com fechamento no dia 30 e vencimento no dia 7, uma compra em 4x feita em 30/01/2026 coloca as parcelas 1 e 2 na fatura de 07/03/2026 e nenhuma em abril. Um cartão que fecha no dia 31 sofre isso depois de todo mês de 30 dias.

**Correção sugerida:** calcular o vencimento da primeira parcela e somar `relativedelta(months=i)` ao vencimento, em vez de deslocar a data da compra.

### FIN-07 · ALTO · Total da fatura só é atualizado na fatura de destino

**Onde:** `transactions/signals.py:82` e `:89`, acionado por `accounts/services.py:155-156`

```python
if instance.invoice:
    total = instance.invoice.transactions.filter(
```

**Cenário:** pagar R$ 600 de uma fatura de R$ 1.000 move R$ 400 para o mês seguinte, mas a fatura paga mantém `total_amount = 1.000`. O histórico mostra uma fatura de R$ 1.000 paga e, depois de um estorno, o dashboard conta esses R$ 400 duas vezes no limite.

**Correção sugerida:** capturar a fatura anterior no `pre_save` e recalcular o total das duas (a antiga e a nova) no `post_save` e no `post_delete`.

### FIN-08 · ALTO · Pagamento de fatura sem atomicidade nem trava

**Onde:** `accounts/views.py:93-94`; o serviço em `accounts/services.py:117-224` não usa `atomic` nem `select_for_update`

```python
except Exception as e:
    return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
```

**Cenário:** um erro no meio do laço deixa os itens já processados como `COMPLETED` e debitados, com a fatura ainda aberta. [inferido] Um duplo clique envia dois pagamentos que passam juntos pela checagem de "já paga" e podem duplicar a linha "(Restante)".

**Correção sugerida:** `@transaction.atomic` no serviço, `select_for_update()` na fatura (e na conta) com a checagem de status dentro da trava, e capturar só erros de validação na view.

### FIN-09 · ALTO · Razão da meta não é revertido quando a transação é excluída ou editada

**Onde:** `goals/signals.py:101-102`; edições são ignoradas em `goals/signals.py:17-18`

```python
# Ao deletar, removemos tanto o registro manual quanto o automático
GoalDeposit.objects.filter(transaction_id=txn_ref).delete()
```

**Cenário:** aportar R$ 500 numa meta e depois excluir essa transferência reverte os saldos e apaga o histórico, mas `current_amount` continua em R$ 500. A meta mostra uma economia que não existe, não pode ser excluída (`goals/views.py:22`) e um resgate de R$ 500 leva o cofrinho a −R$ 500.

**Correção sugerida:** derivar `current_amount` da soma dos `GoalDeposit` (a mesma lógica do `sync_goals`) a cada alteração, em vez de manter um incremento em cache.

### FIN-10 · ALTO · Duas fontes de verdade para o saldo, e o dashboard soma contas excluídas

**Onde:** `reports/services.py:69-71`

```python
accounts = Account.objects.filter(user=user)
from accounts.services import AccountService
total_balance = sum(AccountService.get_balance(acc) for acc in accounts)
```

**Cenário:** depois de qualquer um dos casos FIN-02 a FIN-04, os cartões de conta (saldo armazenado) e o "saldo total" do dashboard (recalculado) discordam. Uma conta excluída com R$ 2.000 continua somando no dashboard, mas não aparece na lista de contas nem em `total_liquid_balance` (`reports/services.py:234`, que filtra contas ativas).

**Correção sugerida:** escolher uma única fonte de verdade. A opção mais segura é calcular o saldo por agregação (com índice) e usar o campo apenas como cache reconstruível; a alternativa é garantir que toda escrita passe pela camada de serviço e rodar uma conciliação periódica (`init_balances`). Em ambos os casos, filtrar `is_active=True` de forma consistente.

### FIN-11 · ALTO · Importação informa sucesso mesmo quando nada foi gravado [inferido]

**Onde:** `data_exchange/services.py:305-307` e `:429-430` (o OFX tem a mesma estrutura em `:44-88`); resposta em `data_exchange/views.py:105`

```python
with transaction.atomic():
    for index, row in enumerate(records):
        try:
```

**Cenário:** uma única linha com descrição acima de 255 caracteres, ou com uma categoria nova acima de 50, gera erro de banco dentro do bloco atômico. Todas as linhas seguintes falham, tudo é desfeito e, mesmo assim, a resposta é HTTP 200 com `imported: N`, porque a view testa `created >= 0`, que é sempre verdadeiro.

**Correção sugerida:** usar um savepoint por linha (`with transaction.atomic():` dentro do laço), validar tamanhos antes de salvar e montar a resposta a partir do que foi realmente gravado.

### FIN-12 · ALTO · Importação classifica "Crédito" e "Entrada" como despesa

**Onde:** `data_exchange/services.py:368-369`

```python
type_str = str(row[col_type]).upper()
if type_str in ['INCOME', 'RECEITA', 'C', 'CREDITO']:
```

**Cenário:** num extrato cuja coluna de tipo diz "Crédito", o valor vira "CRÉDITO" (com acento), que não está na lista; todo crédito é importado como despesa e o saldo erra pelo dobro de cada crédito.

**Correção sugerida:** normalizar acentos (`unicodedata`) e aceitar também "ENTRADA", ou inferir o tipo pelo sinal do valor quando a coluna não for reconhecida.

#### FIN-13 · MÉDIO · Recorrência mensal escorrega para o dia 28 [executado]

**Onde:** `transactions/serializers.py:183` (`current_date += delta`). Um aluguel criado em 31/01/2026 recebe as datas 28/02, 28/03, 28/04 e assim por diante; uma recorrência anual a partir de 29/02 fica presa em 28/02. **Correção:** calcular cada ocorrência a partir da data inicial (`start + relativedelta(months=i)`), não da ocorrência anterior.

#### FIN-14 · MÉDIO · Recorrências param depois de 12 ocorrências

**Onde:** `transactions/serializers.py:176` (`for _ in range(11):`). Uma recorrência diária termina em 12 dias sem aviso; os campos `end_date`, `last_processed` e `is_active` de `RecurringTransaction` (`transactions/models.py:134-137`) nunca são lidos. A página "Recorrentes" do frontend depende de um filtro que o backend não implementa (ver CON-07). **Correção:** gerar as ocorrências por um comando agendado que use `last_processed` e `end_date`.

#### FIN-15 · MÉDIO · Compras no cartão gravam o vencimento como data da compra

**Onde:** `transactions/services.py:118` (`date=due_date`). Calendário, relatórios por dia da semana e mapa de calor mostram datas de vencimento em vez de datas de compra. Alterar a data ou o cartão de uma compra na edição não a move de fatura, porque `invoice` é somente leitura (`transactions/serializers.py:77`). **Correção:** guardar a data da compra e a fatura separadamente e recalcular a fatura quando a data ou o cartão mudarem.

#### FIN-16 · MÉDIO · Transferência com uma ponta só

**Onde:** `transactions/serializers.py:144`. Um `POST /transactions/` com `type=TRANSFER_OUT` cria uma única ponta: o dinheiro sai de A e não chega a lugar nenhum. Como `type` e `status` continuam editáveis, mudar uma ponta para `INCOME` deixa um `TRANSFER_OUT` órfão. **Correção:** bloquear os tipos de transferência no endpoint genérico e tornar `type` imutável em transferências.

#### FIN-17 · MÉDIO · Compras de cartão sem fatura quando criadas pela API genérica

**Onde:** `transactions/serializers.py:192`. Transações `CREDIT_CARD` recorrentes ou criadas pelo endpoint genérico ficam sem `invoice`: nunca aparecem numa fatura nem podem ser pagas, mas contam para sempre no limite usado (`accounts/services.py:50-54`). **Correção:** obrigar compras de cartão a passar por `create_credit_card_expense`.

#### FIN-18 · MÉDIO · Valores sem checagem de sinal ou de zero

**Onde:** `accounts/serializers.py:37`, `transactions/serializers.py:251` e `:266`, e o próprio campo do modelo. `POST /invoices/{id}/pay/` com `amount: 0` marca a fatura como paga e rola todos os itens para o mês seguinte (a interface exige no mínimo R$ 0,01; a API, não). Uma despesa de −100 aumenta o saldo em 100. **Correção:** `min_value=Decimal('0.01')` nos serializers e `CheckConstraint` com `amount__gt=0` no banco.

#### FIN-19 · MÉDIO · Edições concorrentes sem trava [inferido]

**Onde:** `transactions/signals.py:157`. Dois `PATCH` simultâneos marcando a mesma conta de R$ 300 como paga leem o estado "não pago" e ambos debitam: o saldo cai R$ 600. O mesmo vale para aportes simultâneos em metas (`goals/services.py:67-68`), e salvar uma `Account` inteira sobrescreve incrementos `F()` concorrentes. Não há `select_for_update` no projeto. **Correção:** travar a linha no `pre_save` com `select_for_update` dentro de uma transação e usar `update_fields` ao salvar contas.

#### FIN-20 · MÉDIO · Aporte na meta a partir do próprio cofrinho infla a meta

**Onde:** `goals/services.py:47-48`. Escolher o próprio cofrinho como origem cria uma autotransferência com efeito zero, mas `current_amount += amount` é executado mesmo assim. **Correção:** rejeitar origem igual ao cofrinho da meta.

#### FIN-21 · MÉDIO · Deduplicação da importação descarta lançamentos reais

**Onde:** `data_exchange/services.py:389`. Duas compras de R$ 5,00 na "PADARIA" no mesmo dia são tratadas como duplicata e a segunda é descartada. O OFX usa uma chave parecida (`:60`) em vez do `FITID`, então reimportar depois de editar uma descrição duplica o lançamento. **Correção:** usar o `FITID` no OFX e, em planilhas, deduplicar apenas contra lançamentos que já existem no banco, não entre linhas do mesmo arquivo.

#### FIN-22 · MÉDIO · Linhas ignoradas em silêncio e valores brasileiros mal interpretados

**Onde:** `data_exchange/services.py:319-324`. "1.500" é importado como R$ 1,50 e "1.234,56" falha; linhas com data ilegível caem num `except: continue` e não são contadas nem reportadas. **Correção:** detectar o formato (ponto de milhar e vírgula decimal) e reportar cada linha ignorada.

#### FIN-23 · MÉDIO · Linhas de contas não mapeadas são redirecionadas

**Onde:** `data_exchange/services.py:276` e `:382-385`. Linhas de uma conta não mapeada vão para a conta padrão, ou ficam com `account=None` (sem nenhum impacto no saldo) quando nenhuma conta padrão foi escolhida, o que `data_exchange/views.py:90` permite. **Correção:** rejeitar a importação quando houver contas não mapeadas.

#### FIN-24 · MÉDIO · Exportação em PDF quebra com lançamentos sem conta

**Onde:** `data_exchange/services.py:479` (`tx.account.name[:15]`). Uma compra num cartão sem conta de pagamento, ou uma importação sem conta, gera `AttributeError` e a exportação inteira retorna 500.

#### FIN-25 · MÉDIO · Filtros da exportação diferem dos da lista de transações

**Onde:** `data_exchange/views.py:128-129`. A lista trata "EXPENSE" como despesas mais compras no cartão (`transactions/views.py:98-99`); a exportação não, então exportar "Despesas" omite as compras no cartão que aparecem na tela. **Correção:** extrair um único filtro compartilhado.

#### FIN-26 · MÉDIO · Score financeiro considera todo orçamento estourado

**Onde:** `reports/services.py:299` (há um `TODO` no próprio código). Um usuário com quatro orçamentos saudáveis perde os 20 pontos da parte de orçamentos do `financial_score`.

#### FIN-27 · MÉDIO · Duas fórmulas para o limite disponível do cartão

**Onde:** `accounts/services.py:56` (limite menos transações pendentes) e `reports/services.py:137` (limite menos faturas não pagas). Depois de um pagamento parcial, de uma rolagem ou de um estorno, a página do cartão e o dashboard mostram limites diferentes para o mesmo cartão.

#### FIN-28 · MÉDIO · Exclusão definitiva de usuário com compras no cartão provavelmente falha [inferido]

**Onde:** `transactions/signals.py:82`. No `user.delete()`, o Django pode excluir as faturas antes das transações; esse handler consulta uma fatura que já não existe e a exclusão (`api/views.py:424` e `:670`) é desfeita com erro 500. É o mesmo tipo de erro já contornado para contas em `transactions/signals.py:197-198`.

#### FIN-29 · MÉDIO · Coluna de saldo criada sem preencher as contas existentes [inferido]

**Onde:** `accounts/migrations/0004_account_balance.py:13-15`. Contas criadas antes dessa migração guardam apenas as movimentações posteriores a ela, a menos que `init_balances` tenha sido executado manualmente; o `entrypoint.sh` não o executa. **Correção:** rodar `init_balances` em produção e comparar o resultado com `AccountService.get_balance()`.

#### Itens de severidade BAIXO

| ID | Problema | Onde |
|---|---|---|
| FIN-30 | O próximo vencimento usa o dia 28 como fallback e devolve o vencimento deste mês mesmo depois que ele passou | `accounts/services.py:83-86` |
| FIN-31 | Com fechamento no dia 31, uma compra em 30/04 (o fechamento efetivo de abril) continua na fatura atual | `accounts/services.py:97` |
| FIN-32 | O histórico de investimentos volta de 30 em 30 dias e pula ou duplica meses: a partir de 31/03/2026 saem 11, 12, 12, 01, 03, 03 [executado] | `reports/services.py:520` |
| FIN-33 | O gráfico de patrimônio volta no tempo a partir de um saldo só com `COMPLETED`, mas subtrai movimentações `PENDING` e compras datadas no vencimento | `reports/services.py:461-464` |
| FIN-34 | `TIME_ZONE = 'UTC'` com `date.today()`: depois das 21h em Brasília, "hoje" já é amanhã; o mapa de calor por hora usa `created_at` em UTC | `core/settings.py:131`, `reports/services.py:485` |
| FIN-35 | Excluir a parcela 1/12 apaga as 12 (CASCADE no pai); excluir a 5/12 apaga só ela | `transactions/models.py:97` |
| FIN-36 | Excluir uma série apaga também o histórico já efetivado e deixa o modelo de recorrência ativo | `transactions/views.py:166-169` |
| FIN-37 | Uma transferência entre dois cofrinhos com metas credita só o lado de origem (deduplicação por `transfer_id`) | `goals/signals.py:41` |
| FIN-38 | O arredondamento por meta deixa diferença de centavos entre o total das metas e o saldo do cofrinho | `goals/signals.py:60` |
| FIN-39 | A transferência aceita origem igual ao destino e contas inativas | `transactions/serializers.py:248-261` |
| FIN-40 | O mês do orçamento não é validado (13 é aceito) | `budgets/views.py:66` |
| FIN-41 | `CreditCardInvoiceViewSet` é um `ModelViewSet` completo: `POST /invoices/` sem `card` gera erro 500 | `accounts/views.py:59` |
| FIN-42 | "Limpar dados" do admin apaga em nove etapas, sem transação | `api/views.py:634-642` |
| FIN-43 | O comando `cleanup_db` apaga contas inativas em cascata, levando junto as pontas de transferências em contas ativas (alterando seus saldos) e `GoalDeposit` sem ajustar `current_amount` | `accounts/management/commands/cleanup_db.py:27` |
| FIN-44 | Os modelos usam `DecimalField(15,2)`, mas os relatórios convertem valores para `float` (37 ocorrências), há multiplicação em float e um `Decimal` criado a partir de float do JSON | `reports/services.py:768`, `api/views.py:474-476`, `goals/views.py:53` |

---

## 3. Segurança e privacidade

### SEG-01 · ALTO · Escrita de chaves estrangeiras sem checagem de dono (IDOR)

**Onde:**

- `transactions/serializers.py:64-80`: `account`, `credit_card`, `category` e `tags` do `TransactionSerializer` (só `target_account_id` é filtrado por usuário)
- `transactions/serializers.py:14`: `parent` do `CategorySerializer`
- `budgets/serializers.py:16`: `category` do `BudgetSerializer`
- `goals/serializers.py:32`: `account` do `GoalSerializer`
- `reports/serializers.py:11`: `category` e `tag` do `FocusedMonitorItemSerializer`
- `transactions/views.py:192`: `category` no `bulk-update`

São campos gerados automaticamente pelo `ModelSerializer`, com `queryset=<Modelo>.objects.all()`. O signal de saldo aplica o valor na conta indicada sem verificar o dono (`transactions/signals.py:187`):

```python
Account.objects.filter(id=new_account_id).update(balance=F('balance') + diff)
```

**Cenário:** quem souber o UUID de uma conta de outro usuário consegue lançar transações que alteram o saldo dessa conta, ler o nome dela em `account_detail` na resposta, injetar subcategorias na árvore de categorias da vítima (`get_subcategories` não filtra por usuário) e, com uma meta ligada à conta alheia, fazer aportes nela. As leituras continuam protegidas pelo `UserQuerySetMixin`; hoje a única barreira na escrita é o UUID v4 ser difícil de adivinhar.

**Correção sugerida:** um serializer base que restrinja ao `request.user` o queryset de todo campo relacional cujo modelo tenha `user`, mais validação de dono na camada de serviço (`create_transfer`, `GoalService`) como defesa em profundidade.

### SEG-02 · ALTO · Sem rate limiting e com HTML injetável nos e-mails

**Onde:** `core/settings.py:171-180` (nenhum `DEFAULT_THROTTLE_CLASSES`); `api/utils/email_service.py:213` e `:292`

```python
<h2 style="font-size: 20px; font-weight: 700; margin-bottom: 16px;">Olá, {user.name}!</h2>
```

**Cenário:** login, cadastro e "esqueci a senha" aceitam requisições ilimitadas, o que permite força bruta de senhas e disparo ilimitado de e-mails pela conta Resend/Brevo, com risco de suspensão do remetente. Como o nome entra sem escape no HTML, qualquer pessoa pode cadastrar o e-mail de um terceiro com um "nome" contendo links e texto arbitrários e fazer o Fluxar enviar esse conteúdo com o remetente oficial.

**Correção sugerida:** `ScopedRateThrottle` com limites por escopo (por exemplo, login 5/min; cadastro e redefinição 3/hora por IP e por e-mail), `django.utils.html.escape` ou templates do Django com autoescape nos e-mails, e restrição de caracteres no nome.

### SEG-03 · ALTO · Configuração de produção que falha aberta

**Onde:** `core/settings.py:17` e `:184-188`

```python
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-key')
```

**Cenário:** se a variável faltar em algum deploy, a aplicação sobe com uma chave pública; como o SimpleJWT assina os tokens com a `SECRET_KEY`, qualquer pessoa consegue forjar tokens de qualquer usuário, inclusive de administradores. Sem `CORS_ALLOWED_ORIGINS`, o CORS libera todas as origens. Além disso, a chave original gerada pelo `startproject` está no histórico público do repositório (ver Apêndice B).

**Correção sugerida:** lançar `ImproperlyConfigured` quando `DEBUG=0` e a variável não existir; usar lista vazia como padrão do CORS; rodar `manage.py check --deploy` na CI; confirmar que a chave de produção é diferente da que está no histórico e, se for a mesma, trocá-la (o que encerra as sessões ativas).

### SEG-04 · ALTO · Dependências com vulnerabilidades conhecidas e framework fora de suporte

**Onde:** `fluxar-frontend/package.json`; `requirements.txt`

**Cenário:**

- O `npm audit --omit=dev` aponta 7 vulnerabilidades no frontend: 1 crítica, 5 altas e 1 moderada (Apêndice A). O Next 16.0.10 acumula 33 alertas, entre eles execução remota de código no Image Optimization com AVIF e em servidores Windows; a correção está na 16.3.3 ou superior. O axios 1.13.2 tem 29 alertas de severidade alta. Parte dos alertas do Next pode não se aplicar ao ambiente gerenciado da Vercel, mas a atualização é necessária.
- O `requirements.txt` limita o Django a `<5.2`, ou seja, à série 5.1, sem correções de segurança desde dezembro de 2025. O DRF está limitado a `<3.15` e o SimpleJWT a `<5.4`.

**Correção sugerida:** atualizar o Next (16.3.3 ou superior) e o axios; migrar para o Django 5.2 LTS (suportado até abril de 2028) com versões compatíveis de DRF e SimpleJWT; fixar versões exatas (por exemplo, com `pip-tools`) e rodar `npm audit` e `pip-audit` na CI.

### SEG-05 · MÉDIO · Sessões longas e sem revogação

**Onde:** `fluxar-frontend/src/contexts/auth-context.tsx:79-81`; `core/settings.py:194-202`; `fluxar-frontend/next.config.ts`

```ts
localStorage.setItem("fluxar.token", token)
if (refreshToken) {
    localStorage.setItem("fluxar.refresh_token", refreshToken)
```

**Cenário:** o token de acesso (60 minutos) e o de renovação (7 dias) ficam no `localStorage`, sem rotação, sem lista de revogação e sem endpoint de logout. Qualquer XSS ou dependência maliciosa que leia o token de renovação ganha 7 dias de acesso, mesmo depois do logout; trocar ou redefinir a senha não invalida os tokens já emitidos. O `next.config.ts` não define cabeçalhos, então não há CSP nem `frame-ancestors`.

**Correção sugerida:** ativar `rest_framework_simplejwt.token_blacklist` com `ROTATE_REFRESH_TOKENS` e `BLACKLIST_AFTER_ROTATION`, criar um endpoint de logout, revogar todos os tokens do usuário ao trocar ou redefinir a senha e definir CSP no `next.config.ts`. Idealmente, mover o token de renovação para um cookie `httpOnly`.

### SEG-06 · MÉDIO · Duas regras diferentes para administrador

**Onde:** `fluxar-frontend/src/components/auth/admin-guard.tsx:16`; `api/views.py:282` e demais views admin com `IsAdminUser`; `create_admin.py:39-57`

```ts
} else if (user?.role !== "ADMIN") {
```

**Cenário:** o frontend libera o painel pelo campo `role`; o backend autoriza por `is_staff`, e o painel edita apenas `role`. Rebaixar um administrador para USER esconde a interface, mas ele continua podendo chamar `/api/admin/*` diretamente, inclusive exclusão definitiva e limpeza de dados; promover alguém a ADMIN pelo painel mostra a interface sem dar acesso à API. Quando o `entrypoint.sh` é usado, o `create_admin.py` ainda repromove o usuário configurado a cada boot, desfazendo rebaixamentos.

**Correção sugerida:** uma única fonte de verdade: uma permission que verifique `role == 'ADMIN'`, ou sincronizar `is_staff` com `role` no `save()` do usuário. No `create_admin.py`, apenas criar o usuário, sem repromover.

### SEG-07 · MÉDIO · Tela de usuário do admin exibe dados falsos quando a API falha

**Onde:** `fluxar-frontend/src/services/admin.ts:107-109`

```ts
} catch (error) {
    console.warn("API de detalhes de usuário não encontrada, usando mock de fallback.")
    // Mock fallback for development if backend isn't ready
```

**Cenário:** depois de um erro 500 momentâneo, a página mostra "Usuário Mock / mock@fluxar.com / PREMIUM" com o `id` do usuário real; o administrador pode alterar o plano ou excluir definitivamente esse usuário vendo uma identidade falsa.

**Correção sugerida:** remover o fallback e exibir o erro.

### SEG-08 · MÉDIO · Liberação do premium espalhada e sem controle central

**Onde:** `core/permissions.py:20-28`, `reports/permissions.py:4-13`, `core/services/plan_limits.py:6-22`, `transactions/services.py:180-185` (com um plano `FREE` inexistente), `fluxar-frontend/src/hooks/use-plan.ts:7-8` e `fluxar-frontend/src/app/(app)/relatorios/page.tsx:55` e `:313`

```ts
// Fase de Testes: Todos os usuários têm acesso total
const plan = "PREMIUM_PLUS" as any
```

**Cenário:** as permissions do backend retornam `True`, os limites de plano estão em 999 e o frontend fixa o plano em dois lugares diferentes. Quando a cobrança começar, esquecer um desses pontos deixa o premium acessível de graça pela API. Há ainda inconsistências: a página de importação ignora a liberação e mostra "Recurso Exclusivo" na exportação (`fluxar-frontend/src/app/(app)/importar/page.tsx:70`), e os limites de contas e cartões existem só na interface e divergem do backend (`fluxar-frontend/src/app/(app)/cartoes/page.tsx:37-41` e `fluxar-frontend/src/app/(app)/contas/page.tsx:38-42`).

**Correção sugerida:** uma única flag de configuração (por exemplo, um `GlobalSetting` ou uma variável de ambiente) consultada pelas permissions e pelos limites do backend e exposta ao frontend pelo `/auth/me`, removendo os desvios locais.

### SEG-09 · MÉDIO · Privacidade e LGPD

**Onde:** `api/models.py:46-56`; `api/urls.py`; `core/services/plan_limits.py:32` e `:40`; `transactions/views.py:40`, `:44` e `:46`; `api/views.py:154`; `media/`

**Cenário:**

- CPF, telefone, data de nascimento e renda mensal ficam em texto puro.
- Não existe endpoint para o usuário excluir a própria conta ou exportar os próprios dados.
- [inferido] Como o CPF é único e o `PUT /users/me/` devolve o erro de unicidade, o endpoint funciona como consulta de "este CPF está cadastrado?".
- O e-mail do usuário é impresso a cada emissão de token e verificação de limite, o payload completo de criação de categoria vai para o log e e-mails não cadastrados são registrados nas tentativas de redefinição.
- Uma foto pessoal (`media/avatars/Eu.jpeg`) e imagens de terceiros com direitos autorais estão versionadas.

**Correção sugerida:** criar exclusão e exportação de conta pelo próprio usuário, avaliar se o CPF é necessário (ou criptografá-lo), trocar a mensagem de unicidade por uma genérica, remover os `print` com dados pessoais e tirar `media/` do repositório, adicionando a pasta ao `.gitignore`.

#### Itens de severidade BAIXO

| ID | Problema | Onde |
|---|---|---|
| SEG-10 | A mensagem de login revela que uma conta existe e está inativa, mesmo com a senha errada | `api/serializers.py:142-145` |
| SEG-11 | O e-mail diferencia maiúsculas: "Ana@x.com" e "ana@x.com" viram contas distintas, e o login falha com a caixa diferente [inferido] | `api/models.py:39`, `api/views.py:130` |
| SEG-12 | Há dois endpoints de login (`auth/login/` e `token/`) com serializers duplicados | `api/urls.py:29` e `:60`, `api/serializers.py:127`, `api/serializers_auth.py:5` |
| SEG-13 | Faltam `SECURE_PROXY_SSL_HEADER`, HSTS, redirecionamento para HTTPS e cookies seguros para o admin do Django | `core/settings.py` |
| SEG-14 | Se `NEXT_PUBLIC_API_URL` faltar na Vercel, o frontend aponta para `http://localhost:8000/api` sem avisar | `fluxar-frontend/src/services/apiClient.ts:8` e `:99`, `fluxar-frontend/src/lib/utils.ts:13` |
| SEG-15 | O `debug_serializer.py` apaga e recria um usuário; como `DATABASE_URL` tem prioridade, rodá-lo no contêiner de produção escreveria no banco de produção | `debug_serializer.py`, `core/settings.py:88-93` |

---

## 4. Contratos entre frontend e backend

### CON-01 · CRÍTICO · Redefinição de senha nunca funciona

**Onde:** `fluxar-frontend/src/app/auth/reset-password/page.tsx:56`; `api/serializers.py:167-175`

```ts
await api.post("/auth/reset-password/", { token, password: data.newPassword })
```

**Cenário:** o backend exige `new_password` e `new_password_confirm`. Toda tentativa recebe 400 e o usuário vê "O link pode ter expirado"; quem esquece a senha fica sem acesso à conta.

**Correção sugerida:** enviar `{ token, new_password, new_password_confirm }`.

### CON-02 · ALTO · Listas cortadas no 10º item

**Onde:** `core/settings.py:178-179`; `fluxar-frontend/src/services/tags.ts:9-10`, `fluxar-frontend/src/services/budgets.ts:9-10` e `fluxar-frontend/src/app/(app)/cartoes/page.tsx:75`

```python
'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
'PAGE_SIZE': 10,
```

**Cenário:** tags, orçamentos, metas, cartões, monitores de foco e logs do admin usam a paginação padrão de 10, e o frontend lê apenas o `results` da primeira página. A 11ª tag não pode ser escolhida em nenhum formulário e o 11º orçamento do mês não aparece.

**Correção sugerida:** desativar a paginação nesses viewsets de coleções pequenas (como já é feito em contas e categorias) ou fazer o frontend percorrer as páginas.

### CON-03 · ALTO · Detalhe da fatura mostra no máximo 20 compras

**Onde:** `fluxar-frontend/src/components/cards/invoice-details-dialog.tsx:64-66`

```ts
const response = await api.get(`/transactions/?invoice=${invoice.id}`)
const data = response.data.results || response.data
setTransactions(data)
```

**Cenário:** uma fatura com 35 compras lista 20 itens embaixo do total completo, sem forma de paginar.

**Correção sugerida:** paginar no diálogo ou criar um endpoint de itens da fatura sem paginação.

### CON-04 · ALTO · Preferências nunca são salvas

**Onde:** `fluxar-frontend/src/app/(app)/configuracoes/page.tsx:99-100`; `api/serializers.py:61-66` e `:109-113`

```ts
...user, // Preserve other user data
preferences: {
```

**Cenário:** o backend espera campos planos (`currency`, `theme_preference`, `language` e `notification_settings`) e ignora o objeto `preferences`. O usuário vê um toast de sucesso, o `refreshUser` traz os valores antigos e o tema volta ao anterior.

**Correção sugerida:** enviar os campos planos, ou fazer o serializer aceitar `preferences`.

### CON-05 · ALTO · Filtro por categoria aplica só o último ID

**Onde:** `fluxar-frontend/src/app/(app)/transacoes/page.tsx:315`; `transactions/views.py:80`

```ts
uniqueIds.forEach(id => params.append('categoryId', id))
```

**Cenário:** o backend lê `query_params.get('categoryId')`, que devolve apenas o último valor. Filtrar por "Alimentação" esconde os gastos da categoria-pai e de todas as subcategorias menos uma.

**Correção sugerida:** no backend, usar `getlist('categoryId')` com `category_id__in`.

### CON-06 · ALTO · Ajuste de saldo falha com centavos [executado]

**Onde:** `fluxar-frontend/src/components/accounts/balance-adjustment-dialog.tsx:78` e `:88`

```ts
const difference = newBalance - account.balance
const absAmount = Math.abs(difference)
```

**Cenário:** `Math.abs(999.9 - 1000.1)` resulta em `0.20000000000004547`; o `DecimalField` do DRF recusa mais de duas casas decimais, a requisição volta 400 e o usuário vê um erro genérico.

**Correção sugerida:** arredondar para centavos antes de enviar, ou trabalhar com centavos inteiros.

#### CON-07 · MÉDIO · Página "Recorrentes" lista transações quaisquer

**Onde:** `fluxar-frontend/src/app/(app)/transacoes/recorrentes/page.tsx:39-40`. O filtro `?is_recurring=true` não existe no backend, então a página mostra as últimas 20 transações de qualquer tipo. Nenhum link leva a ela.

#### CON-08 · MÉDIO · Editar uma transferência ignora a conta de origem

**Onde:** `fluxar-frontend/src/components/transactions/transfer-form-dialog.tsx:244`. O campo enviado é `account_id`, mas o serializer usa `account`; a alteração é descartada e o usuário vê "Transferência atualizada" com o débito ainda na conta antiga. O fallback em `:137-140` consulta `?transfer_id=`, filtro que o backend não implementa, e pega a primeira outra transação que encontrar como "parceira".

#### CON-09 · MÉDIO · Pagamento sem fatura selecionada cria um registro órfão

**Onde:** `fluxar-frontend/src/components/transactions/invoice-payment-dialog.tsx:196-200`. O fallback envia um `POST /transactions/` com `account_id` (ignorado pelo backend) e `type: "INVOICE_PAYMENT"`; o usuário vê "Pagamento registrado!", mas nenhuma fatura é paga e nenhuma conta é debitada. [inferido] O formulário não exige a fatura, então o caminho é alcançável.

#### CON-10 · MÉDIO · Logs de auditoria do admin sempre vazios

**Onde:** `fluxar-frontend/src/app/(admin)/admin/configuracoes/page.tsx:32`. O endpoint devolve um objeto paginado e a página espera uma lista, então mostra "Nenhum log encontrado". A mesma página exibe valores fixos ("Uptime: 99.9%", versão de build, "PostgreSQL 15.4"), e o botão "Limpar Cache" (`:69-71`) apenas espera 2 segundos e mostra sucesso.

#### CON-11 · MÉDIO · Exportação inclui um dia a mais [inferido]

**Onde:** `fluxar-frontend/src/services/import-export.ts:94-95` e `data_exchange/views.py:135-137`. O axios serializa as datas com `toISOString`, então o fim de setembro no Brasil vira `2026-10-01T02:59:59.999Z`; o backend usa `parse_datetime(...).date()` e a exportação de setembro inclui o dia 1º de outubro.

#### Itens de severidade BAIXO

| ID | Problema | Onde |
|---|---|---|
| CON-12 | `?limit=50` é ignorado pelo backend, e `getFocusedMonitors` é tipado como lista, mas recebe um objeto paginado | `fluxar-frontend/src/components/transactions/transaction-form-dialog.tsx:204` |

---

## 5. Frontend: sessão, robustez e experiência

### FE-01 · ALTO · Qualquer erro em `/auth/me` desloga o usuário

**Onde:** `fluxar-frontend/src/contexts/auth-context.tsx:62-64`

```ts
} catch {
  logout()
}
```

**Cenário:** recarregar a página enquanto o Render responde 502 (deploy ou cold start) apaga tokens válidos e manda o usuário para o login.

**Correção sugerida:** deslogar apenas em 401, depois de a renovação falhar; em erros de rede ou 5xx, manter a sessão e tentar de novo.

### FE-02 · ALTO · Toasts do `useToast` nunca aparecem

**Onde:** `fluxar-frontend/src/app/layout.tsx:50`

```tsx
<Toaster richColors closeButton position="top-right" />
```

**Cenário:** esse `Toaster` é o do Sonner; o `Toaster` do Radix, que renderiza as mensagens de `useToast`, nunca é montado. Nove arquivos (dashboard, categorias, tags, orçamentos, calendário e os formulários de categoria, orçamento, importação de orçamentos e tag) perdem as mensagens de erro; uma falha ao salvar um orçamento, por exemplo, deixa o diálogo aberto sem nenhum retorno.

**Correção sugerida:** migrar esses arquivos para o `toast` do Sonner e remover o sistema do Radix.

### FE-03 · ALTO · Datas sem horário exibidas e salvas com um dia a menos [executado]

**Onde:** `fluxar-frontend/src/components/goals/GoalForm.tsx:139` e `:190`; exibição em `fluxar-frontend/src/components/transactions/invoice-payment-dialog.tsx:423`, `:442`, `:492-493`, `:505`, `:539` e `:558`, `fluxar-frontend/src/app/(app)/transacoes/recorrentes/page.tsx:142`, `fluxar-frontend/src/app/(app)/metas/page.tsx:499`, `fluxar-frontend/src/components/goals/GoalDetails.tsx:179` e `fluxar-frontend/src/app/(app)/relatorios/page.tsx:416`

```ts
target_date: initialData.target_date ? new Date(initialData.target_date) : null,
```

**Cenário:** `new Date("2026-12-31")` é interpretado em UTC; no fuso de Brasília vira 30/12 às 21h, e salvar a meta grava "2026-12-30", mesmo quando o usuário só troca o nome. Uma fatura com vencimento em 01/10 aparece como 30/09 ("Setembro"), o que pode levar à escolha da fatura errada.

**Correção sugerida:** usar `parseISO` do date-fns para datas sem horário, como já é feito em `fluxar-frontend/src/components/cards/invoice-list.tsx:164`.

#### FE-04 · MÉDIO · O cabeçalho `Authorization` padrão sobrevive ao logout [inferido]

**Onde:** `fluxar-frontend/src/services/apiClient.ts:106`. Depois de uma renovação, o token fica em `api.defaults.headers.common`, e o `logout()` (`fluxar-frontend/src/contexts/auth-context.tsx:99-104`) limpa apenas o `localStorage`. Na mesma aba, cadastro, redefinição e verificação de e-mail continuam enviando o token antigo; quando ele expira, o DRF responde 401 nessas views públicas, o interceptador redireciona e o formulário se perde.

#### FE-05 · MÉDIO · Renovação com falha redireciona até em páginas públicas [inferido]

**Onde:** `fluxar-frontend/src/services/apiClient.ts:115-117`. Num navegador com tokens antigos, abrir o link de verificação de e-mail falha: `/auth/verify-email/` responde 401 antes de a view rodar e a conta continua sem verificação.

#### FE-06 · MÉDIO · Formulários de meta interpretam "1.500" como R$ 1,50

**Onde:** `fluxar-frontend/src/components/goals/GoalForm.tsx:52-55`, com a mesma lógica em `GoalDepositForm.tsx` e `GoalWithdrawForm.tsx`. Sem vírgula, o ponto é tratado como separador decimal.

#### FE-07 · MÉDIO · Requisições sobrepostas e erros falsos na lista de transações

**Onde:** `fluxar-frontend/src/app/(app)/transacoes/page.tsx:355-367` e `:473`. A página busca duas vezes ao montar, a volta para a página 1 roda depois da busca e a pesquisa dispara a cada tecla, sem debounce nem cancelamento. Mudar um filtro estando na página 3 pede a página 3 primeiro, o DRF responde 404 e aparece "Erro ao carregar"; respostas fora de ordem podem deixar resultados antigos na tela.

#### FE-08 · MÉDIO · Mensagens de validação do backend são descartadas

**Onde:** `fluxar-frontend/src/components/transactions/transaction-form-dialog.tsx:186` e `fluxar-frontend/src/app/auth/register/page.tsx:83-87`. Erros por campo nunca aparecem; no cadastro, qualquer erro de e-mail vira "já está em uso" e uma senha comum mostra "Tente novamente mais tarde".

#### FE-09 · MÉDIO · Aviso de "servidor acordando" pode travar a aplicação [inferido]

**Onde:** `fluxar-frontend/src/services/apiClient.ts:7-12` e `fluxar-frontend/src/services/serverStatus.ts:24-29`. Não há timeout no axios e a sobreposição de tela cheia aparece sempre que uma requisição passa de 5 segundos; uma requisição travada, ou uma exportação de PDF legitimamente lenta, bloqueia a interface sem opção de cancelar.

#### FE-10 · MÉDIO · Cofrinho de arredondamento pode depositar o mesmo troco várias vezes

**Onde:** `fluxar-frontend/src/components/goals/SpareChangeBank.tsx:50`, `:97` e `:101`. Os arredondamentos são recalculados a partir das 20 últimas transações a cada montagem, sem registro do que já foi depositado, e todo o valor sai da conta da primeira transação.

#### Itens de severidade BAIXO

| ID | Problema | Onde |
|---|---|---|
| FE-11 | `isRefreshing` não é reiniciado quando não há token de renovação; requisições enfileiradas depois disso ficariam penduradas | `fluxar-frontend/src/services/apiClient.ts:92` e `:123-128` |
| FE-12 | O logout não limpa `dashboard_layout_config`, que não é separado por usuário, e não se propaga para outras abas | `fluxar-frontend/src/app/(app)/dashboard/page.tsx:180` |
| FE-13 | O cabeçalho mostra a navegação completa a usuários deslogados | `fluxar-frontend/src/components/layout/header.tsx:115-165` |
| FE-14 | O `MoneyInput` remove o sinal negativo (saldos negativos não podem ser digitados) e colar "100" resulta em R$ 1,00 | `fluxar-frontend/src/components/ui/money-input.tsx:30-31` |
| FE-15 | Os eixos dos gráficos mostram números sem formatação local abaixo de 1.000 | `fluxar-frontend/src/components/dashboard/MonthlyComparisonChart.tsx:137` |
| FE-16 | Aparece `**` literal em textos renderizados | `fluxar-frontend/src/app/auth/forgot-password/page.tsx:81`, `fluxar-frontend/src/app/auth/verify-email/page.tsx:97`, `fluxar-frontend/src/app/(app)/importar/page.tsx:289`, `fluxar-frontend/src/app/(app)/metas/page.tsx:129`, `fluxar-frontend/src/app/(app)/relatorios/page.tsx:322` e `:475` |
| FE-17 | A página de manutenção aponta para `/suporte`, que não existe | `fluxar-frontend/src/app/manutencao/page.tsx:67` |
| FE-18 | Média zero exibida como "Infinity%" e promessas rejeitadas sem tratamento | `fluxar-frontend/src/app/(app)/relatorios/page.tsx:736`, `:454-455` e `:481-482` |
| FE-19 | "Saldo do Dia" soma apenas a página atual da lista | `fluxar-frontend/src/app/(app)/transacoes/page.tsx` |
| FE-20 | `console.log` com payloads completos de transação em produção | `fluxar-frontend/src/components/transactions/transfer-form-dialog.tsx:117`, `:118`, `:135`, `:153` e `:181` |
| FE-21 | A vitrine de componentes `/design-system` é publicada em produção | `fluxar-frontend/src/app/design-system/` |

---

## 6. Performance

### PERF-01 · ALTO · N+1 na listagem de transações

**Onde:** `transactions/serializers.py:17-19`, `:96-100` e `:112-130`; o queryset em `transactions/views.py:62-116` não usa `select_related` nem `prefetch_related`

```python
def get_subcategories(self, obj):
    # Retorna subcategorias de 1º nível
    subs = obj.subcategories.filter(is_active=True)
```

**Cenário:** cada linha custa de 5 a 9 queries (conta, categoria, categoria-pai, subcategorias recursivas, tags duas vezes, transferência parceira e sua conta, modelo de recorrência): estimativa de 100 a 180 queries por página de 20 e até ~900 com `page_size=100`. O projeto inteiro tem 3 `select_related` e nenhum `prefetch_related`.

**Correção sugerida:** `select_related('account', 'category__parent', 'credit_card', 'recurring_source')`, `prefetch_related('tags')`, um serializer de categoria sem subcategorias para a lista e a parceira da transferência anotada por subquery.

#### PERF-02 · MÉDIO · Relatórios recalculam tudo a cada requisição

**Onde:** `reports/services.py:447`. `charts/advanced` reconstrói o dashboard inteiro só para obter o saldo total, percorre em Python todas as transações do período (`:450-462`) e faz consultas recursivas de categoria por item monitorado (`:570-652`). O dashboard roda duas agregações por conta, duas vezes (`:71` e `:240-241`), 3 queries por orçamento e 4 por cartão: dezenas de queries por requisição, podendo passar de 150 (estimativa).

#### PERF-03 · MÉDIO · N+1 em orçamentos, metas e categorias

**Onde:** `budgets/services.py:22-24` (cerca de 5 queries por orçamento) e `goals/serializers.py:21`. Cada meta da lista embute todo o histórico de aportes, com uma query de conta por aporte, e o payload cresce sem limite.

#### PERF-04 · MÉDIO · Sem índices para os filtros mais comuns

**Onde:** `transactions/models.py:56-109` não define `Meta.indexes`. Todos os relatórios filtram por usuário, período e tipo contando só com os índices das chaves estrangeiras; os filtros por `date__month` e `date__year` (`transactions/views.py:90`, `budgets/services.py:32-33` e vários pontos de `reports/services.py`) não aproveitam índice de data, e a busca usa `description__icontains`. **Correção:** índices em `(user, date)`, `(user, type, date)` e `(account, status)`, trocando os filtros por mês por intervalos de data.

#### Itens de severidade BAIXO

| ID | Problema | Onde |
|---|---|---|
| PERF-05 | O parâmetro `months` não tem limite superior (`tag-insights` faz uma query por mês, então `months=1000` são mil queries) e um valor não numérico gera 500 | `reports/views.py:57` e `:66` |
| PERF-06 | Uma query sem cache em toda requisição para checar o modo manutenção | `api/middleware.py:26` |
| PERF-07 | O pagamento de fatura faz cerca de 5 queries por item | `accounts/services.py:117-224` |
| PERF-08 | As exportações não têm limite de linhas nem carregamento antecipado de relações | `data_exchange/views.py:107-199` |

---

## 7. Operação, CI/CD e processo

### OPS-01 · ALTO · Nenhum teste automatizado

**Onde:** `api/tests.py` e `data_exchange/tests.py` contêm apenas o template do Django; o frontend não tem arquivos de teste nem executor de testes

**Cenário:** nada cobre os signals de saldo, o cálculo de faturas e parcelas, o pagamento e o estorno ou a importação, justamente onde estão os erros da seção 2.

**Correção sugerida:** começar com `pytest-django` nos cálculos financeiros (vencimento parametrizado por dia de fechamento, dia de vencimento e mês; parcelas; pagamento e estorno; signals de saldo; importação) e com Vitest nos utilitários de dinheiro e datas do frontend.

### OPS-02 · ALTO · As duas pipelines de CI nunca disparam

**Onde:** `.github/workflows/ci-backend.yml:6-7` e `:18`; `fluxar-frontend/.github/workflows/ci-frontend.yml:6-7` e `:18`

```yaml
paths:
  - 'fluxar-backend/**'
```

**Cenário:** os workflows vieram de um layout de monorepo. A raiz de cada repositório já é o próprio projeto, então o filtro de `paths` nunca casa e o `working-directory` não existe. Eles também só rodam em push e PR para a `main`, enquanto o trabalho entra pela `development`. Mesmo que rodassem, o backend faria apenas `compileall` e a checagem de migrações (sem testes e sem o `mypy` configurado em `mypy.ini`), e o lint do frontend falharia com 168 erros (Apêndice A).

**Correção sugerida:** remover `paths` e `working-directory`, rodar em PRs para `development` e `main` e incluir testes, `manage.py check --deploy`, `mypy`, `npm ci`, `tsc --noEmit`, lint e `next build`.

### OPS-03 · ALTO · Capacidade: um worker e trabalho pesado dentro da requisição

**Onde:** `DEPLOY.md` (comando de start `gunicorn core.wsgi:application`) e `entrypoint.sh:16`; `data_exchange/services.py:136-138`, `:242-246` e `:303`

**Cenário:** sem `--workers`, o Gunicorn sobe com um único worker síncrono, a menos que `WEB_CONCURRENCY` esteja definido no Render. Importação, relatórios e PDF rodam dentro da requisição; a importação não tem limite de tamanho e carrega na memória o arquivo, uma cópia dele em dicionários e todas as transações do usuário, com 3 ou mais queries por linha. [inferido] Um arquivo de ~20 mil linhas pode passar do `--timeout 120`: o worker é morto, tudo é desfeito e, enquanto isso, os demais usuários esperam.

**Correção sugerida:** configurar `--workers` (ou `WEB_CONCURRENCY`) de acordo com a memória do plano, limitar o tamanho do upload e mover importação e exportação para uma fila de tarefas.

### OPS-04 · ALTO · Modo manutenção derruba os admins e o health check

**Onde:** `api/middleware.py:15-22`; `fluxar-frontend/src/services/apiClient.ts:71-74`

```python
'/api/auth/token/refresh/',
is_admin_user = request.user.is_authenticated and request.user.is_staff
```

**Cenário:** o middleware roda antes da autenticação JWT, que só acontece dentro das views do DRF, então `request.user` é anônimo e `is_staff` nunca é verdadeiro para quem usa a SPA. A lista de exceções tem `/api/auth/token/refresh/`, mas a rota real é `/api/auth/refresh/`, e `/api/auth/me/` não está liberada: com a manutenção ligada, recarregar a página desloga até os administradores (ver FE-01), que só conseguem desligá-la chamando a API diretamente. O `/api/health/` também passa a responder 503, e o health check do Render falha.

**Correção sugerida:** liberar `/api/health/`, `/api/auth/refresh/` e `/api/auth/me/`; fazer a checagem numa permission ou no `initial()` das views do DRF, onde o usuário do JWT já está resolvido; guardar o valor da configuração em cache.

#### OPS-05 · MÉDIO · E-mails enviados em threads soltas

**Onde:** `api/views.py:54-59` (cadastro) e `:140-145` (redefinição). A thread vive dentro do worker do Gunicorn; se ele for reciclado ou morto (deploy, reinício do Render ou o timeout de outra requisição), o e-mail se perde. Não há nova tentativa nem endpoint de "reenviar verificação"; o usuário continua inativo e o `cleanup_inactive_users` (`api/management/commands/cleanup_inactive_users.py:16`) o apaga depois de 7 dias. O `EMAIL_TIMEOUT` foi adicionado no commit `31f09c1` e removido no `747716b`, então o fallback SMTP não tem timeout. Sem `LOGGING` configurado, as mensagens `logger.info` de sucesso não aparecem e a entrega não pode ser confirmada pelos logs. **Correção:** fila de tarefas com nova tentativa (ou, no mínimo, `EMAIL_TIMEOUT` e um endpoint de reenvio) e configuração de `LOGGING`.

#### OPS-06 · MÉDIO · Ambiente local diferente da produção

**Onde:** `requirements.txt` e o venv local. O venv roda Django 6.0.0 e DRF 3.16.1, enquanto o `requirements.txt` instala Django 5.1 e DRF 3.14 em produção; 15 migrações foram geradas pelo Django 6.0 e 11 pelo 5.1.15. Código testado localmente roda em outra versão no deploy. **Correção:** recriar o venv a partir do `requirements.txt`, com versões fixas, e usar a mesma imagem no desenvolvimento e na produção.

#### Itens de severidade BAIXO

| ID | Problema | Onde |
|---|---|---|
| OPS-07 | Arquivos versionados que não deveriam estar no repositório: a página de debug `last_error.html` (sem segredos expostos), o `debug_serializer.py` (SEG-15), duas cópias antigas da lógica de faturas em `scratch/` (sem asserts; uma quebra no dia 31) e 10 imagens de upload em `media/`, que não está no `.gitignore`. O `.dockerignore` não exclui nenhum deles, então todos vão para a imagem. A pasta vazia `fluxar-frontend/fluxar-frontend/` não é versionada e pode ser apagada | `last_error.html`, `debug_serializer.py`, `scratch/`, `media/`, `.gitignore`, `.dockerignore` |
| OPS-08 | O Docker do frontend serve só para desenvolvimento: roda `next dev` como root, usa `npm install` em vez de `npm ci` e tem um único estágio; `${PWD}:/app` não funciona no cmd nem no PowerShell | `fluxar-frontend/Dockerfile:11` e `:21`, `fluxar-frontend/docker-compose.yml:10` |

---

## 8. Manutenibilidade

#### MAN-01 · MÉDIO · Arquivos e funções muito grandes

- Backend: `reports/services.py` (1.296 linhas; `get_advanced_charts` sozinha tem 551, entre as linhas 437 e 987), `data_exchange/services.py` (549; `process_spreadsheet` tem 307, com quatro closures aninhadas), `api/views.py` (687, misturando autenticação, admin e sistema), `api/utils/email_service.py` (352) e `transactions/serializers.py` (279, com a geração de recorrências dentro do `create()`).
- Frontend, em linhas: `relatorios/page.tsx` 1.082, `transacoes/page.tsx` 1.015, `admin/usuarios/[id]/page.tsx` 869, `transaction-form-dialog.tsx` 847, `admin/usuarios/page.tsx` 836, `tags/page.tsx` 776, `transfer-form-dialog.tsx` 638, `invoice-payment-dialog.tsx` 629, `metas/page.tsx` 627 e `categorias/page.tsx` 618.

#### MAN-02 · MÉDIO · Regras de negócio duplicadas

- O sinal de entrada ou saída de cada tipo existe em 3 lugares: `transactions/signals.py:141-146`, `accounts/services.py:21-33` e `transactions/serializers.py:108`.
- A matemática de datas de fatura existe em 3 lugares, cada um tratando o fim de mês de um jeito: `accounts/services.py:83-86` (dia 28 fixo), `accounts/services.py:110-113` (correto num ramo, quebra no outro) e `transactions/services.py:144-163` (`calendar.monthrange`), além de 2 cópias em `scratch/`.
- O limite disponível tem duas fórmulas (FIN-27) e o cálculo de intervalos de mês se repete 4 vezes em `reports/services.py` (`:49-58`, `:219-231`, `:521-525` e `:998-1013`).
- `type__in=['EXPENSE','CREDIT_CARD']` aparece 18 vezes; `INVOICE_PAYMENT` não é mais criado (`accounts/services.py:122`), mas é referenciado 26 vezes.
- Os filtros de exportação em PDF e XLSX são copiados (`data_exchange/views.py:110-146` e `:157-193`) e diferem dos da lista (`transactions/views.py:67-116`).
- Os limites de plano estão em dois lugares (`core/services/plan_limits.py:6-22` e `transactions/services.py:180-185`), assim como a permission de premium (`core/permissions.py:20-28` e `reports/permissions.py:4-13`).
- Há dois `CustomTokenObtainPairSerializer` (`api/serializers.py:127` e `api/serializers_auth.py:5`) atrás de duas rotas de login.
- As categorias padrão estão fixas num signal (`transactions/signals.py:8-74`), enquanto o comando `populate_templates` e `clone_templates_to_user` (`transactions/services.py:218`) nunca são chamados.
- No frontend: 18 cópias locais de `formatCurrency` (existe uma em `fluxar-frontend/src/lib/utils.ts:27`), 33 `new Intl.NumberFormat`, o achatamento da árvore de categorias copiado em 5 arquivos e `/accounts/` buscado a partir de 12 lugares; 26 arquivos de interface chamam o `api` diretamente e 25 usam os módulos de serviço.

#### MAN-03 · BAIXO · Código morto e estrutura vazia

- `imports/` e `auth/` são diretórios vazios, nem versionados nem instalados; `api/repositories`, `api/services` e `api/tests` têm apenas `.gitkeep`.
- O status `CLOSED` de fatura nunca é atribuído; `end_date`, `last_processed` e `is_active` da recorrência nunca são usados; o filtro de `transactions/views.py:99` e `:101` lista tipos que não existem (`CREDIT_CARD_EXPENSE` e `TRANSFER`); `IsOwner` e `IsAuthenticatedOrPublic` não são usados; `send_welcome_email` (`api/utils/email.py:7`) nunca é importado.
- No frontend: `adjustBrightness` em `fluxar-frontend/src/components/cards/credit-card-item.tsx:37-53` não é usado (e tem um bug com `& 0x00`), `ui/toaster.tsx` nunca é montado e a página "Recorrentes" não tem link.

#### MAN-04 · BAIXO · Tipagem, modelagem e higiene

- Backend: a variável local `transaction` esconde o módulo `django.db.transaction` (`transactions/serializers.py:149`) e parâmetros chamados `date` escondem `datetime.date` (`accounts/services.py:118` e `transactions/services.py:14`, `:32`, `:51` e `:75`); há `print` de debug espalhados e nenhum `LOGGING` configurado.
- Modelagem: `Goal` usa ID numérico enquanto todos os outros modelos usam UUID, e não há `CheckConstraint` no banco (valor positivo, mês de 1 a 12, dia de 1 a 31).
- Frontend: 131 usos de `any`, valores monetários tipados como `number` embora o DRF envie strings decimais, e 4 `@ts-ignore`.

---

## 9. Pontos positivos

- Todos os campos monetários do banco são `DecimalField(15,2)`; não há `FloatField`.
- As leituras são filtradas pelo usuário logado via `UserQuerySetMixin`, e as chaves primárias são UUID.
- `plan` e `role` são somente leitura no perfil, então o usuário não consegue se promover pelo `PUT /users/me/`.
- Os tokens de verificação e de redefinição de senha expiram e são de uso único, e o "esqueci a senha" não revela se o e-mail existe.
- `DEBUG` vem desligado por padrão, e nenhum arquivo `.env` entrou no histórico dos repositórios.
- No frontend, o `AuthGuard` não renderiza conteúdo protegido antes do redirecionamento, a fila de renovação de token trata corretamente 401 concorrentes e não há `dangerouslySetInnerHTML`, `eval` nem segredos no código.
- O `tsc --noEmit` em modo strict passa sem nenhum erro.

---

## 10. Plano de ação sugerido

| Fase | Objetivo | Itens |
|---|---|---|
| 1. Imediato | Fechar falhas de segurança e fluxos quebrados com correções pequenas | CON-01, SEG-01, SEG-02, SEG-03, SEG-04, FIN-05 |
| 2. Saldo confiável | Ter uma única fonte de verdade para saldos e faturas | FIN-01 a FIN-04, FIN-06 a FIN-10, FIN-29 |
| 3. Rede de proteção | Detectar regressões automaticamente | OPS-02, OPS-01 (começando pelos itens da fase 2), OPS-06 |
| 4. Contratos e experiência | Corrigir o que o usuário vê errado | CON-02 a CON-06, FE-01 a FE-03, OPS-04, FIN-11, FIN-12 |
| 5. Escala | Aguentar mais usuários e arquivos maiores | PERF-01, PERF-04, OPS-03, OPS-05 |
| 6. Contínuo | Reduzir a dívida técnica | SEG-05 a SEG-09, MAN-01 a MAN-04 e os demais itens MÉDIO e BAIXO |

---

## Apêndice A — Resultados de ferramentas

### `npm audit --omit=dev` (frontend, 23/09/2026)

| Pacote | Severidade | Faixa vulnerável | Alertas |
|---|---|---|---|
| `next` | crítica | até 16.3.2 | 33, incluindo execução remota de código no Image Optimization com AVIF e em servidores Windows |
| `axios` | alta | 1.0.0 a 1.17.0 | 29 |
| `postcss` (dependência do `next`) | alta | até 8.5.22 | 4 |
| `sharp` | alta | até 0.35.4-rc.0 | 2 |
| `form-data` | alta | 4.0.0 a 4.0.5 | 1 |
| `nanoid` | alta | até 3.3.17 | 3 |
| `follow-redirects` | moderada | até 1.15.11 | 1 |

Total: 7 vulnerabilidades (1 crítica, 5 altas e 1 moderada). O `npm audit fix --force` sugere `next@16.3.6`.

### TypeScript (frontend)

`npx tsc --noEmit -p . --incremental false`: 0 erros.

### ESLint (frontend)

`npm run lint`: 415 problemas, sendo 168 erros e 247 avisos.

| Regra | Quantidade | Nível |
|---|---|---|
| `@typescript-eslint/no-unused-vars` | 222 | aviso |
| `@typescript-eslint/no-explicit-any` | 132 | erro |
| `react-hooks/exhaustive-deps` | 23 | aviso |
| `react/no-unescaped-entities` | 18 | erro |
| `prefer-const` | 4 | erro |
| `no-var` | 4 | erro |
| `@typescript-eslint/ban-ts-comment` | 4 | erro |
| `react-hooks/set-state-in-effect` | 3 | erro |
| `@typescript-eslint/no-empty-object-type` | 2 | erro |
| `react-hooks/immutability` | 1 | erro |
| `@typescript-eslint/no-unused-expressions` | 1 | aviso |
| `@next/next/no-img-element` | 1 | aviso |

## Apêndice B — Histórico e segredos

- Nenhum arquivo `.env` foi versionado em nenhum dos dois repositórios, e não há strings com formato de segredo no histórico do frontend.
- A única chave real encontrada no histórico do backend é a `SECRET_KEY` gerada pelo `startproject`, presente em `core/settings.py` entre os commits `be6e077` (14/12/2025) e `4e9dce2` (16/12/2025). O `docker-compose.yml` teve, no commit `c716938`, uma chave de desenvolvimento diferente dessa.
- O `last_error.html` versionado mostra `SECRET_KEY` e `EMAIL_HOST_PASSWORD` mascarados e `DATABASE_URL` vazio.
