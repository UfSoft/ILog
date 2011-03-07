# -*- coding: utf-8 -*-
"""
    ilog.database.models
    ~~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
import unicodedata
from datetime import datetime, timedelta
from hashlib import md5, sha1
from time import time
from uuid import uuid4
from sqlalchemy import orm
from werkzeug.security import check_password_hash, generate_password_hash


from ilog.database import dbm, BaseQuery

log = logging.getLogger(__name__)

def gen_slug(name):
    return '-'.join(
        unicodedata.normalize('NFKD', name).encode('ascii','ignore').split()
    ).lower()

class SchemaVersion(dbm.Model):
    """SQLAlchemy-Migrate schema version control table."""

    __tablename__   = 'migrate_version'

    repository_id   = dbm.Column(dbm.String(255), primary_key=True)
    repository_path = dbm.Column(dbm.Text)
    version         = dbm.Column(dbm.Integer)

    def __init__(self, repository_id, repository_path, version):
        self.repository_id = repository_id
        self.repository_path = repository_path
        self.version = version


class AccountProvider(dbm.Model):

    __tablename__   = 'account_providers'

    identifier = dbm.Column(dbm.String, primary_key=True)
    account_id = dbm.Column(dbm.ForeignKey("accounts.id"))
    provider   = dbm.Column(dbm.String(25), index=True, unique=True)

    # relationships
    account    = None

    def __init__(self, identifier=None, provider=None):
        self.identifier = identifier
        self.provider = provider

    def __repr__(self):
        return '<%s for %r>' % (self.__class__.__name__, self.provider)

class AccountQuery(orm.Query):

    def expired_activations(self):
        return self.filter(dbm.and_(
            Account.active==False,
            Account.register_date<=datetime.utcnow()-timedelta(days=30)
        ))

    def by_provider(self, identifier):
        return getattr(AccountProvider.query.get(identifier), 'account', None)

    def by_username(self, username):
        return self.filter(Account.username==username).first()


class Account(dbm.Model):

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

    query_class   = AccountQuery

    def __init__(self, username=None, display_name=None, confirmed=False,
                 passwd=None, tzinfo="UTC", locale="en"):
        self.username = username
        self.display_name = display_name and display_name or username
        self.confirmed = confirmed
        if passwd:
            self.set_password(passwd)

    def __repr__(self):
        return "<User %s>" % (self.username or 'annonymous')

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


class ProfilePhoto(dbm.Model):
    __tablename__   = 'profile_photos'
    id              = dbm.Column(dbm.Integer, primary_key=True)
    filename        = dbm.Column(dbm.String)
    url             = dbm.Column(dbm.String)
    preferred       = dbm.Column(dbm.Boolean, default=False)
    account_id      = dbm.Column(dbm.ForeignKey("accounts.id"))

    def __init__(self, filename=None, url=None):
        self.filename = filename
        self.url = url

class EMailAddress(dbm.Model):
    __tablename__   = 'email_addresses'
    address         = dbm.Column(dbm.String, primary_key=True)
    verified        = dbm.Column(dbm.Boolean, default=False)
    preferred       = dbm.Column(dbm.Boolean, default=False)
    account_id      = dbm.Column(dbm.ForeignKey("accounts.id"))

    activation_key  = dbm.relation("ActivationKey", backref="email",
                                   uselist=False,
                                   cascade="all, delete, delete-orphan")

    def __init__(self, address):
        self.address = address


class ActivationKey(dbm.Model):
    __tablename__   = 'activation_keys'
    key             = dbm.Column(dbm.String, default=lambda:uuid4().hex, primary_key=True)
    generated_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    email_address   = dbm.Column(dbm.ForeignKey("email_addresses.address"))


class PrivilegeQuery(orm.Query):

    def get(self, privilege):
        if not isinstance(privilege, basestring):
            try:
                privilege = privilege.name
            except AttributeError:
                # It's a Need
                try:
                    privilege = privilege.value
                except AttributeError:
                    raise
        return self.filter(Privilege.name==privilege).first()


class Privilege(dbm.Model):
    __tablename__   = 'privileges'

    id      = dbm.Column(dbm.Integer, primary_key=True)
    name    = dbm.Column(dbm.String(50), unique=True)

    query_class = PrivilegeQuery

    def __init__(self, privilege_name):
        if not isinstance(privilege_name, basestring):
            try:
                privilege_name = privilege_name.name
            except AttributeError:
                # It's a Need
                try:
                    privilege_name = privilege_name.value
                except AttributeError:
                    raise
        self.name = privilege_name

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.name)


account_privileges = dbm.Table('account_privileges', dbm.metadata,
    dbm.Column('account_id', dbm.ForeignKey('accounts.id')),
    dbm.Column('privilege_id', dbm.ForeignKey('privileges.id'))
)

class GroupQuery(BaseQuery):

    def get(self, privilege):
        if isinstance(privilege, basestring):
            return self.filter(Group.name==privilege).first()
        return orm.Query.get(privilege)

class Group(dbm.Model):
    __tablename__ = 'groups'

    id            = dbm.Column(dbm.Integer, primary_key=True)
    name          = dbm.Column(dbm.String(30))

    accounts      = dbm.dynamic_loader("Account", secondary="group_accounts",
                        backref=dbm.backref("groups", lazy=True,
                                            collection_class=set),
                        query_class=AccountQuery)
    privileges    = dbm.relation("Privilege", secondary="group_privileges",
                                 backref="priveliged_groups", lazy=True,
                                 collection_class=set, cascade='all, delete')

    query_class   = GroupQuery


    def __init__(self, group_name):
        self.name = group_name

    def __repr__(self):
        return u'<%s %r:%r>' % (self.__class__.__name__, self.id, self.name)


group_accounts = dbm.Table('group_accounts', dbm.metadata,
    dbm.Column('group_id', dbm.ForeignKey('groups.id')),
    dbm.Column('account_id', dbm.ForeignKey('accounts.id'))
)

group_privileges = dbm.Table('group_privileges', dbm.metadata,
    dbm.Column('group_id', dbm.ForeignKey('groups.id')),
    dbm.Column('privilege_id', dbm.ForeignKey('privileges.id'))
)

class NetworkQuery(BaseQuery):

    def get(self, slug_or_id):
        if isinstance(slug_or_id, basestring):
            return self.filter(Network.slug==slug_or_id).first()
        return orm.Query.get(slug_or_id)

class Network(dbm.Model):
    __tablename__ = 'networks'
    __mapper_args__ = {'order_by': "name"}

    id            = dbm.Column(dbm.Integer, primary_key=True)
    slug          = dbm.Column(dbm.String(10), unique=True, index=True)
    name          = dbm.Column(dbm.String(30))
    host          = dbm.Column(dbm.String(30))
    port          = dbm.Column(dbm.Integer)
    created_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    created_by_id = dbm.Column(dbm.ForeignKey("accounts.id"))

    created_by    = dbm.relation("Account", backref="networks", lazy=True,
                                 cascade='all, delete')
    channels      = dbm.dynamic_loader("Channel", backref="network",
                                       cascade='all, delete, delete-orphan')

    query_class   = NetworkQuery

    def __init__(self, name, host, port=6667, slug=None):
        if not slug:
            slug = gen_slug(name)
        self.slug = slug
        self.name = name
        self.host = host
        self.port = port


class Identity(dbm.Model):
    __tablename__ = 'identities'

    id            = dbm.Column(dbm.Integer, primary_key=True)
    account_id    = dbm.Column(dbm.ForeignKey('accounts.id'), default=None)
    network_id    = dbm.Column(dbm.ForeignKey('networks.id'), default=None)
    nickname      = dbm.Column(dbm.String(30))
    realname      = dbm.Column(dbm.String(30))

    def __init__(self, nickname, realname=None):
        self.nickname = nickname
        self.realname = realname

class TopicChange(dbm.Model):
    __tablename__ = 'topic_changes'

    id            = dbm.Column(dbm.Integer, primary_key=True)
    changed_by    = dbm.Column(dbm.ForeignKey('accounts.id'))
    topic         = dbm.Column(dbm.String(30))
    changed_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)

    def __init__(self, topic):
        self.topic = topic

class ChannelQuery(BaseQuery):

    def get(self, slug_or_id):
        if isinstance(slug_or_id, basestring):
            return self.filter(Channel.slug==slug_or_id).first()
        return orm.Query.get(slug_or_id)

class Channel(dbm.Model):
    __tablename__ = 'channels'
    id            = dbm.Column(dbm.Integer, primary_key=True)
    network_id    = dbm.Column(dbm.ForeignKey('networks.id'), default=None)
    slug          = dbm.Column(dbm.String(10), unique=True, index=True)
    prefix        = dbm.Column(dbm.String(30))
    name          = dbm.Column(dbm.String(30))
    key           = dbm.Column(dbm.String(30))
    created_on    = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    topic_id      = dbm.Column(dbm.ForeignKey('topic_changes.id'))
    created_by_id = dbm.Column(dbm.ForeignKey("accounts.id"))

    # Relations
    topic         = dbm.relation("TopicChange", backref="channel",
                                 single_parent=True,
                                 cascade="all, delete, delete-orphan")
    events        = dbm.relation("IRCEvent", backref="channel",
                                 cascade="all, delete, delete-orphan")
    created_by    = dbm.relation("Account", backref="channels", lazy=True)

    query_class   = ChannelQuery

    def __init__(self, name, slug=None, prefix=None, key=None):
        if not prefix and name[0] in "#&":
            prefix = name[0]
            name = name[1:]
        elif not prefix and name[0] not in "#&":
            prefix = "#"
            name = name
        if not slug:
            slug = gen_slug(name)
        self.slug = slug
        self.name = name
        self.prefix = prefix
        self.key = key

    @property
    def prefixed_name(self):
        return ''.join([self.prefix, self.name])

class IRCEventType(dbm.Model):
    __tablename__ = 'irc_event_types'
    type          = dbm.Column(dbm.String(30), primary_key=True)

    def __init__(self, type):
        self.type = type

class IRCEvent(dbm.Model):
    __tablename__ = 'irc_events'
    id            = dbm.Column(dbm.Integer, primary_key=True)
    type_id       = dbm.Column(dbm.ForeignKey('irc_event_types.type'))
    channel_id    = dbm.Column(dbm.ForeignKey('channels.id'))
    stamp         = dbm.Column(dbm.DateTime, default=datetime.utcnow)
    raw_message   = dbm.Column(dbm.String(30))
    clean_message = dbm.Column(dbm.String(30))
    message       = dbm.Column(dbm.String(30))

    def __init__(self):
        pass
