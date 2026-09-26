# STATE

## Decisions

### AD-001
- **Decision**: As specs usam em inglês os títulos de seção e os rótulos do template do tlc-spec-driven (`Problem Statement`, `Goals`, `Out of Scope`, `Assumptions & Open Questions`, `User Stories`, `Edge Cases`, `Requirement Traceability`, `Success Criteria`, `**User Story**`, `**Acceptance Criteria**:`, `**Independent Test**`, `**Open questions:**`). Todo o conteúdo fica em português, com as palavras-chave EARS em inglês.
- **Reason**: o `validate_spec.py` procura esses títulos e rótulos exatos. Traduzidos, a spec falha no gate ou os critérios de aceite deixam de ser verificados.
- **Trade-off**: a spec mistura títulos em inglês com texto em português.
- **Scope**: todas as specs em `.specs/features/`.
- **Date**: 2026-09-25
- **Status**: active

### AD-002
- **Decision**: Uma transação só altera o saldo quando está efetivada (`COMPLETED`), qualquer que seja a data dela. Toda ocorrência gerada por uma série recorrente nasce pendente, inclusive as receitas, e só passa a contar quando o usuário a efetiva.
- **Reason**: decisão do usuário. É como as despesas já funcionam, deixa com o usuário a confirmação do que realmente aconteceu e dispensa uma rotina agendada.
- **Trade-off**: o usuário precisa efetivar cada ocorrência; uma receita que já caiu, mas não foi efetivada, fica fora do saldo.
- **Scope**: saldo, faturas, importacao, relatorios e qualquer feature que crie transações.
- **Date**: 2026-09-25
- **Status**: active

### AD-003
- **Decision**: Uma conta só pode ser excluída com saldo zero e sem transações pendentes. A conta excluída não entra em nenhum total de saldo, não recebe movimentação nova e mantém as transações efetivadas no histórico, somente para leitura.
- **Reason**: decisão do usuário. Impede que dinheiro suma do patrimônio sem registro, como já acontece na exclusão de metas; as demais restrições mantêm em zero o saldo de uma conta que saiu dos totais.
- **Trade-off**: antes de excluir, o usuário precisa transferir ou ajustar o saldo restante e resolver as transações pendentes da conta.
- **Scope**: saldo, faturas (conta de pagamento do cartão), importacao, metas (cofrinhos), relatorios e painel admin.
- **Date**: 2026-09-25
- **Status**: active

### AD-004
- **Decision**: A feature `saldo` é a dona das regras de como qualquer operação altera o saldo de uma conta. As features `faturas`, `importacao` e `metas` definem quais transações criar, alterar ou excluir e seguem essas regras, sem regra de saldo própria.
- **Reason**: hoje cada caminho atualiza o saldo do seu jeito, e é daí que vêm as divergências da auditoria (FIN-02 a FIN-04 e FIN-10).
- **Trade-off**: qualquer mudança de saldo pedida por outra feature passa a depender desta spec.
- **Scope**: saldo, faturas, importacao e metas.
- **Date**: 2026-09-25
- **Status**: active

### AD-005
- **Decision**: O endpoint genérico de transações só cria `INCOME` e `EXPENSE`. `TRANSFER_IN` e `TRANSFER_OUT` nascem só da operação de transferência, `CREDIT_CARD` só da compra no cartão, e `INVOICE_PAYMENT` não é mais criado. Uma compra no cartão só é efetivada pelo pagamento da fatura.
- **Reason**: criados pelo endpoint genérico, esses tipos geram uma perna de transferência solta, uma compra que debita a conta sem passar pela fatura ou um pagamento que não paga nada (FIN-16, FIN-17 e CON-09).
- **Trade-off**: telas e integrações precisam usar a operação própria de cada tipo; o pagamento genérico que a tela de fatura usa como fallback deixa de funcionar.
- **Scope**: saldo, faturas, importacao, metas e o frontend.
- **Date**: 2026-09-25
- **Status**: active

