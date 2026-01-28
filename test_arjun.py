import asyncio
import logging
import sys
from app.enumeration import run_arjun_single_url

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def run_test():
    url = "https://google-gruyere.appspot.com/477090468614028063248179346190986534601/snippets.gtl?uid=brie"
    print(f"Testing Arjun on {url}...")
    
    result = await run_arjun_single_url(url, timeout_seconds=60)
    
    if result:
        print(f"✅ Success! Found parameters: {result.get('params')}")
        return 0
    else:
        print("❌ Failed or no parameters found")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(run_test()))
