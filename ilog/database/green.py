# -*- coding: utf-8 -*-
"""
    ilog.database.green
    ~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import gevent
from sqlalchemy.pool import QueuePool

class PoolTimeout(Exception):
    """Exception raised when getting a connection from the pool takes too long.
    """

class GreenQueuePool(QueuePool):
    """Simple subclass of the standard SA QueuePool.
    Uses a sleep when the pool is empty to green thread switch.
    """


    def do_get(self):
        # while the queue pool is filled, switch to another greenthread until
        # one is available.
        timeout = gevent.Timeout(self._timeout, PoolTimeout)
        try:
            while self._max_overflow > -1 and \
                                        self._overflow >= self._max_overflow:
                gevent.sleep(0)
        finally:
            timeout.cancel()
        return super(GreenQueuePool,self).do_get()

