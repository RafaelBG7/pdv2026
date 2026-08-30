#!/usr/bin/env bash
set -euo pipefail

tenant_prefix="${MYSQL_TENANT_DATABASE_PREFIX:-adega}"
if [[ ! "$tenant_prefix" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "MYSQL_TENANT_DATABASE_PREFIX inválido." >&2
  exit 1
fi
escaped_tenant_prefix="${tenant_prefix//_/\\_}"

mysql --protocol=socket -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
GRANT ALL PRIVILEGES ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON \`${escaped_tenant_prefix}\\_%\`.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL
