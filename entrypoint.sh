#!/bin/sh

# Falhar o script se algum comando der erro
set -e

echo "📍 Rodando Migrations..."
python manage.py migrate --noinput

echo "📍 Criando Superusuário (se necessário)..."
python create_admin.py

echo "📍 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "🚀 Iniciando Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000

