# 프론트·관리자 정적 빌드. 빌드 컨텍스트는 저장소 루트다(프론트가 contracts·content 를 import 한다).
# 타깃 frontend, admin 이 같은 build 단계를 공유한다.
FROM node:24-slim AS build
RUN npm install -g pnpm@11
WORKDIR /src

COPY frontend/package.json frontend/pnpm-lock.yaml ./frontend/
RUN cd frontend && pnpm install --frozen-lockfile
COPY admin/package.json admin/pnpm-lock.yaml ./admin/
RUN cd admin && pnpm install --frozen-lockfile

COPY contracts ./contracts
COPY content ./content
COPY frontend ./frontend
COPY admin ./admin

# GA4 측정 ID 는 빌드 시점에 번들에 들어간다.
ARG VITE_GA_ID=""
RUN cd frontend && VITE_GA_ID="${VITE_GA_ID}" pnpm build
RUN cd admin && pnpm build

FROM nginx:1.29-alpine AS frontend
COPY deploy/nginx/spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/frontend/dist /usr/share/nginx/html

FROM nginx:1.29-alpine AS admin
COPY deploy/nginx/spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/admin/dist /usr/share/nginx/html
