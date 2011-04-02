# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.forms
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import gevent
import logging
import errno
from datetime import datetime
from gevent import socket
from gevent.event import Event
from girclib import client, signals
from ilog.web.forms import FormBase, _DBBoundForm
from flask import flash, Markup
from flaskext.babel import gettext as _
from flaskext.wtf import *
from flaskext.wtf.html5 import *

log = logging.getLogger(__name__)

class ValidationTimeout(Exception):
    pass

class Connectable(object):
    def __init__(self, timeout=60):
        self.timeout = timeout

    def on_disconnected(self, emitter):
        self.waiting_isupport.set()
        self.waiting_motd.set()
        self.validated.set()

    def on_motd(self, emitter, motd=None):
        log.trace("Rceived a MOTD: %s", motd)
        self.form.motd = '\n'.join(motd)
        self.waiting_motd.set()

    def on_signed_on(self, emitter):
        self.validate_form = True
        self.validated.set()

    def on_rpl_isupport(self, emitter, options):
        self.form.isupport_options = options
        self.waiting_isupport.set()

    def on_notice(self, emitter, channel=None, user=None, message=None):
        log.trace("Received _on_notice: %s", message)

    def get_host(self):
        return self.form.host.data

    def get_port(self):
        return self.form.port.data

    def skip_connect(self):
        db_entry = getattr(self.form, 'db_entry', None)
        if not db_entry:
            return False
        return db_entry.host == self.host and db_entry.port == self.port

    def __call__(self, form, field):
        self.validate_form = False
        self.validated = Event()
        self.waiting_motd = Event()
        self.waiting_isupport = Event()
        self.form = form
        self.form.motd = self.form.isupport_options = None
        self.host = self.get_host()
        self.port = self.get_port()

        if self.skip_connect():
            self.on_signed_on(self)
            return

        self.start = datetime.utcnow()
        nick = "ILog-%s" % id(self)
        self.client = client.IRCClient(self.host, self.port, nick, nick, nick)
        signals.on_motd.connect(self.on_motd, sender=self.client)
        signals.on_notice.connect(self.on_notice, sender=self.client)
        signals.on_rpl_isupport.connect(self.on_rpl_isupport, sender=self.client)
        signals.on_signed_on.connect(self.on_signed_on, sender=self.client)
        log.trace("Attempting to connect to %s:%s", self.host, self.port)
        timeout = gevent.Timeout(self.timeout, ValidationTimeout())
        try:
            timeout.start()
            self.client.connect(self.timeout)
            self.validated.wait()           # Wait until we're connected
            self.waiting_isupport.wait(10)  # Wait for ISUPPORT, 10 secs
            self.waiting_motd.wait(10)      # Wait for MOTD, 10 secs
        except ValidationTimeout:
            if not self.validate_form:
                log.trace("Timeout while connecting to %s:%s", self.host, self.port)
                raise ValidationError(_(
                    "Timeout while establish a connection to %(host)s:%(port)s."
                    " Are the details correct?", host=self.host, port=self.port)
                )
        except Exception, err:
            if err.errno == errno.EHOSTUNREACH:
                log.trace("Wrong port number while connecting to %s:%s?",
                          self.host, self.port)
                raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Is the port number correct?", host=self.host, port=self.port)
                )
            elif err.errno == errno.ECONNREFUSED:
                log.trace("Connection refused while connecting to %s:%s",
                          self.host, self.port)
                raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Connection refused!", host=self.host, port=self.port)
                )
            elif err.errno in (socket._socket.EAI_NODATA,
                               socket._socket.EAI_NONAME):
                log.trace("Wrong hostname while connecting to %s:%s?",
                          self.host, self.port)
                raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Is the host address correct?", host=self.host, port=self.port)
                )

            log.trace("Error while connecting to %s:%s  %s",
                      self.host, self.port, err)
            raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Error returned: %(error)s",
                    host=self.host, port=self.port, error=err)
                )

        finally:
            timeout.cancel()
            from flaskext.babel import format_timedelta
            log.trace("Connecting to server took %s",
                      format_timedelta(self.start))
            try:
                self.client.disconnect()
            except Exception, err:
                log.exception(err)
                print 9999999, err
            del self.client

        if not self.validate_form:
            raise ValidationError(_(
                "Could not establish a connection to %(host)s:%(port)s. "
                "Did not received a valid response from the IRC server.",
                host=self.host, port=self.port)
            )


