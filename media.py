"Handle subreddit media links"

import os
import stat
import re
import random
import logging
from subprocess import Popen, PIPE
from json import loads
from time import time, sleep
from local_storage import LocalStorage
from threading import Thread
from queue import Queue, Empty
from math import ceil

class MPlayerThread(Thread):
    def __init__(self):
        logging.debug('Initializing MPlayerThread')
        Thread.__init__(self)
        logging.debug('Opening mplayer process')
        self.process = Popen(['mplayer', '-vo', 'null', '-slave', '-idle',
                        '-msglevel', 'all=4'], stdout=PIPE, stdin=PIPE, stderr=PIPE)
        self.properties = {}
        self.run_properties_thread = True
        self.properties_thread = Thread(target=self.get_properties)
        self.properties_thread.daemon = True

    def get_properties(self):
        logging.debug('Running mplayer process-watching thread')
        while self.run_properties_thread:
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
                self.process.stdin.write(('get_property %s\n' % p).encode())
                self.process.stdin.flush()

    def run(self):
        logging.debug('Running MPlayerThread')
        self.properties_thread.start()
        while True:
            exit_code = self.process.poll()
            if exit_code is not None:
                logging.error('Mplayer process has ended with exit code %s' % exit_code)
                break
            line = self.process.stdout.readline().decode()
            if re.search('^ANS_.*=.*$', line):
                k, v = line.replace('ANS_', '').replace('\n', '').split('=')
                self.properties[k] = v
            try:
                self.properties['volume'] = float(self.properties['volume'])
                self.properties['length'] = float(self.properties['length'])
                self.properties['time_pos'] = float(self.properties['time_pos'])
                self.properties['time_left'] = ceil(self.properties['length'] - self.properties['time_pos'])
                self.properties['percent_pos'] = int(self.properties['percent_pos'])
            except BaseException:
                self.properties['volume'] = 0
                self.properties['length'] = 0
                self.properties['time_pos'] = 0
                self.properties['time_left'] = 0
                self.properties['percent_pos'] = 0

class YoutubeDLThread(Thread):
    PROPERTIES_TEMPLATE = {
        'status': 'starting',
        'process': None,
        'parse_thread': None,
        'destination': 'unknown',
        'percent': '0.0%',
        'size': 'unknown',
        'rate': '0B/s',
        'eta': 'unknown',
        }

    PROCESS_TEMPLATE = ['youtube-dl', '--newline', '-o', 'DOWNLOAD_PATH',
                        '--prefer-free-formats', '-f', '45/22/43/34/44/35', 'URL']

    def __init__(self, queue):
        logging.debug('Initializing YoutubeDLThread')
        Thread.__init__(self)
        self.queue = queue
        self.downloads = {}

    def parse_output(self, dlid):
        logging.debug('Running youtube-dl parse thread for dlid: %s' % dlid)
        while self.downloads[dlid]['process'].poll() is None:
            line = self.downloads[dlid]['process'].stdout.readline().decode()
            if re.search('^\[(youtube|soundcloud|vimeo)\] *', line):
                self.downloads[dlid]['status'] = line
            elif re.search('^\[download\] Destination: ', line):
                self.downloads[dlid]['status'] = 'downloading'
                self.downloads[dlid]['destination'] = re.split(' *', line.replace('\n', ''))[2]
            elif re.search('^\[download\] *\d*\.\d%', line):
                params = re.split(' *', line.replace('\n', ''))
                self.downloads[dlid]['percent'] = params[1]
                self.downloads[dlid]['size'] = params[3]
                self.downloads[dlid]['rate'] = params[5]
                self.downloads[dlid]['eta'] = params[7]
                if params[1] == '100.0%': self.downloads[dlid]['status'] = 'complete'

    def run(self):
        logging.debug('Running YoutubeDLThread')
        while True:
            try:
                newdl = self.queue.get(True, 1.0)
                logging.debug('New download found in queue: %s' % newdl)
            except Empty:
                newdl = None
            if newdl:
                dlid = newdl['id']
                download_dir = newdl['download_dir']
                url = newdl['url']

                self.downloads[dlid] = {}
                for k, v in self.PROPERTIES_TEMPLATE.items():
                    self.downloads[dlid][k] = v

                if os.path.isfile(os.path.join(download_dir, dlid)):
                    logging.debug('File already exists: %s' % dlid)
                    self.downloads[dlid]['percent'] = '1000.0%'
                    self.downloads[dlid]['status'] = 'complete'
                    return None

                process_args = []
                for x in self.PROCESS_TEMPLATE:
                    process_args.append(x)
                process_args[3] = os.path.join(download_dir, dlid)
                process_args[-1] = url

                logging.debug('Opening youtube-dl process')
                self.downloads[dlid]['process'] = Popen(process_args,
                        stdout=PIPE, stderr=PIPE)

                self.downloads[dlid]['parse_thread'] = \
                        Thread(target=self.parse_output, args=(dlid,))
                self.downloads[dlid]['parse_thread'].daemon = True
                self.downloads[dlid]['parse_thread'].start()

