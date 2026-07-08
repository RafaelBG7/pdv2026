#!/bin/sh
set -eu

umask 077

BACKUP_DIR="${AUTO_BACKUP_DIR:-/backups}"
INTERVAL_SECONDS="${AUTO_BACKUP_INTERVAL_SECONDS:-86400}"
RETENTION_DAYS="${AUTO_BACKUP_RETENTION_DAYS:-30}"
RETENTION_COUNT="${AUTO_BACKUP_RETENTION_COUNT:-30}"
MYSQL_HOST_VALUE="${MYSQL_HOST:-mysql}"
MYSQL_PORT_VALUE="${MYSQL_PORT:-3306}"
MYSQL_USER_VALUE="${MYSQL_BACKUP_USER:-root}"

is_enabled() {
  case "${AUTO_BACKUP_ENABLED:-1}" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

wait_for_mysql() {
  attempts=0
  until mysqladmin ping \
    --host="$MYSQL_HOST_VALUE" \
    --port="$MYSQL_PORT_VALUE" \
    --user="$MYSQL_USER_VALUE" \
    --silent >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "MySQL indisponível após 5 minutos; backup não executado." >&2
      return 1
    fi
    sleep 5
  done
}

apply_retention() {
  find "$BACKUP_DIR" -type f -name 'girofy_mysql_full_*.sql' -mtime "+$RETENTION_DAYS" -delete

  index=0
  for backup_file in $(find "$BACKUP_DIR" -type f -name 'girofy_mysql_full_*.sql' -print | sort -r); do
    index=$((index + 1))
    if [ "$index" -gt "$RETENTION_COUNT" ]; then
      rm -f "$backup_file"
    fi
  done
}

run_backup() {
  mkdir -p "$BACKUP_DIR"
  wait_for_mysql

  timestamp=$(date -u '+%Y%m%d_%H%M%S')
  backup_path="$BACKUP_DIR/girofy_mysql_full_${timestamp}.sql"
  temporary_path="${backup_path}.tmp"

  echo "Iniciando backup completo do MySQL em $timestamp UTC."
  rm -f "$temporary_path"
  mysqldump \
    --host="$MYSQL_HOST_VALUE" \
    --port="$MYSQL_PORT_VALUE" \
    --user="$MYSQL_USER_VALUE" \
    --protocol=TCP \
    --single-transaction \
    --quick \
    --routines \
    --events \
    --triggers \
    --hex-blob \
    --all-databases \
    --add-drop-database \
    --result-file="$temporary_path"

  if [ ! -s "$temporary_path" ]; then
    rm -f "$temporary_path"
    echo "O MySQL gerou um arquivo de backup vazio." >&2
    return 1
  fi

  mv "$temporary_path" "$backup_path"
  chmod 600 "$backup_path"
  apply_retention
  printf '%s|success|%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$backup_path" > "$BACKUP_DIR/automatic_backup.status"
  echo "Backup concluído: $backup_path"
}

if [ "${AUTO_BACKUP_ONCE:-0}" = "1" ]; then
  run_backup
  exit 0
fi

while true; do
  if is_enabled; then
    if ! run_backup; then
      printf '%s|error\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$BACKUP_DIR/automatic_backup.status"
    fi
  else
    echo "Backup automático desativado por AUTO_BACKUP_ENABLED."
  fi
  sleep "$INTERVAL_SECONDS"
done
