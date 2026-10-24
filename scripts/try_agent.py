"""Step 2: run the full agent loop. Run: python -m scripts.try_agent "your goal here" """
import asyncio
import sys

from app.agent.llm import make_llm
from app.agent.loop import resume_goal, run_goal
from app.agent.tools import Budget, build_tools
from app.config import get_settings
from app.tinyfish.client import TinyFishClient


async def main(goal: str) -> None:
    s = get_settings()
    budget = Budget(s.max_steps, s.max_agent_runs)
    llm, model = make_llm(s)
    async with TinyFishClient(s.tinyfish_api_key) as tf:
        kw = dict(
            llm=llm,
            model=model,
            tools=build_tools(tf, budget),
            budget=budget,
            result_char_limit=s.tool_result_char_limit,
            on_step=lambda st: print("STEP:", st["tool"], st.get("output_preview", st.get("paused", ""))),
        )
        result = await run_goal(goal, **kw)
        while result.status == "waiting_for_user":
            reply = input(f"\nAgent asks: {result.question}\n> ")
            result = await resume_goal(result, reply, **kw)
        print("\nFINAL:", result.status, "-", result.answer)


asyncio.run(main(" ".join(sys.argv[1:]) or "What is the title of example.com?"))
