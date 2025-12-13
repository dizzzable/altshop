FROM node:20-alpine AS base

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Build stage
FROM base AS builder

# Copy workspace files
COPY package.json pnpm-workspace.yaml turbo.json ./
COPY apps/backend/package.json ./apps/backend/

# Install dependencies
RUN pnpm install

# Copy source code
COPY apps/backend ./apps/backend

# Build the application
RUN pnpm --filter backend build

# Production stage
FROM base AS production

# Install wget for healthcheck
RUN apk add --no-cache wget

WORKDIR /app

# Copy package files
COPY package.json pnpm-workspace.yaml ./
COPY apps/backend/package.json ./apps/backend/

# Install production dependencies only
RUN pnpm install --prod

# Copy built application
COPY --from=builder /app/apps/backend/dist ./apps/backend/dist

# Set environment
ENV NODE_ENV=production
ENV PORT=4000

# Expose port
EXPOSE 4000

# Start the application
CMD ["node", "apps/backend/dist/main.js"]