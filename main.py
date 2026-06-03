import argparse
import sys
import random
import os
import shutil
import datetime
from pathlib import Path

# Helper to generate schedule times respecting start time and interval, spreading across days if needed
def _generate_schedule(count: int):
    """Generate a list of datetime objects for scheduling.
    Starts at config.SCHEDULE_START on the next possible slot and adds intervals of
    config.SCHEDULE_INTERVAL_HOURS, rolling over to the next day when past midnight.
    """
    now = datetime.datetime.now()
    start_hour, start_minute = map(int, config.SCHEDULE_START.split(":"))
    # initial base time
    base = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    if base < now:
        base += datetime.timedelta(days=1)
    schedule = []
    cur = base
    while len(schedule) < count:
        schedule.append(cur)
        cur = cur + datetime.timedelta(hours=config.SCHEDULE_INTERVAL_HOURS)
        # If we've passed the end of the day, roll to next day's start time
        if cur.day != schedule[-1].day:
            cur = cur.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    return schedule


import config
from quotes import QuoteFetcher
from video import BackgroundGenerator, AudioGenerator, VideoRenderer, ImageFetcher
from upload import Uploader


BANNER = """
  ** Quote Video Generator -- AI-Powered Shorts **
"""

SEP = "-" * 60


def prompt(message: str, default: str = None) -> str:
    if default:
        val = input(f"  [?] {message} [{default}]: ").strip()
        return val if val else default
    return input(f"  [?] {message}: ").strip()


def confirm(message: str) -> bool:
    resp = input(f"  [?] {message} (y/n): ").strip().lower()
    return resp in ("y", "yes", "")


def show_quote_preview(quotes: list):
    print(f"\n  [i] Found {len(quotes)} quote(s):")
    print()
    for i, q in enumerate(quotes, 1):
        wrapped = q.text[:80] + ("..." if len(q.text) > 80 else "")
        print(f"    {i}. '{wrapped}'")
        print(f"       -- {q.author}")
        print()


def show_file_size(path: str):
    size = os.path.getsize(path)
    if size > 1_000_000:
        return f"{size / 1_000_000:.1f} MB"
    return f"{size / 1_000:.0f} KB"


def get_random_bg_music() -> str | None:
    bgmusics_dir = config.MUSIC_DIR
    if bgmusics_dir.exists():
        musics = [f for f in os.listdir(bgmusics_dir) if f.endswith('.mp3') or f.endswith('.wav')]
        if musics:
            return str(bgmusics_dir / random.choice(musics))
    return None

def get_random_bg_image(bg_gen, fallback_path) -> str:
    bgs_dir = config.BACKGROUNDS_DIR
    if bgs_dir.exists():
        bgs = [f for f in os.listdir(bgs_dir) if f.endswith(".jpg") or f.endswith(".png") and f != "bg.png" and f != fallback_path.name]
        if bgs:
            return str(bgs_dir / random.choice(bgs))
    return bg_gen.generate_random(fallback_path)


def upload_video_outputs(
    uploader: Uploader,
    video_path: Path,
    *,
    youtube_payload: dict | None = None,
    schedule_time: datetime.datetime | None = None,
):
    if youtube_payload:
        try:
            # Ensure default tags are present
            if "tags" not in youtube_payload or not youtube_payload.get("tags"):
                youtube_payload["tags"] = config.DEFAULT_YT_TAGS
            # Compute publishAt if scheduling is requested
            publish_at = None
            if schedule_time:
                # Convert to UTC RFC3339 format
                publish_at = schedule_time.astimezone(datetime.timezone.utc).replace(tzinfo=None).isoformat() + "Z"
                youtube_payload["publish_at"] = publish_at
            uploader.upload_to_youtube(video_path, **youtube_payload)
        except Exception as exc:
            print(f"  [YouTube] Upload failed: {exc}")


