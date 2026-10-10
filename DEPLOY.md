# 🚀 Guia de Deploy - Fluxar Backend

Este repositório utiliza **GitHub Actions** para CI e **Render** para CD (Deploy Contínuo).

## 🔄 Fluxo de CI/CD
1. **Pull Request:** Ao abrir um PR para a `main` ou a `development`, o GitHub Actions roda:
   - Instalação de dependências.
   - Auditoria de dependências (`pip-audit`).
   - Verificação de sintaxe (`compileall`).
   - Verificação de migrações pendentes.
   - Testes (`manage.py test`), com um Postgres 15.
2. **Merge na Main:** O Render detecta o push automaticamente e inicia o deploy.

## ☁️ Configuração no Render
O serviço deve ser configurado como **Web Service** (Python 3). O Render roda o Python nativo, não o `Dockerfile`, então o `entrypoint.sh` não é executado lá: os comandos abaixo precisam estar no painel.

### Build & Start
- **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- **Pre-Deploy Command:** `python manage.py check --deploy && python manage.py migrate --noinput && python manage.py createcachetable`
  - `check --deploy` recusa a `SECRET_KEY` que já apareceu no histórico do repositório.
  - `createcachetable` cria a tabela de cache usada pelos limites de tentativas; sem ela, as rotas de autenticação respondem 500.
  - Se o plano não tiver Pre-Deploy Command, coloque os três comandos no fim do Build Command.
- **Start Command:** `gunicorn core.wsgi:application`
  - O gunicorn lê sozinho o `gunicorn.conf.py` da raiz: workers `gthread` com threads, timeout de 120 s e a porta de `PORT`. Assim uma importação ocupa só uma thread, e as outras requisições seguem atendidas (AD-043).

### Variáveis de Ambiente (Production)
Configure estas chaves no painel do Render:
- `PYTHON_VERSION`: `3.11.0`
- `SECRET_KEY`: chave nova e aleatória, que nunca apareceu no repositório. Obrigatória: sem ela o backend não sobe.
- `DEBUG`: `0`
- `ALLOWED_HOSTS`: `fluxar-api.onrender.com` (ou seu domínio customizado)
- `DATABASE_URL`: (Connection string interna do PostgreSQL no Render)
- `FRONTEND_URL`: endereço do frontend, usado nos links dos e-mails. Obrigatória: sem ela o backend não sobe.
- `CORS_ALLOWED_ORIGINS`: origens do frontend, separadas por vírgula. Sem ela, nenhuma origem é liberada.
- `NUM_PROXIES`: quantos proxies ficam na frente da aplicação, para ler o IP do cliente nos limites de tentativas (padrão `1`).
- `WEB_CONCURRENCY`: quantos workers do gunicorn (padrão `2`). Se a memória do plano não der, use `1`; as threads continuam atendendo outras requisições durante uma importação.
- `GUNICORN_THREADS`: threads por worker (padrão `4`).
- E-mail: `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL` e, para o fallback SMTP, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD`.
- `FIELD_ENCRYPTION_KEY`: chave Fernet que criptografa CPF, telefone, data de nascimento e renda no banco (LGPD-15, AD-047). Obrigatória: sem ela o backend não sobe.
  - **Configure antes do deploy que traz a criptografia**: a migração `api/0014` criptografa os dados já gravados no Pre-Deploy e precisa da chave definitiva.
  - Gere com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  - Guarde uma cópia fora do Render (num gerenciador de senhas): sem a chave, os dados criptografados ficam ilegíveis.
  - Para trocar a chave, coloque a nova na frente, separada por vírgula (`nova,antiga`): a primeira grava e todas leem. Só retire a antiga depois de regravar os dados.
- `ROTINA_DIARIA_TOKEN`: token longo e aleatório que protege `POST /api/rotina-diaria/` (AD-048). Gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Sem ele, a rota responde 404 e a rotina só roda pelo comando.
- `APP_VERSION` (opcional): a versão mostrada no painel admin, como `1.3.0` (ADMIN-03, AD-051). Sem ela, o painel mostra os 7 primeiros caracteres de `RENDER_GIT_COMMIT`, que o Render preenche sozinho em todo deploy; não crie `RENDER_GIT_COMMIT` à mão. Sem as duas, como no ambiente local, aparece "desenvolvimento".

### Rotina diária (GitHub Actions)
O workflow `.github/workflows/rotina-diaria.yml` roda todo dia às 6h UTC (3h de Brasília) e chama `POST /api/rotina-diaria/`, que apaga as contas cuja exclusão definitiva venceu (30 dias depois do pedido). Em **Settings → Secrets and variables → Actions** do repositório, crie:
- `API_URL`: URL do Render, sem `/api` no fim (ex.: `https://fluxar-api.onrender.com`).
- `ROTINA_DIARIA_TOKEN`: o mesmo valor da variável do Render.

A resposta traz `{excluidas, falhas}`. Uma conta que falha (por exemplo, com o Cloudinary fora do ar) continua desativada e marcada, e é apagada na execução seguinte. Para rodar à mão, use **Run workflow** na aba Actions ou `python manage.py rotina_diaria` no Render Shell.

### Frontend na Vercel (proxy da API)
O frontend chama a API por `/api` na própria origem, e o Next.js repassa para o Render (AD-036). Na Vercel:
- `BACKEND_URL`: URL do Render, sem `/api` no fim (ex.: `https://fluxar-api.onrender.com`). Lida no build: depois de criar ou mudar, faça um novo deploy.
- No Render, inclua o domínio da Vercel em `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS`; a renovação e o logout recusam outra origem (403).
- Depois do primeiro deploy com o proxy, confira num log do Render o `X-Forwarded-For` e ajuste `NUM_PROXIES`; confira também que a renovação responde 200 (sinal de que `Origin` e o cookie passam pelo proxy).
- Todos os usuários entram de novo uma vez: as sessões antigas não têm o `sid`.

### Depois do deploy
- `python manage.py check_isolation`: deve listar 0 ligações entre usuários.
- `python manage.py check_saldos`: deve terminar com "Contas com saldo divergente: 0" (a migração `transactions/0008` recalcula os saldos no `migrate`).
- `python manage.py check_email_case`: lista as contas cujos e-mails só diferem na caixa, para resolução manual.
- `python manage.py divergencias_de_admin`: lista quem tem `is_staff` sem o papel `ADMIN` e quem tem o papel sem `is_staff`, e termina com "Contas divergentes: N". Não altera ninguém: o administrador do app é só quem tem o papel (AD-016), e cada caso é decidido à mão (PERM-29).
- O `create_admin.py` só cria o administrador de `DJANGO_SUPERUSER_EMAIL` quando não existe nenhum administrador ativo, e nunca promove nem altera contas existentes (PERM-07).

## 🩺 Health Check
O Render monitora a saúde da aplicação através do endpoint:
- `/api/health/` (Retorna 200 OK)
