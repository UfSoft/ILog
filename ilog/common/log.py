# -*- coding: utf-8 -*-
"""
    ilog.common.log
    ~~~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
import logging.handlers
from ilog import __package_name__

LoggingLoggerClass = logging.getLoggerClass()
logging.TRACE = 5
logging.GARBAGE = 1

class Logging(LoggingLoggerClass):
    def __init__(self, logger_name):
        LoggingLoggerClass.__init__(self, logger_name)

    def garbage(self, msg, *args, **kwargs):
        LoggingLoggerClass.log(self, 1, msg, *args, **kwargs)

    def trace(self, msg, *args, **kwargs):
        LoggingLoggerClass.log(self, 5, msg, *args, **kwargs)


def setup_logging(log_to_file=False):
    if logging.getLoggerClass() is not Logging:
        import pkg_resources
        format='%(asctime)s.%(msecs)03.0f '
        if 'dev' in pkg_resources.require(__package_name__)[0].version:
            format+='[%(name)-30s:%(lineno)-4s] '
        else:
            format='%(asctime)s.%(msecs)03.0f [%(name)-30s] '
        format += '%(levelname)-7.7s: %(message)s'

        formatter = logging.Formatter(format, '%H:%M:%S')

        logging.setLoggerClass(Logging)
        if log_to_file:
            handler = logging.handlers.RotatingFileHandler(
                log_to_file, "a", maxBytes=10*1024*1024, backupCount=3
            )
        else:
            import sys
            handler = logging.StreamHandler(sys.stdout)


        handler.setLevel(1)
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)

        logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
        logging.getLogger('migrate').setLevel(logging.INFO)
        logging.addLevelName(logging.TRACE, "TRACE")
        logging.addLevelName(logging.GARBAGE, "GARBAGE")
        logging.root.setLevel(1)

log_levels = {
    "none": logging.NOTSET,
    "info": logging.INFO,
    "warn": logging.WARN,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "debug": logging.DEBUG,
    "trace": logging.TRACE,
    "garbage": logging.GARBAGE
}

def set_loglevel(logger, loglevel):
    if not isinstance(loglevel, basestring):
        logger.setLevel(loglevel)
    else:
        logger.setLevel(log_levels[loglevel.lower()])
