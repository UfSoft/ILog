# -*- coding: utf-8 -*-
"""
    ilog.database
    ~~~~~~~~~~~~~

    Part of the work done here was adapted from work on the `Flask SQLAlchemy`_
    extension by Armin Ronacher.

    :copyright: © 2010 by Armin Ronacher.
    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.

    _`Flask SQLAlchemy`: https://github.com/mitsuhiko/flask-sqlalchemy/
"""

import re
import logging
import eventlet
from eventlet import tpool
# Need to import exceptions myself so that errors are not thrown
eventlet.import_patched("migrate.exceptions")
migrate = eventlet.import_patched("migrate")
eventlet.import_patched("sqlalchemy.engine.default")
import sqlalchemy
import sqlalchemy.orm
from os import path
from functools import partial
from giblets import implements, implemented_by, Component, ExtensionPoint
from math import ceil
from migrate.versioning.api import upgrade
from migrate.versioning.repository import Repository
from sqlalchemy import orm
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.interfaces import (MapperExtension, SessionExtension,
                                       EXT_CONTINUE)
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.orm.session import Session
from sqlalchemy.util import to_list
from werkzeug.urls import url_decode

from ilog.database import upgrades
from ilog.common import component_manager
from ilog.common.interfaces import ComponentBase
from ilog.common.signals import running
from .green import GreenQueuePool
from .interfaces import IDatabaseManager, IDatabaseUpgradeParticipant
from .signals import (database_upgraded, database_setup, models_committed,
                      before_models_committed, database_engine_created)

log = logging.getLogger(__name__)

_sqlite_re = re.compile(r'sqlite:(?:(?://(.*?))|memory)(?:\?(.*))?$')

def _make_table(db):
    def _make_table(*args, **kwargs):
        if len(args) > 1 and isinstance(args[1], db.Column):
            args = (args[0], db.metadata) + args[2:]
        return sqlalchemy.Table(*args, **kwargs)
    return _make_table


def _include_sqlalchemy(obj):
    for module in sqlalchemy, sqlalchemy.orm:
        for key in module.__all__:
            if not hasattr(obj, key):
                setattr(obj, key, getattr(module, key))
    obj.Table = _make_table(obj)


class _SignalTrackingMapperExtension(MapperExtension):

    def after_delete(self, mapper, connection, instance):
        return self._record(mapper, instance, 'delete')

    def after_insert(self, mapper, connection, instance):
        return self._record(mapper, instance, 'insert')

    def after_update(self, mapper, connection, instance):
        return self._record(mapper, instance, 'update')

    def _record(self, mapper, model, operation):
        pk = tuple(mapper.primary_key_from_instance(model))
        orm.object_session(model)._model_changes[pk] = (model, operation)
        return EXT_CONTINUE


class _SignalTrackingMapper(Mapper):

    def __init__(self, *args, **kwargs):
        extensions = to_list(kwargs.pop('extension', None), [])
        extensions.append(_SignalTrackingMapperExtension())
        kwargs['extension'] = extensions
        Mapper.__init__(self, *args, **kwargs)


class _SignallingSessionExtension(SessionExtension):

    def before_commit(self, session):
        d = session._model_changes
        if d:
            before_models_committed.send(dbm, changes=d.values())
        return EXT_CONTINUE

    def after_commit(self, session):
        d = session._model_changes
        if d:
            models_committed.send(dbm, changes=d.values())
            d.clear()
        return EXT_CONTINUE

    def after_rollback(self, session):
        session._model_changes.clear()
        return EXT_CONTINUE


class _SignallingSession(Session):

    def __init__(self, dbm=None, autocommit=False, autoflush=False, **options):
        Session.__init__(self, autocommit=autocommit, autoflush=autoflush,
                         extension=[_SignallingSessionExtension()],
                         bind=dbm.database_engine, **options)
        self._model_changes = {}

    def commit(self):
        eventlet.spawn(Session.commit, self).wait()


class _ModelTableNameDescriptor(object):
    _camelcase_re = re.compile(r'([A-Z]+)(?=[a-z0-9])')

    def __get__(self, obj, type):
        tablename = type.__dict__.get('__tablename__')
        if not tablename:
            def _join(match):
                word = match.group()
                if len(word) > 1:
                    return ('_%s_%s' % (word[:-1], word[-1])).lower()
                return '_' + word.lower()
            tablename = self._camelcase_re.sub(_join, type.__name__).lstrip('_')
            setattr(type, '__tablename__', tablename)
        return tablename

class _QueryProperty(object):

    def __init__(self, dbm):
        self.dbm = dbm

    def __get__(self, obj, mapper_type):
        try:
            mapper = orm.class_mapper(mapper_type)
            if mapper:
                return mapper_type.query_class(
                    mapper, session=self.dbm.session()
                )
        except UnmappedClassError:
            return None


