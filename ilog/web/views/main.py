# -*- coding: utf-8 -*-
"""
    ilog.views.main
    ~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
from operator import itemgetter
from flask import Module, render_template, request
from flaskext.babel import gettext as _
from ilog.database import dbm
from ilog.web.application import app, url_for
from ilog.web.signals import ctxnav_build

log = logging.getLogger(__name__)

main = Module(__name__, name='main')

@ctxnav_build.connect_via(main)
def on_main_ctxnav_build(emitter):
    return (
        # prio, endpoint, name, partial also macthes
        (0, 'main.libraries', _("Libraries"), False),
    )

@ctxnav_build.connect
def on_global_ctxnav_build(emitter):
    return (
        # prio, endpoint, name, partial also macthes
        (0, 'main.index', _("Home"), False),
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
