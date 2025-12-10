#!/bin/sh
set -e

# Get the API base URL from environment variable (set by ECS task definition)
API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000}"

echo "========================================="
echo "Frontend Runtime Configuration"
echo "========================================="
echo "API_BASE_URL: $API_BASE_URL"
echo ""

# Verify index.html exists
if [ ! -f /usr/share/nginx/html/index.html ]; then
  echo "ERROR: index.html not found in /usr/share/nginx/html/"
  ls -la /usr/share/nginx/html/ || true
  exit 1
fi

# Create runtime config file that will be injected into index.html
# Escape the URL properly for JSON (handle special characters)
ESCAPED_URL=$(echo "$API_BASE_URL" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.__RUNTIME_CONFIG__ = {
  VITE_API_BASE_URL: "${ESCAPED_URL}"
};
console.log('[Runtime Config] Loaded API_BASE_URL:', window.__RUNTIME_CONFIG__.VITE_API_BASE_URL);
EOF

echo "Created runtime-config.js:"
cat /usr/share/nginx/html/runtime-config.js
echo ""

# Inject the config script into index.html before the main script
# Use awk for reliable text manipulation in Alpine/busybox
if ! grep -q 'runtime-config.js' /usr/share/nginx/html/index.html; then
  # Create a temporary file with the updated content
  awk '
    /<script type="module" src="\/src\/main.jsx"><\/script>/ {
      print "    <script src=\"/runtime-config.js\"></script>"
      print $0
      next
    }
    /<\/body>/ && !found {
      print "    <script src=\"/runtime-config.js\"></script>"
      found = 1
    }
    { print }
  ' /usr/share/nginx/html/index.html > /tmp/index.html.new
  
  # Replace the original file
  mv /tmp/index.html.new /usr/share/nginx/html/index.html
  echo "Updated index.html to include runtime-config.js"
else
  echo "runtime-config.js already present in index.html"
fi

echo ""
echo "Verifying index.html contains runtime-config.js:"
grep -o 'runtime-config.js' /usr/share/nginx/html/index.html && echo "✓ Found runtime-config.js in index.html" || echo "✗ WARNING: runtime-config.js not found in index.html"

echo ""
echo "Configuration complete. Starting nginx..."
echo "========================================="
echo ""

# Start nginx
exec nginx -g "daemon off;"
