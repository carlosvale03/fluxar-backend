# Painel admin Specification

## Problem Statement

O painel admin mostra dados que não existem e esconde os que existem. Depois de um erro da API, a tela do usuário exibe "Usuário Mock", e o administrador pode mudar o plano ou excluir alguém vendo uma identidade falsa (SEG-07). O log de auditoria aparece sempre vazio, e a tela de configurações mostra valores fixos ("Uptime: 99.9%", "PostgreSQL 15.4") e um botão "Limpar Cache" que não faz nada (CON-10). O dashboard mostra "API HEALTH CHECK OK" fixo e chama de "Assinaturas ativas" usuários que nunca pagaram, e a receita é estimada com preços escritos no código (`api/views.py:471-476`). O "Limpar dados" apaga em nove etapas sem ser tudo ou nada e deixa o usuário sem nenhuma categoria (FIN-42).

Origem: `docs/auditoria-2026-09.md`, seção 3 (SEG-07), seção 4 (CON-10) e seção 2 (FIN-28 e FIN-42), além dos itens que as specs `permissoes-e-planos`, `saldo` e `metas` encaminharam para cá.

## Goals

- [ ] Nenhuma tela do painel mostra dado inventado ou fixo no código.
- [ ] Toda ação de administrador fica registrada, sem dado pessoal, e aparece no log.
- [ ] Limpar ou excluir um usuário é tudo ou nada e exige confirmação.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
| ------- | ------ |
| Quem é administrador, travas dos planos e liberação para testes | Spec `permissoes-e-planos` |
| Modo manutenção e fim das sessões | Spec `sessao` |
| Exclusão definitiva, registro da exclusão e dados pessoais mascarados | Spec `lgpd` (LGPD-11, LGPD-13 e LGPD-19) |
| Paginação das listas do admin | Spec `contratos-frontend-backend` (CONTRATO-02) |
| Receita, assinaturas e pagamentos | Spec da cobrança dos planos, quando existir |
| Comando `cleanup_db` (FIN-43) | A regra já está na spec `saldo`: não apaga o histórico de contas excluídas nem muda o saldo de contas ativas |
| Uptime do sistema | Exige monitoramento externo; o painel mostra só o que o backend mede |
| Eventos de segurança dos próprios usuários no log | Decisão do usuário: o log de auditoria cobre as ações de administradores |
| HTTPS, HSTS e cookies do admin do Django (SEG-13) | Feature de infraestrutura |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Receita e assinatura | Somem até existir cobrança; "Assinaturas ativas" vira "Usuários em planos pagos" | Decisão do usuário | sim |
| Limpar dados | Tudo ou nada, e o usuário fica como um cadastro novo | Decisão do usuário | sim |
| Log de auditoria | Todas as ações de administradores | Decisão do usuário (AD-030) | sim |
| Senha do administrador | Pedida só para excluir, limpar dados, redefinir senha, mudar papel e desativar conta | Decisão do usuário | sim |
| Saúde do sistema | Estado da API e do banco, com a latência e a versão do banco medidas na hora | O backend já mede o banco; o uptime exigiria monitoramento externo | sim |
| Versão do sistema | Lida da configuração do deploy | Hoje "1.2.5" está fixa no código | sim |
| Identificação no log | Administrador e usuário afetado pelo identificador interno e pelo e-mail mascarado | A AD-019 proíbe nome e e-mail completo em log | sim |
| Log depois da exclusão da conta | Os registros sobre o usuário continuam, só com o identificador interno | Mantém a trilha de quem fez o quê, sem dado pessoal, como o registro da LGPD-11 | sim |
| Filtros do log | Por ação, por administrador e por período | Num log longo, achar uma ação sem filtro é inviável | sim |
| Log somente leitura | A API não cria, altera nem apaga registros | Um log que se edita não serve de auditoria | sim |
| Confirmação de limpar e de excluir | A tela mostra o que será apagado e pede que o administrador digite o e-mail do usuário | Evita apagar o usuário errado | sim |
| O que a limpeza mantém | Login, senha, perfil, plano e papel | É o que a função promete hoje | sim |
| Imagens das metas na limpeza | Apagadas no Cloudinary junto com as metas | Mesma regra da exclusão da conta (AD-018) | sim |
| Busca de usuários | Por nome ou e-mail, com filtros de plano, papel e status | É o que a lista já oferece | sim |
| Estatísticas financeiras do usuário | Pelas regras da spec `relatorios`, sem as contas excluídas | Os números do painel batem com os que o usuário vê | sim |
| Limpar os próprios dados | Recusado, como em PERM-06 | Um administrador não apaga os próprios dados por engano | sim |

