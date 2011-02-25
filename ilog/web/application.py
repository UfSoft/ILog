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
from flask.signals import request_started, request_finished

# Import Green patched versions first
eventlet.import_patched('flaskext.cache')
eventlet.import_patched('flaskext.babel')
eventlet.import_patched('flaskext.mail')
# Now the usefull imports
from flaskext.cache import Cache
from flaskext.babel import Babel, gettext as _
from ilog.common.signals import running, shutdown
from ilog.database import dbm
from ilog.web import defaults
from .signals import webapp_setup_complete, webapp_shutdown, ctxnav_build, nav_build
from .mail import mail

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

        theme_name = self.config.get("THEME_NAME", None)
        if theme_name not in ("redmond", "smoothness"):
            raise RuntimeError("Theme \"%s\" not supported" % theme_name)

        dbm.native_unicode = self.config.get('SQLALCHEMY_NATIVE_UNICODE', True)
        dbm.record_queries = self.config.get('SQLALCHEMY_RECORD_QUERIES', False)
        dbm.pool_size = self.config.get('SQLALCHEMY_POLL_SIZE', 5)
        dbm.pool_timeout = self.config.get('SQLALCHEMY_POLL_TIMEOUT', 10)
        dbm.pool_recycle = self.config.get('SQLALCHEMY_POLL_RECYCLE', 3600)
        dbm.set_database_uri(self.config['SQLALCHEMY_DATABASE_URI'])

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
        from .views.admin import admin
        from .views.admin.accounts import accounts
        from .views.admin.channels import channels
        from .views.admin.networks import networks
        self.register_module(main)
        self.register_module(account)
        self.register_module(admin)
        self.register_module(accounts)
        self.register_module(channels)
        self.register_module(networks)

        # WebApp setup is complete. Signal it.
        eventlet.sleep(0.5)
        webapp_setup_complete.send(self)

    def shutdown(self):
        log.info("ILog web Application shut down")
#        webapp_shutdown.send(self, _waitall=True)
#        shutdown.send(self, _waitall=True)
        webapp_shutdown.send(self)
        shutdown.send(self)



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

@app.errorhandler(403)
def on_403(error):
    flash(_("You don't the required permissions."), "error")
    return redirect_to('main.index', code=307)


# Account Navigation building
@app.context_processor
def process_context():
    from .permissions import admin_permission, admin_or_manager_permission
    account_nav = []
    if g.identity.account is None:
        profile_photo = None
        account_nav.append((url_for('account.signin'), _("Sign-In"), "first"))
        account_nav.append((url_for('account.register'), _("Register"), None))
    else:
        account_nav.append((url_for('account.signout'), _("Sign-Out"), "first"))
        account_nav.append((url_for('account.profile'), _("My Profile"), None))

        if not g.identity.account.confirmed and not \
                                session.get('_skip_verified_warning', False):
            message = Markup("You're account is not yet verified! "
                             "<a href=\"%s\">Resend confirmation email</a>." %
                             url_for('account.resend_activation_email'))
            flash(message, "error")

        profile_photo = g.identity.account.profile_photos.filter_by(
                                                        preferred=True).first()

    if g.identity.can(admin_or_manager_permission):
        account_nav.append(
            (url_for('admin.dashboard'), _("Administration"), None)
        )

    @cache.memoize(3600)
    def construct_nav(module=None, identity_name="anon", url_path=None):
        participant_results = []
        for participant, nav_entry in nav_build.send(module):
            if isinstance(nav_entry, eventlet.greenthread.GreenThread):
                nav_entry = nav_entry.wait()
            elif not nav_entry:
                continue
            for prio, endpoint, name, partial in nav_entry:
                participant_results.append((prio, name, endpoint, partial))
        for (prio, name, endpoint, partial) in sorted(participant_results):
            url = url_for(endpoint)
            if request.path==url or (partial and request.path.startswith(url)):
                yield url, name, "active"
            else:
                yield url, name, "inactive"

    @cache.memoize(3600)
    def construct_ctxnav(module=None, identity_name="anon", url_path=None):
        participant_results = []
        for participant, nav_entry in ctxnav_build.send(module):
            if isinstance(nav_entry, eventlet.greenthread.GreenThread):
                nav_entry = nav_entry.wait()
            elif not nav_entry:
                continue
            for prio, endpoint, name, partial in nav_entry:
                participant_results.append((prio, name, endpoint, partial))
        for (prio, name, endpoint, partial) in sorted(participant_results):
            url = url_for(endpoint)
            if request.path==url or (partial and request.path.startswith(url)):
                yield url, name, "active"
            else:
                yield url, name, "inactive"

    return dict(
        theme_name = app.config.get("THEME_NAME", 'smoothness'),
        account_nav=tuple(account_nav),
        profile_photo=profile_photo,
        request_path=request.path,
        nav=construct_nav(
            app.modules[request.module], g.identity.name, request.path
        ),
        ctxnav=construct_ctxnav(
            app.modules[request.module], g.identity.name, request.path
        ),
    )

@app.context_processor
def account_related_actions():
    account = g.identity.account
    if account is None:
        profile_photo = None
    else:
        if not account.confirmed and not \
                                session.get('_skip_verified_warning', False):
            message = Markup("You're account is not yet verified! "
                             "<a href=\"%s\">Resend confirmation email</a>." %
                             url_for('account.resend_activation_email'))
            flash(message, "error")

        profile_photo = account.profile_photos.filter_by(preferred=True).first()

    return dict(profile_photo=profile_photo)

@app.context_processor
def get_total_events():
    @cache.cached(timeout=10, key_prefix='total_irc_events')
    def get_total_events_from_db():
        from ilog.database.models import IRCEvent
        return IRCEvent.query.count()

    @cache.cached(timeout=10, key_prefix='total_irc_channels')
    def get_total_channels_from_db():
        from ilog.database.models import Channel
        return Channel.query.count()

    @cache.cached(timeout=10, key_prefix='total_irc_networks')
    def get_total_netwokrs_from_db():
        from ilog.database.models import Network
        return Network.query.count()

    return dict(total_events_logged=get_total_events_from_db(),
                total_channels_logged=get_total_channels_from_db(),
                total_networks_logged=get_total_netwokrs_from_db())

@request_started.connect_via(app)
def on_request_started(app):
    if request.path.startswith(app.static_path):
        return

    @cache.cached(timeout=3600, key_prefix='no_warning_urls')
    def build_no_warning_urls():
        return (
            url_for('account.register'),
            url_for('account.resend_activation_email')
        )

    if request.path in build_no_warning_urls():
        session['_skip_verified_warning'] = True


    redirect_target = get_redirect_target(session.pop('_redirect_target', ()))
    if redirect_target is not None:
        session['_redirect_target'] = redirect_target


@request_finished.connect_via(app)
def on_request_finished(app, response):
    if request.path.startswith(app.static_path):
        return

    if response.status_code not in range(300+1, 307+1):
        skip_verified_warning = session.pop('_skip_verified_warning', None)
        if skip_verified_warning:
            app.save_session(session, response)

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
