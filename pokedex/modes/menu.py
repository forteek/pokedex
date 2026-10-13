from dataclasses import dataclass

from ..devices.display import DisplayDevice, PANEL_SIZE, Panel
from ..devices.filesystem import ImageAsset
from ..devices.input import Action
from .base import ModeContext, ModeRequest


@dataclass(frozen=True)
class MenuOption:
    name: str
    image: ImageAsset
    mode: str


class Menu:
    def __init__(self, context: ModeContext):
        self.options = (
            MenuOption("Camera", context.filesystem.load_ui("camera.png"), "camera"),
            MenuOption("Music", context.filesystem.load_ui("music.png"), "music"),
            MenuOption("Gallery", context.filesystem.load_ui("gallery.png"), "gallery"),
            MenuOption("Pokedex", context.filesystem.load_ui("pokedex.png"), "pokedex"),
        )
        self.position = 0.0
        self._start_position = 0.0
        self._target_position = 0
        self._transition_elapsed = 0.0
        self._transition_duration = 0.24

    @property
    def focused_option(self) -> int:
        return self._target_position % len(self.options)

    def update(self, actions: frozenset[Action], delta_time: float) -> ModeRequest | None:
        self._advance_transition(delta_time)

        if Action.LEFT in actions or Action.UP in actions:
            self._move(-1)
        elif Action.RIGHT in actions or Action.DOWN in actions:
            self._move(1)

        if Action.CONFIRM in actions:
            return ModeRequest(self.options[self.focused_option].mode)
        return None

    def _advance_transition(self, delta_time: float) -> None:
        if self.position == self._target_position:
            return

        self._transition_elapsed = min(
            self._transition_elapsed + max(delta_time, 0.0),
            self._transition_duration,
        )
        progress = self._transition_elapsed / self._transition_duration
        if progress < 0.5:
            eased = 4 * progress**3
        else:
            eased = 1 - ((-2 * progress + 2) ** 3) / 2

        self.position = self._start_position + (
            self._target_position - self._start_position
        ) * eased
        if progress == 1:
            self.position = float(self._target_position)

    def _move(self, direction: int) -> None:
        self._start_position = self.position
        self._target_position += direction
        self._transition_elapsed = 0.0

    def render(self, display: DisplayDevice) -> None:
        center_x = PANEL_SIZE[0] // 2
        gap = 105
        for index, option in enumerate(self.options):
            offset = (index - self.position + len(self.options) / 2) % len(self.options)
            offset -= len(self.options) / 2

            size = round(104 - min(abs(offset), 1) * 40)
            x = center_x + offset * gap - size // 2
            y = (PANEL_SIZE[1] - size) // 2
            display.draw_image(Panel.MAIN, option.image, (x, y, size, size))
