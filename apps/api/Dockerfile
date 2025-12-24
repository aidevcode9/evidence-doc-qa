FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.5 \
    uvicorn==0.30.6 \
    python-multipart==0.0.9 \
    pypdf==4.3.1 \
    sqlalchemy==2.0.36 \
    alembic==1.14.0 \
    "psycopg[binary]==3.2.3"

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
