# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.channels
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Blueprint, request, url_for, render_template, g, flash
from flaskext.babel import gettext as _
from ilog.database import dbm
from ilog.database.models import Channel, Group, Network, Privilege
from ilog.web.application import menus, redirect_to, redirect_back
from ilog.web.permissions import (admin_permission, manager_permission,
                                  require_permissions, admin_or_manager_permission)
from ilog.web.views.admin.forms import AddChannel, EditChannel, DeleteChannel

channels = Blueprint("admin.channels", __name__, url_prefix="/admin/channels")

def check_for_admin_or_manager(menu_item):
    return (g.identity.account is not None and
            g.identity.can(admin_or_manager_permission) and
            (request.blueprint=='admin' or request.blueprint.startswith('admin.')))

def check_for_admin_or_manager_and_blueprint(menu_item):
    return (g.identity.account is not None and
            g.identity.can(admin_or_manager_permission) and
            request.blueprint=='admin.channels')


def request_endpoint_startswith_admin_accounts(menu_item):
    return request.blueprint=='admin.channels'

menus.add_menu_entry(
    'nav', _("Channels"), 'admin.channels.index',
    activewhen=request_endpoint_startswith_admin_accounts,
    visiblewhen=check_for_admin_or_manager, classes="admin"
)

menus.add_menu_entry(
    'ctxnav', _("List Channels"), 'admin.channels.index',
    visiblewhen=check_for_admin_or_manager_and_blueprint, classes="admin"
)
menus.add_menu_entry(
    'ctxnav', _("Add Channel"), 'admin.channels.add', priority=1,
    visiblewhen=check_for_admin_or_manager_and_blueprint, classes="admin"
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

