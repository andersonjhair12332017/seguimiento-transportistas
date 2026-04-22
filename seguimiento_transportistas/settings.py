"""
Django settings for seguimiento_transportistas project.
"""

import os
from pathlib import Path

# -------------------------------------------------------------------
# RUTAS BASE
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------
# SEGURIDAD BÁSICA
# -------------------------------------------------------------------
# En local usa este valor por defecto.
# En Azure debes definir SECRET_KEY como variable de entorno.
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-insegura-solo-local-cambia-esto-en-azure-1234567890"
)

# En local puede ir True.
# En Azure / producción debe ir False.
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Hosts permitidos.
# En local funciona con 127.0.0.1 y localhost.
# En Azure debes poner tu dominio o azurewebsites.net
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost"
    ).split(",")
    if host.strip()
]

# Orígenes confiables para CSRF.
# En Azure debes agregar tu dominio HTTPS.
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]

# URL pública base (la usarás luego para los QR en Azure)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

# -------------------------------------------------------------------
# APPS
# -------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'operaciones',
]

# -------------------------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Si luego instalas whitenoise, deja esta línea activa:
    # 'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'seguimiento_transportistas.urls'

# -------------------------------------------------------------------
# TEMPLATES
# -------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.debug',
                'django.template.context_processors.media',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'seguimiento_transportistas.wsgi.application'

# -------------------------------------------------------------------
# BASE DE DATOS
# -------------------------------------------------------------------
# Si existe DBHOST, usa PostgreSQL (Azure)
# Si NO existe DBHOST, usa SQLite local
if os.getenv("DBHOST"):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DBNAME', 'seguimiento'),
            'USER': os.getenv('DBUSER', 'postgres'),
            'PASSWORD': os.getenv('DBPASS', ''),
            'HOST': os.getenv('DBHOST', 'localhost'),
            'PORT': os.getenv('DBPORT', '5432'),
            'OPTIONS': {
                'sslmode': 'require'
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# -------------------------------------------------------------------
# VALIDACIÓN DE CONTRASEÑAS
# -------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
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

# -------------------------------------------------------------------
# INTERNACIONALIZACIÓN
# -------------------------------------------------------------------
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA
# -------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Si luego instalas whitenoise, puedes activar esto:
# STORAGES = {
#     "default": {
#         "BACKEND": "django.core.files.storage.FileSystemStorage",
#     },
#     "staticfiles": {
#         "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
#     },
# }

# -------------------------------------------------------------------
# LOGIN / LOGOUT
# -------------------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'lista'
LOGOUT_REDIRECT_URL = 'login'

# -------------------------------------------------------------------
# SEGURIDAD PARA AZURE / PRODUCCIÓN
# -------------------------------------------------------------------
# Déjalas en False/0 localmente.
# En Azure las pondrás con variables de entorno.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "False").lower() == "true"

SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "False"
).lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "False").lower() == "true"

# Azure normalmente va detrás de proxy HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# -------------------------------------------------------------------
# CONFIGURACIÓN POR DEFECTO DE PK
# -------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'