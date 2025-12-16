# Fluxar Backend

API RESTful para o sistema de controle financeiro Fluxar, desenvolvida com Django e Django Rest Framework.

## 🚀 Tecnologias
- Python 3.11+
- Django 5
- Django Rest Framework
- PostgreSQL
- Docker & Docker Compose

## ⚙️ Configuração de Ambiente

Antes de executar o projeto, é necessário configurar as variáveis de ambiente.

1. **Copie o arquivo de exemplo:**
   Na raiz do projeto (`fluxar-backend`), faça uma cópia do `.env.example`:
   ```bash
   cp .env.example .env
   # Ou no Windows: copy .env.example .env
   ```

2. **Ajuste as variáveis** (se necessário): O arquivo .env já vem com valores padrão para o ambiente de desenvolvimento Docker.

- SECRET_KEY: Chave de segurança do Django (altere em produção).
- DEBUG: 1 para ativado, 0 para desativado.
- DB_*: Credenciais do banco de dados.

## 🐳 Execução com Docker (Recomendado)

Certifique-se de estar na raiz do projeto ou na raiz do workspace (`fluxar/`).

```bash
docker compose up --build
```

A API estará disponível em: `http://localhost:8000/api` Painel Admin: `http://localhost:8000/admin`

## 📦 Instalação Local (Sem Docker)
- Crie o ambiente virtual: `python -m venv venv`
- Ative: source `venv/bin/activate` (Linux/Mac) ou `.\venv\Scripts\activate` (Windows)
- Instale dependências: `pip install -r requirements.txt`
- Configure o `.env` apontando para um banco local.
- Execute: `python manage.py runserver`