class SubredditMediaPlayer(Thread):

    def __init__(self, config_dir, download_dir):

        logging.debug('Initializing SubredditMediaPlayer thread')

        Thread.__init__(self)

        self.idx = 0
        self.playlist = []
        self.playing = False
        self.buffering = False

        self.config_dir = config_dir
        self.history = LocalStorage(os.path.join(config_dir, 'history.json'))

        self.download_dir = download_dir

        self.mp = MPlayerThread()
        self.mp.daemon = True
        self.mp.start()

        self.playtime = 0

        self.dlq = Queue()
        self.dl = YoutubeDLThread(self.dlq)
        self.dl.daemon = True
        self.dl.start()

    @property
    def has_next(self):
        return len(self.playlist) > self.idx+1

    def run(self):
        logging.debug('Running SubredditMediaPlayer thread')
        while True:
            sleep(1)
            if self.playing and self.has_next and (self.mp.properties['time_left'] == 1) and not self.buffering:
                sleep(1)
                logging.debug('End of file')
                self.next()
            elif self.playing and not self.has_next and not (self.mp_properties['filename'] or self.buffering):
                logging.debug('End of playlist')
                self.playing = False

    def shuffle(self):
        logging.debug('Shuffling playlist')
        current_id = self.playlist[self.idx]['id']
        random.shuffle(self.playlist)

        idx = 0
        for item in self.playlist:
            if item['id'] == current_id:
                self.idx = item
                break
            idx += 1
        self.idx = idx

    def download(self, idx):
        f_path = os.path.join(self.download_dir, self.playlist[idx]['id'])
        if os.path.isfile(f_path):
            logging.debug('Playlist item exists. Skipping download: %s' % idx)
        else:
            logging.debug('Putting playlist item in download queue: %s' % idx)
            self.dlq.put({'id': self.playlist[idx]['id'],
                          'url': self.playlist[idx]['url'].replace('&amp;', '&'),
                          'download_dir': self.download_dir})

    def play(self, idx):
        logging.debug('Playing playlist item: %s' % idx)
        logging.debug('Stopping first, before playing: %s' % idx)
        self.stop()

        self.playing = True
        f_path = os.path.join(self.download_dir, self.playlist[idx]['id'])
        if os.path.isfile(f_path):
            logging.debug('File exists. Loading file to mplayer process: %s' % idx)
            self.idx = idx
            self.buffering = False
            self.playtime = time()
            self.mp.process.stdin.write(('loadfile "%s"\n' % f_path).encode())
            self.mp.process.stdin.write('get_property filename\n'.encode())
            self.mp.process.stdin.flush()
            self.history[self.playlist[idx]['id']] = {
                'playtime': self.playtime,
                'voted': 0,
                'subreddit': self.playlist[idx]['subreddit'],
                }
            self.download(idx+1)
        else:
            logging.debug('File does not exist. Need to buffer/download first: %s' % idx)
            print("Buffering...")
            self.buffering = True
            self.download(idx)
            while True:
                sleep(1)
                dlid = self.playlist[idx]['id']
                status = self.dl.downloads[dlid]
                if status['status'] == 'downloading': print(status['percent'])
                if (status['status'] == 'complete') or (status['status'] == 'idle'): break
            logging.debug('Download finished. Running play function again: %s' % idx)
            self.play(idx)

    def next(self):
        logging.debug('Next')
        if self.has_next:
            self.play(self.idx+1)

    def previous(self):
        if time() - self.playtime > 10:
            logging.debug('Seeking back to back to beginning')
            self.mp.process.stdin.write('seek 0 2\n'.encode())
            self.mp.process.stdin.flush()
            self.playtime = time()
        elif self.idx != 0:
            logging.debug('Previous')
            self.play(self.idx-1)

    def pause(self):
        self.mp.process.stdin.write('pause\n'.encode())
        self.mp.process.stdin.flush()

    def stop(self):
        logging.debug('Stop')
        self.mp.process.stdin.write('stop\n'.encode())
        self.mp.process.stdin.flush()
        self.playing = False

    def upvote(self, idx):
        # TODO
        return 0

    def downvote(self, idx):
        # TODO
        return 0

