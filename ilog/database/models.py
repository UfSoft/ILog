# -*- coding: utf-8 -*-
"""
    ilog.database.models
    ~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import re
import sys
import logging
import sqlalchemy
import sqlalchemy.orm
from datetime import datetime, timedelta
from hashlib import md5, sha1
from time import time
from types import ModuleType
from sqlalchemy import and_, or_, orm
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.orm.interfaces import (MapperExtension, SessionExtension,
                                       EXT_CONTINUE)
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.orm.session import Session
from sqlalchemy.util import to_list
from werkzeug.security import check_password_hash, generate_password_hash


from .signals import before_models_committed, database_setup, models_committed

log = logging.getLogger(__name__)

#: create a new module for all the database related functions and objects
sys.modules['ilog.database.db'] = db = ModuleType('db')
for module in sqlalchemy, sqlalchemy.orm:
    for key in module.__all__:
        if not hasattr(db, key):
            setattr(db, key, getattr(module, key))



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
            before_models_committed.send(session.db_manager, changes=d.values())
        return EXT_CONTINUE

    def after_commit(self, session):
        d = session._model_changes
        if d:
            models_committed.send(session.db_manager, changes=d.values())
            d.clear()
        return EXT_CONTINUE

    def after_rollback(self, session):
        session._model_changes.clear()
        return EXT_CONTINUE


class _SignallingSession(Session):

    def __init__(self, db, autocommit=False, autoflush=False, **options):
#        print 123, db, dir(db)
        Session.__init__(self, autocommit=autocommit, autoflush=autoflush,
                         extension=[_SignallingSessionExtension()],
                         bind=db.database_engine, **options)
        self.db_manager = db
        self._model_changes = {}
        self.begin()


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

    def __init__(self):
        database_setup.connect(self.__on_database_setup)

    def __on_database_setup(self, sender):
        if not hasattr(db, 'manager'):
            db.manager = sender
        self.db_manager = sender

    def __get__(self, obj, type):
        try:
            mapper = orm.class_mapper(type)
            if mapper:
                return type.query_class(
                    mapper, session=self.db_manager.get_session()
                )
        except UnmappedClassError:
            return None


class Model(object):
    """Baseclass for custom user models."""

    #: the query class used. The :attr:`query` attribute is an instance
    #: of this class. By default a :class:`BaseQuery` is used.
    query_class = orm.Query

    #: an instance of :attr:`query_class`. Can be used to query the
    #: database for instances of this model.
    query = None

    #: arguments for the mapper
    __mapper_cls__ = _SignalTrackingMapper

    __tablename__ = _ModelTableNameDescriptor()

db.and_ = and_
db.or_ = or_
#del and_, or_

Model = declarative_base(cls=Model, name='Model')
Model.query = _QueryProperty()
metadata = Model.metadata

db.metadata = metadata


class SchemaVersion(Model):
    """SQLAlchemy-Migrate schema version control table."""

    __tablename__   = 'migrate_version'

    repository_id   = db.Column(db.String(255), primary_key=True)
    repository_path = db.Column(db.Text)
    version         = db.Column(db.Integer)

    def __init__(self, repository_id, repository_path, version):
        self.repository_id = repository_id
        self.repository_path = repository_path
        self.version = version


class AccountProvider(Model):

    __tablename__   = 'account_providers'

    identifier = db.Column(db.String, primary_key=True)
    account_id = db.Column(db.ForeignKey("accounts.id"))
    provider   = db.Column(db.String(25), index=True, unique=True)

    # relationships
    account    = None

    def __init__(self, identifier=None, provider=None):
        self.identifier = identifier
        self.provider = provider

class AccountQuery(orm.Query):
    def get_nobody(self):
        return AnonymousAccount()

    def expired_activations(self):
        return self.filter(db.and_(
            Account.active==False,
            Account.register_date<=datetime.utcnow()-timedelta(days=30)
        ))

    def by_provider(self, identifier):
        return getattr(AccountProvider.query.get(identifier), 'account', None)


class Account(Model):

    __tablename__   = 'accounts'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(25), index=True, unique=True)
    email         = db.deferred(db.Column(db.String, index=True, unique=True))
    display_name  = db.Column(db.String(60))
    banned        = db.Column(db.Boolean, default=False)
    confirmed     = db.Column(db.Boolean, default=False)
    passwd_hash   = db.Column(db.String, default="!")
    last_login    = db.Column(db.DateTime, default=datetime.utcnow)
    register_date = orm.deferred(db.Column(db.DateTime,
                                           default=datetime.utcnow))
    activation_key= db.Column(db.String, default="!")
    tzinfo        = db.Column(db.String(25), default="UTC")
    locale        = db.Column(db.String(10), default="en")


    # Relationships
    privileges    = db.relation("Privilege", secondary="user_privileges",
                                backref="priveliged_accounts", lazy=True,
                                collection_class=set, cascade='all, delete')

    groups        = None    # Defined on Group
    providers     = db.relation("AccountProvider", backref="account",
                                collection_class=set,
                                cascade="all, delete, delete-orphan")
    identities    = None    # Defined on Identity

    query_class   = AccountQuery

    def __init__(self, username=None, email=None, display_name=None,
                 confirmed=False, passwd=None, tzinfo="UTC", locale="en"):
        self.username = username
        self.display_name = display_name and display_name or username
        self.email = email
        self.confirmed = confirmed
        if passwd:
            self.set_password(passwd)

    def __repr__(self):
        return "<User %s>" % (self.username or 'annonymous')

    def _active(self):
        return self.activation_key == '!'
    active = property(_active)

    def set_activation_key(self):
        self.activation_key = sha1(("%s|%s|%s|%s" % (
            self.id, self.username, self.register_date, time())).encode('utf-8')
        ).hexdigest()

    def activate(self):
        self.activation_key = '!'

    def get_gravatar_url(self, size=80):
        from ilog.application import get_application
        assert 8 < size < 256, 'unsupported dimensions'
        return '%s/%s?d=%s&rating=%s&size=%d' % (
            get_application().cfg['gravatar/url'].rstrip('/'),
            md5(self.email.lower()).hexdigest(),
            get_application().cfg['gravatar/fallback'],
            get_application().cfg['gravatar/rating'],
            size
        )
    gravatar_url = property(get_gravatar_url)

    def set_password(self, password):
        self.passwd_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.passwd_hash == '!':
            return False
        if check_password_hash(self.passwd_hash, password):
            self.update_last_login()
            return True
        return False

    def update_last_login(self):
        self.last_login = datetime.utcnow()

    @property
    def all_privileges(self):
        from ilog.application import get_application
        result = set(self.privileges)
        for group in self.groups:
            result.update(group.privileges)
        return frozenset([get_application().privileges.get(p.name)
                          for p in result])

    def has_privilege(self, privilege):
        return add_privilege(privilege)(self.all_privileges)

    @property
    def is_admin(self):
        return self.has_privilege(ILOG_ADMIN)

    @property
    def is_manager(self):
        return self.has_privilege(ENTER_ADMIN_PANEL)

class AnonymousAccount(Account):
    is_somebody   = False
    locale        = 'en'


class PrivilegeQuery(orm.Query):

    def get(self, privilege):
        if not isinstance(privilege, basestring):
            privilege = privilege.name
        return self.filter(Privilege.name==privilege).first()


class Privilege(Model):
    __tablename__   = 'privileges'

    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(50), unique=True)

    query_class = PrivilegeQuery

    def __init__(self, privilege_name):
        if not isinstance(privilege_name, basestring):
            privilege_name = privilege_name.name
        self.name = privilege_name

    @property
    def privilege(self):
        from ilog.application import get_application
        return get_application().privileges.get(self.name)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.name)


user_privileges = db.Table('user_privileges', metadata,
    db.Column('user_id', db.ForeignKey('accounts.id')),
    db.Column('privilege_id', db.ForeignKey('privileges.id'))
)


class Group(Model):
    __tablename__ = 'groups'

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(30))

    accounts      = db.dynamic_loader("Account",
                                      backref=db.backref("groups", lazy=True),
                                      secondary="group_accounts",
                                      query_class=AccountQuery)
    privileges    = db.relation("Privilege", secondary="group_privileges",
                                backref="priveliged_groups", lazy=True,
                                collection_class=set, cascade='all, delete')

    def __init__(self, group_name):
        self.name = group_name

    def __repr__(self):
        return u'<%s %r:%r>' % (self.__class__.__name__, self.id, self.name)


group_accounts = db.Table('group_accounts', metadata,
    db.Column('group_id', db.ForeignKey('groups.id')),
    db.Column('user_id', db.ForeignKey('accounts.id'))
)

group_privileges = db.Table('group_privileges', metadata,
    db.Column('group_id', db.ForeignKey('groups.id')),
    db.Column('privilege_id', db.ForeignKey('privileges.id'))
)

class Network(Model):
    __tablename__ = 'networks'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(30))
    host          = db.Column(db.String(30))
    port          = db.Column(db.Integer)

    def __init__(self, name, host, port=6667):
        self.name = name
        self.host = host
        self.port = port


class Identity(Model):
    __tablename__ = 'identities'

    id            = db.Column(db.Integer, primary_key=True)
    account_id    = db.Column(db.ForeignKey('accounts.id'), default=None)
    network_id    = db.Column(db.ForeignKey('networks.id'), default=None)
    nickname      = db.Column(db.String(30))
    realname      = db.Column(db.String(30))

    def __init__(self, nickname, realname=None):
        self.nickname = nickname
        self.realname = realname

class TopicChange(Model):
    __tablename__ = 'topic_changes'

    id            = db.Column(db.Integer, primary_key=True)
    changed_by    = db.Column(db.ForeignKey('accounts.id'))
    topic         = db.Column(db.String(30))
    changed_on    = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, topic):
        self.topic = topic

class Channel(Model):
    __tablename__ = 'channels'
    id            = db.Column(db.Integer, primary_key=True)
    network_id    = db.Column(db.ForeignKey('networks.id'), default=None)
    prefix        = db.Column(db.String(30))
    name          = db.Column(db.String(30))
    key           = db.Column(db.String(30))
    topic_id      = db.Column(db.ForeignKey('topic_changes.id'))

    # Relations
    topic = db.relation("TopicChange", backref="channel", single_parent=True,
                        cascade="all, delete, delete-orphan")

    def __init__(self, name, prefix=None, key=None):
        if not prefix and name[0] in "#&":
            prefix = name[0]
            name = name[1:]
        self.name = name
        self.prefix = prefix
        self.key = key


