# SDV602-Assessment-2--Galpin-Zandi

# Data Explorer

The Data Explorer is a desktop application for
exploring data as interactive charts. There are 2 modes.

- **Local mode:** load CSV file(s) from disk and view them in a Data Explorer
  Screen (DES).
- **Remote mode:** log in with an account, with data and chat stored in
  MongoDB.

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
python app.py test [--verbose]
```


`local` opens the DES for CSV files on disk. `--file` opens a file on start.
`remote` runs login and registration against MongoDB. `--uri` and `--db` override the server and database in case the ones you use are different to that described above.
`test` runs the headless tests with no windows. Exits with 0 if all pass, 1 otherwise. `--fullinfo` lists passing tests too.

## Configuration

- The server address comes from the `MONGO_URI` environment variable, or
  `--uri` in the command line. The default is `mongodb://localhost:27017`.
- The database name is `SDV602_assessment_2_database`. Use `--db`
  to change it if yours is different for whatever reason. 

## Tests

The tests dont open windows. Tests that use the database run against a
separate database called `SDV602_test_database`, this is wiped before each
test, If MongoDB is not running, the database tests have errors and the other tests still run. the errors are caught