class Pagination(object):
    """Internal helper class returned by :meth:`BaseQuery.paginate`.  You
    can also construct it from any other SQLAlchemy query object if you are
    working with other libraries.  Additionally it is possible to pass `None`
    as query object in which case the :meth:`prev` and :meth:`next` will
    no longer work.
    """

    def __init__(self, query, page, per_page, total, items):
        #: the unlimited query object that was used to create this
        #: pagination object.
        self.query = query
        #: the current page number (1 indexed)
        self.page = page
        #: the number of items to be displayed on a page.
        self.per_page = per_page
        #: the total number of items matching the query
        self.total = total
        #: the items for the current page
        self.items = items


    @property
    def pages(self):
        """The total number of pages"""
        return int(ceil(self.total / float(self.per_page)))

    @property
    def required(self):
        return self.pages > 1

    def prev(self, error_out=False):
        """Returns a :class:`Pagination` object for the previous page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.query.paginate(self.page - 1, self.per_page, error_out)

    @property
    def prev_num(self):
        """Number of the previous page."""
        return self.page - 1

    @property
    def has_prev(self):
        """True if a previous page exists"""
        return self.page > 1

    def next(self, error_out=False):
        """Returns a :class:`Pagination` object for the next page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.query.paginate(self.page + 1, self.per_page, error_out)

    @property
    def has_next(self):
        """True if a next page exists."""
        return self.page < self.pages

    @property
    def next_num(self):
        """Number of the next page"""
        return self.page + 1

    def iter_pages(self, left_edge=2, left_current=2,
                   right_current=5, right_edge=2):
        """Iterates over the page numbers in the pagination.  The four
        parameters control the thresholds how many numbers should be produced
        from the sides.  Skipped page numbers are represented as `None`.
        This is how you could render such a pagination in the templates:

        .. sourcecode:: html+jinja

            {% macro render_pagination(pagination, endpoint) %}
              <div class=pagination>
              {%- for page in pagination.iter_pages() %}
                {% if page %}
                  {% if page != pagination.page %}
                    <a href="{{ url_for(endpoint, page=page) }}">{{ page }}</a>
                  {% else %}
                    <strong>{{ page }}</strong>
                  {% endif %}
                {% else %}
                  <span class=ellipsis>…</span>
                {% endif %}
              {%- endfor %}
              </div>
            {% endmacro %}
        """
        last = 0
        for num in xrange(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and \
                num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


class BaseQuery(orm.Query):

    def paginate(self, page, per_page=20, error_out=True):
        """Returns `per_page` items from page `page`.  By default it will
        abort with 404 if no items were found and the page was larger than
        1.  This behavor can be disabled by setting `error_out` to `False`.

        Returns an :class:`Pagination` object.
        """
        from flask import abort
        if error_out and page < 1:
            abort(404)
        items = self.limit(per_page).offset((page - 1) * per_page).all()
        if not items and page != 1 and error_out:
            abort(404)
        return Pagination(self, page, per_page, self.count(), items)



class Model(object):
    """Baseclass for custom user models."""

    #: the query class used. The :attr:`query` attribute is an instance
    #: of this class. By default a :class:`BaseQuery` is used.
    query_class = BaseQuery

    #: an instance of :attr:`query_class`. Can be used to query the
    #: database for instances of this model.
    query = None

    #: arguments for the mapper
    __mapper_cls__ = _SignalTrackingMapper

    __tablename__ = _ModelTableNameDescriptor()


class ConnectTimeout(Exception):
    """Connection timeout."""


class DatabaseManager(ComponentBase):
    implements(IDatabaseManager, IDatabaseUpgradeParticipant)

    upgrade_participants = ExtensionPoint(IDatabaseUpgradeParticipant)

    # IDatabaseUpgradeParticipant attributes
    repository_id   = "ILog Schema Version Control"
    repository_path = upgrades.__path__[0]

    # ComponentBase methods
    def activate(self):
        _include_sqlalchemy(self)
        self.Model = declarative_base(cls=Model, name='Model')
        self.Model.query = _QueryProperty(self)

    def connect_signals(self):
        database_engine_created.connect(self.on_database_engine_created)
        database_upgraded.connect(self.on_database_upgraded)

    @property
    def metadata(self):
        """Returns the metadata"""
        return self.Model.metadata

    # IDatabase Attributes And Methods
    database_uri = None
    database_engine = None
    native_unicode = True
    record_queries = False
    pool_size = 5
    pool_timeout = 10
    pool_recycle = 3600

    def set_database_uri(self, uri):
        """Set the database uri"""
        if uri != self.database_uri:
            log.debug("Setting database URI to %s", uri)
            self.database_uri = uri
            eventlet.spawn(self.create_engine)

    def create_engine(self):
        """Create the database engine"""
        log.debug("Creating ENGINE")
        options = {
            'convert_unicode': self.native_unicode,
            'poolclass': GreenQueuePool,
            'pool_size': self.pool_size,
            'pool_recycle': self.pool_recycle,
            'pool_timeout': self.pool_timeout

        }

        if self.database_uri.startswith('sqlite:'):

            options.pop('pool_timeout')

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
            pool_size = options.get('pool_size', 0)
            # we go to memory and the pool size was explicitly set to 0
            # which is fail.  Let the user know that
            if info.database in (None, '', ':memory:'):
                if pool_size == 0:
                    raise RuntimeError('SQLite in memory database with an '
                                       'empty queue not possible due to data '
                                       'loss.')
                # if pool size is None or explicitly set to 0 we assume the
                # user did not want a queue for this sqlite connection and
                # hook in the null pool.
                elif not pool_size:
                    log.warn("SQLite database is using the NullPool")
                    from sqlalchemy.pool import NullPool
                    options['poolclass'] = NullPool
            else:
                from .green import GreenSingletonThreadPool
                options['poolclass'] = GreenSingletonThreadPool
        else:
            info = make_url(self.database_uri)
            # if mysql is the database engine, god forbid, and no connection
            # encoding is provided we set it to utf-8
            if info.drivername == 'mysql':
                info.query.setdefault('charset', 'utf8')
                options.setdefault('pool_size', 10)
                options.setdefault('pool_recycle', 7200)
            elif info.drivername.startswith('postgresql+psycopg2'):
                from psycopg2 import extensions
                options['use_native_unicode'] = self.native_unicode

                if hasattr(extensions, 'set_wait_callback'):
                    from eventlet.support import psycopg2_patcher
                    psycopg2_patcher.make_psycopg_green()

        dialect_cls = info.get_dialect()

        # get the correct DBAPI base on connection url
        dbapi_args = {}
        dbapi = dialect_cls.dbapi(**dbapi_args)

        # create the dialect
        dialect_args = {'dbapi':dbapi}
        dialect = dialect_cls(**dialect_args)

        # assemble connection arguments for this dialect
        (cargs, connection_params) = dialect.create_connect_args(info)
        log.debug("CARGS: %s; CONNECTION_PARAMS: %s;", cargs, connection_params)

        def eventlet_connection_creator():
            """Creator method to wrap DBAPI connections with native threads to
            allow non-blocking db access."""
            # This code is lifted and slightly tweaked
            # from the db_pool in the eventlet package
            timeout = eventlet.Timeout(5, ConnectTimeout)
            try:
                if self.database_uri.startswith('sqlite:'):
#                    return dbapi.connect(cargs[0], **connection_params)
                    conn = eventlet.spawn(dbapi.connect, cargs[0],
                                          **connection_params)
                    return conn.wait()

                conn = dbapi.connect(cargs[0], **connection_params)
                ## I think this is to keep the connection itself from blocking
                ## unfortunately it's hanging. The proxied connection still works
                ## nonblockingly though.
                # conn = tpool.execute(dbapi.connect, **kw)
                proxied_connection = tpool.Proxy(conn, autowrap_names=('cursor',))
                return proxied_connection
            finally:
                # cancel the timeout
                timeout.cancel()

        options.setdefault('creator', eventlet_connection_creator)

        log.debug("Creating db engine. info: %s; options: %s;", info, options)
        engine = sqlalchemy.create_engine(info, **options)
        database_engine_created.send(self, engine=engine)

    # Database Manager Methods
    def upgrade_database(self):
        from .models import SchemaVersion
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
            repository = Repository(participant.repository_path)
            if not self.session.query(SchemaVersion).get(repo_id):
                self.session.add(SchemaVersion(
                    repo_id,
                    path.abspath(path.expanduser(repository.path)), 0)
                )
                self.session.commit()

            schema_version = self.session.query(SchemaVersion).get(repo_id)
            if schema_version.version < repository.latest:
                log.warn("Upgrading database (from -> to...) on repository "
                         "\"%s\"", repo_id)
                try:
                    eventlet.spawn(upgrade, self.database_engine, repository)
                except Exception, err:
                    log.exception(err)
                log.warn("Upgrade complete for repository \"%s\"", repo_id)
            else:
                log.debug("No database upgrade required for repository: \"%s\"",
                         repo_id)

        log.debug("Upgrades complete.")
        database_upgraded.send(self)
        eventlet.sleep(0.1)

    def on_database_engine_created(self, emitter, engine):
        self.database_engine = engine
        self.metadata.bind = engine

        def eventlet_greenlet_scope():
            return id(eventlet.greenthread.getcurrent())

        self.session = orm.scoped_session(
            partial(_SignallingSession, self, autoflush=False, autocommit=False),
            scopefunc=eventlet_greenlet_scope
        )
        eventlet.spawn(self.upgrade_database)

    def on_database_upgraded(self, emitter):
        database_setup.send(self)


dbm = DatabaseManager(component_manager)
