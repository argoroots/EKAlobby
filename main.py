#!/usr/bin/env python

from google.appengine.api import urlfetch

from operator import itemgetter
from datetime import datetime, date
from time import mktime
from dateutil import tz

from icalendar import Calendar, Event


import rfc822
import xmltodict
import json
import webapp2


rooms_url = 'https://dev.entu.ee/api/get_entity_list?only_public=true&full_info=true&entity_definition_keyname=room'
news_url  = 'http://beta.artun.ee/?feed=newsticker'
timezone  = 'Europe/Tallinn'


def _get_time(t):
    return datetime.fromtimestamp(mktime(t.timetuple())).replace(tzinfo=tz.gettz(timezone))


class GetRoomsCalendar(webapp2.RequestHandler):
    def get(self, room=''):
        room = room.strip('/')
        calendars = []
        rooms = json.loads(urlfetch.fetch(rooms_url, deadline=100).content)
        for r in rooms:
            if r.get('displayname')[:len(room)].upper() != room.upper():
                continue
            if not r.get('properties', {}).get('calendar', {}).get('values'):
                continue
            for v in r.get('properties', {}).get('calendar', {}).get('values'):
                if not v.get('value'):
                    continue
                ical_file = urlfetch.fetch(v.get('value'), deadline=100).content
                try:
                    ical = Calendar.from_ical(ical_file)
                except Exception, e:
                    continue
                calendar = []
                for c in ical.walk():
                    if c.name != "VEVENT":
                        continue
                    if _get_time(c.get('dtstart').dt).date() > date.today():
                        continue
                    if _get_time(c.get('dtend').dt).date() < date.today():
                        continue
                    calendars.append({
                        'name': r.get('displayname'),
                        'info': r.get('displayinfo'),
                        'start': str(_get_time(c.get('dtstart').dt)),
                        'end': str(_get_time(c.get('dtend').dt)),
                        'summary': c.get('summary'),
                        # 'description': c.get('description'),
                    })
        calendars = sorted(calendars, key=itemgetter('start', 'name', 'info'))

        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.write(json.dumps(calendars))


class GetNews(webapp2.RequestHandler):
    def get(self):
        news = []
        for n in xmltodict.parse(urlfetch.fetch(news_url, deadline=100).content).get('rss', {}).get('channel', {}).get('item'):
            news.append({
                'date': str(_get_time(datetime.fromtimestamp(mktime(rfc822.parsedate(n.get('pubDate')))))),
                'title': n.get('title'),
                'description': n.get('description'),
            })
        news = sorted(news, key=itemgetter('date', 'title'))

        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.write(json.dumps(news))


app = webapp2.WSGIApplication([
    (r'/room(.*)', GetRoomsCalendar),
    ('/news', GetNews)
], debug=True)
