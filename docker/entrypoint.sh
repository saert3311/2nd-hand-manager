#!/bin/sh
set -e

echo "==> Starting 2ndHand Staging Hub Container..."

# Ensure all Gunicorn workers share one strong SECRET_KEY when DEBUG=False
DEBUG_LOWER=$(printf '%s' "${DEBUG:-True}" | tr '[:upper:]' '[:lower:]')
if [ "$DEBUG_LOWER" = "false" ] || [ "$DEBUG_LOWER" = "0" ] || [ "$DEBUG_LOWER" = "no" ]; then
    case "${SECRET_KEY:-}" in
        ""|django-insecure-*)
            RUNTIME_KEY_FILE="/app/data/.runtime_secret_key"
            if [ -s "$RUNTIME_KEY_FILE" ]; then
                SECRET_KEY=$(cat "$RUNTIME_KEY_FILE")
            else
                SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
                if [ -d "/app/data" ] && [ -w "/app/data" ]; then
                    printf '%s' "$SECRET_KEY" > "$RUNTIME_KEY_FILE"
                    chmod 600 "$RUNTIME_KEY_FILE" || true
                fi
            fi
            export SECRET_KEY
            ;;
    esac
fi

# Apply database migrations
echo "==> Applying database migrations..."
python manage.py migrate --noinput

# Collect static assets
echo "==> Collecting static assets..."
python manage.py collectstatic --noinput

# Verify system roles and groups exist
echo "==> Verifying system roles and groups..."
python manage.py setup_roles --no-demo-users

# Execute the container's main process (passed as arguments)
echo "==> Launching application server: $@"
exec "$@"
