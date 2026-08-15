"""
alarm.py — Plays the bundled alarm sound in a non-blocking thread.
The alarm fires ONLY when a break ends, not when work ends.
"""

import os
import threading

_mixer_ready = False


def _init_mixer():
    global _mixer_ready
    if _mixer_ready:
        return True
    try:
        import pygame
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        _mixer_ready = True
        return True
    except Exception:
        return False


def _asset(filename: str) -> str:
    """Resolve path to assets/ relative to project root."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", filename)


def play_alarm(repeats: int = 3, gap_seconds: float = 1.5):
    """
    Play alarm.wav `repeats` times with a gap between each.
    Non-blocking — runs in a daemon thread.
    """
    def _play():
        try:
            import pygame
            if not _init_mixer():
                return
            path = _asset("alarm.wav")
            if not os.path.exists(path):
                return
            sound = pygame.mixer.Sound(path)
            sound.set_volume(0.85)
            for _ in range(repeats):
                sound.play()
                # Wait until this play finishes + gap
                import time
                time.sleep(sound.get_length() + gap_seconds)
        except Exception:
            pass

    t = threading.Thread(target=_play, daemon=True)
    t.start()


def stop_alarm():
    try:
        import pygame
        if _mixer_ready:
            pygame.mixer.stop()
    except Exception:
        pass
