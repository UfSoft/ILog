# -*- coding: utf-8 -*-
"""
    ilog.common.convert
    ~~~~~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import chardet

def to_unicode(data, initial_encoding='utf8'):
    try:
        return initial_encoding, data.decode(initial_encoding)
    except UnicodeDecodeError:
        detected = chardet.detect(data)
        return to_unicode(data, detected['encoding'])

