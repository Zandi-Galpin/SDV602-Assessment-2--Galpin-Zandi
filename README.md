# SDV602-Assessment-2--Galpin-Zandi

# Data Explorer

The Data Explorer is a desktop application for
exploring data as interactive charts. There are 2 modes.

- **Local mode:** load CSV file(s) from disk and view them in a Data Explorer Screen (DES). You can zoom in and out, pan left and right, add more data to the file you have open, change to a different file, and there is a short description of the data under the chart.
- **Remote mode:** log in (or register) with an account. You can then see a list of public sessions, join one, create a new one (public or private) or delete one you made. Each session has its own shared chart, live chat and data. Uploading a CSV saves it in MongoDB and everyone in that session sees it. You can have more than one session open at once.

## Requirements

- Python 3.x 
- MongoDB Community Server, for remote mode and the database tests.
  The default address is `mongodb://localhost:27017`.
- Git

## Setup

1. Clone the repository
2. Create a virtual environment using "python -m venv .venv"

3. Activate it with any of the following depending on the system you are using:

   - Git Bash (Windows): `source .venv/Scripts/activate`
   - PowerShell: `.venv\Scripts\Activate.ps1`
   - CMD: `.venv\Scripts\activate.bat`
   - Mac/Linux: `source .venv/bin/activate`

4. Install the dependencies using "pip install -r requirements.txt"

## Running

A mode is required:

```
python app.py local [--file samples/example.csv]
python app.py remote [--uri MONGO_URI] [--db DATABASE_NAME]
python app.py test [--fullinfo]
```


`local` opens the DES for CSV files on disk. `--file` opens a file on start.

`remote` runs login and registration against MongoDB. `--uri` and `--db` override the server and database in case the ones you use are different to that described above.

`test` runs the headless tests with no windows. Exits with 0 if all pass, 1 otherwise. `--fullinfo` lists passing tests too.

To try remote mode with 2 users, open 2 terminals and run
`python app.py remote` in both, then log in as different accounts. One person creates a session, both of you join it, and then uploading a file in one window shows up in the other one.

## Configuration

- The server address comes from the `MONGO_URI` environment variable, or
  `--uri` in the command line. The default is `mongodb://localhost:27017`.
- The database name is `SDV602_assessment_2_database`. Use `--db`
  to change it if yours is different for whatever reason. 

## Tests

The tests dont open windows. Tests that use the database run against a
separate database called `SDV602_test_database`, this is wiped before each
test, If MongoDB is not running, the database tests have errors and the other tests still run. the errors are caught

## Project structure

`app.py` is the entry point and the command line modes
`config.py` is the "settings" (server address, database and collection names)
`controller/` connects the windows to the data and models (window_manager.py runs every window, background.py runs slow work on threads)
`data/` has database access
`model/` has plain classes with no gui or database code
`view/` has FreeSimpleGUI windows and chart drawing
`tests/` has headless test runner and tests
`samples/` has sample csv files
`DEVLOG.md` has the development log

## How remote mode works

After logging in you get the session screen. Joining a session opens a DES window with the chart on the left and the live chat on the right. Uploading or appending a CSV saves it in MongoDB as that sessions data source. Every window in the session checks for new chat messages and a new data source roughly once each second, so changes show up for everyone without them clicking anything. Deleting a session also deletes its chat and data. Multiple windows can be open and work at the same time (threads).
