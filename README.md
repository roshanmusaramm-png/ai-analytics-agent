\# AI Analytics Agent



Ask a business question in plain English and get back the SQL, a chart, and a written insight, with guardrails that stop the AI from running unsafe queries or misreporting numbers.



Built on the Superstore sales dataset.



\## How it works



```

Question

&#x20; -> Claude writes SQL (text-to-SQL)

&#x20; -> SQL validation (read-only, no forbidden keywords)

&#x20; -> DuckDB runs the query (one automatic retry if it errors)

&#x20; -> Claude explains the result in plain English

&#x20; -> Number check (figures in the explanation are compared to the result)

&#x20; -> Streamlit shows answer, chart, SQL and raw data

```



\## Features



\- Natural-language questions converted to DuckDB SQL

\- Plain-English insight with one suggested action

\- Automatic chart selection (line for time series, bar for categories)

\- Guardrails: SELECT-only validation, single retry using the error message, and a check that numbers in the explanation match the query result



\## Tech stack



Python, DuckDB, pandas, Anthropic API (Claude), Plotly, Streamlit



\## Run it yourself



1\. Download the Superstore dataset from Kaggle and save it as `sales.csv` in the project folder.

2\. Install dependencies:

```

&#x20;  pip install -r requirements.txt

```

3\. Set your Anthropic API key as an environment variable (Windows Command Prompt):

```

&#x20;  set ANTHROPIC\_API\_KEY=your-key-here

```

4\. Start the app:

```

&#x20;  streamlit run app.py

```



\## Example questions



\- What was total sales by region?

\- Which product category has the highest profit?

\- Show me monthly sales trend over time



\## Limitations



\- The keyword filter is a coarse first defense; the agent also works only on an in-memory copy of the data.

\- The number check can flag correct figures the model calculated itself (for example, a percentage change), so it is a warning, not proof of an error.

\- Built for a single table; multi-table joins are not supported yet.



\## What I learned



\- \[Add 2 or 3 honest lessons here, e.g. dates stored as text made the model guess the wrong format, and converting them to real dates at load time fixed it more reliably than retrying.]

