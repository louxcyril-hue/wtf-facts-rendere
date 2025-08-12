import os, math, tempfile, base64, requests
from typing import List, Optional
from PIL import Image
from moviepy.editor import (ImageClip, AudioFileClip, concatenate_videoclips,
                            CompositeVideoClip, TextClip, vfx)

TARGET_W = int(os.getenv("TARGET_WIDTH", 1080))
TARGET_H = int(os.getenv("TARGET_HEIGHT", 1920))
MIN_DUR = float(os.getenv("MIN_DURATION", 50))
MAX_DUR = float(os.getenv("MAX_DURATION", 60))
THREADS = int(os.getenv("MOVIEPY_THREADS", 4))

def _dl(url: str, path: str):
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

def _write_b64(b64_str: str, path: str):
    data = base64.b64decode(b64_str.split(",")[-1])
    with open(path, "wb") as f:
        f.write(data)

def _fit_9x16(img_path: str):
    im = Image.open(img_path).convert("RGB")
    w, h = im.size
    target_ratio = TARGET_W / TARGET_H
    ratio = w / h
    if ratio > target_ratio:
        new_w = int(h * target_ratio)
        x = (w - new_w) // 2
        im = im.crop((x, 0, x + new_w, h))
    else:
        new_h = int(w / target_ratio)
        y = (h - new_h) // 2
        im = im.crop((0, y, w, y + new_h))
    im = im.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    im.save(img_path, "JPEG", quality=95)

def _ken_burns(clip: ImageClip, zoom=1.06):
    return clip.fx(vfx.resize, lambda t: 1 + (zoom - 1) * (t / max(0.001, clip.duration)))

def _safe_duration(audio_dur: float) -> float:
    return max(MIN_DUR, min(MAX_DUR, audio_dur))

def render_video(payload: dict, out_path: str) -> float:
    """
    Accepts either URLs or base64 for images and voice:
      - image_urls: list[str] OR image_b64: list[str]
      - voice_url: str OR voice_b64: str
    Writes MP4 to out_path, returns duration in seconds.
    """
    script = payload["script"]
    images_urls = payload.get("image_urls") or []
    images_b64 = payload.get("image_b64") or []
    voice_url = payload.get("voice_url")
    voice_b64 = payload.get("voice_b64")
    music_url = payload.get("music_url")
    watermark_text = payload.get("watermark_text")
    brand_color_hex = payload.get("brand_color_hex", "#ffffff")

    if not images_urls and not images_b64:
        raise ValueError("Provide image_urls or image_b64")
    if not voice_url and not voice_b64:
        raise ValueError("Provide voice_url or voice_b64")

    from moviepy.audio.AudioClip import CompositeAudioClip

    with tempfile.TemporaryDirectory() as td:
        img_paths = []
        # write images
        if images_b64:
            for i, b in enumerate(images_b64, 1):
                p = os.path.join(td, f"img{i}.jpg")
                _write_b64(b, p)
                _fit_9x16(p)
                img_paths.append(p)
        else:
            for i, url in enumerate(images_urls, 1):
                p = os.path.join(td, f"img{i}.jpg")
                _dl(url, p)
                _fit_9x16(p)
                img_paths.append(p)

        # voice
        voice_path = os.path.join(td, "voice.mp3")
        if voice_b64:
            _write_b64(voice_b64, voice_path)
        else:
            _dl(voice_url, voice_path)

        voice = AudioFileClip(voice_path)
        final_dur = _safe_duration(voice.duration)

        # music (optional)
        music_clip = None
        if music_url:
            music_path = os.path.join(td, "music.mp3")
            _dl(music_url, music_path)
            music_clip = AudioFileClip(music_path).volumex(0.12)

        # visuals
        seg = final_dur / len(img_paths)
        clips = []
        for p in img_paths:
            c = ImageClip(p).set_duration(seg)
            c = _ken_burns(c, zoom=1.06)
            clips.append(c)
        bg = concatenate_videoclips(clips, method="compose").set_duration(final_dur)

        # audio mix
        if music_clip:
            if music_clip.duration < final_dur:
                music_clip = music_clip.audio_loop(duration=final_dur)
            else:
                music_clip = music_clip.subclip(0, final_dur)
            composite_audio = CompositeAudioClip([voice.audio_fadein(0.05).audio_fadeout(0.2),
                                                  music_clip])
            bg = bg.set_audio(composite_audio)
        else:
            bg = bg.set_audio(voice)

        # watermark
        layers = [bg]
        if watermark_text:
            try:
                txt = TextClip(watermark_text, fontsize=52, color="white", font="Arial-Bold")
            except Exception:
                txt = TextClip(watermark_text, fontsize=52, color="white")
            txt = (txt
                   .margin(right=40, bottom=30, opacity=0)
                   .set_pos(("right", "bottom"))
                   .set_duration(final_dur)
                   .opacity(0.8))
            layers.append(txt)
        final = CompositeVideoClip(layers, size=(TARGET_W, TARGET_H)).set_duration(final_dur)

        final.write_videofile(out_path,
                              fps=30,
                              codec="libx264",
                              audio_codec="aac",
                              preset="medium",
                              threads=THREADS,
                              verbose=False,
                              logger=None)
        return final_dur
