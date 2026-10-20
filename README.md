# La Liga 2024/25 Data Engineering

A MySQL database of La Liga 2024/25 data (clubs, players, goalkeepers, outfield players, coaches, fans and matches), built and queried from Python. Includes SQL queries for the league table, top scorers, goalkeeper saves, nationality split, coach nationalities and fan support, plotted with Plotly.

## Files

- `CW.py`: creates the schema and triggers, loads the CSVs and runs the queries.
- `*.csv`: source data.

## Running

Install `mysql-connector-python` and `plotly`, start MySQL locally, then run `python CW.py`.
