FROM oven/bun:1-alpine AS deps

WORKDIR /app

COPY apps/frontend/package.json apps/frontend/bun.lock /app/
RUN bun install --frozen-lockfile

FROM deps AS dev

COPY apps/frontend /app

EXPOSE 5174

ENV VITE_PROXY_TARGET=http://backend:8001

CMD ["bun", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5174"]

FROM deps AS build

COPY apps/frontend /app

ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

RUN bun run build

FROM nginx:1.27-alpine AS production

COPY apps/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
