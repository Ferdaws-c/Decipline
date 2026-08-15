"""
generate_assets.py — One-time script to generate alarm.wav and icon.ico.
Run: python generate_assets.py
"""

import os
import struct
import math
import wave
import array

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(ASSETS, exist_ok=True)


# ── Generate alarm.wav (calm 3-note chime) ────────────────────────────────────

def sine_wave(freq, duration, sample_rate=44100, amplitude=0.6):
    """Generate a sine wave with fade-in/fade-out envelope."""
    n_samples = int(sample_rate * duration)
    fade = int(sample_rate * 0.05)   # 50ms fade
    samples = []
    for i in range(n_samples):
        t   = i / sample_rate
        val = math.sin(2 * math.pi * freq * t)
        # Apply envelope
        env = 1.0
        if i < fade:
            env = i / fade
        elif i > n_samples - fade:
            env = (n_samples - i) / fade
        samples.append(val * env * amplitude)
    return samples


def generate_alarm_wav(path: str):
    """
    Three ascending chime notes: C5 → E5 → G5
    Calm, pleasant, but carrying enough to hear from another room.
    """
    sample_rate = 44100
    notes = [
        (523.25, 0.45),   # C5
        (659.25, 0.45),   # E5
        (783.99, 0.70),   # G5 — held a bit longer
    ]
    gap_samples = [0.0] * int(sample_rate * 0.12)   # 120ms gap between notes

    all_samples = []
    for freq, dur in notes:
        all_samples.extend(sine_wave(freq, dur, sample_rate))
        all_samples.extend(gap_samples)

    # Convert to 16-bit PCM
    pcm = array.array("h", [int(s * 32767) for s in all_samples])

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    print(f"[assets] Generated alarm.wav -> {path}")


# ── Generate icon.ico (amber ring logo) ───────────────────────────────────────

def generate_icon_ico(path: str):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[assets] Pillow not found, skipping icon generation")
        return

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer amber circle
        pad  = max(1, size // 16)
        draw.ellipse([pad, pad, size - pad, size - pad], fill="#F59E0B")

        # Inner dark cutout (ring)
        inner_pad = max(3, int(size * 0.28))
        draw.ellipse(
            [inner_pad, inner_pad, size - inner_pad, size - inner_pad],
            fill="#1C1C1E"
        )

        # Small white dot in center
        dot = max(1, size // 10)
        cx  = size // 2
        draw.ellipse([cx - dot, cx - dot, cx + dot, cx + dot], fill="#F5F5F7")

        images.append(img)

    images[0].save(path, format="ICO", sizes=[(s, s) for s in sizes],
                   append_images=images[1:])
    print(f"[assets] Generated icon.ico -> {path}")


if __name__ == "__main__":
    generate_alarm_wav(os.path.join(ASSETS, "alarm.wav"))
    generate_icon_ico(os.path.join(ASSETS, "icon.ico"))
    print("[assets] Done.")
