import logging
from concurrent.futures import Future, ThreadPoolExecutor

from ..devices.display import DisplayDevice, PANEL_SIZE, Panel
from ..devices.filesystem import ImageAsset
from ..devices.recognition import PokemonRecognition, RecognitionDependencyError
from .base import ModeContext


logger = logging.getLogger(__name__)


class PokemonScanFlow:
    MIN_CONFIDENCE = 0.2
    MIN_SCAN_DURATION = 0.9
    SCAN_LINE_SPEED = 0.7
    ENTRY_FADE_DURATION = 0.35

    def __init__(self, context: ModeContext):
        self.context = context
        self.backgrounds = context.filesystem.load_backgrounds()
        self.pokemon_types = context.filesystem.list_pokemon_types()
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="pokemon-scan",
        )
        self._photo: ImageAsset | None = None
        self._future: Future[PokemonRecognition | None] | None = None
        self._scan_elapsed = 0.0
        self._candidate: PokemonRecognition | None = None
        self._scan_completed = False
        self._entry_active = False
        self._entry_background: ImageAsset | None = None
        self._entry_sprite: ImageAsset | None = None
        self._entry_opacity = 0.0
        self._fade_start = 0.0
        self._fade_target = 0.0
        self._fade_elapsed = self.ENTRY_FADE_DURATION
        self._entry_audio_active = False

    @property
    def is_scanning(self) -> bool:
        return self._future is not None

    @property
    def scan_elapsed(self) -> float:
        return self._scan_elapsed

    def start(self, photo: ImageAsset) -> None:
        if (
            self.is_scanning
            and self._photo is not None
            and self._photo.name == photo.name
        ):
            return

        self.cancel()
        self._photo = photo
        self._scan_elapsed = 0.0
        try:
            saved_result = self.context.filesystem.load_scan_result(photo.name)
        except Exception:
            logger.exception("Could not load saved Pokémon scan for %s", photo.name)
            saved_result = None

        if saved_result is not None:
            self._handle_result(saved_result)
            return

        self._future = self._executor.submit(
            self.context.pokemon_recognizer.recognize,
            photo.data,
        )

    def update(self, delta_time: float) -> None:
        delta_time = max(delta_time, 0.0)
        self.context.speaker.update()
        self._advance_entry(delta_time)
        future = self._future
        if future is None:
            return

        self._scan_elapsed += delta_time
        if future.done() and not self._scan_completed:
            try:
                self._candidate = future.result()
            except RecognitionDependencyError as error:
                logger.error("%s", error)
                self._candidate = None
            except Exception:
                logger.exception("Pokémon scan failed")
                self._candidate = None
            self._scan_completed = True

        if not self._scan_completed or self._scan_elapsed < self.MIN_SCAN_DURATION:
            return

        self._future = None
        result = self._candidate
        self._candidate = None
        self._scan_completed = False
        if result is None:
            return

        if self._photo is not None:
            try:
                self.context.filesystem.save_scan_result(
                    self._photo.name,
                    result.pokemon_id,
                    result.confidence,
                )
            except Exception:
                logger.exception(
                    "Could not save Pokémon scan result for %s",
                    self._photo.name,
                )

        self._handle_result(result)

    def _handle_result(self, result: PokemonRecognition) -> None:
        if result.confidence < self.MIN_CONFIDENCE:
            unknown_voice = (
                self.context.filesystem.assets_dir
                / "mp3"
                / "ui"
                / "unknown.mp3"
            )
            self.context.speaker.play_voice_sequence([unknown_voice])
            return
        self._show_pokedex_entry(result)

    def _show_pokedex_entry(self, result: PokemonRecognition) -> None:
        primary_type, secondary_type = self.pokemon_types.get(
            result.pokemon_id,
            (None, None),
        )
        background_name = primary_type or "grass"
        self._entry_background = self.backgrounds.get(background_name)
        if self._entry_background is None:
            self._entry_background = self.backgrounds.get("grass")
        if self._entry_background is None:
            self._entry_background = self.context.default_background

        try:
            self._entry_sprite = self.context.filesystem.load_pokemon_asset(
                f"{result.pokemon_id}.png"
            )
        except FileNotFoundError:
            self._entry_sprite = None

        voice_paths = [
            self.context.filesystem.pokemon_voice_path(
                "names",
                str(result.pokemon_id),
            )
        ]
        if primary_type:
            type_name = (
                f"{primary_type}-{secondary_type}"
                if secondary_type
                else primary_type
            )
            voice_paths.append(
                self.context.filesystem.pokemon_voice_path("types", type_name)
            )
        voice_paths.append(
            self.context.filesystem.pokemon_voice_path(
                "flavor",
                str(result.pokemon_id),
            )
        )

        self._entry_active = True
        self._entry_opacity = 0.0
        self._entry_audio_active = self.context.speaker.play_voice_sequence(
            voice_paths
        )
        self._start_fade(1.0)

    def _start_fade(self, target: float) -> None:
        self._fade_start = self._entry_opacity
        self._fade_target = target
        self._fade_elapsed = 0.0

    def _advance_entry(self, delta_time: float) -> None:
        if not self._entry_active:
            return

        if self._fade_elapsed < self.ENTRY_FADE_DURATION:
            self._fade_elapsed = min(
                self._fade_elapsed + delta_time,
                self.ENTRY_FADE_DURATION,
            )
            progress = self._fade_elapsed / self.ENTRY_FADE_DURATION
            eased = progress * progress * (3 - 2 * progress)
            self._entry_opacity = self._fade_start + (
                self._fade_target - self._fade_start
            ) * eased
            if self._fade_elapsed < self.ENTRY_FADE_DURATION:
                return

            self._entry_opacity = self._fade_target
            if self._fade_target == 0.0:
                self._clear_entry()
                return

        if self._fade_target == 1.0:
            if (
                self._entry_audio_active
                and self.context.speaker.is_sequence_active
            ):
                return
            self._entry_audio_active = False
            self._start_fade(0.0)

    def render_scan_indicator(
        self,
        display: DisplayDevice,
        rect: tuple[int, int, int, int],
    ) -> None:
        if not self.is_scanning:
            return
        x, y, width, height = rect
        cycle = (self._scan_elapsed * self.SCAN_LINE_SPEED) % 2
        position = cycle if cycle <= 1 else 2 - cycle
        line_y = y + round(position * max(height - 2, 0))
        display.draw_rect(
            Panel.CONTEXT,
            (x, line_y, width, min(2, height)),
            (80, 255, 180),
        )

    def render_entry(self, display: DisplayDevice) -> None:
        if not self._entry_active:
            return

        alpha = round(self._entry_opacity * 255)
        if self._entry_background is not None:
            display.draw_image(
                Panel.CONTEXT,
                self._entry_background,
                (0, 0, *PANEL_SIZE),
                alpha=alpha,
            )
        if self._entry_sprite is not None:
            width, height = self._entry_sprite.original_size or (128, 128)
            x = (PANEL_SIZE[0] - width) // 2
            y = (PANEL_SIZE[1] - height) // 2
            display.draw_image(
                Panel.CONTEXT,
                self._entry_sprite,
                (x, y, width, height),
                alpha=alpha,
            )

    def cancel(self) -> None:
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self._candidate = None
        self._scan_completed = False
        self._clear_entry()
        self._photo = None
        self.context.speaker.stop()

    def _clear_entry(self) -> None:
        self._entry_active = False
        self._entry_background = None
        self._entry_sprite = None
        self._entry_opacity = 0.0
        self._fade_start = 0.0
        self._fade_target = 0.0
        self._fade_elapsed = self.ENTRY_FADE_DURATION
        self._entry_audio_active = False

    def on_exit(self) -> None:
        self.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
