#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2009 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

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
      platforms="OS Independent - Anywhere Eventlet, ZMQ, Eventlet and "
                "GStreamer is known to run.",
      keywords = "Eventlet ZMQ Gstreamer Audio Network Monitor",
      packages = find_packages(),
      include_package_data = True,
      package_data = {
        'ilog': ['*.cfg']
      },
      install_requires = [
        "Distribute", "giblets>=0.2.1", "blinker>=1.1",
        "pyzmq>=2.1.0,==2.1.0dev",
      ],
      message_extractors = {
        'ilog': [
            ('**.py', 'python', None),
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
