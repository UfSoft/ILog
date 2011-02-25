# -*- coding: utf-8 -*-
"""
    ilog.web.views.admin.forms
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import eventlet
import errno
from eventlet.green import socket
from eventlet.support import get_errno
from ilog.web.forms import FormBase, _DBBoundForm
from flaskext.babel import gettext as _
from flaskext.wtf import *
from flaskext.wtf.html5 import *


class ConnectTimeout(Exception):
    pass

def Connectable(secondary_field_name, timeout=5):
    def _connectable(form, field):
        try:
            port = int(field.data)
            host = getattr(form, secondary_field_name).data
        except ValueError:
            host = field.data
            port = getattr(form, secondary_field_name).data

        t = eventlet.Timeout(timeout, ConnectTimeout())
        try:
            eventlet.connect((host, port))
        except ConnectTimeout:
            raise ValidationError(_(
                "Timeout while establish a connection to %(host)s:%(port)s. "
                "Are the details correct?", host=host, port=port)
            )
        except Exception, err:
            if get_errno(err) == errno.EHOSTUNREACH:
                raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Is the port number correct?", host=host, port=port)
                )
            elif get_errno(err) == errno.ECONNREFUSED:
                raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Connection refused!", host=host, port=port)
                )
            elif get_errno(err) in (socket.EAI_NODATA, socket.EAI_NONAME):
                raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Is the host address correct?", host=host, port=port)
                )
            raise ValidationError(_(
                    "Could not establish a connection to %(host)s:%(port)s. "
                    "Error returned: %(error)s",
                    host=host, port=port, error=err)
                )
        finally:
            t.cancel()
    return _connectable

# Network related forms
class AddNetwork(FormBase):
    title            = _("Add Network")
    name             = TextField(_("Name"), validators=[Required()],
                        description=_("Pretty name of the network. For "
                                      "example \"Freenode\"."))
    host             = TextField(_("Host"), validators=[Required(),
                                                        Connectable('port')],
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
                                                        Connectable('port')],
                        description=_("The hostname of the network. For the "
                                      "example above \"irc.freenode.net\"."))
    port             = IntegerField(_("Port"), validators=[
                        Required(), NumberRange(min=1, max=65535)],
                        description=_("The network port number. For the "
                                      "example above \"6667\"."), default=6667)
    slug             = TextField(_("Slug"), validators=[Required()],
                        description=_("The url part of the network"))


class DeleteNetwork(_DBBoundForm):
    title            = _("Delete Network")
    id               = HiddenField(validators=[Required()])
