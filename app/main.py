"""A simple web application to create feeds similar to that of the
   live-text feeds on BBC or theguardian. The idea is that anyone can
   begin a live-text feed and additionally readers can combine live-text
   feeds.
"""

from enum import IntEnum
import random
from collections import namedtuple

import unittest

import flask
from flask import request, url_for
import sqlalchemy
import sqlalchemy.orm
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
import flask_wtf
from wtforms import HiddenField, IntegerField, StringField
from wtforms.validators import DataRequired, Email

import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Configuration(object):
    SECRET_KEY = b'7a\xe1f\x17\xc9C\xcb*\x85\xc1\x95G\x97\x03\xa3D\xd3F\xcf\x03\xf3\x99>'  # noqa
    LIVE_SERVER_PORT = 5000
    database_file = os.path.join(basedir, '../../db.sqlite')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + database_file
application = flask.Flask(__name__)
application.config.from_object(Configuration)

database = SQLAlchemy(application)


@application.template_test('plural')
def is_plural(container):
    return len(container) > 1


def redirect_url(default='frontpage'):
    """ A simple helper function to redirect the user back to where they came.

        See: http://flask.pocoo.org/docs/0.10/reqcontext/ and also here:
        http://stackoverflow.com/questions/14277067/redirect-back-in-flask
    """

    return request.args.get('next') or request.referrer or url_for(default)


@application.route("/")
def frontpage():
    return flask.render_template('frontpage.html')

# Create a bbb-feed
@application.route('/startfeed')
def start_feed():
    # TODO: The only thing about this is, that I don't really want
    # people accidentally refreshing and starting multiple feeds, so I
    # guess I want this to only accept POST?
    db_feed = create_database_feed()
    url = flask.url_for('writefeed', feed_no=db_feed.id,
                        author_secret=db_feed.author_secret)
    return flask.redirect(url)

@application.route('/writefeed/<int:feed_no>/<int:author_secret>')
def write_feed(feed_no, author_secret):
    db_feed = database.session.query(DBFeed).filter_by(id=feed_no).one()
    

# Show a list of current/recent bbb-events

# Allow viewing a single bbb-event (although we will want to be able
# to combine bbb-events so that a user can monitor several).


if __name__ == "__main__":
    application.run(debug=True)
