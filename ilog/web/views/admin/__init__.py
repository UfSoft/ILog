# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin
    ~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Module, request, url_for, render_template, g
from flaskext.babel import gettext as _
from ilog.web.permissions import admin_permission, admin_or_manager_permission
from ilog.web.signals import ctxnav_build, nav_build

admin = Module(__name__, name="admin", url_prefix="/admin")

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