**Open questions:** none. As decisões em aberto estão resolvidas ou registradas na tabela acima.

---

## User Stories

### P1: Telas sem dados falsos ⭐ MVP

**User Story**: Como administrador, quero que o painel mostre só dados reais, para não tomar decisões sobre informação inventada.

**Why P1**: hoje o administrador pode excluir alguém vendo "Usuário Mock" (SEG-07), e a saúde, a versão e o uptime são valores fixos (CON-10).

**Acceptance Criteria**:
1. **ADMIN-01** IF a API falhar ao carregar os dados de um usuário THEN a interface SHALL mostrar o erro com a opção de tentar de novo e desabilitar todas as ações sobre ele, sem exibir dados de exemplo.
2. **ADMIN-02** WHEN o painel mostra a saúde do sistema THEN o sistema SHALL devolver o estado da API e do banco, com a latência e a versão do banco medidas na hora.
3. **ADMIN-03** WHEN o painel mostra a versão do sistema THEN o sistema SHALL devolver a versão do deploy em execução, lida da configuração.
4. **ADMIN-04** WHEN a tela de configurações é aberta THEN a interface SHALL mostrar só as ações que o backend executa: modo manutenção, liberação para testes e travas dos planos.
5. **ADMIN-05** WHILE não existir cobrança dos planos, o sistema SHALL deixar de calcular e de mostrar receita.
6. **ADMIN-06** WHILE não existir cobrança dos planos, a interface SHALL esconder a aba "Assinatura" do usuário.
7. **ADMIN-07** WHEN o dashboard do admin carrega THEN o sistema SHALL mostrar o total de usuários, a quantidade em cada plano, os cadastros recentes e a porcentagem de usuários em planos pagos, com o rótulo "Usuários em planos pagos".

**Independent Test**: com a rota de detalhes do usuário devolvendo 500, a tela mostra o erro e nenhum botão de ação habilitado; o dashboard mostra a latência real do banco e nenhum "API HEALTH CHECK OK" fixo; a tela de configurações não tem "Uptime", "PostgreSQL 15.4" nem "Limpar Cache"; nenhuma tela mostra receita.

---

### P1: Log de auditoria ⭐ MVP

**User Story**: Como administrador, quero ver quem fez cada ação no painel, quando e sobre quem, para responder por qualquer mudança.

**Why P1**: hoje o log aparece vazio (CON-10), a exclusão definitiva não deixa registro e o nome do administrador vai para o log.

**Acceptance Criteria**:
1. **ADMIN-08** WHEN um administrador muda o plano, o papel ou o status de um usuário, redefine a senha dele, limpa os dados ou exclui a conta THEN o sistema SHALL registrar no log quem fez, quando, a ação, o usuário afetado e os valores de antes e de depois, quando houver.
2. **ADMIN-09** WHEN um administrador liga ou desliga o modo manutenção, a liberação para testes ou uma trava de plano, ou muda um limite, THEN o sistema SHALL registrar no log quem fez, quando e os valores de antes e de depois.
3. **ADMIN-10** WHEN o sistema registra um log de auditoria THEN o sistema SHALL identificar o administrador e o usuário afetado só pelo identificador interno e pelo e-mail mascarado (AD-019).
4. **ADMIN-11** WHEN a conta de um usuário é excluída THEN o sistema SHALL manter os registros do log sobre ele, só com o identificador interno, junto com o registro da exclusão (LGPD-11).
5. **ADMIN-12** WHEN o administrador abre o log de auditoria THEN a interface SHALL mostrar a lista paginada de CONTRATO-02, do registro mais recente para o mais antigo, com navegação entre as páginas.
6. **ADMIN-13** WHEN o administrador filtra o log por ação, por administrador ou por período THEN o sistema SHALL devolver só os registros que atendem aos filtros.
7. **ADMIN-14** WHEN o administrador abre o log de um usuário THEN o sistema SHALL devolver os registros sobre ele, paginados no formato de CONTRATO-02.
8. **ADMIN-15** IF uma requisição tentar criar, alterar ou apagar um registro do log pela API THEN o sistema SHALL recusá-la com HTTP 405.

