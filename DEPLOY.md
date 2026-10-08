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

## 🩺 Health Check
O Render monitora a saúde da aplicação através do endpoint:
- `/api/health/` (Retorna 200 OK)
