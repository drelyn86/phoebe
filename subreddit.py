"Parse Reddit for music links"

try: # Python3
    from urllib.request import urlopen, Request
except ImportError: # Python2
    from urllib2 import urlopen, Request
finally: # Cross-Compatible
    import re
    import logging
    from bs4 import BeautifulSoup
    from json import loads

class Subreddit(object):

    SUPPORTED_DOMAINS = ('youtube.com', 'soundcloud.com', 'vimeo.com')
    USER_AGENT = 'phoebe/0.1 by drelyn86'

    def __init__(self, name, sort='hot', limit='25'):
        logging.debug('Initializing subreddit object: %s' % name)
        self.name = name
        self.sort = sort
        self.limit = limit
        self.json_url = 'http://www.reddit.com/r/%(name)s/%(sort)s.json?limit=%(limit)s' % locals()

    @property
    def links(self):
        logging.debug('Requesting json info from reddit')
        request = Request(self.json_url, headers={'User-Agent': Subreddit.USER_AGENT})
        logging.debug('Processing json data')
        js = loads(urlopen(request).read().decode())
        playable_links = []
        for x in js['data']['children']:
            data = x['data']
            #if data['id'] in self.links.keys(): continue
            if data['domain'] not in Subreddit.SUPPORTED_DOMAINS: continue
            playable_links.append(data)
        return playable_links

class SRManager(object):

    def __init__(self):
        self.subscribed_subreddits = []

    def get_recommended_subreddits():
        logging.debug('Fetching list from /r/Music wiki')
        wiki_list_url = 'http://www.reddit.com/r/Music/wiki/musicsubreddits'
        list_page_html = urlopen(wiki_list_url).read()
        bs = BeautifulSoup(list_page_html)

        logging.debug('Processing wiki html')
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
    sub = Subreddit('Dubstep')
    print(sub.links)
