# -*- coding: utf-8 -*-
"""
    ilog.database.interfaces
    ~~~~~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from giblets import Attribute, ExtensionInterface

class IDatabaseManager(ExtensionInterface):
    database_uri = Attribute("migrate repository id")
    database_engine = Attribute("database engine")

    def set_database_uri(uri):
        """Set the database uri"""

    def create_engine():
        """Create the database engine"""

    def get_session():
        """Get a database session"""


class IDatabaseUpgradeParticipant(ExtensionInterface):
    repository_id   = Attribute("migrate repository id")
    repository_path = Attribute("migrate repository path")
