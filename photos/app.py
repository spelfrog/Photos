import json
import os
import subprocess
from datetime import datetime, timedelta
from functools import wraps
from secrets import token_hex, token_urlsafe

import flask
from PIL.ExifTags import TAGS
from PIL.TiffImagePlugin import IFDRational
from flask import send_file, jsonify, Response, abort, send_from_directory, render_template, session, redirect, url_for
from flask import Flask
from flask import request
from pathlib import Path
from os import listdir
from PIL import Image, ImageOps, ExifTags, UnidentifiedImageError, ImageFile
from werkzeug.exceptions import HTTPException

image_types = ['.jpg', '.JPG']
video_types = ['.mp4', ".MP4"]
preview_size = 256
video_cache_version = 2
fav_folder_name = ".favorites"
root_folder = Path(os.environ.get("PHOTO_FOLDER", "test_images"))
disable_login = os.environ.get("disable_login", False)

_crypt_data = None

app = Flask(__name__, template_folder='template')
app.secret_key = os.environ.get("secret_key", token_hex(32))

token = os.environ.get("token", token_urlsafe(10))
os.environ[token] = token

failed_ips = {}

print("Login token:", token)


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.content_type = "application/json"
    return response


def login_required(test):
    @wraps(test)
    def wrap(*args, **kwargs):
        if disable_login or 'logged_in' in session and session['logged_in'] == True:
            return test(*args, **kwargs)
        else:
            abort(401)
    return wrap


def get_ip():
    return request.environ.get('HTTP_X_REAL_IP', request.remote_addr)


def is_ip_banned(ip):
    if ip in failed_ips:
        some_time_ago = datetime.now() - timedelta(minutes=5)

        print(failed_ips)
        failed_ips[ip] = [fail_time for fail_time in failed_ips[ip] if fail_time > some_time_ago]
        print(failed_ips)

        return len(failed_ips[ip]) >= 3
    else:
        return False


@app.route('/')
def home(login_failed=False):
    redirect_url = url_for('home')
    if request.args.get('path', None):
        redirect_url += "?path=" + request.args.get('path')

    if is_ip_banned(get_ip()):
        return abort(429)
    elif not session.get('logged_in') and not disable_login:
        return render_template('login.html', login_failed=login_failed, login_redirect_url=redirect_url)
    else:
        return render_template("index.html")


@app.route('/login', methods=['POST'])
def login():
    ip = get_ip()
    if is_ip_banned(ip):
        return abort(429)

    form_token = str(request.form['token'])

    if form_token == token:
        session['logged_in'] = True
    else:
        if ip not in failed_ips:
            failed_ips[ip] = []
        failed_ips[ip].append(datetime.now())
        print("adding %s to failed ips" % str(ip))

    return redirect(request.form.get('login_redirect_url', url_for('home')))


@app.route('/image')
@login_required
def get_image():
    path = (root_folder / Path(request.args.get('path'))).resolve()
    if path.exists():
        is_video = path.suffixes[0] in video_types
        is_image = path.suffixes[0] in image_types
        if request.args.get('preview') == "true" and (is_image or is_video):
            return send_file(get_preview(path), mimetype=('image/' + str(path.suffixes[0])[1:]))
        elif is_image:
            return send_file(path, mimetype=('image/' + str(path.suffixes[0])[1:]))
        elif is_video:
            return send_file(path, mimetype=('video/' + str(path.suffixes[0])[1:]))
        # last option
        return send_file("static/img/file-solid.svg", mimetype='image/svg+xml')
    else:
        abort(404)


@app.route('/fav')
@login_required
def set_fav():
    path = root_folder / Path(request.args.get('file'))
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

    return jsonify(path=path, active=value), 200


def parse_tag_data(data):
    try:
        if isinstance(data, IFDRational):
            data = float(data)
        elif isinstance(data, bytes):
            data = data.decode()
        elif isinstance(data, dict):
            for key, value in data.items():
                data[key] = parse_tag_data(value)
        elif isinstance(data, tuple):
            data_as_list = list()
            for value in data:
                data_as_list.append(parse_tag_data(value))
            data = data_as_list

    except UnicodeDecodeError:
        return str(data)
    except ZeroDivisionError:
        return "NaN"
    else:
        try:
            json.dumps(data)
        except TypeError:
            print()
        return data


