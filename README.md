# Prediction Market Aggregator

Track and aggregate probabilities from multiple prediction markets using a tiered AI pipeline.

## Tiered AI Architecture

This tool uses a specialized pipeline of best-in-class AI models to optimize discovery, analysis, and synthesis:

| Task | Models Used | Purpose |
| :--- | :--- | :--- |
| **Market Discovery** | Exa AI, Platform APIs | Find relevant markets across specialized platforms and the open web. |
| **Reranking** | Cohere Rerank v3 | Filter candidate markets for high semantic relevance. |
| **Data Extraction** | GPT-4o mini / Llama 3 | Extract probabilities from noisy web data and unstructured text. |
| **Final Synthesis** | Claude 3.5 Sonnet / Gemini | High-reasoning analysis of consensus, outliers, and directional conviction. |

## Supported Platforms & Accuracy Weights

Aggregated data is weighted based on historical directional accuracy:

| Platform | Accuracy Weight | Description |
| :--- | :--- | :--- |
| **PredictIt** | 93% | Highest accuracy among political markets. |
| **ForecastEx** | 90% | Institutional gold standard for economic data. |
| **Manifold Markets** | 87% | High performance on tech and sports events. |
| **Kalshi** | 78% | Regulated US market for economics and politics. |
| **Robinhood** | 78% | Routes political/economic trades to Kalshi. |
| **Polymarket** | 67% | High speed and volume, with higher speculative noise. |

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your API keys:
   ```env
   # Core
   DISCORD_WEBHOOK_URL=your_webhook_url

   # Discovery & Reranking
   EXA_API_KEY=your_exa_key
   COHERE_API_KEY=your_cohere_key

   # Extraction & Synthesis
   ANTHROPIC_API_KEY=your_claude_key
   OPENAI_API_KEY=your_gpt_key
   # OR
   GEMINI_API_KEY=your_gemini_key
   GROQ_API_KEY=your_groq_key
   ```

## Usage

### Search and Aggregate

Execute a tiered search and get an AI-synthesized probability analysis:

```bash
python cli.py search "Will the US strike Iran in 2026?"
```

### Real-time Tracking

Start a monitoring process for specific queries:

```bash
python cli.py track "Trump 2024" --interval 300
```

## Project Structure

- `cli.py`: Tiered AI pipeline coordinator and CLI entry point.
- `fetcher.py`: Multi-source data retrieval (Exa, Kalshi, Polymarket, etc.).
- `aggregator.py`: AI-powered reranking, extraction, and synthesis logic.
- `tracker.py`: Real-time monitoring and Discord notification logic.