### AD-006
- **Decision**: Quando uma regra usa um dia do mês que não existe naquele mês (29, 30 ou 31), vale o último dia do mês. O ajuste não se acumula: no mês seguinte volta o dia original.
- **Reason**: decisão do usuário. É o que os bancos fazem com fechamento e vencimento, e mantém cada data no próprio mês.
- **Trade-off**: em meses curtos o ciclo da fatura fica um ou dois dias menor.
- **Scope**: faturas (fechamento e vencimento) e qualquer regra mensal por dia, inclusive as séries recorrentes mensais.
- **Date**: 2026-09-25
- **Status**: active

### AD-007
- **Decision**: O pagamento de fatura é idempotente. Cada tentativa leva um identificador; a repetição com o mesmo identificador recebe a mesma resposta do primeiro processamento e não gera outro pagamento. Um pagamento com outro identificador, ou sem identificador, numa fatura já paga é recusado com HTTP 400.
- **Reason**: decisão do usuário. Um reenvio depois de timeout, comum no cold start do Render, não pode cobrar duas vezes nem mostrar um erro falso.
- **Trade-off**: o backend guarda o identificador de cada pagamento, e o frontend precisa gerar e reaproveitar o identificador da tentativa.
- **Scope**: faturas, saldo (SALDO-26) e o frontend.
- **Date**: 2026-09-25
- **Status**: active

### AD-008
- **Decision**: Toda regra que depende da data de hoje usa a data corrente no fuso de Brasília (`America/Sao_Paulo`).
- **Reason**: os usuários estão no Brasil e o servidor roda em UTC; depois das 21h o "hoje" do servidor já é o dia seguinte (FIN-34).
- **Trade-off**: um usuário em outro fuso vê a virada do dia no horário de Brasília.
- **Scope**: saldo (data do ajuste), faturas (fatura aberta ou fechada, próximo vencimento), relatorios e séries recorrentes.
- **Date**: 2026-09-25
- **Status**: active

### AD-009
- **Decision**: Um valor em texto no formato brasileiro é lido assim: com vírgula, a vírgula é o separador decimal e os pontos são de milhar; sem vírgula, os pontos são de milhar quando todos os grupos depois deles têm três dígitos e a parte antes do primeiro ponto não é zero, e decimal nos demais casos ("1.500" é 1500; "12.5" é 12,50; "0.50" é 0,50).
- **Reason**: é a leitura que um usuário brasileiro espera. A regra atual troca vírgula por ponto e lê "1.500" como 1,50 (FIN-22), e o mesmo erro aparece nos formulários de meta (FE-06).
- **Trade-off**: um valor escrito no formato americano com três casas decimais sem vírgula ("1.500" querendo dizer 1,5) é lido como milhar.
- **Scope**: importacao e qualquer campo que receba valor em texto, inclusive os formulários de metas.
- **Date**: 2026-09-25
- **Status**: active

### AD-010
- **Decision**: Toda relação gravável pela API só aceita objetos do usuário da requisição. Um ID de outro usuário no corpo da requisição recebe HTTP 400, com o erro no campo e a mesma mensagem de um ID inexistente; no endereço, recebe HTTP 404, também igual a um objeto inexistente.
- **Reason**: decisão do usuário. O 400 mantém o erro por campo nos formulários, e a resposta idêntica à de um ID inexistente não revela que o ID existe em outra conta.
- **Trade-off**: as views que hoje respondem 404 para um ID do corpo (aporte e resgate de meta, importação) mudam para 400.
- **Scope**: todas as features; qualquer relação nova precisa seguir esta regra.
- **Date**: 2026-09-26
- **Status**: active

