import asyncio
from httpx import AsyncClient
from predmarket import KalshiRest, PolymarketRest

async def main():
    try:
        async with AsyncClient() as client:
            kalshi = KalshiRest(client)
            polymarket = PolymarketRest(client)
            print("Fetching Kalshi questions...")
            kalshi_response = await kalshi.fetch_questions()
            print(f"Kalshi response type: {type(kalshi_response)}")
            print(f"Kalshi response dir: {dir(kalshi_response)}")
            try:
                print(f"Kalshi response json: {kalshi_response.json()}")
            except:
                print("Kalshi response has no .json()")

            print("Fetching Polymarket questions...")
            polymarket_response = await polymarket.fetch_questions(limit=10)
            print(f"Polymarket response type: {type(polymarket_response)}")
            try:
                print(f"Polymarket response json: {polymarket_response.json()}")
            except:
                print("Polymarket response has no .json()")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
