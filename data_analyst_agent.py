#!/usr/bin/env python3
"""
Data Analyst Agent
Turns plain-English questions into SQL queries and generates charts.
Works with SQLite databases.

Usage:
    python data_analyst_agent.py --db ./data.db --question "What are total sales by region?"
    python data_analyst_agent.py --db ./data.db --list-tables
"""

import os
import sys
import json
import argparse
import sqlite3
import re
from pathlib import Path
from datetime import datetime


class DataAnalystAgent:
    """Translates natural language to SQL and executes it."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.schema = {}

    def get_schema(self):
        """Extract database schema."""
        if not self.db_path.exists():
            return {"error": f"Database not found: {self.db_path}"}

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        schema = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]
            schema[table] = {"columns": columns, "row_count": row_count}

        conn.close()
        self.schema = schema
        return schema

    def list_tables(self):
        """Return list of tables."""
        schema = self.get_schema()
        if "error" in schema:
            return schema
        return {"tables": list(schema.keys()), "schema": schema}

    def nl_to_sql(self, question):
        """Convert natural language to SQL (rule-based)."""
        question_lower = question.lower()
        schema = self.get_schema()

        if "error" in schema:
            return {"error": schema["error"]}

        tables = list(schema.keys())
        if not tables:
            return {"error": "No tables found in database"}

        # Detect aggregation
        agg_map = {
            "total": "SUM", "sum": "SUM", "average": "AVG", "avg": "AVG",
            "count": "COUNT", "max": "MAX", "min": "MIN"
        }

        # Detect table mentioned in question
        target_table = None
        for table in tables:
            if table.lower() in question_lower:
                target_table = table
                break

        if not target_table:
            target_table = tables[0]  # default to first table

        table_info = schema[target_table]
        columns = [c["name"] for c in table_info["columns"]]

        # Detect column mentioned — prefer columns that appear with aggregation context
        target_column = None
        # First pass: look for column near aggregation words
        for keyword in agg_map:
            if keyword in question_lower:
                # Find words near the aggregation keyword
                words = question_lower.split()
                for i, w in enumerate(words):
                    if w == keyword:
                        # Check nearby words for column names
                        for j in range(max(0, i-3), min(len(words), i+4)):
                            for col in columns:
                                if col.lower() == words[j]:
                                    target_column = col
                                    break
                            if target_column:
                                break
                    if target_column:
                        break
            if target_column:
                break

        # Second pass: any column mentioned in question
        if not target_column:
            for col in columns:
                if col.lower() in question_lower:
                    target_column = col
                    break

        # Build SQL
        sql_parts = ["SELECT"]

        # Check for aggregation
        agg_func = None
        for keyword, func in agg_map.items():
            if keyword in question_lower:
                agg_func = func
                break

        if agg_func and target_column:
            sql_parts.append(f"{agg_func}({target_column}) AS {agg_func.lower()}_{target_column}")
        elif target_column:
            sql_parts.append(target_column)
        else:
            sql_parts.append("*")

        sql_parts.append(f"FROM {target_table}")

        # Check for GROUP BY — look for "by <column>" pattern
        group_col = None
        by_match = re.search(r'\bby\s+(\w+)', question_lower)
        if by_match:
            by_word = by_match.group(1)
            for col in columns:
                if col.lower() == by_word:
                    group_col = col
                    break
        if group_col:
            sql_parts.append(f"GROUP BY {group_col}")

        # Check for ORDER BY / LIMIT
        if "top" in question_lower or "highest" in question_lower:
            order_col = target_column or columns[0]
            sql_parts.append(f"ORDER BY {order_col} DESC")
            sql_parts.append("LIMIT 10")

        sql = " ".join(sql_parts) + ";"

        return {
            "sql": sql,
            "table": target_table,
            "aggregation": agg_func,
            "target_column": target_column,
            "question": question
        }

    def execute_sql(self, sql):
        """Execute SQL and return results."""
        if not self.db_path.exists():
            return {"error": f"Database not found: {self.db_path}"}

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(sql)
            rows = [dict(row) for row in cursor.fetchall()]
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "sql": sql
            }
        except Exception as e:
            conn.close()
            return {"error": str(e), "sql": sql}

    def generate_chart_spec(self, sql_result, chart_type="bar"):
        """Generate a chart specification (for frontend rendering)."""
        if "error" in sql_result:
            return {"error": sql_result["error"]}

        columns = sql_result["columns"]
        rows = sql_result["rows"]

        if len(columns) < 2:
            return {"error": "Need at least 2 columns for a chart"}

        x_col = columns[0]
        y_col = columns[1]

        chart = {
            "type": chart_type,
            "title": f"{y_col} by {x_col}",
            "xAxis": x_col,
            "yAxis": y_col,
            "data": [
                {x_col: row[x_col], y_col: row[y_col]} for row in rows[:20]
            ],
            "generated_at": datetime.now().isoformat()
        }
        return chart

    def analyze(self, question, chart_type="bar"):
        """Full pipeline: NL → SQL → Execute → Chart."""
        # Convert to SQL
        sql_result = self.nl_to_sql(question)
        if "error" in sql_result:
            return sql_result

        # Execute
        execution = self.execute_sql(sql_result["sql"])
        if "error" in execution:
            return execution

        # Generate chart
        chart = self.generate_chart_spec(execution, chart_type)

        return {
            "question": question,
            "sql": sql_result["sql"],
            "results": execution,
            "chart": chart,
            "analyzed_at": datetime.now().isoformat()
        }


def main():
    parser = argparse.ArgumentParser(description="Data Analyst Agent")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--question", help="Natural language question")
    parser.add_argument("--list-tables", action="store_true", help="List all tables")
    parser.add_argument("--chart", default="bar", help="Chart type (bar, line, pie)")
    parser.add_argument("--output", default="analysis_result.json", help="Output file")
    args = parser.parse_args()

    agent = DataAnalystAgent(args.db)

    if args.list_tables:
        tables = agent.list_tables()
        print(json.dumps(tables, indent=2))
        if not args.question:
            return

    if not args.question:
        print("[-] --question is required (unless using --list-tables)")
        return

    result = agent.analyze(args.question, args.chart)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n[+] Question: {args.question}")
    print(f"[+] SQL: {result.get('sql', 'N/A')}")
    if "results" in result:
        print(f"[+] Rows returned: {result['results']['row_count']}")
        print(f"[+] Chart: {result['chart']['type']} — {result['chart']['title']}")
    print(f"[+] Full result saved to {args.output}")


if __name__ == "__main__":
    main()