def get_video_meta(file: Path):
    try:
        result = subprocess.check_output(
            ["exiftool", "-q", "-j", file.name],
            cwd=file.parent)
        meta = json.loads(result.decode())[0]
    except subprocess.CalledProcessError:
        return None
    else:
        return meta


def get_image_meta(file: Path):
    meta = {}
    try:
        with Image.open(file) as image:
            metadata = image.getexif()
            for tag_id in metadata:
                # get the tag name, instead of human unreadable tag id
                tag = TAGS.get(tag_id, tag_id)
                data = metadata.get(tag_id)

                if tag_id == 59932:
                    continue

                meta[str(tag)] = parse_tag_data(data)
    except UnidentifiedImageError as e:
        print(e)
        return None
    else:
        return meta


@app.route('/files')
@login_required
def get_files():
    path = root_folder / Path(request.args.get('path'))
    meta_cache_path = path / ".meta_cache.json"
    save_cache = False
    meta_cache = {'version': video_cache_version}
    if meta_cache_path.exists():
        print("Using meta cache.")
        with open(meta_cache_path) as json_file:
            meta_cache = json.load(json_file)
            # deleting cache if outdated
            if meta_cache['version'] != video_cache_version:
                meta_cache = {'version': video_cache_version}
    files = []
    unknown_files = []
    folders = []
    if path.exists():
        files_in_folder = listdir(path)
        for f in files_in_folder:
            file = Path(path) / f
            if file.name.startswith("."):
                continue
            elif file.is_file():
                last_suffixes_index = len(file.suffixes) - 1
                is_image = file.suffixes[last_suffixes_index] in image_types
                is_video = file.suffixes[last_suffixes_index] in video_types

                is_fav = (file.parent / fav_folder_name / file.name).exists()

                meta = {}
                if is_image or is_video:
                    # if meta data in cache
                    if file.name in meta_cache:
                        meta = meta_cache[file.name]
                    else:
                        if is_video:
                            meta = get_video_meta(file)
                        else:  # is_image
                            meta = get_image_meta(file)

                        # save new meta data if any is found
                        if meta is not None and len(meta) != 0:
                            meta_cache[file.name] = meta
                            save_cache = True
                        else:
                            unknown_files.append({'name': f, 'path': str(file.relative_to(root_folder))})
                            continue

                else:
                    # files without video or image extension
                    unknown_files.append({'name': f, 'path': str(file.relative_to(root_folder))})
                    continue

                files.append({
                    'name': f,
                    'path': str(file.relative_to(root_folder)),
                    'is_image': is_image,
                    'is_video': is_video,
                    'is_fav': is_fav,
                    'meta': meta,
                })
            else:
                folders.append({
                    'name': f,
                    'path': str(file.relative_to(root_folder)),
                })

        # order by capture date
        files.sort(key=get_date_of_file)

        if save_cache:
            with open(meta_cache_path, 'w') as outfile:
                json.dump(meta_cache, outfile)

        # dumps is a order of magnitude faster then jsonify (in Debug mode)
        json_encoded_files = flask.json.dumps({'folders': folders, 'files': files, 'unknown_files': unknown_files})
        return Response(json_encoded_files, mimetype="application/json")
    else:
        abort(404)


def get_date_of_file(file):
    if file['is_image'] and file['meta'] is not None and 'DateTime' in file['meta']:
        date = datetime.strptime(file['meta']['DateTime'], "%Y:%m:%d %H:%M:%S")
    elif file['is_video'] and file['meta'] is not None and \
            'MediaCreateDate' in file['meta']:
        date = datetime.strptime(file['meta']['MediaCreateDate'], "%Y:%m:%d %H:%M:%S")
    else:
        date = datetime.fromtimestamp(0)

    file['date'] = date
    return date


def get_preview(image) -> Path:
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
    return preview.resolve()


def create_image_preview(image, preview):
    with Image.open(image) as image_stream:
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        im = ImageOps.fit(image_stream, (preview_size, preview_size), Image.ANTIALIAS)
    if not preview.parent.exists():
        preview.parent.mkdir()
    im.save(preview)


def create_video_preview(image, preview):
    command = ["ffmpeg", "-i", str(image), "-ss", "00:00:01.000", "-vframes", "1", "-v", "quiet", str(preview)]
    subprocess.check_output(command)
    if preview.exists():
        create_image_preview(preview, preview)
    else:
        abort(500)
