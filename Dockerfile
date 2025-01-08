
FROM python:3.8-slim


WORKDIR /app

COPY . /app
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

RUN python -m venv /opt/venv
RUN . /opt/venv/bin/activate && pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000"]


FROM ubuntu:xenial
FROM node
RUN apt-get -y update
RUN apt-get --yes install libav-tools
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY package.json /usr/src/app
RUN npm install
COPY . /usr/src/app
RUN npm run build
ENV NODE_ENV production
EXPOSE 8000
CMD ["npm", "run", "start:prod"]
