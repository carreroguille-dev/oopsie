from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import time
from pathlib import Path

from src.bootstrap import build_agent, build_notion, build_space_cache
from src.utils.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("load_test")

_QUERIES_FILE = Path(__file__).parent.parent / "docs" / "load-test-queries.md"
_QUERY_RE = re.compile(r"^\d+\.\s+(.+)$")

_RESET_AT = {91, 116, 136, 146, 166, 191}


def parse_queries(path: Path) -> list[str]:
    """Extract numbered queries from the markdown file."""
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _QUERY_RE.match(line.strip())
        if match:
            queries.append(match.group(1))
    return queries


async def run(delay: float, start: int, end: int) -> None:
    logger.info("=== Oopsie Load Test START ===")
    logger.info("Loading config and building agent...")

    config = load_config()
    notion = build_notion(config)
    space_cache = build_space_cache(notion)
    agent = build_agent(config, notion, space_cache)

    queries = parse_queries(_QUERIES_FILE)
    if not queries:
        logger.error("No queries found in %s", _QUERIES_FILE)
        sys.exit(1)

    total = len(queries)
    logger.info("Loaded %d queries from %s", total, _QUERIES_FILE)

    subset = queries[start - 1:end]
    logger.info("Running queries %d to %d (total: %d)", start, end, len(subset))

    passed = 0
    failed = 0
    total_duration = 0.0

    for i, query in enumerate(subset, start=start):
        if i in _RESET_AT:
            agent.reset()
            logger.info("--- Agent conversation reset before query #%d ---", i)

        logger.info("[%d/%d] Query: %s", i, end, query)

        t0 = time.perf_counter()
        try:
            response = await agent.process_message(query)
            duration = time.perf_counter() - t0
            total_duration += duration
            passed += 1
            logger.info(
                "[%d/%d] OK | duration=%.2fs | response_length=%d chars",
                i, end, duration, len(response),
            )
            logger.debug("[%d/%d] Response: %s", i, end, response[:120])
        except Exception:
            duration = time.perf_counter() - t0
            total_duration += duration
            failed += 1
            logger.error(
                "[%d/%d] FAILED | duration=%.2fs",
                i, end, duration, exc_info=True,
            )

        if i < end:
            await asyncio.sleep(delay)

    avg = total_duration / len(subset) if subset else 0
    logger.info("=== Oopsie Load Test END ===")
    logger.info(
        "Results: total=%d passed=%d failed=%d | avg_duration=%.2fs | total_duration=%.0fs",
        len(subset), passed, failed, avg, total_duration,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Oopsie agent load test")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between queries in seconds")
    parser.add_argument("--start", type=int, default=1, help="First query index (1-based)")
    parser.add_argument("--end", type=int, default=200, help="Last query index (1-based)")
    args = parser.parse_args()

    asyncio.run(run(delay=args.delay, start=args.start, end=args.end))


if __name__ == "__main__":
    main()
