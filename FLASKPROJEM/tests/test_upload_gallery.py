import os
from io import BytesIO
from PIL import Image

import pytest

import app as application


def make_image_bytes(format='PNG'):
    img = Image.new('RGB', (100, 100), color=(123, 222, 64))
    buf = BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf


def test_upload_creates_file_and_thumbnail(tmp_path):
    # configure app to use a temporary upload folder
    upload_dir = tmp_path / 'uploads'
    thumb_dir = upload_dir / 'thumbs'
    upload_dir.mkdir()
    thumb_dir.mkdir()

    application.app.config['UPLOAD_FOLDER'] = str(upload_dir)
    application.THUMB_FOLDER = str(thumb_dir)

    client = application.app.test_client()
    data = {
        'file': (make_image_bytes(), 'sample.png')
    }

    rv = client.post('/upload', data=data, content_type='multipart/form-data')
    # upload route redirects to gallery
    assert rv.status_code in (302, 303)

    saved = upload_dir / 'sample.png'
    thumb = thumb_dir / 'sample.png'
    assert saved.exists()
    assert thumb.exists()


def test_gallery_lists_files(tmp_path):
    upload_dir = tmp_path / 'uploads'
    thumb_dir = upload_dir / 'thumbs'
    upload_dir.mkdir()
    thumb_dir.mkdir()

    # create a fake image and thumb
    (upload_dir / 'a.png').write_bytes(make_image_bytes().getvalue())
    (thumb_dir / 'a.png').write_bytes(make_image_bytes().getvalue())

    application.app.config['UPLOAD_FOLDER'] = str(upload_dir)
    application.THUMB_FOLDER = str(thumb_dir)

    client = application.app.test_client()
    rv = client.get('/gallery')
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    assert 'a.png' in body
