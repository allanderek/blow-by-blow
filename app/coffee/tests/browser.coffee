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
  numTests: 3

  testBody: (test) ->
    url = @get_url 'startfeed'
    casper.thenOpen url, =>
      current_url = casper.getCurrentUrl()
      fields = current_url.split "/"
      feed_id = fields[4]
      expected_viewer_feed_url = '/viewfeed/' + feed_id
      @check_author_controls test, expected_viewer_feed_url

  get_url: (local_url) ->
    serverUrl + "/" + local_url

  update_header_button_css: '#update-feed-header-button'
  add_moment_submit_button_css: '#add-moment-button'

  check_author_controls: (test, expected_viewer_feed_url) ->
    viewer_link_selector = "div.alert
                            a.alert-link[href$=\"#{expected_viewer_feed_url}\"]"
    test.assertExists viewer_link_selector
    test.assertExists @update_header_button_css
    test.assertExists @add_moment_submit_button_css

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
