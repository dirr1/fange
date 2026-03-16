import asyncio
import unittest
from unittest.mock import MagicMock, patch
from tracker import RealTimeTracker

class TestTracker(unittest.IsolatedAsyncioTestCase):
    async def test_send_discord_update(self):
        fetcher = MagicMock()
        aggregator = MagicMock()
        tracker = RealTimeTracker(fetcher, aggregator)

        with patch('requests.post') as mock_post:
            tracker.send_discord_update("Test Query", 0.75, {"simple_average": 0.74}, "http://fake-webhook")
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(kwargs['json']['embeds'][0]['title'], "Probability Update: Test Query")

if __name__ == '__main__':
    unittest.main()
