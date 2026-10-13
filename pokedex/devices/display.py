from enum import Enum, auto
from collections import OrderedDict
from io import BytesIO
from typing import Protocol

import pygame

from .camera import CameraFrame
from .filesystem import ImageAsset

Rect = tuple[int, int, int, int]
PANEL_SIZE = (320, 240)


class Panel(Enum):
    """The primary view and its independent supporting context view."""

    MAIN = auto()
    CONTEXT = auto()


class DisplayDevice(Protocol):
    def clear(self, panel: Panel, color: tuple[int, int, int]) -> None: ...

    def draw_image(self, panel: Panel, image: ImageAsset, rect: Rect) -> None: ...

    def draw_rotated_image(
        self,
        panel: Panel,
        image: ImageAsset,
        center: tuple[int, int],
        size: tuple[int, int],
        angle: float,
    ) -> None: ...

    def draw_camera_frame(self, panel: Panel, frame: CameraFrame, rect: Rect) -> None: ...

    def draw_rect(
        self,
        panel: Panel,
        rect: Rect,
        color: tuple[int, int, int],
        width: int = 0,
    ) -> None: ...

    def draw_text(
        self,
        panel: Panel,
        text: str,
        position: tuple[int, int],
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> None: ...

    def present(self) -> None: ...


class PygameDisplay:
    """Draw onto two 320x240 panels and present them side by side in pygame."""

    def __init__(self):
        self.window = pygame.display.set_mode((PANEL_SIZE[0] * 2, PANEL_SIZE[1]))
        pygame.display.set_caption("Pokedex")
        self.panels = {
            Panel.MAIN: pygame.Surface(PANEL_SIZE),
            Panel.CONTEXT: pygame.Surface(PANEL_SIZE),
        }
        self._images: OrderedDict[tuple[str, str], pygame.Surface] = OrderedDict()
        self._scaled_images: OrderedDict[tuple[str, str, int, int], pygame.Surface] = OrderedDict()
        self._fonts: dict[int, pygame.font.Font] = {}

    def clear(self, panel: Panel, color: tuple[int, int, int]) -> None:
        self.panels[panel].fill(color)

    def draw_image(self, panel: Panel, image_asset: ImageAsset, rect: Rect) -> None:
        x, y, width, height = rect
        scaled = self._scaled_image(image_asset, (width, height))
        self.panels[panel].blit(scaled, (x, y))

    def draw_rotated_image(
        self,
        panel: Panel,
        image_asset: ImageAsset,
        center: tuple[int, int],
        size: tuple[int, int],
        angle: float,
    ) -> None:
        scaled = self._scaled_image(image_asset, size)
        rotated = pygame.transform.rotate(scaled, angle)
        rect = rotated.get_rect(center=center)
        self.panels[panel].blit(rotated, rect)

    def _scaled_image(
        self,
        image_asset: ImageAsset,
        size: tuple[int, int],
    ) -> pygame.Surface:
        width, height = size
        category = self._image_category(image_asset)
        image_key = (category, image_asset.name)
        scale_key = (category, image_asset.name, width, height)

        scaled = self._scaled_images.get(scale_key)
        if scaled is None:
            image = self._images.get(image_key)
            if image is None:
                image = pygame.image.load(BytesIO(image_asset.data)).convert_alpha()
                self._cache_image(self._images, image_key, image, category)
            else:
                self._images.move_to_end(image_key)
            scaled = pygame.transform.smoothscale(image, (width, height))
            self._cache_image(self._scaled_images, scale_key, scaled, category)
        else:
            self._scaled_images.move_to_end(scale_key)
        return scaled

    @staticmethod
    def _image_category(image_asset: ImageAsset) -> str:
        if image_asset.is_thumbnail:
            return "thumbnail"
        if image_asset.is_music_cover:
            return "music_cover"
        if image_asset.is_pokemon:
            return "pokemon"
        if image_asset.is_photo:
            return "photo"
        return "static"

    @staticmethod
    def _cache_image(cache, key, image, category: str) -> None:
        cache[key] = image
        cache.move_to_end(key)

        capacity = {
            "thumbnail": 33,
            "photo": 5,
            "music_cover": 5,
            "pokemon": 12,
        }.get(category)
        if capacity is None:
            return

        while sum(cache_key[0] == category for cache_key in cache) > capacity:
            oldest_key = next(cache_key for cache_key in cache if cache_key[0] == category)
            del cache[oldest_key]

    def draw_camera_frame(self, panel: Panel, frame: CameraFrame, rect: Rect) -> None:
        x, y, width, height = rect
        image = pygame.image.frombuffer(frame.rgb, (frame.width, frame.height), "RGB")
        scaled = pygame.transform.smoothscale(image, (width, height))
        self.panels[panel].blit(scaled, (x, y))

    def draw_rect(
        self,
        panel: Panel,
        rect: Rect,
        color: tuple[int, int, int],
        width: int = 0,
    ) -> None:
        pygame.draw.rect(self.panels[panel], color, rect, width)

    def draw_text(
        self,
        panel: Panel,
        text: str,
        position: tuple[int, int],
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        font = self._fonts.get(24)
        if font is None:
            font = pygame.font.Font(None, 24)
            self._fonts[24] = font
        self.panels[panel].blit(font.render(text, True, color), position)

    def present(self) -> None:
        self.window.blit(self.panels[Panel.MAIN], (0, 0))
        self.window.blit(self.panels[Panel.CONTEXT], (PANEL_SIZE[0], 0))
        pygame.display.flip()
