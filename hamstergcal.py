# -*- coding: UTF-8 -*-
"""Send all events stored in Hamster to Google Calendar"""

import sqlite3 as sql

from gdata.calendar import client
from gdata.gauth import ClientLoginToken

# TODO: find out how to find Hamster's db location
db_path = u"/home/mariano/.local/share/hamster-applet/hamster.db"
source = "hamster-gcalendar"
conn = None

def get_sqlite_cursor():
    """Return a sqlite's cursor. If connection is None, connect first"""
    global conn
    if conn is None:
        conn = sql.connect(db_path)
        conn.row_factory = sql.Row
    return conn.cursor()

class GoogleParametersError(Exception): pass

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
                             (self._token_string, self._last_update))
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

def gcalendar_connect(user=None, password=None):
    """If this is the first time we connect, we need to pass user and password.
    If we connect ok, we can get an auth token we can save in the database and
    don't ask for the user and password again.
    If everything's ok, we return the gc (GoogleCalendar) connection
    """
    param = GoogleParameters()
    gc = client.CalendarClient(source=source)
    if param.token_string is None:
        # we never connected or we lost our token
        try:
            gc.ClientLogin(user, password, client.source)
        except Exception, e:
            raise(GoogleParametersError("We couldn't connect with Google. We "
                                        "got %s error and this was the "
                                        "companion message: %s" %\
                                        (e.__class__.__name__, e.args[0])))

        # let's get a new token and keep on going
        param.token_string = gc.auth_token.token_string
    else:
        gc.auth_token = ClientLoginToken(param.token_string)
    return gc




