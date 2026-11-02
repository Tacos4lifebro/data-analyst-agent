# data-analyst-agent

Natural language to SQL + charts.

Ask a plain-English question about a SQLite database and get back the SQL query, the result set, and (when the result is chartable) a quick visualization. Built to show the full loop: schema introspection → NL-to-SQL translation → safe execution → presentation.

## How it works

1. **Schema introspection** — reads table names, columns, and types directly from the SQLite file so the agent always grounds its query in the real schema, not a guess.
2. **NL → SQL** — maps the question against the schema to produce a query (pluggable: swap in an LLM call for production use; ships with a deterministic rule-based translator so it runs with zero API keys).
3. **Safe execution** — read-only connection, parameterized queries, rejects anything that isn't a `SELECT`.
4. **Output** — prints the result table and, when it detects a groupable numeric column, renders a chart.

## Usage

```bash
pip install -r requirements.txt
python data_analyst_agent.py --db ./data.db --list-tables
python data_analyst_agent.py --db ./data.db --question "What are total sales by region?"
```

## Why this exists

Most "chat with your data" demos hide the SQL. This one shows it, so a reviewer can see exactly what the agent decided to run and why — the part that actually matters for trusting an agent near a production database.

## Stack

Python · SQLite · matplotlib (optional, for charts)
