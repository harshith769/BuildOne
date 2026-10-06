# Postgres 18 + pgvector 0.8.7 + wal-g (continuous backup to R2) for the self-hosted option.
# Pinned and checksum-verified on 2026-10-05 against the published .sha256 file of the wal-g release.
# The Ubuntu 24.04 wal-g build needs glibc 2.34 or newer; Debian trixie ships 2.41.
FROM pgvector/pgvector:0.8.7-pg18-trixie
ARG WALG_VERSION=3.0.9
ARG WALG_ASSET=wal-g-pg-24.04-amd64.tar.gz
ARG WALG_SHA256=444ce216230c254edef803e098a59a1746806da3e0d55671d7b0f0082db14ef4
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
 && curl -fsSL -o /tmp/walg.tar.gz "https://github.com/wal-g/wal-g/releases/download/v${WALG_VERSION}/${WALG_ASSET}" \
 && echo "${WALG_SHA256}  /tmp/walg.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/walg.tar.gz -C /tmp \
 && install -m 0755 "$(find /tmp -maxdepth 1 -type f -name 'wal-g*' ! -name '*.tar.gz' | head -n1)" /usr/local/bin/wal-g \
 && rm -rf /tmp/walg* /var/lib/apt/lists/*
