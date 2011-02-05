# -*- coding: utf-8 -*-
"""
    ilog.web.application
    ~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import os
import sys
import logging
from urlparse import urlparse, urljoin
from flask import Flask, redirect, url_for, request
from flask.ctx import _RequestContext as _RequestContextBase
from flask.globals import _lookup_object, LocalProxy, partial
from flaskext.cache import Cache
from flaskext.babel import Babel
from flaskext.principal import Principal
from giblets import ComponentManager
from ilog.common.signals import daemonized, shutdown
from ilog.database import DatabaseManager
from ilog.web import defaults

log = logging.getLogger(__name__)

#babel = LocalProxy(partial(_lookup_object, 'babel'))
#cache = LocalProxy(partial(_lookup_object, 'cache'))
#config = LocalProxy(partial(_lookup_object, 'config'))
#dbm = LocalProxy(partial(_lookup_object, 'dbm'))
#principal = LocalProxy(partial(_lookup_object, 'principal'))
#
#class _RequestContext(_RequestContextBase):
#    def __init__(self, app, environ):
#        _RequestContextBase.__init__(self, app, environ)
#        self.babel = app.babel
#        self.cache = app.cache
#        self.config = app.config
#        self.dbm = app.dbm
#        self.principal = app.principal

class Application(Flask):
    def __init__(self):
        Flask.__init__(self, 'ilog.web')
#        self.component_manager = ComponentManager()
#        self.dbm = DatabaseManager(self.component_manager)
#        self.dbm.activate()
#        self.dbm.connect_signals()
        self.config.from_object(defaults)
        daemonized.connect(self.on_daemonized_signal)

#    def request_context(self, environ):
##        ctx = Flask.request_context(self, environ)
##        ctx.babel = self.babel
##        ctx.cache = self.cache
##        ctx.dbm = self.dbm
##        ctx.principal = self.principal
#        return _RequestContext(self, environ)

    def on_daemonized_signal(self, emitter):
        try:
            sys.path.insert(0, os.getcwd())
            import ilogconfig
            log.info("Found \"ilogconfig.py\" on %s",
                     os.path.abspath(os.path.dirname(ilogconfig.__file__)))
            self.config.from_object(ilogconfig)
        except ImportError:
            log.info("No \"ilogconfig.py\" found. Using default configuration.")
        self.logger_name = '.'.join([__name__, 'SERVER'])

#        self.dbm.set_database_uri(self.config['SQLALCHEMY_DATABASE_URI'])
        dbm.set_database_uri(self.config['SQLALCHEMY_DATABASE_URI'])

#        self.cache = Cache(self)
#        self.babel = Babel(self, default_locale='en', default_timezone='UTC',
#                           date_formats=None, configure_jinja=True)
#        self.principal = Principal(self, use_sessions=True)
#
        if self.debug:
            # LessCSS Support
            import eventlet
            eventlet.import_patched('flaskext.lesscss')
            from flaskext.lesscss import lesscss
            lesscss(self, self.config['LESSC_BIN_PATH'])

            from werkzeug.debug import DebuggedApplication
            self.wsgi_app = DebuggedApplication(self.wsgi_app, True)

        # Setup views
        from .views.main import main
        from .views.account import account
        self.register_module(main)
        self.register_module(account)

    def shutdown(self):
        log.info("ILog web Application shut down")
        shutdown.send(self, _waitall=True)


def redirect_to(*args, **kwargs):
    return redirect(url_for(*args, **kwargs))

def get_redirect_target(invalid_targets=()):
    check_target = request.values.get('_redirect_target') or \
                   request.args.get('next') or \
                   request.environ.get('HTTP_REFERER')

    # if there is no information in either the form data
    # or the wsgi environment about a jump target we have
    # to use the target url
    if not check_target:
        return

    # otherwise drop the leading slash
    app_url = url_for('main.index', _external=True)
    url_parts = urlparse(app_url)
    check_parts = urlparse(urljoin(app_url, check_target))

    # if the jump target is on a different server we probably have
    # a security problem and better try to use the target url.
    if url_parts[:2] != check_parts[:2]:
        return

    # if the jump url is the same url as the current url we've had
    # a bad redirect before and use the target url to not create a
    # infinite redirect.
    current_parts = urlparse(urljoin(app_url, request.path))
    if check_parts[:5] == current_parts[:5]:
        return

    # if the `check_target` is one of the invalid targets we also fall back.
    for invalid in invalid_targets:
        if check_parts[:5] == urlparse(urljoin(app_url, invalid))[:5]:
            return

    return check_target


def redirect_back(*args, **kwargs):
    """Redirect back to the page we are comming from or the URL rule given.
    """
    target = get_redirect_target()
    if target is None:
        target = url_for(*args, **kwargs)
    return redirect(target)


app = Application()
component_manager = ComponentManager()
dbm = DatabaseManager(component_manager)
dbm.activate()
dbm.connect_signals()

config = app.config
cache = Cache(app)
babel = Babel(app, default_locale='en', default_timezone='UTC',
              date_formats=None, configure_jinja=True)

