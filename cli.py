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

# Configure logging at the application entry point
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def search_command(args):
    fetcher = MarketFetcher()
    aggregator = MarketAggregator()

    print(f"[*] Searching for: '{args.query}' across platforms...")
    try:
        # Pass query to fetch_all for more efficient/targeted fetching
        all_markets = await fetcher.fetch_all(query=args.query)
        # Aggregator still does fuzzy matching and sorting
        matched = aggregator.aggregate_markets(args.query, all_markets)

        if not matched:
            print("[!] No matching markets found.")
            return

        # Optionally apply semantic filtering if Gemini is enabled
        if aggregator.gemini_enabled:
            print("[*] Enhancing search with Gemini AI semantic filtering...")
            matched = await aggregator.semantic_filter(args.query, matched)

        probs = aggregator.calculate_aggregate_probability(matched)

        # Generate AI summary if enabled
        ai_summary = ""
        if aggregator.gemini_enabled:
            ai_summary = await aggregator.generate_summary(args.query, probs, len(matched))

        print("\n" + "="*60)
        print(f"AGGREGATED RESULTS FOR: {args.query}")
        print("="*60)
        print(f"Accuracy Weighted:  {probs.get('accuracy_weighted', 0):.2%}")
        print(f"Simple Average:     {probs.get('simple_average', 0):.2%}")
        print(f"Liquidity Weighted: {probs.get('liquidity_weighted', 0):.2%}")
        print("="*60)

        if ai_summary:
            print(f"\nAI SUMMARY:\n{ai_summary}")
            print("="*60)

        print("\nIndividual Markets (Top 15):")
        for m in matched[:15]:
            yes_prob = 0
            found_yes = False
            for o in m['outcomes']:
                if o['name'] and "yes" in str(o['name']).lower():
                    yes_prob = o['probability']
                    found_yes = True
                    break
            if not found_yes and m['outcomes']:
                yes_prob = m['outcomes'][0]['probability']

            print(f"- [{m['platform']:<10}] {m['question'][:40]:<40} | {yes_prob:>7.2%} | {m['url']}")

    finally:
        await fetcher.close()

async def track_command(args):
    webhook = args.webhook or os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("[!] Error: Discord Webhook URL not provided and not found in .env (DISCORD_WEBHOOK_URL).")
        sys.exit(1)

    fetcher_factory = MarketFetcher
    aggregator = MarketAggregator()
    tracker = RealTimeTracker(fetcher_factory, aggregator)

    print(f"[*] Starting tracking for: '{args.query}'")
    print(f"[*] Interval: {args.interval} seconds")
    print(f"[*] Webhook: {webhook[:20]}...")

    tracker.add_tracking_job(args.query, webhook, interval=args.interval)

    # Run in foreground
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
    parser = argparse.ArgumentParser(description="Prediction Market Aggregator CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search and aggregate markets")
    search_parser.add_argument("query", help="Keywords or sentence to search for")

    # Track command
    track_parser = subparsers.add_parser("track", help="Track a query and send alerts to Discord")
    track_parser.add_argument("query", help="Query to track")
    track_parser.add_argument("--webhook", help="Discord Webhook URL (optional if DISCORD_WEBHOOK_URL is in .env)")
    track_parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")

    args = parser.parse_args()

    if args.command == "search":
        try:
            asyncio.run(search_command(args))
        except KeyboardInterrupt:
            pass
    elif args.command == "track":
        try:
            asyncio.run(track_command(args))
        except KeyboardInterrupt:
            pass
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
