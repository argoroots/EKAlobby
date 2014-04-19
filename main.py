#!/usr/bin/env python

from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from operator import itemgetter
from datetime import datetime
from time import mktime
from dateutil import tz


import os
import rfc822
import xmltodict
import json
import webapp2
import jinja2
import logging
import vobject


rooms_url = 'https://eka.entu.ee/api/get_entity_list?only_public=true&full_info=true&entity_definition_keyname=room'
news_url  = 'http://www.artun.ee/?feed=newsticker'
timezone  = 'Europe/Tallinn'


class News(ndb.Model):
    date  = ndb.DateTimeProperty(indexed=False)
    title = ndb.StringProperty(indexed=False)
    text  = ndb.TextProperty(indexed=False)
    link  = ndb.TextProperty(indexed=False)

    @property
    def local_date(self):
        return datetime.fromtimestamp(mktime(self.date.timetuple())).replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz(timezone))


class Events(ndb.Model):
    room    = ndb.StringProperty(indexed=False)
    info    = ndb.StringProperty(indexed=False)
    start   = ndb.DateTimeProperty(indexed=False)
    end     = ndb.DateTimeProperty()
    summary = ndb.TextProperty(indexed=False)

    @property
    def local_start(self):
        return datetime.fromtimestamp(mktime(self.start.timetuple())).replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz(timezone))

    @property
    def local_end(self):
        return datetime.fromtimestamp(mktime(self.end.timetuple())).replace(tzinfo=tz.gettz('UTC')).astimezone(tz.gettz(timezone))


class ShowPage(webapp2.RequestHandler):
    def get(self, room):
        news = []
        cache_events = []
        events = []

        try:
            logging.info('Start')

            news = News.query()
            cache_events = Events.query(Events.end >= datetime.today())
            events = []

            logging.info('DB loaded')

            for e in cache_events:
                if e.room[:len(room)].upper() != room.upper():
                    continue
                if e.start > datetime.today():
                    continue
                events.append({
                    'room':    e.room,
                    'info':    e.info,
                    'start':   e.local_start,
                    'end':     e.local_end,
                    'summary': e.summary,
                })
            events = sorted(events, key=itemgetter('start', 'end', 'room', 'summary'))
        except Exception, e:
            logging.error(e)

        logging.info('News: %s - Events: %s/%s' % (news.count(), len(events), cache_events.count()))

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
                guid = n.get('guid', {}).get('#text')
                if not guid:
                    continue

                post = ndb.Key(News, guid).get()
                if not post:
                    post = News(id=guid)

                if post.date == datetime.fromtimestamp(mktime(rfc822.parsedate(n.get('pubDate')))) and post.title == n.get('title') and post.text == n.get('description') and post.link == n.get('link'):
                    continue

                post.date  = datetime.fromtimestamp(mktime(rfc822.parsedate(n.get('pubDate'))))
                post.title = n.get('title')
                post.text  = n.get('description')
                post.link  = n.get('link')
                post.put()

            logging.info('News added to DB: %s' % len(news))
        except Exception, e:
            logging.error('News import: %s' % e)

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
                        for ical_component in vobject.readComponents(ical_file):
                            for ical_event in ical_component.vevent_list:
                                guid = '%s-%s' % (r.get('id'), ical_event.uid.value)
                                if not guid:
                                    continue

                                event = ndb.Key(Events, guid).get()
                                if not event:
                                    event = Events(id=guid)

                                if event.room == r.get('displayname') and event.info == r.get('displayinfo') and event.start == datetime.fromtimestamp(mktime(ical_event.dtstart.value.timetuple())) and event.end == datetime.fromtimestamp(mktime(ical_event.dtend.value.timetuple())) and event.summary == ical_event.summary.value:
                                    continue

                                event.room    = r.get('displayname')
                                event.info    = r.get('displayinfo')
                                event.start   = datetime.fromtimestamp(mktime(ical_event.dtstart.value.timetuple()))
                                event.end     = datetime.fromtimestamp(mktime(ical_event.dtend.value.timetuple()))
                                event.summary = ical_event.summary.value
                                event.put()

                        logging.info('#%s - %s - OK' % (idx, r.get('displayname')))
                    except Exception, e:
                        logging.warning('#%s - %s - Cant open %s (%s)' % (idx, r.get('displayname'), v.get('value'), e))
                        continue
            logging.info('Events added to DB: %s' % len(events))
        except Exception, e:
            logging.error('Event import: %s' % e)


app = webapp2.WSGIApplication([
    ('/cache', FillMemcache),
    (r'/(.*)', ShowPage),
], debug=True)