### AD-011
- **Decision**: E-mails transacionais são enviados dentro da própria requisição, tentando os provedores em ordem (Resend e depois SMTP), com no máximo 10 segundos no total e sem thread em segundo plano. Todo texto vindo do usuário é escapado no HTML, e o endereço aparece mascarado nos logs.
- **Reason**: decisão do usuário: a falha no envio não bloqueia o cadastro, e o usuário pede o reenvio. Dispensa fila e rotina agendada, e acaba com os e-mails perdidos em threads soltas quando o worker reinicia (OPS-05).
- **Trade-off**: sem nova tentativa automática, um e-mail que falha depende de o usuário pedir o reenvio; a requisição pode levar até 10 segundos a mais quando os provedores estão lentos.
- **Scope**: autenticacao e qualquer e-mail transacional futuro.
- **Date**: 2026-09-26
- **Status**: active

### AD-012
- **Decision**: Em produção (`DEBUG` desligado), o backend não sobe sem a configuração obrigatória (`SECRET_KEY` e `FRONTEND_URL`), e a falta da lista de CORS não libera nenhuma origem. Nenhuma configuração de segurança tem valor padrão que falhe aberto.
- **Reason**: hoje a `SECRET_KEY` tem um fallback público, que permitiria forjar tokens de qualquer usuário, e o CORS libera todas as origens quando a variável falta (SEG-03).
- **Trade-off**: um deploy com variável faltando falha na hora, em vez de subir degradado.
- **Scope**: todas as features e qualquer configuração nova.
- **Date**: 2026-09-26
- **Status**: active

### AD-013
- **Decision**: O token de renovação fica num cookie httpOnly, Secure e SameSite, restrito às rotas de sessão, e o token de acesso fica só na memória da aba. Para o cookie funcionar em todos os navegadores, o frontend e a API passam a ficar no mesmo site, por domínio próprio compartilhado ou por proxy do Next.js.
- **Reason**: decisão do usuário. Um XSS ou uma dependência comprometida não consegue ler o token de renovação, como consegue hoje no `localStorage` (SEG-05).
- **Trade-off**: o deploy passa a exigir o mesmo site para frontend e API (hoje Vercel e Render são sites diferentes), a rota de renovação precisa de proteção contra pedidos de outras origens e cada recarga de página faz uma renovação.
- **Scope**: sessao, autenticacao (respostas de login e verificação), o frontend inteiro e a infraestrutura de deploy.
- **Date**: 2026-09-26
- **Status**: active

### AD-014
- **Decision**: Trocar a senha encerra todas as outras sessões do usuário e mantém a atual; redefinir a senha por link ou pelo administrador encerra todas. Os tokens de acesso dessas sessões são recusados já na próxima requisição, e o mesmo vale para uma conta desativada ou excluída.
- **Reason**: decisão do usuário. Quem troca a senha por suspeita de invasão precisa derrubar o invasor na hora.
- **Trade-off**: o backend confere a cada requisição se a sessão do token ainda vale.
- **Scope**: sessao, autenticacao (redefinição por link) e o painel admin (redefinição e desativação).
- **Date**: 2026-09-26
- **Status**: active

### AD-015
- **Decision**: Durante o modo manutenção, só administradores usam a API; os demais recebem 503 com o código `maintenance_mode`, sem perder a sessão. Login, renovação, `/auth/me`, logout e `/api/health/` continuam respondendo para todos.
- **Reason**: decisão do usuário. Hoje a manutenção desloga até os administradores, e o health check do Render passa a falhar (OPS-04).
- **Trade-off**: toda rota nova precisa respeitar a regra da manutenção, e a definição de administrador depende da feature do painel admin (SEG-06).
- **Scope**: sessao, painel admin e todas as rotas da API.
- **Date**: 2026-09-26
- **Status**: active

