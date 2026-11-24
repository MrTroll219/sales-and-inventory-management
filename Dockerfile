FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app
COPY --chown=app:app . .
# Build-only key: never persisted as an image ENV or used at runtime.
RUN SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
    DEBUG=false DJANGO_SECURE_SSL=false DB_ENGINE=sqlite \
    python manage.py collectstatic --noinput \
    && mkdir -p /app/media \
    && chown app:app /app/media \
    && chmod +x /app/entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "scripts/container_healthcheck.py"]
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "InventoryMS.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
