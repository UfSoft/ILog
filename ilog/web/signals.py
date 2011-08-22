# -*- coding: utf-8 -*-
"""
    ilog.web.signals
    ~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from ilog.common.signals import signal

webapp_setup_complete = signal("webapp-setup-complete", """\
Emitted once the web application has been fully configured.
""")

webapp_shutdown = signal("webapp-shutdown", """\
Emitted once the web application has been fully shutdown.
""")

after_identity_account_loaded = signal("after-identity-account-loaded", """\
Emmited after loading the identity from the database.
""")
