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
- E-mail: `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL` e, para o fallback SMTP, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD`.

### Depois do deploy
- `python manage.py check_isolation`: deve listar 0 ligações entre usuários.
- `python manage.py check_email_case`: lista as contas cujos e-mails só diferem na caixa, para resolução manual.

## 🩺 Health Check
O Render monitora a saúde da aplicação através do endpoint:
- `/api/health/` (Retorna 200 OK)
