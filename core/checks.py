"""
Checagem de sistema da SECRET_KEY de produção (AUTH-42).

Recusa, com DEBUG desligado, uma chave que já apareceu no histórico do
repositório ou que começa com "django-insecure". A lista guarda só o SHA-256
de cada chave, nunca a chave.

A checagem é de implantação (`deploy=True`): roda no `check --deploy`, que o
entrypoint.sh executa antes de migrar e subir o servidor. Por isso a
inicialização em produção para com a chave comprometida, e a suíte de testes,
que força DEBUG desligado, não depende da chave do ambiente de
desenvolvimento.
"""
import hashlib

from django.conf import settings
from django.core.checks import Error, Tags, register

# SHA-256 dos valores de SECRET_KEY encontrados no histórico do git, em
# core/settings.py, docker-compose.yml, .env.example, README.md e no CI.
CHAVES_COMPROMETIDAS = frozenset({
    # core/settings.py: chave original do startproject
    '4b26d370bd974a2d08aed1307e42cd7e3c2c93165020260e45ff1b02d72f09ee',
    # core/settings.py: fallback de desenvolvimento
    '10eabb027d82dc3184b31274716fc59d509533c0e318887811b7708e86c324bc',
    # docker-compose.yml
    'a76e2054352ffa990259867657fe9592c92b189704b2d677577b978d95c9ae14',
    # .env.example
    'f05d62a86cb342e698872e56901659c5cf14d3ab7b4acccaf8bb05d91c29327b',
    # README.md
    '01966c51593afa085f19b1f1c364d8582ed1cdd1db66b820d74681c908d40645',
    # .github/workflows/ci-backend.yml
    '6fe49d6a8372ad524a3bde0e03094c87193c9ca1180a7599e09caaa751585754',
})

PREFIXO_INSEGURO = 'django-insecure'


@register(Tags.security, deploy=True)
def check_secret_key(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    chave = settings.SECRET_KEY
    comprometida = hashlib.sha256(chave.encode()).hexdigest() in CHAVES_COMPROMETIDAS
    if comprometida or chave.startswith(PREFIXO_INSEGURO):
        return [
            Error(
                'A SECRET_KEY de produção está comprometida: ela aparece no '
                'histórico do repositório ou começa com "django-insecure".',
                hint='Gere uma chave nova e defina-a na variável de ambiente SECRET_KEY.',
                id='core.E001',
            )
        ]
    return []
