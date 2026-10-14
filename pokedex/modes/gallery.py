import math
import random

from ..devices.display import DisplayDevice, PANEL_SIZE, Panel
from ..devices.filesystem import ImageAsset
from ..devices.input import Action
from .base import ModeContext, ModeRequest
from .pokemon_scan import PokemonScanFlow


class Gallery:
    COLUMNS = 3
    VISIBLE_ROWS = 3
    THUMBNAIL_BUFFER_ROWS = 5
    THUMBNAIL_SIZE = (75, 50)
    CELL_WIDTH = PANEL_SIZE[0] // COLUMNS
    CELL_HEIGHT = PANEL_SIZE[1] // VISIBLE_ROWS
    SCROLL_DURATION = 0.24
    PHOTO_TRANSITION_DURATION = 0.18
    ROTATION_TRANSITION_DURATION = 0.2

    def __init__(self, context: ModeContext):
        self.context = context
        self.photos = context.filesystem.list_photos()
        self._photo_angles = {
            name: random.uniform(-10, 10)
            for name in self.photos
        }
        self._current_photo_angles = dict(self._photo_angles)
        if self.photos:
            self._current_photo_angles[self.photos[0]] = 0.0
        self._photo_angle_animations: dict[str, tuple[float, float, float]] = {}
        self.focused_index = 0
        self.scroll_position = 0.0
        self._scroll_start = 0.0
        self._scroll_target = 0.0
        self._scroll_elapsed = self.SCROLL_DURATION
        self._photo_transition_elapsed = self.PHOTO_TRANSITION_DURATION
        self._thumbnails: dict[str, ImageAsset] = {}
        self._full_photos: dict[int, ImageAsset] = {}
        self.scan_flow = PokemonScanFlow(context)
        self._refresh_asset_window()

    @property
    def total_rows(self) -> int:
        return math.ceil(len(self.photos) / self.COLUMNS)

    def update(self, actions: frozenset[Action], delta_time: float) -> ModeRequest | None:
        if Action.HOME in actions:
            return ModeRequest("menu")
        if not self.photos:
            return None

        self._advance_animations(max(delta_time, 0.0))
        old_index = self.focused_index
        column = old_index % self.COLUMNS

        if Action.LEFT in actions and column > 0:
            self.focused_index = old_index - 1
        elif Action.RIGHT in actions and column < self.COLUMNS - 1:
            if old_index + 1 < len(self.photos):
                self.focused_index = old_index + 1
        elif Action.UP in actions and old_index >= self.COLUMNS:
            self.focused_index = old_index - self.COLUMNS
        elif Action.DOWN in actions and old_index + self.COLUMNS < len(self.photos):
            self.focused_index = old_index + self.COLUMNS

        if self.focused_index != old_index:
            self._set_photo_angle_target(
                self.photos[old_index],
                self._photo_angles[self.photos[old_index]],
            )
            self._set_photo_angle_target(
                self.photos[self.focused_index],
                0.0,
            )
            self._retarget_scroll()
            self._photo_transition_elapsed = 0.0
            self._refresh_asset_window()
            self.scan_flow.cancel()

        if Action.SCAN in actions and not self.scan_flow.is_scanning:
            self._photo_transition_elapsed = self.PHOTO_TRANSITION_DURATION
            self.scan_flow.start(self._full_photos[self.focused_index])

        self.scan_flow.update(max(delta_time, 0.0))
        return None

    def _advance_animations(self, delta_time: float) -> None:
        if self.scroll_position != self._scroll_target:
            self._scroll_elapsed = min(
                self._scroll_elapsed + delta_time,
                self.SCROLL_DURATION,
            )
            progress = self._scroll_elapsed / self.SCROLL_DURATION
            eased = self._ease_in_out(progress)
            self.scroll_position = self._scroll_start + (
                self._scroll_target - self._scroll_start
            ) * eased
            if progress == 1:
                self.scroll_position = self._scroll_target

        self._advance_photo_angle_animations(delta_time)

        self._photo_transition_elapsed = min(
            self._photo_transition_elapsed + delta_time,
            self.PHOTO_TRANSITION_DURATION,
        )

    def _set_photo_angle_target(self, photo_name: str, target: float) -> None:
        current = self._current_photo_angles[photo_name]
        if abs(current - target) < 0.01:
            self._current_photo_angles[photo_name] = target
            self._photo_angle_animations.pop(photo_name, None)
            return
        self._photo_angle_animations[photo_name] = (current, target, 0.0)

    def _advance_photo_angle_animations(self, delta_time: float) -> None:
        for photo_name, (start, target, elapsed) in tuple(
            self._photo_angle_animations.items()
        ):
            elapsed = min(elapsed + delta_time, self.ROTATION_TRANSITION_DURATION)
            progress = elapsed / self.ROTATION_TRANSITION_DURATION
            eased = 3 * progress**2 - 2 * progress**3
            self._current_photo_angles[photo_name] = start + (target - start) * eased
            if progress >= 1:
                self._current_photo_angles[photo_name] = target
                del self._photo_angle_animations[photo_name]
            else:
                self._photo_angle_animations[photo_name] = (start, target, elapsed)

    def _retarget_scroll(self) -> None:
        focus_row = self.focused_index // self.COLUMNS
        last_start = max(0, self.total_rows - self.VISIBLE_ROWS)
        self._scroll_start = self.scroll_position
        self._scroll_target = min(max(focus_row - 1, 0), last_start)
        self._scroll_elapsed = 0.0

    def _refresh_asset_window(self) -> None:
        if not self.photos:
            self._thumbnails.clear()
            self._full_photos.clear()
            return

        focus_row = self.focused_index // self.COLUMNS
        first_row = max(0, focus_row - self.THUMBNAIL_BUFFER_ROWS)
        last_row = min(
            self.total_rows - 1,
            focus_row + self.THUMBNAIL_BUFFER_ROWS,
        )
        first_index = first_row * self.COLUMNS
        last_index = min(len(self.photos), (last_row + 1) * self.COLUMNS)
        wanted_thumbnails = self.photos[first_index:last_index]
        old_thumbnails = self._thumbnails
        self._thumbnails = {
            name: old_thumbnails.get(name)
            or self.context.filesystem.load_photo_thumbnail_asset(name)
            for name in wanted_thumbnails
        }

        focus_column = self.focused_index % self.COLUMNS
        focus_row = self.focused_index // self.COLUMNS
        neighbors = []
        if focus_column > 0:
            neighbors.append(self.focused_index - 1)
        if focus_column < self.COLUMNS - 1 and self.focused_index + 1 < len(self.photos):
            neighbors.append(self.focused_index + 1)
        if focus_row > 0:
            neighbors.append(self.focused_index - self.COLUMNS)
        if self.focused_index + self.COLUMNS < len(self.photos):
            neighbors.append(self.focused_index + self.COLUMNS)
        wanted_full_photos = [
            self.focused_index,
            *neighbors,
        ]
        old_full_photos = self._full_photos
        self._full_photos = {
            index: old_full_photos.get(index)
            or self.context.filesystem.load_photo_asset(self.photos[index])
            for index in dict.fromkeys(wanted_full_photos)
        }

    def render(self, display: DisplayDevice) -> None:
        if not self.photos:
            display.draw_text(Panel.MAIN, "No photos yet", (16, 108))
            display.draw_text(Panel.CONTEXT, "Take a photo in Camera", (16, 108))
            return

        first_visible_row = max(0, math.floor(self.scroll_position))
        last_visible_row = min(
            self.total_rows,
            math.ceil(self.scroll_position + self.VISIBLE_ROWS),
        )
        for row in range(first_visible_row, last_visible_row):
            for column in range(self.COLUMNS):
                photo_index = row * self.COLUMNS + column
                if photo_index >= len(self.photos):
                    break

                is_focused = photo_index == self.focused_index
                angle = self._current_photo_angles[self.photos[photo_index]]
                image_size = (
                    (84, 56) if is_focused else self.THUMBNAIL_SIZE
                )
                image_x = column * self.CELL_WIDTH + (self.CELL_WIDTH - image_size[0]) // 2
                image_y = round(
                    (row - self.scroll_position) * self.CELL_HEIGHT
                    + (self.CELL_HEIGHT - image_size[1]) // 2
                )
                display.draw_shadow(
                    Panel.MAIN,
                    (image_x, image_y, *image_size),
                    angle=angle,
                )
                if is_focused:
                    display.draw_rect(
                        Panel.MAIN,
                        (image_x - 3, image_y - 3, image_size[0] + 6, image_size[1] + 6),
                        (255, 214, 64),
                    )

                thumbnail = self._thumbnails[self.photos[photo_index]]
                display.draw_rotated_image(
                    Panel.MAIN,
                    thumbnail,
                    (
                        image_x + image_size[0] // 2,
                        image_y + image_size[1] // 2,
                    ),
                    image_size,
                    angle,
                )

        focused_photo = self._full_photos[self.focused_index]
        progress = self._photo_transition_elapsed / self.PHOTO_TRANSITION_DURATION
        eased = 1 - (1 - progress) ** 3
        width = round(240 + (PANEL_SIZE[0] - 240) * eased)
        height = round(180 + (PANEL_SIZE[1] - 180) * eased)
        x = (PANEL_SIZE[0] - width) // 2
        y = (PANEL_SIZE[1] - height) // 2
        display.draw_image(Panel.CONTEXT, focused_photo, (x, y, width, height))
        self.scan_flow.render_scan_indicator(
            display,
            (x, y, width, height),
        )
        self.scan_flow.render_entry(display)

    def on_exit(self) -> None:
        self.scan_flow.on_exit()

    def _ease_in_out(self, progress: float) -> float:
        if progress < 0.5:
            return 4 * progress**3
        return 1 - ((-2 * progress + 2) ** 3) / 2
