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
  numTests: 12

  feed_title: 'Red Team vs Blue Team'
  feed_description: 'My commentary on the Red vs Blue match'
  first_moment: 'Match has kicked off, it is raining.'
  second_moment: "We're into the second minute."

  testBody: (test) ->
    url = @get_url 'startfeed'
    casper.thenOpen url, =>
      current_url = casper.getCurrentUrl()
      fields = current_url.split "/"
      feed_id = fields[4]
      @expected_viewer_feed_url = '/viewfeed/' + feed_id
      @check_author_controls test, true, @expected_viewer_feed_url
      # Give the feed a title
      casper.fillSelectors '#update-feed', ('#title_text': @feed_title), true
    casper.then =>
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
    casper.then =>
      @check_moments test, [@second_moment, @first_moment]
    # We would really like to do the viewing in a second window but that seems
    # at best non-trivial in casperJS, and perhaps impossible. So for the
    # time-being we just use the one window.
    casper.thenOpen (@get_url 'current'), =>
      feed_url = @expected_viewer_feed_url
      feed_link_selector = "a[href$=\"#{feed_url}\"]"
      test.assertExists feed_link_selector
      casper.click feed_link_selector
    casper.then =>
      @check_author_controls test, false, @expected_viewer_feed_url
      @check_feed_title test, @feed_title
      @check_feed_description test, @feed_description


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
    # casper.fetchTexts returns the concatenated string of all the texts
    # from all the elements matching the given selector.
    # actual_moments = casper.fetchText '#feed-moment-list li .moment-text'
    #test.assertEqual actual_moments, (expected_moment_texts.join())
    test.assertSelectorHasText '#feed-moment-list li .moment-text',
      (expected_moment_texts.join('')), 'Checking moments in feed.'

runTestClass = (testClass) ->
  casper.test.begin testClass.description, testClass.numTests, (test) ->
    casper.start()
    testClass.testBody(test)
    casper.run ->
      test.done()

runTestClass (new NormalFunctionalityTest)

casper.test.begin 'The shutdown test', 0, (test) ->
  casper.start()
  casper.thenOpen 'http://localhost:5000/shutdown', method: 'post', ->
    casper.echo 'Shutting down ...'
  casper.run ->
    casper.echo 'Shutdown'
    test.done()
