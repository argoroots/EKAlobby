#!/usr/bin/env python

from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from operator import itemgetter
from datetime import datetime, date
from time import mktime
from dateutil import tz


import os
import rfc822
import xmltodict
import json
import cPickle
import webapp2
import jinja2
import logging
import vobject


rooms_url = 'https://eka.entu.ee/api/get_entity_list?only_public=true&full_info=true&entity_definition_keyname=room'
news_url  = 'http://www.artun.ee/?feed=newsticker'
timezone  = 'Europe/Tallinn'


class Cache(ndb.Model):
  value = ndb.PickleProperty()
  updated = ndb.DateTimeProperty(auto_now=True)


class ShowPage(webapp2.RequestHandler):
    def get(self, room):
        news = []
        cache_events = []
        events = []

        try:
            logging.info('Start')

            news = _get_cache('news', [])
            cache_events = _get_cache('events', [])

            logging.info('DB loaded')

            for e in cache_events:
                if e.get('room')[:len(room)].upper() != room.upper():
                    continue
                if e.get('end') < _get_time(datetime.today()):
                    continue
                if e.get('start').date() > _get_time(datetime.today()).date():
                    continue
                events.append(e)
            events = sorted(events, key=itemgetter('start', 'end', 'room', 'summary'))
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
        news = []
        events = []

        try:
            for n in xmltodict.parse(urlfetch.fetch(news_url, deadline=100).content).get('rss', {}).get('channel', {}).get('item'):
                news.append({
                    'date': _get_time(datetime.fromtimestamp(mktime(rfc822.parsedate(n.get('pubDate'))))),
                    'title': n.get('title'),
                    'text': n.get('description'),
                    'link': n.get('link'),
                })
            _set_cache(key='news', value=news)
            logging.info('News added to DB: %s' % len(news))
        except Exception, e:
            logging.error('News import: ' % e)

        try:
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
                    try:
                        ical_file = urlfetch.fetch(v.get('value'), deadline=100).content
                        for component in vobject.readComponents(ical_file):
                            for event in component.vevent_list:
                                if _get_time(event.dtend.value).date() < _get_time(datetime.today()).date():
                                    continue

                                events.append({
                                    'room': r.get('displayname'),
                                    'info': r.get('displayinfo'),
                                    'start': _get_time(event.dtstart.value),
                                    'end': _get_time(event.dtend.value),
                                    'summary': event.summary.value,
                                })

                        logging.info('#%s - %s - OK' % (idx, r.get('displayname')))
                    except Exception, e:
                        logging.warning('#%s - %s - Cant open %s (%s)' % (idx, r.get('displayname'), v.get('value'), e))
                        continue
            _set_cache(key='events', value=events)
            logging.info('Events added to DB: %s' % len(events))
        except Exception, e:
            logging.error('Event import: %s' % e)


def _get_time(t):
    try:
        return datetime.fromtimestamp(mktime(t.timetuple())).replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz(timezone))
    except Exception, e:
        logging.error('Invalid date: %s' % t)


def _set_cache(key, value, time=86400):
    c = Cache(id=key)
    c.value = value
    c.put()


def _get_cache(key, default=None):
    c = Cache.get_by_id(key)
    return c.value


app = webapp2.WSGIApplication([
    ('/cache', FillMemcache),
    (r'/(.*)', ShowPage),
], debug=True)
