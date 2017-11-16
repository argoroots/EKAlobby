FROM node:8-slim

ADD ./ /usr/src/eka_lobby
RUN cd /usr/src/eka_lobby && npm --silent --production install

CMD ["node", "/usr/src/eka_lobby/worker.js"]
