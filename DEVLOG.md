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

## 10/11/2026
Made a csv loader (data/csv_loader.py) that reads a CSV into a DataSource and raises DataError with a message that can be shown to a user. Errors could be for missing files, empty files, binary files, header only files, etc.
Made model/data_source.py which is the layer for preparing charts. It automatically detects X/Y/series columns, does number validation, label sorting, and converts rows in data ready to be plotted. Supports grouping data in multiple series, tracks skipped rows, maps X axis labels to number positions for good plotting. Made generator for chart descriptions which summarise the data, plotted variable, series and range of values. Made an append method which lets one data source be added to another. 

## 11/11/2026
Made model/view_window.py which manages the charts visible stuff using four coordinate numbers. it also handles zooming and panning, keeping the view in the data range. It also allows resetting to the original view.
Made model/explorer.py which managed the state of a single DES. It keeps track of the loaded data source, the chart generated, and the visible chart area. It handles loading a new data source, appending more data and zooming, panning, resetting the chart. When loading or appending, it builds the chart and state before replacing the one thats already there. This means if something goes wrong the data that is already there is preserved.

## 12/11/2026
Made tests/test_local_mode.py which has all the test functions for local mode, covers tests for everything that was added with csv_loader.py, data_source.py, view_window.py and explorer.py.
these tests were imported into test_runner.py so all tests can be run at once. 

## 13/11/2026
made zoom and pan for x only and y changes to fit the data when zoomed. This is because zooming into certain places could leave the user in a blank part of the graph and they could get lost. This stops that from ever happening.

Added local des window, controller and chart drawing. 
view/chart_drawing.py draws the charts and the placeholder on a matplotlib figure.
view/des_view.py is a freesimplegui window with the embedded chart and zoom, pan, reset, change source and append source controls, with a status line and description.
controller/des_controller turns button presses into actions for the explorer. each DataError becomes a message instead of a crash, including bad files.
tests/test_des added 22 more tests for the des using a fake window.

Moved test database helper to tests/helpers.py. made the BrokenDatabase always fail. 
Added sessions model, sessions repository, session management screen.
DatabaseManager has find_many, delete_one_by_id, invalid ids are treated as not found. 
Session model and SessionRepository, names are trimmed, have to be unique for each owner (cant have 2 sessions named the same thing).
Sessions DES has create, join, refresh, delete, logout buttons.
new sessions can be marked as private.
jdatabase failures lead to a plain message.
app.py remote goes to login screen, then sessions. logout returns back to login. join opens the global chat unless a DES exists which it doesnt yet.
added 29 more tests for all of this.

## 14/11/2026
Its 2am. my head hurts.
Added per session chat which handles outages and cascade deletion.
added things to make this work as below
MessageRepository: messages belong to a session. blank messages not allowed. over 500 char messages not allowed. 
ChatFeed: windowless chat logic that the remote DES can reuse.
ChatController: redraws only when changes happen. Shows status during database loss of access and clears it when access is back. Keeps the users text in the text box if sending fails.
added more tests and a switchable "database" that can be turned on and off.

## 15/11/2026
Multiple DES need to be running in parallel. But FreeSimpleGUI isnt thread safe. Because of this, one loop on the main thread runs every window (WindowManager.) Slower work runs on "worker" thread. Workers never do anything with widgets. Workers post their result back to the window (write_event_value) and the main thread applies it. The session screen now doesnt block, so it can be used while DES windows are open.

Next i need to update the readme, make everything pep8 compliant with autopep8 and do the devlog reflection