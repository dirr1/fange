# Prediction Market Aggregator

Track and aggregate probabilities from Polymarket, Kalshi, and PredictIt using this command-line tool.

## Features

- **Unified Search**: Search for topics across multiple prediction markets.
- **Weighted Aggregation**:
  - **Simple Average**: Mean of all matching market probabilities.
  - **Liquidity-Weighted**: Heavier weighting for markets with higher trading volume.
  - **Accuracy-Weighted**: Weighting based on historical accuracy (PredictIt: 0.93, Kalshi: 0.78, Polymarket: 0.67).
- **Real-time Tracking**: Monitor specific queries and get notified via Discord webhooks when probabilities change.
- **Environment Support**: Manage sensitive URLs and API keys using `.env`.

## Installation

1. Install dependencies:
   ```bash
   pip install predmarket pandas requests python-dotenv httpx
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
python cli.py search "Who will win the 2024 US Election?"
```

### Real-time Tracking

Start a background tracking process that polls markets and sends updates to Discord:

```bash
python cli.py track "Trump wins 2024" --interval 60
```

*Note: If `DISCORD_WEBHOOK_URL` is set in `.env`, the `--webhook` argument is optional.*

## Project Structure

- `cli.py`: Main entry point for the CLI tool.
- `fetcher.py`: Handles data retrieval from Polymarket, Kalshi, and PredictIt.
- `aggregator.py`: Logic for keyword matching and probability aggregation.
- `tracker.py`: Real-time monitoring and Discord notification logic.
