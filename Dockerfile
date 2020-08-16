FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt waitress

COPY photos photos

ENV FLASK_APP=photos/app.py
ENV FLASK_ENV=development
ENV PHOTO_FOLDER=/usr/share/photos

RUN mkdir -p $PHOTO_FOLDER/see\ readme

CMD [ "python", "photos/waitress_server.py" ]