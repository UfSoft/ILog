# -*- coding: utf-8 -*-
"""
    ilog.database.interfaces
    ~~~~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from giblets import Attribute, ExtensionInterface

class IDatabaseManager(ExtensionInterface):
    database_uri    = Attribute("migrate repository id")
    database_engine = Attribute("database engine")
    native_unicode  = Attribute("Use native unicode with PG databases")
    record_queries  = Attribute("Record database queries")
    pool_size       = Attribute("Database pool size")
    pool_timeout    = Attribute("Database pool timeout")
    pool_recycle    = Attribute("Database pool recycle")

    def set_database_uri(uri):
        """Set the database uri"""

    def create_engine():
        """Create the database engine"""


class IDatabaseUpgradeParticipant(ExtensionInterface):
    repository_id   = Attribute("migrate repository id")
    repository_path = Attribute("migrate repository path")
