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

@admin.route('/')
@admin.route('/dashboard')
def dashboard():
    return render_template('admin/dashboard.html')
