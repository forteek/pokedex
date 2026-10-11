from dataclasses import dataclass
from typing import Protocol

from ..devices.camera import Camera
from ..devices.display import DisplayDevice
from ..devices.filesystem import Filesystem
from ..devices.input import Action
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


class Mode(Protocol):
    def update(self, actions: frozenset[Action], delta_time: float) -> ModeRequest | None: ...

    def render(self, display: DisplayDevice) -> None: ...
