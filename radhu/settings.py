import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-generate-a-random-one-or-use-this-for-now'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'stock',
    'accounts',
    'cycletube',
    'cycletyres',
    'tallysync',
    'hrms',
    'orders',
    'ai_agent',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'radhu.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'radhu.wsgi.application'

# Database Configuration (MySQL as primary, fallback to SQLite)
USE_MYSQL = os.environ.get('USE_MYSQL', 'false').lower() == 'true'

if USE_MYSQL:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'radhu_db'),
            'USER': os.environ.get('DB_USER', 'root'),
            'PASSWORD': os.environ.get('DB_PASSWORD', '123456'),
            'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'charset': 'utf8mb4',
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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/api/auth/login/'

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    'https://radhuerp.site',
    'https://www.radhuerp.site',
    'https://api.radhuerp.site',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https:\/\/.*\.vercel\.app$",
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'accounts.authentication.CsrfExemptSessionAuthentication',
    ],
}

SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False
CSRF_TRUSTED_ORIGINS = [
    'http://3.7.243.183',
    'https://3.7.243.183',
    'http://radhuerp.site',
    'https://radhuerp.site',
    'http://*.radhuerp.site',
    'https://*.radhuerp.site',
    'http://localhost:3000',
    'https://*.vercel.app',
]

TALLY_SYNC_API_KEY = 'fc2e1029465c118d144c93a093c0efd2cfa2d40a258c32c8'

JAZZMIN_SETTINGS = {
    "site_title": "Radhu ERP Admin",
    "site_header": "Radhu Industries",
    "site_brand": "RADHU INDUSTRIES",
    "welcome_sign": "Welcome to Radhu Industries ERP Admin",
    "copyright": "Radhu Industries Ltd",
    "search_model": ["stock.TyreItem", "cycletyres.CycleTyreItem", "cycletube.CycleTubeItem"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Frontend Live Portal", "url": "https://radhuerp.site", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user-shield",
        "auth.Group": "fas fa-users",
        "accounts.UserProfile": "fas fa-id-badge",
        "accounts.UserPagePermission": "fas fa-lock",
        
        "stock.TyreItem": "fas fa-car",
        "stock.DailyEntry": "fas fa-clipboard-list",
        "stock.DailyProductionManualEntry": "fas fa-industry",
        
        "cycletyres.CycleTyreItem": "fas fa-bicycle",
        "cycletyres.CycleTyreEntry": "fas fa-history",
        "cycletyres.CycleTyreDailyManualEntry": "fas fa-calculator",
        
        "cycletube.CycleTubeItem": "fas fa-ring",
        "cycletube.TubeEntry": "fas fa-clipboard-check",
        "cycletube.TubeDailyManualEntry": "fas fa-file-invoice",
        
        "orders.Order": "fas fa-shopping-cart",
        "orders.OrderItem": "fas fa-boxes",
        
        "hrms.Employee": "fas fa-user-tie",
        "hrms.Department": "fas fa-building",
        "hrms.Attendance": "fas fa-calendar-check",
        "hrms.PieceProduction": "fas fa-cogs",
        "hrms.Salary": "fas fa-money-bill-wave",
        
        "tallysync.TallyRawInvoice": "fas fa-receipt",
        "tallysync.TallyRawItem": "fas fa-barcode",
        "tallysync.TallyMapping": "fas fa-link",
        "tallysync.TallySyncLog": "fas fa-sync",
        "tallysync.TallySaleInvoice": "fas fa-file-invoice-dollar",
        "tallysync.TallySaleItem": "fas fa-list-ol",
        "ai_agent.AiAuditLog": "fas fa-history",
        "ai_agent.AiConfig": "fas fa-key",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-navy",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-navy",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "pulse",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}
