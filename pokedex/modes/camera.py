from ..devices.display import DisplayDevice, PANEL_SIZE, Panel
from ..devices.input import Action
from .base import ModeContext, ModeRequest
from .pokemon_scan import PokemonScanFlow


class CameraView:
    PHOTO_TRANSITION_DURATION = 0.22
    PREVIEW_INTERVAL = 1 / 30

    def __init__(self, context: ModeContext):
        self.context = context
        self.camera_available = context.camera.start()
        self.scan_flow = PokemonScanFlow(context)
        self.camera_frame = None
        self.last_photo = None
        self._preview_elapsed = self.PREVIEW_INTERVAL
        self._photo_transition_elapsed = self.PHOTO_TRANSITION_DURATION

    def update(self, actions: frozenset[Action], delta_time: float) -> ModeRequest | None:
        if Action.HOME in actions:
            return ModeRequest("menu")

        delta_time = max(delta_time, 0.0)
        if self.camera_available:
            self._preview_elapsed += delta_time
            if self._preview_elapsed >= self.PREVIEW_INTERVAL:
                self.camera_frame = self.context.camera.read_frame()
                self._preview_elapsed %= self.PREVIEW_INTERVAL

        if self.last_photo is not None:
            self._photo_transition_elapsed = min(
                self._photo_transition_elapsed + delta_time,
                self.PHOTO_TRANSITION_DURATION,
            )

        if Action.CONFIRM in actions and self.camera_available:
            photo = self.context.camera.capture()
            if photo is not None:
                self.scan_flow.cancel()
                self.last_photo = self.context.filesystem.save_photo(photo)
                self._photo_transition_elapsed = 0.0

        if (
            Action.SCAN in actions
            and self.last_photo is not None
            and not self.scan_flow.is_scanning
        ):
            self.scan_flow.start(self.last_photo)
        self.scan_flow.update(delta_time)
        return None

    def render(self, display: DisplayDevice) -> None:
        if self.camera_frame is None:
            message = "Camera unavailable"
            if not self.camera_available:
                error = getattr(self.context.camera, "error", None)
                if error:
                    message = error
            display.draw_text(Panel.MAIN, message, (20, PANEL_SIZE[1] // 2 - 12))
        else:
            display.draw_camera_frame(
                Panel.MAIN,
                self.camera_frame,
                (0, 0, PANEL_SIZE[0], PANEL_SIZE[1]),
            )

        if self.last_photo is not None:
            progress = self._photo_transition_elapsed / self.PHOTO_TRANSITION_DURATION
            eased = 1 - (1 - progress) ** 3
            width = round(72 + (PANEL_SIZE[0] - 72) * eased)
            height = round(54 + (PANEL_SIZE[1] - 54) * eased)
            x = (PANEL_SIZE[0] - width) // 2
            y = (PANEL_SIZE[1] - height) // 2
            display.draw_image(
                Panel.CONTEXT,
                self.last_photo,
                (x, y, width, height),
            )
            self.scan_flow.render_scan_indicator(
                display,
                (x, y, width, height),
            )

        self.scan_flow.render_entry(display)

    def on_exit(self) -> None:
        self.scan_flow.on_exit()
        self.context.camera.stop()
