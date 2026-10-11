from enum import Enum, auto
from io import BytesIO
from typing import Protocol

import pygame

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
        self._images: dict[str, pygame.Surface] = {}
        self._scaled_images: dict[tuple[str, int, int], pygame.Surface] = {}

    def clear(self, panel: Panel, color: tuple[int, int, int]) -> None:
        self.panels[panel].fill(color)

    def draw_image(self, panel: Panel, image_asset: ImageAsset, rect: Rect) -> None:
        x, y, width, height = rect
        cache_key = (image_asset.name, width, height)
        scaled = self._scaled_images.get(cache_key)
        if scaled is None:
            image = self._images.get(image_asset.name)
            if image is None:
                image = pygame.image.load(BytesIO(image_asset.data)).convert_alpha()
                self._images[image_asset.name] = image
            scaled = pygame.transform.smoothscale(image, (width, height))
            self._scaled_images[cache_key] = scaled
        self.panels[panel].blit(scaled, (x, y))

    def present(self) -> None:
        self.window.blit(self.panels[Panel.MAIN], (0, 0))
        self.window.blit(self.panels[Panel.CONTEXT], (PANEL_SIZE[0], 0))
        pygame.display.flip()
