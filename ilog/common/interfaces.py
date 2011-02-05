# -*- coding: utf-8 -*-
"""
    ilog.common.interfaces
    ~~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from giblets import Component

class ComponentBase(Component):
    def activate(self):
        raise NotImplementedError

    def connect_signals(self):
        raise NotImplementedError
