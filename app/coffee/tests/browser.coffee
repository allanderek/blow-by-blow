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


# test inventory management

testObjectsByName = {}
allTestObjects = []

registerTest = (test) ->
  allTestObjects.push test
  for name in test.names
    testObjectsByName[name] = test

# test suites
class BrowserTest
  # An abstract base class for our browser tests
  #
  # Instances should define the following properties:
  #
  # * testBody: called by `run` below to execute the test
  # * names: array of names by which a caller can identify this test (with the
  #          `--single` command line option)
  # * description
  # * numTests: expected number of assertions

  run: =>
    casper.test.begin @description, @numTests, (test) =>
      casper.start()
      @testBody(test)
      casper.then ->
        test.done()

  names: []
  description: 'This class needs a description'
  numTests: 0

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

class FrontPageTest extends BrowserTest
  names: ['FrontPage']
  description: "Simplest test possible, we visit the homepage."
  numTests: 1

  testBody: (test) ->
    casper.thenOpen serverUrl, ->
      test.assertExists 'h1'

registerTest new FrontPageTest


class NormalFunctionalityTest extends BrowserTest
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

registerTest new NormalFunctionalityTest

runTests = (name) ->
  test = testObjectsByName[name]
  test.run()

runAll = ->
  for test in allTestObjects
    test.run()

shutdown = ->
  casper.log "shutting down..."
  casper.open 'http://localhost:5000/shutdown', method: 'post'

if casper.cli.has("single")
  runTest casper.cli.options['single']
else
  runAll()

casper.run ->
  shutdown()
