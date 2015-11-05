"""A simple web application to create feeds similar to that of the
   live-text feeds on BBC or theguardian. The idea is that anyone can
   begin a live-text feed and additionally readers can combine live-text
   feeds.
"""

from enum import IntEnum
import random
from collections import namedtuple

import unittest

import datetime
import redis
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
redis_protocol = redis.StrictRedis()


class DBFeed(database.Model):
    __tablename__ = 'feeds'
    id = database.Column(database.Integer, primary_key=True)
    author_secret = database.Column(database.Integer)
    moments = database.relationship('DBMoment')

    def __init__(self):
        self.author_secret = random.getrandbits(48)

class DBMoment(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    content = database.Column(database.String(2400))
    feed_id = database.Column(database.Integer,
                              database.ForeignKey('feeds.id'))

    def __init__(self, content):
        self.content = content

def create_database_feed():
    """ Create a feed in the database. """
    dbfeed = DBFeed()
    database.session.add(dbfeed)
    database.session.commit()
    return dbfeed

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
    url = flask.url_for('write_feed', feed_no=db_feed.id,
                        author_secret=db_feed.author_secret)
    return flask.redirect(url)


class CommentateForm(flask_wtf.Form):
    validators = [DataRequired()]
    comment_text = StringField("Next comment:", validators=validators)

@application.route('/writefeed/<int:feed_no>/<int:author_secret>')
def write_feed(feed_no, author_secret):
    db_feed = database.session.query(DBFeed).filter_by(id=feed_no).one()
    # I should really be checking that the secret is correct? Although
    # that is done by 'commentate_on_feed'
    return flask.render_template('author_feed.html', feed_no=feed_no,
                                 secret=author_secret,
                                 commentate_form=CommentateForm())

@application.route('/viewfeed/<int:feed_no>')
def view_feed(feed_no):
    db_feed = database.session.query(DBFeed).filter_by(id=feed_no).one()
    return flask.render_template('view_feed.html', feed_no=feed_no)


def event_stream():
    pubsub = redis_protocol.pubsub()
    pubsub.subscribe('chat')
    # TODO: handle client disconnection.
    for message in pubsub.listen():
        print(message)
        yield 'data: %s\n\n' % message['data']

@application.route('/stream')
def stream():
    return flask.Response(event_stream(),
                          mimetype="text/event-stream")


@application.route('/commentate/<int:feed_no>/<int:secret>',
                   methods=['POST'])
def commentate_on_feed(feed_no, secret):
    try:
        query = database.session.query(DBFeed)
        db_feed = query.filter_by(id=feed_no).one()
    except SQLAlchemyError:
        flask.flash("Feed number: {0} not found!".format(feed_no))
        return flask.redirect(redirect_url())
    if db_feed.author_secret != secret:
        msg = 'You do not have the correct secret to post to this feed'
        flask.flash(msg)
        return flask.redirect(redirect_url())
    form = CommentateForm()
    if form.validate_on_submit():
        now = datetime.datetime.now().replace(microsecond=0).time()
        message = u'[{0}]: {1}'.format(now.isoformat(),
                                       form.comment_text.data)
        redis_protocol.publish('chat', message)
        database.session.commit()
        return flask.redirect(redirect_url())
    flask.flash("Commentate form not validated.")
    return flask.redirect(redirect_url())
    

# Show a list of current/recent bbb-events

# Allow viewing a single bbb-event (although we will want to be able
# to combine bbb-events so that a user can monitor several).

# 1. we need to figure out a way for runserver to automatically have
# --threaded.

# 2. Obviously each feed should have a different channel, that should
# be pretty easy.

# 3. Posting should not make you leave the current page but simply
# post the new comment.

# 4. Obviously we need some kind of permenance to these comments so that
# new visitors to a feed can see the previous comments.

if __name__ == "__main__":
    application.run(debug=True, threaded=True)
