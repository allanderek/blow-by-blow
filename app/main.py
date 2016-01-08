"""A simple web application to create feeds similar to that of the
   live-text feeds on BBC or theguardian. The idea is that anyone can
   begin a live-text feed and additionally readers can combine live-text
   feeds.
"""

import random
import requests
import datetime
import flask
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
import flask_wtf
import wtforms

import threading


def async(f):
    def wrapper(*args, **kwargs):
        thr = threading.Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper


import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Configuration(object):
    SECRET_KEY = b'7a\xe1f\x17\xc9C\xcb*\x85\xc1\x95G\x97\x03\xa3D\xd3F\xcf\x03\xf3\x99>'  # noqa
    LIVE_SERVER_PORT = 5000
    database_file = os.path.join(basedir, '../../db.sqlite')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + database_file
    DOMAIN = os.environ.get('BLOWBYBLOW_DOMAIN', 'localhost')

    MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
    ADMINS = ['allan.clark@gmail.com']

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
        path = flask.url_for('view_feed', feed_no=self.id)
        return application.config['DOMAIN'] + path

    def jsonify(self):
        json_moments = [moment.jsonify() for moment in self.moments]
        return flask.jsonify({'title': self.feed_title,
                              'description': self.feed_desc,
                              'moments': json_moments})


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

    def jsonify(self):
        return {'time': self.date_time.isoformat(),
                'content': self.content}


def create_database_feed():
    """ Create a feed in the database. """
    dbfeed = DBFeed()
    database.session.add(dbfeed)
    database.session.commit()
    return dbfeed


@application.template_test('plural')
def is_plural(container):
    return len(container) > 1


@application.template_filter('flash_bootstrap_category')
def flash_bootstrap_category(flash_category):
    return {'success': 'success',
            'info': 'info',
            'warning': 'warning',
            'error': 'danger',
            'danger': 'danger'}.get(flash_category, 'info')


def redirect_url(default='frontpage'):
    """ A simple helper function to redirect the user back to where they came.

        See: http://flask.pocoo.org/docs/0.10/reqcontext/ and also here:
        http://stackoverflow.com/questions/14277067/redirect-back-in-flask
    """

    return (flask.request.args.get('next') or flask.request.referrer or
            flask.url_for(default))


def render_template(*args, **kwargs):
    """ A simple wrapper, the base template requires some arguments such as
    the feedback form. This means that this argument will be in all calls to
    `flask.render_template` so we may as well factor it out."""
    return flask.render_template(*args, feedback_form=FeedbackForm(), **kwargs)


@application.route('/grabmoments', methods=['POST'])
def grab_moments():
    feed_id = flask.request.form['feed_id']
    db_feed = database.session.query(DBFeed).filter_by(id=feed_id).one()
    return db_feed.jsonify()


@application.route("/")
def frontpage():
    return render_template('frontpage.html')


@application.route('/current')
def current_feeds():
    query = database.session.query(DBFeed)
    # The use of 'all' turns this into a list, might be better
    # for it to simply iterate through the results.
    db_feeds = query.limit(100).all()
    return render_template('current_feeds.html', db_feeds=db_feeds)


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
    moment_text = wtforms.TextAreaField("Next moment:")


