#!/bin/sh
# Entrypoint: runs as root, fixes ownership of the (possibly volume-mounted)
# data + logs dirs, then drops privileges to the `app` user to run the command.
#
# Why: Railway volumes mount at runtime owned by root, *over* the build-time
# directory. A build-time chown can't reach the mounted volume, so we chown
# here on every boot before the app (non-root) tries to write into it.
set -e

# Ensure the writable dirs exist and are owned by app (covers volume mounts).
mkdir -p /app/data/usage /app/data/posts_db /app/logs 2>/dev/null || true
chown -R app:app /app/data /app/logs 2>/dev/null || true

# Drop to the app user and exec the real command.
exec su app -s /bin/sh -c "$*"