def generate_single(topic: str = None, count: int = 1, upload_yt: bool = False, languages: list[str] = None, auto_confirm: bool = False):
    """Generate one or more quote videos.

    If `languages` is provided, a separate video is generated for each language.
    When `languages` is None, it defaults to the single language passed via `topic` or config.
    """
    print("\n  [*] Fetching quotes...")
    bg_gen = BackgroundGenerator()
    audio_gen = AudioGenerator()
    renderer = VideoRenderer()
    image_fetcher = ImageFetcher()

    # Determine which languages to use
    if languages is None:
        languages = [config.DEFAULT_LANGUAGE]

    for lang in languages:
        fetcher = QuoteFetcher(language=lang)
        if topic:
            quotes = fetcher.fetch_by_category(topic, count)
        else:
            quotes = fetcher.fetch_random(count)
        if not quotes:
            print(f"  [X] No quotes fetched for language '{lang}'. Skipping.")
            continue
        show_quote_preview(quotes)
        if not auto_confirm:
            if not confirm("Generate videos for these quotes?"):
                print("  [X] Cancelled.\n")
                continue
        bgmusic_path = get_random_bg_music()
        if bgmusic_path:
            print(f"  [i] Selected background music: {Path(bgmusic_path).name}")
        else:
            print(f"  [WARNING] No background music found in bgmusics directory!")
        run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = config.OUTPUT_DIR / run_timestamp / lang
        out_dir.mkdir(parents=True, exist_ok=True)
        back_dir = config.BACKUP_DIR / run_timestamp / lang
        back_dir.mkdir(parents=True, exist_ok=True)
        uploader = Uploader() if upload_yt else None
        # Determine schedule times iterator using helper
        schedule_times = []
        if upload_yt:
            schedule_times = _generate_schedule(len(quotes))
        for idx, q in enumerate(quotes, 1):
            output = out_dir / f"{q.author}_{abs(hash(q.text)) % 10000}_{lang}.mp4"
            print(f"\n  [*] Rendering quote {idx}/{len(quotes)} ({lang})...")
            print(f"     '{q.text[:60]}...'")
            fetched_img = image_fetcher.fetch_image_for_quote(q.text)
            temp_bg = config.BACKGROUNDS_DIR / f"temp_bg_single_{idx}_{lang}.jpg"
            if fetched_img:
                bg_path = bg_gen.generate_blended(fetched_img, temp_bg)
            else:
                bg_path = bg_gen.generate_random(temp_bg)
            renderer.render_single_quote(q.text, q.author, bg_path, output, bgmusic_path=bgmusic_path)
            size = show_file_size(str(output))
            print(f"  [OK] Saved: {output.name} ({size})")
            try:
                if os.path.exists(bg_path):
                    os.remove(bg_path)
            except Exception:
                pass
            backup_path = back_dir / output.name
            shutil.copy2(output, backup_path)
            print(f"  [OK] Backup saved: {backup_path.name}")
            if uploader:
                schedule_time = None
                if schedule_times:
                    schedule_time = schedule_times[idx - 1]
                upload_video_outputs(
                    uploader,
                    output,
                    youtube_payload={
                        "title": f"Quote by {q.author} ({lang})",
                        "description": f"{q.text}\n\n#quotes #shorts",
                    },
                    schedule_time=schedule_time,
                )

    print(f"\n  [+] Done! Generated quotes for languages: {', '.join(languages)}")

    print("\n  [*] Fetching quotes...")
    fetcher = QuoteFetcher()
    bg_gen = BackgroundGenerator()
    audio_gen = AudioGenerator()
    renderer = VideoRenderer()
    image_fetcher = ImageFetcher()

    if topic:
        quotes = fetcher.fetch_by_category(topic, count)
    else:
        quotes = fetcher.fetch_random(count)

    if not quotes:
        print("  [X] No quotes fetched. Try again later.")
        return

    show_quote_preview(quotes)

    if not auto_confirm:
        if not confirm("Generate videos for these quotes?"):
            print("  [X] Cancelled.\n")
            return

    bgmusic_path = get_random_bg_music()
    if bgmusic_path:
        print(f"  [i] Selected background music: {Path(bgmusic_path).name}")
    else:
        print(f"  [WARNING] No background music found in bgmusics directory!")

    run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = config.OUTPUT_DIR / run_timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    back_dir = config.BACKUP_DIR / run_timestamp
    back_dir.mkdir(parents=True, exist_ok=True)
    uploader = Uploader() if upload_yt else None

    # Determine schedule times iterator using helper
    schedule_times = []
    if upload_yt:
        schedule_times = _generate_schedule(len(quotes))
        # No sorting needed as times are sequential

    for idx, q in enumerate(quotes, 1):
        output = out_dir / f"{q.author}_{abs(hash(q.text)) % 10000}.mp4"
        print(f"\n  [*] Rendering quote {idx}/{len(quotes)}...")
        print(f"     '{q.text[:60]}...'")

        # 1. Fetch stock photo dynamically based on quote keywords
        fetched_img = image_fetcher.fetch_image_for_quote(q.text)
        
        # 2. Render blended premium gradient background
        temp_bg = config.BACKGROUNDS_DIR / f"temp_bg_single_{idx}.jpg"
        if fetched_img:
            bg_path = bg_gen.generate_blended(fetched_img, temp_bg)
        else:
            bg_path = bg_gen.generate_random(temp_bg)
            
        # Removed invalid background layer call
        renderer.render_single_quote(q.text, q.author, bg_path, output, bgmusic_path=bgmusic_path)
        size = show_file_size(str(output))
        print(f"  [OK] Saved: {output.name} ({size})")
        
        # 3. Clean up temporary background file
        try:
            if os.path.exists(bg_path):
                os.remove(bg_path)
        except Exception:
            pass

        backup_path = back_dir / output.name
        shutil.copy2(output, backup_path)
        print(f"  [OK] Backup saved: {backup_path.name}")
        
        if uploader:
            # Choose a schedule time cyclically
            schedule_time = None
            if schedule_times:
                schedule_time = schedule_times[idx - 1]
            upload_video_outputs(
                uploader,
                output,
                youtube_payload={
                    "title": f"Quote by {q.author}",
                    "description": f"{q.text}\n\n#quotes #shorts",
                },
                schedule_time=schedule_time,
            )

    print(f"\n  [+] Done! Generated {len(quotes)} video(s) in: {out_dir}")
    print()


