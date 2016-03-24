# compute server url from arguments

defaultHost = "http://localhost"
host = casper.cli.options['host'] or defaultHost
port = casper.cli.options['port'] or
  if host is defaultHost then "5000" else "80"

portString = if port == "80" or port == 80 then "" else ":#{port}"

unless (host.match /localhost/) or (host.match /staging/)
  casper.die "Server url contains neither 'localhost' nor 'staging', aborting"

serverUrl = "#{host}#{portString}"
casper.echo "Testing against server at #{serverUrl}"

debug_dump_html = () ->
  "Occasionally can be useful during debugging just to dump the current HTML."
  casper.echo (casper.getHTML())


class NormalFunctionalityTest
  names: ['NormalFunctionality']
  description: "Tests the normal functionality of authoring and viewing feeds"
  numTests: 20

  original_title: 'Original title'
  original_description: 'Original description'
  feed_title: 'Red Team vs Blue Team'
  feed_description: 'My commentary on the Red vs Blue match'
  first_moment: 'Match has kicked off, it is raining.'
  second_moment: "We're into the second minute."
  third_moment: "A booking in the third minute."

  run: =>
    casper.test.begin @description, @numTests, (test) =>
      casper.start()
      @testBody(test)
      casper.then ->
        test.done()


  testBody: (test) ->
    author_url = null
    expected_viewer_feed_url = null
    casper.thenOpen (@get_url 'startfeed'), =>
      form_data =
         '#title_text': @original_title
         '#desc_text': @original_description
      casper.fillSelectors '#create-feed-form', form_data, true
      debug_dump_html()
    casper.waitForText @original_title, =>
      @check_feed_title test, @original_title
      @check_feed_description test, @original_description
      author_url = casper.getCurrentUrl()
      fields = author_url.split "/"
      feed_id = fields[4]
      expected_viewer_feed_url = '/viewfeed/' + feed_id
      @check_author_controls test, true, expected_viewer_feed_url
      # Give the feed a title
      casper.fillSelectors '#update-feed', ('#title_text': @feed_title), true
    casper.waitForText @feed_title, =>
      @check_feed_title test, @feed_title
      # Give the feed a description, note that we could fill in
      # both the title and the description and *then* click update,
      # but we're doing it as two separate POSTs.
      casper.fillSelectors '#update-feed',
                           ('#desc_text': @feed_description), true
    casper.then =>
      @check_feed_description test, @feed_description
      # Add a moment to that feed.
      @add_moment @first_moment
    casper.then =>
      @add_moment @second_moment
    casper.waitForText @second_moment, =>
      @check_moments test, [@second_moment, @first_moment]
    # We would really like to do the viewing in a second window but that seems
    # at best non-trivial in casperJS, and perhaps impossible. So for the
    # time-being we just use the one window.
    casper.thenOpen (@get_url 'current'), ->
      feed_url = expected_viewer_feed_url
      feed_link_selector = "a[href$=\"#{feed_url}\"]"
      test.assertExists feed_link_selector
      # Save the csrf_token for later use (that later use is not working yet)
      # csrf_selector = '#update-controls input#csrf_token'
      # @csrf_token = casper.getElementAttribute csrf_selector, 'value'
      casper.click feed_link_selector
    casper.then =>
      @check_author_controls test, false, expected_viewer_feed_url
      @check_feed_title test, @feed_title
      @check_feed_description test, @feed_description
      # Now we check the moment order, then hit the toggle order button and
      # check that we indeed have a toggled moment order
      @check_moments test, [@second_moment, @first_moment]
      casper.click '#feed-direction-button'
    casper.waitFor ->
      return casper.evaluate ->
        return earliest_first
    casper.then =>
      @check_moments test, [@first_moment, @second_moment]
    # We would like to switch back to the author window at this point, but
    # unfortunately due to a limitation in casperJS that only allows for a
    # single open window, so instead we'll send a post request to update the
    # feed with the correct author secret and then check that the refresh feed
    # works.
    # TODO, this does not quite work yet.
    # casper.then =>
    #   fields = author_url.split "/"
    #   feed_id = fields[4]
    #   author_secret = fields[5]
    #   update_url = @get_url "update_feed/#{feed_id}/#{author_secret}"
    #   casper.echo update_url
    #   casper.open update_url, method: 'post', data: {
    #     'title_text': ''
    #     'desc_text': ''
    #     'moment_text': @third_moment
    #     'csrf_token': @csrf_token
    #   }
    # casper.thenClick '#refresh-feed-button', =>
    #  @check_moments test, [@first_moment, @second_moment, @third_moment]
    # This represents a slightly strange construction here merely because
    # outwith a 'then' step we cannot access 'author_url'
    casper.then ->
      incorrect_author_url = author_url + "1"
      casper.open incorrect_author_url
    casper.then =>
      expected_message = "You do not have the correct author secret"
      @check_flashed_message test, expected_message, 'warning'

  get_url: (local_url) ->
    serverUrl + "/" + local_url

  update_header_button_css: '#update-feed-header-button'
  add_moment_submit_button_css: '#add-moment-button'

  check_feed_title: (test, expected_title) ->
    test.assertSelectorHasText '#feed-title', expected_title,
      'Feed has the correct title'

  check_feed_description: (test, expected_desc) ->
    test.assertSelectorHasText '#feed-description', expected_desc,
      'Feed has the correct description'

  check_author_controls: (test, is_author, expected_viewer_feed_url) ->
    viewer_link_selector = "div.alert
                            a.alert-link[href$=\"#{expected_viewer_feed_url}\"]"
    assertion = (s) ->
      if is_author then test.assertExists s else test.assertDoesntExist s
    assertion viewer_link_selector
    assertion @update_header_button_css
    assertion @add_moment_submit_button_css

  add_moment: (moment_text) ->
    casper.fillSelectors '#make-moment', ('#moment_text': moment_text), true

  check_moments: (test, expected_moment_texts) ->
    for moment in expected_moment_texts
      test.assertSelectorHasText '#feed-moment-list li .moment-text', moment,
                                 'Checking moments in feed.'

  check_flashed_message: (test, expected_message, category) ->
    selector = "div.alert.alert-#{category}"
    test.assertSelectorHasText selector, expected_message,
      'Checking flashed message'


test_classes = [new NormalFunctionalityTest]
for test in test_classes
  test.run()

casper.run ->
  casper.log "tests concluded ..."
