# syntax=docker/dockerfile:1

# Production-only image — dev still runs via native `npm run dev`
# (see CLAUDE.md's "Environment" section), this Dockerfile exists
# purely to produce a static build served behind the self-hosted
# Cloudflare Tunnel.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
# .npmrc only holds the registry URL + an env-var reference
# (${GITHUB_PACKAGES_TOKEN}), never a literal token, so it's safe to
# commit — the real value is supplied per the BuildKit secret mount
# below (`docker build --secret id=npm_token,env=GITHUB_PACKAGES_TOKEN`
# or the equivalent `build.secrets` block in docker-compose.prod.yml),
# never baked into an image layer.
RUN --mount=type=secret,id=npm_token,env=GITHUB_PACKAGES_TOKEN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
