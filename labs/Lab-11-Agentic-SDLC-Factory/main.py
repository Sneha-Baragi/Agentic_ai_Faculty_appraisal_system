#!/usr/bin/env python3
"""
Lab 11: Agentic SDLC Factory
Entry point for the autonomous software engineering pipeline.

Usage::

    python main.py                    # run first story as demo
    python main.py --story US-001     # run a specific story
    python main.py --all              # run all fixture stories
    python main.py --all --log-level DEBUG
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the lab root is on sys.path so sub-packages import correctly when
# the script is invoked from any working directory.
# ---------------------------------------------------------------------------
_LAB_ROOT = Path(__file__).parent.resolve()
if str(_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LAB_ROOT))

from models.schemas import SDLCFactoryReport, StoryStatus, UserStory  # noqa: E402
from pipeline.sdlc_pipeline import SDLCPipeline  # noqa: E402
from tools.story_parser import StoryParser  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with a consistent format.

    Args:
        level: Logging level string (``DEBUG``, ``INFO``, ``WARNING``, …).
    """
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    logger.debug("Logging initialised at level %s.", level)


def load_stories(path: Path) -> list[UserStory]:
    """Load user stories from a JSON fixture file.

    Args:
        path: Path to the JSON fixture file.

    Returns:
        A list of :class:`~models.schemas.UserStory` objects.

    Raises:
        SystemExit: If the file does not exist or is malformed.
    """
    if not path.exists():
        logger.error("Story fixture file not found: %s", path)
        sys.exit(1)
    try:
        parser = StoryParser()
        return parser.parse_file(path)
    except (ValueError, KeyError) as exc:
        logger.error("Failed to load stories from %s: %s", path, exc)
        sys.exit(1)


def run_single(
    story_id: str,
    stories: list[UserStory],
    pipeline: SDLCPipeline,
) -> SDLCFactoryReport:
    """Run the pipeline for a single story identified by *story_id*.

    Args:
        story_id: The story identifier to find in *stories*.
        stories: Full list of loaded user stories.
        pipeline: Configured pipeline instance.

    Returns:
        The :class:`~models.schemas.SDLCFactoryReport` for the story.

    Raises:
        SystemExit: If *story_id* is not found in *stories*.
    """
    match = [s for s in stories if s.story_id == story_id]
    if not match:
        available = [s.story_id for s in stories]
        logger.error(
            "Story '%s' not found. Available: %s", story_id, available
        )
        sys.exit(1)
    story = match[0]
    logger.info("Running pipeline for story %s: %s", story.story_id, story.title)
    return pipeline.run(story)


def run_all(
    stories: list[UserStory],
    pipeline: SDLCPipeline,
) -> list[SDLCFactoryReport]:
    """Run the pipeline for every story in *stories*.

    Args:
        stories: All loaded user stories.
        pipeline: Configured pipeline instance.

    Returns:
        An ordered list of :class:`~models.schemas.SDLCFactoryReport` objects.
    """
    reports: list[SDLCFactoryReport] = []
    for story in stories:
        logger.info("─── Processing %s: %s ───", story.story_id, story.title)
        report = pipeline.run(story)
        reports.append(report)
        status_icon = "✓" if report.final_status == StoryStatus.COMPLETED else "✗"
        print(
            f"  {status_icon} {report.story_id:8s} │ "
            f"{report.final_status.value:12s} │ "
            f"{report.total_duration_ms:7.1f} ms │ "
            f"{report.story_title}",
            file=sys.stderr,
        )
    return reports


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Parse arguments and run the SDLC pipeline.

    Returns:
        Exit code: ``0`` on success, ``1`` if any story failed.
    """
    parser = argparse.ArgumentParser(
        description="Lab 11: Agentic SDLC Factory — autonomous software engineering pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                # run first story (demo)\n"
            "  python main.py --story US-001\n"
            "  python main.py --all --log-level DEBUG\n"
        ),
    )
    parser.add_argument(
        "--story",
        metavar="STORY_ID",
        help="Story ID to run (e.g. US-001).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all stories from the fixture file.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--data",
        default="data/story_fixtures.json",
        help="Path to story fixtures JSON (default: data/story_fixtures.json).",
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = _LAB_ROOT / data_path

    stories = load_stories(data_path)
    logger.info("Loaded %d stories from %s.", len(stories), data_path)

    config: dict = {
        "max_complexity": 7,
        "min_coverage": 80.0,
        "min_review_score": 70,
        "deploy_target_staging": "staging.faculty-appraisal.local",
        "deploy_target_prod": "prod.faculty-appraisal.local",
        "quality_gate_threshold": 0.9,
    }
    pipeline = SDLCPipeline(config)

    if args.story:
        report = run_single(args.story, stories, pipeline)
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return 0 if report.final_status == StoryStatus.COMPLETED else 1

    if args.all:
        print(
            f"\n{'Story':8s} │ {'Status':12s} │ {'Duration':>10s} │ Title",
            file=sys.stderr,
        )
        print("─" * 70, file=sys.stderr)
        reports = run_all(stories, pipeline)
        passed = sum(1 for r in reports if r.final_status == StoryStatus.COMPLETED)
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(
            f"SDLC Factory Summary: {passed}/{len(reports)} stories COMPLETED",
            file=sys.stderr,
        )
        print(f"{'=' * 60}\n", file=sys.stderr)
        return 0 if passed == len(reports) else 1

    # Default: run the first story as a quick demo
    story = stories[0]
    logger.info("Demo mode: running story %s", story.story_id)
    report = run_single(story.story_id, [story], pipeline)
    print(json.dumps(report.to_dict(), indent=2, default=str))
    return 0 if report.final_status == StoryStatus.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
