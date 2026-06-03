import os
import re
import urllib.request
import urllib.parse
import urllib.error
import random
from pathlib import Path
import config

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "because", "as", "what", "how", "why", "where",
    "when", "who", "which", "this", "that", "these", "those", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "to", "for", "of", "in", "on",
    "at", "by", "with", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "from", "up", "down", "out", "over", "under", "again", "further",
    "then", "once", "here", "there", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t",
    "can", "will", "just", "should", "now", "i", "me", "my", "myself", "we", "our", "ours",
    "ourselves", "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself",
    "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs",
    "themselves", "dont", "cant", "isnt", "wasnt", "arent", "youre", "im", "weve", "theyre",
    "go", "long", "stop", "matter", "slowly", "always", "every", "lies", "does", "not"
}

class ImageFetcher:
    def __init__(self):
        self.cache_dir = config.BACKGROUNDS_DIR / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = 15

    def extract_keywords(self, quote_text: str) -> list[str]:
        # Normalize and find all word tokens
        clean_text = re.sub(r"[^\w\s]", "", quote_text.lower())
        words = clean_text.split()
        
        # Filter out stop words and short particles
        keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        
        # If no significant keywords remain, choose from default configuration
        if not keywords:
            keywords = random.sample(config.IMAGE_KEYWORDS_DEFAULT, min(2, len(config.IMAGE_KEYWORDS_DEFAULT)))
            
        return keywords[:3]

    def fetch_image_for_quote(self, quote_text: str) -> Path | None:
        """Extracts keywords and downloads a highly relevant 1080x1920 portrait photo to a local cache directory."""
        if not config.USE_DYNAMIC_IMAGES:
            print("  [i] Dynamic images disabled in config. Using fallback backgrounds.")
            return None

        keywords = self.extract_keywords(quote_text)
        # Append general aesthetic terms to focus on stunning backgrounds rather than literal portraits of people
        query_words = keywords + ["nature", "aesthetic"]
        query_string = ",".join(query_words)
        
        # Generate a unique hash for the cached image name
        safe_filename = f"bg_{abs(hash(query_string)) % 100000}.jpg"
        cached_path = self.cache_dir / safe_filename
        
        # Check if already cached
        if cached_path.exists():
            return cached_path

        # Use Lorem Flickr for ultra-stable, high-quality keyword image fetching
        url = f"https://loremflickr.com/1080/1920/{urllib.parse.quote(query_string)}/all"
        
        print(f"  [*] Fetching aesthetic image for keywords: {', '.join(keywords)}...")
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                image_data = resp.read()
                
            # Basic validation that we received a real image (usually JPEG starts with \xff\xd8)
            if len(image_data) > 1000 and image_data.startswith(b"\xff\xd8") or image_data.startswith(b"\x89PNG"):
                with open(cached_path, "wb") as f:
                    f.write(image_data)
                print(f"  [OK] Saved stock photo to cache: {safe_filename}")
                return cached_path
            else:
                print("  [WARNING] Fetched data does not appear to be a valid image.")
                return None
        except Exception as exc:
            print(f"  [WARNING] Could not fetch image online: {exc}. Falling back to default background.")
            return None
