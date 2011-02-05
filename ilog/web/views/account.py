# -*- coding: utf-8 -*-
"""
    ilog.web.views.account
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
import simplejson
from eventlet.green import urllib, urllib2
from flask import Module, url_for, redirect, flash, request, session, render_template
from flaskext.principal import Identity, identity_changed
from ilog.database.models import Account, AccountProvider
from ilog.web.application import app, config, redirect_to, redirect_back
from ilog.web.forms import LoginForm
from ilog.web.permissions import authenticated_permission

log = logging.getLogger(__name__)

account = Module(__name__, name="account", url_prefix='/account')

@account.route('/signin', methods=("GET", "POST"))
def signin():
    form=LoginForm(formdata=request.values.copy())
    token_url = url_for('account.rpx', _external=True)
    app_domain = config.get('JANRAIN_APP_DOMAIN', None)
    if form.validate_on_submit():
        pass

    print 888, app_domain
    return render_template('account/login.html', token_url=token_url,
                           app_domain=app_domain, form=form)

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
        flash(_("Welcome to ILog please confirm your details and "
                "create your account!"))
        return redirect_to("account.register")

    identity_changed.send(app, identity=Identity(provider.account.id))

    flash(_("Welcome back %(display_name)s!",
            display_name=provider.account.display_name))
    return redirect_back("account.profile")

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
    provider = Provider.query.get(identifier)
    if provider:
        if provider in g.identity.account.providers:
            flash(_(u"You already have this login provider associated with "
                    u"your account."), "error")
            return redirect_to('account.profile')
        flash(_(u"Another account(not your's) is already associated with "
                u"this provider."), "error")
        return redirect_to('account.profile')

    provider_email = profile.get('verifiedEmail', rpx_profile.get('email'))
    existing_email = EMailAddress.query.get(provider_email)
    if existing_email and existing_email.account != g.identity.account:
        flash(_("Another account using the email address %(email_address)s "
                "is already registred with us. Do you have two accounts with "
                "us!?", email_address=existing_email.address), "error")
        return redirect_to('account.profile')

    provider = Provider(identifier, profile['providerName'])
    g.identity.account.providers.add(provider)
    if not existing_email:
        session['provider_email'] = provider_email
        return redirect_to('account.profile_extra_email')
    db.session.commit()
    flash(_("Sucessfuly added the account provider to your account"), "ok")
    return redirect_to('account.profile')
