#!/bin/bash
set -e

echo "🔧 Setting up local PostgreSQL database for development..."

# Default values (can be overridden by environment variables)
DB_STANDBY_NAME=${DB_STANDBY_NAME:-app_standby}
DB_STANDBY_USER=${DB_STANDBY_USER:-app_user}
DB_STANDBY_PASSWORD=${DB_STANDBY_PASSWORD:-app_password}

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed. Please install it first:"
    echo "   brew install postgresql@14"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready -q; then
    echo "⚠️  PostgreSQL is not running. Starting it..."
    if command -v brew &> /dev/null; then
        brew services start postgresql@14 || brew services start postgresql
    else
        echo "❌ Please start PostgreSQL manually"
        exit 1
    fi
    echo "⏳ Waiting for PostgreSQL to be ready..."
    sleep 3
fi

# Get current user for admin operations
ADMIN_USER=$(whoami)

echo "📝 Creating database and user..."

# Create database if it doesn't exist
if psql -U "$ADMIN_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$DB_STANDBY_NAME'" | grep -q 1; then
    echo "✓ Database '$DB_STANDBY_NAME' already exists"
else
    psql -U "$ADMIN_USER" -d postgres -c "CREATE DATABASE $DB_STANDBY_NAME;"
    echo "✓ Created database '$DB_STANDBY_NAME'"
fi

# Create user if it doesn't exist
if psql -U "$ADMIN_USER" -d postgres -tc "SELECT 1 FROM pg_user WHERE usename='$DB_STANDBY_USER'" | grep -q 1; then
    echo "✓ User '$DB_STANDBY_USER' already exists"
    # Update password in case it changed
    psql -U "$ADMIN_USER" -d postgres -c "ALTER USER $DB_STANDBY_USER WITH PASSWORD '$DB_STANDBY_PASSWORD';" || true
else
    psql -U "$ADMIN_USER" -d postgres -c "CREATE USER $DB_STANDBY_USER WITH PASSWORD '$DB_STANDBY_PASSWORD';"
    echo "✓ Created user '$DB_STANDBY_USER'"
fi

# Grant privileges
psql -U "$ADMIN_USER" -d postgres -c "ALTER DATABASE $DB_STANDBY_NAME OWNER TO $DB_STANDBY_USER;" || true
psql -U "$ADMIN_USER" -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_STANDBY_NAME TO $DB_STANDBY_USER;" || true

echo ""
echo "✅ Local PostgreSQL setup complete!"
echo ""
echo "Connection details:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: $DB_STANDBY_NAME"
echo "  User: $DB_STANDBY_USER"
echo "  Password: $DB_STANDBY_PASSWORD"
echo ""
echo "You can now run your API with local PostgreSQL as fallback when RDS is unavailable."