### AD-016
- **Decision**: O administrador do app é definido só pelo papel `role = ADMIN`, lido do banco a cada requisição. O `is_staff` deixa de dar acesso à API e serve apenas para o admin do Django, definido por linha de comando.
- **Reason**: decisão do usuário. O papel já é o que a interface, o token e a proteção do último admin usam; hoje o backend autoriza por `is_staff`, e rebaixar alguém no painel não tira o acesso à API (SEG-06).
- **Trade-off**: quem hoje tem `is_staff` sem o papel `ADMIN` perde o acesso às rotas de administração até receber o papel.
- **Scope**: permissoes-e-planos, sessao (quem acessa na manutenção), painel admin e qualquer rota de administração nova.
- **Date**: 2026-09-26
- **Status**: active

### AD-017
- **Decision**: O que cada plano libera é configurado pelo administrador no painel, não no código. Cada recurso ou limite que um plano pode travar tem uma chave num catálogo; o backend aplica a trava em cada rota, e o frontend só reflete o que o `/auth/me` informa. A liberação do premium para testes é uma única chave no painel.
- **Reason**: decisão do usuário. Hoje a liberação está espalhada em cerca de oito pontos, com limites diferentes no frontend e no backend (SEG-08).
- **Trade-off**: toda funcionalidade nova precisa entrar no catálogo de travas ou na lista de recursos essenciais, e cada rota do catálogo passa a consultar a configuração dos planos.
- **Scope**: todas as features com telas ou rotas para o usuário.
- **Date**: 2026-09-26
- **Status**: active

### AD-018
- **Decision**: A exclusão da conta pelo usuário desativa a conta na hora, encerra as sessões e dá 30 dias para desistir; no fim do prazo, uma rotina diária apaga tudo (dados pessoais, financeiros e imagens no Cloudinary) e guarda só um registro sem dados pessoais. Antes de confirmar, o usuário pode baixar os dados financeiros em XLSX, qualquer que seja o plano. A exclusão pelo administrador é imediata e faz a mesma limpeza.
- **Reason**: decisão do usuário. Atende o direito de exclusão da LGPD sem apagar por engano, e o usuário leva os próprios dados antes.
- **Trade-off**: exige uma rotina diária agendada no Render, e toda feature que guarde dados do usuário precisa entrar na lista do que a exclusão apaga.
- **Scope**: lgpd, autenticacao (login durante o prazo), sessao (fim das sessões), permissoes-e-planos (exportação essencial no fluxo de exclusão) e toda feature que guarde dados do usuário.
- **Date**: 2026-09-26
- **Status**: active

### AD-019
- **Decision**: Nenhum log ou registro de auditoria contém e-mail completo, nome, CPF, telefone, data de nascimento, renda, senha, token ou parte dele, conteúdo de requisição, nem descrição, valor ou nome de conta, cartão, categoria ou meta. Para identificar um usuário, vale o identificador interno ou o e-mail mascarado. Mensagens passam só pelo log com nível, nunca por `print`.
- **Reason**: hoje o e-mail inteiro aparece a cada login e em todo envio de e-mail, junto com pedaços de tokens e payloads (SEG-09), e os logs ficam guardados por terceiros.
- **Trade-off**: depurar um problema de um usuário específico exige cruzar o identificador interno com o banco.
- **Scope**: todo o backend e qualquer log novo.
- **Date**: 2026-09-26
- **Status**: active

### AD-020
- **Decision**: CPF, telefone, data de nascimento e renda mensal ficam criptografados no banco, com uma chave própria obrigatória em produção. O CPF deixa de ser único, e o painel admin mostra esses dados mascarados ou ocultos.
- **Reason**: são dados pessoais que o app só exibe e não usa para buscar nem somar; hoje ficam em texto puro, e a unicidade do CPF revela se ele está cadastrado (SEG-09).
- **Trade-off**: não dá para buscar nem ordenar por esses campos no banco, e perder a chave torna os dados ilegíveis.
- **Scope**: lgpd, painel admin e qualquer dado pessoal novo que não seja usado em buscas.
- **Date**: 2026-09-26
- **Status**: active