class Joinable(Connectable):
    def on_motd(self, emitter, motd=None):
        log.trace("Rceived a MOTD: %s", motd)

    def on_signed_on(self, emitter):
        signals.on_joined.connect(self.on_joined, sender=self.client)
        self.client.join(self.form.name.data)

    def on_joined(self, emitter, channel):
        log.trace("Sucessfuly joined %s", channel)
        self.client.leave(channel)
        self.validate_form = True
        self.validated.set()

    def on_notice(self, emitter, channel=None, user=None, message=None):
        log.trace("Received _on_notice: %s", message)

    def get_host(self):
        return self.form.network.data.host

    def get_port(self):
        return self.form.network.data.port

    def skip_connect(self):
        db_entry = getattr(self.form, 'db_entry', None)
        if not db_entry:
            return False
        return self.form.db_entry.name == self.form.name


# Network related forms
class AddNetwork(FormBase):
    title            = _("Add Network")
    name             = TextField(_("Name"), validators=[Required()],
                        description=_("Pretty name of the network. For "
                                      "example \"Freenode\"."))
    host             = TextField(_("Host"), validators=[Required(),
                                                        Connectable()],
                        description=_("The hostname of the network. For the "
                                      "example above \"irc.freenode.net\"."))
    port             = IntegerField(_("Port"), validators=[Required()],
                        description=_("The network port number. For the "
                                      "example above \"6667\"."), default=6667)

class EditNetwork(_DBBoundForm):
    title            = _("Edit Network")
    id               = HiddenField(validators=[Required()])
    name             = TextField(_("Name"), validators=[Required()],
                        description=_("Pretty name of the network. For "
                                      "example \"Freenode\"."))
    host             = TextField(_("Host"), validators=[Required(),
                                                        Connectable()],
                        description=_("The hostname of the network. For the "
                                      "example above \"irc.freenode.net\"."))
    port             = IntegerField(_("Port"), validators=[
                        Required(), NumberRange(min=1, max=65535)],
                        description=_("The network port number. For the "
                                      "example above \"6667\"."), default=6667)
    slug             = TextField(_("Slug"), validators=[Required()],
                        description=_("The url part of the network"))

    encoding         = TextField(_("Encoding"), validators=[Required()],
                        description=_("The detected encoding the network uses"))


class DeleteNetwork(_DBBoundForm):
    title            = _("Delete Network")
    id               = HiddenField(validators=[Required()])


# Channel related forms
class AddChannel(FormBase):
    title            = _("Add Channel")
    network          = QuerySelectField(_("Network"), get_label='name')
    name             = TextField(_("Name"), validators=[Required(), Joinable()],
                        description=Markup(_(
                            "The channel name. If the prefix is ommited, ie, "
                            "\"<tt>#</tt>\" or \"<tt>&</tt>\", the default, "
                            "\"<tt>#</tt>\" is the one used.")))

class EditChannel(_DBBoundForm):
    title            = _("Add Channel")
    id               = HiddenField(validators=[Required()])
    network          = QuerySelectField(_("Network"), get_label='name')
    name             = TextField(_("Name"), validators=[Required(), Joinable()],
                        description=_("The channel name. If the prefix is "
                                      "ommited, ie, \"#\" or \"&\" the default "
                                      "\"#\" is the one used."))
    slug             = TextField(_("Slug"), validators=[Required()],
                        description=_("The url part of the network"))

class DeleteChannel(_DBBoundForm):
    title            = _("Delete Channel")
    id               = HiddenField(validators=[Required()])
