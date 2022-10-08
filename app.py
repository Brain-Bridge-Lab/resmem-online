from botocore.exceptions import ClientError
from flask import Flask, render_template, flash, redirect, url_for, request, send_from_directory, jsonify
import os
from werkzeug.utils import secure_filename
import boto3
import random
from flask_restful import Resource, Api
import json
import time
import jinja2
import sys

UPLOAD_FOLDER = 'tmp/'
DATA_FOLDER = 'tmp/data'

if not os.path.exists(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)

if not os.path.exists(DATA_FOLDER):
    os.mkdir(DATA_FOLDER)

ACCESS_KEY = os.environ['ACCESS_KEY']
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_EXTENSIONS = {'jpg', 'png', 'jpeg'}

session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name='us-east-2'
)

s3_client = session.client('s3')
logclient = session.client('logs')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
api = Api(app)


class ResponseListener(Resource):
    def post(self):
        data = request.form['data']
        data = json.loads(data)
        with open(DATA_FOLDER + '/' + data[0].split('.')[0], 'w+') as f:
            f.write(str(data[1]))
        return {'success': True}


api.add_resource(ResponseListener, '/receiver')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket.

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        return False
    return True


@app.route('/', methods=['GET', 'POST'])
def file_upload():
    if request.method == 'POST':
        imgid = random.getrandbits(64)
        imgid = hex(imgid)[1:]
        # check if the post request has the file part
        if 'file' not in request.files:
            print('No File Detected', file=sys.stderr)
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            resp = upload_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'resmem-web',
                               'img/' + imgid + '.' + filename.rsplit('.', 1)[1].lower())
            if resp:
                return redirect(url_for('uploaded_file', filename=imgid, image=filename))

    return render_template('resmem.html')


@app.route('/data/<filename>')
def uploaded_file(filename):
    dat = None
    c = 0
    image = request.args.get('image')
    full_filename = os.path.join(app.config['UPLOAD_FOLDER'], image)
    while True:
        try:
            with open('tmp/data/' + filename, 'r') as f:
                dat = float(f.read())
            if dat:
                break
        except FileNotFoundError:
            time.sleep(0.01)
            c += 1
            if c > 1000:
                return render_template('coldboot.html', filename=filename, image=image)
    return render_template('result.html', score=str(round(dat, 3)), image=full_filename)


@app.route('/tmp/<path:filename>')
def send_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/_file_checker')
def file_checker():
    fname = request.args.get('fname', type=str)
    if os.path.exists('tmp/data/' + fname):
        return jsonify(result=1)
    else:
        return jsonify(result=0)
