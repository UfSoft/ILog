# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.accounts
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Module, request, url_for, render_template
from flaskext.babel import gettext as _
from ilog.web.signals import ctxnav_build, nav_build

accounts = Module(__name__, name="admin.accounts", url_prefix="/admin/accounts")

@ctxnav_build.connect_via(accounts)
def on_accounts_ctxnav_build(emitter):
        return (
            # prio, endpoint, name, partial also macthes
            (1, 'admin.accounts.index', _("List Accounts"), False),
            (2, 'admin.accounts.add', _("Add Accounts"), False),
            (3, 'admin.accounts.edit', _("Edit Accounts"), False),
            (4, 'admin.accounts.delete', _("Delete Accounts"), False),
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
