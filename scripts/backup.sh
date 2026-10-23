#!/usr/bin/env bash
# Backup do DBeeAS: banco de dados (PostgreSQL) e arquivos (fotos e fichas).
#
# Uso, na pasta do projeto no servidor:
#     ./scripts/backup.sh
#
# Cria backups/AAAA-MM-DD_HHMM/ com:
#     banco.dump        cópia do banco (formato do pg_dump, para o pg_restore)
#     arquivos.tar.gz   fotos, miniaturas e imagens das fichas
# e apaga os backups com mais de BACKUP_DIAS dias (padrão: 14).
#
# Para rodar todo dia às 3h30 (crontab -e):
#     30 3 * * * cd /home/ramilton/dbeeas && ./scripts/backup.sh >> backups/backup.log 2>&1
#
# Importante: guarde também uma cópia FORA do servidor (veja o README).
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE="docker compose -f ${COMPOSE_FILE:-docker-compose.prod.yml}"
DIAS="${BACKUP_DIAS:-14}"
DESTINO="$(pwd)/backups/$(date +%Y-%m-%d_%H%M)"

mkdir -p "$DESTINO"
echo "[$(date '+%F %T')] Backup em $DESTINO"

# 1. Banco de dados (o banco continua funcionando durante a cópia)
$COMPOSE exec -T db pg_dump -U dbeeas -d dbeeas --format=custom > "$DESTINO/banco.dump"
echo "  banco: $(du -h "$DESTINO/banco.dump" | cut -f1)"

# 2. Arquivos. Os ZIPs exportados e a pasta temporária ficam de fora: dá para gerar de novo.
$COMPOSE run --rm --no-deps -T -v "$DESTINO:/backup" --entrypoint tar backend \
    czf /backup/arquivos.tar.gz -C /data \
    --exclude=arquivos/tmp --exclude=arquivos/exportacoes arquivos
echo "  arquivos: $(du -h "$DESTINO/arquivos.tar.gz" | cut -f1)"

# 3. Confere se os arquivos do backup abrem
gzip -t "$DESTINO/arquivos.tar.gz"
test -s "$DESTINO/banco.dump"

# 4. Apaga backups antigos
find "$(pwd)/backups" -mindepth 1 -maxdepth 1 -type d -mtime "+$DIAS" -exec rm -rf {} +
echo "[$(date '+%F %T')] Backup concluído."
