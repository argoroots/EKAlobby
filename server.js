const fs = require('fs')
const http = require('http')
const mime = require('mime-types')
const path = require('path')



// create server
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

//start server
server.listen(process.env.PORT)
