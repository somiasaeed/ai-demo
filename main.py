#!/usr/bin/env python3
"""AI Agent Demo with subcommands for different agents.

Usage:
    uv run main.py cvtailor --cv resume.pdf --cover-letter cover.pdf --job-desc job.txt
    uv run main.py summarize --file document.pdf
"""

import argparse
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Suppress noisy library logs — only show our own INFO and above.
_noisy_loggers = (
    "strands", "strands.models", "strands.models.openai",
    "strands.telemetry", "strands.event_loop",
    "LiteLLM", "LiteLLM Router", "LiteLLM Proxy",
    "httpx", "httpcore", "openai", "openai._base_client",
)
for _name in _noisy_loggers:
    logging.getLogger(_name).setLevel(logging.WARNING)

# Suppress the specific reasoningContent warning (strands handles it correctly, warning is cosmetic).
def _filter_reasoning_warning(record: logging.LogRecord) -> bool:
    return "reasoningContent is not supported" not in record.getMessage()

for _name in ("strands.models.openai", "strands.models"):
    logging.getLogger(_name).addFilter(_filter_reasoning_warning)


def cmd_cvtailor(args: argparse.Namespace) -> None:
    """Tailor CV and cover letter to a job description."""
    for path, label in [
        (args.cv, "CV"),
        (args.cover_letter, "Cover letter"),
        (args.job_desc, "Job description"),
    ]:
        if not os.path.exists(path):
            print(f"Error: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)
    if getattr(args, "photo", None) and not os.path.exists(args.photo):
        print(f"Error: Photo file not found: {args.photo}", file=sys.stderr)
        sys.exit(1)

    from agents.cv_tailorer import CVTailorerAgent

    agent = CVTailorerAgent()
    version = agent._next_version(args.output_dir)

    print("=" * 50)
    print("  CV & Cover Letter Tailorer")
    print("=" * 50)
    print(f"  CV:           {args.cv}")
    print(f"  Cover Letter: {args.cover_letter}")
    print(f"  Job Desc:     {args.job_desc}")
    if getattr(args, "photo", None):
        print(f"  Photo:        {args.photo} (top right of CV)")
    print(f"  Output:       {args.output_dir}/ (v{version})")
    print(f"  Model:        {agent.settings.openai_model} ({'reasoning' if agent.is_reasoning else 'standard'})")
    print("=" * 50)
    print()
    print("Agent workflow:")

    start = time.time()
    result = agent.tailor(
        cv_path=args.cv,
        cover_letter_path=args.cover_letter,
        job_desc_path=args.job_desc,
        output_dir=args.output_dir,
        photo_path=getattr(args, "photo", None),
    )
    elapsed = time.time() - start

    print()
    print("-" * 50)
    print("Summary of changes:")
    print("-" * 50)
    print(result)
    print()
    print(f"Output saved to {args.output_dir}/ (v{version}):")
    print(f"  tailored_cv_v{version}.md  + .pdf  + .docx")
    print(f"  tailored_cover_letter_v{version}.md  + .pdf  + .docx")
    print(f"  tailored_cv_de_v{version}.md  + .pdf  + .docx")
    print(f"  tailored_cover_letter_de_v{version}.md  + .pdf  + .docx")
    print(f"\nCompleted in {elapsed:.1f}s")


def cmd_summarize(args: argparse.Namespace) -> None:
    """Summarize a document."""
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    from agents.summarizer import SummarizerAgent

    agent = SummarizerAgent()

    print("=" * 50)
    print("  Document Summarizer")
    print("=" * 50)
    print(f"  File:   {args.file}")
    print(f"  Model:  {agent.settings.openai_model} ({'reasoning' if agent.is_reasoning else 'standard'})")
    print("=" * 50)
    print()
    print("Agent workflow:")

    start = time.time()
    result = agent.summarize(file_path=args.file)
    elapsed = time.time() - start

    print()
    print("-" * 50)
    print("Summary:")
    print("-" * 50)
    print(result)
    print(f"\nCompleted in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="AI Agent Demo — run different agents via subcommands",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available agents")

    # cvtailor subcommand
    cv_parser = subparsers.add_parser("cvtailor", help="Tailor CV and cover letter to a job description")
    cv_parser.add_argument("--cv", required=True, help="Path to CV/resume PDF")
    cv_parser.add_argument("--cover-letter", required=True, help="Path to cover letter PDF")
    cv_parser.add_argument("--job-desc", required=True, help="Path to job description text file")
    cv_parser.add_argument("--photo", help="Path to photo image for CV (placed at top right of first page)")
    cv_parser.add_argument("--output-dir", default="output", help="Output directory (default: output)")

    # summarize subcommand
    sum_parser = subparsers.add_parser("summarize", help="Summarize a document (PDF or text)")
    sum_parser.add_argument("--file", required=True, help="Path to document (PDF or text)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\nAvailable agents:")
        print("  cvtailor   Tailor CV and cover letter to a job description")
        print("  summarize  Summarize a document (PDF or text)")
        print("\nExample:")
        print("  uv run main.py cvtailor --cv samples/cv.pdf --cover-letter samples/cover_letter.pdf --job-desc samples/job_description.txt [--photo photo.jpg]")
        sys.exit(1)

    commands = {
        "cvtailor": cmd_cvtailor,
        "summarize": cmd_summarize,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
