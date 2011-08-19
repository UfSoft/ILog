# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.accounts
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Blueprint, request, g, render_template
from flaskext.babel import gettext as _
from ilog.web.application import menus
from ilog.web.permissions import admin_permission
from ilog.web.views.admin import check_for_admin

accounts = Blueprint("admin.accounts", __name__, url_prefix="/admin/accounts")

def check_for_admin(menu_item):
    return (g.identity.account is not None and
            g.identity.can(admin_permission) and
            (request.blueprint=='admin' or request.blueprint.startswith('admin.')))

def check_for_admin_and_blueprint(menu_item):
    return (g.identity.account is not None and
            g.identity.can(admin_permission) and
            request.blueprint=='admin.accounts')


def request_endpoint_startswith_admin_accounts(menu_item):
    return request.blueprint=='admin.accounts'

menus.add_menu_entry(
    'nav', _("Accounts"), 'admin.accounts.index',
    activewhen=request_endpoint_startswith_admin_accounts,
    visiblewhen=check_for_admin, classes="admin"
)

menus.add_menu_entry(
    'ctxnav', _("List Accounts"), 'admin.accounts.index',
    visiblewhen=check_for_admin_and_blueprint, classes="admin"
)
menus.add_menu_entry(
    'ctxnav', _("Add Accounts"), 'admin.accounts.add',
    visiblewhen=check_for_admin_and_blueprint, classes="admin"
)
menus.add_menu_entry(
    'ctxnav', _("Edit Accounts"), 'admin.accounts.edit',
    visiblewhen=check_for_admin_and_blueprint, classes="admin"
)
menus.add_menu_entry(
    'ctxnav', _("Delete Accounts"), 'admin.accounts.delete',
    visiblewhen=check_for_admin_and_blueprint, classes="admin"
)


@accounts.route('/')
def index():
    return render_template('index.html')

@accounts.route('/add')
def add():
    return render_template('index.html')

@accounts.route('/edit/')
@accounts.route('/edit/<int:id>')
def edit(id=None):
    return render_template('index.html')

@accounts.route('/delete/')
@accounts.route('/delete/<int:id>')
def delete(id=None):
    return render_template('index.html')
