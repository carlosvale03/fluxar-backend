"""
Configuração do gunicorn, lida automaticamente por `gunicorn core.wsgi:application`
(IMPORT-41, AD-043).

Com `gthread`, uma importação ocupa uma thread e as outras requisições
seguem atendidas. `WEB_CONCURRENCY` e `GUNICORN_THREADS` ajustam os workers
e as threads sem mudar o Start Command. Opções passadas na linha de comando
(como o `--bind` e o `--timeout` do `entrypoint.sh`) prevalecem sobre as daqui.
"""
import os

worker_class = 'gthread'
workers = int(os.getenv('WEB_CONCURRENCY', 2))
threads = int(os.getenv('GUNICORN_THREADS', 4))
timeout = 120

if os.getenv('PORT'):
    bind = f"0.0.0.0:{os.environ['PORT']}"
