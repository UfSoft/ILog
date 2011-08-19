# -*- coding: utf-8 -*-
"""
    ilog.common.signals
    ~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from blinker import Namespace
signal = Namespace().signal

daemonized = signal("daemonized", """\
Emitted once a daemon is daemonized.
""")

running = signal("running", """\
Emitted once a daemon is running.
""")

chrooting = signal("chrooting", """\
Emitted once a daemon is about to chroot.
This is done late because of python imports. Import everything you need before
this signal.
""")

shutdown = signal("shutdown", """\
Emitted once a daemon starts to shutdown.
""")

undaemonized = signal("undaemonized", """\
Emitted once a daemon is un-daemonized.
""")
