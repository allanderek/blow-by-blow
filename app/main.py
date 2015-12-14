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
    db_feeds = query.all()  # Turns into a list, might be better to iter.
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
    comment_text = wtforms.TextAreaField("Next comment:")


@application.route('/viewfeed/<int:feed_no>')  # noqa
@application.route('/viewfeed/<int:feed_no>/<int:secret>')
def view_feed(feed_no, secret=None):
    db_feed = database.session.query(DBFeed).filter_by(id=feed_no).one()
    update_feed_form = None if secret is None else UpdateFeedForm()
    if secret is not None and secret != db_feed.author_secret:
        viewers_link = flask.url_for('view_feed', feed_no=feed_no)
        message = ("<p>You do not have the correct author secret "
                   "to update this feed, hence you will be unable "
                   "to make any updates including adding moments."
                   "</p>"
                   "<p>"
                   'You can simply view the feed <a href="{0}">here</a> '
                   "without any author controls."
                   "</p>").format(viewers_link)
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


class FeedbackForm(flask_wtf.Form):
    feedback_name = wtforms.StringField("Name:")
    feedback_email = wtforms.StringField("Email:")
    feedback_text = wtforms.TextAreaField("Next comment:")


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
    # because this code will not be executed in a different process to the
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
        selector = '#feed-title'
        title_element = self.driver.find_element_by_css_selector(selector)
        self.assertEqual(title, title_element.text)

    def check_feed_description(self, description):
        selector = '#feed-description'
        desc_element = self.driver.find_element_by_css_selector(selector)
        self.assertEqual(description, desc_element.text)

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
        selector = 'div.alert.alert-{0}'.format(category)
        elements = self.driver.find_elements_by_css_selector(selector)
        self.assertTrue(any(message in e.text for e in elements))

    def test_create_feed(self):
        # Start a new feed.
        self.driver.get(self.get_url('startfeed'))

        url_fields = self.driver.current_url.split('/')
        feed_id = url_fields[url_fields.index('viewfeed') + 1]
        expected_viewer_feed_url = '/viewfeed/' + feed_id
        sel_template = 'div.alert a.alert-link[href$="{0}"]'
        send_viewers_div_css = sel_template.format(expected_viewer_feed_url)
        self.assertCssSelectorExists(send_viewers_div_css)

        # Give the feed a title
        title = 'Red Team vs Blue Team'
        update_header_button_css = '#update-feed-header-button'
        self.fill_in_and_submit_form({'#title_text': title},
                                     update_header_button_css)
        self.check_feed_title(title)

        # Give the feed a description, note that we could fill in
        # both the title and the description and *then* click update,
        # but we're doing it as two separate POSTs.
        description_text = "My commentary on the Red vs Blue match."
        self.fill_in_and_submit_form({'#desc_text': description_text},
                                     update_header_button_css)
        self.check_feed_description(description_text)

        # Add a comment to that feed.
        first_comment = 'Match has kicked off, it is raining'
        commentate_button_css = '#commentate_button'
        self.fill_in_and_submit_form({'#comment_text': first_comment},
                                     commentate_button_css)
        self.check_comment_exists(first_comment)

        # In a new window we wish to view the feed without being able
        # to author it, we could just remove the author-secret from the
        # current url but this seems more 'genuine'.
        view_current_url = self.get_url('current')
        script = "$(window.open('{0}'))".format(view_current_url)
        self.driver.execute_script(script)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        feed_link_selector = 'a[href$="{0}"]'.format(expected_viewer_feed_url)
        self.click_element_with_css(feed_link_selector)
        self.assertCssSelectorNotExists(send_viewers_div_css)
        self.assertCssSelectorNotExists(update_header_button_css)
        self.assertCssSelectorNotExists(commentate_button_css)
        self.check_feed_title(title)
        self.check_feed_description(description_text)
        self.check_comment_exists(first_comment)

    def test_feedback(self):
        self.driver.get(self.get_url('/'))
        feedback = {'#feedback_email': "example_user@example.com",
                    '#feedback_name': "Avid User",
                    '#feedback_text': "I hope your feedback form works."}
        self.fill_in_and_submit_form(feedback, '#feedback_submit_button')
        self.check_flashed_message("Thanks for your feedback!", 'info')

    def test_server_is_up_and_running(self):
        response = urllib.request.urlopen(self.get_server_url())
        self.assertEqual(response.code, 200)

    def test_frontpage_links(self):
        """ Just make sure we can go to the front page and that
        the main menu is there and has at least one item."""
        self.driver.get(self.get_server_url())
        main_menu_css = 'nav .container #navbar ul li'
        current_feeds_link_css = main_menu_css + ' a[href$="current"]'
        start_new_feed_link_css = main_menu_css + ' a[href$="startfeed"]'
        self.assertCssSelectorExists(main_menu_css)
        self.assertCssSelectorExists(current_feeds_link_css)
        self.assertCssSelectorExists(start_new_feed_link_css)

    def setUp(self):
        database.create_all()
        database.session.commit()

    def tearDown(self):
        self.driver.quit()
        database.session.remove()
        database.drop_all()

# A lightweight way to write down a few simple todos. Of course using the
# issue tracker is the better way to do this, this is just a lightweight
# solution for relatively *obvious* defects/todos.

# TODO: Posting should not make you leave the current page but simply
# post the new comment. Note however that if you have multiple authors
# then you may in fact wish to refresh the feed when you post, so I'm not
# entirely sure about this.

# TODO: Add some instructions about multiple authors

# TODO: Write a test to specifically check for XSS errors.

# TODO: More tests, specifically for refreshing the feed and toggling
# the feed direction.

# TODO: Check the accessiblity, I suspect it is poor, at least use labels
# for form inputs. Can we install a screen reader and see how it works?

# TODO: Check that someone cannot break the feedback form by sending some
# kind of control/escape characters that would break the 'api' call.
# Obviously would be good to author a test for that as well.

if __name__ == "__main__":
    application.run(debug=True, threaded=True)
