# -*- coding: utf-8 -*-
"""
    ilog.database.signals
    ~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from ilog.common.signals import signal

database_engine_created = signal("database-engine-created", """\
This signal is emmited once we have a database engine.
""")

database_upgraded = signal("database-upgraded", """\
This signal is emmited when database has been upgraded.
""")

database_setup = signal("database-setup", """\
This signal is emmited when database has been setup and is ready to be used.
""")

before_models_committed = signal("before-models-commited")
models_committed = signal("models-commited")
