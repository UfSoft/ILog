# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin
    ~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Module, request, url_for, render_template
from flaskext.babel import gettext as _
from ilog.web.signals import ctxnav_build

admin = Module(__name__, name="admin", url_prefix="/admin")

@ctxnav_build.connect_via(admin)
def on_admin_ctxnav_build(emitter):
    return (
        # prio, endpoint, name, partial also macthes
        (1, 'admin.dashboard', _("Dashboard"), False),
        (2, 'admin.account.index', _("Accounts"), False)
    )

@admin.route('/')
@admin.route('/dashboard')
def dashboard():
    return render_template('index.html')
