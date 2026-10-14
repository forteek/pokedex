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

    def draw_image(
        self,
        panel: Panel,
        image: ImageAsset,
        rect: Rect,
        alpha: int = 255,
    ) -> None: ...

    def draw_shadow(
        self,
        panel: Panel,
        rect: Rect,
        offset: tuple[int, int] = (2, 2),
        blur_radius: int = 8,
        spread: int = 1,
        opacity: int = 84,
        angle: float = 0,
    ) -> None: ...

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

    def draw_circle(
        self,
        panel: Panel,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int],
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
        self._rotated_thumbnails: OrderedDict[
            tuple[str, int, int, float], pygame.Surface
        ] = OrderedDict()
        self._circles: dict[tuple[int, tuple[int, int, int]], pygame.Surface] = {}
        self._shadows: dict[
            tuple[int, int, tuple[int, int], int, int, int],
            tuple[pygame.Surface, int],
        ] = {}
        self._fonts: dict[int, pygame.font.Font] = {}

    def clear(self, panel: Panel, color: tuple[int, int, int]) -> None:
        self.panels[panel].fill(color)

    def draw_image(
        self,
        panel: Panel,
        image_asset: ImageAsset,
        rect: Rect,
        alpha: int = 255,
    ) -> None:
        x, y, width, height = rect
        alpha = max(0, min(alpha, 255))
        scaled = self._scaled_image(image_asset, (width, height))
        if alpha == 0:
            return
        if alpha < 255:
            faded = scaled.copy()
            faded.fill(
                (255, 255, 255, alpha),
                special_flags=pygame.BLEND_RGBA_MULT,
            )
            scaled = faded
        self.panels[panel].blit(scaled, (x, y))

    def draw_shadow(
        self,
        panel: Panel,
        rect: Rect,
        offset: tuple[int, int] = (2, 2),
        blur_radius: int = 8,
        spread: int = 1,
        opacity: int = 84,
        angle: float = 0,
    ) -> None:
        import cv2
        import numpy as np

        x, y, width, height = rect
        key = (width, height, offset, blur_radius, spread, opacity)
        cached = self._shadows.get(key)
        if cached is None:
            padding = int(blur_radius * 1.5) + spread + max(
                abs(offset[0]), abs(offset[1])
            )
            mask = np.zeros(
                (height + 2 * padding, width + 2 * padding),
                dtype=np.uint8,
            )
            left = padding + offset[0] - spread
            top = padding + offset[1] - spread
            cv2.rectangle(
                mask,
                (left, top),
                (left + width + 2 * spread - 1, top + height + 2 * spread - 1),
                255,
                thickness=cv2.FILLED,
            )
            mask = cv2.GaussianBlur(
                mask,
                (0, 0),
                sigmaX=blur_radius / 2,
                sigmaY=blur_radius / 2,
                borderType=cv2.BORDER_CONSTANT,
            )
            rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
            rgba[:, :, 3] = (mask.astype(np.uint16) * opacity // 255).astype(np.uint8)
            shadow = pygame.image.fromstring(
                rgba.tobytes(),
                (mask.shape[1], mask.shape[0]),
                "RGBA",
            ).convert_alpha()
            cached = (shadow, padding)
            self._shadows[key] = cached

        shadow, padding = cached
        if angle:
            shadow = pygame.transform.rotozoom(shadow, angle, 1.0)
            rect = shadow.get_rect(
                center=(x + width // 2, y + height // 2)
            )
            self.panels[panel].blit(shadow, rect)
        else:
            self.panels[panel].blit(shadow, (x - padding, y - padding))

    def draw_rotated_image(
        self,
        panel: Panel,
        image_asset: ImageAsset,
        center: tuple[int, int],
        size: tuple[int, int],
        angle: float,
    ) -> None:
        scaled = self._scaled_image(image_asset, size)
        rotated = None
        if image_asset.is_thumbnail:
            key = (image_asset.name, size[0], size[1], angle)
            rotated = self._rotated_thumbnails.get(key)
            if rotated is not None:
                self._rotated_thumbnails.move_to_end(key)
        if rotated is None:
            rotated = (
                self._supersampled_rotate(scaled, angle)
                if image_asset.is_thumbnail
                else pygame.transform.rotozoom(scaled, angle, 1.0)
            )
            if image_asset.is_thumbnail:
                self._rotated_thumbnails[key] = rotated
                while len(self._rotated_thumbnails) > 33:
                    self._rotated_thumbnails.popitem(last=False)
        rect = rotated.get_rect(center=center)
        self.panels[panel].blit(rotated, rect)

    @staticmethod
    def _supersampled_rotate(
        image: pygame.Surface,
        angle: float,
        factor: int = 6,
    ) -> pygame.Surface:
        width, height = image.get_size()
        enlarged = pygame.transform.smoothscale(
            image,
            (width * factor, height * factor),
        )
        rotated = pygame.transform.rotozoom(enlarged, angle, 1.0)
        output_size = (
            max(1, round(rotated.get_width() / factor)),
            max(1, round(rotated.get_height() / factor)),
        )
        return PygameDisplay._alpha_aware_smoothscale(rotated, output_size)

    @staticmethod
    def _alpha_aware_smoothscale(
        image: pygame.Surface,
        size: tuple[int, int],
    ) -> pygame.Surface:
        import numpy as np

        source_width, source_height = image.get_size()
        rgba = np.frombuffer(
            pygame.image.tostring(image, "RGBA"),
            dtype=np.uint8,
        ).reshape((source_height, source_width, 4)).astype(np.uint16)
        alpha = rgba[:, :, 3:4]
        rgba[:, :, :3] = (rgba[:, :, :3] * alpha + 127) // 255
        premultiplied = pygame.image.fromstring(
            rgba.astype(np.uint8).tobytes(),
            image.get_size(),
            "RGBA",
        )
        scaled = pygame.transform.smoothscale(premultiplied, size)

        rgba = np.frombuffer(
            pygame.image.tostring(scaled, "RGBA"),
            dtype=np.uint8,
        ).reshape((size[1], size[0], 4)).astype(np.uint16)
        alpha = rgba[:, :, 3:4]
        visible = alpha[:, :, 0] > 0
        rgb = rgba[:, :, :3]
        rgb[visible] = np.minimum(
            (rgb[visible] * 255 + alpha[visible] // 2) // alpha[visible],
            255,
        )
        rgba[:, :, :3] = rgb
        return pygame.image.fromstring(
            rgba.astype(np.uint8).tobytes(),
            size,
            "RGBA",
        ).convert_alpha()

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
            scaled = (
                image
                if image.get_size() == (width, height)
                else pygame.transform.smoothscale(image, (width, height))
            )
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

    def draw_circle(
        self,
        panel: Panel,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int],
    ) -> None:
        key = (radius, color)
        circle = self._circles.get(key)
        if circle is None:
            diameter = radius * 2 + 1
            factor = 4
            high_resolution = pygame.Surface(
                (diameter * factor, diameter * factor),
                pygame.SRCALPHA,
            )
            pygame.draw.circle(
                high_resolution,
                color,
                (diameter * factor // 2, diameter * factor // 2),
                radius * factor,
            )
            circle = self._alpha_aware_smoothscale(
                high_resolution,
                (diameter, diameter),
            )
            self._circles[key] = circle
        self.panels[panel].blit(circle, circle.get_rect(center=center))

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
