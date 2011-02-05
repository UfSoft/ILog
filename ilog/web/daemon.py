# -*- coding: utf-8 -*-
"""
    ilog.daemon
    ~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from eventlet.hubs import use_hub, get_hub
import eventlet
import time
use_hub('zeromq')
from eventlet import debug, wsgi
debug.hub_blocking_detection(True, 0.5)

import logging
from giblets import ComponentManager
from ilog.common.daemonbase import BaseDaemon, BaseOptionParser

class FilelikeLogger(object):
    LOG_FORMAT = ('%(client_ip)s "%(request_line)s"'
                  ' %(status_code)s %(body_length)s %(wall_seconds).6f secs')

    def __init__(self):
        self.log = logging.getLogger('ilog.SERVE')

    def write(self, line):
        self.log.info(line.strip())

class Daemon(BaseDaemon):

    def __init__(self, serve_host="127.0.0.1", serve_port=5000, **kwargs):
        super(Daemon, self).__init__(**kwargs)
        self.serve_host = serve_host
        self.serve_port = serve_port

    def prepare(self):
        super(Daemon, self).prepare()

    @classmethod
    def cli(cls):
        parser = BaseOptionParser()
        parser.add_option('-H', '--hostname', default="127.0.0.1",
                          help="Hostname or IP to bind the webserver to.")
        parser.add_option('-P', '--port', default=5000, type="int",
                          help="Port number to bind the webserver to.")
        (options, args) = parser.parse_args()

        if args:
            parser.print_help()
            print
            parser.exit(1, "no args should be passed, only the available "
                        "options\n")

        cli = cls(serve_host=options.hostname, serve_port=options.port,
                  pidfile=options.pidfile, logfile=options.logfile,
                  detach_process=options.detach_process, uid=options.uid,
                  gid=options.gid, working_directory=options.working_dir,
                  loglevel=options.loglevel)
        return cli.run_daemon()

    def run(self):
        from ilog.web.application import app
        from ilog.common.signals import daemonized, running
        logging.getLogger(__name__).info("Webserver Daemon Running")
        daemonized.send(self)
        eventlet.spawn(
            wsgi.server,
            eventlet.listen((self.serve_host, self.serve_port)),
            app.wsgi_app,
            log=FilelikeLogger(),
            log_format=FilelikeLogger.LOG_FORMAT
        )
        running.send(self)
        while True:
            eventlet.sleep(1)

    def exit(self):
        self.exited = False
        from ilog.web.application import app
        from ilog.common.signals import undaemonized, shutdown
        logging.getLogger(__name__).info("Webserver Daemon Exiting...")
        def on_web_shutdown(sender):
            logging.getLogger(__name__).info("Webserver Daemon Quitting...")
            undaemonized.send(self)
            self.exited = True
        shutdown.connect(on_web_shutdown)
        logging.getLogger(__name__).debug("Shutdown webserver")
        app.shutdown()
        while not self.exited:
            # Waiting for everyhting to finish up...
            pass
        time.sleep(0.4)

def start_daemon():
    return Daemon.cli()

if __name__ == '__main__':
    start_daemon()
