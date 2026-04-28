FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY server.js ./

ENV NODE_ENV=production \
    PORT=7799

EXPOSE 7799

CMD ["node", "server.js"]
