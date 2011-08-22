# -*- coding: utf-8 -*-
"""
    ilog.daemon
    ~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import gevent
import gevent.monkey
gevent.monkey.patch_all()
from gevent import wsgi, pool

import logging
from st.daemon import BaseDaemon, BaseOptionParser
from ilog import __web_bin_name__, __package_name__, __version__

class FilelikeLogger(object):
    LOG_FORMAT = ('%(client_ip)s "%(request_line)s"'
                  ' %(status_code)s %(body_length)s %(wall_seconds).6f secs')

    def __init__(self):
        self.log = logging.getLogger('ilog.SERVE')

    def write(self, line):
        self.log.info(line.strip())

class Daemon(BaseDaemon):

    LOG_FMT = '%(asctime)s,%(msecs)03.0f [%(name)-30s][%(levelname)-8s] %(message)s'

    def __init__(self, serve_host="127.0.0.1", serve_port=5000,
                 use_reloader=False, **kwargs):
        super(Daemon, self).__init__(**kwargs)
        self.serve_host = serve_host
        self.serve_port = serve_port
        self.use_reloader = use_reloader

    def prepare(self):
        super(Daemon, self).prepare()

    @classmethod
    def cli(cls):
        parser = BaseOptionParser(__package_name__, __version__)
        parser.add_option('-H', '--hostname', default="127.0.0.1",
                          help="Hostname or IP to bind the webserver to.")
        parser.add_option('-P', '--port', default=5000, type="int",
                          help="Port number to bind the webserver to.")
        parser.add_option('--use-reloader', default=False, action="store_true",
                          help="Use Werkzeug's reloader. DO NOT USE THIS IN "
                               "PRODUCTION!!!")
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
                  loglevel=options.loglevel, use_reloader=options.use_reloader,
                  process_name=__web_bin_name__)
        return cli.run_daemon()

    def run(self):
        from ilog.web.application import app
        from ilog.common.signals import daemonized, running
        logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
        logging.getLogger('migrate').setLevel(logging.INFO)
        logging.getLogger(__name__).info("Webserver Daemon Running")
        daemonized.send(self)
        def start_serving():
            wsgi.WSGIServer(
                (self.serve_host, self.serve_port),
                app,
                log=FilelikeLogger(),
                spawn=pool.Pool(10000) # do not accept more than 10000 connections
            ).serve_forever()

        if self.use_reloader:
            import werkzeug.serving
            start_serving = werkzeug.serving.run_with_reloader(start_serving)

        logging.getLogger(__name__).info("before spawning serve")
        serve = gevent.spawn(start_serving)
        logging.getLogger(__name__).info("after spawning serve")
        running.send(self)
        logging.getLogger(__name__).info("running signal sent")

        serve.join()

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

def start_daemon():
    return Daemon.cli()

if __name__ == '__main__':
    start_daemon()
