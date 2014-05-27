#!/usr/bin/env python
#A bot to scan music reddits listing song covers(and youtube links)

from __future__ import print_function
import praw
import os
import datetime
import sys
import time
import re
import math
from lxml import html
from docopt import docopt
import itertools
import fuzzywuzzy

import second_hand_songs_wrapper as s
from debug_print import *
import sqlite3
from time import sleep

import logging
import logging.config
from dummy_thread import exit

import IPython
import markdown_tags as mt

__author__ = "Roman A. Taycher <rtaycher1987@gmail.com>"
__license__ = "MIT"
__version__ = "0.1"


subreddits = []
loginfiles = [ f for f in os.listdir(".") if f.endswith(".redditlogin")]
assert loginfiles
loginfile = loginfiles[0]
username = loginfile.split(".")[0]
with open(loginfile) as f:
    password = f.read().strip()

conn = None

class RedditLogin:
    r = None

    @classmethod
    def get_reddit(class_):
        if not class_.r:
            class_.r = praw.Reddit(user_agent='redditcoverbot')
            class_.r.login(username=username, password=password)
        return class_.r

def submissions_list_wout_old_submissions(submission_dict):
    submission_fresh_time = datetime.timedelta(hours=5)
    temp_submissions_dict = dict()
    for (key, submission) in submission_dict.iteritems():
        if (datetime.datetime.now()
                - datetime.datetime.fromtimestamp(submission.created_utc)
                < submission_fresh_time):
            temp_submissions_dict[key] = submission
    return temp_submissions_dict

praw.objects.Submission.__str__ = lambda x: str(dict([(" title", x.title),("link", x.url if "reddit.com/" not in x.url else "")]))
praw.objects.Submission.__repr__ = lambda x: repr(dict([(" title", x.title),("link", x.url if "reddit.com/" not in x.url else "")]))
def get_sample():
    reddit_login = RedditLogin.get_reddit()
    subreddit = reddit_login.get_subreddit("music")
    return subreddit.get_hot(limit=1000)

def monitor_subreddits(reddit_login, subreddit_list):
    new_submissions = []
    for subreddit_str in subreddit_list:
        subreddit = reddit_login.get_subreddit(subreddit_str)
        new_submissions += subreddit.get_new(limit=1000)
    return new_submissions

def check_submissions(submissions):
    for submission in submissions:
        check_no_comments_for_song_and_post_covers(submission, submit_song_covers)
        sleep(1)

def is_youtube_url(url):
    return "youtu" in url

def check_no_comments_for_song_and_post_covers(submission, action_on_find = lambda: None ):
    performance = None

    if s.is_youtube_url(submission.url):
        youtube_title = get_youtube_title(submission.url)
        if youtube_title:
            banned_symbols = ".;//\!"
            youtube_title = youtube_title.strip(banned_symbols)

            parts = split_title(youtube_title)
            for (i, part) in enumerate(parts):
                band_name = None
                for combo in no_skip_in_order_combinations_words(part):
                    if is_artist_or_band_name_in_local_db(combo):
                        band_name = combo
                        break
                if band_name:
                    break

            if band_name:
                bands = s.second_hand_search("",common_name=band_name)
                if bands:
                    band = bands[0]
                    performances = band.performances
                    for part in parts[i+1:] + parts[:i-1]:
                        for combo in no_skip_in_order_combinations_words(part):

                            matches = [combo == perf.title for perf in performances]
                            if matches:
                                performance = matches[0]
                                action_on_find({"matchedSong": performance, "submission": submission})

    submission_title = submission.title
    banned_symbols = ".;//\!"
    submission_title = submission_title.strip(banned_symbols)

    parts = split_title(submission_title)
    for (i, part) in enumerate(parts):
        band_name = None
        for combo in no_skip_in_order_combinations_words(part):
            if is_artist_or_band_name_in_local_db(combo):
                band_name = combo
                break
        if band_name:
            break

    if band_name:
        bands = s.second_hand_search("",common_name=band_name)
        if bands:
            band = bands[0]
            performances = band.performances
            for part in parts[i+1:] + parts[:i-1]:
                for combo in no_skip_in_order_combinations_words(part):
                    matches = [combo == perf.title for perf in performances]
                    if matches:
                        performance = matches[0]
                        action_on_find({"matchedSong": performance, "submission": submission})



def submit_song_covers(data):
    try:
        coversList = data["matchedSong"].covers
        botSignature = None
        logging.debug("line 88" + covers_message_string(data["matchedSong"], coversList, botSignature))
        data["submission"].add_comment(covers_message_string(data["matchedSong"], coversList, botSignature))
    except Exception, e:
        logging.debug(e)

