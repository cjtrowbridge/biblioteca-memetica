from __future__ import annotations

from cicd.entrypoints.run_summarizer_pipeline import run_summarizer_pipeline


def main() -> int:
    return run_summarizer_pipeline()


if __name__ == "__main__":
    raise SystemExit(main())
