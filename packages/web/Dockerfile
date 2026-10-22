# Static SPA. Build it first with `npm run build:web`; the ingress routes /v1 to the API.
FROM nginx:1.31-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY dist /usr/share/nginx/html

EXPOSE 80
