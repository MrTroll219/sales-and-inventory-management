#!/bin/sh
set -eu
# Existing databases need TU01's read-only preflight; a fresh DB has no table yet.
python manage.py shell -c "from django.db import connection; from django.core.management import call_command; call_command('check_profile_data') if 'accounts_profile' in connection.introspection.table_names() else None"
python manage.py migrate --noinput
# Static files are built into the image, never collected at container startup.
exec "$@"
