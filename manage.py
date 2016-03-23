import os

import flask
from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand
import requests
import subprocess

from app.main import application, database

migrate = Migrate(application, database)
manager = Manager(application)
manager.add_command('db', MigrateCommand)


def run_command(command):
    """ We frequently inspect the return result of a command so this is just
        a utility function to do this. Generally we call this as:
        return run_command ('command_name args')
    """
    result = os.system(command)
    return 0 if result == 0 else 1


@manager.command
def coffeelint():
    return run_command('coffeelint app/coffee')


@manager.command
def coffeebuild():
    return run_command('coffee -cb -o app/static/compiled-js app/coffee')


def coverage_command(command_args, coverage, accumulate):
    """The `accumulate` argument specifies whether we should add to the existing
    coverage data or wipe that and start afresh. Generally you wish to
    accumulate if you need to run multiple commands and you want the coverage
    analysis relevant to all those commands. So, for the commands we specify
    below this is usually off by default, since if you are running coverage on
    a particular test command then presumably you only wish to know about that
    command. However, for the main 'test' command, we want to accumulte the
    coverage results for both the casper and unit tests, hence in our 'test'
    command below we supply 'accumulate=True' for the sub-commands test_casper
    and run_unittests.
    """
    
    # No need to specify the sources, this is done in the .coveragerc file.
    if coverage:
        command = ["coverage", "run"]
        if accumulate:
            command.append("-a")
        return command + command_args
    else:
        return ['python'] + command_args
    
def run_with_test_server(test_command, coverage, accumulate):
    """Run the test server and the given test command in parallel. If 'coverage'
    is True, then we run the server under coverage analysis and produce a
    coverge report.
    """
    # Note, if we start running Selenium tests again, then we should have,
    # rather than a single 'test_command' a series of 'test_commands'. Then
    # we start the server and *then* run each of the test commands, that way
    # we will get the combined coverage of all the test commands, for example
    # selenium + capserJS tests.
    server_command_args = ["manage.py", "run_test_server"]
    server_command = coverage_command(server_command_args, coverage, accumulate)
    server = subprocess.Popen(server_command, stderr=subprocess.PIPE)
    # TODO: If we don't get this line we should  be able to detect that
    # and avoid the starting test process.
    for line in server.stderr:
        if b' * Running on' in line:
            break
    test_process = subprocess.Popen(test_command)
    test_return_code = test_process.wait(timeout=60)
    # Once the test process has completed we can shutdown the server. To do so
    # we have to make a request so that the server process can shut down
    # cleanly, and in particular finalise coverage analysis.
    # We could check the return from this is success.
    requests.post('http://localhost:5000/shutdown')
    server_return_code = server.wait(timeout=60)
    if coverage:
        os.system("coverage report -m")
        os.system("coverage html")
    return test_return_code + server_return_code


@manager.command
def test_casper(name=None, coverage=False, accumulate=False):
    """Run the casper test suite with or without coverage analysis."""
    if coffeebuild():
        print("Coffee script failed to compile, exiting test!")
        return 1
    js_test_file = "app/static/compiled-js/tests/browser.js"
    casper_command = ["./node_modules/.bin/casperjs", "test", js_test_file]
    if name is not None:
        casper_command.append('--single={}'.format(name))
    return run_with_test_server(casper_command, coverage, accumulate)

@manager.command
def test_main(name=None, coverage=False, accumulate=True):
    """Run the casper test suite with or without coverage analysis."""
    # Unlike in casper we run coverage on this command as well, however we need
    # to accumulate if we want this to work at all, because we need to
    # accumulate the coverage results of the server process as well as the
    # pytest process itself. We do this because we want to make sure that the
    # tests themselves don't contain dead code. So it almost never makes sense
    # to run `test_main` with `coverage=True` but `accumulate=False`.
    pytest_command = coverage_command(['-m', 'pytest', 'app/main.py'],
                                      coverage, accumulate)
    if name is not None:
        pytest_command.append('--k={}'.format(name))
    return run_with_test_server(pytest_command, coverage, accumulate)


@manager.command
def test(nocoverage=False, coverage_erase=True):
    """ Run both the casperJS and all the unittests. We do not bother to run
    the capser tests if the unittests fail. By default this will erase any
    coverage-data accrued so far, you can avoid this, and thus get the results
    for multiple runs by passing `--coverage_erase=False`"""
    if coverage_erase:
        os.system('coverage erase')
    coverage = not nocoverage
    unit_result = test_main(coverage=coverage, accumulate=True)
    if unit_result:
        print('Unit test failure!')
        return unit_result
    casper_result = test_casper(coverage=coverage,  accumulate=True)
    if not casper_result:
        print('All tests passed!')
    else:
        print('Casper test failure!')
    return casper_result


def shutdown():
    """Shutdown the Werkzeug dev server, if we're using it.
    From http://flask.pocoo.org/snippets/67/"""
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:  # pragma: no cover
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'


@manager.command
def run_test_server():
    """Used by the phantomjs tests to run a live testing server"""
    # running the server in debug mode during testing fails for some reason
    application.config['DEBUG'] = True
    application.config['TESTING'] = True
    port = application.config['LIVE_SERVER_PORT']
    # Don't use the production database but a temporary test database.
    application.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///test.db"
    database.create_all()
    database.session.commit()

    # Add a route that allows the test code to shutdown the server, this allows
    # us to quit the server without killing the process thus enabling coverage
    # to work.
    application.add_url_rule('/shutdown', 'shutdown', shutdown,
                             methods=['POST', 'GET'])

    application.run(port=port, use_reloader=False, threaded=True)

    database.session.remove()
    database.drop_all()


if __name__ == "__main__":
    manager.run()
