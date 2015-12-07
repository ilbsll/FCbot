# import praw
import sqlite3
# from FCsettings import useragent

# r = praw.Reddit(user_agent=useragent, site_name='FCbot')
# r.refresh_access_information()

db = sqlite3.connect('FCbot.db')
c = db.cursor()
highest_score = c.execute('SELECT user, score FROM users WHERE distinction="highest"').fetchone()
lowest_score = c.execute('SELECT user, score FROM users WHERE distinction="lowest"').fetchone()
sub_counts = c.execute('SELECT * FROM subs ORDER BY count DESC').fetchall()

post_text = '''\
**User Stats**

  | User | Score
-|-|-
Most Reactionary User Found | {0} | {1}
Most Revolutionary User Found | {2} | {3}


**Number of hits by subreddit**

Subreddit | Hits
-|-
'''

for sub in sub_counts:
    post_text += sub[0] + ' | ' + str(sub[1]) + '\n'

print(post_text)