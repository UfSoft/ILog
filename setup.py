#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
"""
    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from setuptools import setup, find_packages
import ilog

setup(name=ilog.__package_name__,
      version=ilog.__version__,
      author=ilog.__author__,
      author_email=ilog.__email__,
      url=ilog.__url__,
      download_url='http://python.org/pypi/%s' % ilog.__package_name__,
      description=ilog.__summary__,
      long_description=ilog.__description__,
      license=ilog.__license__,
      platforms="OS Independent - Anywhere Flask, Eventlet and is known to run.",
      keywords = "Eventlet ZMQ IRC Logging FLask",
      packages = find_packages(),
      include_package_data = True,
      package_data = {
        'ilog': ['*.cfg']
      },
      install_requires = [
        "Distribute",
        "giblets>=0.2.1",
        "blinker>=1.1",
        "pytz",
        "SQLAlchemy>=0.6.6",
        "Flask>=0.6.1",
        "Flask-Babel>=0.6",
        "Flask-Cache>=0.3.2",
        "Flask-Mail>=0.6.1",
        "Flask-Principal>=0.2.1",
        "Flask-WTF>=0.5.2",
        "pyzmq>=2.1.0,==2.1.0dev",
      ],
      extras_require = {
        "DEV": [
            "flask-lesscss>=0.9.2",
        ]
      },
      dependency_links = [
        "https://bitbucket.org/s0undt3ch/flask-lesscss/get/tip.tar.gz",
        "https://bitbucket.org/s0undt3ch/flask-principal-main/get/tip.tar.gz"
      ],
      message_extractors = {
        'ilog': [
            ('web/**.py', 'python', None),
            ('web/templates/**.html', 'jinja2', None),
            ('web/templates/**.txt', 'jinja2', None)
        ],
      },
      entry_points = """
      [console_scripts]
      ilog-web = ilog.web.daemon:start_daemon

      [distutils.commands]
      compile = babel.messages.frontend:compile_catalog
      extract = babel.messages.frontend:extract_messages
         init = babel.messages.frontend:init_catalog
       update = babel.messages.frontend:update_catalog
      """,
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Web Environment',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Utilities',
          'Topic :: Internet :: WWW/HTTP',
          'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
      ]
)
