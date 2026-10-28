## 19/10/2026
Initial commit. Imported initial files from practice. Set up virtual environment.

## 21/10/2026
Updated initial files to session 22 files. This is the proper starting point. Then fixed an issues in create_user using the wrong variable. Wrapped pymongo errors in DatabaseError, added a connection timeout, and added AuthError with specific error messages for login/registration with validation. 

## 26/10/2026
Changed LoginController and RegisterController so they can have an optional view so tests can pass a fake instead of opening a window
UserRepository now can take a db, and passwords over 72bytes give an error message now instead of crashing.
Changed app.py so it now has argparse for local, remote and test modes, along with extra things like specifying uri and db for remote, or specifying full info for test mode. Will set up the tests fully before committing.

## 28/10/2026
Finished making tests/fakes.py and tests/test_runner.py
Database tests use their own test database, and the wipe function doesnt run if the name isn't the test database, so a mistake can't delete the real data in the real database. 
test runner returns {passed, failed, errors} for 14 tests which are for auth, controllers and the CLI parser itself