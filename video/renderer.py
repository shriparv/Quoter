import os
import textwrap
import tempfile
from pathlib import Path
import numpy as np


try:
    from moviepy import (
        VideoClip, ImageClip, AudioFileClip, CompositeVideoClip,
        concatenate_videoclips
    )
    import moviepy.video.fx as vfx
    import moviepy.audio.fx as afx
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

import config


class VideoRenderer:
    CORNER_RADIUS = 50
    BORDER_WIDTH = 3
    BORDER_COLOR = (255, 255, 255, 50)

    def __init__(self):
        if not HAS_MOVIEPY:
            raise ImportError("moviepy is required. Install: pip install moviepy")
        if not HAS_PIL:
            raise ImportError("Pillow is required. Install: pip install Pillow")

    # ------------------------------------------------------------------
    # Rounded corners
    # ------------------------------------------------------------------
    def _create_rounded_mask(self, size=None):
        if size is None:
            size = (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
        w, h = size
        r = self.CORNER_RADIUS
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=r, fill=255)
        mask_path = Path(tempfile.gettempdir()) / f"rmask_{w}_{h}.png"
        mask.save(mask_path)
        border = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(border).rounded_rectangle(
            [(1, 1), (w - 2, h - 2)], radius=r,
            outline=self.BORDER_COLOR, width=self.BORDER_WIDTH,
        )
        border_path = Path(tempfile.gettempdir()) / f"rborder_{w}_{h}.png"
        border.save(border_path)
        return mask_path, border_path

    def _apply_rounded_corners(self, clip):
        mask_path, border_path = self._create_rounded_mask()
        mc = ImageClip(mask_path, is_mask=True, duration=clip.duration)
        bc = ImageClip(border_path, duration=clip.duration)
        return CompositeVideoClip(
            [clip.with_mask(mc), bc], size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
        )

    # ------------------------------------------------------------------
    # Background – blurred image with slow zoom
    # ------------------------------------------------------------------
    def _create_bg_layer(self, bg_path: str, duration: float):
        """Create background clip.
        - If a pre‑generated background image exists at *bg_path*, load it directly (no extra dim/blur).
        - If the file is missing, fall back to a gradient background; if that fails, use solid black.
        """
        if os.path.exists(bg_path):
            # Load the already‑blended background image produced by BackgroundGenerator
            bg_image = Image.open(bg_path).convert("RGBA")
        else:
            # Gradient fallback
            try:
                from moviepy.video.tools.drawing import color_gradient
                gradient = color_gradient(
                    size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
                    p1=(0, 0),
                    p2=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
                    color_1=config.GRADIENT_COLOR_START,
                    color_2=config.GRADIENT_COLOR_END,
                    shape="linear",
                ).astype(np.uint8)
                bg_image = Image.fromarray(gradient).convert("RGBA")
            except Exception as exc:
                print(f"[WARNING] Gradient generation failed ({exc}), using black background.")
                bg_image = Image.new("RGBA", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), (0, 0, 0, 255))
        # Save temporary image and create clip with subtle zoom effect
        tmp = Path(tempfile.gettempdir()) / f"bg_base_{abs(hash(bg_path))}.png"
        bg_image.save(tmp)
        clip = ImageClip(str(tmp), duration=duration)
        clip = clip.with_effects([vfx.Resize(lambda t: 1.0 + 0.03 * (t / duration))])
        return clip

    def _create_vignette(self, duration: float):
        w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy = w // 2, h // 2
        max_r = int(max(w, h) * 0.7)
        for r in range(max_r, 0, -1):
            alpha = int(140 * (1 - r / max_r))
            draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(0, 0, 0, alpha))
        tmp = Path(tempfile.gettempdir()) / "vignette.png"
        img.save(tmp)
        return ImageClip(str(tmp), duration=duration)

    # ------------------------------------------------------------------
    # Animated text – staggered fade‑in + slide‑up per line
    # ------------------------------------------------------------------
    def _create_animated_text(self, quote_text: str, author: str, duration: float):
        w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT

        text_len = len(quote_text)
        if text_len < 50:
            body_pt = 68
            wrap = 20
        elif text_len < 100:
            body_pt = 54
            wrap = 25
        elif text_len < 150:
            body_pt = 46
            wrap = 30
        else:
            body_pt = 36
            wrap = 38
        author_pt = int(body_pt * 0.65)

        try:
            font_body = ImageFont.truetype("arialbd.ttf", body_pt)
            font_author = ImageFont.truetype("arial.ttf", author_pt)
        except (OSError, IOError):
            font_body = ImageFont.load_default()
            font_author = ImageFont.load_default()

        lines = textwrap.wrap(quote_text, width=wrap)
        line_h = int(body_pt * 1.3)
        total_text_h = len(lines) * line_h
        text_start_y = (h - total_text_h) // 2 - 40

        # Pre‑render each line onto its own RGBA layer
        line_layers = []
        for ln in lines:
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            bb = draw.textbbox((0, 0), ln, font=font_body)
            tw = bb[2] - bb[0]
            x = (w - tw) // 2
            y = text_start_y
            # shadow
            draw.text((x + 2, y + 2), ln, fill=(0, 0, 0, 160), font=font_body)
            draw.text((x, y), ln, fill=(255, 255, 255, 248), font=font_body)
            line_layers.append(layer)
            text_start_y += line_h

        # Author layer
        author_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_a = ImageDraw.Draw(author_layer)
        author_text = f"\u2014 {author}"
        ba = draw_a.textbbox((0, 0), author_text, font=font_author)
        aw = ba[2] - ba[0]
        ax = (w - aw) // 2
        ay = text_start_y + 25
        draw_a.text((ax + 1, ay + 1), author_text, fill=(0, 0, 0, 120), font=font_author)
        draw_a.text((ax, ay), author_text, fill=(200, 200, 200, 230), font=font_author)

        per_line = 2.0
        author_t = len(lines) * per_line + 0.3

        def make_frame(t):
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            # Render each line with staggered fade‑in + slide‑up
            for li, layer in enumerate(line_layers):
                start = li * per_line
                if t < start:
                    continue
                local = t - start
                if local < 0.5:
                    alpha = int(255 * local / 0.5)
                    slide = int(25 * (1 - local / 0.5))
                else:
                    alpha = 255
                    slide = 0
                # Copy layer and set its global alpha
                l = layer.copy()
                r, g, b, a = l.split()
                a = a.point(lambda v: min(v, alpha))
                l = Image.merge("RGBA", (r, g, b, a))
                canvas.paste(l, (0, slide), l)
            # Author – fade in
            if t >= author_t:
                local_a = t - author_t
                a_alpha = min(255, int(255 * local_a / 0.5))
                al = author_layer.copy()
                r, g, b, a = al.split()
                a = a.point(lambda v: min(v, a_alpha))
                al = Image.merge("RGBA", (r, g, b, a))
                canvas.paste(al, (0, 0), al)
            return np.array(canvas.convert("RGB"))

        return VideoClip(make_frame, duration=duration)

    # ------------------------------------------------------------------
    # CTA clip
    # ------------------------------------------------------------------
    def _create_cta_clip(self, duration: float = 3.0):
        w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
        try:
            font = ImageFont.truetype("arialbd.ttf", 58)
        except (OSError, IOError):
            font = ImageFont.load_default()
        lines = ["Follow for more", "inspiring quotes!"]

        def make_frame(t):
            fade = min(1.0, t / 0.4)
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            for i, ln in enumerate(lines):
                bb = draw.textbbox((0, 0), ln, font=font)
                tw = bb[2] - bb[0]
                x = (w - tw) // 2
                y = h // 2 - 60 + i * 90
                draw.text((x + 2, y + 2), ln, fill=(0, 0, 0, int(140 * fade)), font=font)
                draw.text((x, y), ln, fill=(255, 255, 255, int(240 * fade)), font=font)
            return np.array(img.convert("RGB"))

        return VideoClip(make_frame, duration=duration)

    # ------------------------------------------------------------------
    def _composite_with_transitions(self, clips, transition_type=None, transition_duration=None):
        if transition_type is None:
            transition_type = config.SLIDE_TRANSITION_TYPE
        if transition_duration is None:
            transition_duration = config.SLIDE_TRANSITION_DURATION

        timed_clips = []
        current_time = 0.0
        
        for i, clip in enumerate(clips):
            if i == 0:
                timed_clip = clip.with_start(0)
                current_time = clip.duration
            else:
                # Calculate overlapping start time
                start_time = max(0.0, current_time - transition_duration)
                timed_clip = clip.with_start(start_time)
                
                # Apply high-end transition effects
                if transition_type == "crossfade":
                    timed_clip = timed_clip.with_effects([vfx.FadeIn(transition_duration)])
                elif transition_type == "slide_left":
                    timed_clip = timed_clip.with_position(
                        lambda t: (int(config.VIDEO_WIDTH * (1.0 - min(1.0, t / transition_duration))), 0)
                    )
                elif transition_type == "slide_right":
                    timed_clip = timed_clip.with_position(
                        lambda t: (int(-config.VIDEO_WIDTH * (1.0 - min(1.0, t / transition_duration))), 0)
                    )
                elif transition_type == "fade":
                    timed_clip = timed_clip.with_effects([vfx.FadeIn(transition_duration)])
                
                current_time = start_time + clip.duration
            timed_clips.append(timed_clip)
            
        return CompositeVideoClip(timed_clips, size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)).with_duration(current_time)

    # ------------------------------------------------------------------
    # Public API – single quote
    # ------------------------------------------------------------------
    def render_single_quote(self, quote_text: str, author: str, bg_path: str,
                            output_path: str | Path, bgmusic_path: str = None) -> str:
        dur = config.TEXT_DISPLAY_SECONDS
        bg_layer = self._create_bg_layer(bg_path, dur)
        vignette = self._create_vignette(dur)
        text_clip = self._create_animated_text(quote_text, author, dur)
        quote_scene = CompositeVideoClip([bg_layer, vignette, text_clip],
                                          size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)).with_duration(dur)

        cta_scene = self._create_cta_clip(3.0)

        # Smooth overlapping transition between scene and CTA
        clip = self._composite_with_transitions([quote_scene, cta_scene])
        clip = self._apply_rounded_corners(clip)

        bgm = None
        if bgmusic_path:
            bgm = AudioFileClip(bgmusic_path)
            bgm = bgm.with_effects([afx.AudioLoop(duration=clip.duration), afx.MultiplyVolume(config.BG_MUSIC_VOLUME)])
            clip = clip.with_audio(bgm)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clip.write_videofile(str(output_path), fps=config.VIDEO_FPS,
                             codec="libx264", audio_codec="aac",
                             bitrate=config.VIDEO_BITRATE, logger=None)
        clip.close()
        if bgm:
            bgm.close()
        return str(output_path)

    # ------------------------------------------------------------------
    # Public API – compilation
    # ------------------------------------------------------------------
    def render_compilation(self, quotes: list, bg_paths: list[str],
                           output_path: str | Path, bgmusic_path: str = None) -> str:
        all_clips = []
        for i, q in enumerate(quotes):
            bg = bg_paths[i] if i < len(bg_paths) else bg_paths[-1]
            dur = config.TEXT_DISPLAY_SECONDS
            bg_layer = self._create_bg_layer(bg, dur)
            vignette = self._create_vignette(dur)
            text_clip = self._create_animated_text(q.text, q.author, dur)
            scene = CompositeVideoClip([bg_layer, vignette, text_clip],
                                       size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)).with_duration(dur)
            all_clips.append(scene)

        cta = self._create_cta_clip(3.0)
        all_clips.append(cta)
        
        # Smooth overlapping transitions between all slides & CTA
        final = self._composite_with_transitions(all_clips)
        final = self._apply_rounded_corners(final)

        bgm = None
        if bgmusic_path:
            bgm = AudioFileClip(bgmusic_path)
            bgm = bgm.with_effects([afx.AudioLoop(duration=final.duration), afx.MultiplyVolume(config.BG_MUSIC_VOLUME)])
            final = final.with_audio(bgm)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(str(output_path), fps=config.VIDEO_FPS,
                              codec="libx264", audio_codec="aac",
                              bitrate=config.VIDEO_BITRATE, logger=None)
        final.close()
        if bgm:
            bgm.close()
        for c in all_clips:
            c.close()
        return str(output_path)

