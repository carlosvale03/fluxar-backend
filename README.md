# Fluxar – Sistema de Controle Financeiro Pessoal (Backend)

[![CI Backend](https://github.com/carlosvale03/fluxar-backend/actions/workflows/ci-backend.yml/badge.svg)](https://github.com/carlosvale03/fluxar-backend/actions/workflows/ci-backend.yml)

O **Fluxar** é uma API RESTful robusta desenvolvida para fornecer inteligência e controle total sobre a vida financeira do usuário. O projeto segue uma arquitetura moderna de desacoplamento (**API + SPA**), servindo como o motor central para o frontend desenvolvido em Next.js.

## 🚀 Tecnologias Utilizadas

- **Linguagem:** Python 3.11+
- **Framework Principal:** [Django 5.0](https://www.djangoproject.com/)
- **API Toolkit:** [Django Rest Framework (DRF)](https://www.django-rest-framework.org/)
- **Autenticação:** JWT (JSON Web Tokens) via SimpleJWT
- **Banco de Dados:** PostgreSQL 15
- **Manipulação de Dados:** Pandas & Openpyxl
- **Geração de Documentos:** ReportLab (PDF)
- **Containerização:** Docker & Docker Compose
- **Deploy:** Render

---

## 🏗️ Arquitetura e Módulos

O backend está organizado em apps modulares, cada um responsável por uma área de domínio do sistema:

- **`api`**: Núcleo do sistema, gerindo a autenticação (Register/Login), perfis de usuários e tokens JWT.
- **`accounts`**: Gestão de contas bancárias (Corrente, Poupança, Investimento) e Cartões de Crédito (Limite, Fechamento, Vencimento).
- **`transactions`**: O coração financeiro. Gerencia receitas, despesas, transferências e etiquetas (tags), com suporte a transações recorrentes.
- **`budgets`**: Sistema de orçamentos mensais por categoria, com alertas de limites de gastos.
- **`reports`**: Inteligência financeira com endpoints para dashboards, gráficos avançados, score de saúde e evolução patrimonial.
- **`data_exchange`**: Módulo de integração para importação de arquivos (OFX, XLS/CSV) e exportação de relatórios financeiros.
- **`goals`**: Gestão de metas financeiras e "cofrinhos" (Funcionalidade Premium Plus).

---

## ⚙️ Como Rodar o Projeto

### 1. Configuração de Variáveis de Ambiente
Na raiz do diretório `fluxar-backend`, crie um arquivo `.env` baseado no exemplo:

```bash
cp .env.example .env
```

Ajuste as variáveis no `.env` conforme necessário (especialmente a `SECRET_KEY` e as credenciais do DB).

### 2. Execução com Docker (Recomendado) 🐳
Certifique-se de ter o Docker instalado e execute:

```bash
docker compose up --build
```
*   **Backend:** `http://localhost:8000/api`
*   **Admin:** `http://localhost:8000/admin`
*   **DB:** PostgreSQL rodando na porta `5433` (mapeada da 5432 interna).

### 3. Instalação Local (Sem Docker) 🐍
Caso prefira rodar diretamente na máquina:

1. **Crie e ative um ambiente virtual:**
   ```bash
   python -m venv venv
   # Linux/Mac:
   source venv/bin/activate
   # Windows:
   .\venv\Scripts\activate
   ```
2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure o banco de dados** no seu `.env` para apontar para um PostgreSQL local.
4. **Rode as migrações e o servidor:**
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

---

## 🗄️ Migrações e Superusuário

### Rodar Migrações
Sempre que houver mudanças nos modelos:

**Local:**
```bash
python manage.py makemigrations
python manage.py migrate
```

**Com Docker:**
```bash
docker compose exec backend python manage.py migrate
```

### Criar Superusuário (Acesso ao Admin)
Para acessar o painel administrativo em `/admin`:

```bash
docker compose exec backend python manage.py createsuperuser
```

---

## 📂 Estrutura de Pastas

```text
fluxar-backend/
├── core/               # Configurações globais (settings, urls, wsgi)
├── api/                # Gestão de usuários e autenticação
├── accounts/           # Contas e Cartões de Crédito
├── transactions/       # Transações e Categorias
├── budgets/            # Planejamento orçamentário
├── reports/            # Dashboards e Analytics
├── data_exchange/      # Importação/Exportação (OFX, XLS, PDF)
├── goals/              # Metas financeiras (Premium Plus)
├── media/              # Arquivos de upload (avatars, comprovantes)
├── manage.py           # CLI do Django
└── Dockerfile          # Definição da imagem Docker
```

---

## 🔄 CI/CD e Deploy

O projeto utiliza **GitHub Actions** para Integração Contínua (CI), garantindo que todo código enviado para a branch `main` passe por testes de sintaxe e verificações de migração.

- **Deploy Backend:** Realizado automaticamente no [Render](https://render.com/) ao realizar push na branch `main`.
- **Banco de Dados:** PostgreSQL gerenciado no Render.

---

## 🤝 Como Contribuir

1. Faça um **Fork** do projeto.
2. Crie uma **Branch** para sua feature (`git checkout -b feat/minha-feature`).
3. Faça o **Commit** das suas alterações seguindo o padrão [Conventional Commits](https://www.conventionalcommits.org/).
4. Faça o **Push** para a branch (`git push origin feat/minha-feature`).
5. Abra um **Pull Request**.

---

## 📄 Licença

Este projeto foi desenvolvido para fins educacionais e de demonstração de portfólio. O código está aberto para consulta, estudo e contribuições fundamentadas no aprendizado. Para informações sobre licenciamento comercial ou redistribuição, por favor, entre em contato com os mantenedores.
