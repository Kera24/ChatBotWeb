# Builds the public widget SDK + iframe release bundle and stages it for
# static serving by the reverse proxy. Produces the same content-hashed,
# manifest-described layout as `npm run widget:release:build`
# (see apps/widget/scripts/build-release.mjs and deployment/widget/headers.json).
#
# This is a build-and-publish step, not a long-running service: the final
# stage copies pre-built assets into the mounted /out volume and exits.

FROM node:20-alpine AS build

WORKDIR /repo

ARG WIDGET_RELEASE_ENVIRONMENT=production
ARG WIDGET_RELEASE_CHANNEL=stable
ARG WIDGET_PUBLIC_ORIGIN
ARG WIDGET_PUBLIC_API_ORIGIN
ARG WIDGET_SDK_PUBLIC_ORIGIN

ENV WIDGET_RELEASE_ENVIRONMENT=$WIDGET_RELEASE_ENVIRONMENT \
    WIDGET_RELEASE_CHANNEL=$WIDGET_RELEASE_CHANNEL \
    WIDGET_PUBLIC_ORIGIN=$WIDGET_PUBLIC_ORIGIN \
    WIDGET_PUBLIC_API_ORIGIN=$WIDGET_PUBLIC_API_ORIGIN \
    WIDGET_SDK_PUBLIC_ORIGIN=$WIDGET_SDK_PUBLIC_ORIGIN

COPY packages/widget-sdk ./packages/widget-sdk
COPY apps/widget ./apps/widget
COPY deployment/widget/headers.json ./deployment/widget/headers.json

RUN npm --prefix packages/widget-sdk ci \
    && npm --prefix packages/widget-sdk run build \
    && npm --prefix apps/widget ci \
    && npm --prefix apps/widget run build \
    && node apps/widget/scripts/build-release.mjs

FROM alpine:3.20

COPY --from=build /repo/artifacts/widget-release /widget-release

CMD ["sh", "-c", "rm -rf /out/* && cp -r /widget-release/. /out/ && echo 'widget assets published to /out'"]
