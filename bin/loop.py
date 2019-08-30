# -*- coding: utf-8 -*-


'''
    ~~~~~~~~~~~~~~~~~~
    Author: cloudp
    Create: 2018-12-25
    Version: 1.0.2
    ~~~~~~~~~~~~~~~~~~
'''


import os
import sys
import time
import Queue
import logging
import threading
import pyinotify
import subprocess
import ConfigParser


SELFPATH = os.path.dirname(os.path.realpath(__file__))


class Log(object):
    def __new__(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = super(Log, cls).__new__(cls)
        return cls._instance

    def init(self, filename, level='info'):
        self.log_level = {
            'debug':    logging.DEBUG,
            'info':     logging.INFO,
            'warning':  logging.WARNING,
            'error':    logging.ERROR,
        }
        self.log_format = '(%(asctime)s) [%(levelname)s] %(threadName)s: %(message)s'
        self.logging = logging
        self.logging.basicConfig(filename=filename, level=self.log_level[level], format=self.log_format)
        return self.logging

    def get_log(self):
        return self.logging


class ExecThread(threading.Thread):
    def __init__(self, sleeps, script):
        super(ExecThread, self).__init__()
    
        self.log = Log().get_log()

        self.sleeps = int(sleeps)
        self.script = script
        
        self.queue = Queue.Queue()
        self.flag = True
    
    def _get_flag(self):
        return self.flag
        
    def _set_flag(self, value):
        self.flag = value
    
    def _rstrip(self, msg=[]):
        if len(msg) != 0:
            if isinstance(msg[-1], str):
                msg[-1] = msg[-1].rstrip('\n')
        return msg

    def popen(self):
        try:
            self._set_flag(False)
            time.sleep(self.sleeps)

            sp = subprocess.Popen('bash %s && exit || exit' %self.script, shell=True, close_fds=True, \
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
            msg = sp.stdout.readlines() + sp.stderr.readlines()

            if not sp.stdout.closed:            
                sp.stdout.close()
            if not sp.stderr.closed:
                sp.stderr.close()

            messages = 'exec script \'%s\'' %self.script
            if len(msg) != 0:
                messages += '\n'
                for m in self._rstrip(msg):
                    messages += '%s%s' %(' '*8, m)

            self.log.info(messages)
            
        except Exception as e:
            self.log.error(e)
    
        finally:
            self.queue.put(self.sleeps)

    def run(self):
        while True:
            sleep = self.queue.get()
            time.sleep(sleep)
            self._set_flag(True)

    def check(self):
        if self._get_flag():
            self.popen()
        

class MyEvent(pyinotify.ProcessEvent):
    def __init__(self, sleeps, script):

        self.execut= ExecThread(sleeps, script)
        self.execut.start()

    def process_default(self, event):
        self.execut.check()


class MyThread(threading.Thread):
    def __init__(self, name=None, item=[]):
        super(MyThread, self).__init__(name=name)
    
        self.item = item
        self.log = Log().get_log()

        self.event = {
            'modify':      pyinotify.IN_MODIFY,
            'attrib':      pyinotify.IN_ATTRIB,
            'move':        pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO,
            'create':      pyinotify.IN_CREATE,
            'delete':      pyinotify.IN_DELETE,
            'delete_self': pyinotify.IN_DELETE_SELF,
            'move_self':   pyinotify.IN_MOVE_SELF,
        }

    def get_event(self, events=[]):
        event = 0
        for e in events:
            element = self.event.get(e, None)      
            if element:
                event |= element
        return event

    def run(self):
        for i in self.item:
            key, value = i
            if key == 'folder':
                self.folder = os.path.abspath(value)
            elif key == 'events':
                self.events = value
            elif key == 'sleeps':
                self.sleeps = value
            elif key == 'script':
                self.script = value
        try:
            event = []
            if '*' in self.events:
                event = self.event.keys()
            else:
                for e in self.events.split(','):
                    event.append(e.strip())
    
            wmgr = pyinotify.WatchManager()
            wmgr.add_watch(self.folder, self.get_event(event), rec=True, auto_add=True)
            loop = pyinotify.Notifier(wmgr, MyEvent(self.sleeps, self.script))

            loop.loop()

        except Exception as e:
            self.log.error(e)


def global_init(gl=[]):
    for i in gl:
        key, value = i
        if key == 'pid_file':
            pid_file = value
        elif key == 'log_file':
            log_file = value

    Log().init(log_file)
    with open(pid_file, 'w') as pf:
        pf.write(str(os.getpid()))


def main():
    BASEPATH = os.path.dirname(SELFPATH)

    config = os.path.join(BASEPATH, 'etc/loop.conf')
    if not os.path.exists(config):
        print('Configure file \'%s\' is not exists.' %config)
        sys.exit(1)

    parser = ConfigParser.ConfigParser()
    parser.read(config)

    pl = parser.sections()

    threads = []
    for p in pl:
        if p == 'global':
            global_init(parser.items(p))
        else:
            threads.append(MyThread(p, parser.items(p)))

    for t in threads:
        t.start()

    for t in threads:
        t.join()
        
    
if __name__ == "__main__":
    main()


