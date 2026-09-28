import duckdb
import pandas as pd
import anthropic
import os
import re
import plotly.express as px

# ---- Load data ----
for enc in ['utf-8', 'latin-1', 'cp1252']:
    try:
        df = pd.read_csv('sales.csv', encoding=enc)
        break
    except UnicodeDecodeError:
        continue

# Convert date columns from text to real dates (file uses DD-MM-YYYY)
for col in df.columns:
    if 'date' in col.lower():
        df[col] = pd.to_datetime(df[col], dayfirst=True)

con = duckdb.connect()
con.register('sales', df)

# ---- Build schema description for the prompt ----
schema_df = con.execute("DESCRIBE sales").fetchdf()
schema_text = "\n".join(
    f"- {row['column_name']} ({row['column_type']})"
    for _, row in schema_df.iterrows()
)

# ---- Claude client ----
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# =====================================================
# GUARDRAIL 1: SQL validation
# =====================================================
FORBIDDEN_KEYWORDS = [
    'drop', 'delete', 'insert', 'update', 'alter', 'create', 'truncate',
    'attach', 'detach', 'copy', 'pragma', 'export', 'import', 'install',
    'load', 'call', 'set', 'read_csv', 'read_csv_auto', 'read_parquet',
    'read_json', 'read_text', 'glob'
]

def validate_sql(sql):
    # Clean up stray markdown fences or trailing semicolon
    sql = sql.replace("```sql", "").replace("```", "").strip().rstrip(";").strip()
    lowered = sql.lower()

    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Blocked: query must start with SELECT (or WITH)")

    if ";" in sql:
        raise ValueError("Blocked: multiple statements are not allowed")

    for word in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{word}\b", lowered):
            raise ValueError(f"Blocked: query contains forbidden keyword '{word}'")

    return sql


# ---- Step 1: question -> SQL (with optional retry context) ----
def question_to_sql(question, previous_sql=None, error=None):
    prompt = f"""You are a SQL expert. Given this table schema for a table called "sales":

{schema_text}

Write a single SQL query (DuckDB syntax) that answers this question:
"{question}"

Rules:
- Return ONLY the SQL query, nothing else
- No explanations, no markdown code fences, no backticks
- Query must start with SELECT (or WITH)
- Wrap every column name in double quotes, e.g. "Order Date", "Sub-Category"
"""
    if previous_sql and error:
        prompt += f"""
Your previous attempt failed.
Previous query:
{previous_sql}

Error message:
{error}

Write a corrected query that fixes this error.
"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


# =====================================================
# GUARDRAIL 2: retry once on failure
# =====================================================
def get_valid_result(question):
    sql = question_to_sql(question)

    for attempt in range(2):
        try:
            sql = validate_sql(sql)
            result = con.execute(sql).fetchdf()
            return sql, result
        except Exception as e:
            if attempt == 1:
                raise  # second failure: give up and let the caller handle it
            print(f"\n(Attempt 1 failed: {e}\n Retrying with the error message...)")
            sql = question_to_sql(question, previous_sql=sql, error=str(e))


# ---- Step 2: result -> plain-English explanation ----
def explain_result(question, sql, result_df):
    result_text = result_df.to_string(index=False)

    prompt = f"""You are a data analyst. A user asked this question:
"{question}"

This SQL query was run to answer it:
{sql}

Here is the result:
{result_text}

In 2-3 sentences, explain what this result means in plain English.
Mention the biggest/most important number or driver.
End with one brief, actionable suggestion based on this finding.
Do not just repeat the numbers - interpret them.
Only cite numbers that appear in the result or are directly calculated from it.
Use plain text only: no markdown, no headers, no bold.
"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


# =====================================================
# GUARDRAIL 3: check numbers in the explanation
# =====================================================
def extract_numbers(text):
    numbers = []
    pattern = r'(\d[\d,]*\.?\d*)\s*(thousand|million|[KkMm])?'
    for match in re.finditer(pattern, text):
        raw = match.group(1).replace(',', '')
        try:
            value = float(raw)
        except ValueError:
            continue
        suffix = (match.group(2) or '').lower()
        if suffix in ('k', 'thousand'):
            value *= 1_000
        elif suffix in ('m', 'million'):
            value *= 1_000_000
        numbers.append(value)
    return numbers


def check_explanation(explanation, result_df):
    # Allowed values: every number in the result, plus each value's % share of its column
    allowed = []
    for col in result_df.select_dtypes(include='number').columns:
        values = result_df[col].dropna().tolist()
        allowed.extend(values)
        total = sum(values)
        if total:
            allowed.extend(v / total * 100 for v in values)

    unverified = []
    for value in extract_numbers(explanation):
        # Skip small numbers (ranks, "top 5") and years
        if value <= 10 or 1900 <= value <= 2100:
            continue
        if not any(abs(value - a) <= 0.02 * max(abs(a), 1) for a in allowed):
            unverified.append(value)
    return unverified


# ---- Step 3: result -> chart ----

def generate_chart(result_df, question):

    if len(result_df) <= 1:
        print("\n(Result is a single value - no chart needed)")
        return None

    columns = result_df.columns.tolist()
    date_cols = [
        c for c in columns
        if any(w in c.lower() for w in ('date', 'month', 'year'))
        or pd.api.types.is_datetime64_any_dtype(result_df[c])
    ]
    numeric_cols = [
        c for c in result_df.select_dtypes(include='number').columns
        if c not in date_cols
    ]
    non_numeric_cols = [c for c in columns if c not in numeric_cols]

    if date_cols and numeric_cols:
        fig = px.line(result_df, x=date_cols[0], y=numeric_cols[0], title=question)
    elif non_numeric_cols and numeric_cols:
        fig = px.bar(result_df, x=non_numeric_cols[0], y=numeric_cols[0], title=question)
    else:
        print("\n(Could not determine chart type for this result)")
        return None

    safe_name = "".join(c if c.isalnum() else "_" for c in question)[:40]
    chart_path = f"chart_{safe_name}.html"
    fig.write_html(chart_path)
    print(f"\n=== CHART SAVED ===\nOpen {chart_path} in your browser to view it")
    return fig

# ---- Run all test questions from file (only when run directly) ----
if __name__ == "__main__":
    with open('test_questions.txt', 'r') as f:
        questions = [line.strip() for line in f if line.strip()]

    for question in questions:
        print(f"\n{'=' * 60}")
        print(f"QUESTION: {question}")
        print('=' * 60)

        try:
            sql, result = get_valid_result(question)
            print("\n--- SQL ---")
            print(sql)

            print("\n--- RESULT ---")
            print(result)

            explanation = explain_result(question, sql, result)
            print("\n--- EXPLANATION ---")
            print(explanation)

            unverified = check_explanation(explanation, result)
            if unverified:
                print(f"\n!!! WARNING: these numbers in the explanation don't match the data: {unverified}")
            else:
                print("\n(Number check passed: all figures match the query result)")

            generate_chart(result, question)

        except Exception as e:
            print(f"\n!!! ERROR on this question: {e}")