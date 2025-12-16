# 🚀 Guia de Deploy - Fluxar Backend

Este repositório utiliza **GitHub Actions** para CI e **Render** para CD (Deploy Contínuo).

## 🔄 Fluxo de CI/CD
1. **Pull Request:** Ao abrir um PR para a `main`, o GitHub Actions roda:
   - Instalação de dependências.
   - Verificação de sintaxe (`compileall`).
   - Verificação de migrações pendentes.
2. **Merge na Main:** O Render detecta o push automaticamente e inicia o deploy.

## ☁️ Configuração no Render
O serviço deve ser configurado como **Web Service** (Python 3).

### Build & Start
- **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- **Start Command:** `gunicorn core.wsgi:application`

### Variáveis de Ambiente (Production)
Configure estas chaves no painel do Render:
- `PYTHON_VERSION`: `3.11.0`
- `SECRET_KEY`: (Sua chave secreta de produção)
- `DEBUG`: `0`
- `ALLOWED_HOSTS`: `fluxar-api.onrender.com` (ou seu domínio customizado)
- `DATABASE_URL`: (Connection string interna do PostgreSQL no Render)

## 🩺 Health Check
O Render monitora a saúde da aplicação através do endpoint:
- `/api/health/` (Retorna 200 OK)
