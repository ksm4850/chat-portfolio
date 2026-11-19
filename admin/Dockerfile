# 로컬 개발용 이미지. 소스는 compose에서 마운트하고 Vite dev 서버로 실행한다.
FROM node:24-slim

RUN npm install -g pnpm@11

WORKDIR /app/admin
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5175
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5175"]
