#!/usr/bin/env python
#
from __future__ import print_function

import os
import sqlite3
import lxml.etree as ET

_dir = os.path.abspath(os.path.dirname(__file__))

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


conn = sqlite3.connect('artist_names.db')
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
    mod_fast_iter_context_from_filename(os.path.join(_dir, "discogs_20120101_artists.xml"), add_name)

finally:
    conn.commit()
    conn.close()
