# -*- coding: utf-8 -*-
"""
    ilog.common.signals
    ~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from .evblinker import signal

daemonized = signal("daemonized", """\
Emitted once a daemon is daemonized.
""")

running = signal("running", """\
Emitted once a daemon is running.
""")

shutdown = signal("shutdown", """\
Emitted once a daemon starts to shutdown.
""")

undaemonized = signal("undaemonized", """\
Emitted once a daemon is un-daemonized.
""")
