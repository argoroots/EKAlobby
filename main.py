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
import cPickle
import webapp2
import jinja2
import logging


rooms_url = 'https://eka.entu.ee/api/get_entity_list?only_public=true&full_info=true&entity_definition_keyname=room'
news_url  = 'http://www.artun.ee/?feed=newsticker'
timezone  = 'Europe/Tallinn'


class ShowPage(webapp2.RequestHandler):
    def get(self, room):
        news = []
        cache_events = []
        events = []

        try:
            logging.info('Start')

            news = _get_cache('news', [])
            cache_events = _get_cache('events', [])

            logging.info('Cache loaded')

            for e in cache_events:
                if e.get('room')[:len(room)].upper() != room.upper():
                    continue
                if e.get('start').date() > _get_time(date.today()).date():
                    continue
                if e.get('end') < _get_time(datetime.today()):
                    continue
                events.append(e)
            events = sorted(events, key=itemgetter('start', 'room'))
        except Exception, e:
            logging.error(e)

        logging.info('News: %s - Events: %s/%s' % (len(news), len(events), len(cache_events)))

        template = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__)))).get_template('template.html')
        self.response.out.write(template.render({
            'news': news,
            'events':  events,
        }))


class FillMemcache(webapp2.RequestHandler):
    def get(self):
        memcache.flush_all()
        try:
            news = []
            for n in xmltodict.parse(urlfetch.fetch(news_url, deadline=100).content).get('rss', {}).get('channel', {}).get('item'):
                news.append({
                    'date': _get_time(datetime.fromtimestamp(mktime(rfc822.parsedate(n.get('pubDate'))))),
                    'title': n.get('title'),
                    'text': n.get('description'),
                    'link': n.get('link'),
                })
            _set_cache(key='news', value=news, time=1800)
            logging.info('News added to Memcache: %s' % len(news))
        except Exception, e:
            logging.error('News import: ' % e)

        try:
            events = []
            rooms = json.loads(urlfetch.fetch(rooms_url, deadline=100).content)
            logging.info('Started to load %s rooms' % len(rooms))
            for idx, r in enumerate(rooms):
                if not r.get('properties', {}).get('calendar', {}).get('values'):
                    logging.warning('#%s - %s - No iCal property' % (idx, r.get('displayname')))
                    continue
                for v in r.get('properties', {}).get('calendar', {}).get('values'):
                    if not v.get('value'):
                        logging.warning('#%s - %s - No iCal URL' % (idx, r.get('displayname')))
                        continue
                    ical_file = urlfetch.fetch(v.get('value'), deadline=100).content
                    try:
                        ical = Calendar.from_ical(ical_file)
                        for c in ical.walk():
                            if c.name != "VEVENT":
                                continue
                            events.append({
                                'room': r.get('displayname'),
                                'info': r.get('displayinfo'),
                                'start': _get_time(c.get('dtstart').dt),
                                'end': _get_time(c.get('dtend').dt),
                                'summary': c.get('summary'),
                            })
                        logging.info('#%s - %s - OK' % (idx, r.get('displayname')))
                    except Exception, e:
                        logging.error('#%s - %s - Cant open %s' % (idx, r.get('displayname'), v.get('value')))
                        continue
            _set_cache(key='events', value=events, time=86400)
            logging.info('Events added to Memcache: %s' % len(events))
        except Exception, e:
            logging.error('Event import: ' % e)


def _get_time(t):
    try:
        return datetime.fromtimestamp(mktime(t.timetuple())).replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz(timezone))
    except Exception, e:
        logging.error('Invalid date: %s' % t)


def _set_cache(key, value, time=1800):
    l = 100000
    value = cPickle.dumps(value)
    values = [value[i:i+l] for i in range(0, len(value), l)]
    for idx, v in enumerate(values):
        memcache.add(key='%s_%s' % (key, idx), value=v, time=1800)
    memcache.add(key=key, value=len(values), time=1800)


def _get_cache(key, default=None):
    c = memcache.get(key)
    if not c:
        return default
    values = []
    for idx in range(0, int(c)):
        values.append(memcache.get(key='%s_%s' % (key, idx)))
    return cPickle.loads(''.join(values))


app = webapp2.WSGIApplication([
    ('/cache', FillMemcache),
    (r'/(.*)', ShowPage),
], debug=True)
