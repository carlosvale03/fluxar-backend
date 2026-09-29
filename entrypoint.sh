#!/bin/sh

# Falhar o script se algum comando der erro
set -e

echo "📍 Conferindo a configuração de produção..."
python manage.py check --deploy

echo "📍 Rodando Migrations..."
python manage.py migrate --noinput

echo "📍 Criando Superusuário (se necessário)..."
python create_admin.py

echo "📍 Criando a tabela de cache..."
python manage.py createcachetable

echo "📍 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "🚀 Iniciando Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --timeout 120

