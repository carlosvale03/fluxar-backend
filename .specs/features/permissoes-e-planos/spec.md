# Permissoes e planos Specification

## Problem Statement

Quem é administrador e o que cada plano libera estão definidos em lugares diferentes e contraditórios. O frontend decide quem é admin pelo campo `role` e o backend pelo `is_staff`, e o painel só edita o `role`: rebaixar um admin esconde a interface, mas mantém o acesso à API (SEG-06). A liberação do premium para a fase de testes está espalhada em cerca de oito pontos, e o frontend tem limites próprios de contas e cartões que divergem do backend (SEG-08). Nada disso pode ser ajustado sem mudar código.

Origem: `docs/auditoria-2026-09.md`, seção 3 (SEG-06 e SEG-08).

## Goals

- [ ] Um único campo define quem é administrador, e a interface e a API concordam sobre isso.
- [ ] O que cada plano libera é configurado pelo administrador no painel, sem mudar código.
- [ ] A liberação do premium para testes liga e desliga num único ponto, e desligá-la faz valer só as travas configuradas.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Gateway de pagamento, cobrança, preços e troca de plano pelo próprio usuário | Pedido do usuário |
| Definir agora o que cada plano libera | Decisão do usuário: o administrador configura as travas no painel |
| Papéis intermediários (suporte, financeiro) e permissões por função dentro do painel | Não foi pedido |
| Robustez e dados das telas do painel admin, como o usuário falso exibido quando a API falha (SEG-07) e os logs vazios (CON-10) | Fica numa feature do painel admin |
| Isolamento de dados entre usuários, autenticação e sessão | Features `isolamento-entre-usuarios`, `autenticacao` e `sessao` |

---

## Catálogo de travas

Cada trava tem uma chave. Um recurso é ligado ou desligado por plano; um limite recebe, por plano, um número inteiro maior ou igual a zero ou a opção "sem limite".

| Chave | Tipo | Telas e funcionalidades | Rotas do backend |
| ----- | ---- | ----------------------- | ---------------- |
| `relatorios_avancados` | Recurso | Aba "Avançados" da tela Relatórios | `GET /api/reports/charts/advanced/` |
| `comparacao_mensal` | Recurso | Gráfico de comparação mensal no dashboard e nos relatórios | `GET /api/reports/charts/monthly-comparison/` |
| `analise_por_tag` | Recurso | Análise e distribuição por tag nos relatórios | `GET /api/reports/charts/tag-insights/` e `GET /api/reports/charts/tag-distribution/` |
| `monitor_de_foco` | Recurso | Monitor de foco nos relatórios | `/api/focused-monitors/` |
| `calendario` | Recurso | Tela Calendário | `GET /api/reports/calendar/` |
| `orcamentos` | Recurso | Tela Orçamentos, inclusive a importação de orçamentos de outro mês | `/api/budgets/` e `POST /api/budgets/bulk_import/` |
| `metas` | Recurso | Tela Metas: metas, aportes, resgates, histórico e cofrinho de arredondamento | `/api/goals/`, `/api/goals/{id}/deposit/`, `/withdraw/` e `/history/` |
| `cartoes` | Recurso | Telas Cartões e detalhe do cartão, e compras no cartão; pagar e estornar faturas existentes continua liberado (PERM-22) | `/api/credit-cards/`, `GET /api/invoices/` e `POST /api/transactions/credit-card-expense/` |
| `compras_parceladas` | Recurso | Parcelamento acima de 1x na compra no cartão | `POST /api/transactions/credit-card-expense/` com `installments` maior que 1 |
| `transacoes_recorrentes` | Recurso | Opção "recorrente" ao lançar, e edição e exclusão de séries inteiras | `POST /api/transactions/` com `is_recurring`, `PATCH /api/transactions/bulk-update/` e `DELETE /api/transactions/bulk-delete/` por série |
| `tags` | Recurso | Tela Tags e campo de tags nos lançamentos | `/api/tags/` e o campo `tags` das transações |
| `importacao_ofx` | Recurso | Importação de OFX | `POST /api/import/ofx/` |
| `importacao_planilha` | Recurso | Importação de CSV e XLSX, inclusive de transferências | `POST /api/import/spreadsheet/` e `POST /api/import/spreadsheet/preflight/` |
| `exportacao_pdf` | Recurso | Exportação de transações em PDF | `GET /api/export/transactions/pdf/` |
| `exportacao_xlsx` | Recurso | Exportação de transações em XLSX | `GET /api/export/transactions/xls/` |
| `personalizar_dashboard` | Recurso | Personalização do layout do dashboard | Só na interface, porque o layout fica no navegador |
| `gestao_do_salario` | Recurso | Tela Gestão do salário: plano de divisão, simulação, divisão, desfazer e o aviso ao lançar o salário (spec `gestao-do-salario`) | As rotas da gestão do salário |
| `vinculos` | Recurso | Criar e trocar vínculos entre transações, filtro de vinculadas e relatório de gastos puxados; desfazer vínculos continua liberado (spec `vinculo-entre-transacoes`) | As rotas de vínculo, o filtro de vínculo das transações e o relatório de gastos puxados |
| `limite_contas` | Limite | Contas ativas, sem contar os cofrinhos criados por metas | `POST /api/accounts/` |
| `limite_cartoes` | Limite | Cartões ativos | `POST /api/credit-cards/` |
| `limite_categorias` | Limite | Categorias principais ativas | `POST /api/categories/` sem `parent` |
| `limite_subcategorias` | Limite | Subcategorias ativas de uma mesma categoria | `POST /api/categories/` com `parent` |
| `limite_tags` | Limite | Tags | `POST /api/tags/` |
| `limite_metas` | Limite | Metas ativas | `POST /api/goals/` |

