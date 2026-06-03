import os
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import config


class BackgroundGenerator:
    # Curated modern, ultra-premium gradient color palettes
    COLOR_PALETTES = [
        # Sunset Glow (neon pink to vibrant orange)
        [(255, 0, 128), (255, 105, 180), (255, 120, 0)],
        # Ocean Breeze (neon teal to electric blue)
        [(0, 242, 254), (79, 172, 254), (0, 102, 204)],
        # Royal Amethyst (deep violet to bright orchid)
        [(194, 21, 224), (142, 45, 226), (74, 0, 224)],
        # Aurora Borealis (neon green to deep midnight blue)
        [(0, 255, 135), (96, 239, 255), (26, 42, 108)],
        # Cosmic Dust (rich indigo, deep purple, neon pink)
        [(15, 12, 75), (80, 20, 120), (255, 0, 128)],
        # Premium Charcoal & Gold (deep charcoal with shimmering gold)
        [(20, 20, 20), (40, 40, 40), (218, 165, 32)],
        # Sweet Candy (pink to purple to soft blue)
        [(255, 154, 158), (250, 208, 196), (196, 224, 229)],
        # Electric Violet (neon magenta to dark purple)
        [(241, 39, 17), (245, 175, 25), (100, 10, 80)]
    ]

    def __init__(self, width: int = None, height: int = None):
        self.width = width or config.VIDEO_WIDTH
        self.height = height or config.VIDEO_HEIGHT

    def generate_gradient(self, output_path: str | Path, palette: list[tuple] = None) -> str:
        if palette is None:
            palette = random.choice(self.COLOR_PALETTES)
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)
        bands = len(palette)
        band_height = self.height // bands
        for i in range(bands):
            y0 = i * band_height
            y1 = (i + 1) * band_height if i < bands - 1 else self.height
            for y in range(y0, y1):
                ratio = (y - y0) / band_height
                r = int(palette[i][0] * (1 - ratio) + palette[(i + 1) % bands][0] * ratio)
                g = int(palette[i][1] * (1 - ratio) + palette[(i + 1) % bands][1] * ratio)
                b = int(palette[i][2] * (1 - ratio) + palette[(i + 1) % bands][2] * ratio)
                draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, quality=95)
        return str(output_path)

    def generate_circular_gradient(self, output_path: str | Path, palette: list[tuple] = None) -> str:
        if palette is None:
            palette = random.choice(self.COLOR_PALETTES)
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)
        cx, cy = self.width // 2, self.height // 2
        max_radius = int(((cx ** 2 + cy ** 2) ** 0.5))
        for r in range(max_radius, 0, -1):
            ratio = r / max_radius
            idx = int(ratio * (len(palette) - 1))
            c = palette[idx] if idx < len(palette) else palette[-1]
            draw.ellipse(
                [(cx - r, cy - r), (cx + r, cy + r)],
                fill=(c[0], c[1], c[2]),
            )
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, quality=95)
        return str(output_path)

    def generate_pattern(self, output_path: str | Path, palette: list[tuple] = None) -> str:
        if palette is None:
            palette = random.choice(self.COLOR_PALETTES)
        base = Image.new("RGB", (self.width, self.height), palette[0])
        draw = ImageDraw.Draw(base)
        step = 80
        for x in range(0, self.width, step):
            for y in range(0, self.height, step):
                c = random.choice(palette[1:] if len(palette) > 1 else palette)
                shape = random.choice(["circle", "square", "diamond"])
                if shape == "circle":
                    draw.ellipse([(x, y), (x + step // 2, y + step // 2)], fill=c)
                elif shape == "square":
                    draw.rectangle([(x, y), (x + step // 2, y + step // 2)], fill=c)
                else:
                    draw.polygon(
                        [(x + step // 4, y), (x + step // 2, y + step // 4), (x + step // 4, y + step // 2), (x, y + step // 4)],
                        fill=c,
                    )
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        base.save(output_path, quality=95)
        return str(output_path)

    def generate_blended(self, image_path: str | Path, output_path: str | Path, palette: list[tuple] = None) -> str:
        """Loads a fetched image, crops/resizes it to portrait aspect ratio, blurs it, and blends it with a rich gradient overlay."""
        if not os.path.exists(image_path):
            # Fall back to custom random gradient if the image doesn't exist
            return self.generate_random(output_path)

        # Load image and convert to RGBA
        img = Image.open(image_path).convert("RGBA")
        
        # Center-crop & resize to fill the exact video dimensions (portrait aspect ratio)
        img_w, img_h = img.size
        aspect_ratio = img_w / img_h
        target_aspect = self.width / self.height
        if aspect_ratio > target_aspect:
            new_w = int(img_h * target_aspect)
            left = (img_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, img_h))
        else:
            new_h = int(img_w / target_aspect)
            top = (img_h - new_h) // 2
            img = img.crop((0, top, img_w, top + new_h))
            
        img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        # Apply heavy blur to keep the background abstract and aesthetic
        img = img.filter(ImageFilter.GaussianBlur(radius=15))

        # Generate a premium gradient overlay
        grad_img = Image.new("RGBA", (self.width, self.height))
        draw = ImageDraw.Draw(grad_img)
        if palette is None:
            palette = random.choice(self.COLOR_PALETTES)
            
        bands = len(palette)
        band_height = self.height // bands
        for i in range(bands):
            y0 = i * band_height
            y1 = (i + 1) * band_height if i < bands - 1 else self.height
            for y in range(y0, y1):
                ratio = (y - y0) / band_height
                r = int(palette[i][0] * (1 - ratio) + palette[(i + 1) % bands][0] * ratio)
                g = int(palette[i][1] * (1 - ratio) + palette[(i + 1) % bands][1] * ratio)
                b = int(palette[i][2] * (1 - ratio) + palette[(i + 1) % bands][2] * ratio)
                # Apply 140/255 transparency to beautifully overlay the gradient over the stock photo details
                draw.line([(0, y), (self.width, y)], fill=(r, g, b, 140))

        # Composite the blurred stock photo and the gradient overlay
        blended = Image.alpha_composite(img, grad_img)
        
        # Add a subtle vignette dimming layer for optimal readability of text
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 60))
        final = Image.alpha_composite(blended, overlay)
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.convert("RGB").save(output_path, "JPEG", quality=95)
        return str(output_path)

    def generate_random(self, output_path: str | Path) -> str:
        """Generate a random background with gradient/circular/pattern.
        If generation fails, fallback to solid black background.
        """
        try:
            style = random.choice(["gradient", "circular", "pattern"])
            palette = random.choice(self.COLOR_PALETTES)
            if style == "gradient":
                return self.generate_gradient(output_path, palette)
            elif style == "circular":
                return self.generate_circular_gradient(output_path, palette)
            else:
                return self.generate_pattern(output_path, palette)
        except Exception as exc:
            # Log warning and create black background
            print(f"[WARNING] generate_random failed ({exc}), using black background.")
            black_path = Path(output_path)
            img = Image.new("RGB", (self.width, self.height), (0, 0, 0))
            img.save(black_path, quality=95)
            return str(black_path)
