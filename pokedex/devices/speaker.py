from pathlib import Path

import pygame


class Speaker:
    """Pygame audio adapter for streamed music playback."""

    def __init__(self):
        self._paused = False
        self._sequence_active = False
        self._sequence_paths: list[Path] = []
        self._voice_playback = False
        self._current_path: Path | None = None
        self.error: str | None = None

    def play(self, path: Path) -> bool:
        self._sequence_active = False
        self._sequence_paths.clear()
        self._voice_playback = False
        return self._play_path(path)

    def play_voice(self, path: Path) -> bool:
        self._sequence_active = False
        self._sequence_paths.clear()
        self._voice_playback = self._play_path(path)
        return self._voice_playback

    def play_voice_sequence(self, paths: list[Path]) -> bool:
        available_paths = [path for path in paths if path.is_file()]
        self.stop()
        if not available_paths:
            return False

        self._sequence_paths = available_paths[1:]
        self._sequence_active = True
        self._voice_playback = True
        if self._play_path(available_paths[0]):
            return True
        self.update()
        return self._sequence_active

    def queue_voice_sequence(self, paths: list[Path]) -> bool:
        available_paths = [path for path in paths if path.is_file()]
        if not self.is_voice_playing():
            return self.play_voice_sequence(available_paths)

        self._sequence_paths = available_paths
        self._sequence_active = bool(available_paths)
        return self._sequence_active

    def _play_path(self, path: Path) -> bool:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
        except pygame.error as error:
            self.error = str(error)
            self._paused = False
            self._current_path = None
            return False

        self.error = None
        self._paused = False
        self._current_path = path
        return True

    def update(self) -> None:
        if self._paused or self.is_playing():
            return

        self._current_path = None
        if not self._sequence_active:
            self._voice_playback = False
            return

        while self._sequence_paths:
            next_path = self._sequence_paths.pop(0)
            if self._play_path(next_path):
                return
        self._sequence_active = False
        self._voice_playback = False

    def fade_voice(self, duration_ms: int) -> None:
        if not self._voice_playback:
            return

        if pygame.mixer.get_init() is not None:
            pygame.mixer.music.fadeout(max(0, duration_ms))
        self._paused = False
        self._sequence_active = False
        self._sequence_paths.clear()
        self._voice_playback = False
        self._current_path = None

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
        self._sequence_active = False
        self._sequence_paths.clear()
        self._voice_playback = False
        self._current_path = None

    @property
    def is_sequence_active(self) -> bool:
        return self._sequence_active

    def is_voice_playing(self, path: Path | None = None) -> bool:
        return (
            self._voice_playback
            and self.is_playing()
            and (path is None or self._current_path == path)
        )

    def is_playing(self) -> bool:
        return pygame.mixer.get_init() is not None and pygame.mixer.music.get_busy()

    def is_paused(self) -> bool:
        return self._paused

    def position_seconds(self) -> float:
        if pygame.mixer.get_init() is None:
            return 0.0
        position_ms = pygame.mixer.music.get_pos()
        return max(position_ms, 0) / 1000
