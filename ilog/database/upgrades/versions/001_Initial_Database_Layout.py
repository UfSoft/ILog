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
from uuid import uuid4
from ilog.database import dbm

Model = declarative_base(name='Model')
metadata = Model.metadata

log = logging.getLogger('evafm.core.upgrades.001')

class SchemaVersion(Model):
    """SQLAlchemy-Migrate schema version control table."""

    __tablename__   = 'migrate_version'

    repository_id   = dbm.Column(dbm.String(255), primary_key=True)
    repository_path = dbm.Column(dbm.Text)
    version         = dbm.Column(dbm.Integer)


class AccountProvider(Model):

    __tablename__   = 'account_providers'

    identifier = dbm.Column(dbm.String, primary_key=True)
    account_id = dbm.Column(dbm.ForeignKey("accounts.id"))
    provider   = dbm.Column(dbm.String(25), index=True, unique=True)


class Account(Model):

    __tablename__   = 'accounts'

    id            = dbm.Column(dbm.Integer, primary_key=True)
    username      = dbm.Column(dbm.String(25), index=True, unique=True)
    display_name  = dbm.Column(dbm.String(60))
    banned        = dbm.Column(dbm.Boolean, default=False)
    confirmed     = dbm.Column(dbm.Boolean, default=False)
    passwd_hash   = dbm.Column(dbm.String, default="!")
    last_login    = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    register_date = orm.deferred(dbm.Column(dbm.DateTime,
                                            default=datetime.utcnow))
    timezone      = dbm.Column(dbm.String(25), default="UTC")
    locale        = dbm.Column(dbm.String(10), default="en")


    # Relationships
    privileges    = dbm.relation("Privilege", secondary="account_privileges",
                                 backref="priveliged_accounts", lazy=True,
                                 collection_class=set, cascade='all, delete')

    groups        = None    # Defined on Group
    providers     = dbm.relation("AccountProvider", backref="account",
                                 collection_class=set,
                                 cascade="all, delete, delete-orphan")

    identities    = None    # Defined on Identity

    email_addresses = dbm.relation("EMailAddress", backref="account",
                                   collection_class=set,
                                   cascade="all, delete, delete-orphan")
    profile_photos  = dbm.dynamic_loader("ProfilePhoto", backref="account",
                                         cascade="all, delete, delete-orphan")

class ProfilePhoto(Model):
    __tablename__   = 'profile_photos'
    id              = dbm.Column(dbm.Integer, primary_key=True)
    filename        = dbm.Column(dbm.String)
    url             = dbm.Column(dbm.String)
    preferred       = dbm.Column(dbm.Boolean, default=False)
    account_id      = dbm.Column(dbm.ForeignKey("accounts.id"))


class EMailAddress(Model):
    __tablename__   = 'email_addresses'
    address         = dbm.Column(dbm.String, primary_key=True)
    verified        = dbm.Column(dbm.Boolean, default=False)
    preferred       = dbm.Column(dbm.Boolean, default=False)
    account_id      = dbm.Column(dbm.ForeignKey("accounts.id"))

    activation_key  = dbm.relation("ActivationKey", backref="email",
                                   uselist=False,
                                   cascade="all, delete, delete-orphan")


class ActivationKey(Model):
    __tablename__   = 'activation_keys'
    key             = dbm.Column(dbm.String, default=lambda:uuid4().hex, primary_key=True)
    generated_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    email_address   = dbm.Column(dbm.ForeignKey("email_addresses.address"))


class Privilege(Model):
    __tablename__   = 'privileges'

    id      = dbm.Column(dbm.Integer, primary_key=True)
    name    = dbm.Column(dbm.String(50), unique=True)

    def __init__(self, name):
        self.name = name


account_privileges = dbm.Table('account_privileges', metadata,
    dbm.Column('account_id', dbm.ForeignKey('accounts.id')),
    dbm.Column('privilege_id', dbm.ForeignKey('privileges.id'))
)


class Group(Model):
    __tablename__ = 'groups'

    id            = dbm.Column(dbm.Integer, primary_key=True)
    name          = dbm.Column(dbm.String(30))

    accounts      = dbm.dynamic_loader("Account", secondary="group_accounts",
                                       backref=dbm.backref("groups", lazy=True))
    privileges    = dbm.relation("Privilege", secondary="group_privileges",
                                 backref="priveliged_groups", lazy=True,
                                 collection_class=set, cascade='all, delete')

    def __init__(self, name):
        self.name = name

