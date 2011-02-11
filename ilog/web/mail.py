# -*- coding: utf-8 -*-
"""
    ilog.web.mail
    ~~~~~~~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import os
import cPickle
import logging
import eventlet
eventlet.import_patched('smtplib')
from eventlet.queue import Empty, PriorityQueue, Queue
from flaskext.mail import Mail, Message, email_dispatched
from ilog.common import component_manager
from ilog.common.interfaces import ComponentBase
from ilog.web.signals import webapp_setup_complete, webapp_shutdown

log = logging.getLogger(__name__)

class SendMessageTimeout(Exception):
    """Exception raised when sending a message takes too long."""

class EMailManager(ComponentBase):

    unsent_emails_pickle = 'unsent-emails.pickle'

    def activate(self):
        self.m_queue = PriorityQueue()
        self.e_queue = Queue()
        self.processing = self.q_prio = self.q_message = None

    def connect_signals(self):
        email_dispatched.connect(self.on_email_dispatched)
        webapp_setup_complete.connect(self.on_webapp_setup_complete)
        webapp_shutdown.connect(self.on_webapp_shutdown)

    def on_email_dispatched(self, message, app):
        log.trace("Email dispatched... %s", message)
        self.q_message = self.q_prio = None

    def on_webapp_setup_complete(self, app):
        self.smtp = Mail(app)
        self.load_unsent_messages()

    def load_unsent_messages(self):
        unsent_emails_count = 0
        try:
            unsend_emails = cPickle.load(open(self.unsent_emails_pickle, 'rb'))
            for priority, message in unsend_emails:
                unsent_emails_count += 1
                eventlet.spawn_after(1, self.send, message, priority)
            log.debug("Loaded %s unsent emails from file backup",
                      unsent_emails_count)
        except IOError:
            # File does not exist
            pass
        except Exception, err:
            raise

        try:
            os.unlink(self.unsent_emails_pickle)
        except IOError, err:
            print err

    def save_unsent_messages(self):
        unsent_messages = []
        unsent_emails_count = 0
        if self.q_message:
            unsent_messages.append((self.q_prio, self.q_message))
            unsent_emails_count += 1

        while True:
            try:
                priority, message = self.m_queue.get(block=False)
                unsent_messages.append((priority, message))
                unsent_emails_count += 1
            except Empty:
                break

        # Error messages are going to be saved too
        while True:
            try:
                err, priority, message = self.e_queue.get(block=False)
                unsent_messages.append((priority, message))
                unsent_emails_count += 1
            except Empty:
                break

        if unsent_messages:
            log.debug("Saving %s unsent emails to backup file.",
                      len(unsent_messages))

            unsent_emails_pickle = open(self.unsent_emails_pickle, 'wb')
            cPickle.dump(unsent_messages, unsent_emails_pickle)
            unsent_emails_pickle.close()

    def on_webapp_shutdown(self, app):
        log.warning("Waiting to send all messages before shutting down!!!")
        self.save_unsent_messages()

    def schedule_processing(self):
        def reset_processing(gt):
            self.processing = None

        if self.processing is None:
            self.processing = eventlet.spawn_after(1, self.process_messages)
            self.processing.link(reset_processing)

    def send(self, message, priority=0):
        self.m_queue.put((priority, message), block=False)
        self.schedule_processing()

    def process_messages(self):
        while True:
            if self.q_message:
                # There's a message being processed
                break

            log.trace("Messages waiting to be sent: %s", self.m_queue.qsize())
            timeout = eventlet.Timeout(5, SendMessageTimeout())
            try:
                self.q_prio, self.q_message = self.m_queue.get(block=False)
                log.debug("Sending message to \"%s\"",
                          ", ".join(self.q_message.send_to))
                self.smtp.send(self.q_message)
                self.m_queue.task_done()
                self.q_prio = self.q_message = None
                # Allow other things to run
                eventlet.sleep(0)
            except SendMessageTimeout:
                log.debug("Sending message took too long. Requeing.")
                self.m_queue.task_done()
                self.m_queue.put((self.q_prio, self.q_message), block=False)
                self.q_prio = self.q_message = None
            except Empty:
                # No messages waiting to be sent. In case we're waiting for all
                # messages to be send before shuting down, state that we're
                # ready to be shutdown
                break
            except Exception, err:
                log.exception(err)
                self.m_queue.task_done()
                self.e_queue.put((err, self.q_prio, self.q_message),
                                 block=False)
                self.q_prio = self.q_message = None
            finally:
                timeout.cancel()

mail = EMailManager(component_manager)
