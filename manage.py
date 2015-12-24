import os

from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

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
    return run_command('coffee -c -o app/static/compiled-js app/coffee')


@manager.command
def test_browser(name):
    """Run a single browser test, given its name (excluding `test_`)"""
    command = "python -m unittest app.browser_tests.test_{}".format(name)
    return run_command(command)


@manager.command
def test_casper(nocoverage=False):
    """Run the casper test suite with or without coverage analysis."""
    import subprocess
    coverage_prefix = ["coverage", "run", "--source", "app.main"]
    server_command_prefx = ['python'] if nocoverage else coverage_prefix
    server_command = server_command_prefx + ["manage.py", "run_test_server"]
    js_test_file = "app/static/compiled-js/tests/browser.js"
    casper_command = ["casperjs", "test", js_test_file]
    server = subprocess.Popen(server_command, stderr=subprocess.PIPE)
    # TODO: If we don't get this line we should  be able to detect that
    # and avoid the starting casper process.
    for line in server.stderr:
        if line.startswith(b' * Running on'):
            break
    casper = subprocess.Popen(casper_command)
    casper.wait(timeout=60)
    server.wait(timeout=60)
    if not nocoverage:
        os.system("coverage report -m")
        os.system("coverage html")

@manager.command
def test_main():
    """Run the python only tests defined within app/main.py"""
    return run_command("py.test app/main.py")


@manager.command
def test():
    casper_result = test_casper()
    main_result = test_main()
    return max([casper_result, main_result])


@manager.command
def run_test_server():
    """Used by the phantomjs tests to run a live testing server"""
    # running the server in debug mode during testing fails for some reason
    application.config['DEBUG'] = True
    application.config['TESTING'] = True
    port = application.config['LIVE_SERVER_PORT']
    application.run(port=port, use_reloader=False, threaded=True)

if __name__ == "__main__":
    manager.run()
