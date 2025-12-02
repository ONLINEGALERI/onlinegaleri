import os
import sys
import pytest

# Ensure the project root is on sys.path so tests can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as application


def test_home_route_exists():
    client = application.app.test_client()
    rv = client.get('/')
    assert rv.status_code == 200
