import random
from os import path
from download import DLThread
from local_storage import LocalStorage
from mplayer import MPlayerThread
from null import Null
from reddit import Reddit
from subprocess import Popen, PIPE
from threading import Thread
from time import time, sleep
from queue import Queue

class Phoebe(Thread):

    def __init__(self, config_dir, logger=Null()):

        self.logger = logger
        self.log = self.logger.getLogger('phoebe.Phoebe')
        self.log.debug('Phoebe Thread initialized')
        self.log.debug('config_dir: %s' % config_dir)

        Thread.__init__(self)

        self.idx = 0
        self.playlist = []
        self.playing = False
        self.buffering = False

        self.config_dir = config_dir

        self.log.debug('Loading history file')
        self.history = LocalStorage(path.join(config_dir, 'history.json'), logger=self.logger)

        self.log.debug('Loading settings file')
        self.settings = LocalStorage(path.join(config_dir, 'settings.json'), logger=self.logger)

        self.reddit = Reddit(logger=self.logger)
        if ('reddit_username' in self.settings.keys()) \
          and ('reddit_password' in self.settings.keys()):
            self.reddit.login(self.settings['reddit_username'], self.settings['reddit_password'])

        self.mpq = Queue()
        if self.settings['backend'] == 'mplayer':
            self.mp = MPlayerThread(queue=self.mpq, logger=self.logger)
        self.mp.daemon = True
        self.mp.start()

        self.playtime = 0

        self.dlq = Queue()
        self.dl = DLThread(self.dlq, logger=self.logger)
        self.dl.daemon = True
        self.dl.start()

    @property
    def has_next(self):
        return len(self.playlist) > self.idx+1

    def run(self):
        self.log.debug('Running Phoebe thread')
        while True:
            sleep(1)
            if self.playing and self.has_next and (self.mp.properties['time_left'] == 1) and not self.buffering:
                self.log.debug('End of file. Sleep 1')
                sleep(1)
                self.next()
            elif self.playing and not self.has_next and not (self.mp_properties['filename'] or self.buffering):
                self.log.debug('End of playlist')
                self.playing = False

    def shuffle(self):
        self.log.debug('Shuffling playlist')
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
        f_path = path.join(self.settings['download_dir'], self.playlist[idx]['id'])
        if path.isfile(f_path):
            self.log.debug('Playlist item exists. Skipping download: %s' % idx)
        else:
            self.log.debug('Putting playlist item in download queue: %s' % idx)
            self.dlq.put({'id': self.playlist[idx]['id'],
                          'url': self.playlist[idx]['url'].replace('&amp;', '&'),
                          'download_dir': self.settings['download_dir']})

    def play(self, idx):
        self.log.debug('Playing playlist item: %s' % idx)
        self.log.debug('Stopping first, before playing: %s' % idx)
        self.stop()

        self.playing = True
        f_path = path.join(self.settings['download_dir'], self.playlist[idx]['id'])
        if path.isfile(f_path):
            self.log.debug('File exists. Loading file to mplayer process: %s' % idx)
            self.idx = idx
            self.buffering = False
            self.playtime = time()
            self.mpq.put('loadfile %s' % f_path)
            self.mpq.put('get_property filename')
            if self.playlist[idx]['id'] in self.history.keys():
                voted = self.history[self.playlist[idx]['id']]['voted']
            else:
                voted = 0
            self.history[self.playlist[idx]['id']] = {
                'playtime': self.playtime,
                'voted': voted,
                'subreddit': self.playlist[idx]['subreddit'],
                }
            self.download(idx+1)
        else:
            self.log.debug('File does not exist. Need to buffer/download first: %s' % idx)
            if self.playlist[idx]['id'] in self.dl.downloads.keys():
                status = self.dl.downloads[self.playlist[idx]['id']]
                if (status['process'].poll() is not None) and (status['status'] is not 'complete'):
                    self.log.info('Previous download attempt failed. Skipping: %s' % idx)
                    self.log.info('Error from download process: %s' % status['error'])
                    self.playlist[idx]['filter'] = 'download_failed'
                    self.next()
                    return None
            print("Buffering...")
            self.buffering = True
            self.download(idx)
            while True:
                sleep(1)
                dlid = self.playlist[idx]['id']
                status = self.dl.downloads[dlid]
                if status['status'] == 'downloading': print(status['percent'])
                if (status['status'] == 'complete') or (status['status'] == 'idle'): break
                if (status['process'].poll() is not None) and (status['status'] is not 'complete'):
                    self.log.info('Download attempt failed. Skipping: %s' % idx)
                    self.log.info('Error from download process: %s' % status['error'])
                    self.playlist[idx]['filter'] = 'download_failed'
                    self.next()
                    return None
            self.log.debug('Download finished. Running play function again: %s' % idx)
            self.play(idx)

    def next(self):
        self.log.debug('Next')
        if self.has_next:
            for idx in range(self.idx+1, len(self.playlist)):
                self.idx = idx
                if not 'filter' in self.playlist[idx].keys():
                    self.play(idx)
                    break
                else:
                    reason = self.playlist[idx]['filter']
                    self.log.debug('Skipping playlist item %s due to filter: %s' % (idx, reason))

    def previous(self):
        if time() - self.playtime > 10:
            self.log.debug('Seeking back to back to beginning')
            self.mpq.put('seek 0 2')
            self.playtime = time()
        elif self.idx != 0:
            self.log.debug('Previous')
            self.play(self.idx-1)

    def pause(self):
        self.log.debug('Pause')
        self.mpq.put('pause')

    def stop(self):
        self.log.debug('Stop')
        self.mpq.put('stop')
        self.playing = False

    def upvote(self):
        if self.playlist[self.idx]['id'] in self.history.keys():
            self.log.debug('upvoting')
            hist = self.history[self.playlist[self.idx]['id']]
            hist['voted'] = 1
            self.history[self.playlist[self.idx]['id']] = hist
        if self.reddit.logged_in:
            self.reddit.upvote(self.playlist[self.idx]['id'])

    def downvote(self):
        if self.playlist[self.idx]['id'] in self.history.keys():
            self.log.debug('downvoting')
            hist = self.history[self.playlist[self.idx]['id']]
            hist['voted'] = -1
            self.history[self.playlist[self.idx]['id']] = hist
        if self.reddit.logged_in:
            self.reddit.downvote(self.playlist[self.idx]['id'])
        self.next()