**Independent Test**: mudar o plano de um usuário de Comum para Premium cria um registro com o administrador, o usuário, "COMMON" e "PREMIUM", sem nome nem e-mail completo; ligar o modo manutenção aparece no log com o valor de antes e de depois; depois de excluir a conta do usuário, os registros sobre ele continuam com o identificador interno; a tela do log mostra 20 registros por página.

---

### P1: Operações sobre usuários ⭐ MVP

**User Story**: Como administrador, quero buscar usuários, mudar plano, papel e status, redefinir senhas, limpar dados e excluir contas com segurança, sem apagar a pessoa errada nem deixar nada pela metade.

**Why P1**: hoje o "Limpar dados" roda em nove etapas sem ser tudo ou nada e deixa o usuário sem categorias (FIN-42), e a exclusão de quem tem compras no cartão provavelmente falha (FIN-28).

**Acceptance Criteria**:
1. **ADMIN-16** WHEN o administrador busca usuários THEN o sistema SHALL procurar pelo nome ou pelo e-mail e filtrar por plano, papel e status, na lista paginada de CONTRATO-02.
2. **ADMIN-17** WHEN o administrador exclui uma conta, limpa os dados, redefine a senha, muda o papel ou desativa um usuário THEN o sistema SHALL exigir a senha do administrador.
3. **ADMIN-18** IF a senha do administrador faltar ou estiver errada numa dessas ações THEN o sistema SHALL recusar com HTTP 403 e a mensagem "Senha do administrador incorreta." no campo da senha.
4. **ADMIN-19** WHEN o administrador muda o plano de um usuário THEN o sistema SHALL aplicar a mudança sem pedir a senha.
5. **ADMIN-20** WHEN o administrador pede para limpar os dados ou excluir a conta de um usuário THEN a interface SHALL mostrar o que será apagado e só confirmar depois que ele digitar o e-mail do usuário.
6. **ADMIN-21** WHEN o administrador limpa os dados de um usuário THEN o sistema SHALL apagar, numa única operação, transações, recorrências, contas, cartões e faturas, categorias, classes, tags, orçamentos, metas, monitores de foco, o plano da gestão do salário e os vínculos entre transações.
7. **ADMIN-22** WHEN a limpeza termina THEN o sistema SHALL recriar o padrão de um cadastro novo: as classes Essencial e Dispensável (CLASSE-01), as categorias padrão com as classes iniciais (CLASSE-24) e a conta Carteira.
8. **ADMIN-23** WHEN o administrador limpa os dados de um usuário THEN o sistema SHALL manter o login, a senha, o perfil, o plano e o papel dele.
9. **ADMIN-24** WHEN a limpeza apaga metas com imagem THEN o sistema SHALL apagar também as imagens no Cloudinary.
10. **ADMIN-25** IF a limpeza falhar no meio THEN o sistema SHALL manter os dados do usuário como estavam.
11. **ADMIN-26** WHILE houver duas limpezas simultâneas do mesmo usuário, o sistema SHALL terminar com um único conjunto de dados padrão.
12. **ADMIN-27** IF um administrador tentar limpar os próprios dados pelo painel THEN o sistema SHALL recusar com HTTP 400.
13. **ADMIN-28** WHEN o administrador exclui a conta de um usuário com compras no cartão, parcelas, transferências e metas THEN o sistema SHALL concluir a exclusão definitiva conforme LGPD-13.
14. **ADMIN-29** WHEN o administrador abre as estatísticas financeiras de um usuário THEN o sistema SHALL calculá-las pelas regras da spec `relatorios` (AD-029), sem as contas excluídas (SALDO-31).

**Independent Test**: buscar "maria" com o filtro Premium traz só as Marias do plano Premium; mudar o plano não pede senha, e desativar pede; limpar os dados de um usuário com 300 transações deixa só as categorias padrão, as duas classes e a Carteira, com o login funcionando; com uma falha forçada na metade da limpeza, todas as 300 transações continuam lá; excluir um usuário com uma compra parcelada termina sem erro.

---

## Edge Cases

