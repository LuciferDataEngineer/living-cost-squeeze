# Docker Hub and dl.min.io no longer serve the MinIO image anonymously.
# This image packages the still-public AGPL release binaries from GitHub.
FROM alpine:3.22
RUN apk add --no-cache ca-certificates curl
ARG MINIO_URL=https://github.com/minio/minio/releases/download/RELEASE.2025-09-07T16-13-09Z/minio.linux-amd64.RELEASE.2025-09-07T16-13-09Z
ARG MC_URL=https://github.com/minio/mc/releases/download/RELEASE.2025-08-13T08-35-41Z/mc.linux-amd64.RELEASE.2025-08-13T08-35-41Z
RUN curl -fsSL -o /usr/bin/minio "$MINIO_URL" \
    && curl -fsSL -o /usr/bin/mc "$MC_URL" \
    && chmod +x /usr/bin/minio /usr/bin/mc
EXPOSE 9000 9001
ENTRYPOINT ["/usr/bin/minio"]
