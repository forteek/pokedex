from dataclasses import dataclass
from typing import Protocol

from ..devices.camera import Camera
from ..devices.display import DisplayDevice, PANEL_SIZE, Panel
from ..devices.filesystem import ImageAsset
from ..devices.filesystem import Filesystem
from ..devices.input import Action
from ..devices.recognition import PokemonRecognizer
from ..devices.speaker import Speaker


@dataclass(frozen=True)
class ModeRequest:
    """A request for the app to switch to another registered mode."""

    target: str


@dataclass(frozen=True)
class ModeContext:
    filesystem: Filesystem
    camera: Camera
    speaker: Speaker
    pokemon_recognizer: PokemonRecognizer
    default_background: ImageAsset

    def draw_default_background(self, display: DisplayDevice) -> None:
        for panel in Panel:
            display.draw_image(panel, self.default_background, (0, 0, *PANEL_SIZE))


class Mode(Protocol):
    def update(self, actions: frozenset[Action], delta_time: float) -> ModeRequest | None: ...

    def render(self, display: DisplayDevice) -> None: ...
