FROM node:20.19-alpine AS frontend-builder

WORKDIR /app/web-app

COPY web-app/package.json web-app/package-lock.json ./

RUN npm ci --legacy-peer-deps

COPY web-app/ ./

RUN npm run build

FROM nginx:1.28-alpine AS final

RUN mkdir -p /etc/nginx/ssl /opt/altshop/webapp /etc/nginx/altshop

COPY nginx/nginx.conf /etc/nginx/altshop/default.conf.template
COPY nginx/docker-entrypoint.d/10-render-default-conf.sh /docker-entrypoint.d/10-render-default-conf.sh
COPY --from=frontend-builder /app/web-app/dist /opt/altshop/webapp

RUN chmod +x /docker-entrypoint.d/10-render-default-conf.sh
