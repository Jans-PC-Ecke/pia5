#!/bin/bash
# ki/export_memory.sh – Backup der memory_jan.json

BACKUP_DIR="../backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp ../memory_jan.json "$BACKUP_DIR/memory_jan_$TIMESTAMP.json"
echo "✅ Backup gespeichert: $BACKUP_DIR/memory_jan_$TIMESTAMP.json"