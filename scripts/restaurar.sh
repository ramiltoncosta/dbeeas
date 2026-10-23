#!/usr/bin/env bash
# Restaura um backup feito pelo scripts/backup.sh.
#
# Uso, na pasta do projeto no servidor:
#     ./scripts/restaurar.sh backups/2026-10-23_0330
#
# ATENÇÃO: substitui o banco e as fotos atuais pelos do backup.
set -euo pipefail

cd "$(dirname "$0")/.."
ORIGEM="$(cd "${1:?Informe a pasta do backup, ex.: backups/2026-10-23_0330}" && pwd)"
COMPOSE="docker compose -f ${COMPOSE_FILE:-docker-compose.prod.yml}"

test -s "$ORIGEM/banco.dump" || { echo "Não encontrei $ORIGEM/banco.dump"; exit 1; }
test -s "$ORIGEM/arquivos.tar.gz" || { echo "Não encontrei $ORIGEM/arquivos.tar.gz"; exit 1; }

read -r -p "Isto apaga os dados atuais e restaura $ORIGEM. Digite RESTAURAR para continuar: " ok
[ "$ok" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

echo "Parando o site e o worker..."
$COMPOSE stop backend worker frontend

echo "Restaurando o banco..."
$COMPOSE exec -T db pg_restore -U dbeeas -d dbeeas --clean --if-exists --no-owner < "$ORIGEM/banco.dump"

echo "Restaurando os arquivos..."
$COMPOSE run --rm --no-deps -T -v "$ORIGEM:/backup:ro" --entrypoint sh backend \
    -c 'rm -rf /data/arquivos/* && tar xzf /backup/arquivos.tar.gz -C /data'

echo "Subindo de novo..."
$COMPOSE up -d
echo "Pronto."
