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
import eventlet
from urlparse import urlparse, urljoin
from flask import Flask, flash, g, redirect, url_for, request, session, Markup

# Import Green patched versions first
eventlet.import_patched('flaskext.cache')
eventlet.import_patched('flaskext.babel')
eventlet.import_patched('flaskext.mail')
# Now the usefull imports
from flaskext.cache import Cache
from flaskext.babel import Babel, gettext as _
from flaskext.mail import Mail
from ilog.common.signals import running, shutdown
from ilog.database import dbm
from ilog.web import defaults

log = logging.getLogger(__name__)

class Application(Flask):
    def __init__(self):
        Flask.__init__(self, 'ilog.web')
        self.config.from_object(defaults)
        running.connect(self.on_running_signal)

    def on_running_signal(self, emitter):
        try:
            sys.path.insert(0, os.getcwd())
            import ilogconfig
            log.info("Found \"ilogconfig.py\" on %s",
                     os.path.abspath(os.path.dirname(ilogconfig.__file__)))
            self.config.from_object(ilogconfig)
        except ImportError:
            log.info("No \"ilogconfig.py\" found. Using default configuration.")
        self.logger_name = '.'.join([__name__, 'SERVER'])

        dbm.native_unicode = self.config.get('SQLALCHEMY_NATIVE_UNICODE', True)
        dbm.record_queries = self.config.get('SQLALCHEMY_RECORD_QUERIES', False)
        dbm.pool_size = self.config.get('SQLALCHEMY_POLL_SIZE', 5)
        dbm.pool_timeout = self.config.get('SQLALCHEMY_POLL_TIMEOUT', 10)
        dbm.pool_recycle = self.config.get('SQLALCHEMY_POLL_RECYCLE', 3600)
        dbm.set_database_uri(self.config['SQLALCHEMY_DATABASE_URI'])

        mail.init_app(self)
        cache.init_app(self)

        if self.debug:
            # LessCSS Support
            eventlet.import_patched('flaskext.lesscss')
            from flaskext.lesscss import lesscss
            lesscss(self, self.config['LESSC_BIN_PATH'])

            eventlet.import_patched('werkzeug.debug')
            from werkzeug.debug import DebuggedApplication
            self.wsgi_app = DebuggedApplication(self.wsgi_app, True)

#            from flaskext.debugtoolbar import DebugToolbarExtension
#            self.debug_toolbar = DebugToolbarExtension(self)


            if 'SHOW_ILOG_CONFIG' in os.environ:
                from cStringIO import StringIO
                from pprint import pprint
                log_output = StringIO()
                current_config = self.config.copy()
                for key, val in current_config.iteritems():
                    if 'password' in key.lower() or 'secret' in key.lower():
                        current_config[key] = (val[0] + ('*'*(len(val)-2)) +
                                               val[-1])
                pprint(current_config, stream=log_output, indent=2)
                log_output.seek(0)
                log.trace("Current configuration:\n%s",
                          log_output.read().strip())
                del log_output, StringIO, pprint, current_config

        # Setup views
        from .views.main import main
        from .views.account import account
        self.register_module(main)
        self.register_module(account)

    def shutdown(self):
        log.info("ILog web Application shut down")
        shutdown.send(self, _waitall=True)



def redirect_to(*args, **kwargs):
    code = kwargs.pop('code', 302)
    return redirect(url_for(*args, **kwargs), code=code)

def get_redirect_target(invalid_targets=()):
    check_target = request.values.get('_redirect_target') or \
                   request.args.get('next') or \
                   session.get('_redirect_target', None) or \
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
    if not isinstance(invalid_targets, (tuple, list)):
        invalid_targets = [invalid_targets]
    for invalid in invalid_targets:
        if check_parts[:5] == urlparse(urljoin(app_url, invalid))[:5]:
            return

    return check_target


def redirect_back(*args, **kwargs):
    """Redirect back to the page we are comming from or the URL rule given.
    """
    code = kwargs.pop('code', 302)
    target = get_redirect_target(kwargs.pop('invalid_targets', ()))
    if target is None:
        target = url_for(*args, **kwargs)
    return redirect(target, code=code)


app = Application()

config = app.config
mail = Mail(app)
cache = Cache(app)
babel = Babel(app, default_locale='en', default_timezone='UTC',
              date_formats=None, configure_jinja=True)

@babel.localeselector
def get_locale():
    # if a user is logged in, use the locale from the user settings
    identity = getattr(g, 'identity', None)
    if identity is not None and identity.name != 'anon':
        account = getattr(identity, 'account', None)
        if account:
            return account.locale
    # otherwise try to guess the language from the user accept
    # header the browser transmits.  We support de/fr/en in this
    # example.  The best match wins.
    return request.accept_languages.best_match([
        l.language for l in babel.list_translations()
    ])


@babel.timezoneselector
def get_timezone():
    identity = getattr(g, 'identity', None)
    if identity is not None and identity.name != 'anon':
        account = getattr(identity, 'account', None)
        if account:
            return account.timezone
    return 'UTC'

@app.errorhandler(401)
def on_401(error):
    flash(_("You have not signed in yet."), "error")
    return redirect_to('account.signin', code=307)


# Account Navigation building
@app.context_processor
def build_account_nav():
    from .permissions import admin_permission
    ctxnav = []
    if not g.identity.account:
        ctxnav.append((url_for('account.signin'), _("Sign-In"), "first"))
        ctxnav.append((url_for('account.register'), _("Register"), None))
    else:
        ctxnav.append((url_for('account.signout'), _("Sign-Out"), "first"))
        ctxnav.append((url_for('account.profile'), _("My Profile"), None))

    if g.identity.can(admin_permission):
        ctxnav.append((url_for('account.signin'), _("Administration"), None))
    return dict(ctxnav=tuple(ctxnav))

@app.context_processor
def account_related_actions():
    account = g.identity.account
    if account is None:
        profile_photo = None
    else:
        @cache.memoize(3600)
        def build_invalid_paths():
            return (url_for('account.register'),
                    url_for('account.resend_activation_email'))

        if not account.confirmed and request.path not in build_invalid_paths():
            message = Markup("You're account is not yet verified! "
                             "<a href=\"%s\">Resend confirmation email</a>." %
                             url_for('account.resend_activation_email'))
            flash(message, "error")

        profile_photo = account.profile_photos.filter_by(preferred=True).first()

    return dict(profile_photo=profile_photo)

#@app.context_processor
@app.after_request
def store_redirect_target(response):
    redirect_target = get_redirect_target(session.get('_redirect_target', ()))
    if redirect_target is not None:
        session['_redirect_target'] = redirect_target
    return response


#@app.before_request
#def before_request():
#    from flask import flash
#    flash("Foo error", "error")
#    flash("Foo Ok", "ok")
#    flash("Foo info", "info")
#    flash("Foo message", "message")
#    flash("Foo Config", "config")
#    flash("Foo add", "add")
#    flash("Foo remove", "remove")
