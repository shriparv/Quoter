import json
import random
import urllib.request
import urllib.error
from dataclasses import dataclass

@dataclass
class Quote:
    text: str
    author: str
    category: str = "general"

FALLBACK_QUOTES = [
    Quote("The only way to do great work is to love what you do.", "Steve Jobs", "inspirational"),
    Quote("In the middle of every difficulty lies opportunity.", "Albert Einstein", "wisdom"),
    Quote("Success is not final, failure is not fatal: it is the courage to continue that counts.", "Winston Churchill", "success"),
    Quote("Life is what happens when you're busy making other plans.", "John Lennon", "life"),
    Quote("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt", "inspirational"),
    Quote("It does not matter how slowly you go as long as you do not stop.", "Confucius", "wisdom"),
    Quote("Believe you can and you're halfway there.", "Theodore Roosevelt", "motivation"),
    Quote("The only impossible journey is the one you never begin.", "Tony Robbins", "motivation"),
    Quote("What lies behind us and what lies before us are tiny matters compared to what lies within us.", "Ralph Waldo Emerson", "wisdom"),
    Quote("The best time to plant a tree was 20 years ago. The second best time is now.", "Chinese Proverb", "wisdom"),
    Quote("Your time is limited, don't waste it living someone else's life.", "Steve Jobs", "inspirational"),
    Quote("The mind is everything. What you think you become.", "Buddha", "wisdom"),
    Quote("Strive not to be a success, but rather to be of value.", "Albert Einstein", "success"),
    Quote("Happiness is not something ready made. It comes from your own actions.", "Dalai Lama", "life"),
    Quote("The only person you are destined to become is the person you decide to be.", "Ralph Waldo Emerson", "motivation"),
    Quote("Everything you've ever wanted is on the other side of fear.", "George Addair", "motivation"),
    Quote("Do what you can, with what you have, where you are.", "Theodore Roosevelt", "inspirational"),
    Quote("The secret of getting ahead is getting started.", "Mark Twain", "success"),
    Quote("It's not whether you get knocked down, it's whether you get up.", "Vince Lombardi", "motivation"),
    Quote("The only limit to our realization of tomorrow will be our doubts of today.", "Franklin D. Roosevelt", "inspirational"),
]


class QuoteFetcher:
    def __init__(self, timeout: int = 10, language: str = "en"):
        self.timeout = timeout
        self.language = language

    def fetch_random(self, count: int = 5) -> list[Quote]:
        quotes = []
        for _ in range(count * 2):
            url = "https://api.quotable.io/random"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode())
                    quote = Quote(
                        text=data.get("content", "").strip().strip("\u201c").strip("\u201d"),
                        author=data.get("author", "Unknown"),
                        category=data.get("tags", ["general"])[0] if data.get("tags") else "general",
                    )
                    if quote.text and len(quote.text) > 20 and len(quote.text) < 250:
                        quotes.append(quote)
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
                pass
            if len(quotes) >= count:
                break
        if len(quotes) < count:
            extras = random.sample(FALLBACK_QUOTES, min(count - len(quotes), len(FALLBACK_QUOTES)))
            quotes.extend(extras)
        return quotes[:count]

    def fetch_by_category(self, category: str, count: int = 5) -> list[Quote]:
        url = f"https://api.quotable.io/quotes/random?limit={count}&tags={category}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    return [
                        Quote(
                            text=item.get("content", "").strip().strip("\u201c").strip("\u201d"),
                            author=item.get("author", "Unknown"),
                            category=category,
                        )
                        for item in data
                        if item.get("content")
                    ]
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            pass
        return random.sample(FALLBACK_QUOTES, min(count, len(FALLBACK_QUOTES)))
