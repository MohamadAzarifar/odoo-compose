#!/bin/bash
# scripts/backup.sh

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="odoo_backup_${TIMESTAMP}"

mkdir -p $BACKUP_DIR

echo "🔄 Starting backup..."

# Backup database
echo "📦 Backing up database..."
docker exec odoo_db pg_dump -U odoo postgres > ${BACKUP_DIR}/${BACKUP_NAME}_db.sql

# Backup Odoo data
echo "📁 Backing up Odoo data..."
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}_data.tar.gz -C ./odoo_data .

# Backup addons
echo "📦 Backing up custom addons..."
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}_addons.tar.gz -C ./addons .

echo "✅ Backup completed: ${BACKUP_NAME}"
echo "📁 Location: ${BACKUP_DIR}/"
ls -lh ${BACKUP_DIR}/${BACKUP_NAME}_*

# Keep only last 7 backups
echo "🧹 Cleaning old backups (keeping last 7)..."
ls -t ${BACKUP_DIR}/odoo_backup_*_db.sql | tail -n +8 | xargs -r rm