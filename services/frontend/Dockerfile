# Frontend-контейнер запускает dev-сервер Vite. Наружу он публикуется
# через reverse-proxy nginx (см. nginx/nginx.conf).
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
