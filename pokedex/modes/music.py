from dataclasses import dataclass

from ..devices.display import DisplayDevice, PANEL_SIZE, Panel
from ..devices.filesystem import ImageAsset
from ..devices.input import Action
from .base import ModeContext, ModeRequest


@dataclass(frozen=True)
class Track:
    filename: str


@dataclass
class CoverTransition:
    track_index: int
    cover: ImageAsset | None
    start_x: float
    target_x: float
    elapsed: float = 0.0
    angle: float = 0.0


class MusicPlayer:
    """Smooth song carousel with a separate currently played cover pane."""

    RECORD_SIZE = (210, 210)
    COVER_SIZE = (110, 110)
    COVER_SPIN_DEGREES_PER_SECOND = -100
    SLIDE_DURATION = 0.36

    def __init__(self, context: ModeContext):
        self.context = context
        self.tracks = [Track(name) for name in context.filesystem.list_music()]
        track_count = len(self.tracks)
        self.carousel_count = (
            ((3 + track_count - 1) // track_count) * track_count
            if track_count
            else 0
        )
        self.record = context.filesystem.load_ui("record.png")
        self.position = 0.0
        self._start_position = 0.0
        self._target_position = 0
        self._transition_elapsed = 0.0
        self._transition_duration = 0.24
        self._active_index: int | None = None
        self._playing = False
        self._paused = False
        self._cover_transitions: list[CoverTransition] = []
        self._covers: dict[int, ImageAsset | None] = {}
        self._refresh_cover_window()

    @property
    def focused_index(self) -> int:
        return self._target_position % len(self.tracks) if self.tracks else 0

    def update(self, actions: frozenset[Action], delta_time: float) -> ModeRequest | None:
        delta_time = max(delta_time, 0.0)
        self._advance_transition(delta_time)
        self._advance_cover_transitions(delta_time)
        if Action.HOME in actions:
            return ModeRequest("menu")
        if not self.tracks:
            return None

        if self._playing and not self._paused and not self.context.speaker.is_playing():
            self._playing = False
            self._paused = False
            self._active_index = None
            self._slide_covers_out()
        if self._playing and not self._paused:
            for transition in self._cover_transitions:
                if (
                    transition.track_index == self._active_index
                    and transition.target_x == 0
                ):
                    transition.angle = (
                        transition.angle
                        + delta_time * self.COVER_SPIN_DEGREES_PER_SECOND
                    ) % 360

        if Action.LEFT in actions or Action.UP in actions:
            self._move(-1)
        elif Action.RIGHT in actions or Action.DOWN in actions:
            self._move(1)

        if Action.CONFIRM in actions:
            self._play_focused_track()
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
        self._refresh_cover_window()

    def _play_focused_track(self) -> None:
        if self._active_index == self.focused_index and self._playing:
            if self._paused:
                self.context.speaker.resume()
                self._paused = False
            else:
                self.context.speaker.pause()
                self._paused = True
            return

        track = self.tracks[self.focused_index]
        self._playing = self.context.speaker.play(
            self.context.filesystem.music_path(track.filename)
        )
        self._paused = False
        if self._playing:
            self._active_index = self.focused_index
            self._refresh_cover_window()
            self._slide_track_in(self._active_index)

    def _slide_covers_out(self) -> None:
        for transition in self._cover_transitions:
            transition.start_x = self._cover_x(transition)
            transition.target_x = float(PANEL_SIZE[0])
            transition.elapsed = 0.0

    def _slide_track_in(self, track_index: int) -> None:
        self._slide_covers_out()
        self._cover_transitions.append(
            CoverTransition(
                track_index=track_index,
                cover=self._covers.get(track_index),
                start_x=-float(PANEL_SIZE[0]),
                target_x=0.0,
            )
        )

    def _advance_cover_transitions(self, delta_time: float) -> None:
        for transition in self._cover_transitions:
            transition.elapsed = min(
                transition.elapsed + delta_time,
                self.SLIDE_DURATION,
            )
        self._cover_transitions = [
            transition
            for transition in self._cover_transitions
            if not (
                transition.target_x > 0
                and transition.elapsed >= self.SLIDE_DURATION
            )
        ]

    def _cover_x(self, transition: CoverTransition) -> float:
        progress = transition.elapsed / self.SLIDE_DURATION
        if progress < 0.5:
            eased = 4 * progress**3
        else:
            eased = 1 - ((-2 * progress + 2) ** 3) / 2
        return transition.start_x + (transition.target_x - transition.start_x) * eased

    def _refresh_cover_window(self) -> None:
        if not self.tracks:
            self._covers.clear()
            return

        count = len(self.tracks)
        wanted = {
            (self.focused_index + offset) % count
            for offset in (-1, 0, 1)
        }
        if self._active_index is not None:
            wanted.add(self._active_index)

        previous = self._covers
        self._covers = {
            index: previous[index]
            if index in previous
            else self.context.filesystem.load_music_cover_asset(
                self.tracks[index].filename
            )
            for index in wanted
        }

    def render(self, display: DisplayDevice) -> None:
        self._render_carousel(display)
        center_y = PANEL_SIZE[1] // 2
        for transition in self._cover_transitions:
            center = (
                round(PANEL_SIZE[0] // 2 + self._cover_x(transition)),
                center_y,
            )
            if transition.cover is not None:
                cover_rect = (
                    center[0] - self.COVER_SIZE[0] // 2,
                    center[1] - self.COVER_SIZE[1] // 2,
                    *self.COVER_SIZE,
                )
                display.draw_shadow(
                    Panel.CONTEXT,
                    cover_rect,
                    angle=transition.angle,
                )
                display.draw_rotated_image(
                    Panel.CONTEXT,
                    transition.cover,
                    center,
                    self.COVER_SIZE,
                    transition.angle,
                )
            record_size = self.RECORD_SIZE
            display.draw_image(
                Panel.CONTEXT,
                self.record,
                (
                    center[0] - record_size[0] // 2,
                    center[1] - record_size[1] // 2,
                    *record_size,
                ),
            )

    def _render_carousel(self, display: DisplayDevice) -> None:
        if not self.tracks:
            return

        center_x = PANEL_SIZE[0] // 2
        gap = 105
        for carousel_index in range(self.carousel_count):
            offset = (
                carousel_index - self.position + self.carousel_count / 2
            ) % self.carousel_count
            offset -= self.carousel_count / 2

            size = round(104 - min(abs(offset), 1) * 40)
            x = center_x + offset * gap - size // 2
            y = (PANEL_SIZE[1] - size) // 2
            track_index = carousel_index % len(self.tracks)
            cover = self._covers.get(track_index)
            if cover is not None:
                cover_rect = (round(x), y, size, size)
                display.draw_shadow(Panel.MAIN, cover_rect)
                display.draw_image(Panel.MAIN, cover, cover_rect)

    def on_exit(self) -> None:
        self.context.speaker.stop()
