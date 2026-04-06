FROM python:3.13-slim

RUN apt-get update

# Create a non-root user so that it runs with least priveleges
RUN groupadd app && useradd -m -g app app

WORKDIR /app
COPY pyproject.toml ./
COPY README.md ./
COPY --chown=app:app backend ./backend
RUN pip install --no-cache-dir .
RUN chmod +x backend/entrypoint.sh

USER app

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
ENV PYTHONPATH=/app
WORKDIR /app/backend
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]