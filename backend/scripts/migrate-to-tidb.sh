#!/bin/bash
# Copy the local MySQL database (backend/.env) into TiDB Cloud (backend/.env.tidb).
#
#   ./backend/scripts/migrate-to-tidb.sh
#
# backend/.env.tidb holds only the target connection (git-ignored):
#   DB_HOST=gateway01.<region>.prod.aws.tidbcloud.com
#   DB_PORT=4000
#   DB_USER=xxxxxxxx.root
#   DB_PASSWORD=...
#   DB_NAME=investiq
#
# Tables that already exist in TiDB are dropped and re-created from the local copy.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MYSQL_BIN="${MYSQL_BIN:-/usr/local/mysql/bin}"
CA_FILE="${CA_FILE:-/etc/ssl/cert.pem}"

read_env() { grep -E "^$2=" "$1" | tail -1 | cut -d= -f2-; }

SRC="$BACKEND_DIR/.env"
DST="$BACKEND_DIR/.env.tidb"
[ -f "$DST" ] || { echo "Missing $DST (see the header of this script)"; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Credentials go through option files, not the command line (visible in `ps`)
cat > "$WORK/src.cnf" <<EOF
[client]
host=$(read_env "$SRC" DB_HOST)
port=$(read_env "$SRC" DB_PORT || true)
user=$(read_env "$SRC" DB_USER)
password=$(read_env "$SRC" DB_PASSWORD)
EOF
sed -i '' '/^port=$/d' "$WORK/src.cnf"

cat > "$WORK/dst.cnf" <<EOF
[client]
host=$(read_env "$DST" DB_HOST)
port=$(read_env "$DST" DB_PORT)
user=$(read_env "$DST" DB_USER)
password=$(read_env "$DST" DB_PASSWORD)
ssl-mode=VERIFY_IDENTITY
ssl-ca=$CA_FILE
EOF
chmod 600 "$WORK"/*.cnf

SRC_DB="$(read_env "$SRC" DB_NAME)"
DST_DB="$(read_env "$DST" DB_NAME)"

echo "Dumping local database '$SRC_DB'..."
"$MYSQL_BIN/mysqldump" --defaults-extra-file="$WORK/src.cnf" \
  --single-transaction --no-tablespaces --set-gtid-purged=OFF \
  --skip-triggers \
  --default-character-set=utf8mb4 "$SRC_DB" > "$WORK/dump.sql"
echo "Dump size: $(du -h "$WORK/dump.sql" | cut -f1)"

echo "Loading into TiDB database '$DST_DB'..."
"$MYSQL_BIN/mysql" --defaults-extra-file="$WORK/dst.cnf" \
  -e "CREATE DATABASE IF NOT EXISTS \`$DST_DB\`"
"$MYSQL_BIN/mysql" --defaults-extra-file="$WORK/dst.cnf" \
  --default-character-set=utf8mb4 "$DST_DB" < "$WORK/dump.sql"

echo "Row counts (local -> TiDB):"
for t in $("$MYSQL_BIN/mysql" --defaults-extra-file="$WORK/src.cnf" -N -e "SHOW TABLES" "$SRC_DB"); do
  a=$("$MYSQL_BIN/mysql" --defaults-extra-file="$WORK/src.cnf" -N -e "SELECT COUNT(*) FROM \`$t\`" "$SRC_DB")
  b=$("$MYSQL_BIN/mysql" --defaults-extra-file="$WORK/dst.cnf" -N -e "SELECT COUNT(*) FROM \`$t\`" "$DST_DB")
  printf "  %-24s %8s -> %8s %s\n" "$t" "$a" "$b" "$([ "$a" = "$b" ] && echo ok || echo MISMATCH)"
done
