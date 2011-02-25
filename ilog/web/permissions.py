# -*- coding: utf-8 -*-
"""
    ilog.web.permissions
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
import eventlet
from flask import flash, g, request
from flaskext.principal import *
from sqlalchemy.exc import OperationalError
from ilog.database import dbm
from ilog.database.signals import database_setup
from ilog.database.models import Account, Privilege
from .application import app, redirect_to

log = logging.getLogger(__name__)

Identity.__repr__ = lambda x: """\
<Identity name="%s" auth_type="%s" provides=%s>""" % (x.name, x.auth_type,
                                                      x.provides)

principal = Principal(app, use_sessions=False, skip_static=True)

anonymous_permission = Permission()

admin_role = RoleNeed('administrator')
manager_role = RoleNeed('manager')

manager_permission = Permission(manager_role)
admin_permission = Permission(admin_role)

admin_or_manager_permission = Permission(admin_role, manager_role)
#admin_permission = manager_permission.union(Permission(RoleNeed('administrator')))
#admin_permission = Permission(RoleNeed('administrator'), RoleNeed('manager'))
#print 789, admin_permission.needs

authenticated_permission = Permission(TypeNeed('authenticated'))

@principal.identity_loader
def load_request_identity():
    log.trace("Loading request identity. Session: %s", session)
    if "uid" in session:
        identity = Identity(session['uid'], "cookie")
    else:
        identity = AnonymousIdentity()
    return identity

@principal.identity_saver
def save_request_identity(identity):
    log.trace("On save_request_identity: %s", identity)
    if not identity.account:
        log.trace("No account associated with identity. Nothing to store.")
        return

    for need in identity.provides:
        log.debug("Identiy provides: %s", need)
        if need.method in ("type", "role"):
            # We won't store type methods, ie, "authenticated", nor, role
            # methods which are permissions belonging to groups and managed
            # on the administration panel.
            continue

        privilege = Privilege.query.get(need)
        if not privilege:
            log.debug("Privilege does not existe. creating...")
            privilege = Privilege(need)

        if privilege not in identity.account.privileges:
            identity.account.privileges.add(privilege)

    dbm.session.commit()
    session["uid"] = identity.account.id
    session.modified = True

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    log.trace("Identity loaded: %s", identity)
    try:
        identity.account = account = Account.query.get(identity.name)
        if account:
            account.update_last_login()
            identity.provides.add(TypeNeed('authenticated'))
            # Update the privileges that a user has
            for privilege in account.privileges:
                identity.provides.add(ActionNeed(privilege.name))
            for group in account.groups:
                # And for each of the groups the user belongs to
                for privilege in group.privileges:
                    # Add the group privileges to the user
                    identity.provides.add(RoleNeed(privilege.name))

    except OperationalError:
        # Database has not yet been setup
        pass

