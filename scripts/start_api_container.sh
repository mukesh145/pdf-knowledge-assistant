#!/bin/bash
set -e

echo "🚀 Starting API container..."

# Get environment variables with defaults
DB_STANDBY_HOST=${DB_STANDBY_HOST:-localhost}
DB_STANDBY_PORT=${DB_STANDBY_PORT:-5432}
DB_STANDBY_NAME=${DB_STANDBY_NAME:-app_standby}
DB_STANDBY_USER=${DB_STANDBY_USER:-app_user}
DB_STANDBY_PASSWORD=${DB_STANDBY_PASSWORD:-app_password}

# Find PostgreSQL binary path
PG_BIN=$(find /usr/lib/postgresql -name "initdb" -type f 2>/dev/null | head -1 | xargs dirname)
if [ -z "$PG_BIN" ]; then
    PG_BIN="/usr/lib/postgresql/$(ls /usr/lib/postgresql | head -1)/bin"
fi
PG_DATA="/var/lib/postgresql/data"
PG_CONF="$PG_DATA/postgresql.conf"
PG_HBA="$PG_DATA/pg_hba.conf"

# Initialize PostgreSQL data directory if it doesn't exist
if [ ! -d "$PG_DATA" ] || [ -z "$(ls -A $PG_DATA 2>/dev/null)" ]; then
    echo "📦 Initializing PostgreSQL data directory..."
    mkdir -p "$PG_DATA"
    chown -R postgres:postgres "$PG_DATA"
    su - postgres -c "$PG_BIN/initdb -D $PG_DATA"
fi

# Configure PostgreSQL to listen on localhost (only if not already configured)
if ! grep -q "listen_addresses" "$PG_CONF" 2>/dev/null; then
    echo "⚙️  Configuring PostgreSQL..."
    echo "listen_addresses = 'localhost'" >> "$PG_CONF"
    echo "port = $DB_STANDBY_PORT" >> "$PG_CONF"
fi

# Configure pg_hba.conf if it doesn't have our entries
if ! grep -q "$DB_STANDBY_NAME.*$DB_STANDBY_USER" "$PG_HBA" 2>/dev/null; then
    # Backup original and create new pg_hba.conf
    cp "$PG_HBA" "$PG_HBA.bak" 2>/dev/null || true
    cat > "$PG_HBA" <<EOF
# PostgreSQL Client Authentication Configuration File
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
host    $DB_STANDBY_NAME    $DB_STANDBY_USER    127.0.0.1/32            md5
host    $DB_STANDBY_NAME    $DB_STANDBY_USER    ::1/128                 md5
EOF
    chown postgres:postgres "$PG_HBA"
fi

# Check if PostgreSQL is already running
if ! su - postgres -c "$PG_BIN/pg_ctl -D $PG_DATA status" > /dev/null 2>&1; then
    # Start PostgreSQL in the background
    echo "🔄 Starting PostgreSQL server..."
    su - postgres -c "$PG_BIN/pg_ctl -D $PG_DATA -l $PG_DATA/logfile start" || true
else
    echo "✓ PostgreSQL is already running"
fi

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if su - postgres -c "psql -c 'SELECT 1' > /dev/null 2>&1"; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to start"
        exit 1
    fi
    sleep 1
done

# Create database and user if they don't exist
echo "📝 Setting up standby database..."
su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='$DB_STANDBY_NAME'\" | grep -q 1" || \
    su - postgres -c "psql -c 'CREATE DATABASE $DB_STANDBY_NAME'"

su - postgres -c "psql -tc \"SELECT 1 FROM pg_user WHERE usename='$DB_STANDBY_USER'\" | grep -q 1" || \
    su - postgres -c "psql -c \"CREATE USER $DB_STANDBY_USER WITH PASSWORD '$DB_STANDBY_PASSWORD'\""

su - postgres -c "psql -c \"ALTER DATABASE $DB_STANDBY_NAME OWNER TO $DB_STANDBY_USER\""
su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE $DB_STANDBY_NAME TO $DB_STANDBY_USER\""

# Reload PostgreSQL configuration to apply changes
su - postgres -c "$PG_BIN/pg_ctl -D $PG_DATA reload" || true

echo "✅ Standby database setup complete!"

# Start the FastAPI application
echo "🚀 Starting FastAPI application..."
cd /app
exec uvicorn api.app:app --host 0.0.0.0 --port 8000

