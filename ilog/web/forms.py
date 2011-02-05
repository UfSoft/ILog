# -*- coding: utf-8 -*-
"""
    ilog.web.forms
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""


import eventlet
from flask import flash
from flaskext.babel import gettext as _
eventlet.import_patched('flaskext.wtf.recaptcha')
eventlet.import_patched('flaskext.wtf.html5')
#eventlet.import_patched('flaskext.wtf')
from flaskext.wtf import *
from babel.dates import get_timezone_name
from pytz import timezone, common_timezones
from werkzeug.datastructures import MultiDict

from .application import cache

skip_zones = (
   'America/Argentina/Salta',
   'Asia/Kathmandu',
   'America/Matamoros',
   'Asia/Novokuznetsk',
   'America/Ojinaga',
   'America/Santa_Isabel',
   'America/Santarem'
)

@cache.memoize(3600)
def build_timezones(locale=None):
    print 'Building TimeZones'
    timezones = {}
    for tz in common_timezones:
        if tz.startswith('Etc/') or tz.startswith('GMT') or tz in skip_zones:
            continue
        timezones[get_timezone_name(timezone(tz), locale=locale)] = tz
    for key in sorted(timezones.keys()):
        yield timezones[key], key

class FormBase(Form):
    def __init__(self, formdata=None, *args, **kwargs):
        if formdata and not isinstance(formdata, MultiDict):
            formdata = MultiDict(formdata)
        super(FormBase, self).__init__(formdata, *args, **kwargs)

    def validate(self, extra_validators=None):
        rv = super(Form, self).validate()
        if 'csrf' in self.errors:
            flash(_("Form Token Is Invalid. You MUST have cookies enabled."),
                  "error")
        return rv

class LoginForm(FormBase):
    title       = _("Please Authenticate")
    username    = TextField(_("Username"), validators=[Required()],
                            description=_("Your username"))
    password    = PasswordField(_("Password"), validators=[Required()],
                                description=_("Your password"))

