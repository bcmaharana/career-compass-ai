# syntax=docker/dockerfile:1

# Production-only image — dev still runs via native `npm run dev`
# (see CLAUDE.md's "Environment" section), this Dockerfile exists
# purely to produce a static build served behind the self-hosted
# Cloudflare Tunnel.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
