"""Step 1: prove the TinyFish connection works. Run: python -m scripts.hello_tinyfish"""
import asyncio
import json

from app.config import get_settings
from app.tinyfish.client import TinyFishClient

SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "first_paragraph": {"type": "string"}},
    "required": ["title"],
}


async def main() -> None:
    s = get_settings()
    async with TinyFishClient(s.tinyfish_api_key) as tf:
        async for ev in tf.stream("https://example.com", "Extract the page title and the first paragraph", output_schema=SCHEMA):
            print(ev["type"], ev.get("purpose", ""))
            if ev["type"] == "COMPLETE":
                print(json.dumps(ev.get("result"), indent=2))


asyncio.run(main())
