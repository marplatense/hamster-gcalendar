# -*- coding: UTF-8 -*-
"""Send all events stored in Hamster to Google Calendar"""
import datetime
import sqlite3 as sql
import os.path

import atom
from gdata.calendar import client, data
from gdata.gauth import ClientLoginToken

# TODO: find out how to find Hamster's db location
db_path = os.path.expanduser(u"~/.local/share/hamster-applet/hamster.db")
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
        """An authentication token generated by Google when we use the
        client_login routine for the first time. Next time we want to connect,
        instead of submitting user and password once again, we can provide the
        auth token
        """
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
        """Timestamp of the last time we sync Hamster's db with Google
        Calendar"""
        return self._last_update

    @last_update.setter
    def last_update(self, value):
        if value != self._last_update:
            self._last_update = value
            self.cur.execute("update google_parameters set last_update=?",
                             (self._last_update,))
            conn.commit()

param = GoogleParameters()

def gcalendar_connect(user=None, password=None):
    """Routine for connecting with a Google Calendar account. 
    If this is the first time we connect, we need to send the user and password
    identification.  If we connect ok, we can get an auth token we can save in 
    the database and don't ask for the user and password again.
    If everything's ok, we return the gc (GoogleCalendar) connection
    """
    global param
    gc = client.CalendarClient(source=source)
    try:
        if param.token_string is None:
            # we never connected or we lost our token
            gc.ClientLogin(user, password, client.source)
            # let's get a new token and keep on going
            param.token_string = gc.auth_token.token_string
        else:
            # we have a token, let's connect
            gc.auth_token = ClientLoginToken(param.token_string)
    except Exception, e:
        raise(GoogleParametersError("We couldn't connect with Google. We "
                                    "got %s error and this was the "
                                    "companion message: %s" %\
                                    (e.__class__.__name__, e.args[0])))
    return gc

def collect_new_events():
    """Look for new events in the database that were added after the last time
    we upload something to google calendar. Return a list of sqlite's
    rows. The returned structure should be as follows:
        start_time: start date of the activity, unicode
        end_time: end date of the activity, unicode
        description: self explained
        tag: self explained
        activity: id.
        timestamp: this moment
    """
    global param
    # qry string to bring all the required data
    qry = "SELECT facts.start_time as start_time, facts.end_time as end_time,"\
          "facts.description as description, tags_fact.name as tag, "\
          "activities.name as activity, ? as timestamp FROM facts "\
          "inner join activities on (facts.activity_id=activities.id) "\
          "inner join (select tags.id, tags.name, fact_tags.fact_id from "\
          "tags inner join fact_tags on (tags.id=fact_tags.tag_id)) as "\
          "tags_fact on (facts.id=tags_fact.fact_id) where facts.end_time "\
          "is not null and facts.end_time>=? order by tags_fact.name, "\
          "facts.start_time"
    cur = get_sqlite_cursor()
    cur.execute(qry, (datetime.datetime.now(), param.last_update))
    return cur.fetchall()

def create_calendar(gc, name, summary):
    """Create a new calendar in Google. You need to pass the calendar name and
    the summary."""
    calendar = data.CalendarEntry()
    calendar.title = atom.data.Title(text=name)
    calendar.summary = atom.data.Summary(text=summary)
    new_calendar = gc.InsertCalendar(new_calendar=calendar)
    return new_calendar

def insert_event(calendar, event_title, event_description, event_st,
                 event_et):
    """Insert a new event in a given calendar"""
    # paranoid check
    if not isinstance(calendar, data.CalendarEventFeed):
        raise(Exception("calendar must be an instance of CalendarEventFeed"))
    event = data.CalendarEventEntry()
    event.title = atom.data.Title(text=event_title)
    event.content = atom.data.Content(text=event_description)
    event.content = atom.data.Content(text=event_description)
    start_time = "%04d-%02d-%02dT%02d:%02d:%02d" % (event_st.year,
                                                    event_st.month,
                                                    event_st.day,
                                                    event_st.hour,
                                                    event_st.minute,
                                                    event_st.second)
    end_time = "%04d-%02d-%02dT%02d:%02d:%02d" % (event_et.year,
                                                  event_et.month,
                                                  event_et.day,
                                                  event_et.hour,
                                                  event_et.minute,
                                                  event_et.second)
    event.when.append(data.When(start=start_time, end=end_time))
    new_event = calendar.InsertEvent(event)
    return new_event

def iter_new_events(gc, events):
    """Inspect new events and insert in the corresponding calendar
    accordingly"""
    used_cals = []
    cal_feed = gc.get_own_calendars_feed()
    ev_res = []
    for i in cal_feed.entry:
        for j in [l for l in events if l['tag'].upper()==i.title.text.upper()]:
            insert_event(i, j['activity'], j['description'], 
                         datetime.datetime.strptime(j['start_time'], 
                                                    '%Y-%m-%d %H:%M:%S'),
                         datetime.datetime.strptime(j['end_time'], 
                                                    '%Y-%m-%d %H:%M:%S'))
            # if the tag is in this list, we used this cal.
            used_cals.append(l['tag'])

if __name__ == '__main__':
    gc = gcalendar_connect()
    events = collect_new_events()






