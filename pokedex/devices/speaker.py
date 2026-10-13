from pathlib import Path

import pygame


class Speaker:
    """Pygame audio adapter for streamed music playback."""

    def __init__(self):
        self._paused = False
        self.error: str | None = None

    def play(self, path: Path) -> bool:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
        except pygame.error as error:
            self.error = str(error)
            self._paused = False
            return False

        self.error = None
        self._paused = False
        return True

    def pause(self) -> None:
        if self.is_playing():
            pygame.mixer.music.pause()
            self._paused = True

    def resume(self) -> None:
        if self._paused:
            pygame.mixer.music.unpause()
            self._paused = False

    def stop(self) -> None:
        if pygame.mixer.get_init() is not None:
            pygame.mixer.music.stop()
        self._paused = False

    def is_playing(self) -> bool:
        return pygame.mixer.get_init() is not None and pygame.mixer.music.get_busy()

    def is_paused(self) -> bool:
        return self._paused

    def position_seconds(self) -> float:
        if pygame.mixer.get_init() is None:
            return 0.0
        position_ms = pygame.mixer.music.get_pos()
        return max(position_ms, 0) / 1000
