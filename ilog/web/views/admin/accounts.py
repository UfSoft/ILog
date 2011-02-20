# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.accounts
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from flask import Module

account = Module(__name__, name="admin.account", url_prefix="/admin/accounts")

@account.route('/')
def index():
    raise NotImplementedError()
