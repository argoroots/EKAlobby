const _ = require('lodash')
const async = require('async')
const crypto = require('crypto')
const entities = require('html-entities').AllHtmlEntities
const fs = require('fs')
const http = require('http')
const ical = require('ical')
const mime = require('mime-types')
const op = require('object-path')
const parseString = require('xml2js').parseString
const path = require('path')
const request = require('request')


const interval = process.env.HARVEST_INTERVAL || 1000 * 60 * 20

const newsFile = path.resolve(__dirname, 'json', 'news.json')
const eventsFile = path.resolve(__dirname, 'json', 'events.json')
var newsMd5
var eventsMd5


var getNews = (news_url, callback) => {
    request.get({url: news_url, strictSSL: true, timeout: 10000}, (err, response, body) => {
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
    request.get({url: rooms_url, strictSSL: true, json: true, timeout: 10000}, (err, response, body) => {
        if(err) { return callback(err) }

        let rooms = []
        for (let i = 0; i < body.length; i++) {
            if(!op.get(body, [i, 'properties', 'calendar', 'values', 0, 'value'])) { continue }

            rooms.push({
                title: op.get(body, [i, 'displayname']),
                info: op.get(body, [i, 'displayinfo']),
                ical: op.get(body, [i, 'properties', 'calendar', 'values', 0, 'value']),
            })
        }

        callback(null, rooms)
    })
}


var getMd5 = (str) => {
    return crypto.createHash('md5').update(str, 'utf8').digest('hex')
}


var getFileMd5 = (path) => {
    if (!fs.existsSync(path)) { return }

    return getMd5(fs.readFileSync(path, 'utf8'))
}


var doHarvest = () => {
    getNews('http://www.artun.ee/?feed=newsticker', (err, news) => {
        if (err) { return console.error(err) }

        var sortedNews = JSON.stringify(_.sortBy(news, ['date']))

        if (getMd5(sortedNews) === (newsMd5 || getFileMd5(newsFile))) {
            // console.log((new Date()).toISOString(), `News: not changed`)
        } else {
            fs.writeFile(newsFile, sortedNews, 'utf8', () => {
                newsMd5 = getFileMd5(newsFile)
                console.log((new Date()).toISOString(), `News: ${news.length}`)
            })
        }
    })

    getRooms('https://eka.entu.ee/api/get_entity_list?only_public=true&full_info=true&entity_definition_keyname=room', (err, rooms) => {
        if (err) { return console.error(err) }

        var events = []
        async.each(rooms, (room, callback) => {
            ical.fromURL(room.ical, {}, function(err, data) {
                if (err) {
                    console.error(room.ical)
                    console.error(err)
                    return callback(null)
                }

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
            if (err) { return console.error(err) }

            var sortedEvents = JSON.stringify(_.sortBy(events, ['start', 'end', 'title']))

            if (getMd5(sortedEvents) === (eventsMd5 || getFileMd5(eventsFile))) {
                // console.log((new Date()).toISOString(), `Events: not changed`)
            } else {
                fs.writeFile(eventsFile, sortedEvents, 'utf8', () => {
                    eventsMd5 = getFileMd5(eventsFile)
                    console.log((new Date()).toISOString(), `Events: ${events.length}`)
                })
            }
        })
    })
}


var server = http.createServer((request, response) => {
    var filePath = request.url.split('?')[0]
    var contentType = mime.lookup(path.extname(filePath)) || 'application/octet-stream'

    fs.readFile(filePath, (err, content) => {
        if (err) {
            response.writeHead(404, { 'Content-Type': 'text/plain' })
            response.end('404\n')
        } else {
            response.writeHead(200, { 'Content-Type': contentType })
            response.end(content, 'utf-8')
        }
    })
})

server.listen(process.env.PORT)

doHarvest()

setInterval(doHarvest, interval)
