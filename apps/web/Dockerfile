FROM node:20-alpine AS build

WORKDIR /app/apps/web

ENV NEXT_TELEMETRY_DISABLED=1

COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web ./
RUN npm run build
RUN npm prune --omit=dev

FROM node:20-alpine AS runtime

WORKDIR /app/apps/web

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

COPY --from=build --chown=nextjs:nodejs /app/apps/web/package*.json ./
COPY --from=build --chown=nextjs:nodejs /app/apps/web/node_modules ./node_modules
COPY --from=build --chown=nextjs:nodejs /app/apps/web/next.config.mjs ./next.config.mjs
COPY --from=build --chown=nextjs:nodejs /app/apps/web/.next ./.next
COPY --from=build --chown=nextjs:nodejs /app/apps/web/app ./app
COPY --from=build --chown=nextjs:nodejs /app/apps/web/components ./components
COPY --from=build --chown=nextjs:nodejs /app/apps/web/lib ./lib

USER nextjs

EXPOSE 3000

CMD ["npm", "run", "start"]