### AD-021
- **Decision**: Coleções pequenas (contas, cartões, faturas de um cartão, categorias, tags, orçamentos, metas e monitores de foco) vêm completas, sem paginação. Transações e as listas de usuários e de logs do admin vêm paginadas num formato único (`count`, `total_pages`, `current_page`, `next`, `previous` e `results`), com 20 itens por padrão e no máximo 100.
- **Reason**: decisão do usuário. Hoje oito rotas cortam no 10º item, e a interface lê só a primeira página (CON-02).
- **Trade-off**: uma coleção pequena que cresça muito vem inteira numa única resposta.
- **Scope**: todas as rotas de lista e todas as telas que as consomem.
- **Date**: 2026-09-26
- **Status**: active

### AD-022
- **Decision**: Filtros com vários valores repetem o parâmetro (`categoryId=a&categoryId=b`), e escolher uma categoria-pai inclui as subcategorias. A lista, a exportação e os relatórios aceitam os mesmos filtros com o mesmo significado, e uma rota que recebe um filtro desconhecido responde 400.
- **Reason**: decisão do usuário. Hoje o filtro aplica só a última categoria (CON-05), a exportação entende "despesas" de outro jeito (FIN-25) e filtros desconhecidos são ignorados em silêncio (CON-07, CON-12).
- **Trade-off**: toda tela que envia um parâmetro fora do contrato passa a receber erro, em vez de um resultado ignorado.
- **Scope**: transações, exportações, relatórios e qualquer rota de lista com filtro.
- **Date**: 2026-09-26
- **Status**: active

### AD-023
- **Decision**: Valores em dinheiro trafegam como texto decimal com duas casas e ponto ("1234.56") em todas as rotas, inclusive nos relatórios, e o frontend não faz conta em ponto flutuante nem tem formatação de moeda própria em cada tela. Datas sem hora trafegam como `AAAA-MM-DD` e são tratadas como datas de calendário, sem fuso; datas com hora usam ISO 8601 com o fuso.
- **Reason**: hoje os relatórios enviam números de ponto flutuante, o frontend soma e subtrai valores em ponto flutuante e datas sem hora perdem um dia no fuso de Brasília (FE-03, CON-06, CON-11, FIN-44).
- **Trade-off**: gráficos e contas do frontend precisam converter o texto decimal antes de usar os valores.
- **Scope**: todas as rotas e telas que mostram ou recebem valores e datas.
- **Date**: 2026-09-26
- **Status**: active

### AD-024
- **Decision**: A API mantém o formato de erro do DRF (erros de validação por campo; `detail` com `code` nos demais), com todas as mensagens em português. A interface trata os erros num único lugar: erro de campo aparece no campo, os demais num aviso do Sonner, que é o único sistema de avisos, e toda requisição tem tempo máximo.
- **Reason**: hoje as mensagens padrão saem em inglês, nove telas usam um sistema de avisos que nunca aparece (FE-02) e erros de campo são descartados (FE-08).
- **Trade-off**: códigos de erro próprios de outras specs (`plan_locked`, `deletion_pending`, `email_not_verified`) continuam dentro do formato do DRF, e a interface precisa conhecer cada um.
- **Scope**: todas as rotas e todas as telas.
- **Date**: 2026-09-26
- **Status**: active

### AD-025
- **Decision**: As categorias de despesa têm classe. Cada usuário tem as classes Essencial e Dispensável, que não podem ser excluídas nem renomeadas, e pode criar outras até o total de 5. A classe é um campo da categoria: a subcategoria sem classe própria herda a da mãe, categorias de receita não têm classe, e relatórios e filtros usam a classe efetiva atual, inclusive nos meses passados.
- **Reason**: decisão do usuário. Mostra quanto das despesas vai para o necessário e quanto vai para o que dá para cortar, e é a base das sugestões da gestão do salário (PROP-01).
- **Trade-off**: mudar a classe de uma categoria muda também os relatórios dos meses passados, e o orçamento continua só por categoria.
- **Scope**: classes-de-despesa, relatorios, filtros da lista de transações, exportação, importação e a gestão do salário.
- **Date**: 2026-09-26
- **Status**: active