## Recursos essenciais

Ficam liberados em todos os planos e não têm trava:

- Cadastro, verificação de e-mail, login, sessão e redefinição de senha.
- Perfil, configurações e preferências.
- Dashboard: resumo, saldos e gráficos simples (`/api/reports/dashboard/` e `/api/reports/charts/simple/`), inclusive a divisão das despesas por classe (CLASSE-28).
- Contas: listar, criar dentro do limite, editar, ajustar saldo e excluir.
- Transações avulsas: listar, filtrar, criar, editar, efetivar e excluir, inclusive as ocorrências já criadas de uma série.
- Transferências entre contas.
- Categorias: listar, usar e criar dentro do limite, inclusive as classes de despesa e a classe de cada categoria (CLASSE-13).
- Pagamento e estorno de faturas existentes e movimentação das contas-cofrinho das metas (PERM-22).
- Download dos dados financeiros em XLSX dentro do fluxo de exclusão da conta (LGPD-02).
- Página de planos.

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Campo que define quem é administrador | O papel `role = ADMIN`; `is_staff` serve só para o admin do Django | Decisão do usuário (AD-016). É o que a interface, o token e a proteção do último admin já usam | sim |
| O que cada plano libera | Não fica no código: o administrador configura as travas no painel | Decisão do usuário (AD-017) | sim |
| Catálogo de travas | Os 18 recursos e 6 limites da seção Catálogo de travas | Cobre as telas e funcionalidades que existem hoje, inclusive as que o código já tentava travar | sim |
| Recursos essenciais | Os da seção Recursos essenciais, sempre liberados | Sem eles o usuário não consegue usar o app nem mexer no próprio dinheiro | sim |
| Configuração inicial | Liberação para testes ligada, e todas as travas liberadas e sem limite nos três planos | Mantém o comportamento atual até o administrador configurar as travas | sim |
| Onde fica a liberação para testes | Uma chave no painel admin, junto do modo manutenção | Muda sem novo deploy, num único ponto | sim |
| Recurso bloqueado na interface | Aparece com o aviso do plano e um link para a página de planos, sem chamar a rota | É o padrão que as telas de metas e de importação já usam | sim |
| Resposta da API para uma trava | HTTP 403 com o código `plan_locked` ou `plan_limit_reached` e a chave da trava | A interface distingue a trava de outros erros; hoje o limite volta como 400 genérico | sim |
| Descida de plano ou trava fechada | Nada é apagado; o recurso travado fica bloqueado e o limite só impede criar itens novos | O usuário não perde dados ao mudar de plano nem quando a fase de testes termina | sim |
| Dinheiro em recursos travados | Contas-cofrinho continuam movimentáveis como contas comuns, e faturas existentes continuam podendo ser pagas e estornadas | O usuário nunca fica sem acesso ao próprio dinheiro nem sem poder quitar uma dívida | sim |
| Plano do administrador | O administrador tem todos os recursos, sem limites | Ele precisa ver e testar todas as telas | sim |
| Estado usado nas permissões | O papel e o plano atuais no banco, não os gravados no token | Uma mudança vale na próxima requisição, e não só quando o token vence | sim |
| Admin do Django (`/admin/`) | Só para quem tem `is_staff`, definido por linha de comando | É acesso direto ao banco e não deve vir junto com o papel do app | sim |
| Comando de criação do primeiro admin | Só cria quando não há nenhum admin ativo e não repromove ninguém | Hoje ele desfaz rebaixamentos a cada boot (SEG-06) | sim |
| Contas em que `role` e `is_staff` divergem hoje | São listadas na implantação, sem mudança automática | O administrador decide caso a caso | sim |
| Página de planos | Mostra o que cada plano libera e os limites, sem compra | O pagamento está fora do escopo | sim |
| Tempo para uma mudança de trava valer | Até 30 segundos | É o mesmo padrão do modo manutenção (SESSAO-24) | sim |
| Cofrinho criado por uma meta | Não conta no limite de contas | Senão criar uma meta poderia travar a criação de contas do usuário | sim |

