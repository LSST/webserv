#!/usr/bin/env python

# LSST Data Management System
# Copyright 2015 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.

"""
This is RESTful LSST Data Access Web Server. It handles /meta, /image, and /db

"""

from flask import Flask, request
import json
import logging as log
import os
import sys

from sqlalchemy import create_engine

from lsst.dax.imgserv import api_v1 as is_api_v1
from lsst.dax.imgserv import api_soda as is_api_soda
from lsst.dax.metaserv import api_v1 as ms_api_v1

from configparser import RawConfigParser

ACCEPT_TYPES = ["application/json", "text/html"]

log.basicConfig(
    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S',
    level=log.DEBUG)

defaults_file = os.environ.get("WEBSERV_CONFIG", "~/.lsst/webserv.ini")
WERKZEUG_PREFIX = "dax.webserv.werkzeug."

# instance folder not under version control
i_path=os.path.join(os.path.expanduser("~"), ".lsst/instance")
app = Flask(__name__, instance_path=i_path)

# Initialize configuration
webserv_parser = RawConfigParser()
webserv_parser.optionxform = str

with open(os.path.expanduser(defaults_file)) as cfg:
    webserv_parser.readfp(cfg, defaults_file)

webserv_config = dict(webserv_parser.items("webserv"))
default_imgserv_meta_url = webserv_config.get("dax.imgserv.meta.url")
default_db_url = webserv_config.get("dax.webserv.db.url")

# Initialize configuration for ImageServ
imgserv_config_path = os.path.join(app.instance_path, "imgserv")
with app.app_context():
    # imgserv_config_path only prep for use of instance folder later
    is_api_soda.load_imgserv_config(None, default_imgserv_meta_url)

# Execute this last, we can overwrite anything we don't like
app.config["default_engine"] = create_engine(default_db_url,
                                             pool_size=10,
                                             pool_recycle=3600)
app.config.update(webserv_config)

# Extract werkzeug options, if necessary
# It's okay that we put them into app.config above
werkzeug_options = {}

for key, value in webserv_config.items():
    if key.startswith(WERKZEUG_PREFIX):
        werkzeug_options[key[len(WERKZEUG_PREFIX):]] = value


@app.route('/api')
@app.route('/')
def route_webserv_root():
    fmt = request.accept_mimetypes.best_match(ACCEPT_TYPES)
    if fmt == 'text/html':
        return ("<b>Hello, LSST Image Service here.</b> <br>"
                "I support: "
                "<a href='api/image'>image</a>")
    return "{'LSST Image Service. Links': ['/api/image']}"


@app.route('/api/image')
def route_imgserv():
    """Lists supported versions for /image."""
    fmt = request.accept_mimetypes.best_match(ACCEPT_TYPES)
    if fmt == 'text/html':
        return "<a href='image/soda'>SODA</a>"
    return json.dumps("{'DAX Image. Links': '/api/image/soda'}")


app.register_blueprint(is_api_soda.app, url_prefix='/api/image/soda')
app.register_blueprint(is_api_v1.image_api_v1, url_prefix='/api/image/v1')
app.register_blueprint(ms_api_v1.meta_api_v1, url_prefix='/api/meta/v1')

if __name__ == '__main__':
    try:
        app.run(
                host=app.config.get("dax.webserv.host", "0.0.0.0"),
                port=int(app.config.get("dax.webserv.port", "5000")),
                debug=app.config.get("dax.webserv.debug", True),
                **werkzeug_options
                )
    except Exception as e:
        print("Problem starting the Image Server.", str(e))
        sys.exit(1)
