const _ = require('lodash')
const async = require('async')
const entities = require('html-entities').AllHtmlEntities
const fs = require('fs')
const ical = require('ical')
const op = require('object-path')
const parseString = require('xml2js').parseString
const request = require('request')


const interval = 1000 * 60 * 15


var getNews = (news_url, callback) => {
    request.get({url: news_url, strictSSL: true, timeout: 1000}, (err, response, body) => {
        if(err) { return callback(err) }

        parseString(body, { trim: true, normalizeTags: true, ignoreAttrs: true }, (err, result) => {
            if(err) { return callback(err) }

            const rss = op.get(result, 'rss.channel.0.item')

            let news = []
            for (let i = 0; i < rss.length; i++) {
                news.push({
                    title: op.get(rss, [i, 'title', 0]),
                    date: new Date(op.get(rss, [i, 'pubdate', 0])),
                    text: op.get(rss, [i, 'description', 0]).replace('[&#8230;]', '...'),
                    url: op.get(rss, [i, 'link', 0])
                })
            }

            callback(null, news)
        })
    })
}


var getRooms = (rooms_url, callback) => {
    request.get({url: rooms_url, strictSSL: true, json: true, timeout: 1000}, (err, response, body) => {
        if(err) { return callback(err) }

        let rooms = []
        for (let i = 0; i < body.length; i++) {
            if(!op.has(body, [i, 'properties', 'calendar', 'values', 0, 'value'])) { continue }

            rooms.push({
                title: op.get(body, [i, 'displayname']),
                info: op.get(body, [i, 'displayinfo']),
                ical: op.get(body, [i, 'properties', 'calendar', 'values', 0, 'value']),
            })
        }

        callback(null, rooms)
    })
}


var doHarvest = () => {
    console.log('')

    getNews('http://www.artun.ee/?feed=newsticker', (err, news) => {
        if (err) { console.error(err) }

        sortedNews = _.sortBy(news, ['date'])

        fs.writeFile(path.resolve(__dirname, 'json', 'news.json'), JSON.stringify(sortedNews, null, 3), 'utf8', () => {
            console.log((new Date()).toISOString(), `News: ${sortedNews.length}`);
        })
    })

    getRooms('https://eka.entu.ee/api/get_entity_list?only_public=true&full_info=true&entity_definition_keyname=room', (err, rooms) => {
        if (err) { console.error(err) }

        console.log((new Date()).toISOString(), `Rooms: ${rooms.length}`)

        var events = []
        async.each(rooms, (room, callback) => {
            ical.fromURL(room.ical, {}, function(err, data) {
                if(err) { return callback(err) }

                for (let k in data) {
                    if (!data.hasOwnProperty(k)) { continue }
                    if (op.get(data, [k, 'type']) !== 'VEVENT') { continue }

                    events.push({
                        title: room.title,
                        info: room.info,
                        start: op.get(data, [k, 'start']),
                        end: op.get(data, [k, 'end']),
                        summary: entities.decode(op.get(data, [k, 'summary'])),
                        description: entities.decode(op.get(data, [k, 'description']))
                    })
                }

                callback(null)
            })
        }, err => {
            if (err) { console.error(err) }

            sortedEvents = _.sortBy(events, ['start', 'end', 'title'])

            fs.writeFile(path.resolve(__dirname, 'json', 'events.json'), JSON.stringify(sortedEvents, null, 3), 'utf8', () => {
                console.log((new Date()).toISOString(), `Events: ${sortedEvents.length}`)
            })
        })
    })
}


setInterval(doHarvest, interval)


doHarvest()
