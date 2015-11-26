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
import flask
from flask import request, url_for
import sqlalchemy
import sqlalchemy.orm
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
import flask_wtf
import wtforms


import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Configuration(object):
    SECRET_KEY = b'7a\xe1f\x17\xc9C\xcb*\x85\xc1\x95G\x97\x03\xa3D\xd3F\xcf\x03\xf3\x99>'  # noqa
    LIVE_SERVER_PORT = 5000
    database_file = os.path.join(basedir, '../../db.sqlite')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + database_file
    DOMAIN = 'localhost'
application = flask.Flask(__name__)
application.config.from_object(Configuration)

database = SQLAlchemy(application)


class DBFeed(database.Model):
    __tablename__ = 'feeds'
    id = database.Column(database.Integer, primary_key=True)
    author_secret = database.Column(database.Integer)
    moments = database.relationship('DBMoment')
    feed_title = database.Column(database.String(2400),
                                 default='My Event')
    feed_desc = database.Column(database.String(2400),
                                default="Description of this feed.")

    def __init__(self):
        self.author_secret = random.getrandbits(48)

    @property
    def viewers_link(self):
        path = url_for('view_feed', feed_no=self.id)
        return application.config['DOMAIN'] + path

class DBMoment(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    content = database.Column(database.String(2400))
    feed_id = database.Column(database.Integer,
                              database.ForeignKey('feeds.id'))
    date_time = database.Column(database.DateTime(timezone=False),
                                default=datetime.datetime.utcnow)

    def __init__(self, feed_id, content):
        self.feed_id = feed_id
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

@application.route('/current')
def current_feeds():
    query = database.session.query(DBFeed)
    db_feeds = query.all() # Turns into a list, might be better to iter.
    return flask.render_template('current_feeds.html',
                                 db_feeds=db_feeds)

# Create a bbb-feed
@application.route('/startfeed')
def start_feed():
    # TODO: The only thing about this is, that I don't really want
    # people accidentally refreshing and starting multiple feeds, so I
    # guess I want this to only accept POST?
    db_feed = create_database_feed()
    url = flask.url_for('view_feed', feed_no=db_feed.id,
                        secret=db_feed.author_secret)
    return flask.redirect(url)


class UpdateFeedForm(flask_wtf.Form):
    title_text = wtforms.StringField("New Title:")
    desc_text = wtforms.TextAreaField("Description:")
    comment_text = wtforms.TextAreaField("Next comment:")


@application.route('/viewfeed/<int:feed_no>')  # noqa
@application.route('/viewfeed/<int:feed_no>/<int:secret>')
def view_feed(feed_no, secret=None):
    db_feed = database.session.query(DBFeed).filter_by(id=feed_no).one()
    update_feed_form = None if secret is None else UpdateFeedForm()
    # I should really be checking that the secret is correct? Although
    # that is done by 'commentate_on_feed'
    return flask.render_template('view_feed.html',
                                 db_feed=db_feed,
                                 secret=secret,
                                 update_feed_form=update_feed_form)


@application.route('/update_feed/<int:feed_no>/<int:secret>',
                   methods=['POST'])
def update_feed(feed_no, secret):
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
    form = UpdateFeedForm()
    if not form.validate_on_submit():
        flask.flash("Change title form not validated.")
        return flask.redirect(redirect_url())

    # If we get here then it should only be because we have a valid
    # update to the feed. Note that we could check to see if *all* of
    # these entries are empty and if so issue a warning/error.
    new_title = form.title_text.data.lstrip()
    new_description = form.desc_text.data.lstrip()
    comment = form.comment_text.data.lstrip()
    if new_title:
        db_feed.feed_title = new_title
    if new_description:
        db_feed.feed_desc = new_description
    if comment:
        moment = DBMoment(db_feed.id, comment)
        database.session.add(moment)
    database.session.commit()
    return flask.redirect(redirect_url())

# Allow viewing a single bbb-event (although we will want to be able
# to combine bbb-events so that a user can monitor several).

# 3. Posting should not make you leave the current page but simply
# post the new comment.

# Now for some testing.
import flask.ext.testing
import urllib
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException


class BasicFunctionalityTest(flask.ext.testing.LiveServerTestCase):
    def create_app(self):
        application.config['TESTING'] = True
        # Default port is 5000
        application.config['LIVESERVER_PORT'] = 8943

        # Don't use the production database but a temporary test
        # database.
        application.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///test.db"
        
        self.driver = webdriver.PhantomJS()
        self.driver.set_window_size(1120, 550)
        return application

    def get_url(self, local_url):
        return "/".join([self.get_server_url(), local_url])

    def assertCssSelectorExists(self, css_selector):
        """ Asserts that there is an element that matches the given
        css selector."""
        try:
            self.driver.find_element_by_css_selector(css_selector)
        except NoSuchElementException:
            self.assertTrue(False)

    def assertCssSelectorNotExists(self, css_selector):
        """ Asserts that no element that matches the given css selector
        is present."""
        with self.assertRaises(NoSuchElementException):
            self.driver.find_element_by_css_selector(css_selector)

    def check_comment_exists(self, comment):
        selector = '#feed-moment-list li .comment-text'
        comments = self.driver.find_elements_by_css_selector(selector)
        comment_texts = (element.text for element in comments)
        self.assertIn(comment, comment_texts)

    def check_feed_title(self, title):
        selector = '.feed-title'
        title_element = self.driver.find_element_by_css_selector(selector)
        self.assertEqual(title, title_element.text)

    def check_feed_description(self, description):
        selector = '.feed-description'
        desc_element = self.driver.find_element_by_css_selector(selector)
        self.assertEqual(description, desc_element.text)

    def fill_in_and_submit_form(self, fields, submit):
        for field_css, field_text in fields:
            self.fill_in_text_input_by_css(field_css, field_text)
        self.click_element_with_css(submit)

    def click_element_with_css(self, selector):
        element = self.driver.find_element_by_css_selector(selector)
        element.click()

    def fill_in_text_input_by_css(self, input_css, input_text):
        input_element = self.driver.find_element_by_css_selector(input_css)
        input_element.send_keys(input_text)

    def test_create_feed(self):
        # Start a new feed.
        self.driver.get(self.get_url('startfeed'))

        send_viewers_div_css = '#send-viewers-link'
        self.assertCssSelectorExists(send_viewers_div_css)

        # Give the feed a title
        title = 'Red Team vs Blue Team'
        update_header_button_css = '#update-feed-header-button'
        self.fill_in_and_submit_form([('#title_text', title)],
                                     update_header_button_css)
        self.check_feed_title(title)

        # Give the feed a description, note that we could fill in
        # both the title and the description and *then* click update,
        # but we're doing it as two separate POSTs.
        description_text = "My commentary on the Red vs Blue match."
        self.fill_in_and_submit_form([('#desc_text', description_text)],
                                      update_header_button_css)
        self.check_feed_description(description_text)

        # Add a comment to that feed.
        first_comment = 'Match has kicked off, it is raining'
        commentate_button_css = '#commentate_button'
        self.fill_in_and_submit_form([('#comment_text', first_comment)],
                                     commentate_button_css)
        self.check_comment_exists(first_comment)

        # In a new window we wish to view the feed without being able
        # to author it, we could just remove the author-secret from the
        # current url but this seems more 'genuine'.
        url_fields = self.driver.current_url.split('/')
        feed_id = url_fields[url_fields.index('viewfeed') + 1]
        # view_url = self.get_server_url() + '/viewfeed/' + feed_id
        view_current_url = self.get_url('current')
        script = "$(window.open('{0}'))".format(view_current_url)
        self.driver.execute_script(script)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        expected_feed_url = '/viewfeed/' + feed_id
        feed_link_selector = 'a[href$="{0}"]'.format(expected_feed_url)
        self.click_element_with_css(feed_link_selector)
        self.assertCssSelectorNotExists(send_viewers_div_css)
        self.assertCssSelectorNotExists(update_header_button_css)
        self.assertCssSelectorNotExists(commentate_button_css)
        self.check_feed_title(title)
        self.check_feed_description(description_text)
        self.check_comment_exists(first_comment)

    def test_server_is_up_and_running(self):
        response = urllib.request.urlopen(self.get_server_url())
        self.assertEqual(response.code, 200)

    def test_frontpage_links(self):
        """ Just make sure we can go to the front page and that
        the main menu is there and has at least one item."""
        self.driver.get(self.get_server_url())
        main_menu_css = '#main_menu ul li'
        self.assertCssSelectorExists(main_menu_css)

    def setUp(self):
        database.create_all()
        database.session.commit()

    def tearDown(self):
        self.driver.quit()
        database.session.remove()
        database.drop_all()

# TODO: Write a test to specifically check for XSS errors.


if __name__ == "__main__":
    application.run(debug=True, threaded=True)
