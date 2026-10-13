#!/bin/sh
set -e

echo "==> Starting 2ndHand Staging Hub Container..."

# Apply database migrations
echo "==> Applying database migrations..."
python manage.py migrate --noinput

# Collect static assets
echo "==> Collecting static assets..."
python manage.py collectstatic --noinput

# Execute the container's main process (passed as arguments)
echo "==> Launching application server: $@"
exec "$@"
