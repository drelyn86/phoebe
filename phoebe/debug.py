
import os
import logging
from time import sleep

from phoebe import Phoebe
from reddit import Subreddit

subreddits = [Subreddit('dubstep')]

phoebe = Phoebe(os.path.join(os.path.expanduser('~'), '.config', 'phoebe'), logging)
phoebe.daemon = True

for subreddit in subreddits:
    for link in subreddit.links:
        phoebe.playlist.append(link)

phoebe.start()
phoebe.play(0)

while True:
    sleep(1)