def generate_batch(category: str = None, count: int = 5, upload_yt: bool = False, auto_confirm: bool = False):
    print("\n  [*] Fetching quotes for compilation...")
    fetcher = QuoteFetcher()
    bg_gen = BackgroundGenerator()
    audio_gen = AudioGenerator()
    renderer = VideoRenderer()
    image_fetcher = ImageFetcher()

    if category:
        quotes = fetcher.fetch_by_category(category, count)
    else:
        quotes = fetcher.fetch_random(count)

    if not quotes:
        print("  [X] No quotes fetched. Try again later.")
        return

    show_quote_preview(quotes)

    if not auto_confirm:
        if not confirm("Generate a compilation video?"):
            print("  [X] Cancelled.\n")
            return

    print(f"\n  [*] Generating {count} unique blended backgrounds...")
    bg_paths = []
    for i, q in enumerate(quotes):
        print(f"     Background {i + 1}/{count} for quote: '{q.text[:40]}...'")
        
        # 1. Fetch related dynamic stock image
        fetched_img = image_fetcher.fetch_image_for_quote(q.text)
        
        # 2. Render blended premium gradient background
        temp_bg = config.BACKGROUNDS_DIR / f"temp_bg_comp_{i}.jpg"
        if fetched_img:
            bg = bg_gen.generate_blended(fetched_img, temp_bg)
        else:
            bg = bg_gen.generate_random(temp_bg)
            
        bg_paths.append(bg)
    print("  [OK] All backgrounds ready")

    bgmusic_path = get_random_bg_music()
    if bgmusic_path:
        print(f"  [i] Selected background music: {Path(bgmusic_path).name}")
    else:
        print(f"  [WARNING] No background music found in bgmusics directory!")

    run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = config.OUTPUT_DIR / run_timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    back_dir = config.BACKUP_DIR / run_timestamp
    back_dir.mkdir(parents=True, exist_ok=True)
    uploader = Uploader() if upload_yt else None

    # Determine schedule times iterator using helper
    schedule_times = []
    if upload_yt:
        schedule_times = _generate_schedule(len(quotes))

    output = out_dir / f"quote_compilation_{category or 'mixed'}_{random.randint(1000, 9999)}.mp4"
    print(f"\n  [*] Rendering compilation ({len(quotes)} quotes)...")
    renderer.render_compilation(quotes, bg_paths, output, bgmusic_path=bgmusic_path)
    size = show_file_size(str(output))
    print(f"  [OK] Saved: {output.name} ({size})")
    
    # 3. Clean up temporary background files
    for bg in bg_paths:
        try:
            if os.path.exists(bg):
                os.remove(bg)
        except Exception:
            pass

    backup_path = back_dir / output.name
    shutil.copy2(output, backup_path)
    print(f"  [OK] Backup saved: {backup_path.name}")
    
    if uploader:
        # Choose schedule time based on first schedule entry
        schedule_time = schedule_times[0] if schedule_times else None
        upload_video_outputs(
            uploader,
            output,
            youtube_payload={
                "title": "Incredible Quotes Compilation",
                "description": "A compilation of some of the best quotes.\n\n#quotes #shorts",
                "tags": ["quotes", "compilation", "shorts"],
            },
            schedule_time=schedule_time,
        )

    print(f"\n  [+] Done! Video saved in: {out_dir}")
    print()


