import logging
import praw
import random
import re
from FCsettings import opt_in_subs, reactionary_subreddits


def search_history(user):
    reactionary_comments = {}
    reactionary_scores = {}
    reactionary_submissions = {}
    for comment in user.get_comments(limit=1000):
        sub_name = comment.subreddit.display_name.lower()
        if sub_name in reactionary_subreddits:
            if sub_name in reactionary_comments:
                reactionary_comments[sub_name].append(comment.name)
                reactionary_scores[sub_name] += comment.score
            else:
                reactionary_comments[sub_name] = [comment.name]
                reactionary_scores[sub_name] = comment.score
    for submission in user.get_submitted(limit=1000):
        sub_name = submission.subreddit.display_name.lower()
        if sub_name in reactionary_subreddits:
            if sub_name in reactionary_submissions:
                reactionary_submissions[sub_name] += 1
                reactionary_scores[sub_name] += submission.score
            else:
                reactionary_submissions[sub_name] = 1
                if sub_name in reactionary_scores:
                    reactionary_scores[sub_name] += submission.score
                else:
                    reactionary_scores[sub_name] = submission.score
    return reactionary_scores, reactionary_comments, reactionary_submissions


def get_username(messagetxt, is_pm):
    match = username_regex.match(messagetxt)
    if match:
        if match.group('ulink') and not is_pm:
            return 'U'
        return match.group('username')
    return None


def reply_with_sig(message, response):
    signature = '\n\n---\n\nI am a bot. Only the last 1,000 comments and submissions are searched.'
    message.reply(response + signature)


def process_message(message):
    try:
        if message.subreddit is not None and message.subreddit.display_name.lower() not in opt_in_subs:
            return True
        username = get_username(message.body, message.subreddit is None)
        if not username:
            return True
        if username == 'U':
            reply_with_sig(message, 'Please do not use /u/ links when naming the user you wish me to search.')
            return True
        if username.lower() == bot_name.lower():
            reply_with_sig(message, 'Nah.')
            return True
        if username.lower() == 'me':
            username = message.author.name
        user = r.get_redditor(username)
        try:
            user_results = search_history(user)
            reactionary_scores = user_results[0]
            reactionary_comments = user_results[1]
            reactionary_submissions = user_results[2]
        except praw.errors.NotFound:
            reply_with_sig(message, 'User {0} not found.'.format(username))
            return True
        total_score = 0
        if not reactionary_scores:
            reply_with_sig(message, 'No participation in reactionary subreddits found for {0}.'.format(username))
            return True
        response_text = "{0}'s post history contains participation in the following reactionary subreddits:\n\n".format(user.name)
        for subreddit in reactionary_scores:
            total_score += reactionary_scores[subreddit]
            num_comments = 0
            num_submissions = 0
            if subreddit in reactionary_comments:
                num_comments = len(reactionary_comments[subreddit])
            if subreddit in reactionary_submissions:
                num_submissions = reactionary_submissions[subreddit]
            response_text += '**{0}: {1} comment{4}, {2} submission{5}. Total score: {3}**  '.format(subreddit, num_comments,
                             num_submissions, reactionary_scores[subreddit], '' if num_comments == 1 else 's',
                             '' if num_submissions == 1 else 's')
            if num_comments > 0:
                response_text += '\nSample comment:  \n>{0}\n\n'.format(r.get_info(thing_id=random.choice(reactionary_comments[subreddit])).body.replace('\n\n', '\n\n>'))
            else:
                response_text += '\n\n'
            if len(response_text) > 9900:
                response_text = response_text[:9900] + '...'
                break
        response_text += '#Total Score: {0}'.format(str(total_score))
        reply_with_sig(message, response_text)
        return True
    except praw.errors.HTTPException:
        return False
    except praw.errors.APIException:
        logging.exception('Exception: ')
        return False


def main():
    unread = list(r.get_unread(limit=1000))
    for message in r.get_mentions(limit=1000):
        if message not in unread:
            continue
        if process_message(message):
            message.mark_as_read()
    for message in r.get_messages(limit=1000):
        if message not in unread:
            continue
        if process_message(message):
            message.mark_as_read()

logging.basicConfig(level=logging.ERROR, filename='FCbot.log')
r = praw.Reddit(user_agent='FULLCOMMUNISM reactionary sub peeksy-pie agent v1', site_name='FCbot')
r.refresh_access_information()
bot_name = r.get_me().name
username_regex = re.compile(r'.*^\s*(/?u/{0})?\s*(?P<ulink>/?u/)?\\?(?P<username>[-\w]+)\s*$'.format(bot_name), re.IGNORECASE | re.MULTILINE | re.DOTALL)
if __name__ == '__main__':
    try:
        main()
    except:
        logging.exception('Exception: ')
