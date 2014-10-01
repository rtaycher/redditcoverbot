#!/usr/bin/env python
#
from __future__ import print_function
from contextlib import closing
from datetime import datetime
import shutil
import urllib2
import os
import sqlite3
import zlib

from lxml import html
import lxml.etree as ET


_dir = os.path.abspath(os.path.dirname(__file__))
user_agent = "reddit_cover_bot/0.1 (https://github.com/rtaycher/redditcoverbot)"
def mod_fast_iter(context, func, *args, **kwargs):
    """
    http://www.ibm.com/developerworks/xml/library/x-hiperfparse/
    Author: Liza Daly
    See also http://effbot.org/zone/element-iterparse.htm
    """
    for event, elem in context:
        #print('Processing {e}'.format(e=ET.tostring(elem)))
        func(elem, *args, **kwargs)
        # It's safe to call clear() here because no descendants will be
        # accessed
        #print('Clearing {e}'.format(e=ET.tostring(elem)))
        elem.clear()
        # Also eliminate now-empty references from the root node to elem
        for ancestor in elem.xpath('ancestor-or-self::*'):
            #print('Checking ancestor: {a}'.format(a=ancestor.tag))
            while ancestor.getprevious() is not None:
                #print(   'Deleting {p}'.format(p=(ancestor.getparent()[0]).tag))
                del ancestor.getparent()[0]

def mod_fast_iter_context_from_filename(filename, func, *args, **kwargs):
    with open(filename) as f:
        mod_fast_iter(ET.iterparse(f, events=('end', ), tag='name'), func, *args, **kwargs)

def xml_to_db(xml_source_file, sqlite_dump):
    conn = sqlite3.connect(sqlite_dump)
    try:
        conn.execute('''CREATE TABLE  if not exists names(name PRIMARY KEY)''')

        def add_name(elem):
            if not elem.text:
                return
            name = elem.text.upper()
            if not name:
                return
            try:
                print("name is:" + repr(name))
                conn.execute('''INSERT OR IGNORE INTO names VALUES(?)''', (name,))
            except:
                raise
        mod_fast_iter_context_from_filename(xml_source_file, add_name)

    finally:
        conn.commit()
        conn.close()
def download_stream(response):
    DOWNLOAD_CHUNK_SIZE = 2**15
    while True:
        chunk = response.read(DOWNLOAD_CHUNK_SIZE)
        if chunk:
            yield chunk
        else:
            return
def stream_decompress(stream):
    dec = zlib.decompressobj(15+32)  # same as gzip module
    for chunk in stream:
        rv = dec.decompress(chunk)
        if rv:
            yield rv

def get_possibly_zipped_file(url_source, dest_filename):
    DOWNLOAD_CHUNK_SIZE = 2**15

    req = urllib2.Request(url_source, headers={ 'User-Agent': user_agent, 'Accept-encoding': 'gzip' })

    with closing(urllib2.urlopen(req)) as response:
        with open(dest_filename, 'wb') as dest_file:

            if response.info().get('Content-Type').endswith("gzip"):
                for chunk in stream_decompress(download_stream(response)):
                    dest_file.write(chunk)
            else:
                for chunk in download_stream(response):
                    dest_file.write(chunk)

def get_latest_discogs_artists_xml_file():
    base_url = "http://www.discogs.com/data/"
    req = urllib2.Request(base_url, headers={ 'User-Agent': user_agent })
    with closing(urllib2.urlopen(req)) as res:
        html_tree = html.parse(res)
    files_and_dates = [(file_list_row .xpath("string(.//a/@href)"),
                        file_list_row .xpath("string(./td[@class='m']/text())"))
                       for file_list_row in html_tree.xpath("//tr")]
    artist_list = [(f, d) for (f, d) in files_and_dates if "artists.xml" in f]
    assert artist_list, "there should be at least one artists.xml file link but there isn't"
    artist_list.sort(key=lambda (file_and_date_tuple): datetime.strptime(file_and_date_tuple[1], "%Y-%b-%d %H:%M:%S"))
    newest_artists_xml_name = sorted(artist_list)[0][0]
    newest_artist_url = base_url + "/" + newest_artists_xml_name
    download_path = os.path.join(_dir, newest_artists_xml_name).rstrip(".gz")
    get_possibly_zipped_file(newest_artist_url, download_path)
    return download_path

def backup(filename):
    if os.path.exists(filename):
        backup_name = filename + ".bak"
        while os.path.exists(backup_name):
            backup_name = backup_name + ".bak"
        print("backing up filename " + filename + " to " + backup_name)
        shutil.move(filename, backup_name)

def main():
    artist_db_path = os.path.join(_dir, 'artist_names.db')
    backup(artist_db_path)
    xml_to_db(get_latest_discogs_artists_xml_file(), os.path.join(_dir, artist_db_path))


if __name__ == "__main__":
    main()
