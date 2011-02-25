# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.channels
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Module, request, url_for, render_template
from flaskext.babel import gettext as _
from ilog.web.signals import ctxnav_build, nav_build

channels = Module(__name__, name="admin.channels", url_prefix="/admin/channels")


@ctxnav_build.connect_via(channels)
def on_channels_ctxnav_build(emitter):
    if request.path.startswith(url_for('admin.channels.index')):
        return (
            # prio, endpoint, name, partial also macthes
            (1, 'admin.channels.index', _("List Channels"), False),
            (2, 'admin.channels.add', _("Add Channels"), False),
            (3, 'admin.channels.edit', _("Edit Channels"), False),
            (4, 'admin.channels.delete', _("Delete Channels"), False),
        )

@channels.route('/')
def index():
    return render_template('index.html')

@channels.route('/add')
def add():
    return render_template('index.html')

@channels.route('/edit/<int:id>')
@channels.route('/edit/')
def edit(id=None):
    return render_template('index.html')

@channels.route('/delete/<int:id>')
@channels.route('/delete/')
def delete(id=None):
    return render_template('index.html')
