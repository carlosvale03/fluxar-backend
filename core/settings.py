import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', '0') == '1'


def obrigatoria_em_producao(nome, valor_de_desenvolvimento):
    """
    Lê uma variável que a produção precisa ter (AD-012). Vazia ou só com
    espaços conta como ausente. Com DEBUG ligado, a falta usa o valor de
    desenvolvimento; com DEBUG desligado, interrompe a inicialização.
    """
    valor = os.getenv(nome, '').strip()
    if valor:
        return valor
    if DEBUG:
        return valor_de_desenvolvimento
    raise ImproperlyConfigured(
        f'A variável de ambiente {nome} é obrigatória com DEBUG desligado.'
    )


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = obrigatoria_em_producao('SECRET_KEY', 'django-insecure-fallback-key')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,testserver').split(',')

AUTH_USER_MODEL = 'api.User'


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',
    # Libs de terceiros
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    # Nossos apps
    'api',
    'accounts',
    'transactions',
    'budgets',
    'reports',
    'data_exchange',
    'goals.apps.GoalsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'api.middleware.MaintenanceModeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'



# Database Configuration
# Tenta pegar DATABASE_URL (Render/Prod) ou usa as vars individuais (Docker/Local)
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
            'NAME': os.getenv('DB_NAME', 'fluxar_db'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

# Toda requisição roda numa transação de banco: uma falha no meio desfaz a
# operação inteira (SALDO-10, AD-038). Vale para os dois ramos acima.
DATABASES['default']['ATOMIC_REQUESTS'] = True


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'api.validators.SenhaParecidaValidator',
        # O padrão procura username, first_name e last_name, que o User do
        # Fluxar não tem; sem isto a senha parecida com o nome passaria (AUTH-04)
        'OPTIONS': {'user_attributes': ('name', 'email')},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Compactação e cache para produção
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media Files (Uploads)
# Configuração para usar Cloudinary em produção ou se as chaves existirem
import cloudinary

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUD_NAME'),
    'API_KEY': os.getenv('API_KEY'),
    'API_SECRET': os.getenv('API_SECRET'),
}

if CLOUDINARY_STORAGE['CLOUD_NAME']:
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    # Configuração explícita para o CloudinaryField nos modelos
    cloudinary.config(
        cloud_name=CLOUDINARY_STORAGE['CLOUD_NAME'],
        api_key=CLOUDINARY_STORAGE['API_KEY'],
        api_secret=CLOUDINARY_STORAGE['API_SECRET'],
        secure=True
    )
    # Força o MEDIA_URL a apontar para a CDN do Cloudinary
    MEDIA_URL = f'https://res.cloudinary.com/{CLOUDINARY_STORAGE["CLOUD_NAME"]}/'
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'


# Django Rest Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # JWT com a sessão do token aberta (AD-037)
        'core.authentication.SessaoJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'EXCEPTION_HANDLER': 'core.exceptions.exception_handler',
    # Quantos proxies ficam na frente do app; o IP do cliente usado nos
    # limites de tentativas vem do X-Forwarded-For com base nesse número.
    'NUM_PROXIES': int(os.getenv('NUM_PROXIES', '1')),
}

# Sem a lista, nenhuma origem é liberada (AD-012)
CORS_ALLOWED_ORIGINS = [
    origem.strip()
    for origem in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
    if origem.strip()
]
CORS_ALLOW_ALL_ORIGINS = False

# Frontend URL used in transactional email links
FRONTEND_URL = obrigatoria_em_producao('FRONTEND_URL', 'http://localhost:3000')

# Contadores dos limites de tentativas, compartilhados entre os workers.
# A tabela é criada pelo `createcachetable` no entrypoint.sh.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'fluxar_cache',
    }
}

# Logs no console, para os registros de e-mail aparecerem no Render
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'api': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'core': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    # A rotação e a revogação ficam com api/sessoes.py (AD-037)
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')

# Email provider flags
USE_EMAILJS_TESTING_FALLBACK = os.getenv('USE_EMAILJS_TESTING_FALLBACK', 'False').lower() in ('1', 'true', 'yes', 'on')
ENABLE_RESEND_PROVIDER = os.getenv('ENABLE_RESEND_PROVIDER', 'True').lower() in ('1', 'true', 'yes', 'on')
ENABLE_SMTP_FALLBACK = os.getenv('ENABLE_SMTP_FALLBACK', 'True').lower() in ('1', 'true', 'yes', 'on')

# EmailJS credentials (test-only fallback)
EMAILJS_SERVICE_ID = os.getenv('EMAILJS_SERVICE_ID')
EMAILJS_TEMPLATE_ID = os.getenv('EMAILJS_TEMPLATE_ID')
EMAILJS_PUBLIC_KEY = os.getenv('EMAILJS_PUBLIC_KEY')
EMAILJS_PRIVATE_KEY = os.getenv('EMAILJS_PRIVATE_KEY')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
