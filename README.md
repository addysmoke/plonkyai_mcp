# Plonky Forecasting MCP Server

Connect AI agents to [Plonky](https://plonky.ai) for time-series forecasting and backtesting.

## Setup

```bash
pip install -r requirements.txt
```

## Configuration

Set your API key as an environment variable:

```bash
export PLONKY_API_KEY="plk_your_key_here"
```

Don't have a key? The `register` tool can create an account and return one, or sign up at [plonky.ai](https://plonky.ai) and generate a key in Settings.

### Automatic key persistence

If no `PLONKY_API_KEY` env var is set, the server checks `~/.plonky/api_key`. When you register through the `register` tool, the key is saved there automatically so subsequent runs reuse the same account. To reset, delete the file:

```bash
rm ~/.plonky/api_key
```

## Usage

### Claude Desktop / Cursor

Add to your MCP config (`claude_desktop_config.json` or Cursor settings):

```json
{
  "mcpServers": {
    "plonky": {
      "command": "python",
      "args": ["/path/to/mcp-server/server.py"],
      "env": {
        "PLONKY_API_KEY": "plk_your_key_here"
      }
    }
  }
}
```

### Direct

```bash
python server.py
```

## Available Tools

| Tool | Description |
|------|-------------|
| `register` | Create a Plonky account and get an API key |
| `get_credits` | Check credit balance |
| `upload_data` | Upload CSV data |
| `list_datasets` | List uploaded datasets |
| `analyze_dataset` | Get summary stats and data quality info |
| `create_forecast` | Run a forecast (polls until complete) |
| `get_forecast` | Get results for an existing forecast |
| `create_backtest` | Backtest a forecast for accuracy metrics |
| `create_forecast_batch` | Forecast multiple dimensions at once |

## Credits

Each forecast costs 1 credit. Backtests cost dimensions × period_count credits. New accounts start with 50 credits. Top up at [plonky.ai/billing](https://plonky.ai/billing) for $0.33/credit.
