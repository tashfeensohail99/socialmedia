# ─── Frontend (Next.js standalone) Docker image ────────────────────────
# Three-stage build for minimal runtime size (~150MB vs ~1.2GB without).
# Requires `output: "standalone"` in next.config.ts (we have that).
#
# Build:    docker build -t summit-frontend .
# Run:      docker run -p 3100:3000 -e NEXT_PUBLIC_API_URL=... summit-frontend

# ─── deps ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# `npm install` (not `npm ci`) because the lock file is generated on
# Windows and won't have Linux-specific optional native deps recorded —
# `ci` is strict about that and aborts. `install` reconciles the diff.
RUN npm install --no-audit --no-fund

# ─── builder ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* env vars are baked in at build time. Railway sets these
# via the service config; the build picks them up automatically.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ─── runner ───────────────────────────────────────────────────────────
FROM node:20-alpine AS runner

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Copy the standalone build (it embeds only the modules actually used).
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
