"Communicate with the Reddit API  for the purpose of audio and video link entertainment"

try: # Python3
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
except ImportError: # Python2
    from urllib2 import urlopen, Request
finally: # Cross-Compatible
    import re
    import logging
    from null import Null
    from bs4 import BeautifulSoup
    from json import loads

class Reddit(object):

    USER_AGENT = 'phoebe/0.1a by drelyn86'
    LOGIN_URL = 'https://ssl.reddit.com/api/login'
    API_URL = 'http://www.reddit.com/api'

    def __init__(self, logger=Null()):
        self.logger = logger
        self.log = self.logger.getLogger('phoebe.reddit.Reddit')
        self.log.debug('Reddit object initialized')
        self.user = None
        self.modhash = None
        self.headers = {'User-Agent': Reddit.USER_AGENT}

    def api(self, method):
        return '%s/%s' % (Reddit.API_URL, method)

    def login(self, user, passwd):
        self.log.info('Logging in')
        self.user = user
        self.passwd = passwd
        data = urlencode({'api_type': 'json', 'user': user, 'passwd': passwd, 'rem': False}).encode()
        request = Request(Reddit.LOGIN_URL, headers=self.headers, data=data)
        response = urlopen(request).read().decode()
        self.log.debug(response)
        js = loads(response)
        self.modhash = js['json']['data']['modhash']
        self.headers['X-Modhash'] = self.modhash
        return True

    def upvote(self, id):
        self.log.debug('upvoting: %s' % id)
        if self.modhash:
            data = urlencode({'id': 't3_%s' % id, 'dir': 1}).encode()
            request = Request(self.api('vote'), headers=self.headers, data=data)
            response = urlopen(Request).read().decode()
            self.log.debug(response)
        else:
            self.log.warning('cannot cast vote to reddit. not logged in')

    def downvote(self, id):
        self.log.debug('downvoting: %s' % id)
        if self.modhash:
            data = urlencode({'id': 't3_%s' % id, 'dir': -1}).encode()
            request = Request(self.api('vote', headers=self.headers, data=data))
            response = urlopen(Request).read().decode()
            self.log.debug(response)
        else:
            self.log.warning('cannot cast vote to reddit. not logged in')

class Subreddit(object):

    def __init__(self, name, headers={'User-Agent': Reddit.USER_AGENT},
                 sort='hot', limit='25', logger=Null()):
        self.logger = logger
        self.log = self.logger.getLogger('phoebe.reddit.Subreddit')
        self.log.debug('Subreddit object initialized: %s' % name)
        self.name = name
        self.headers = headers
        self.sort = sort
        self.limit = limit
        self.json_url = 'http://www.reddit.com/r/%(name)s/%(sort)s.json?limit=%(limit)s' % locals()

    @property
    def links(self):
        self.log.info('Requesting json info from reddit')
        request = Request(self.json_url, headers=self.headers)
        self.log.info('Processing json data')
        js = loads(urlopen(request).read().decode())
        link_list = []
        for x in js['data']['children']:
            link_list.append(x)
        return link_list

class SRManager(object):

    SUPPORTED_DOMAINS = ('youtube.com', 'soundcloud.com', 'vimeo.com')

    def __init__(self, headers={'User-Agent': Reddit.USER_AGENT}, logger=Null()):
        self.logger = logger
        self.log = self.logger.getLogger('phoebe.reddit.SRManager')
        self.log.debug('SRManager object initialized')
        self.headers = headers
        self.subscribed_subreddits = []

    def filter_links(self, links):
        filtered_list = []
        for x in links:
            if x['data']['domain'] in SRManager.SUPPORTED_DOMAINS:
                filtered_list.append(x)
        return filtered_list

    def get_recommended_music_subreddits():
        self.log.info('Fetching list from /r/Music wiki')
        wiki_list_url = 'http://www.reddit.com/r/Music/wiki/musicsubreddits'
        list_page_html = urlopen(wiki_list_url).read()
        bs = BeautifulSoup(list_page_html)

        self.log.debug('Processing wiki html')
        mdwiki = bs.find_all(attrs={'class': ['wiki','mkd']})[0]

        # We don't want anything south of the "Images" header
        images_header = mdwiki.find('h2', {'id': 'wiki_images'})
        categories = images_header.find_previous_siblings('h2')

        subreddits = {}
        for cat in categories:
            category = cat.get_text()
            subreddits[category] = []

            subs = cat.find_next_sibling('ul').find_all('li')

            for sub in subs:
                subreddit = re.sub('^/r/', '', sub.find('a').get('href'))
                if '+' in subreddit: continue # skip combined subs
                subreddits[category].append(subreddit)

        return subreddits

if __name__ == '__main__':
    from getpass import getpass
    user = input('user: ')
    passwd = getpass('passwd: ')
    r = Reddit()
    r.login(user, passwd)
    sr = Subreddit('coversongs', r.headers)
    links = sr.links
    print(len(links))
    srm = SRManager(r.headers)
    print(len(srm.filter_links(links)))
