import csv
import os

from model.data_source import DataError, DataSource


def load_csv(path):
    """Reads a CSV file, turns into a DataSource.
    raises DataError with a message that can be shown to the user.
    """
    name = os.path.basename(path)

    try:
        #utf-8-sig removes the byte order mark which some exports can add
        with open(path, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            originals = reader.fieldnames
            raw_rows = list(reader)
    except FileNotFoundError:
        raise DataError(f"File not found: {name}") from None
    except UnicodeDecodeError:
        raise DataError(f"{name} is not a readable CSV text file.") from None
    except csv.Error:
        raise DataError(f"{name} is not a valid CSV file.") from None
    except OSError:
        raise DataError(f"Could not read {name}.") from None

    if not originals:
        raise DataError(f"{name} is empty.")
    if not raw_rows:
        raise DataError(f"{name} has a header but no data rows.")

    columns = [column.strip() for column in originals]
    #a row that is shorter than the header comes back with None, so it gets made blank
    rows = [
        {column: (raw.get(original) or "").strip()
         for column, original in zip(columns, originals)}
        for raw in raw_rows
    ]
    return DataSource(name, columns, rows)