def list_categories():
    from config import DEFAULT_QUOTE_CATEGORIES
    print("  Available categories:")
    for c in DEFAULT_QUOTE_CATEGORIES:
        print(f"    - {c}")


def interactive_mode(upload_yt: bool = False):
    print(BANNER)
    print(SEP)
    print("  What would you like to do?")
    print()
    print("    1) Generate a single quote video")
    print("    2) Generate a compilation video (multiple quotes)")
    print("    3) Browse available categories")
    print("    4) Exit")
    print()

    choice = prompt("Enter your choice", default="1")

    if choice == "1":
        categories = config.DEFAULT_QUOTE_CATEGORIES
        print(f"\n  Categories: {', '.join(categories)}")
        cat = prompt("Category (leave blank for random)")
        c = prompt("Number of quotes", default="3")
        generate_single(cat if cat else None, int(c), upload_yt)
    elif choice == "2":
        categories = config.DEFAULT_QUOTE_CATEGORIES
        print(f"\n  Categories: {', '.join(categories)}")
        cat = prompt("Category (leave blank for random)")
        c = prompt("Number of quotes", default="5")
        generate_batch(cat if cat else None, int(c), upload_yt)
    elif choice == "3":
        list_categories()
        print()
        interactive_mode(upload_yt, upload_fb, upload_ig)
    else:
        print("  Goodbye!")


def main():
    parser = argparse.ArgumentParser(description="Quote Shorts Video Generator")
    parser.add_argument("--mode", choices=["single", "batch", "interactive"], default="interactive",
                        help="Generation mode (default: interactive)")
    parser.add_argument("--category", type=str, default="inspirational",
                        help="Quote category (inspirational, wisdom, success, life, motivation)")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of quotes (default: 1)")
    parser.add_argument("--language", type=str, default=config.DEFAULT_LANGUAGE,
                        help="Quote language (e.g., en, hi). Use with --count>1 for single language.")
    parser.add_argument("--youtube", action="store_true", help="Upload to YouTube")
    args = parser.parse_args()

    if args.mode == "interactive":
        interactive_mode(args.youtube)
        return

    print(BANNER)
    print(SEP)
    if args.mode == "single":
        # If only one quote requested, generate both English and Hindi versions
        langs = ["en", "hi"] if args.count == 1 else [args.language]
        generate_single(args.category, args.count, args.youtube,
                        languages=langs, auto_confirm=True)
    else:
        generate_batch(args.category, args.count, args.youtube, auto_confirm=True)


if __name__ == "__main__":
    main()