group_accounts = dbm.Table('group_accounts', metadata,
    dbm.Column('group_id', dbm.ForeignKey('groups.id')),
    dbm.Column('account_id', dbm.ForeignKey('accounts.id'))
)

group_privileges = dbm.Table('group_privileges', metadata,
    dbm.Column('group_id', dbm.ForeignKey('groups.id')),
    dbm.Column('privilege_id', dbm.ForeignKey('privileges.id'))
)

class Network(Model):
    __tablename__ = 'networks'
    id            = dbm.Column(dbm.Integer, primary_key=True)
    slug          = dbm.Column(dbm.String(10), unique=True, index=True)
    name          = dbm.Column(dbm.String(30))
    host          = dbm.Column(dbm.String(30))
    port          = dbm.Column(dbm.Integer)
    encoding      = dbm.Column(dbm.String(25))
    features      = dbm.Column(dbm.PickleType)
    created_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    created_by_id = dbm.Column(dbm.ForeignKey("accounts.id"))

class NetworkMotd(Model):
    __tablename__ = 'networks_motds'
    network_id    = dbm.Column(dbm.ForeignKey("networks.id"), primary_key=True)
    motd          = dbm.Column(dbm.String(30))
    updated_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)

class Identity(Model):
    __tablename__ = 'identities'

    id            = dbm.Column(dbm.Integer, primary_key=True)
    account_id    = dbm.Column(dbm.ForeignKey('accounts.id'), default=None)
    network_id    = dbm.Column(dbm.ForeignKey('networks.id'), default=None)
    nickname      = dbm.Column(dbm.String(30))
    realname      = dbm.Column(dbm.String(30))


class TopicChange(Model):
    __tablename__ = 'topic_changes'

    id            = dbm.Column(dbm.Integer, primary_key=True)
    changed_by    = dbm.Column(dbm.ForeignKey('accounts.id'))
    topic         = dbm.Column(dbm.String(30))
    changed_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)


class Channel(Model):
    __tablename__ = 'channels'
    id            = dbm.Column(dbm.Integer, primary_key=True)
    network_id    = dbm.Column(dbm.ForeignKey('networks.id'), default=None)
    slug          = dbm.Column(dbm.String(10), unique=True, index=True)
    prefix        = dbm.Column(dbm.String(30))
    name          = dbm.Column(dbm.String(30))
    key           = dbm.Column(dbm.String(30))
    encoding      = dbm.Column(dbm.String(25))
    created_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    topic_id      = dbm.Column(dbm.ForeignKey('topic_changes.id'))
    created_by_id = dbm.Column(dbm.ForeignKey("accounts.id"))

    # Relations
    topic         = dbm.relation("TopicChange", backref="channel",
                                 single_parent=True,
                                 cascade="all, delete, delete-orphan")
    created_by    = dbm.relation("Account", backref="channels", lazy=True,
                                 cascade='all, delete')


class IRCEventType(Model):
    __tablename__ = 'irc_event_types'
    type          = dbm.Column(dbm.String(30), primary_key=True)


class IRCEvent(Model):
    __tablename__ = 'irc_events'
    id            = dbm.Column(dbm.Integer, primary_key=True)
    type_id       = dbm.Column(dbm.ForeignKey('irc_event_types.type'))
    channel_id    = dbm.Column(dbm.ForeignKey('channels.id'))
    stamp         = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    raw_message   = dbm.Column(dbm.String(30))
    clean_message = dbm.Column(dbm.String(30))
    message       = dbm.Column(dbm.String(30))


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; use the engine
    # named 'migrate_engine' imported from migrate.
    log.debug("Creating Database Tables")
    metadata.create_all(migrate_engine)

    session = create_session(migrate_engine, autoflush=True, autocommit=False)
    admins = Group("Administrators")
    admins.privileges.add(Privilege("administrator"))
    session.add(admins)
    managers = Group("Managers")
    managers.privileges.add(Privilege("manager"))
    session.add(managers)
    session.commit()

    # The first account created will be an administrator!!!
    migrate_engine.execute(group_accounts.insert(), group_id=admins.id,
                           account_id=1)

def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    metadata.drop_all(migrate_engine)