**Open questions:** none. As suposições da tabela foram aprovadas pelo usuário em 2026-09-26.

---

## User Stories

### P1: Quem é administrador ⭐ MVP

**User Story**: Como administrador, quero que promover ou rebaixar alguém no painel valha igual na interface e na API.

**Why P1**: hoje rebaixar um admin esconde o painel, mas mantém o acesso às rotas de administração (SEG-06).

**Acceptance Criteria**:
1. **PERM-01** WHILE um usuário tiver o papel `ADMIN`, o sistema SHALL tratá-lo como administrador no backend e na interface.
2. **PERM-02** IF quem não tem o papel `ADMIN` tentar uma função de administração (listar e buscar usuários; ver detalhes, estatísticas financeiras e logs de um usuário; mudar plano, papel ou status; arquivar, excluir definitivamente ou limpar dados; redefinir a senha de outro usuário; ver estatísticas e logs globais; ligar ou desligar a manutenção; configurar as travas e a liberação para testes) THEN o sistema SHALL responder HTTP 403, mesmo que o usuário tenha `is_staff`.
3. **PERM-03** WHILE um usuário não for administrador, a interface SHALL esconder os links do painel admin e, se ele abrir uma página do painel, levá-lo ao dashboard sem mostrar o conteúdo.
4. **PERM-04** WHEN o papel ou o plano de um usuário muda THEN o sistema SHALL aplicar a mudança a partir da próxima requisição, pelo valor atual no banco e não pelo gravado no token.
5. **PERM-05** IF uma mudança de papel, um arquivamento ou uma exclusão deixar o sistema sem nenhum administrador ativo THEN o sistema SHALL recusá-la com HTTP 400 e a mensagem "O sistema precisa ter pelo menos um administrador ativo."
6. **PERM-06** IF um administrador tentar tirar o próprio papel, arquivar ou excluir a própria conta pelo painel THEN o sistema SHALL recusar a operação com HTTP 400.
7. **PERM-07** WHEN o comando de criação do primeiro administrador é executado THEN o sistema SHALL criar o administrador só se não houver nenhum ativo, sem alterar o papel de contas existentes.
8. **PERM-08** IF alguém sem `is_staff` tentar entrar no admin do Django (`/admin/`) THEN o sistema SHALL recusar o acesso, mesmo que tenha o papel `ADMIN`.
9. **PERM-09** WHILE um usuário for administrador, o sistema SHALL liberar para ele todos os recursos do catálogo e ignorar os limites, qualquer que seja o plano.

