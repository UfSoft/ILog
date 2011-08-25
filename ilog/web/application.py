# -*- coding: utf-8 -*-
"""
    ilog.web.application
    ~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import os
import logging
from urlparse import urlparse, urljoin
from flask import Flask, flash, g, redirect, url_for, request, session, Markup
from flask.signals import request_started, request_finished

# Now the useful imports
from flaskext import menubuilder
from flaskext.cache import Cache
from flaskext.babel import Babel, gettext as _
from ilog.common.signals import running, shutdown
from ilog.database import dbm, signals
from ilog.web import defaults
from .signals import webapp_setup_complete, webapp_shutdown, after_identity_account_loaded
from .mail import mail

log = logging.getLogger(__name__)

class Application(Flask):
    def __init__(self):
        Flask.__init__(self, 'ilog.web')
        self.config.from_object(defaults)
        running.connect(self.on_running_signal)
        signals.database_upgraded.connect(self.on_database_upgraded)

    def on_running_signal(self, daemon):
        log.trace("Got running signal")
        self.config.root_path = daemon.working_directory
        custom_config_file_name = "ilogwebconfig.py"
        try:
            custom_config_file = os.path.join(
                os.path.abspath(self.config.root_path), custom_config_file_name
            )

            if os.path.isfile(custom_config_file):
                self.config.from_pyfile(custom_config_file)
                log.info("Loaded custom configuration from %r",
                         custom_config_file)
            else:
                log.info("%s not found", custom_config_file)
        except IOError:
            log.info("No %r found. Using default configuration.",
                     custom_config_file_name)
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
            from flaskext.lesscss import lesscss
            lesscss(self, self.config['LESSC_BIN_PATH'])

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
        self.register_blueprint(main)
        self.register_blueprint(account)
        self.register_blueprint(admin)
        self.register_blueprint(accounts)
        self.register_blueprint(channels)
        self.register_blueprint(networks)

        from ilog.web.utils.jinjafilters import format_irc_message
        self.jinja_env.filters['ircformat'] = format_irc_message

    def on_database_upgraded(self, emitter):
        # WebApp setup is complete. Signal it.
        webapp_setup_complete.send(self)

    def shutdown(self):
        log.info("ILog web Application shut down")
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
    """Redirect back to the page we are coming from or the URL rule given.
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
menus = menubuilder.MenuBuilder(app)

@babel.localeselector
def get_locale():
    # if a user is logged in, use the locale from the user settings
    if len(babel.list_translations()) == 1:
        return babel.list_translations()[0].language
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
    flash(_("You don't have the required permissions."), "error")
    return redirect_back('main.index', code=307)


def check_wether_account_is_none(menu_item):
    return g.identity.account is None

def check_wether_account_is_not_none(menu_item):
    return g.identity.account is not None

menus.add_menu_entry(
    "account_nav", _("Sign-In"), 'account.signin', priority=-1,
    classes="first", li_classes="first",
    visiblewhen=check_wether_account_is_none
)
menus.add_menu_entry(
    "account_nav", _("Register"), 'account.register',
    visiblewhen=check_wether_account_is_none
)

menus.add_menu_entry(
    "account_nav", _("Sign-Out"), 'account.signout', priority=-1,
    classes="first", li_classes="first",
    visiblewhen=check_wether_account_is_not_none
)
menus.add_menu_entry(
    "account_nav", _("My Profile"), 'account.profile',
    visiblewhen=check_wether_account_is_not_none
)
def check_for_admin_or_manager_permission(menu_item):
    from .permissions import admin_or_manager_permission
    return g.identity.can(admin_or_manager_permission)

menus.add_menu_entry(
    "account_nav", _("Administration"), 'admin.dashboard', priority=10,
    visiblewhen=check_for_admin_or_manager_permission
)

def generate_profile_photo_content(menu_item):
    if g.identity.account is not None:
        profile_photo = g.identity.account.profile_photos.filter_by(preferred=True).first()
        if not profile_photo:
            return
        return '<img width="22" height="22" src="%s">' % profile_photo.url
    return

profile_photo_menuitem = menubuilder.MenuItemContent(
    generate_profile_photo_content, priority=-2,
    activewhen=menubuilder.ANYTIME,
    visiblewhen=lambda mi: g.identity.account is not None,
    li_classes="first", classes="first", builder=menus.builder,
    is_link=False
)
menus.add_menu_item('account_nav', profile_photo_menuitem)

@app.context_processor
def theme_name_in_jinja_context():
    return dict(theme_name = app.config.get("THEME_NAME", 'redmond'))
#    theme = request.args.get('theme', app.config.get("THEME_NAME", 'redmond'))
#    return dict(theme_name = theme)

@after_identity_account_loaded.connect_via(app)
def account_related_actions(sender, account=None):
    if account and session.get('_skip_verified_warning', False):
        if not account.confirmed:
            message = Markup(_(
                "You're account is not yet verified! "
                "<a href=\"%(url)s\">Resend confirmation email</a>.",
                url=url_for('account.emails.notify')
            ))
            flash(message, "error")
        else:
            for email in account.get_unverified_addresses():
                message = Markup(_(
                    "Your email address \"%(address)s\" is not yet verified! "
                    "<a href=\"%(href)s\">Resend confirmation email</a>.",
                    address=email.address,
                    href=url_for('account.emails.notify')
                ))
                flash(message, "warn")

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
    if request.path.startswith(app.static_url_path):
        return

    @cache.cached(timeout=3600, key_prefix='no_warning_urls')
    def build_no_warning_urls():
        return (
            url_for('account.register'),
            url_for('account.activate', hash=''),
            url_for('account.emails.notify')
        )

    for url in build_no_warning_urls():
        if request.path == url or request.path.startswith(url):
            session['_skip_verified_warning'] = session.modified = True
            break

    redirect_target = get_redirect_target(session.pop('_redirect_target', ()))
    if redirect_target is not None:
        session['_redirect_target'] = redirect_target


@request_finished.connect_via(app)
def on_request_finished(app, response):
    if request.path.startswith(app.static_url_path):
        return

    if response.status_code not in range(300+1, 307+1):
        skip_verified_warning = session.pop('_skip_verified_warning', None)
        if skip_verified_warning:
            app.save_session(session, response)
