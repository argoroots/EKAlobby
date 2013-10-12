#!/usr/bin/env python

from google.appengine.api import urlfetch
from google.appengine.api import memcache

from operator import itemgetter
from datetime import datetime, date
from time import mktime
from dateutil import tz

from icalendar import Calendar, Event


import os
import rfc822
import xmltodict
import json
import webapp2
import jinja2
import logging


rooms_url = 'https://eka.entu.ee/api/get_entity_list?only_public=true&full_info=true&entity_definition_keyname=room'
news_url  = 'http://beta.artun.ee/?feed=newsticker'
timezone  = 'Europe/Tallinn'


class ShowPage(webapp2.RequestHandler):
    def get(self, room):
        template = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__)))).get_template('template.html')
        self.response.out.write(template.render({
            'calendar':  _get_calendars(room)[:15],
            'news': _get_news(),
        }))


class FillMemcache(webapp2.RequestHandler):
    def get(self):
        _get_calendars()


def _get_calendars(filter=''):
    calendars = []
    try:
        rooms = json.loads(urlfetch.fetch(rooms_url, deadline=100).content)
        for r in rooms:
            if r.get('displayname')[:len(filter)].upper() != filter.upper():
                continue
            if not r.get('properties', {}).get('calendar', {}).get('values'):
                continue
            for v in r.get('properties', {}).get('calendar', {}).get('values'):
                if not v.get('value'):
                    continue
                try:
                    ical_file = memcache.get('ical_%s' % v.get('id'))
                    if not ical_file:
                        ical_file = urlfetch.fetch(v.get('value'), deadline=100).content
                        memcache.add(key='ical_%s' % v.get('id'), value=calendars, time=86400)
                    ical = Calendar.from_ical(ical_file)
                except Exception, e:
                    continue
                calendar = []
                for c in ical.walk():
                    if c.name != "VEVENT":
                        continue
                    if _get_time(c.get('dtstart').dt).date() > _get_time(date.today()).date():
                        continue
                    if _get_time(c.get('dtend').dt).date() < _get_time(datetime.today()).date():
                        continue
                    calendars.append({
                        'name': r.get('displayname'),
                        'info': r.get('displayinfo'),
                        'start': _get_time(c.get('dtstart').dt),
                        'end': _get_time(c.get('dtend').dt),
                        'summary': c.get('summary'),
                    })
        calendars = sorted(calendars, key=itemgetter('start', 'name', 'info'))
    except Exception, e:
        logging.error(e)
    return calendars


def _get_news():
    news =  memcache.get('news')
    if news:
        return news
    news = []
    try:
        for n in xmltodict.parse(urlfetch.fetch(news_url, deadline=100).content).get('rss', {}).get('channel', {}).get('item'):
            news.append({
                'date': _get_time(datetime.fromtimestamp(mktime(rfc822.parsedate(n.get('pubDate'))))),
                'title': n.get('title'),
                'description': n.get('description'),
            })
        news = sorted(news, key=itemgetter('date', 'title'), reverse=True)
    except Exception, e:
        logging.error(e)
    memcache.add(key='news', value=news, time=1800)
    return news


def _get_time(t):
    return datetime.fromtimestamp(mktime(t.timetuple())).replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz(timezone))


app = webapp2.WSGIApplication([
    ('/fill_memcache', FillMemcache),
    (r'/(.*)', ShowPage),
], debug=True)
