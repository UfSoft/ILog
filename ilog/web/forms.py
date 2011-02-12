# -*- coding: utf-8 -*-
"""
    ilog.web.forms
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""


import logging
import eventlet
from flask import flash, Markup
from flaskext.babel import gettext as _
eventlet.import_patched('json')
eventlet.import_patched('flaskext.wtf.recaptcha')
eventlet.import_patched('flaskext.wtf.html5')
#eventlet.import_patched('flaskext.wtf')
from flaskext.wtf import *
eventlet.import_patched('babel')
eventlet.import_patched('babel.dates')
from babel.dates import get_timezone_name
pytz = eventlet.import_patched('pytz')
#eventlet.import_patched('pytz.timezone')
#eventlet.import_patched('pytz.common_timezones')
#from pytz import timezone, common_timezones
from werkzeug.datastructures import MultiDict

from ilog.database.models import Account, AccountProvider
from .application import cache, babel, get_locale

log = logging.getLogger(__name__)

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
    log.debug("Building Timezones for locale: %s", locale)
    timezones = {}
    for tz in pytz.common_timezones:
        if tz.startswith('Etc/') or tz.startswith('GMT') or tz in skip_zones:
            continue
        timezones[get_timezone_name(pytz.timezone(tz), locale=locale)] = tz
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
    remember_me = BooleanField(_("Remember Me"), description=_(
                                "Keep me signed-in for future visits."))

    def validate_username(self, field):
        account = Account.query.by_username(username=field.data)
        if not account:
            raise ValidationError(_("The account \"%(account)s\" is not known.",
                                    account=field.data))

    def validate_password(self, field):
        account = Account.query.by_username(username=self.data['username'])
        if account and not account.check_password(field.data):
            raise ValidationError(_("Password does not match."))

class RegisterForm(FormBase):
    title            = _("Please Register")
    identifier       = HiddenField(validators=[Required()])
    provider         = HiddenField(validators=[Required()])
    username         = TextField(_("Username"), validators=[Required()])
    email            = TextField(_("Email"), validators=[Required(), Email()])
    display_name     = TextField(_("Display Name"), validators=[Required()])
    password         = PasswordField(_("Password"), description=_(
                        "Please provide a password if you wish to sign-in "
                        "directly on %(app)s and not the account you're "
                        "using to register.", app='ILog'))
    password_confirm = PasswordField(_("Confirm Password"), validators=[
                        EqualTo('password', _("Passwords do not match"))])

    def validate_identifier(self, field):
        if AccountProvider.query.get(field.data):
            raise ValidationError(_("An account using this provider is already "
                                    "registred with us."))

    def validate_username(self, field):
        if Account.query.filter_by(username=field.data).first():
            raise ValidationError(_("The username \"%(username)s\" is already "
                                    "in use. Please choose another one.",
                                    username=field.data))

class _UserBoundForm(FormBase):
    def __init__(self, db_entry=None, formdata=None, *args, **kwargs):
        self.db_entry = db_entry
        super(_UserBoundForm, self).__init__(formdata, *args, **kwargs)

    def process(self, formdata=None, *args, **kwargs):
        fields = {}
        for name in self._fields.keys():
            value = getattr(self.db_entry, name, None)
            if value:
                fields[name] = value
        fields.update(kwargs)
        super(_UserBoundForm, self).process(formdata, *args, **fields)

def select_multi_checkbox(field, ul_class='multi-checkbox', **kwargs):
    from wtforms.widgets import html_params

    kwargs.setdefault('type', 'checkbox')
    field_id = kwargs.pop('id', field.id)
    html = [u'<ul %s>' % html_params(id=field_id, class_=ul_class)]
    for value, label, checked in field.iter_choices():
        choice_id = u'%s-%s' % (field_id, value)
        options = dict(kwargs, name=field.name, value=value, id=choice_id)
        if checked:
            options['checked'] = 'checked'
        html.append('<li>')
        html.append(u'<input %s /> ' % html_params(**options))
        html.append(u'<label %s>%s</label>' % (html_params(**options), label))
        html.append('</li>')
    html.append(u'</ul>')
    return Markup(u''.join(html))

class ProfileForm(_UserBoundForm):
    title           = _("My Profile")
    id              = HiddenField(validators=[Required()])
    username        = HiddenField(_("Username"), validators=[Required()])
#    username        = TextField(_("Username"))
    display_name    = TextField(_("Display Name"), validators=[Required()])
    timezone        = SelectField(_("Timezone"))
    locale          = SelectField(_("Locale"),
                        description=_("This will be the language ILog will be "
                                      "presented to you."))
    providers       = QuerySelectMultipleField(
        _("Account Providers"), get_label=lambda x: x.provider,
        widget=select_multi_checkbox,
        description=_("Unselected checkboxes will remove those providers from "
                      "your account"))

    password         = PasswordField(_("Password"), description=_(
                        "Please provide a password if you wish to sign-in "
                        "directly on %(app)s, ie, not using an account "
                        "provider", app='ILog'))
    password_confirm = PasswordField(_("Confirm Password"), validators=[
                        EqualTo('password', _("Passwords do not match"))])

    def __init__(self, db_entry=None, formdata=None, *args, **kwargs):
        super(ProfileForm, self).__init__(db_entry, formdata, *args, **kwargs)
        self.timezone.choices = build_timezones(get_locale())
        self.locale.choices = [
            (l.language, l.display_name) for l in babel.list_translations()
        ]
        self.providers.query_factory = lambda: self.db_entry.providers

    def validate_providers(self, field):
        providers_difference = self.db_entry.providers.difference(field.data)
        if len(self.db_entry.providers) < 2 and providers_difference:
            if self.db_entry.passwd_hash != "!":
                flash(_("From now on you must use your username and respective"
                        "password to authenticate."), "info")
            else:
                field.data = self.db_entry.providers
                raise ValidationError(
                    Markup("You <b>must</b> keep at least one account provider "
                           "at <b>all</b> times or you won't be able to "
                           "authenticate. Account provider not removed!")
                )
        for entry in providers_difference:
            flash(_("Your \"%(provider)s\" account provider was removed "
                    "sucessfully.", provider=entry.provider), "ok")
            self.db_entry.providers.remove(entry)

class ExtraEmailForm(FormBase):
    title           = _("Extra Email Address")
    email_address   = HiddenField(validators=[Required()])
