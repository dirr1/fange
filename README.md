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
- **AI Semantic Filtering**: Uses Google Gemini to rank and filter markets by relevance, handling synonyms and complex queries.
- **AI Summarization**: Generates natural-language summaries of aggregated probabilities.
- **Weighted Aggregation**:
  - **Accuracy-Weighted**: Uses the coefficients above to provide a reliable "wisdom of the crowd" probability.
  - **Simple Average**: Mean of all matching market probabilities.
  - **Liquidity-Weighted**: Weighted by trading volume/open interest where available.
- **Real-time Tracking**: Monitor specific queries and get notified via Discord webhooks.
- **Environment Support**: Manage sensitive URLs and API keys using `.env`.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the root directory:
   ```env
   DISCORD_WEBHOOK_URL=your_discord_webhook_url
   GEMINI_API_KEY=your_google_gemini_api_key

   # Optional API keys for higher rate limits
   KALSHI_KEY_ID=your_id
   KALSHI_KEY_SECRET=your_secret
   POLYMARKET_API_KEY=your_key
   ```

## Usage

### Search and Aggregate

Search for a query and see aggregated results with AI summary:

```bash
python cli.py search "Who will win the 2024 US Election?"
```

### Real-time Tracking

Start a background tracking process:

```bash
python cli.py track "Trump wins 2024" --interval 60
```

## Project Structure

- `cli.py`: Main entry point for the CLI tool.
- `fetcher.py`: Handles data retrieval from all platforms.
- `aggregator.py`: Logic for semantic matching (Gemini) and probability aggregation.
- `tracker.py`: Real-time monitoring and Discord notification logic.
