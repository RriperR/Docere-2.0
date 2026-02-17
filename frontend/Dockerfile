# 1. Stage: сборка
FROM node:20-alpine AS builder

WORKDIR /app

# Сначала копируем только package*.json — это позволит кэшировать слои установки
COPY package*.json ./
RUN npm ci

# Затем — весь остальной код (уже после установки)
COPY . .
RUN npm run build

# 2. Stage: артефакт
FROM alpine:3.18

WORKDIR /react
COPY --from=builder /app/dist ./dist