**Independent Test**: um usuário com `is_staff` e sem o papel `ADMIN` recebe 403 em `/api/admin/users/`; promovido a `ADMIN` pelo painel, passa a acessar o painel e a API na requisição seguinte; rebaixado, perde os dois na requisição seguinte; tentar rebaixar o último admin recebe 400.

---

### P1: Configuração das travas pelo administrador ⭐ MVP

**User Story**: Como administrador, quero definir no painel o que cada plano libera, sem depender de uma mudança de código.

**Why P1**: hoje os planos estão escritos em cerca de oito pontos do código, com valores que divergem entre frontend e backend (SEG-08).

**Acceptance Criteria**:
1. **PERM-10** WHEN o administrador abre a configuração dos planos no painel THEN o sistema SHALL mostrar cada trava da seção Catálogo de travas, com o valor atual para Comum, Premium e Premium Plus.
2. **PERM-11** WHEN o administrador liga ou desliga um recurso para um plano, ou muda um limite, THEN o sistema SHALL gravar a mudança e aplicá-la a todos os usuários daquele plano em até 30 segundos.
3. **PERM-12** IF um limite receber um valor que não seja um inteiro maior ou igual a zero nem a opção "sem limite" THEN o sistema SHALL recusá-lo com HTTP 400.
4. **PERM-13** WHEN uma trava ou a liberação para testes muda de valor THEN o sistema SHALL registrar no log do sistema quem mudou, quando, qual trava, em qual plano e os valores antigo e novo.
5. **PERM-14** WHILE um recurso for essencial (seção Recursos essenciais), o sistema SHALL mantê-lo liberado em todos os planos, sem trava configurável.

**Independent Test**: o administrador desliga `exportacao_pdf` para o Comum e define `limite_contas` como 2 no Comum; em até 30 segundos, um usuário Comum passa a ver a exportação em PDF travada e não consegue criar a terceira conta; o log mostra as duas mudanças com os valores antigo e novo.

---

### P1: Travas aplicadas em cada tela e rota ⭐ MVP

**User Story**: Como usuário, quero ver com clareza o que o meu plano libera, e o sistema precisa barrar de fato o que não libera, na tela e na API.

**Why P1**: hoje as travas estão só na interface, ou só no backend, ou em nenhum dos dois, e cada tela decide por conta própria.

**Acceptance Criteria**:
1. **PERM-15** IF um usuário chamar uma rota de um recurso bloqueado para o plano dele THEN o sistema SHALL recusá-la com HTTP 403, o código `plan_locked` e a chave da trava.
2. **PERM-16** IF um usuário tentar criar um item além do limite do plano dele THEN o sistema SHALL recusá-lo com HTTP 403, o código `plan_limit_reached`, a chave da trava e o limite.
3. **PERM-17** WHEN o usuário abre o app THEN o sistema SHALL informar no `/auth/me` o plano real do usuário, os recursos liberados para ele e, para cada limite, o valor e o uso atual.
4. **PERM-18** WHEN a interface decide se mostra um recurso ou deixa criar um item THEN o sistema SHALL usar só o que o `/auth/me` informou, sem plano nem limite escritos no código do frontend.
5. **PERM-19** WHILE um recurso estiver bloqueado para o usuário, a interface SHALL mostrar a tela ou o controle dele com o aviso de que o recurso depende do plano e um link para a página de planos, sem chamar a rota bloqueada.
6. **PERM-20** WHILE um limite estiver atingido, a interface SHALL mostrar o uso e o limite, desabilitar a criação de itens novos e oferecer o link para a página de planos.
7. **PERM-21** WHEN o plano de um usuário desce, uma trava é fechada ou a liberação para testes é desligada THEN o sistema SHALL manter todos os dados do usuário, bloquear só o uso dos recursos travados e impedir só a criação de itens além do limite.
8. **PERM-22** WHILE um recurso travado envolver dinheiro já lançado, o sistema SHALL continuar permitindo movimentar as contas-cofrinho das metas como contas comuns e pagar e estornar as faturas existentes.

