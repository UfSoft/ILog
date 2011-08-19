# -*- coding: utf-8 -*-
"""
    ilog.web.views.account
    ~~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
import gevent
import simplejson
import urllib
import urllib2
from flask import Blueprint, url_for, g, flash, request, session, render_template
from flaskext import menubuilder
from flaskext.babel import gettext as _
from flaskext.principal import AnonymousIdentity, Identity, identity_changed
from ilog.database import dbm
from ilog.database.models import (Account, AccountProvider, EMailAddress,
                                  ActivationKey, ProfilePhoto)
from ilog.web.application import app, config, menus, redirect_to, redirect_back
from ilog.web.forms import (DeleteAccountForm, LoginForm, RegisterForm,
                            ProfileForm, ExtraEmailForm)
from ilog.web.mail import mail, Message
from ilog.web.permissions import authenticated_permission
from ilog.web.signals import ctxnav_build, nav_build

log = logging.getLogger(__name__)

account = Blueprint("account", __name__, url_prefix='/account')

def check_wether_account_is_not_none(menu_item):
    return g.identity.account is not None and request.blueprint=='account'

def request_endpoint_startswith_accounts(menu_item):
    return request.blueprint=='account' and request.endpoint.startswith('account.')

menus.add_menu_entry(
    'nav', _("My Profile"), 'account.profile',
    activewhen=request_endpoint_startswith_accounts,
    visiblewhen=check_wether_account_is_not_none
)

menus.add_menu_entry(
    'ctxnav', _("Profile Details"), 'account.profile',
    visiblewhen=check_wether_account_is_not_none
)

menus.add_menu_entry(
    'ctxnav', _("Date & Time Formats"), 'account.formats', priority=2,
    visiblewhen=check_wether_account_is_not_none
)
menus.add_menu_entry(
    'ctxnav', _("Profile Photos"), 'account.photos', priority=2,
    visiblewhen=check_wether_account_is_not_none
)

#
#@ctxnav_build.connect_via(account)
#def on_networks_ctxnav_build(emitter):
#    return (
#        # prio, endpoint, name, partial also macthes
#        (1, 'account.profile', _("Profile Details"), False),
#        (2, 'account.formats', _("Date & Time Formats"), False),
#        (2, 'account.photos', _("Profile Photos"), False),
#    )

@account.route('/signin', methods=("GET", "POST"))
def signin():
    if g.identity.account is not None:
        flash("You're already authenticated!", "info")
        return redirect_back("account.profile")

    form=LoginForm(formdata=request.values.copy())
    token_url = url_for('account.rpx', _external=True)
    app_domain = config.get('JANRAIN_APP_DOMAIN', None)

    if form.validate_on_submit():
        account = Account.query.by_username(request.values.get('username', ''))
        session['uid'] = account.id
        session.permanent = request.values.get('remember_me', 'n')=='y'
        identity_changed.send(app, identity=Identity(account.id, "dbm"))
        flash(_("Welcome back %(display_name)s!",
                display_name=account.display_name))
        return redirect_back("account.profile",
                             invalid_targets=url_for('account.signin'))

    return render_template('account/login.html', token_url=token_url,
                           app_domain=app_domain, form=form)

@account.route('/signout')
@authenticated_permission.require(403)
def signout():
    session.clear()
    identity_changed.send(app, identity=AnonymousIdentity())
    return redirect_back('main.index',
                         invalid_targets=url_for('account.profile'))

@account.route('/rpx', methods=('POST',))
def rpx():
    token = request.values.get('token')
    params = urllib.urlencode({
        'token': token,
        'apiKey': app.config['JANRAIN_API_KEY'],
        'format': 'json'
    })

    http_response = urllib2.urlopen('https://rpxnow.com/api/v2/auth_info', params)
    auth_info = simplejson.loads(http_response.read())

    del http_response

    if auth_info['stat'] != 'ok':
        return None

    profile = auth_info['profile']
    if not profile:
        flash(_("Something went wrong signing-in with your other account. "
                "Please try again."), "error")
        return redirect_to("account.signin")

    identifier = profile['identifier']
    provider = AccountProvider.query.get(identifier)
    if not provider:
        session['rpx_profile'] = profile
        session.modified = True
        flash(_("Welcome to ILog please confirm your details and "
                "create your account!"))
        return redirect_to("account.register")

    identity_changed.send(app, identity=Identity(provider.account.id, "dbm"))

    flash(_("Welcome back %(display_name)s!",
            display_name=provider.account.display_name))
    return redirect_back("account.profile",
                         invalid_targets=url_for('account.signin'))

@account.route('/profile-rpx', methods=('POST',))
@authenticated_permission.require(401)
def profile_rpx():
    token = request.values.get('token')
    params = urllib.urlencode({
        'token': token,
        'apiKey': config['JANRAIN_API_KEY'],
        'format': 'json'
    })

    http_response = urllib2.urlopen('https://rpxnow.com/api/v2/auth_info', params)
    auth_info = simplejson.loads(http_response.read())

    del http_response

    if auth_info['stat'] != 'ok':
        flash(_("Something went wrong signing-in with your account provider. "
                "Please try again."), "error")
        return redirect_to("account.profile")

    profile = auth_info['profile']
    if not profile:
        flash(_("Something went wrong signing-in with your account provider. "
                "Please try again."), "error")
        return redirect_to("account.profile")

    identifier = profile['identifier']
    provider = AccountProvider.query.get(identifier)
    if provider:
        if provider in g.identity.account.providers:
            flash(_(u"You already have this login provider associated with "
                    u"your account."), "error")
            return redirect_to('account.profile')
        flash(_(u"Another account(not your's) is already associated with "
                u"this provider."), "error")
        return redirect_to('account.profile')

    provider_email = profile.get('verifiedEmail', profile.get('email'))
    existing_email = EMailAddress.query.get(provider_email)
    if existing_email and existing_email.account != g.identity.account:
        flash(_("Another account using the email address %(email_address)s "
                "is already registred with us. Do you have two accounts with "
                "us!?", email_address=existing_email.address), "error")
        return redirect_to('account.profile')

    provider = AccountProvider(identifier, profile['providerName'])
    g.identity.account.providers.add(provider)

    if 'photo' in profile:
        photo = ProfilePhoto(url=profile['photo'])
        if g.identity.account.profile_photos.count() == 0:
            photo.preferred = True
        g.identity.account.profile_photos.append(photo)

    dbm.session.commit()

    if not existing_email:
        session['provider_email'] = provider_email
        return redirect_to('account.profile_extra_email')
    flash(_("Sucessfuly added the account provider \"%(provider)s\" to your "
            "account", provider=provider.provider), "ok")
    return redirect_to('account.profile')

@account.route('/profile-extra', methods=('GET', 'POST'))
@authenticated_permission.require(401)
def profile_extra_email():
    provider_email = session.get('provider_email', None)
    if not provider_email:
        return redirect_to('account.profile')

    form = ExtraEmailForm(request.values.copy(), email_address=provider_email)
    if form.validate_on_submit():
        # Remove provider_email from session
        session.pop('provider_email')
        if 'no' in request.values:
            flash(_("The email address \"%(provider_email)s\" won't be added "
                    "to your account", provider_email=provider_email))
            return redirect_back("account.profile")


        email = EMailAddress(provider_email)
        email.activation_key = ActivationKey()
        g.identity.account.email_addresses.add(email)
        dbm.session.commit()

        message = Message(_("ILog: Please Confirm You Email Address"),
                          recipients=[email.address])

        activation_url = url_for('account.activate',
                                 hash=email.activation_key.key, _external=True)
        body = render_template('emails/initial_email_confirm.txt',
                               account=account, activation_url=activation_url)
        message.body = body
        log.trace("Sending confirmation email.")
        mail.send(message)
        log.trace("Sent confirmation email.")
        flash(_("An email has been sent to confirm the email address "
                "%(email_address)s.", email_address=email.address))
        return redirect_to('account.profile')
    return render_template('account/extra_email.html', form=form,
                           email_address=provider_email)

@account.route('/profile', methods=('GET', 'POST'))
@authenticated_permission.require(401)
def profile():
    if 'delete_account' in request.values:
        return redirect_to('account.delete_account')

    account = Account.query.get(g.identity.account.id)
    form = ProfileForm(account)
    if form.validate_on_submit():
        locale = request.values.get('locale')
        timezone = request.values.get('timezone')
        if locale != account.locale:
            account.locale = locale
        if timezone != account.timezone:
            account.timezone = timezone
        password = request.values.get('password')
        if password:
            account.set_password(password)
        dbm.session.commit()
        flash(_("Account details updated."), "ok")
        return redirect_to('account.profile')

    token_url = url_for('account.profile_rpx', _external=True)
    app_domain = app.config.get('JANRAIN_APP_DOMAIN', None)

    return render_template('account/profile.html', form=form,
                           token_url=token_url, app_domain=app_domain)

@account.route('/register', methods=('GET', 'POST'))
def register():
    log.debug("on account.register")
    if getattr(g.identity, 'account', None):
        flash(_("You're already authenticated!"), "error")
        return redirect_back("account.profile")

    rpx_profile = session.get('rpx_profile', None)
    if not rpx_profile:
        flash(_(u"Account registrations will be performed after signing-in "
                u"using one of the following services."),
              (request.method=="POST" and "error" or "info"))
        return redirect_to('account.signin')

    display_name = rpx_profile.get('name', None)
    form = RegisterForm(**{
        'identifier': rpx_profile.get('identifier'),
        'provider': rpx_profile.get('providerName'),
        'username': rpx_profile.get('preferredUsername', ''),
        'display_name': display_name and
                        display_name.get('formatted', '') or '',
        'email': rpx_profile.get('verifiedEmail', rpx_profile.get('email'))
    })

    if form.validate_on_submit():
        log.debug("Register form validated")
        del session['rpx_profile']
        session.modified = True
        provider = AccountProvider.query.get(request.values.get('identifier'))
        if provider:
            flash(_("We already have an account using this provider. "
                    "Please sign-in using your account with "
                    "%(provider)s") % {'provider': rpx_profile['providerName']},
                    "error")
            return redirect_back('account.signin')
        account = Account(username=request.form.get('username'),
                          display_name=request.form.get('display_name'),
                          passwd=request.form.get('new_password'))

        email = EMailAddress(request.values.get('email'))
        email.preferred = True
        email.activation_key = ActivationKey()
        account.email_addresses.add(email)

        if 'photo' in rpx_profile:
            photo = ProfilePhoto(url=rpx_profile['photo'])
            photo.preferred = True
            account.profile_photos.append(photo)

        account.providers.add(AccountProvider(
            identifier=request.values.get('identifier'),
            provider=request.values.get('provider')
        ))
        dbm.session.add(account)
        dbm.session.commit()

        identity_changed.send(app, identity=Identity(account.id, "dbm"))

        log.trace("Added account %s to database", account)

        message = Message(_("ILog: Please Confirm You Email Address"),
                          recipients=[email.address])
        body = render_template('emails/initial_email_confirm.txt',
            account=account, activation_url=url_for(
                'account.activate', hash=email.activation_key.key,
                _external=True
            )
        )
        message.body = body
        gevent.spawn_later(1, mail.send, message)
        flash(_("An email has been sent to confirm your email address"))
        return redirect_to('account.profile')
    return render_template('account/register.html', form=form)


@account.route('/activate/<hash>', methods=('GET',))
def activate(hash):
    activation_key = ActivationKey.query.get(hash)
    if not activation_key:
        flash(_("Activation Key Not Known. Plobably Expired"))
        if g.identity.account:
            return redirect_back('account.profile')
        return redirect_back('account.signin')

    activation_key.email.verified = True
    activation_key.email.account.confirmed = True
    if len(activation_key.email.account.email_addresses) == 1:
        activation_key.email.preferred = True
    message = Message(_("ILog: Welcome to %(website)s", website="ILog"),
                      recipients=[activation_key.email.address])
    body = render_template('emails/welcome.txt',
                           account=activation_key.email.account)
    message.body = body
    gevent.spawn_later(1, mail.send, message)
    dbm.session.delete(activation_key)
    dbm.session.commit()
    flash(_("Your account is now fully active."))
    return redirect_to('account.profile')

@account.route("/resend-activation-email")
def resend_activation_email():
    account = g.identity.account
    if not account:
        flash("You have to authenticate first!", "warn")
        return redirect_to("account.signin")

    messages = []

    for email in account.email_addresses:
        if email.activation_key is not None:
            dbm.session.delete(email.activation_key)
            email.activation_key = ActivationKey()
            dbm.session.commit()
            message = Message(_("ILog: Please Confirm You Email Address"),
                              recipients=[email.address])
            body = render_template('emails/initial_email_confirm.txt',
                account=account, activation_url=url_for(
                    'account.activate', hash=email.activation_key.key,
                    _external=True
                )
            )
            message.body = body
            messages.append(message)
            flash(_("An email has been sent to %(address)s in order to confirm "
                    "the email address", address=email.address))

    for message in messages:
        gevent.spawn_later(1, mail.send, message)

    return redirect_back('account.profile')

@account.route('/delete-account', methods=('GET', 'POST'))
@authenticated_permission.require(401)
def delete_account():
    if 'cancel' in request.values:
        return redirect_back('account.profile')

    account = Account.query.get(g.identity.account.id)

    form = DeleteAccountForm(account, request.values.copy())

    if form.validate_on_submit():
        dbm.session.delete(account)
        dbm.session.commit()
        session.clear()
        identity_changed.send(app, identity=AnonymousIdentity())
        return redirect_to("main.index")

    return render_template('account/delete.html', form=form)

@account.route('/photos', methods=('GET', 'POST'))
@authenticated_permission.require(401)
def photos():
    return render_template('account/photos.html')
    raise NotImplementedError()

@account.route('/formats', methods=('GET', 'POST'))
@authenticated_permission.require(401)
def formats():
    return render_template('account/formats.html')
    raise NotImplementedError()
