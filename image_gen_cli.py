#!/usr/bin/env python3
"""
CLI to generate images via OpenAI's API using GPT-4o (or compatible image model),
with persistent prompt-prepend, quality/resolution controls, and optional base64 output.

Features:
- Loads API key from a file (default: ~/.openai_api_key; override with --api-key-file)
- --quality: low|mid|high (maps to Images API quality)
- --resolution: e.g., 512x512, 1024x1024 (if supported by API)
- --prompt-prepend: sets persistent text prepended to every prompt across runs
- -f / --filename: desired filename (without path)
- -p / --path: output directory
- --base64: save base64-encoded PNG bytes to a file with suffix .base64encodedPNG
- Always appends "Create as PNG" to the prompt; requests transparent background where possible

Note: This script uses the OpenAI Images API. If model support differs for GPT-4o,
you can try the default provided here, or override via --model. The code favors
"gpt-image-1" for broad compatibility if GPT-4o direct image generation is not available.
"""

import argparse
import base64
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path


CONFIG_PATH = Path.home() / ".imagegen_cli_config.json"
DEFAULT_API_KEY_FILE = Path.home() / ".openai_api_key"
DEFAULT_API_KEY_FILE_LINUX = Path.cwd() / ".api"


class HelpOnErrorArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"Error: {message}\n\n")
        self.print_help(sys.stderr)
        raise SystemExit(2)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: failed to save config: {e}")


def read_api_key_file_or_die(path: Path, linux_mode: bool) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        if linux_mode:
            raise SystemExit(
                "OpenAI API key not found. Please paste your OpenAI API key into a file named '.api' and rerun."
            )
        else:
            raise SystemExit(
                f"API key file not found at '{path}'. Create it and place your OpenAI API key inside."
            )
    except Exception as e:
        raise SystemExit(f"Failed to read API key file: {e}")


def get_api_key(api_key_file_arg: Path) -> str:
    is_linux = sys.platform.startswith("linux")

    # On Linux: prefer OPENAI_API_KEY env var first, then file (default ./.api if not overridden)
    if is_linux:
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            return env_key.strip()
        # If user explicitly passed a file path, use it; otherwise default to ./.api
        file_path = api_key_file_arg if api_key_file_arg else DEFAULT_API_KEY_FILE_LINUX
        return read_api_key_file_or_die(Path(file_path).expanduser(), linux_mode=True)

    # Non-Linux: original behavior (file required or override via --api-key-file)
    file_path = api_key_file_arg if api_key_file_arg else DEFAULT_API_KEY_FILE
    return read_api_key_file_or_die(Path(file_path).expanduser(), linux_mode=False)


def map_quality(quality_choice: str) -> str:
    # Map low/mid/high to OpenAI Images API quality values
    # OpenAI supports 'standard' and 'hd' for images. We'll map:
    # low -> standard, mid -> standard, high -> hd
    return {
        "low": "standard",
        "mid": "standard",
        "high": "hd",
    }[quality_choice]


def default_size_for_quality(quality_choice: str) -> str:
    # Provide reasonable default size per quality if --resolution not provided
    return {
        "low": "512x512",
        "mid": "1024x1024",
        "high": "2048x2048",
    }[quality_choice]


def sanitize_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name.strip())
    return safe or "image"


