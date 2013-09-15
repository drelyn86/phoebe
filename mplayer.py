import re
from math import ceil
from null import Null
from subprocess import Popen, PIPE
from threading import Thread
from time import sleep

class MPlayerThread(Thread):
    def __init__(self, queue, logger=Null()):
        self.logger = logger
        self.log = self.logger.getLogger('phoebe.mplayer.MPlayerThread')
        self.log.debug('MPlayerThread initialized')
        self.process_log = self.logger.getLogger('phoebe.mplayer.process')

        Thread.__init__(self)

        self.queue = queue
        self.properties = {}

        self.properties_thread = Thread(target=self.request_properties)
        self.properties_thread.daemon = True

        self.parse_output_thread = Thread(target=self.parse_output)
        self.parse_output_thread.daemon = True

    def run(self):
        self.log.debug('Running MPlayerThread')
        self.log.debug('Opening mplayer process')
        self.process = Popen(['mplayer', '-vo', 'null', '-slave', '-idle',
                        '-msglevel', 'all=4'], stdout=PIPE, stdin=PIPE, stderr=PIPE)
        self.properties_thread.start()
        self.parse_output_thread.start()
        while True:
            command = self.queue.get(True)
            self.process.stdin.write(('%s\n' % command).encode())
            self.process.stdin.flush()

    def request_properties(self):
        log = self.logger.getLogger('phoebe.mplayer.request_properties')
        log.debug('request_properties thread started')
        while True:
            sleep(1)
            self.properties = {
                            'filename': None,
                            'volume': 0,
                            'pause': None,
                            'length': 0,
                            'time_pos': 0,
                            'percent_pos': 0,
                            'time_left': 0,
                            }
            for p in self.properties.keys():
                if p == 'time_left': continue
                self.queue.put('get_property %s' % p)

    def parse_output(self):
        self.log.debug('Running parse_output thread for mplayer')
        while True:
            exit_code = self.process.poll()
            if exit_code is not None:
                self.log.debug('mplayer exit code: %s' % exit_code)
                break
            line = self.process.stdout.readline().decode()
            self.mp_log.info('stdout: %s' % line.replace('\n', ''))
            if re.search('^ANS_.*=.*$', line):
                k, v = line.replace('ANS_', '').replace('\n', '').split('=')
                if k != 'ERROR':
                    self.properties[k] = v
            try:
                self.properties['volume'] = float(self.properties['volume'])
                self.properties['length'] = float(self.properties['length'])
                self.properties['time_pos'] = float(self.properties['time_pos'])
                self.properties['time_left'] = ceil(self.properties['length'] - self.properties['time_pos'])
                self.properties['percent_pos'] = int(self.properties['percent_pos'])
            except BaseException as e:
                self.log.debug('unexpected value of property: %s' % e)
                self.properties['volume'] = 0
                self.properties['length'] = 0
                self.properties['time_pos'] = 0
                self.properties['time_left'] = 0
                self.properties['percent_pos'] = 0

