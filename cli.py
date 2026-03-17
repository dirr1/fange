import os
import argparse
import asyncio
import sys
import logging
from dotenv import load_dotenv
from fetcher import MarketFetcher
from aggregator import MarketAggregator
from tracker import RealTimeTracker

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def search_command(args):
    fetcher = MarketFetcher()
    aggregator = MarketAggregator()

    print(f"[*] Searching for: '{args.query}' across platforms...")
    try:
        # Phase 1: Multi-source Retrieval
        all_markets = await fetcher.fetch_all(query=args.query)
        if not all_markets:
            print("[!] No candidate markets found.")
            return

        # Phase 2: AI-Powered Reranking & Semantic Filtering
        print(f"[*] Reranking {len(all_markets)} candidate markets...")
        top_markets = await aggregator.rerank_markets(args.query, all_markets, top_n=20)

        if not top_markets:
            print("[!] No relevant markets found after reranking.")
            return

        # Phase 3: AI Data Extraction (for messy/missing web data)
        print(f"[*] Extracting and normalizing market data...")
        final_markets = await aggregator.extract_missing_data(top_markets)

        # Phase 4: Aggregation
        probs = aggregator.calculate_aggregate_probability(final_markets)

        # Phase 5: High-Reasoning Synthesis
        print(f"[*] Synthesizing final analysis...")
        analysis = await aggregator.synthesize_summary(args.query, final_markets, probs)

        print("\n" + "="*60)
        print(f"TIERED AI ANALYSIS FOR: {args.query}")
        print("="*60)
        print(f"Accuracy Weighted Prob: {probs.get('accuracy_weighted', 0):.2%}")
        print(f"Simple Average Prob:   {probs.get('simple_average', 0):.2%}")
        print(f"Liquidity/OI Weighted: {probs.get('liquidity_weighted', 0):.2%}")
        print("="*60)

        if analysis:
            print(f"\nAI SYNTHESIS:\n{analysis}")
            print("="*60)

        print("\nTop Contributing Markets:")
        for m in final_markets[:15]:
            yes_prob = "N/A"
            if m.get('outcomes'):
                yes_prob = f"{m['outcomes'][0]['probability']:>7.2%}"

            print(f"- [{m['platform']:<10}] {m['question'][:40]:<40} | {yes_prob} | {m['url']}")

    finally:
        await fetcher.close()

async def track_command(args):
    webhook = args.webhook or os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("[!] Error: Discord Webhook URL not provided.")
        sys.exit(1)

    fetcher_factory = MarketFetcher
    aggregator = MarketAggregator()
    tracker = RealTimeTracker(fetcher_factory, aggregator)

    print(f"[*] Starting tracking for: '{args.query}'")
    tracker.add_tracking_job(args.query, webhook, interval=args.interval)

    tracker.is_running = True
    tracker.fetcher = fetcher_factory()
    try:
        print("[*] Press Ctrl+C to stop tracking.")
        await tracker.run()
    except KeyboardInterrupt:
        print("\n[!] Stopping tracker...")
    finally:
        tracker.stop()
        await tracker.fetcher.close()

def main():
    parser = argparse.ArgumentParser(description="Tiered AI Prediction Market Aggregator")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    search_parser = subparsers.add_parser("search", help="Search and synthesize markets")
    search_parser.add_argument("query", help="Query to search for")

    track_parser = subparsers.add_parser("track", help="Track a query and send alerts")
    track_parser.add_argument("query", help="Query to track")
    track_parser.add_argument("--webhook", help="Discord Webhook URL")
    track_parser.add_argument("--interval", type=int, default=300, help="Interval in seconds")

    args = parser.parse_args()
    if args.command == "search":
        asyncio.run(search_command(args))
    elif args.command == "track":
        asyncio.run(track_command(args))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
