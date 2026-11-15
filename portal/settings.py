"""Einstellungen des Vereinsportals.

Alles Betriebsrelevante kommt aus Umgebungsvariablen mit dem Präfix ``PORTAL_`` (siehe docs/betrieb.md).
Ohne Variablen startet eine lokale Entwicklungsumgebung (DEBUG, SQLite unter ./data, Mails auf der Konsole).
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(f"PORTAL_{name}")
    return value if value not in (None, "") else default


def env_bool(name: str, default: bool) -> bool:
    value = env(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "ja"}


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in (env(name, default) or "").split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(env("DATA_DIR", str(BASE_DIR / "data")) or "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEBUG = env_bool("DEBUG", False)
SECRET_KEY = env("SECRET_KEY") or ("dev-only-secret-key" if DEBUG else None)
if not SECRET_KEY:
    raise ImproperlyConfigured("PORTAL_SECRET_KEY muss gesetzt sein (oder PORTAL_DEBUG=true für die Entwicklung).")

# Öffentliche Adresse, z. B. https://judo.tlandsberger.de – für Links in Mails und CSRF.
BASE_URL = (env("BASE_URL", "http://localhost:8000") or "").rstrip("/")
# Version des Images, gesetzt vom Release-Workflow (Build-Argument VERSION); lokal und in der CI „dev“.
VERSION = (env("VERSION", "dev") or "dev").removeprefix("v")
RELEASES_URL = "https://github.com/tlandsberger/judo-portal/releases"
# localhost bleibt immer erlaubt: Der Docker-Healthcheck ruft http://127.0.0.1:8000/healthz auf.
ALLOWED_HOSTS = [*env_list("ALLOWED_HOSTS", ""), "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = [BASE_URL]

INSTALLED_APPS = [
    "portal.core",
    "portal.accounts",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.usersessions",
    "django.forms",
    "django_htmx",
]

MIDDLEWARE = [
    "portal.core.middleware.ClientIPMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "allauth.usersessions.middleware.UserSessionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "portal.accounts.middleware.SetupSessionMiddleware",
    "portal.accounts.middleware.SlidingSessionMiddleware",
]

ROOT_URLCONF = "portal.urls"
WSGI_APPLICATION = "portal.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "portal" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "portal.core.context_processors.portal",
            ],
        },
    }
]

# SQLite im Datenverzeichnis (Volume). WAL erlaubt Lesen während des Schreibens, IMMEDIATE vermeidet
# „database is locked“ bei gleichzeitigen Schreibzugriffen.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "portal.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 10,
            "init_command": (
                "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;PRAGMA foreign_keys=ON;PRAGMA busy_timeout=10000;"
            ),
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_KEEP_DAYS = int(env("BACKUP_KEEP_DAYS", "14") or 14)
BACKUP_HOUR = int(env("BACKUP_HOUR", "2") or 2)

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "home"

# Sitzungen liegen in der Datenbank; der Browser hält nur die Sitzungs-ID (HttpOnly, Secure, SameSite).
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60  # „Angemeldet bleiben“: 30 Tage, verlängert sich bei Nutzung
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_COOKIES = env_bool("SECURE_COOKIES", not DEBUG)
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_NAME = "wtsv_session"
CSRF_COOKIE_NAME = "wtsv_csrftoken"

# Hinter Traefik/Cloudflare: HTTPS und Host aus den Proxy-Headern übernehmen.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Proxys, deren X-Forwarded-For für die echte Client-IP übernommen wird.
TRUSTED_PROXIES = env_list("TRUSTED_PROXIES", "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,::1/128,fc00::/7")
USE_X_FORWARDED_HOST = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 365 * 24 * 60 * 60 if SECURE_COOKIES else 0
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Content Security Policy: nur eigene Quellen, Skripte zusätzlich per Nonce (Theme-Umschaltung vor dem Rendern).
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "manifest-src": [CSP.SELF],
    "worker-src": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "object-src": [CSP.NONE],
}

LANGUAGE_CODE = "de"
LANGUAGES = [("de", "Deutsch")]
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
# Eigene Übersetzungen (vor allem für allauth: Du-Form, „Zugang“ statt „Konto“); gelten vor denen der Pakete.
LOCALE_PATHS = [BASE_DIR / "portal" / "locale"]
USE_TZ = True

# Formulare und Widgets mit DaisyUI-Klassen aus portal/templates/django/forms/ (ADR 0008)
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "portal" / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# Mail: SMTP (IONOS) in Produktion; ohne Host auf die Konsole bzw. in Dateien (Tests, E2E).
DEFAULT_FROM_EMAIL = env("EMAIL_FROM", "Wedeler TSV Judo <portal@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = "[Wedeler TSV Judo] "
if env("EMAIL_HOST"):
    _mailer = {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": env("EMAIL_HOST"),
            "port": int(env("EMAIL_PORT", "587") or 587),
            "username": env("EMAIL_USER", ""),
            "password": env("EMAIL_PASSWORD", ""),
            "use_tls": env_bool("EMAIL_USE_TLS", True),
            "timeout": 20,
        },
    }
elif env("EMAIL_FILE_PATH"):
    _mailer = {
        "BACKEND": "django.core.mail.backends.filebased.EmailBackend",
        "OPTIONS": {"file_path": env("EMAIL_FILE_PATH")},
    }
else:
    _mailer = {"BACKEND": "django.core.mail.backends.console.EmailBackend"}
MAILERS = {"default": _mailer}

INITIAL_ADMIN_EMAIL = env("INITIAL_ADMIN_EMAIL")
INVITATION_DAYS = 7

# allauth: Anmeldung per E-Mail mit Passkey, Passwort oder Code; keine Selbstregistrierung (nur Einladung).
ACCOUNT_ADAPTER = "portal.accounts.adapter.PortalAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"  # Adressen sind durch die Einladung bestätigt
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 15 * 60
ACCOUNT_LOGIN_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_SESSION_REMEMBER = None  # Kästchen „Angemeldet bleiben“
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_RATE_LIMITS = {
    "login_failed": "10/m/ip,5/5m/key",
    "confirm_email": "1/3m/key",
    "reset_password": "20/m/ip,5/m/key",
}
ACCOUNT_EMAIL_SUBJECT_PREFIX = EMAIL_SUBJECT_PREFIX
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https" if SECURE_COOKIES else "http"
USERSESSIONS_TRACK_ACTIVITY = True  # „Meine Anmeldung“ zeigt angemeldete Geräte mit letzter Nutzung
MFA_SUPPORTED_TYPES = ["webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = DEBUG or env_bool("WEBAUTHN_ALLOW_INSECURE_ORIGIN", False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
