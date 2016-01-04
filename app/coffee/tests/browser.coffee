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
  numTests: 6

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
      expected_viewer_feed_url = '/viewfeed/' + feed_id
      @check_author_controls test, expected_viewer_feed_url
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
      # @add_moment @first_moment
      casper.fillSelectors '#make-moment', ('#moment_text': @first_moment), true
    casper.then =>
      casper.fillSelectors '#make-moment', ('#moment_text': @second_moment), true
    casper.then =>
      @check_moments test, [@second_moment, @first_moment]


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

  check_author_controls: (test, expected_viewer_feed_url) ->
    viewer_link_selector = "div.alert
                            a.alert-link[href$=\"#{expected_viewer_feed_url}\"]"
    test.assertExists viewer_link_selector
    test.assertExists @update_header_button_css
    test.assertExists @add_moment_submit_button_css

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
    casper.echo 'I just want anything to work.'
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
