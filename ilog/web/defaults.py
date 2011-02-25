# -*- coding: utf-8 -*-
"""
    ilog.web.defaults
    ~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from os import path
from datetime import timedelta

# Built-in settings
DEBUG = False    # enable/disable debug mode
TESTING = False # enable/disable testing mode
SECRET_KEY = 'not_secret_should_be_changed'
SESSION_COOKIE_NAME = 'EvAFM'
PERMANENT_SESSION_LIFETIME = timedelta(days=30)
USE_X_SENDFILE = False  # enable/disable x-sendfile
LOGGER_NAME = 'ilog.webserver'
#SERVER_NAME = 'lgl.localhost'   # the name of the server. Required for subdomain support
#SERVER_NAME = ''   # the name of the server. Required for subdomain support
MAX_CONTENT_LENGTH = 8388608   # 8 MiB
THEME_NAME = 'redmond'


# I18N Support
BABEL_DEFAULT_LOCALE = 'en'
BABEL_DEFAULT_TIMEZONE = 'UTC'

# Cache settings
CACHE_TYPE='null'
CACHE_ARGS=''
CACHE_OPTIONS=''
CACHE_DEFAULT_TIMEOUT=3600  # One hour
CACHE_KEY_PREFIX='ilog_'
CACHE_MEMCACHED_SERVERS=''


# Former RPXNow, now Janrain Settings
JANRAIN_API_KEY = ''
JANRAIN_APP_DOMAIN = ''

# Email settings
MAIL_SERVER=''
MAIL_PORT=25
MAIL_USE_TLS=False
MAIL_USE_SSL=False
MAIL_DEBUG=False
MAIL_USERNAME=''
MAIL_PASSWORD=''
DEFAULT_MAIL_SENDER=''
MAIL_SUPPRESS_SEND=False
MAIL_FAIL_SILENTLY=True
DEFAULT_MAX_EMAILS=None

# Database Settings
SQLALCHEMY_DATABASE_URI = None
SQLALCHEMY_RECORD_QUERIES = False
SQLALCHEMY_NATIVE_UNICODE = False
SQLALCHEMY_POOL_SIZE = 5
SQLALCHEMY_POOL_TIMEOUT = 10
SQLALCHEMY_POOL_RECYCLE = 3600

# WTForms Settings
CSRF_ENABLED=True
CSRF_SESSION_KEY='_csrf_token'
RECAPTCHA_USE_SSL=False
RECAPTCHA_PUBLIC_KEY=''
RECAPTCHA_PRIVATE_KEY=''
RECAPTCHA_OPTIONS={}

# LESSCSS
LESSC_BIN_PATH="/var/lib/gems/1.8/bin/lessc"

del path, timedelta
