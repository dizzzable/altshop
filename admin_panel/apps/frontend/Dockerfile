FROM node:20-alpine AS base

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Build stage
FROM base AS builder

# Copy workspace files
COPY package.json pnpm-workspace.yaml turbo.json ./
COPY apps/frontend/package.json ./apps/frontend/

# Install dependencies
RUN pnpm install

# Copy source code
COPY apps/frontend ./apps/frontend

# Build the application
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN pnpm --filter frontend build

# Production stage with nginx
FROM nginx:alpine AS production

# Install wget for healthcheck
RUN apk add --no-cache wget

# Copy custom nginx config
COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built application
COPY --from=builder /app/apps/frontend/dist /usr/share/nginx/html

# Expose port
EXPOSE 4080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]