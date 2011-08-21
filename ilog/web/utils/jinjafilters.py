# -*- coding: utf-8 -*-
"""
    ilog.web.utils.jinjafilters
    ~~~~~~~~

    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""
# http://twistedmatrix.com/trac/attachment/ticket/3844/parse-irc-formatting.diff

import copy
from jinja2 import Markup, escape

IRC_COLORS = {
    0:  "white",
    1:  "black",
    2:  "dark-blue",
    3:  "dark-green",
    4:  "red",
    5:  "dark-red",
    6:  "dark-magenta",
    7:  "orange",
    8:  "yellow",
    9:  "green",
    10: "dark-cyan",
    11: "cyan",
    12: "blue",
    13: "magenta",
    14: "dark-grey",
    15: "light-grey"
}

class PartAttributes(object):
    def __init__(self, attributes=None):
        if attributes is None:
            attributes = set()
        self.attributes = attributes
        self.foreground = None
        self.background = None

    def toggle(self, attr):
        if attr in self.attributes:
            self.attributes.remove(attr)
        else:
            self.attributes.add(attr)

    def copy(self):
        return copy.deepcopy(self)

    def reset_colors(self):
        self.foreground = None
        self.background = None

    def has_colors(self):
        return self.foreground is not None or self.background is not None

    def __nonzero__(self):
        if self.attributes:
            return True
        elif self.foreground is not None or self.background is not None:
            return True
        return False

    def __repr__(self):
        attrs = list(self.attributes)
        if self.has_colors():
            attrs.append('color=[%s,%s]' % (self.foreground, self.background))
        if attrs:
            return " attributes=(%s)" % ', '.join(attrs).rstrip()
        return ' ' + ', '.join(attrs).rstrip()
        return '<%s%s>' % (type(self).__name__, attrs.rstrip())

class PartState(object):

    formating = {
        '\x0f': 'off',
        '\x02': 'bold',
        '\x03': 'color',
        '\x1d': 'italic',
        '\x16': 'reverse',
        '\x1f': 'underline'
    }

    def __init__(self, strip=False):
        self.strip = strip
        self.state = "text"
        self._buffer = ""
        self._attrs = PartAttributes()
        self._result = []


    def complete(self):
        self.emit()
        return FormattedIrcMessage(self._result)

    def process(self, char):
        getattr(self, 'process_%s' % self.state)(char)

    def emit(self):
        if self.strip:
            self._attrs = PartAttributes()

        if self._buffer:
            self._result.append(Part(self._attrs, self._buffer))
            self._buffer = ''
        self._attrs = self._attrs.copy()

    def process_text(self, char):
        formatting = self.formating.get(char, None)
        if formatting == "color":
            self.emit()
            self.state = "foreground"
        else:
            if formatting is None:
                self._buffer += char
            else:
                if self._buffer:
                    self.emit()

                if formatting == "off":
                    self._attrs = PartAttributes()
                else:
                    self._attrs.toggle(formatting)

    def process_foreground(self, char):
        # Color codes may only be a maximum of two characters.
        if char.isdigit() and len(self._buffer) < 2:
            self._buffer += char
        else:
            if self._buffer:
                self._attrs.foreground = int(self._buffer)
            else:
                # If there were no digits, then this has been an empty color
                # code and we can reset the color state.
                self._attrs.reset_colors()

            if char == ',' and self._buffer:
                # If there's a comma and it's not the first thing, move on to
                # the background state.
                self._buffer = ''
                self.state = 'background'
            else:
                # Otherwise, this is a bogus color code, fall back to text.
                self._buffer = ''
                self.state = 'text'
                self.emit()
                self.process(char)

    def process_background(self, char):
        # Color codes may only be a maximum of two characters.
        if char.isdigit() and len(self._buffer) < 2:
            self._buffer += char
        else:
            if self._buffer:
                self._attrs.background = int(self._buffer)
                self._buffer = ''

            self.emit()
            self.state = 'text'
            self.process(char)

class Part(object):
    def __init__(self, attributes, text):
        self.attributes = attributes
        self.text = text

    def __repr__(self):
        return '<%s%r text="%s">' % (type(self).__name__, self.attributes, self.text)

    def __html__(self):
        output = '<span'
        if self.attributes:
            classes = []
            if self.attributes.foreground is not None:
                classes.append("irc-fg-%s" % IRC_COLORS[self.attributes.foreground])
            if self.attributes.background is not None:
                classes.append("irc-bg-%s" % IRC_COLORS[self.attributes.background])
            for attribute in self.attributes.attributes:
                classes.append("irc-%s" % attribute)
            output += ' class="%s"' % ' '.join(classes)
        return "%s>%s</span>" % (output, escape(self.text))

class FormattedIrcMessage(object):
    def __init__(self, parts):
        self.parts = parts

    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, self.parts)

    def __html__(self):
        output = ""
        for part in self.parts:
            output += part.__html__()
        return output

def format_irc_message(message, strip=False):
    state = PartState(strip)
    for char in message:
        state.process(char)
#    print state.complete()
    return Markup(state.complete())

if __name__ == '__main__':
    txts = [
        "Some now \x02bold\x02 text\n",
        "Some now \x031,2colored\x03 text\n",
        "\x0300,01BLACK BG\x03",
        "\x0301,00WHITE BG\x03",
        "\x0305DARK RED \x03\x0306DARK MAGENTA \x03\x0307ORANGE \x03\x0308YELLOW \x03\x0309GREEN \x03\x0310DARK CYAN \x03\x0311CYAN \x03\x0312BLUE \x03\x0313MAGENTA \x03\x0314DARK GREY\x03\x0315 LIGHT GREY \x03",
        "\x0300WFG\x03 \x0301BFG \x03\x0302DBFG\x03 \x0303DGFG \x03\x0304RED\x03",
        "\x02BOLD\x02 \x1DITALIC\x1D \x1FUNDERLINE\x1F",
        "\x0315LIGHT GREY\x03",
        "\x0314LIGHT GREY\x03",
        "\x0314DARK GREY\x03",
        "\x0313MAGENTA\x03",
        "\x0312BLUE\x03",
        "\x0311CYAN\x03",
        "\x0310DARK CYAN\x03",
        "\x0309GREEN\x03",
        "\x0308YELLOW\x03",
        "\x0307ORANGE\x03",
        "\x0306DARK MAGENTA\x03",
        "\x0305DARK RED\x03",
        "\x0304RED\x03",
        "\x0303DARK GREEN\x03",
        "\x0302DARK BLUE\x03",
        "\x0301BLACK\x03",
        "\x0300WHITE\x03"
    ]
    txts = [
#        u'sakha.v-irc.ru Message of the Day -',
u'\x0313,5*\x035 -----------------\x038__\x035--------\x038__\x035-----\x038___________\x035--\x038_____\x035---------------------\x0313*',
#u'\x0313,5* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * \x0313',
#u'\x0313,5*\x035 -----------------\x038\\ \\\x035------\x038/ /\x035----\x038|_\x035---\x038_| ___ \\/\x035--\x038__ \\\x035--------------------\x0313*',
#u'\x0313,5* \x035 - - - \x037\u0414 \u041e \u0411 \u0420 \u041e  \u041f \u041e \u0416 \u0410 \u041b \u041e \u0412 \u0410 \u0422 \u042c  \u041d \u0410  \u041d \u0410 \u0428  \u0421 \u0415 \u0420 \u0412 \u0415 \u0420\x035- - - - - -\x0313*',
#u"\x0313,5*\x035 --------\x031(='.'=)\x035----\x038\\ \\\x035--\x038/ / |___|\x035--\x038| | |\x035----\x038/ | |\x035------\x031(='.'=)\x035-----------\x0313*",
#u'\x0313,5*\x035 --------\x031( )_( )\x035---\x038\\ \\\x035----\x038/ / ___\x035---\x038| | | |_/ /| /\x035--\x038\\/\x035--\x031( )_( )\x035-----------\x0313*',
#u'\x0313,5*\x035 --------\x031(")_(")\x035-----\x038\\ \\/ /\x035--------\x038_| |_| |\\ \\ | \\__/\\\x035--\x031(")_(")\x035-----------\x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035 ---------------------\x038\\__/\x035---------\x038\\___/\\_| \\_| \\____/\x035--------------------\x0313*',
#u'\x0313,5*\x038 \x1f\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u0438\u0432\u043d\u044b\u0435 \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u044b:\x1f \x035--------------------------------------------- \x0313*',
#u'\x0313,5*\x038 \x1f\u041f\u0440\u0430\u0432\u0438\u043b\u0430 \u0441\u0435\u0442\u0438:\x1f \x035---------------------------------------------------------- \x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315Network Admin:\x035-\x0315admin@v-irc.ru \x035----------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315/rules \x035 ------------------------------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1fhttp://www.v-irc.ru/rules_network.html\x1f\x035 ------ \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x038 \x1f\u041f\u0435\u0440\u0435\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u043a\u0430 \u043f\u043e \u043f\u043e\u0440\u0442\u0430\u043c:\x1f \x035----------------------------------------------- \x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6665\x1f\x0315: cp_utf \x035---------------------------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6666\x1f\x0315: cp_dos\x03\x035,5----------------------------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6667\x1f\x0315: CP1251 (Windows)\x03\x035,5------------------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6669\x1f\x0315: ISO-8859-5 (Macintosh) \x03\x035,5-----------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6668\x1f\x0315: KOI8-R \x03\x035,5---------------------------------\x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6675\x1f\x0315: cp_utf \x035---------------------------------\x0313*',
#u'\x0313,5*\x038 \x1f\u041f\u043e\u0440\u0442\u044b \u0434\u043b\u044f \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439 \u043c\u043e\u0431\u0438\u043b\u044c\u043d\u044b\u0445 IRC \u043a\u043b\u0438\u0435\u043d\u0442\u043e\u0432:\x1f \x035------------------------ \x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6676\x1f\x0315: cp_dos\x03\x035,5----------------------------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6677\x1f\x0315: CP1251 (Windows)\x03\x035,5------------------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6679\x1f\x0315: ISO-8859-5 (Macintosh)\x03\x035,5------------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1f6678\x1f\x0315: KOI8-R\x03\x035,5----------------------------------\x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315HelpServ, NickServ, ChanServ,\x035-----------------\x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315MemoServ, HostServ, BotServ.\x035------------------\x0313*',
#u'\x0313,5*\x038 \x1fIRC \u0441\u0435\u0440\u0432\u0435\u0440 V-IRC \u043e\u0431\u043b\u0430\u0434\u0430\u0435\u0442 \u0440\u044f\u0434\u043e\u043c \u0441\u043b\u0443\u0436\u0431:\x1f \x035--------------------------------- \x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315/msg HelpServ help \x035---------------------------\x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x038 \x1f\u041f\u043e\u043c\u043e\u0449\u044c \u043f\u043e \u043a\u043e\u043c\u0430\u043d\u0434\u0430\u043c \u0441\u043b\u0443\u0436\u0431:\x1f \x035---------------------------------------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x038 \x1f\u0414\u043b\u044f \u043e\u0442\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u0444\u0438\u043b\u044c\u0442\u0440\u0430 \u0446\u0435\u043d\u0437\u0443\u0440\u044b \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u0443:\x1f\x035 ----------------------- \x0313*',
#u'\x0313,5*\x038 \x1f\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c \u0440\u0443\u0441\u0441\u043a\u0438\u0439 \u044f\u0437\u044b\u043a \u043e\u0442 \u0441\u043b\u0443\u0436\u0431:\x1f \x035-------------------------------------- \x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315/msg NickServ SET LANGUAGE 11\x035 --------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315/mode nick -G \x035--------------------------------\x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1fhttp://www.v-irc.ru/\x1f\x035 ------------------------ \x0313*',
#u'\x0313,5*\x038 \x1f\u041d\u0430\u0448 \u0441\u0430\u0439\u0442:\x1f\x035 -------------------------------------------------------------- \x0313*',
#u'\x0313,5*\x038 \x1f\u041d\u0430\u0448 \u0444\u043e\u0440\u0443\u043c:\x1f\x035 ------------------------------------------------------------- \x0313*',
#u'\x0313,5*\x038 \x1f\u0413\u0430\u043b\u0435\u0440\u0435\u044f:\x1f\x035 --------------------------------------------------------------- \x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1fhttp://www.arsanna.com/gallery/\x1f\x035 ------------- \x0313*',
#u'\x0313,5*\x035 -------------------------- \x037\x1fhttp://forum.v-irc.ru/\x1f\x035 ---------------------- \x0313*',
#u'\x0313,5*\x035 -------------------------- \x0315sakha.v-irc.ru\x035 ------- \x0315\u0433.\u042f\u043a\u0443\u0442\u0441\u043a\x035 ------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x038 \x1f\u0414\u043b\u044f \u0432\u0445\u043e\u0434\u0430 \u0432 \u043d\u0430\u0448\u0443 \u0441\u0435\u0442\u044c, \u043c\u043e\u0436\u043d\u043e \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u0441\u0435\u0440\u0432\u0435\u0440\u0430:\x1f\x035 --------------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x038 \u041e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u044b\u0435:\x035 ----------------------------------------------------------- \x0313*',
#u'\x0313,5*\x038 \x1f\u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0430\u0435\u043c \u0412\u0430\u0441 \u043d\u0430 \u043d\u0430\u0448\u0438 \u043a\u0430\u043d\u0430\u043b\u044b:\x1f\x035 ----------------------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#V-IRC\x1f \x035-------------------\x0315\u041e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u044b\u0439 \u043a\u0430\u043d\u0430\u043b \u0441\u0435\u0442\u0438\x035----------------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#Help\x1f \x035--------------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e IRC\x035-------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#ARSAnna.com\x1f \x035-------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u0440\u0442\u0430\u043b\u0430 http://www.ARSAnna.com\x035--------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x038 \u0421\u043b\u0443\u0436\u0435\u0431\u043d\u044b\u0435:\x035 ------------------------------------------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#Support\x1f \x035-----------------\x0315\u0422\u0435\u0445\u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 \u043f\u043e \u043f\u043e\u0440\u0442\u0430\u043b\u0443 www.ARSAnna.com\x035------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#Abuse\x1f \x035-------------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u0440\u0438\u0435\u043c\u0430 \u0436\u0430\u043b\u043e\u0431 \u0438 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0439\x035------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#vHost\x1f \x035-------------------\x0315\u041a\u0430\u043d\u0430\u043b \u0432\u0438\u0440\u0442\u0443\u0430\u043b\u044c\u043d\u044b\u0445 \u0445\u043e\u0441\u0442\u043e\u0432\x035--------------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#SMS-help\x1f \x035----------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e \u0421\u041c\u0421 \u0441\u0435\u0440\u0432\u0438\u0441\u0443\x035------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#ScriptHelp\x1f \x035--------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e \u0441\u043a\u0440\u0438\u043f\u0442\u0430\u043c\x035--------------------- \x0313*',
#u'\x0313,5*\x038 \u0420\u0430\u0437\u0432\u043b\u0435\u043a\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0435:\x035 ------------------------------------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#boltalka\x1f \x035----------------\x0315\u041f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u044b\u0439 \u043a\u0430\u043d\u0430\u043b \u043e\u0431\u0449\u0435\u043d\u0438\u044f\x035--------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#\u043e\u044220\u0434\u043e35\x1f \x035----------------\x0315\u041a\u0430\u043d\u0430\u043b \u0434\u043b\u044f \u0437\u0440\u0435\u043b\u043e\u0433\u043e \u043f\u043e\u043a\u043e\u043b\u0435\u043d\u0438\u044f\x035------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#\u0440\u043e\u0432\u0435\u0441\u043d\u0438\u043a\u0438\x1f \x035---------------\x0315\u041c\u043e\u043b\u043e\u0434\u0435\u0436\u043d\u044b\u0439 \u043a\u0430\u043d\u0430\u043b\x035----------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#pub\x1f \x035---------------------\x0315\u041e\u0431\u0449\u0435\u043d\u0438\u0435 \u0431\u0435\u0437 \u0433\u0440\u0430\u043d\u0438\u0446!\x035-------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#anekdot\x1f \x035-----------------\x0315\u041a\u0430\u043d\u0430\u043b \u0430\u043d\u0435\u043a\u0434\u043e\u0442\u043e\u0432\x035------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#azart\x1f \x035-------------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u0440\u0438\u0437\u043e\u0432\u043e\u0439 \u0432\u0438\u043a\u0442\u043e\u0440\u0438\u043d\u044b\x035--------------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#holdem\x1f \x035------------------\x0315\u041a\u0430\u043d\u0430\u043b \u043b\u044e\u0431\u0438\u0442\u0435\u043b\u0435\u0439 \u043f\u043e\u043a\u0435\u0440\u0430\x035----------------------- \x0313*',
#u'\x0313,5*\x038 \u0418\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u043e\u043d\u043d\u044b\u0435:\x035 -------------------------------------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#OptiNet\x1f \x035-----------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e \u0442\u0435\u0445\u043d\u043e\u043b\u043e\u0433\u0438\u0438 Ethernet\x035---------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#info\x1f \x035--------------------\x0315\u041e\u0441\u043d\u043e\u0432\u043d\u043e\u0439 \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u043e\u043d\u043d\u044b\u0439 \u043a\u0430\u043d\u0430\u043b\x035---------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#sakhatelecom\x1f \x035------------\x0315\u0424\u0438\u043b\u0438\u0430\u043b \xab\u0421\u0430\u0445\u0430\u0442\u0435\u043b\u0435\u043a\u043e\u043c\xbb \u041e\u0410\u041e \xab\u0414\u0430\u043b\u044c\u0441\u0432\u044f\u0437\u044c\xbb\x035--------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#ip-tv\x1f \x035-------------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e \u0446\u0438\u0444\u0440\u043e\u0432\u043e\u043c\u0443 \u0442\u0435\u043b\u0435\u0432\u0438\u0434\u0435\u043d\u0438\u044e\x035-------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#mobhelp\x1f \x035-----------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e \u043c\u043e\u0431\u0438\u043b\u044c\u043d\u044b\u043c IRC \u043a\u043b\u0438\u0435\u043d\u0442\u0430\u043c\x035------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#web-help\x1f \x035----------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e \u0432\u0435\u0431-\u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044e\x035--------- \x0313*',
#u'\x0313,5*\x038 \u0418\u0433\u0440\u043e\u0432\u044b\u0435:\x035 --------------------------------------------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#bots\x1f \x035--------------------\x0315\u041a\u0430\u043d\u0430\u043b \u043f\u043e\u043c\u043e\u0449\u0438 \u043f\u043e IRC \u0431\u043e\u0442\u0430\u043c\x035-------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#dota\x1f \x035--------------------\x0315Warcraft III Dota All Stars\x035------------------ \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#cs_lan_adsl\x1f \x035-------------\x0315Counter-Strike\x035------------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#la2\x1f \x035---------------------\x0315LineAge 2\x035------------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#othermaps\x1f \x035---------------\x0315Warcraft III - Othermaps\x035--------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#wowpro\x1f \x035------------------\x0315World of Warcraft\x035---------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#tf2\x1f \x035---------------------\x0315Team Fortress 2\x035------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#css\x1f \x035---------------------\x0315Counter-Strike Source\x035------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#l4d2\x1f \x035--------------------\x0315Left for Dead\x035-------------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#hon\x1f \x035---------------------\x0315Heroes Of Newerth\x035---------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#ro\x1f \x035----------------------\x0315Ragnarok Online\x035------------------------------ \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#fifa\x1f \x035--------------------\x0315Football simulator\x035--------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#cod4mw2\x1f \x035-----------------\x0315Call of Duty MW2\x035----------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#gta\x1f \x035---------------------\x0315Grand Theft Auto\x035----------------------------- \x0313*',
#u'\x0313,5*\x035-\x037 \x1f#lfs_racers\x1f \x035--------------\x0315Live For Speed\x035------------------------------- \x0313*',
#u'\x0313,5*\x035 ------------------------------------------------------------------------ \x0313*',
    ]
    for txt in txts:
        print txt
        formatted = format_irc_message(txt)
        print formatted + '\n'
