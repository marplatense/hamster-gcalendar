# -*- coding: UTF-8 -*-
"""Send all events stored in Hamster to Google Calendar"""

import sqlite3 as sql

# TODO: find out how to find Hamster's db location
db_path = u"/home/mariano/.local/share/hamster-applet/hamster.db"
source = "hamster-gcalendar"
conn = None

def get_sqlite_cursor():
    """Return a sqlite's cursor. If connection is None, connect first"""
    global conn
    global db_path
    if conn is None:
        conn = sql.connect(db_path)
        conn.row_factory = sql.Row
    return conn.cursor()

class GoogleParameters(object):
    """Poor man's ORM for data stored in the db"""

    def __init__(self):
        self.cur = get_sqlite_cursor()
        self.cur.execute("create table if not exists google_parameters "
                         "(token_string text, last_update datetime)")
        self.cur.execute("select * from google_parameters")
        r = self.cur.fetchone()
        if r is None:
            self._token_string = None
            self._last_update = None
            self.cur.execute("insert into google_parameters values (?, ?)",
                             (self.token_string, self.last_update))
            conn.commit()
        else:
            self._token_string = r['token_string']
            self._last_update = r['last_update']

    def __repr__(self):
        return "<Parameters: Last update on %s>" % (self.last_update)

    @property
    def token_string(self):
        return self._token_string

    @token_string.setter
    def token_string(self, value):
        if value != self._token_string:
            self._token_string = value
            self.cur.execute("update google_parameters set token_string=?",
                             (self._token_string,))
            conn.commit()

    @property
    def last_update(self):
        return self._last_update

    @last_update.setter
    def last_update(self, value):
        if value != self._last_update:
            self._last_update = value
            self.cur.execute("update google_parameters set last_update=?",
                             (self._last_update,))
            conn.commit()

def gcalendar_connect(user, password):
    """If this is the first time we connect, we need to pass user and password.
    If we connect ok, we can get an auth token we can save in the database
    """
    param = GoogleParameters()
    if param.token_string is None:
        pass



