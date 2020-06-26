import json
import os
import subprocess
from datetime import datetime
from os.path import isfile

from PIL.ExifTags import TAGS
from flask import send_file, jsonify, Response, abort
from flask import Flask
from flask import request
from pathlib import Path
from os import listdir
from PIL import Image, ImageOps, ExifTags, UnidentifiedImageError

app = Flask(__name__)

image_types = ['.jpg', '.JPG']
video_types = ['.mp4', ".MP4"]
preview_size = 256
video_cache_version = 1
fav_folder_name = ".favorites"


@app.route('/')
def index():
    return Response(open(Path("static") / "index.html"), mimetype="text/html")


@app.route('/image')
def get_image():
    path = Path(request.args.get('path'))
    if path.exists():
        is_video = path.suffixes[0] in video_types
        is_image = path.suffixes[0] in image_types
        if request.args.get('preview') == "true" and (is_image or is_video):
            return send_file(get_preview(path), mimetype=('image/' + str(path.suffixes[0])[1:]))
        elif is_image:
            return send_file(path, mimetype=('image/' + str(path.suffixes[0])[1:]))
        else:
            return send_file("static/img/file-solid.svg", mimetype='image/svg+xml')
    abort(404)


@app.route('/fav')
def set_fav():
    path = Path(request.args.get('file'))
    value = request.args.get('value') == "true"
    print(request.args.get('value'), value, path)
    if path.exists():
        fav_folder = path.parent / fav_folder_name
        if not fav_folder.exists():
            fav_folder.mkdir()
        fav = fav_folder / path.name
        if value and not fav.exists():
            os.symlink(Path("..") / path.name, fav)
            print("create fav", fav)
        elif not value and fav.exists():
            os.remove(fav)
            print("removed fav", fav)
        else:
            print("fav not changed, fav " + ("doesnt " if not fav.exists() else "") + "exists!")

    return "200"


@app.route('/files')
def get_files():
    path = Path(request.args.get('path'))
    video_meta_cache_path = path / ".meta_cache.json"
    save_video_cache = False
    video_meta_cache = {'version': video_cache_version}
    if video_meta_cache_path.exists():
        print("Using meta cache.")
        with open(video_meta_cache_path) as json_file:
            video_meta_cache = json.load(json_file)
    files = []
    folders = []
    if path.exists():
        for f in listdir(path):
            file = Path(path) / f
            if file.name.startswith("."):
                continue
            elif file.is_file():
                is_image = file.suffixes[0] in image_types
                is_video = file.suffixes[0] in video_types

                is_fav = (file.parent / fav_folder_name / file.name).exists()

                meta = {}
                if is_image:
                    try:
                        with Image.open(file) as image:
                            metadata = image.getexif()
                            for tag_id in metadata:
                                # get the tag name, instead of human unreadable tag id
                                tag = TAGS.get(tag_id, tag_id)
                                data = metadata.get(tag_id)

                                if tag_id == 59932:
                                    continue
                                # decode bytes
                                try:
                                    if isinstance(data, bytes):
                                        data = data.decode()
                                    elif isinstance(data, dict):
                                        for key, value in data.items():
                                            if isinstance(value, bytes):
                                                data[key] = value.decode()
                                except UnicodeDecodeError:
                                    data = str(data)
                                meta[str(tag)] = data

                    except UnidentifiedImageError as e:
                        print(e)
                elif is_video:
                    if file.name in video_meta_cache:
                        meta = video_meta_cache[file.name]
                    else:
                        try:
                            result = subprocess.check_output(
                                ["ffprobe", file.name, "-print_format", "json", "-v", "quiet", "-show_format"],
                                cwd=file.parent)
                            meta = json.loads(result.decode())["format"]
                            video_meta_cache[file.name] = meta
                            save_video_cache = True
                        except subprocess.CalledProcessError:
                            pass

                files.append({
                    'name': f,
                    'path': str(file),
                    'is_image': is_image,
                    'is_video': is_video,
                    'is_fav': is_fav,
                    'meta': meta,
                })
            else:
                folders.append({
                    'name': f,
                    'path': str(file),
                })

        files.sort(key=get_date_of_file)

        if save_video_cache:
            with open(video_meta_cache_path, 'w') as outfile:
                json.dump(video_meta_cache, outfile)

        return jsonify({'folders': folders, 'files': files})
    else:
        abort(404)


def get_date_of_file(file):
    if file['is_image'] and file['meta'] is not None and 'DateTime' in file['meta']:
        date = datetime.strptime(file['meta']['DateTime'], "%Y:%m:%d %H:%M:%S")
    elif file['is_video'] and file['meta'] is not None and \
            'tags' in file['meta'] and 'creation_time' in file['meta']['tags']:
        date = datetime.strptime(file['meta']['tags']['creation_time'], "%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        date = datetime.fromtimestamp(0)

    file['date'] = date
    return date


def get_preview(image):
    path = image.parent
    file = image.name

    is_image = image.suffixes[0] in image_types
    is_video = image.suffixes[0] in video_types

    preview = path / ".preview" / file
    if is_video:
        preview = preview.parent / (preview.name + ".jpg")

    if not preview.exists():
        if is_image:
            create_image_preview(image, preview)
        elif is_video:
            create_video_preview(image, preview)
        else:
            abort(500)
    return preview


def create_image_preview(image, preview):
    im = ImageOps.fit(Image.open(image), (preview_size, preview_size), Image.ANTIALIAS)
    im.save(preview)


def create_video_preview(image, preview):
    command = ["ffmpeg", "-i", str(image), "-ss", "00:00:01.000", "-vframes", "1", "-v", "quiet", str(preview)]
    subprocess.check_output(command)
    if preview.exists():
        create_image_preview(preview, preview)
    else:
        abort(500)