@application.route('/viewfeed/<int:feed_no>')  # noqa
@application.route('/viewfeed/<int:feed_no>/<int:secret>')
def view_feed(feed_no, secret=None):
    db_feed = database.session.query(DBFeed).filter_by(id=feed_no).one()
    update_feed_form = None if secret is None else UpdateFeedForm()
    if secret is not None and secret != db_feed.author_secret:
        viewers_link = flask.url_for('view_feed', feed_no=feed_no)
        message_format = """<p>You do not have the correct author secret
        to update this feed, hence you will be unable
        to make any updates including adding moments.
        </p>
        <p>
        You can simply view the feed <a href="{0}">here</a>
        without any author controls.
        </p>
        """
        message = message_format.format(viewers_link)
        flask.flash(flask.Markup(message), 'warning')
    return render_template('view_feed.html',
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
        flask.flash("Feed number: {0} not found!".format(feed_no), 'error')
        return flask.redirect(redirect_url())
    if db_feed.author_secret != secret:
        msg = '<strong>Update Failed:</strong> Incorrect secret!'
        flask.flash(flask.Markup(msg), 'error')
        return flask.redirect(redirect_url())
    form = UpdateFeedForm()
    if not form.validate_on_submit():
        flask.flash("Update feed form not validated.", 'error')
        return flask.redirect(redirect_url())

    # If we get here then it should only be because we have a valid
    # update to the feed. Note that we could check to see if *all* of
    # these entries are empty and if so issue a warning/error.
    new_title = form.title_text.data.lstrip()
    new_description = form.desc_text.data.lstrip()
    moment_text = form.moment_text.data.lstrip()
    if new_title:
        db_feed.feed_title = new_title
    if new_description:
        db_feed.feed_desc = new_description
    if moment_text:
        moment = DBMoment(db_feed.id, moment_text)
        database.session.add(moment)
    database.session.commit()
    return flask.redirect(redirect_url())


class FeedbackForm(flask_wtf.Form):
    feedback_name = wtforms.StringField("Name:")
    feedback_email = wtforms.StringField("Email:")
    feedback_text = wtforms.TextAreaField("Feedback:")


@async
def send_email_message_mailgun(email):
    sandbox = "sandboxadc7751e75ba41dca5e4ab88e3c13306.mailgun.org"
    url = "https://api.mailgun.net/v3/{0}/messages".format(sandbox)
    sender_address = "mailgun@{0}".format(sandbox)
    if email.sender_name is not None:
        sender = "{0} <{1}>".format(email.sender_name, sender_address)
    else:
        sender = sender_address
    api_key = application.config['MAILGUN_API_KEY']
    return requests.post(url,
                         auth=("api", api_key),
                         data={"from": sender,
                               "to": email.recipients,
                               "subject": email.subject,
                               "text": email.body})


class Email(object):
    """ Simple representation of an email message to be sent."""

    def __init__(self, subject, body, sender_name, recipients):
        self.subject = subject
        self.body = body
        self.sender_name = sender_name
        self.recipients = recipients


def send_email_message(email):
    # We don't want to actually send the message every time we're testing.
    # Note that if we really wish to record the emails and check that the
    # correct ones were "sent" out, then we have to do something a bit clever
    # because this code will be executed in a different process to the
    # test code. We could have some kind of test-only route that returns the
    # list of emails sent as a JSON object or something.
    if not application.config['TESTING']:
        send_email_message_mailgun(email)


@application.route('/give_feedback', methods=['POST'])
def give_feedback():
    form = FeedbackForm()
    if not form.validate_on_submit():
        message = ('Feedback form has not been validated.'
                   'Sorry it was probably my fault')
        flask.flash(message, 'error')
        return flask.redirect(redirect_url())
    feedback_email = form.feedback_email.data.lstrip()
    feedback_name = form.feedback_name.data.lstrip()
    feedback_content = form.feedback_text.data
    subject = 'Feedback for Blow-by-Blow'
    sender_name = 'Blow-by-Blow Feedback Form'
    recipients = application.config['ADMINS']
    message_body = """
    You got some feedback from the 'blow-by-blow' web application.
    Sender's name = {0}
    Sender's email = {1}
    Content: {2}
    """.format(feedback_name, feedback_email, feedback_content)
    email = Email(subject, message_body, sender_name, recipients)
    send_email_message(email)
    flask.flash("Thanks for your feedback!", 'info')
    return flask.redirect(redirect_url())


# Now for some testing.
import urllib
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import pytest


class BasicFunctionalityTests(object):  #pragma: no cover
    """Basic functionality test. This requires a running server as it does not
    start one itself. See the 'manage.py' file how this is run.
    """
    def start_driver(self):
        self.driver = webdriver.PhantomJS()
        self.driver.set_window_size(1120, 550)

    def quit_driver(self):
        self.driver.quit()

    def get_url(self, local_url):
        # Obviously this is not the same application instance as the running
        # server and hence the LIVE_SERVER_PORT could in theory be different,
        # but for testing purposes we just make sure it this is correct.
        port = application.config['LIVE_SERVER_PORT']
        url = 'http://localhost:{0}'.format(port)
        return "/".join([url, local_url])

    def assertCssSelectorExists(self, css_selector):
        """ Asserts that there is an element that matches the given
        css selector."""
        # We do not actually need to do anything special here, if the
        # element does not exist we fill fail with a NoSuchElementException
        # however we wrap this up in a pytest.fail because the error message
        # is then a bit nicer to read.
        try:
            self.driver.find_element_by_css_selector(css_selector)
        except NoSuchElementException:
            pytest.fail("Element {0} not found!".format(css_selector))

    def assertCssSelectorNotExists(self, css_selector):
        """ Asserts that no element that matches the given css selector
        is present."""
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_css_selector(css_selector)

    def get_moment_texts(self):
        selector = '#feed-moment-list li .moment-text'
        moment_texts = self.driver.find_elements_by_css_selector(selector)
        return (element.text for element in moment_texts)

    def check_moment_exists(self, moment_text):
        assert (moment_text in self.get_moment_texts())

    def check_moment_does_not_exist(self, moment_text):
        assert moment_text not in self.get_moment_texts()

    def check_moment_order(self, expected_moment_texts):
        """Actually checks if the moments are entirely equal, but in theory
        could just check the ones given are in the correct order ignoring any
        in the feed that are not in the given list of moment texts."""
        moment_texts = self.get_moment_texts()
        assert all(x == y for x, y in zip(expected_moment_texts, moment_texts))

    def check_feed_title(self, title):
        selector = '#feed-title'
        title_element = self.driver.find_element_by_css_selector(selector)
        assert title == title_element.text

    def check_feed_description(self, description):
        selector = '#feed-description'
        desc_element = self.driver.find_element_by_css_selector(selector)
        assert description == desc_element.text

    def fill_in_and_submit_form(self, fields, submit):
        for field_css, field_text in fields.items():
            self.fill_in_text_input_by_css(field_css, field_text)
        self.click_element_with_css(submit)

    def click_element_with_css(self, selector):
        element = self.driver.find_element_by_css_selector(selector)
        element.click()

    def fill_in_text_input_by_css(self, input_css, input_text):
        input_element = self.driver.find_element_by_css_selector(input_css)
        input_element.send_keys(input_text)

    def check_flashed_message(self, message, category):
        category = flash_bootstrap_category(category)
        selector = 'div.alert.alert-{0}'.format(category)
        elements = self.driver.find_elements_by_css_selector(selector)
        if category == 'error':
            print("error: messages:")
            for e in elements:
                print(e.text)
        assert any(message in e.text for e in elements)

    update_header_button_css = '#update-feed-header-button'
    add_moment_submit_button_css = '#add-moment-button'

    def check_author_controls(self, is_author, expected_viewer_feed_url):
        assertExistance = (self.assertCssSelectorExists if is_author
                           else self.assertCssSelectorNotExists)
        sel_template = 'div.alert a.alert-link[href$="{0}"]'
        send_viewers_div_css = sel_template.format(expected_viewer_feed_url)
        assertExistance(send_viewers_div_css)
        assertExistance(send_viewers_div_css)
        assertExistance(self.update_header_button_css)
        assertExistance(self.add_moment_submit_button_css)

    def add_feed_moment(self, moment_text):
        submit_css = self.add_moment_submit_button_css
        form_fields = {'#moment_text': moment_text}
        self.fill_in_and_submit_form(form_fields, submit_css)

    def open_new_window(self, url):
        script = "$(window.open('{0}'))".format(url)
        self.driver.execute_script(script)

    def test_create_feed(self):
        self.driver.get(self.get_url('startfeed'))
        author_url = self.driver.current_url
        url_fields = author_url.split('/')
        feed_id = url_fields[url_fields.index('viewfeed') + 1]
        expected_viewer_feed_url = '/viewfeed/' + feed_id
        self.check_author_controls(True, expected_viewer_feed_url)

        # Give the feed a title
        title = 'Red Team vs Blue Team'
        self.fill_in_and_submit_form({'#title_text': title},
                                     self.update_header_button_css)
        self.check_feed_title(title)

        # Give the feed a description, note that we could fill in
        # both the title and the description and *then* click update,
        # but we're doing it as two separate POSTs.
        description_text = "My commentary on the Red vs Blue match."
        self.fill_in_and_submit_form({'#desc_text': description_text},
                                     self.update_header_button_css)
        self.check_feed_description(description_text)

        # Add a moment to that feed.
        first_moment = 'Match has kicked off, it is raining.'
        self.add_feed_moment(first_moment)
        self.check_moment_exists(first_moment)

        # Now add a second moment to that feed
        second_moment = "We're into the second minute."
        self.add_feed_moment(second_moment)
        self.check_moment_exists(second_moment)

        # In a new window we wish to view the feed without being able
        # to author it, we could just remove the author-secret from the
        # current url but this seems more 'genuine'.
        view_current_url = self.get_url('current')
        self.open_new_window(view_current_url)
        author_window_handle = self.driver.window_handles[0]
        viewer_window_handle = self.driver.window_handles[-1]
        self.driver.switch_to.window(viewer_window_handle)
        feed_link_selector = 'a[href$="{0}"]'.format(expected_viewer_feed_url)
        self.click_element_with_css(feed_link_selector)
        self.check_author_controls(False, expected_viewer_feed_url)
        self.check_feed_title(title)
        self.check_feed_description(description_text)

        self.check_moment_order([second_moment, first_moment])
        feed_direction_toggle_css = '#feed-direction-button'
        self.click_element_with_css(feed_direction_toggle_css)
        self.check_moment_order([first_moment, second_moment])

        # Switch back to the original author window and add a new moment
        # then switch back to the viewer window, press refresh feed and
        # check that the new moment is there *and* the feed is in the
        # correct order.
        self.driver.switch_to.window(author_window_handle)
        third_moment = "A booking in the third minute."
        self.add_feed_moment(third_moment)
        self.driver.switch_to_window(viewer_window_handle)
        refresh_feed_css = '#refresh-feed-button'
        self.click_element_with_css(refresh_feed_css)
        self.check_moment_order([first_moment,
                                 second_moment, third_moment])

        # Now open another window and go to a url that has a secret but
        # one that is incorrect, and check that the warning is flashed.
        incorrect_author_url = author_url + "1"
        self.open_new_window(incorrect_author_url)
        self.driver.switch_to_window(self.driver.window_handles[-1])
        expected_message = "You do not have the correct author secret"
        self.check_flashed_message(expected_message, 'warning')

        # Now we attempt to add a moment anyway and check that we get
        # an error flashed to us and that the moment does not exist.
        failed_moment = "I cannot add moments here."
        self.add_feed_moment(failed_moment)
        self.check_moment_does_not_exist(failed_moment)
        self.check_flashed_message("Update Failed", 'error')
        # Switch back to the viewer window, refresh the feed and check
        # that the moment does not exist.
        self.driver.switch_to_window(viewer_window_handle)
        self.click_element_with_css(refresh_feed_css)
        self.check_moment_does_not_exist(failed_moment)

    def test_feedback(self):
        self.driver.get(self.get_url('/'))
        feedback = {'#feedback_email': "example_user@example.com",
                    '#feedback_name': "Avid User",
                    '#feedback_text': "I hope your feedback form works."}
        self.fill_in_and_submit_form(feedback, '#feedback_submit_button')
        self.check_flashed_message("Thanks for your feedback!", 'info')

    def test_server_is_up_and_running(self):
        response = urllib.request.urlopen(self.get_url('/'))
        assert response.code == 200

    def test_frontpage_links(self):
        """ Just make sure we can go to the front page and that
        the main menu is there and has at least one item."""
        self.driver.get(self.get_url('/'))
        main_menu_css = 'nav .container #navbar ul li'
        current_feeds_link_css = main_menu_css + ' a[href$="current"]'
        start_new_feed_link_css = main_menu_css + ' a[href$="startfeed"]'
        self.assertCssSelectorExists(main_menu_css)
        self.assertCssSelectorExists(current_feeds_link_css)
        self.assertCssSelectorExists(start_new_feed_link_css)

def test_our_server():  #pragma: no cover
    basic = BasicFunctionalityTests()
    basic.start_driver()
    try:
        basic.test_server_is_up_and_running()
        basic.test_frontpage_links()
        basic.test_create_feed()
        basic.test_feedback()
    finally:
        basic.driver.get(basic.get_url('shutdown'))
        basic.quit_driver()


# A lightweight way to write down a few simple todos. Of course using the
# issue tracker is the better way to do this, this is just a lightweight
# solution for relatively *obvious* defects/todos.

# TODO: Posting should not make you leave the current page but simply
# post the new moment. Note however that if you have multiple authors
# then you may in fact wish to refresh the feed when you post, so I'm not
# entirely sure about this.

# TODO: Add some instructions about multiple authors

# TODO: Write a test to specifically check for XSS errors.

# TODO: Check the accessiblity, I suspect it is poor, at least use labels
# for form inputs. Can we install a screen reader and see how it works?

# TODO: Check that someone cannot break the feedback form by sending some
# kind of control/escape characters that would break the 'api' call.
# Obviously would be good to author a test for that as well.

if __name__ == "__main__":
    application.run(debug=True, threaded=True)
