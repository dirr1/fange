# Prediction Market Aggregator

Track and aggregate probabilities from multiple prediction markets using this command-line tool.

## Supported Platforms & Accuracy Weights

This tool aggregates data from the following platforms using historical directional accuracy coefficients:

| Platform | Accuracy Weight | Description |
| :--- | :--- | :--- |
| **PredictIt** | 93% | Highest accuracy among political markets. |
| **ForecastEx** | 90% | Institutional gold standard for economic data. |
| **Manifold Markets** | 87% | High performance on tech and sports events. |
| **Kalshi** | 78% | Regulated US market for economics and politics. |
| **Robinhood** | 78% | Consumer hub (routes political/economic trades to Kalshi). |
| **Polymarket** | 67% | High speed and volume, though with higher "noise" on niche contracts. |

## Features

- **Unified Search**: Search for topics across 6+ prediction markets simultaneously.
- **Weighted Aggregation**:
  - **Accuracy-Weighted**: Uses the coefficients above to provide a reliable "wisdom of the crowd" probability.
  - **Simple Average**: Mean of all matching market probabilities.
  - **Liquidity-Weighted**: Weighted by trading volume where available.
- **Real-time Tracking**: Monitor specific queries and get notified via Discord webhooks when probabilities change by >1%.
- **Environment Support**: Manage sensitive URLs and API keys using `.env`.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the root directory:
   ```env
   DISCORD_WEBHOOK_URL=your_discord_webhook_url
   # Optional API keys for higher rate limits
   KALSHI_KEY_ID=your_id
   KALSHI_KEY_SECRET=your_secret
   POLYMARKET_API_KEY=your_key
   ```

## Usage

### Search and Aggregate

Search for a query across all supported platforms and see aggregated probabilities:

```bash
python cli.py search "Iran strikes"
```

### Real-time Tracking

Start a background tracking process that polls markets and sends updates to Discord:

```bash
python cli.py track "Trump wins 2024" --interval 60
```

*Note: If `DISCORD_WEBHOOK_URL` is set in `.env`, the `--webhook` argument is optional.*

## Project Structure

- `cli.py`: Main entry point for the CLI tool.
- `fetcher.py`: Handles data retrieval from all integrated platforms.
- `aggregator.py`: Logic for keyword matching and probability aggregation using accuracy weights.
- `tracker.py`: Real-time monitoring and Discord notification logic.