**Independent Test**: com `metas` desligado para o Comum, um usuário Comum vê a tela Metas travada com o link para os planos, recebe 403 `plan_locked` ao chamar `/api/goals/`, e ainda consegue transferir o dinheiro do cofrinho para outra conta; com 5 contas e `limite_contas` igual a 2, ele mantém as 5 e recebe 403 `plan_limit_reached` ao criar a sexta.

---

### P1: Liberação para testes ⭐ MVP

**User Story**: Como administrador, quero liberar todos os recursos para todo mundo durante os testes com um único controle, e desligá-lo sem caçar desvios no código.

**Why P1**: hoje a liberação está espalhada em cerca de oito pontos, e desligar um deles não trava o premium de fato (SEG-08).

**Acceptance Criteria**:
1. **PERM-23** WHILE a liberação para testes estiver ligada, o sistema SHALL liberar a todos os usuários todos os recursos do catálogo e ignorar os limites, sem mudar o plano gravado de ninguém.
2. **PERM-24** WHEN o administrador liga ou desliga a liberação para testes no painel THEN o sistema SHALL aplicar a mudança a todos os usuários em até 30 segundos.
3. **PERM-25** WHILE a liberação para testes estiver ligada, a interface SHALL mostrar no perfil o plano real do usuário e o aviso "Todos os recursos estão liberados durante a fase de testes."
4. **PERM-26** WHEN a liberação para testes está desligada THEN o sistema SHALL aplicar só as travas configuradas, em todas as telas e rotas do catálogo, sem nenhum outro desvio.

**Independent Test**: com a liberação ligada, um usuário Comum usa todas as telas do catálogo e o perfil dele mostra "Plano Comum" com o aviso; ao desligar, em até 30 segundos cada trava configurada passa a valer, tela por tela e rota por rota.

---

### P2: Página de planos

**User Story**: Como usuário, quero saber o que cada plano libera antes de pensar em mudar de plano.

**Why P2**: hoje o botão "Seja Premium Agora" leva ao perfil, que não mostra nada sobre os planos.

**Acceptance Criteria**:
1. **PERM-27** WHEN o usuário abre a página de planos THEN o sistema SHALL mostrar os recursos e os limites de cada plano, a partir da configuração atual, e destacar o plano do usuário.

**Independent Test**: depois de o administrador mudar um limite, a página de planos mostra o valor novo em até 30 segundos, com o plano do usuário em destaque.

---

### P2: Implantação

**User Story**: Como responsável pelo Fluxar, quero que a mudança entre no ar sem travar ninguém de surpresa e sem mexer em admins sem revisão.

**Why P2**: a fase de testes ainda está em andamento, e hoje há usuários em que `role` e `is_staff` não batem.

**Acceptance Criteria**:
1. **PERM-28** WHEN a correção é implantada THEN o sistema SHALL começar com a liberação para testes ligada e com todas as travas liberadas e sem limite nos três planos.
2. **PERM-29** WHEN a correção é implantada THEN o sistema SHALL listar os usuários em que o papel e o `is_staff` divergem, sem alterar nenhum deles.

**Independent Test**: logo depois da implantação, nenhum usuário perde acesso a nenhuma tela, e a lista de divergências mostra quem tem `is_staff` sem o papel `ADMIN`, e o contrário.

---

## Edge Cases

