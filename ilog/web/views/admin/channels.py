# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.channels
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Module, request, url_for, render_template, g, flash
from flaskext.babel import gettext as _
from ilog.database import dbm
from ilog.database.models import Channel, Group, Network, Privilege
from ilog.web.application import redirect_to, redirect_back
from ilog.web.permissions import (admin_permission, manager_permission,
                                  require_permissions)
from ilog.web.signals import ctxnav_build
from ilog.web.views.admin.forms import AddChannel, EditChannel, DeleteChannel

channels = Module(__name__, name="admin.channels", url_prefix="/admin/channels")


@ctxnav_build.connect_via(channels)
def on_channels_ctxnav_build(emitter):
    if request.path.startswith(url_for('admin.channels.index')):
        return (
            # prio, endpoint, name, partial also macthes
            (1, 'admin.channels.index', _("List Channels"), False),
            (2, 'admin.channels.add', _("Add Channel"), False),
        )


#@channels.route('/', defaults={'network': None, 'page': 1})
#@channels.route('/page/<int:page>', defaults={'network': None})
#@channels.route('/<network>', defaults={'page': 1})
#@channels.route('/<network>/page/<int:page>')
@channels.route('/', defaults={'page': 1})
@channels.route('/page/<int:page>')
@require_permissions((admin_permission, manager_permission), http_exception=403)
def index(network=None, page=None):
    pagination = Channel.query.paginate(page=page, per_page=25)
    if g.identity.can(admin_permission):
        own_channels = [i.id for i in pagination.items]
    else:
        own_channels = [
            i.id for i in pagination.items if i.created_by==g.identity.account
        ]
    print [i.created_by for i in pagination.items], g.identity.account
    return render_template('admin/channels/index.html', pagination=pagination,
                           own_channels=own_channels,
                           is_admin=g.identity.can(admin_permission))

@channels.route('/add', methods=("GET", "POST"))
@require_permissions((admin_permission, manager_permission), http_exception=403)
def add():
    form = AddChannel(formdata=request.values.copy())
    form.network.query = Network.query
    if form.validate_on_submit():

        channel = Channel(name=form.data.get('name'))
        form.network.data.channels.append(channel)
        account = g.identity.account
        group = Group.query.get("manager")
        account.groups.add(group)
        privilege = Privilege.query.get("manage-%s" % channel.slug)
        if not privilege:
            privilege = Privilege("manage-%s" % channel.slug)
        account.privileges.add(privilege)

        channel.created_by = account
        dbm.session.add(channel)
        dbm.session.commit()
        flash(_("Channel \"%(name)s\" added.", name=channel.prefixed_name))
        return redirect_to("admin.channels.edit", slug=channel.slug)
    return render_template('admin/channels/add.html', form=form)

@channels.route('/edit/<slug>')
@require_permissions(admin_permission, 'slug', http_exception=403)
def edit(slug=None):
    # TODO: If name changed also change permission name
    return render_template('index.html')

@channels.route('/delete/<slug>', methods=("GET", "POST"))
@require_permissions((admin_permission, manager_permission), 'slug', http_exception=403)
def delete(slug=None):
    if 'cancel' in request.values:
        return redirect_back('admin.networks.edit', slug=slug)

    channel = Channel.query.get(slug)
    form = DeleteChannel(channel, request.values.copy())
    if form.validate_on_submit():
        manage_privilege = Privilege.query.get("manage-%s" % channel.slug)
        if manage_privilege:
            g.identity.account.privileges.remove(manage_privilege)
        flash(_("Channel \"%(name)s\" deleted.", name=channel.name))
        dbm.session.delete(channel)
        dbm.session.commit()
        return redirect_to("admin.channels.index")
    return render_template('admin/channels/delete.html', form=form)

