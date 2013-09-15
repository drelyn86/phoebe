"Handle subreddit media links"

import re
from null import Null
from os import path
from subprocess import Popen, PIPE
from threading import Thread

class DLThread(Thread):
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

    def __init__(self, queue, logger=Null()):
        self.logger = logger
        self.log = self.logger.getLogger('phoebe.download.DLThread')
        self.log.debug('YouTubeDLThread initialized')
        self.ytdl_log = self.logger.getLogger('phoebe.download.process')
        Thread.__init__(self)
        self.queue = queue
        self.downloads = {}

    def parse_output(self, dlid):
        self.log.debug('Running parse_output thread for dlid: %s' % dlid)
        exit_code = None
        while exit_code is None:
            exit_code = self.downloads[dlid]['process'].poll()
            if exit_code is None:
                line = self.downloads[dlid]['process'].stdout.readline().decode()
                if line:
                    self.ytdl_log.info('%s stdout: %s' % (dlid, line.replace('\n', '')))
            else:
                self.log.debug('%s: youtube-dl exit_code: %s' % (dlid, exit_code))
                stdout = self.downloads[dlid]['process'].stdout.read().decode()
                if stdout:
                    self.ytdl_log.info('%s process ended, final stdout: %s' % (dlid, stdout))
                    line = stdout.splitlines()[-1]
                else:
                    break
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

    def parse_errors(self, dlid):
        self.log.debug('Running parse_error thread for dlid: %s' % dlid)
        exit_code = None
        while exit_code is None:
            exit_code = self.downloads[dlid]['process'].poll()
            if exit_code is None:
                line = self.downloads[dlid]['process'].stderr.readline().decode()
                if line:
                    self.ytdl_log.info('%s stderr: %s' % (dlid, line.replace('\n', '')))
                    self.downloads[dlid]['error'] = line.replace('\n', '')
            else:
                stderr = self.downloads[dlid]['process'].stderr.read().decode()
                if stderr:
                    self.ytdl_log.info('%s process ended, final stderr: %s' % (dlid, stderr))
                    line = stderr.splitlines()[-1]
                    self.downloads[dlid]['error'] = line

    def run(self):
        self.log.debug('Running DLThread')
        while True:
            newdl = self.queue.get(True)
            self.log.debug('New download found in queue: %s' % newdl)
            dlid = newdl['id']
            download_dir = newdl['download_dir']
            url = newdl['url']

            self.downloads[dlid] = {}
            for k, v in self.PROPERTIES_TEMPLATE.items():
                self.downloads[dlid][k] = v

            if path.isfile(path.join(download_dir, dlid)):
                self.log.debug('File already exists: %s' % dlid)
                self.downloads[dlid]['percent'] = '1000.0%'
                self.downloads[dlid]['status'] = 'complete'
                break

            process_args = []
            for x in self.PROCESS_TEMPLATE:
                process_args.append(x)
            process_args[3] = path.join(download_dir, dlid)
            process_args[-1] = url

            self.log.debug('Opening youtube-dl process: %s' % dlid)
            self.downloads[dlid]['process'] = Popen(process_args,
                    stdout=PIPE, stderr=PIPE)

            self.downloads[dlid]['parse_thread'] = \
                    Thread(target=self.parse_output, args=(dlid,))
            self.downloads[dlid]['parse_thread'].daemon = True
            self.downloads[dlid]['parse_thread'].start()
            self.downloads[dlid]['error_thread'] = \
                    Thread(target=self.parse_errors, args=(dlid,))
            self.downloads[dlid]['error_thread'].daemon = True
            self.downloads[dlid]['error_thread'].start()

