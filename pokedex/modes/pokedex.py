import math
from pathlib import Path

from ..devices.display import DisplayDevice, PANEL_SIZE, Panel
from ..devices.filesystem import ImageAsset
from ..devices.input import Action
from .base import ModeContext, ModeRequest


class Pokedex:
    COLUMNS = 3
    VISIBLE_ROWS = 3
    BUFFER_ROWS = 2
    THUMBNAIL_SIZE = 58
    FOCUSED_SIZE = 72
    CELL_WIDTH = PANEL_SIZE[0] // COLUMNS
    CELL_HEIGHT = PANEL_SIZE[1] // VISIBLE_ROWS
    SCROLL_DURATION = 0.24
    HOVER_NAME_DELAY = 0.5
    SPRITE_SIZE = 128

    def __init__(self, context: ModeContext):
        self.context = context
        self.pokemon = context.filesystem.list_pokemon()
        self.backgrounds = context.filesystem.load_backgrounds()
        self.pokemon_types = context.filesystem.list_pokemon_types()
        self.focused_index = 0
        self._hover_elapsed = 0.0
        self._hover_name_played = False
        self.scroll_position = 0.0
        self._scroll_start = 0.0
        self._scroll_target = 0.0
        self._scroll_elapsed = self.SCROLL_DURATION
        self._assets: dict[str, ImageAsset] = {}
        self._refresh_asset_window()

    @property
    def total_rows(self) -> int:
        return math.ceil(len(self.pokemon) / self.COLUMNS)

    def update(self, actions: frozenset[Action], delta_time: float) -> ModeRequest | None:
        delta_time = max(delta_time, 0.0)
        self.context.speaker.update()
        if Action.HOME in actions:
            self.context.speaker.stop()
            return ModeRequest("menu")
        if not self.pokemon:
            return None

        self._advance_scroll(delta_time)
        old_index = self.focused_index
        column = old_index % self.COLUMNS
        if Action.LEFT in actions and column > 0:
            self.focused_index -= 1
        elif Action.RIGHT in actions and column < self.COLUMNS - 1:
            if old_index + 1 < len(self.pokemon):
                self.focused_index += 1
        elif Action.UP in actions and old_index >= self.COLUMNS:
            self.focused_index -= self.COLUMNS
        elif Action.DOWN in actions and old_index + self.COLUMNS < len(self.pokemon):
            self.focused_index += self.COLUMNS

        if self.focused_index != old_index:
            self._retarget_scroll()
            self._refresh_asset_window()
            self.context.speaker.fade_voice(
                round(self.HOVER_NAME_DELAY * 1000)
            )
            self._hover_elapsed = 0.0
            self._hover_name_played = False

        if Action.CONFIRM in actions:
            pokemon_id = self._focused_pokemon_id()
            name_path = self.context.filesystem.pokemon_voice_path(
                "names",
                str(pokemon_id),
            )
            if (
                self._hover_name_played
                and self.context.speaker.is_voice_playing(name_path)
            ):
                self.context.speaker.queue_voice_sequence(
                    self._focused_type_flavor_voices()
                )
            else:
                self._play_focused_voice(include_name=not self._hover_name_played)
            self._hover_name_played = True
        elif not self._hover_name_played:
            self._hover_elapsed += delta_time
            if (
                self._hover_elapsed >= self.HOVER_NAME_DELAY
                and not self.context.speaker.is_sequence_active
            ):
                pokemon_id = self._focused_pokemon_id()
                name_path = self.context.filesystem.pokemon_voice_path(
                    "names",
                    str(pokemon_id),
                )
                if name_path.is_file():
                    self._hover_name_played = True
                    self.context.speaker.play_voice(name_path)
        return None

    def _focused_pokemon_id(self) -> int:
        return int(Path(self.pokemon[self.focused_index]).stem)

    def _play_focused_voice(self, include_name: bool) -> None:
        pokemon_id = self._focused_pokemon_id()
        paths = []
        if include_name:
            paths.append(
                self.context.filesystem.pokemon_voice_path(
                    "names",
                    str(pokemon_id),
                )
            )
        paths.extend(self._focused_type_flavor_voices())
        self.context.speaker.play_voice_sequence(paths)

    def _focused_type_flavor_voices(self) -> list[Path]:
        pokemon_id = self._focused_pokemon_id()
        primary_type, secondary_type = self.pokemon_types.get(
            pokemon_id,
            (None, None),
        )
        paths = []
        if primary_type:
            type_name = (
                f"{primary_type}-{secondary_type}"
                if secondary_type
                else primary_type
            )
            paths.append(
                self.context.filesystem.pokemon_voice_path("types", type_name)
            )
        paths.append(
            self.context.filesystem.pokemon_voice_path(
                "flavor",
                str(pokemon_id),
            )
        )
        return paths

    def _advance_scroll(self, delta_time: float) -> None:
        if self.scroll_position == self._scroll_target:
            return

        self._scroll_elapsed = min(
            self._scroll_elapsed + delta_time,
            self.SCROLL_DURATION,
        )
        progress = self._scroll_elapsed / self.SCROLL_DURATION
        if progress < 0.5:
            eased = 4 * progress**3
        else:
            eased = 1 - ((-2 * progress + 2) ** 3) / 2
        self.scroll_position = self._scroll_start + (
            self._scroll_target - self._scroll_start
        ) * eased
        if progress == 1:
            self.scroll_position = self._scroll_target

    def _retarget_scroll(self) -> None:
        focus_row = self.focused_index // self.COLUMNS
        last_start = max(0, self.total_rows - self.VISIBLE_ROWS)
        self._scroll_start = self.scroll_position
        self._scroll_target = min(max(focus_row - 1, 0), last_start)
        self._scroll_elapsed = 0.0

    def _refresh_asset_window(self) -> None:
        if not self.pokemon:
            self._assets.clear()
            return

        focus_row = self.focused_index // self.COLUMNS
        first_row = max(0, focus_row - self.BUFFER_ROWS)
        last_row = min(self.total_rows - 1, focus_row + self.BUFFER_ROWS)
        first_index = first_row * self.COLUMNS
        last_index = min(len(self.pokemon), (last_row + 1) * self.COLUMNS)
        wanted = self.pokemon[first_index:last_index]
        old_assets = self._assets
        self._assets = {
            name: old_assets.get(name)
            or self.context.filesystem.load_pokemon_asset(name)
            for name in wanted
        }

    def _asset_for(self, name: str) -> ImageAsset:
        asset = self._assets.get(name)
        if asset is None:
            asset = self.context.filesystem.load_pokemon_asset(name)
            self._assets[name] = asset
        return asset

    def render(self, display: DisplayDevice) -> None:
        if not self.pokemon:
            return

        self._render_gallery(display)
        focused = self.pokemon[self.focused_index]
        pokemon_id = int(Path(focused).stem)
        primary_type = self.pokemon_types.get(pokemon_id, (None, None))[0]
        primary_type = primary_type or "grass"
        background = self.backgrounds.get(primary_type)
        if background is None:
            background = self.backgrounds.get("grass")
        if background is not None:
            display.draw_image(
                Panel.CONTEXT,
                background,
                (0, 0, *PANEL_SIZE),
            )
        sprite_x = (PANEL_SIZE[0] - self.SPRITE_SIZE) // 2
        sprite_y = (PANEL_SIZE[1] - self.SPRITE_SIZE) // 2
        display.draw_image(
            Panel.CONTEXT,
            self._asset_for(focused),
            (sprite_x, sprite_y, self.SPRITE_SIZE, self.SPRITE_SIZE),
        )

    def on_exit(self) -> None:
        self.context.speaker.stop()

    def _render_gallery(self, display: DisplayDevice) -> None:
        first_visible_row = max(0, math.floor(self.scroll_position))
        last_visible_row = min(
            self.total_rows,
            math.ceil(self.scroll_position + self.VISIBLE_ROWS),
        )
        for row in range(first_visible_row, last_visible_row):
            for column in range(self.COLUMNS):
                index = row * self.COLUMNS + column
                if index >= len(self.pokemon):
                    break

                focused = index == self.focused_index
                size = self.FOCUSED_SIZE if focused else self.THUMBNAIL_SIZE
                x = column * self.CELL_WIDTH + (self.CELL_WIDTH - size) // 2
                y = round(
                    (row - self.scroll_position) * self.CELL_HEIGHT
                    + (self.CELL_HEIGHT - size) // 2
                )
                if focused:
                    display.draw_circle(
                        Panel.MAIN,
                        (x + size // 2, y + size // 2),
                        size // 2 + 4,
                        (255, 214, 64),
                    )
                display.draw_image(
                    Panel.MAIN,
                    self._asset_for(self.pokemon[index]),
                    (x, y, size, size),
                )
