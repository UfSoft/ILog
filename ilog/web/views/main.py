# -*- coding: utf-8 -*-
"""
    ilog.views.main
    ~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
from operator import itemgetter
from flask import Blueprint, render_template, request
from flaskext.babel import gettext as _
from ilog.database import dbm
from ilog.web.application import app, url_for, menus
from ilog.web.signals import nav_build, ctxnav_build

log = logging.getLogger(__name__)

main = Blueprint('main', __name__)

def request_enpoint_matches_menuitem_endpoint(menu_item):
    return request.endpoint==menu_item.endpoint

menus.add_menu_entry(
    'nav', _("Home"), 'main.index', priority=-100
)
menus.add_menu_entry(
    'nav', _("Libraries"), 'main.libraries',
    visiblewhen=lambda mi: request.blueprint=='main'
)

@main.route('/')
def index():
    return render_template('index.html')


@main.route('/libraries')
def libraries():
    libraries_used = [
        ("http://flask.pocoo.org/", "Flask"),
        ("http://bitbucket.org/leafstorm/flask-themes", "Flask Themes"),
        ("http://sjl.bitbucket.org/flask-lesscss/", "Flask LessCSS"),
        ("https://github.com/mitsuhiko/flask-sqlalchemy/", "Flask SQLAlchemy"),
        ("http://github.com/mitsuhiko/flask-babel", "Flask Babel"),
        ("http://www.sqlalchemy.org", "SQLAlchemy"),
        ("http://babel.edgewall.org/", "Babel"),
        ("http://bitbucket.org/s0undt3ch/flask-script", "Flask Script")
    ]

    sorted_libraries = sorted(libraries_used, key=itemgetter(1))
    return render_template("libraries.html", libraries=sorted_libraries)