- Meta que cria um cofrinho: o cofrinho não conta no limite de contas.
- Plano que desce com 5 contas para um limite de 2: as 5 continuam, e uma conta nova só pode ser criada quando houver menos de 2 ativas (PERM-16, PERM-21).
- Admin rebaixado: perde o painel na próxima requisição e passa a obedecer às travas do plano dele (PERM-04, PERM-09).
- Liberação desligada com o usuário numa tela que ficou travada: a próxima chamada recebe 403 `plan_locked`, e a tela mostra o aviso (PERM-15, PERM-19).
- Dois administradores mudam a mesma trava ao mesmo tempo: vale a última gravação, e as duas aparecem no log (PERM-13).
- Trava só de interface (`personalizar_dashboard`): vale só na interface, porque não existe rota no backend para ela.
- Série recorrente criada antes de `transacoes_recorrentes` ser travado: as ocorrências já criadas continuam sendo transações comuns, que podem ser editadas e efetivadas uma a uma.

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | PERM-12, PERM-16 |
| Falha e falha parcial | N/A because a configuração das travas fica no mesmo banco do app; sem banco, nenhuma rota funciona |
| Idempotência, repetição e duplicidade | N/A because gravar uma trava com o valor que ela já tem não muda nada e não gera log (PERM-13 só registra mudança de valor) |
| Autorização e rate limiting | PERM-01 a PERM-09, PERM-15, PERM-16 |
| Concorrência e ordem | PERM-13 (vale a última gravação, e as duas ficam no log) |
| Ciclo de vida dos dados | PERM-21, PERM-22, PERM-28, PERM-29 |
| Observabilidade | PERM-13 |
| Falha de dependência externa | N/A because as travas não dependem de nenhum serviço externo |
| Integridade das transições de estado | PERM-04 a PERM-06, PERM-11, PERM-23, PERM-24 |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PERM-01 | P1: Quem é administrador | T1 | Implemented |
| PERM-02 | P1: Quem é administrador | T1 | Implemented |
| PERM-03 | P1: Quem é administrador | - | Pending |
| PERM-04 | P1: Quem é administrador | T1 | Implemented |
| PERM-05 | P1: Quem é administrador | T2 | Implemented |
| PERM-06 | P1: Quem é administrador | T2 | Implemented |
| PERM-07 | P1: Quem é administrador | T3 | Implemented |
| PERM-08 | P1: Quem é administrador | T1 | Implemented |
| PERM-09 | P1: Quem é administrador | T4 | Implemented |
| PERM-10 | P1: Configuração das travas pelo administrador | T5 | In Progress |
| PERM-11 | P1: Configuração das travas pelo administrador | T5 | In Progress |
| PERM-12 | P1: Configuração das travas pelo administrador | T5 | In Progress |
| PERM-13 | P1: Configuração das travas pelo administrador | T5 | In Progress |
| PERM-14 | P1: Configuração das travas pelo administrador | T4 | Implemented |
| PERM-15 | P1: Travas aplicadas em cada tela e rota | T6 | Implemented |
| PERM-16 | P1: Travas aplicadas em cada tela e rota | - | Pending |
| PERM-17 | P1: Travas aplicadas em cada tela e rota | - | Pending |
| PERM-18 | P1: Travas aplicadas em cada tela e rota | - | Pending |
| PERM-19 | P1: Travas aplicadas em cada tela e rota | - | Pending |
| PERM-20 | P1: Travas aplicadas em cada tela e rota | - | Pending |
| PERM-21 | P1: Travas aplicadas em cada tela e rota | - | Pending |
| PERM-22 | P1: Travas aplicadas em cada tela e rota | T6 | In Progress |
| PERM-23 | P1: Liberação para testes | T4 | Implemented |
| PERM-24 | P1: Liberação para testes | T5 | In Progress |
| PERM-25 | P1: Liberação para testes | - | Pending |
| PERM-26 | P1: Liberação para testes | T6 | In Progress |
| PERM-27 | P2: Página de planos | - | Pending |
| PERM-28 | P2: Implantação | T4 | Implemented |
| PERM-29 | P2: Implantação | T3 | Implemented |

**Coverage:** 29 total, 0 mapped to tasks, 29 unmapped ⚠️ (design e tasks ainda não iniciados)

---

## Success Criteria

- [ ] Não existe nenhum plano, limite ou desvio de plano escrito no código do frontend ou do backend; tudo vem da configuração do painel.
- [ ] Para cada trava do catálogo, um teste confirma que a interface mostra o aviso e que a rota responde 403 quando a trava está fechada.
- [ ] Um usuário sem o papel `ADMIN` não consegue executar nenhuma função de administração, com ou sem `is_staff`.