### AD-026
- **Decision**: A divisão do salário cria, num lote único e já efetivadas, as transferências da conta do salário para as contas do plano e os aportes nas metas do plano. O lote é tudo ou nada, idempotente pelo identificador da tentativa, e marca cada transação com o identificador da divisão. Ele pode ser desfeito inteiro em até 7 dias, se nenhuma transação dele mudou, devolvendo saldos e valores das metas. O aporte gerado entra só na meta escolhida, sem o rateio automático do cofrinho compartilhado.
- **Reason**: decisão do usuário: um clique para gerar, com confirmação forte e desfazer. O rateio automático desviaria o aporte da meta escolhida (PROP-01).
- **Trade-off**: as transações nascem efetivadas e dependem de o usuário ter feito as transferências no banco; depois de 7 dias ou de uma edição, corrigir a divisão exige remover as transações à mão.
- **Scope**: gestao-do-salario, saldo (regras de saldo das transferências e aportes), metas (aporte sem rateio e valor devolvido no desfazer) e o frontend.
- **Date**: 2026-09-26
- **Status**: active

### AD-027
- **Decision**: Uma despesa ou compra no cartão pode ser dependente de uma transação principal, num nível só: a dependente tem uma principal só, e a principal não é dependente de outra. O vínculo é só informação: não altera saldo, fatura nem orçamento, cada dependente conta só na própria categoria, e excluir a principal apenas desfaz o vínculo. A compra parcelada se liga inteira, pela primeira parcela. O vínculo fica só no app, fora dos arquivos de exportação e importação.
- **Reason**: decisão do usuário (PROP-03). Mostra o custo real de um gasto sem distorcer os totais por categoria.
- **Trade-off**: cadeias, como um gasto que puxa outro que puxa um terceiro, ficam achatadas num nível, e a planilha exportada não leva o vínculo.
- **Scope**: vinculo-entre-transacoes, relatorios (contagem por categoria), exportação (filtro), faturas (parcelas) e o frontend.
- **Date**: 2026-09-26
- **Status**: active

### AD-028
- **Decision**: O valor de uma meta é a soma dos aportes menos os resgates registrados para ela, calculada a partir desses registros e não guardada à parte. Várias metas podem usar o mesmo cofrinho; o que entra ou sai dele por fora de aporte e resgate muda só o saldo livre do cofrinho, sem rateio entre as metas. Aporte e resgate podem usar o saldo livre do próprio cofrinho sem criar transferência, e excluir ou mudar a transação de um aporte ou resgate muda a meta na mesma operação.
- **Reason**: decisão do usuário. Acaba com o valor que não volta (FIN-09), a meta inflada pelo próprio cofrinho (FIN-20), o crédito de um lado só entre cofrinhos (FIN-37) e os centavos do rateio (FIN-38).
- **Trade-off**: o dinheiro que entra no cofrinho por fora não vai sozinho para as metas; o usuário aloca o saldo livre, e o app avisa quando o cofrinho tem menos do que as metas somam.
- **Scope**: metas, saldo (transferências de e para cofrinhos), gestao-do-salario (aportes da divisão), permissoes-e-planos (PERM-22) e o frontend.
- **Date**: 2026-09-26
- **Status**: active

