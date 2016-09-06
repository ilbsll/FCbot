import fcntl
import praw
import random
import re
from FCsettings import useragent, opt_in_subs, reactionary_subreddits, patrolled_subreddits


def lock():
    global fp
    fp = open('FClock', 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        exit()


def search_history(user):
    """Fetches the user's last 1000 comments and submissions and checks the
    subreddits for membership in the list. Returns a tuple of three dicts, all
    three using the subreddit names as keys.
    """
    reactionary_scores = {}
    reactionary_comments = {}
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
    """Matches the regex statement against the body of the message. Returns
    one of three strings: a username, the special case 'U' if the caller has
    used a /u/ link, or an empty string if the regex didn't match.
    """
    regex = r'^\s*(/?u/{0})?\s*(?P<ulink>/?u/)?\\?(?P<username>[-\w]+)\s*$'.format(bot_name)
    match = re.search(regex, messagetxt, flags=re.IGNORECASE | re.MULTILINE)
    if match:
        if match.group('ulink') and not is_pm:
            return 'U'
        return match.group('username')
    return ''


def reply_with_sig(message, response):
    """Appends the signature to the bot's post before posting it. Does not return a value."""
    signature = '\n\n---\n\nI am a bot. Only the last 1,000 comments and submissions are searched.'
    if isinstance(message, praw.objects.Inboxable):
        message.reply(response + signature)
    elif isinstance(message, praw.objects.Submission):
        message.add_comment(response + signature)


def get_random_comment(commentlist):
    """Takes a list of comment IDs from a particular subreddit and returns the
    text of a random comment whose body is not '[removed]'. If no comments are
    eligible, returns an empty string.
    """
    randomized_comments = random.sample(commentlist, len(commentlist))
    for comment in randomized_comments:
        text = r.get_info(thing_id=comment).body
        if text != '[removed]':
            return text.replace('\n\n', '\n\n>')
    return ''


def generate_response(username):
    """Generates and returns a response based on the results of search_user()."""
    user = r.get_redditor(username)
    try:
        user.refresh()
    except praw.errors.NotFound:
        return 'User {0} not found.'.format(username)
    reactionary_scores, reactionary_comments, reactionary_submissions = search_history(user)
    total_score = 0
    if not reactionary_scores:
        return 'No participation in reactionary subreddits found for {0}.'.format(user.name)
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
        random_comment = get_random_comment(reactionary_comments[subreddit]) if subreddit in reactionary_comments else ''
        if random_comment:
            response_text += '\nSample comment:  \n>{0}\n\n'.format(random_comment)
        else:
            response_text += '\n\n'
        if len(response_text) > 9900:
            response_text = response_text[:9900] + '...\n\n'
            break
    response_text += '#Total Score: {0}'.format(str(total_score))
    return response_text


def process_mod_command(message):
    regex = r'^\s*!(?P<subname>\w+)\s+(?P<command>\w+)\s+(?P<ulink>/?u/)?\\?(?P<username>[-\w]+)\s*$'
    match = re.search(regex, message.body, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return
    sub_name = match.group('subname')
    if sub_name.lower() not in patrolled_subreddits:
        return
    subreddit = r.get_subreddit(sub_name)
    if message.author not in subreddit.get_moderators():
        return
    if match.group('command').lower() == 'whitelist':
        with open(subreddit.display_name.lower() + '_whitelist', 'a') as f:
            f.write(match.group('username').lower() + '\n')
        r.send_message(message.author,
                       'User added to whitelist', 'User {0} has been added to the ban whitelist for the subreddit {1}.'
                       .format(match.group('username'), subreddit.display_name))


def process_message(message):
    """Returns True if the message should be marked as read, and thus not
    addressed again in the future, or False if the message could not be
    processed but should be attempted again on the next pass.
    """
    try:
        if message.body.startswith('!'):
            process_mod_command(message)
            return True
        is_pm = message.subreddit is None
        if not is_pm and message.subreddit.display_name.lower() not in opt_in_subs:
            return True
        username = get_username(message.body, is_pm)
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
        response_text = generate_response(username)
        reply_with_sig(message, response_text)
        return True
    except praw.errors.HTTPException:
        return False
    except praw.errors.APIException:
        return False


def patrol_subreddit(subreddit):
    """Checks commenters and bans them if their score is too high. Does not
    return a value, but does make me wonder if I shouldn't be breaking these
    various roles into separate modules."""
    whitelist = []
    try:
        with open(subreddit.display_name.lower() + '_whitelist', 'r') as f:
            whitelist = [x.strip() for x in f]
    except FileNotFoundError:
        with open(subreddit.display_name.lower() + '_whitelist', 'w') as f:
            pass
    posts = list(subreddit.get_comments(limit=5))
    posts += list(subreddit.get_new(limit=5))
    for post in posts:
        user = post.author
        if user.name.lower() in whitelist:
            continue
        if user is None or post.banned_by is not None:
            continue
        user_scores = search_history(user)[0]
        user_total = sum([user_scores[x] for x in user_scores])
        if user_total > 1000:
            subs = ', '.join(user_scores)
            ban_message = 'You have been automatically banned for participation in the following reactionary ' \
                          'subreddits: ' + subs
            params = {'ban_reason': 'Reactionary subreddits', 'note': subs, 'ban_message': ban_message}
            subreddit.add_ban(user.name, **params)
            post.remove()


def main():
    """Main is usually a function."""
    for message in r.get_mentions(limit=100):
        if message.new and process_message(message):
            message.mark_as_read()
    for message in r.get_messages(limit=100):
        if message.new and process_message(message):
            message.mark_as_read()
    for subreddit in patrolled_subreddits:
        patrol_subreddit(r.get_subreddit(subreddit))


lock()
r = praw.Reddit(user_agent=useragent, site_name='FCbot')
r.refresh_access_information()
bot_name = r.get_me().name

if __name__ == '__main__':
    main()
