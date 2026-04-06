"""Plonky Forecasting MCP Server.

Connects AI agents to Plonky's forecasting and backtesting API.
Install: pip install -r requirements.txt
Run:     python server.py            (stdio transport — for Claude Desktop, Cursor, etc.)
         fastmcp run server.py       (SSE transport — for web clients)

Configuration via environment variables:
  PLONKY_API_KEY  — your Plonky API key (plk_...)
  PLONKY_API_URL  — API base URL (default: https://forecastingbase.onrender.com/api/v1)

The API key is resolved in order: PLONKY_API_KEY env var > ~/.plonky/api_key file.
On first registration the key is saved to ~/.plonky/api_key automatically.
"""

import os
import time
from pathlib import Path
from typing import Annotated, Optional

import httpx
from fastmcp import FastMCP

API_URL = os.environ.get("PLONKY_API_URL", "https://forecastingbase.onrender.com/api/v1")
POLL_INTERVAL = 2
MAX_POLLS = 150

KEY_FILE = Path.home() / ".plonky" / "api_key"


def _load_api_key() -> str:
    """Load API key from env var or persisted key file."""
    env_key = os.environ.get("PLONKY_API_KEY", "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        stored = KEY_FILE.read_text().strip()
        if stored:
            return stored
    return ""


def _save_api_key(key: str) -> None:
    """Persist API key to ~/.plonky/api_key for future runs."""
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(key)


API_KEY = _load_api_key()

mcp = FastMCP(
    name="Plonky Forecasting",
    description="Run time-series forecasts and backtests via the Plonky API",
)


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _get(path: str, params: dict | None = None) -> dict:
    resp = httpx.get(f"{API_URL}{path}", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json: dict | None = None) -> dict:
    resp = httpx.post(f"{API_URL}{path}", headers=_headers(), json=json, timeout=30)
    if resp.status_code == 402:
        data = resp.json()
        detail = data if isinstance(data, dict) else {"detail": data}
        return {"error": "insufficient_credits", **detail}
    resp.raise_for_status()
    return resp.json()


def _delete(path: str) -> dict:
    resp = httpx.delete(f"{API_URL}{path}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _poll_job(job_id: int) -> dict:
    """Poll a forecast job until completion or failure."""
    for _ in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        data = _get(f"/jobs/{job_id}", params={"format": "summary"})
        if data.get("status") == "completed":
            return data
        if data.get("status") == "failed":
            return {"error": data.get("error_message", "Forecast failed")}
    return {"error": f"Forecast timed out after {MAX_POLLS * POLL_INTERVAL}s"}


def _poll_backtest(backtest_id: int) -> dict:
    """Poll a backtest job until completion or failure."""
    for _ in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        data = _get(f"/backtests/{backtest_id}")
        if data.get("status") == "completed":
            return data
        if data.get("status") == "failed":
            return {"error": data.get("error_message", "Backtest failed")}
    return {"error": f"Backtest timed out after {MAX_POLLS * POLL_INTERVAL}s"}


def _format_forecast_table(forecast: list[dict], max_rows: int = 20) -> str:
    """Format forecast data as a readable markdown table."""
    if not forecast:
        return "No forecast data."
    rows = forecast[:max_rows]
    lines = ["| Date | Forecast | Lower | Upper |", "|------|----------|-------|-------|"]
    for pt in rows:
        ds = str(pt.get("ds", ""))[:10]
        yhat = f"{pt.get('yhat', 0):.2f}"
        lo = f"{pt.get('yhat_lower', 0):.2f}"
        hi = f"{pt.get('yhat_upper', 0):.2f}"
        lines.append(f"| {ds} | {yhat} | {lo} | {hi} |")
    if len(forecast) > max_rows:
        lines.append(f"\n*Showing {max_rows} of {len(forecast)} forecast periods.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool
def register(
    email: Annotated[str, "Email address for the new Plonky account"],
) -> str:
    """Create a new Plonky account and get an API key. If already authenticated,
    returns the current balance instead of creating a duplicate account. The human
    can later claim the account by using 'Forgot Password' at the login page."""
    global API_KEY
    if API_KEY:
        try:
            data = _get("/credits/balance")
            balance = data.get("balance", "?")
            return (
                f"Already authenticated. Credits: {balance}. "
                "No need to register again. Use get_credits for details."
            )
        except httpx.HTTPStatusError:
            pass  # key is stale/revoked — fall through to registration

    data = _post("/agent/register", {"email": email})
    if "error" in data:
        return f"Registration failed: {data.get('detail', data['error'])}"

    API_KEY = data["api_key"]
    _save_api_key(API_KEY)

    return (
        f"Account created for {data['email']}.\n"
        f"API Key: {data['api_key']}\n"
        f"Credits: {data['credits']}\n"
        f"Login URL: {data['login_url']}\n"
        f"{data['message']}"
    )


@mcp.tool
def get_credits() -> str:
    """Check the current credit balance."""
    data = _get("/credits/balance")
    total = data.get("balance", 0)
    sub = data.get("subscription_credits", 0)
    purchased = data.get("purchased_credits", 0)
    return f"Credits: {total} total ({sub} subscription + {purchased} purchased)\nTop up at https://plonky.ai/billing"


@mcp.tool
def upload_data(
    csv_text: Annotated[str, "CSV data as a string (with headers in the first row)"],
    filename: Annotated[str, "Filename for the upload (e.g. 'sales.csv')"] = "data.csv",
) -> str:
    """Upload CSV data to Plonky. Returns the dataset ID and detected columns."""
    resp = httpx.post(
        f"{API_URL}/datasets/upload-from-paste",
        headers=_headers(),
        json={"filename": filename, "content": csv_text},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    ds_id = data.get("id")
    cols = data.get("columns", [])
    rows = data.get("row_count", "?")
    return (
        f"Dataset uploaded: ID={ds_id}, {rows} rows, columns: {', '.join(cols)}\n"
        f"View at: https://plonky.ai/forecast/{ds_id}"
    )


@mcp.tool
def list_datasets() -> str:
    """List all uploaded datasets."""
    datasets = _get("/datasets/")
    if not datasets:
        return "No datasets found. Upload data first with upload_data."
    lines = ["| ID | Name | Rows | Created |", "|----|------|------|---------|"]
    for ds in datasets[:20]:
        name = ds.get("original_filename", ds.get("name", "?"))
        lines.append(
            f"| {ds['id']} | {name} | {ds.get('row_count', '?')} | {str(ds.get('created_at', ''))[:10]} |"
        )
    return "\n".join(lines)


@mcp.tool
def analyze_dataset(
    dataset_id: Annotated[int, "Dataset ID to analyze"],
) -> str:
    """Get quick analysis of a dataset — summary stats, data quality, column info."""
    data = _get(f"/datasets/{dataset_id}/quick-analysis")
    parts = [f"**Dataset {dataset_id} Analysis**\n"]
    if "summary" in data:
        parts.append(str(data["summary"]))
    if "quality_issues" in data:
        issues = data["quality_issues"]
        if issues:
            parts.append(f"\nQuality issues: {', '.join(str(i) for i in issues)}")
        else:
            parts.append("\nNo quality issues detected.")
    return "\n".join(parts)


@mcp.tool
def create_forecast(
    dataset_id: Annotated[int, "Dataset ID to forecast"],
    date_column: Annotated[str, "Name of the date column"],
    value_column: Annotated[str, "Name of the value column to forecast"],
    periods: Annotated[int, "Number of future periods to forecast"] = 90,
    weekly_seasonality: Annotated[bool, "Enable weekly seasonality"] = True,
    yearly_seasonality: Annotated[bool, "Enable yearly seasonality"] = True,
    use_holidays: Annotated[bool, "Include US holiday effects"] = True,
    name: Annotated[Optional[str], "Name for this forecast"] = None,
) -> str:
    """Create a time-series forecast. Polls until complete and returns results."""
    payload = {
        "dataset_id": dataset_id,
        "value_column": value_column,
        "periods": periods,
        "forecast_config": {
            "seasonality": {
                "weekly": weekly_seasonality,
                "yearly": yearly_seasonality,
            },
            "use_us_holidays": use_holidays,
        },
    }
    if name:
        payload["name"] = name

    result = _post("/jobs/", payload)
    if "error" in result:
        return f"Failed to create forecast: {result}"

    job_id = result["id"]
    data = _poll_job(job_id)
    if "error" in data:
        return f"Forecast failed: {data['error']}"

    forecast = data.get("result", {}).get("forecast", [])
    table = _format_forecast_table(forecast)
    view_url = f"https://plonky.ai/forecast/{dataset_id}"

    return (
        f"**Forecast complete** (job {job_id})\n"
        f"Periods: {len(forecast)} | Column: {value_column}\n\n"
        f"{table}\n\n"
        f"View full details: {view_url}"
    )


@mcp.tool
def get_forecast(
    job_id: Annotated[int, "Forecast job ID"],
    format: Annotated[str, "Result format: 'full' or 'summary'"] = "summary",
) -> str:
    """Get results for an existing forecast job."""
    data = _get(f"/jobs/{job_id}", params={"format": format})
    if data.get("status") != "completed":
        return f"Job {job_id} status: {data.get('status', 'unknown')}. Error: {data.get('error_message', 'none')}"

    forecast = (data.get("result") or {}).get("forecast", [])
    table = _format_forecast_table(forecast)
    return f"**Forecast {job_id}** — {data.get('value_column', '?')}\n\n{table}"


VALID_PERIOD_TYPES = ("days", "weeks", "months", "quarters", "years")


@mcp.tool
def create_backtest(
    forecast_job_id: Annotated[int, "Forecast job ID to backtest"],
    period_count: Annotated[int, "Number of periods to hold out (e.g. 3 for 'last 3 months')"] = 3,
    period_type: Annotated[str, "Period granularity: days, weeks, months, quarters, or years"] = "months",
) -> str:
    """Run a backtest on a completed forecast to evaluate accuracy.

    Tests how well the model would have predicted the most recent data by
    hiding it and comparing predictions to actuals.  Polls until complete.

    Choosing settings:
      - daily data   → period_type='weeks' or 'months', period_count=3-6
      - weekly data  → period_type='months', period_count=3-6
      - monthly data → period_type='months', period_count=3-6

    Cost: dimensions × period_count credits.
    """
    if period_type not in VALID_PERIOD_TYPES:
        return (
            f"Invalid period_type '{period_type}'. "
            f"Must be one of: {', '.join(VALID_PERIOD_TYPES)}"
        )

    result = _post("/backtests/", {
        "forecast_job_id": forecast_job_id,
        "period_count": period_count,
        "period_type": period_type,
    })
    if "error" in result:
        return f"Failed to create backtest: {result}"

    bt_id = result["id"]
    data = _poll_backtest(bt_id)
    if "error" in data:
        return f"Backtest failed: {data['error']}"

    metrics = data.get("metrics", data.get("result", {}))
    parts = [f"**Backtest {bt_id}** (forecast job {forecast_job_id}, {period_count} {period_type})\n"]
    if isinstance(metrics, dict):
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                parts.append(f"- {k}: {v:.4f}")
            else:
                parts.append(f"- {k}: {v}")
    else:
        parts.append(str(metrics))
    return "\n".join(parts)


@mcp.tool
def create_forecast_batch(
    dataset_id: Annotated[int, "Dataset ID"],
    date_column: Annotated[str, "Date column name"],
    value_column: Annotated[str, "Value column to forecast"],
    dimension_column: Annotated[str, "Column to split by (e.g. 'region', 'product')"],
    dimension_values: Annotated[list[str], "Values to forecast (e.g. ['US', 'UK', 'DE'])"],
    periods: Annotated[int, "Forecast periods"] = 90,
    include_aggregate: Annotated[bool, "Also create an aggregate (total) forecast"] = True,
) -> str:
    """Create forecasts for multiple dimension values in one batch."""
    combinations = []
    if include_aggregate:
        combinations.append({"dimension_values": None})
    for val in dimension_values:
        combinations.append({"dimension_values": {dimension_column: val}})

    payload = {
        "dataset_id": dataset_id,
        "value_column": value_column,
        "periods": periods,
        "combinations": combinations,
    }

    result = _post("/jobs/batch", payload)
    if "error" in result:
        return f"Failed to create batch: {result}"

    batch_id = result.get("batch_id", "?")
    job_count = result.get("job_count", len(combinations))
    return (
        f"Batch created: {job_count} forecasts (batch_id={batch_id})\n"
        f"Dimensions: {', '.join(dimension_values)}"
        + (" + aggregate" if include_aggregate else "")
        + f"\nView at: https://plonky.ai/forecast/{dataset_id}"
    )


if __name__ == "__main__":
    mcp.run()
