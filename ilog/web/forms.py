# -*- coding: utf-8 -*-
"""
    ilog.web.forms
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""


import logging
import gevent
try:
    from pytz.gae import pytz
except ImportError:
    import pytz
from flask import flash, Markup
from flaskext.babel import gettext as _
from flaskext.wtf import *
from babel.dates import get_timezone_name
from werkzeug.datastructures import MultiDict

from ilog.database.models import Account, AccountProvider, EMailAddress
from .application import g, cache, babel, get_locale
from .permissions import admin_permission, require_permissions

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
    return [(timezones[key], key) for key in sorted(timezones.keys())]

class FormBase(Form):
    def __init__(self, formdata=None, *args, **kwargs):
        if formdata and not isinstance(formdata, MultiDict):
            formdata = MultiDict(formdata)
        super(FormBase, self).__init__(formdata, *args, **kwargs)

    def validate(self, extra_validators=None):
        rv = super(Form, self).validate()
        errors = []
        if 'csrf' in self.errors:
            del self.errors['csrf']
            errors.append(
                _("Form Token Is Invalid. You MUST have cookies enabled.")
            )
        for field_name, ferrors in self.errors.iteritems():
            errors.append(
                "<b>%s:</b> %s" % (
                self._fields[field_name].label.text, '; '.join(ferrors)
            ))
        if errors:
            flash(Markup(_("Errors:") + "<ul>%s</ul>" %
                "".join(["<li>%s</li>" %e for e in errors])
            ), "error")
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
        if Account.query.by_username(field.data):
            raise ValidationError(_("The username \"%(username)s\" is already "
                                    "in use. Please choose another one.",
                                    username=field.data))

class _DBBoundForm(FormBase):
    def __init__(self, db_entry=None, formdata=None, *args, **kwargs):
        self.db_entry = db_entry
        super(_DBBoundForm, self).__init__(formdata, *args, **kwargs)

    def process(self, formdata=None, *args, **kwargs):
        fields = {}
        for name in self._fields.keys():
            value = getattr(self.db_entry, name, None)
            if value:
                self._fields[name].value_from_db = fields[name] = value
        fields.update(kwargs)
        super(_DBBoundForm, self).process(formdata, *args, **fields)

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

class ProfileForm(_DBBoundForm):
    title           = _("My Profile")
    id              = HiddenField(validators=[Required()])
    username        = TextField(_("Username"), validators=[Required()])
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
                    "successfully.", provider=entry.provider), "ok")
            self.db_entry.providers.remove(entry)

    def validate_display_name(self, field):
        if field.data != self.db_entry.display_name:
            account = Account.query.filter_by(display_name=field.data).first()
            if account and account.id!=self.db_entry.id:
                display_name = field.data
                field.data = self.db_entry.display_name
                raise ValidationError(_(
                    "Display name \"%(display_name)s\" already in use",
                    display_name=display_name
                ))

    @require_permissions(admin_permission)
    def validate_username(self, field):
        if field.data and field.data != self.db_entry.username:
            account = Account.query.by_username(field.data)
            if account and account.id != self.db_entry.id:
                raise ValidationError(
                    _("The username \"%(username)s\" is already in use. "
                      "Please choose a different one.", username=field.data)
                )


    def validate(self):
        if not self.username.data:
            # In case the user is not an admin. The field will be disabled,
            # so, no data is submitted for it.
            self.username.data = self.db_entry.username
        if self.locale.data is None:
            # In case there's only one locale, then the field is not
            # rendered. Re-set the default.
            self.locale.data = self.db_entry.locale
        return super(ProfileForm, self).validate()

class AccountEmails(_DBBoundForm):
    title           = _("Email Addresses")

    preferred   = QuerySelectField("preferred", validators=[Required()])
    update      = SubmitField(_("Update"))

    def __init__(self, db_entry=None, formdata=None, *args, **kwargs):
        super(AccountEmails, self).__init__(db_entry, formdata, *args, **kwargs)
        self.preferred.query_factory = lambda: self.db_entry.email_addresses

    def validate_preferred(self, field):
        if self.update.data is False:
            return
        for email in self.db_entry.email_addresses:
            email.preferred = email is field.data
            if email.preferred:
                flash(_(
                    "Your preferred email address is now \"%(address)s\"",
                    address=email.address
                ))

class DeleteEmailForm(_DBBoundForm):
    title           = _("Remove Email Address")

    address      = HiddenField("address")
    confirm      = SubmitField(_("Confirm"))
    cancel       = SubmitField(_("Cancel"))

    def __init__(self, db_entry=None, formdata=None, *args, **kwargs):
        super(DeleteEmailForm, self).__init__(db_entry, formdata, *args, **kwargs)


class AddEmailForm(_DBBoundForm):
    title           = _("Add Email Address")

    address      = TextField(_("Email Address"), validators=[Required(), Email()])
    submit       = SubmitField(_("Submit"))

    def validate_address(self, field):
        if EMailAddress.query.get(field.data):
            raise ValidationError(
                _("\"%(address)s\" is already in use.", address=field.data)
            )



class ExtraEmailForm(FormBase):
    title           = _("Extra Email Address")
    email_address   = HiddenField(validators=[Required()])

class DeleteAccountForm(_DBBoundForm):
    title           = _("Delete Account")
    id              = HiddenField(validators=[Required()])
