from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a Hugging Face model into the local cache or a project folder.")
    parser.add_argument("model_id", help="Hugging Face model id. Example: google/gemma-3n-E4B-it")
    parser.add_argument("--local-dir", help="Optional local directory to materialize the model files.")
    parser.add_argument("--cache-dir", help="Optional Hugging Face cache directory.")
    parser.add_argument("--exclude", nargs="*", default=["*.md", "*.gguf"], help="Patterns to exclude.")
    args = parser.parse_args()

    local_dir = Path(args.local_dir).expanduser().resolve() if args.local_dir else None
    cache_dir = Path(args.cache_dir).expanduser().resolve() if args.cache_dir else None

    path = snapshot_download(
        repo_id=args.model_id,
        local_dir=str(local_dir) if local_dir else None,
        cache_dir=str(cache_dir) if cache_dir else None,
        ignore_patterns=args.exclude,
    )
    print(path)


if __name__ == "__main__":
    main()
