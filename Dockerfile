
FROM python:3.8-slim


WORKDIR /app

COPY . /app
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

RUN python -m venv /opt/venv
RUN . /opt/venv/bin/activate && pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["/opt/venv/bin/gunicorn", "app:app", "-b", "0.0.0.0:5000"]

