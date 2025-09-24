FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY equipment.json ./equipment.json
COPY wsgi.py ./wsgi.py

ENV SECRET_KEY=please-change-me
EXPOSE 8000

CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:8000", "wsgi:app", "--access-logfile", "-", "--error-logfile", "-"]
