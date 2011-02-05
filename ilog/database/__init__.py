# -*- coding: utf-8 -*-
"""
    ilog.database
    ~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import re
import logging
import eventlet
# Need to import exceptions myself so that errors are not thrown
eventlet.import_patched("migrate.exceptions")
migrate = eventlet.import_patched("migrate")
import sqlalchemy
from os import path
from functools import partial
from giblets import implements, implemented_by, Component, ExtensionPoint
from migrate.versioning.api import upgrade
from migrate.versioning.repository import Repository
from sqlalchemy import orm
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import ArgumentError
from werkzeug import url_decode

from ilog.database import upgrades
from ilog.common.interfaces import ComponentBase
from ilog.common.signals import running
from .interfaces import IDatabaseManager, IDatabaseUpgradeParticipant
from .models import _SignallingSession, SchemaVersion
from .signals import database_upgraded, database_setup

log = logging.getLogger(__name__)

_sqlite_re = re.compile(r'sqlite:(?:(?://(.*?))|memory)(?:\?(.*))?$')

class DatabaseManager(ComponentBase):
    implements(IDatabaseManager, IDatabaseUpgradeParticipant)

    upgrade_participants = ExtensionPoint(IDatabaseUpgradeParticipant)

    # IDatabaseUpgradeParticipant attributes
    repository_id   = "ILog Schema Version Control"
    repository_path = upgrades.__path__[0]

    # ComponentBase methods
    def activate(self):
        pass

    def connect_signals(self):
        running.connect(self.upgrade_database)
        database_upgraded.connect(self.on_database_upgraded)

    # IDatabase Attributes And Methods
    database_uri = None
    database_engine = None

    def set_database_uri(self, uri):
        """Set the database uri"""
        log.debug("Setting database URI to %s", uri)
        self.database_uri = uri

    def create_engine(self):
        """Create the database engine"""
        log.debug("Creating database engine")
        if self.database_uri.startswith('sqlite:'):
            match = _sqlite_re.match(self.database_uri)
            if match is None:
                raise ArgumentError('Could not parse rfc1738 URL')
            database, query = match.groups()
            if database is None:
                database = ':memory:'
            if query:
                query = url_decode(query).to_dict()
            else:
                query = {}
            info = URL('sqlite', database=database, query=query)
        else:
            info = make_url(self.database_uri)
            # if mysql is the database engine, god forbid, and no connection
            # encoding is provided we set it to utf-8
            if info.drivername == 'mysql':
                info.query.setdefault('charset', 'utf8')

        options = {'convert_unicode': True}
        log.debug("Creating db engine. info: %s; options: %s;", info, options)
        return sqlalchemy.create_engine(info, **options)

    def get_session(self, options=None):
        """Get a database session"""
        if not self.database_engine:
            self.database_engine = self.create_engine()
        if options is None:
            options = {}
        options.setdefault('autoflush', True)
        options.setdefault('autocommit', True)
        return _SignallingSession(self, **options)

    # Database Manager Methods
    def upgrade_database(self, emitter):
        if not self.database_engine:
            self.database_engine = self.create_engine()
        if not self.database_engine.has_table(SchemaVersion.__tablename__):
            log.info("Creating schema version control table")
            try:
                SchemaVersion.__table__.create(self.database_engine)
            except Exception, err:
                log.exception(err)
                raise RuntimeError, err
        # Sort upgraders.
        sorted_upgrade_participants = sorted(
            self.upgrade_participants, key=lambda x: len(implemented_by(x))
        )
        for participant in sorted_upgrade_participants:
            repo_id = participant.repository_id
            log.info("Checking for required upgrade on repository \"%s\"",
                     repo_id)
            self.create_engine()
            session = self.get_session()
            repository = Repository(participant.repository_path)
            if not session.query(SchemaVersion).get(repo_id):
                session.add(SchemaVersion(
                    repo_id,
                    path.abspath(path.expanduser(repository.path)), 0)
                )
                session.commit()

            schema_version = session.query(SchemaVersion).get(repo_id)
            if schema_version.version < repository.latest:
                log.warn("Upgrading database (from -> to...) on repository "
                         "\"%s\"", repo_id)
                try:
                    eventlet.spawn(upgrade, self.database_engine, repository)
                except Exception, err:
                    log.exception(err)
                eventlet.sleep(0.1)
                log.warn("Upgrade complete for repository \"%s\"", repo_id)
            else:
                log.debug("No database upgrade required for repository: \"%s\"",
                         repo_id)

            eventlet.sleep(0.1)
        log.debug("Upgrades complete.")
        database_upgraded.send(self)
        eventlet.sleep(0.1)
        self.database_engine = self.create_engine()

    def on_database_upgraded(self, emitter):
        database_setup.send(self)