def build_output_paths(base_dir: Path, filename: str | None, base64_mode: bool, prompt: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    if filename:
        stem = Path(filename).stem
    else:
        # Derive from prompt + timestamp
        snippet = sanitize_filename("_".join(prompt.split())[:40])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"img_{snippet}_{ts}" if snippet else f"img_{ts}"

    if base64_mode:
        return base_dir / f"{stem}.base64encodedPNG"
    else:
        # Always save PNG
        return base_dir / f"{stem}.png"


def generate_image(
    prompt: str,
    api_key: str,
    model: str,
    quality_choice: str,
    resolution: str | None,
) -> bytes:
    # Import lazily so --help works without the package
    try:
        from openai import OpenAI
    except Exception as e:
        raise SystemExit(
            "The 'openai' package is required. Install with: pip install openai"
        )

    client = OpenAI(api_key=api_key)

    # Prepare parameters for Images API call
    quality_param = map_quality(quality_choice)
    size_param = resolution or default_size_for_quality(quality_choice)

    # Build the prompt and ensure PNG + transparency requested
    augmented_prompt = f"{prompt.strip()} Create as PNG with transparent background."

    # Prefer gpt-image-1 for image generation compatibility if the user leaves default as gpt-4o
    model_to_use = model or "gpt-4o"
    image_params = dict(model=model_to_use, prompt=augmented_prompt, size=size_param, quality=quality_param)

    # Some models support background="transparent". We'll try it if likely supported.
    # We attempt with the param first, then gracefully retry without if the API rejects it.
    try:
        resp = client.images.generate(**{**image_params, "background": "transparent"})
    except Exception:
        resp = client.images.generate(**image_params)

    try:
        b64 = resp.data[0].b64_json
    except Exception as e:
        raise SystemExit(f"Unexpected API response format: {e}")

    try:
        return base64.b64decode(b64)
    except Exception as e:
        raise SystemExit(f"Failed to decode image data: {e}")


def write_output(data: bytes, out_path: Path, base64_mode: bool) -> None:
    if base64_mode:
        # Save base64 of PNG bytes, without newlines, with exact suffix '.base64encodedPNG'
        b64 = base64.b64encode(data).decode("ascii")
        with open(out_path, "w", encoding="ascii") as f:
            f.write(b64)
    else:
        with open(out_path, "wb") as f:
            f.write(data)


def main(argv=None):
    parser = HelpOnErrorArgumentParser(
        prog="image_gen_cli",
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent(
            """
            Generate images using OpenAI via GPT-4o (or compatible image model).

            Examples:
              image_gen_cli --prompt "pink anime elephant" --quality high -f elephant.png
              image_gen_cli --prompt "pink anime elephant" --base64 -p ./out
              image_gen_cli --prompt-prepend "Studio Ghibli style" --prompt "pink elephant"
            """
        ).strip(),
    )

    parser.add_argument(
        "--prompt",
        type=str,
        required=True,
        help="Text prompt to generate the image for.",
    )

    parser.add_argument(
        "--quality",
        choices=["low", "mid", "high"],
        default="mid",
        help="Image quality level (maps to API quality).",
    )

    parser.add_argument(
        "--resolution",
        type=str,
        default=None,
        help="Target resolution, e.g. 512x512, 1024x1024 (if supported).",
    )

    parser.add_argument(
        "--prompt-prepend",
        type=str,
        default=None,
        help="Set persistent text prepended to every prompt across runs.",
    )

    parser.add_argument(
        "-f",
        "--filename",
        type=str,
        default=None,
        help="Filename for output (extension auto-set based on mode).",
    )

    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=str(Path.cwd()),
        help="Directory to save the output file.",
    )

    parser.add_argument(
        "--base64",
        action="store_true",
        help="Save base64-encoded PNG bytes to a .base64encodedPNG file.",
    )

    # Choose platform-appropriate default for API key file argument
    default_key_path = DEFAULT_API_KEY_FILE_LINUX if sys.platform.startswith("linux") else DEFAULT_API_KEY_FILE
    parser.add_argument(
        "--api-key-file",
        type=str,
        default=str(default_key_path),
        help=(
            "Path to file containing OpenAI API key. "
            + (f"Default on Linux: {DEFAULT_API_KEY_FILE_LINUX}. " if sys.platform.startswith("linux") else f"Default: {DEFAULT_API_KEY_FILE}. ")
            + "On Linux, OPENAI_API_KEY env var is preferred if set."
        ),
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="OpenAI model to use (default: gpt-4o). For compatibility, try gpt-image-1.",
    )

    args = parser.parse_args(argv)

    # Load and update persistent config
    cfg = load_config()
    if args.prompt_prepend is not None:
        cfg["prompt_prepend"] = args.prompt_prepend
        save_config(cfg)

    prepend_text = cfg.get("prompt_prepend", "").strip()

    # Compose final prompt; always append PNG instruction
    user_prompt = args.prompt.strip()
    if prepend_text:
        final_prompt = f"{prepend_text} {user_prompt}"
    else:
        final_prompt = user_prompt

    # Resolve API key (Linux: env var first, then file '.api'; others: file)
    api_key = get_api_key(Path(args.api_key_file))

    # Generate image (PNG with transparency requested via prompt/param)
    img_bytes = generate_image(
        prompt=final_prompt,
        api_key=api_key,
        model=args.model,
        quality_choice=args.quality,
        resolution=args.resolution,
    )

    # Build output path and write file
    out_dir = Path(args.path).expanduser()
    out_path = build_output_paths(out_dir, args.filename, args.base64, final_prompt)
    write_output(img_bytes, out_path, args.base64)

    # Report location
    if args.base64:
        print(f"Saved base64 PNG to: {out_path}")
    else:
        print(f"Saved PNG image to: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # Catch-all to ensure a help hint on unexpected errors
        print(f"Unexpected error: {e}", file=sys.stderr)
        print("Use --help for usage.")
        raise SystemExit(1)
