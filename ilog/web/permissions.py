# -*- coding: utf-8 -*-
"""
    ilog.web.permissions
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flaskext.principal import *
from sqlalchemy.exc import OperationalError
from ilog.database.signals import database_setup
from ilog.database.models import Account
from .application import app

principal = Principal(app, use_sessions=True)

admin_permission = Permission(RoleNeed('admin'))
anonymous_permission = Permission()
authenticated_permission = Permission(RoleNeed('authenticated'))


@principal.identity_loader
def load_request_identity():
    print "On load_request_identity"
    if 'identity.name' in session:
        identity = Identity(session['identity.name'])
        return identity
    return AnonymousIdentity()

@principal.identity_saver
def save_request_identity(identity):
    print "On save_request_identity"
#    if identity.name != 'anon':
#        session['id'] = identity.name
    print session

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    print "On identity_loaded"
    try:
        account = Account.query.get(identity.name)
        if account:
            account.update_last_login()
            identity.provides.add(RoleNeed('authenticated'))
            # Update the roles that a user can provide
            for role in account.roles:
                identity.provides.add(RoleNeed(str(role.name)))
            identity.account = account
    except OperationalError:
        # Database has not yet been setup
        pass

#@database_setup.connect_via(app)
#def connect_signals():
#    principal.identity_loader(load_request_identity)
#    principal.identity_saver(save_request_identity)
#    identity_loaded.connect(on_identity_loaded)
