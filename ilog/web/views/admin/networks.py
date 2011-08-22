# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.networks
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""


from flask import Blueprint, request, url_for, render_template, flash, g, session
from flaskext.babel import gettext as _
from ilog.common import convert
from ilog.database import dbm
from ilog.database.models import Group, Network, NetworkMotd, Privilege
from ilog.web.application import menus, redirect_to, redirect_back
from ilog.web.permissions import (admin_permission, manager_permission,
                                  admin_or_manager_permission,
                                  require_permissions)
from ilog.web.views.admin.forms import AddNetwork, DeleteNetwork, EditNetwork

networks = Blueprint("admin.networks", __name__, url_prefix="/admin/networks")


def check_for_admin_or_manager(menu_item):
    return (g.identity.account is not None and
            g.identity.can(admin_or_manager_permission) and
            (request.blueprint=='admin' or request.blueprint.startswith('admin.')))

def check_for_admin_or_manager_and_blueprint(menu_item):
    return (g.identity.account is not None and
            g.identity.can(admin_or_manager_permission) and
            request.blueprint=='admin.networks')


def request_endpoint_startswith_admin_accounts(menu_item):
    return request.blueprint=='admin.networks'

menus.add_menu_entry(
    'nav', _("Networks"), 'admin.networks.index',
    activewhen=request_endpoint_startswith_admin_accounts,
    visiblewhen=check_for_admin_or_manager, classes="admin"
)

menus.add_menu_entry(
    'ctxnav', _("List Networks"), 'admin.networks.index',
    visiblewhen=check_for_admin_or_manager_and_blueprint, classes="admin"
)
menus.add_menu_entry(
    'ctxnav', _("Add Network"), 'admin.networks.add', priority=1,
    visiblewhen=check_for_admin_or_manager_and_blueprint, classes="admin"
)

@networks.route('/', defaults={'page': 1})
@networks.route('/page/<int:page>')
@require_permissions((admin_permission, manager_permission), http_exception=403)
def index(page=1):
    pagination = Network.query.paginate(page=page, per_page=25)
    if g.identity.can(admin_permission):
        own_networks = [i.id for i in pagination.items]
    else:
        own_networks = [
            i.id for i in pagination.items if
            i.created_by==g.identity.account and i.channels.count() == 0
        ]
    print [i.channels for i in pagination.items ]
    return render_template('admin/networks/index.html', pagination=pagination,
                           own_networks=own_networks,
                           is_admin=g.identity.can(admin_permission))

@networks.route('/add', methods=("GET", "POST"))
@require_permissions((admin_permission, manager_permission), http_exception=403)
def add():
    if not request.values:
        session.pop('skip-connect', None)
    form = AddNetwork(formdata=request.values.copy())
    if form.validate_on_submit():
        network = Network(
            name=form.data.get('name'),
            host=form.data.get('host'),
            port=form.data.get('port')
        )

        if form.isupport_options is not None:
            network.features = form.isupport_options._features

        if form.data.get('motd', None) is not None:
            network.motd = NetworkMotd(form.data.get('motd'))

        if form.data.get('encoding', None) is not None:
            network.encoding = form.data.get('encoding')

        account = g.identity.account
        group = Group.query.get("manager")
        account.groups.add(group)
        privilege = Privilege.query.get("manage-%s" % network.slug)
        if not privilege:
            privilege = Privilege("manage-%s" % network.slug)
        account.privileges.add(privilege)

        network.created_by = account
        dbm.session.add(network)
        dbm.session.commit()
        session.pop('skip-connect', None)
        flash(_("Network \"%(name)s\" added.", name=network.name))
        return redirect_to("admin.networks.edit", slug=network.slug)

    return render_template('admin/networks/add.html', form=form)

@networks.route('/edit/<slug>', methods=("GET", "POST"))
@require_permissions(admin_permission, 'slug', http_exception=403)
def edit(slug=None):
    if 'delete' in request.values:
        return redirect_to('admin.networks.delete', slug=slug)
    elif 'cancel' in request.values:
        return redirect_back('admin.networks.index')

    network = Network.query.get(slug)
    if not network:
        return redirect_back("admin.networks.index")

    form = EditNetwork(network, request.values.copy())
    if form.validate_on_submit():
        # TODO: If name changed also change permission name
        form.db_entry.name = form.data.get('name', form.db_entry.name)
        form.db_entry.host = form.data.get('host', form.db_entry.host)
        form.db_entry.port = form.data.get('port', form.db_entry.port)
        dbm.session.commit()
        flash(_("Network \"%(name)s\" updated.", name=network.name))
        return redirect_to("admin.networks.index")
    return render_template('admin/networks/edit.html', form=form)

@networks.route('/delete/<slug>', methods=('POST', 'GET'))
@require_permissions(admin_permission, http_exception=403)
def delete(slug=None):
    if 'cancel' in request.values:
        return redirect_back('admin.networks.edit', slug=slug)

    network = Network.query.get(slug)
    form = DeleteNetwork(network, request.values.copy())
    if form.validate_on_submit():
        manage_privilege = Privilege.query.get("manage-%s" % network.slug)
        if manage_privilege:
            g.identity.account.privileges.remove(manage_privilege)
        network_name = network.name
        dbm.session.delete(network)
        dbm.session.commit()
        flash(_("Network \"%(name)s\" deleted.", name=network_name))
        return redirect_to("admin.networks.index")
    return render_template('admin/networks/delete.html', form=form)
