# -*- coding: utf-8 -*-
"""
    ilog.database.green
    ~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import eventlet
from sqlalchemy.pool import QueuePool, SingletonThreadPool

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
        timeout = eventlet.Timeout(5, PoolTimeout)
        try:
            while self._max_overflow > -1 and \
                                        self._overflow >= self._max_overflow:
                eventlet.sleep(0)
        finally:
            timeout.cancel()
        return super(GreenQueuePool,self).do_get()

class GreenSingletonThreadPool(SingletonThreadPool):
    """Simple subclass of the standard SA SingletonThreadPool.
    Uses a sleep everytime when the pool is empty to green thread switch.
    """
    def do_get(self):
        timeout = eventlet.Timeout(5, PoolTimeout)
        try:
            return SingletonThreadPool.do_get(self)
        finally:
            # switch to another greenthread to run it
            timeout.cancel()
            eventlet.sleep(0)

    def cleanup(self):
        try:
            return SingletonThreadPool.cleanup(self)
        finally:
            print 'SWITCH!!!!\n\n'
            eventlet.sleep(0)