### AD-029
- **Decision**: Relatórios, dashboard, orçamentos e demais totais de gastos contam as despesas efetivadas na data delas e as compras no cartão na data da compra, mesmo com a fatura aberta; numa compra parcelada, a parcela N conta N-1 meses depois da data da compra. As despesas pendentes aparecem à parte, como "A pagar". Receitas contam só as efetivadas. Transferências, pagamentos de fatura e ajustes de saldo ficam fora de receitas e despesas. O patrimônio é a soma das contas ativas menos as compras não pagas dos cartões; os cofrinhos entram como reservas e ficam fora do dinheiro disponível. O dinheiro guardado no mês é o que entra em cofrinhos e investimentos vindo das outras contas, menos o que sai deles.
- **Reason**: decisão do usuário. Hoje cada relatório escolhe as transações do seu jeito, soma pendências e deixa os cofrinhos fora de tudo (FIN-26 e FIN-33).
- **Trade-off**: uma despesa lançada como pendente só entra nos gráficos quando é efetivada, e o patrimônio fica menor para quem tem fatura aberta.
- **Scope**: relatorios, dashboard, orçamentos (gasto do orçamento), classes-de-despesa (divisão por classe), gestao-do-salario (histórico e comprometido), vinculo-entre-transacoes (gastos puxados) e metas.
- **Date**: 2026-09-26
- **Status**: active

### AD-030
- **Decision**: Toda ação de administrador vira um registro no log de auditoria, com quem fez, quando, a ação, o usuário afetado e os valores de antes e de depois. O registro identifica as pessoas só pelo identificador interno e pelo e-mail mascarado, é somente leitura pela API e continua depois da exclusão da conta do usuário afetado. Eventos de segurança dos próprios usuários ficam fora do log de auditoria.
- **Reason**: decisão do usuário. Hoje o log aparece vazio na tela (CON-10), a exclusão definitiva não deixa registro e o nome do administrador vai para o log.
- **Trade-off**: toda ação de administração nova precisa gravar o log, e um problema de segurança do lado do usuário não aparece no painel.
- **Scope**: painel-admin, permissoes-e-planos (travas e liberação para testes), sessao (modo manutenção), lgpd (exclusão pelo administrador) e autenticacao (redefinição de senha pelo administrador).
- **Date**: 2026-09-26
- **Status**: active

## Handoff

- **Feature**: série de specs da auditoria (`.specs/features/`)
- **Phase / Task**: Specify de `saldo` (SALDO-01 a SALDO-47), `faturas` (FATURA-01 a FATURA-45), `importacao` (IMPORT-01 a IMPORT-41), `isolamento-entre-usuarios` (ISOL-01 a ISOL-18), `autenticacao` (AUTH-01 a AUTH-44), `sessao` (SESSAO-01 a SESSAO-25), `permissoes-e-planos` (PERM-01 a PERM-29), `lgpd` (LGPD-01 a LGPD-25), `contratos-frontend-backend` (CONTRATO-01 a CONTRATO-35), `classes-de-despesa` (CLASSE-01 a CLASSE-40), `gestao-do-salario` (SALARIO-01 a SALARIO-56), `vinculo-entre-transacoes` (VINCULO-01 a VINCULO-37), `metas` (META-01 a META-45), `relatorios` (REL-01 a REL-25) e `painel-admin` (ADMIN-01 a ADMIN-29) concluídas e aprovadas; Design de nenhuma delas iniciado
- **Completed**: `saldo`, `faturas`, `importacao`, `isolamento-entre-usuarios`, `autenticacao`, `sessao`, `permissoes-e-planos`, `lgpd`, `contratos-frontend-backend`, `classes-de-despesa`, `gestao-do-salario`, `vinculo-entre-transacoes`, `metas`, `relatorios` e `painel-admin` (`spec.md` e `context.md` de cada uma); seção 11 da auditoria, com as propostas PROP-01 a PROP-05
- **In-progress** (file:line): nenhum
- **Next step**: levar os preparativos da PROP-04 às specs `lgpd` (finalidade de melhoria do produto e aceite dos termos por versão) e `importacao` (correções de categoria), com um commit próprio. Depois, o push e o PR da branch; PROP-04 e PROP-05 não viram spec agora.
- **Blockers**: nenhum
- **Uncommitted files**: nenhum
- **Branch**: docs/specs-features-auditoria-2026-09
