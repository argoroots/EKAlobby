FROM node:6-slim

ADD ./ /usr/src/eka_lobby_harvester
RUN cd /usr/src/eka_lobby_harvester && npm --silent --production install

CMD ["node", "/usr/src/eka_lobby_harvester/master.js"]
