from collections.abc import Callable
import logging
import time

import pygame

from .devices.camera import Camera
from .devices.display import DisplayDevice, PygameDisplay
from .devices.filesystem import Filesystem
from .devices.input import InputDevice, PygameInput
from .devices.speaker import Speaker
from .modes.base import Mode, ModeContext, ModeRequest
from .modes.menu import Menu


logger = logging.getLogger(__name__)
ModeFactory = Callable[[ModeContext], Mode]


class App:
    def __init__(
        self,
        input_device: InputDevice | None = None,
        display_device: DisplayDevice | None = None,
        mode_factories: dict[str, ModeFactory] | None = None,
        filesystem: Filesystem | None = None,
        camera: Camera | None = None,
        speaker: Speaker | None = None,
        frame_rate: int = 60,
    ):
        self.filesystem = filesystem or Filesystem()
        self.filesystem.prepare_user_directories()
        self.context = ModeContext(
            filesystem=self.filesystem,
            camera=camera or Camera(),
            speaker=speaker or Speaker(),
            default_background=self.filesystem.load_image_asset("bg.png"),
        )

        self._owns_pygame = input_device is None or display_device is None
        if self._owns_pygame:
            pygame.init()

        self.input = input_device or PygameInput()
        self.display = display_device or PygameDisplay()
        if frame_rate <= 0:
            raise ValueError("frame_rate must be positive")
        self.frame_rate = frame_rate
        self.running = False

        self.mode_factories = (
            {"menu": lambda context: Menu(context)}
            if mode_factories is None
            else mode_factories
        )
        if "menu" not in self.mode_factories:
            raise ValueError("mode_factories must include a 'menu' factory")
        self.mode: Mode = self.mode_factories["menu"](self.context)

    def run(self) -> None:
        self.running = True
        frame_duration = 1 / self.frame_rate
        previous_frame = time.monotonic()
        try:
            while self.running:
                frame_start = time.monotonic()
                delta_time = min(max(frame_start - previous_frame, 0.0), 0.1)
                previous_frame = frame_start

                frame = self.input.poll()
                if frame.quit_requested:
                    self.running = False
                    continue

                request = self.mode.update(frame.actions, delta_time)
                if request is not None:
                    self._apply_mode_request(request)

                self.context.draw_default_background(self.display)
                self.mode.render(self.display)
                self.display.present()
                remaining = frame_duration - (time.monotonic() - frame_start)
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            if self._owns_pygame:
                pygame.quit()

    def stop(self) -> None:
        self.running = False

    def _apply_mode_request(self, request: ModeRequest) -> None:
        factory = self.mode_factories.get(request.target)
        if factory is None:
            logger.info("Ignoring request for unregistered mode '%s'", request.target)
            return
        self.mode = factory(self.context)


def run() -> None:
    App().run()
