FROM python:3

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    exiftool \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*


COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt waitress

COPY photos photos

ENV FLASK_APP=photos/app.py
ENV FLASK_ENV=production
ENV PHOTO_FOLDER=/usr/share/photos

RUN mkdir -p $PHOTO_FOLDER/see\ readme

EXPOSE 5000
CMD [ "python", "photos/waitress_server.py" ]