# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin
    ~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Blueprint, request, url_for, render_template, g
from flaskext.babel import gettext as _
from ilog.web.application import app, menus
from ilog.web.permissions import admin_permission, admin_or_manager_permission
from ilog.web.signals import ctxnav_build, nav_build

admin = Blueprint("admin", __name__, url_prefix="/admin")

def check_for_admin(menu_item):
    return (g.identity.account is not None and
            g.identity.can(admin_or_manager_permission) and
            request.blueprint.startswith('admin'))

def request_endpoint_startswith_accounts(menu_item):
    return request.module=='account' and request.endpoint.startswith('account.')

menus.add_menu_entry(
    'nav', _("Dashboard"), 'admin.dashboard', priority=-10,
    #activewhen=request_endpoint_startswith_accounts,
    visiblewhen=check_for_admin, classes="admin"
)

#menus.add_menu_entry(
#    'ctxnav', _("Profile Details"), 'account.profile',
#    visiblewhen=check_wether_account_is_not_none
#)
#menus.add_menu_entry(
#    'ctxnav', _("Date & Time Formats"), 'account.formats', priority=2,
#    visiblewhen=check_wether_account_is_not_none
#)
#menus.add_menu_entry(
#    'ctxnav', _("Profile Photos"), 'account.photos', priority=2,
#    visiblewhen=check_wether_account_is_not_none
#)

@nav_build.connect
def on_admin_nav_build(emitter):
    navigation = []
    if not request.path.startswith('/admin') or not \
                                    g.identity.can(admin_or_manager_permission):
        return navigation

    if g.identity.can(admin_permission):
        navigation.extend([
            (1, 'admin.dashboard', _("Dashboard"), False),
            (4, 'admin.accounts.index', _("Accounts"), True),
            (4, 'admin.accounts.index', _("Groups"), True),
            (4, 'admin.accounts.index', _("Permissions"), True)
        ])

    navigation.extend([
        (2, 'admin.networks.index', _("Networks"), True),
        (3, 'admin.channels.index', _("Channels"), True)
    ])
    return navigation

@admin.route('/')
@admin.route('/dashboard')
def dashboard():
    return render_template('admin/dashboard.html')