def split_title(title):
    parens_contents = []
    re_match_parens = re.compile("(.*?)[\(\[](.*?)[\]\)](.*)",re.UNICODE)
    match = re_match_parens.match(title)
    while match:
        (pre, in_parens, post) = match.groups()
        in_parens = in_parens.strip()
        if in_parens:
            parens_contents.append(in_parens)
        title = pre + "--" + post
        match = re_match_parens.match(title)
    splits = [x.strip() for y in title.split("--") for x in y.split("-") if x.strip()] + parens_contents
    return splits


def no_skip_in_order_combinations_words(title_snippet):
    words = title_snippet.split(" ")
    return [" ".join(words[s:e]) for (s,e) in itertools.combinations(range(len(words)),2)]


def parseStringForArtistAndSongTitle(string):
    res_attempt = None
    common_symbols = [chr(x) for x in range(ord('A'), ord('Z') + 1) + range(ord('a'), ord('z') + 1)] + [str(x) for x in range(0, 9 + 1)]

    def split_string_by_chars_not_provided(string, provided):
        ans = []
        while string:
            for i in range(len(string)):
                if string[i] not in provided:
                    ans.append(string[0:i])
                    string = string[i + 1:]
                    break
            if i == len(string) - 1:
                ans.append(string)
                break
        return ans

    def remove_other_symbols(s):
        return " ".join(x for x in split_string_by_chars_not_provided(s, common_symbols) if x)


    part_one, part_two = (None, None)
    match = re.match("\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*\[\d+:\d+\]", string, flags=re.UNICODE)
    if match:
        part_one, part_two = match.groups()
    else:
        match = re.match("\s*([^-]+?)\s*-\s*([^-]+)\s*", string, flags=re.UNICODE)
        if match:
            part_one, part_two = match.groups()
        else:
            match = re.match("\s*([^-]+?)\s*-\s*\[\d+:\d+\]", string, flags=re.UNICODE)
            if match:
                part_one = match.groups()[0]
            else:
                match = re.match("\s*([^-]+?)\s*\[\d+:\d+\]", string, flags=re.UNICODE)
                if match:
                    part_one = match.groups()[0]
                else:
                    match = re.match("\s*([^-]+?)\s*-\s*([^-]+)", string, flags=re.UNICODE)
                    if match:
                        part_one = match.groups()[0]
                        part_two = match.groups()[1]
                    else:
                        match = re.match("\s*(.*)\s*", string, flags=re.UNICODE)
                        return None
                        if match:
                            part_one = match.groups()[0]
                        else:
                            return None
    try:
        part_one = remove_other_symbols(part_one)
        logging.debug("part_one:" + part_one)
        if part_two:
            part_two = remove_other_symbols(part_two)
            logging.debug("part_two:" + part_two)
            if is_artist_or_band_name_in_local_db(part_two):
                res_attempt = s.second_hand_search(part_one, type_=s.performance, performer=part_two)
            if not res_attempt and is_artist_or_band_name_in_local_db(part_one):
                res_attempt = s.second_hand_search(part_two, type_=s.performance, performer=part_one)
        else:
            res_attempt = s.second_hand_search(part_one, type_=s.performance)
    except Exception, e:
        logging.debug(e)
    if res_attempt:
        return res_attempt[0]
    else:
        return None


def get_youtube_title(url):
    try:
        doc = html.parse(url)
        title = doc.xpath('/html/head/meta[@name="title"]/@content')[0]
        return title
    except:
        return None

