# -*- coding: utf-8 -*-
'''
Created on 23 Aug 2010

@author: vampas
'''
import logging
from datetime import datetime
from sqlalchemy import orm
from sqlalchemy.orm import create_session
from sqlalchemy.ext.declarative import declarative_base
from ilog.database.models import db

Model = declarative_base(name='Model')
metadata = Model.metadata

log = logging.getLogger('evafm.core.upgrades.001')

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


    def __init__(self, username=None, email=None, display_name=None,
                 confirmed=False, passwd=None, tzinfo="UTC", locale="en"):
        self.username = username
        self.display_name = display_name and display_name or username
        self.email = email
        self.confirmed = confirmed
        if passwd:
            self.set_password(passwd)

class Privilege(Model):
    __tablename__   = 'privileges'

    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(50), unique=True)


    def __init__(self, privilege_name):
        if not isinstance(privilege_name, basestring):
            privilege_name = privilege_name.name
        self.name = privilege_name


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
                                      secondary="group_accounts")
    privileges    = db.relation("Privilege", secondary="group_privileges",
                                backref="priveliged_groups", lazy=True,
                                collection_class=set, cascade='all, delete')

    def __init__(self, group_name):
        self.name = group_name


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


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; use the engine
    # named 'migrate_engine' imported from migrate.
    log.debug("Creating Database Tables")
    metadata.create_all(migrate_engine)

    session = create_session(migrate_engine, autoflush=True, autocommit=False)

def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    metadata.drop_all(migrate_engine)