- Limpar os dados de um usuário duas vezes seguidas: termina no mesmo estado de um cadastro novo, sem padrão duplicado (ADMIN-22, ADMIN-26).
- Limpar os dados de um usuário no meio de uma divisão do salário ainda desfazível: a divisão some junto com as transações, sem nada a desfazer (ADMIN-21).
- Administrador digita o e-mail errado na confirmação: nada é apagado (ADMIN-20).
- Log de um usuário que já foi excluído: continua consultável pelo identificador interno (ADMIN-11, ADMIN-14).
- Banco fora do ar: a saúde mostra o banco com erro e sem latência, em vez de "Operacional" (ADMIN-02).

---

## Implicit-Requirement Dimensions

| Dimensão | Cobertura |
| -------- | --------- |
| Validação de entrada e limites | ADMIN-18, ADMIN-20, ADMIN-27 |
| Falha e falha parcial | ADMIN-01, ADMIN-25 |
| Idempotência, repetição e duplicidade | ADMIN-22, ADMIN-26 |
| Autorização e rate limiting | ADMIN-17, ADMIN-18; quem é administrador está em PERM-01 e PERM-02 |
| Concorrência e ordem | ADMIN-26 |
| Ciclo de vida dos dados | ADMIN-11, ADMIN-21, ADMIN-23, ADMIN-24, ADMIN-28 |
| Observabilidade | ADMIN-08, ADMIN-09, ADMIN-10 |
| Falha de dependência externa | ADMIN-02 (banco fora do ar) e ADMIN-24 (Cloudinary) |
| Integridade das transições de estado | ADMIN-15 (log imutável) |

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| ADMIN-01 | P1: Telas sem dados falsos | T15 | Pending |
| ADMIN-02 | P1: Telas sem dados falsos | T9, T12, T13 | Pending |
| ADMIN-03 | P1: Telas sem dados falsos | T9, T13 | Pending |
| ADMIN-04 | P1: Telas sem dados falsos | T13 | Pending |
| ADMIN-05 | P1: Telas sem dados falsos | T9, T12 | Pending |
| ADMIN-06 | P1: Telas sem dados falsos | T15 | Pending |
| ADMIN-07 | P1: Telas sem dados falsos | T9, T12 | Pending |
| ADMIN-08 | P1: Log de auditoria | T2 | Implemented |
| ADMIN-09 | P1: Log de auditoria | T3 | Implemented |
| ADMIN-10 | P1: Log de auditoria | T1 | Implemented |
| ADMIN-11 | P1: Log de auditoria | T1, T2 | Implemented |
| ADMIN-12 | P1: Log de auditoria | T4, T14 | In Progress |
| ADMIN-13 | P1: Log de auditoria | T4, T14 | In Progress |
| ADMIN-14 | P1: Log de auditoria | T4, T14 | In Progress |
| ADMIN-15 | P1: Log de auditoria | T4 | Implemented |
| ADMIN-16 | P1: Operações sobre usuários | T11, T17 | Pending |
| ADMIN-17 | P1: Operações sobre usuários | T5, T16 | In Progress |
| ADMIN-18 | P1: Operações sobre usuários | T5, T16 | In Progress |
| ADMIN-19 | P1: Operações sobre usuários | T5, T16 | In Progress |
| ADMIN-20 | P1: Operações sobre usuários | T16 | Pending |
| ADMIN-21 | P1: Operações sobre usuários | T7 | Implemented |
| ADMIN-22 | P1: Operações sobre usuários | T6, T7 | Implemented |
| ADMIN-23 | P1: Operações sobre usuários | T7 | Implemented |
| ADMIN-24 | P1: Operações sobre usuários | T7 | Implemented |
| ADMIN-25 | P1: Operações sobre usuários | T7 | Implemented |
| ADMIN-26 | P1: Operações sobre usuários | T7 | Implemented |
| ADMIN-27 | P1: Operações sobre usuários | T7 | Implemented |
| ADMIN-28 | P1: Operações sobre usuários | T8 | Pending |
| ADMIN-29 | P1: Operações sobre usuários | T10 | Pending |

**Coverage:** 29 total, 29 mapped to tasks, 0 unmapped ✅

---

## Success Criteria

- [ ] Uma busca no código do painel não encontra nenhum valor de exemplo, fixo ou simulado exibido como dado real.
- [ ] Toda ação de administrador feita num teste de ponta a ponta aparece no log, sem nome nem e-mail completo.
- [ ] Nenhuma limpeza ou exclusão deixa dados pela metade, mesmo com falha forçada.
