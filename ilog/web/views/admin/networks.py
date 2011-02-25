# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.networks
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""


from flask import Module, request, url_for, render_template, flash, g
from flaskext.babel import gettext as _
from ilog.database import dbm
from ilog.database.models import Group, Network, Privilege
from ilog.web.application import redirect_to, redirect_back
from ilog.web.permissions import admin_permission, manager_permission, admin_or_manager_permission
from ilog.web.signals import ctxnav_build, nav_build
from ilog.web.views.admin.forms import AddNetwork, DeleteNetwork, EditNetwork

networks = Module(__name__, name="admin.networks", url_prefix="/admin/networks")


@ctxnav_build.connect_via(networks)
def on_networks_ctxnav_build(emitter):
    if request.path.startswith(url_for('admin.networks.index')):
        return (
            # prio, endpoint, name, partial also macthes
            (1, 'admin.networks.index', _("List Networks"), False),
            (2, 'admin.networks.add', _("Add Network"), False),
        )


@networks.route('/', defaults={'page': 1})
@networks.route('/page/<int:page>')
@admin_or_manager_permission.require(403)
def index(page=1):
#    if not g.identity.can(admin_permission):
#        networks = Network.query.filter(
#            Network.created_by_id==g.identity.account.id
#        )
#    else:
#        networks = Network.query
#    pagination = networks.paginate(page=page, per_page=25)
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
@admin_or_manager_permission.require(403)
def add():
    form = AddNetwork(formdata=request.values.copy())
    if form.validate_on_submit():
        network = Network(name=form.data.get('name'),
                          host=form.data.get('host'),
                          port=form.data.get('port'))

        account = g.identity.account
        group = Group.query.get("manager")
        account.groups.add(group)
        account.privileges.add(Privilege("manage-%s" % network.slug))

        network.created_by = account
        dbm.session.add(network)
        dbm.session.commit()
        flash(_("Network \"%(name)s\" added.", name=network.name))
        return redirect_to("admin.networks.edit", id=network.id)

    return render_template('admin/networks/add.html', form=form)

@networks.route('/edit/<int:id>', methods=("GET", "POST"))
@admin_or_manager_permission.require(403)
def edit(id=None):
    if 'delete' in request.values:
        return redirect_to('admin.networks.delete', id=id)
    elif 'cancel' in request.values:
        return redirect_back('admin.networks.index')

    network = Network.query.get(id)

    form = EditNetwork(network, request.values.copy())
    if form.validate_on_submit():
        form.db_entry.name = form.data.get('name', form.db_entry.name)
        form.db_entry.host = form.data.get('host', form.db_entry.host)
        form.db_entry.port = form.data.get('port', form.db_entry.port)
        dbm.session.commit()
        flash(_("Network \"%(name)s\" updated.", name=network.name))
        return redirect_to("admin.networks.index")
    return render_template('admin/networks/edit.html', form=form)

@networks.route('/delete/<int:id>')
@admin_or_manager_permission.require(403)
def delete(id=None):
    if 'cancel' in request.values:
        return redirect_back('admin.networks.edit', id=id)

    network = Network.query.get(id)
    form = DeleteNetwork(network, request.values.copy())
    if form.validate_on_submit():
        manage_privilege = Privilege.query.get("manage-%" % network.slug)
        if manage_privilege:
            dbm.session.delete(manage_privilege)
        dbm.session.delete(network)
        dbm.session.commit()
        flash(_("Network \"%(name)s\" deleted.", name=form.name.value))
        return redirect_to("admin.networks.index")
    return render_template('admin/networks/delete.html', form=form)
