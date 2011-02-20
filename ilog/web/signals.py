# -*- coding: utf-8 -*-
"""
    ilog.web.signals
    ~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from ilog.common.evblinker import signal

webapp_setup_complete = signal("webapp-setup-complete", """\
Emitted once the web application has been fully configured.
""")

webapp_shutdown = signal("webapp-shutdown", """\
Emitted once the web application has been fully configured.
""")

ctxnav_build = signal("ctxnav-build", """\
Emitted in order to get ctxnav contents
""")
