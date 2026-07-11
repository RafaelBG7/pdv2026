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
MYSQL_CENTRAL_DATABASE="${MYSQL_DATABASE:-adega_central}"
AUDIT_CLEANUP_INTERVAL_SECONDS="${AUTO_AUDIT_CLEANUP_INTERVAL_SECONDS:-259200}"
AUDIT_RETENTION_DAYS="${AUTO_AUDIT_RETENTION_DAYS:-90}"

is_enabled() {
  case "${AUTO_BACKUP_ENABLED:-1}" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

audit_cleanup_enabled() {
  case "${AUTO_AUDIT_CLEANUP_ENABLED:-1}" in
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

mysql_exec() {
  mysql \
    --host="$MYSQL_HOST_VALUE" \
    --port="$MYSQL_PORT_VALUE" \
    --user="$MYSQL_USER_VALUE" \
    --protocol=TCP \
    --batch \
    --skip-column-names \
    --execute "$1"
}

safe_database_name() {
  case "$1" in
    ''|*[!A-Za-z0-9_]*)
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

database_has_audit_table() {
  database_name="$1"
  table_count=$(
    mysql_exec "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$database_name' AND table_name = 'audit_logs';"
  )
  [ "${table_count:-0}" -gt 0 ]
}

cleanup_audit_database() {
  database_name="$1"
  safe_database_name "$database_name" || {
    echo "Banco ignorado na limpeza de auditoria por nome inválido: $database_name" >&2
    return 0
  }
  database_has_audit_table "$database_name" || return 0

  deleted_rows=$(
    mysql_exec "DELETE FROM \`$database_name\`.\`audit_logs\` WHERE created_at < UTC_TIMESTAMP() - INTERVAL $AUDIT_RETENTION_DAYS DAY; SELECT ROW_COUNT();" |
      tail -n 1
  )
  echo "Auditoria limpa em $database_name: ${deleted_rows:-0} registro(s) antigo(s) removido(s)."
  AUDIT_CLEANUP_DELETED_TOTAL=$((AUDIT_CLEANUP_DELETED_TOTAL + ${deleted_rows:-0}))
}

audit_cleanup_due() {
  status_file="$BACKUP_DIR/audit_cleanup.status"
  [ "${AUTO_AUDIT_CLEANUP_ONCE:-0}" = "1" ] && return 0
  [ ! -f "$status_file" ] && return 0

  last_epoch=$(awk -F'|' 'NR == 1 {print $1}' "$status_file" 2>/dev/null || true)
  case "$last_epoch" in
    ''|*[!0-9]*)
      return 0
      ;;
  esac

  now_epoch=$(date -u '+%s')
  [ $((now_epoch - last_epoch)) -ge "$AUDIT_CLEANUP_INTERVAL_SECONDS" ]
}

run_audit_cleanup() {
  mkdir -p "$BACKUP_DIR"
  wait_for_mysql

  if [ "$AUDIT_RETENTION_DAYS" -lt 1 ]; then
    echo "AUTO_AUDIT_RETENTION_DAYS precisa ser maior que zero; limpeza ignorada." >&2
    return 1
  fi

  echo "Iniciando limpeza de auditoria. Retenção: $AUDIT_RETENTION_DAYS dia(s)."
  AUDIT_CLEANUP_DELETED_TOTAL=0
  cleanup_audit_database "$MYSQL_CENTRAL_DATABASE"

  tenant_databases=$(
    mysql_exec "SELECT database_path FROM \`$MYSQL_CENTRAL_DATABASE\`.\`companies\` WHERE database_path IS NOT NULL AND database_path <> '';" 2>/dev/null || true
  )
  for tenant_database in $tenant_databases; do
    cleanup_audit_database "$tenant_database"
  done

  now_epoch=$(date -u '+%s')
  printf '%s|success|%s|%s\n' "$now_epoch" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$AUDIT_CLEANUP_DELETED_TOTAL" > "$BACKUP_DIR/audit_cleanup.status"
  echo "Limpeza de auditoria concluída: $AUDIT_CLEANUP_DELETED_TOTAL registro(s) removido(s)."
}

run_audit_cleanup_if_due() {
  if ! audit_cleanup_enabled; then
    return 0
  fi
  if audit_cleanup_due; then
    if ! run_audit_cleanup; then
      printf '%s|error|%s\n' "$(date -u '+%s')" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$BACKUP_DIR/audit_cleanup.status"
      return 1
    fi
  fi
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

if [ "${AUTO_AUDIT_CLEANUP_ONCE:-0}" = "1" ]; then
  run_audit_cleanup
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
  run_audit_cleanup_if_due || true
  sleep "$INTERVAL_SECONDS"
done