def parseForArtistAndSongTitleB(string):
    res_attempt = None
    common_symbols = [chr(x) for x in range(ord('A'), ord('Z') + 1) + range(ord('a'), ord('z') + 1)] + [str(x) for x in range(0, 9 + 1)]
    banned_symbols = ".;//\!"
    banned_symbols.strip(banned_symbols)
    def split_string_by_chars_not_provided(string, provided):
        ans = []
        while string:
            for i in range(len(string)):
                if string[i] not in provided:
                    ans.append(string[0:i])
                    string = string[i + 1:]
                    break
            if i == len(string) - 1:
                ans.append(string)
                break
        return ans

    def remove_other_symbols(s):
        return " ".join(x for x in split_string_by_chars_not_provided(s, common_symbols) if x)


    part_one, part_two = (None, None)
    match = re.match("\s*([^-]+?)\s*-\s*([^-]+?)\s*-\s*\[\d+:\d+\]", string, flags=re.UNICODE)
    if match:
        part_one, part_two = match.groups()
    else:
        match = re.match("\s*([^-]+?)\s*-\s*([^-]+)\s*", string, flags=re.UNICODE)
        if match:
            part_one, part_two = match.groups()
        else:
            match = re.match("\s*([^-]+?)\s*-\s*\[\d+:\d+\]", string, flags=re.UNICODE)
            if match:
                part_one = match.groups()[0]
            else:
                match = re.match("\s*([^-]+?)\s*\[\d+:\d+\]", string, flags=re.UNICODE)
                if match:
                    part_one = match.groups()[0]
                else:
                    match = re.match("\s*([^-]+?)\s*-\s*([^-]+)", string, flags=re.UNICODE)
                    if match:
                        part_one = match.groups()[0]
                        part_two = match.groups()[1]
                    else:
                        match = re.match("\s*(.*)\s*", string, flags=re.UNICODE)
                        return None
                        if match:
                            part_one = match.groups()[0]
                        else:
                            return None
    try:
        part_one = remove_other_symbols(part_one)
        logging.debug("part_one:" + part_one)
        if part_two:
            part_two = remove_other_symbols(part_two)
            logging.debug("part_two:" + part_two)
            if is_artist_or_band_name_in_local_db(part_two):
                res_attempt = s.second_hand_search(part_one, type_=s.performance, performer=part_two)
            if not res_attempt and is_artist_or_band_name_in_local_db(part_one):
                res_attempt = s.second_hand_search(part_two, type_=s.performance, performer=part_one)
        else:
            res_attempt = s.second_hand_search(part_one, type_=s.performance)
    except Exception, e:
        logging.debug(e)
    if res_attempt:
        return res_attempt[0]
    else:
        return None

def song_formatting(song):
        logging.debug(song)
        return mt.Link((song.title + (" by " + ",".join(artist.commonName for artist in song.credits))
                        if hasattr(song, "credits") else "", song.uri))

def covers_message_string(matchedSong, coversList, bot_signature=None):

    if not bot_signature:
        bot_signature = mt.Link(url="http://www.reddit.com/user/redditcoverbot", text="redditcoverbot")
    return mt.MD(mt.P("I think this song is ",
                      song_formatting(matchedSong),
                      mt.OrderedList.with_title("Covers for this song:", *(song_formatting(song)
                                                                                  for song in coversList)),
                      bot_signature if bot_signature else "")).tags_to_markdown(recover=False,
                                                                               format_md=mt.reddit_specific)


def is_artist_or_band_name_in_local_db(string):
    assert conn,"Not connected to artist database"
    #conn.execute('''INSERT OR IGNORE INTO names VALUES(?)''', (name,))
    return bool(list(conn.execute('SELECT * FROM stocks WHERE symbol=?', string.upper())))

def main(args=sys.argv[1:]):
    doc = """
    redditcoverbot.py
    
    Usage:
    
    Options:
      -h, --help
      -v, --version
      -l LOGFILE, --logfile LOGFILE            Log Config File [default: ./log.config]
      --crawler_update_min CRAWLER_UPDATE_MIN  how many minutes before polling for new submissions in subreddits [default: 5]
    """
    #      redditcoverbot.py -s SUBREDDIT --subreddit SUBREDDIT  [default: Music]

    #      redditcoverbot.py --logfile LOGFILE   Log Config File [default: ./log.config]

    arguments = docopt(doc, argv=args, help=True, version=__version__)
    print(arguments)
    logging.config.fileConfig(arguments["--logfile"])
    submission_dict = dict()
    subreddit_list = ["music"]
    global conn
    conn = sqlite3.connect('artist_names.db')
    try:
        while True:
            cycle_start_time = datetime.datetime.now()
            submission_dict.update(dict((x.id, x) for x in monitor_subreddits(RedditLogin.get_reddit(), subreddit_list)))
            submission_dict = submissions_list_wout_old_submissions(submission_dict)
    #        .debug("submission_list(size: " + str(len(submission_list)) + "):" + str([x.title for x in submission_list]))
            logging.debug("submission_dict len:" + str(len(submission_dict.values())))
    #        IPython.embed()

            check_submissions(submission_dict.values())

            time_diff = datetime.datetime.now() - cycle_start_time
            time_left_to_sleep = datetime.timedelta(seconds=math.ceil(60 * float(arguments["--crawler_update_min"]))) - time_diff
            if time_left_to_sleep.total_seconds() > 0:
                time.sleep(time_left_to_sleep.total_seconds())
    finally:
        if conn:
            conn.commit()
            conn.close()

if __name__ == "__main__":
    main()
