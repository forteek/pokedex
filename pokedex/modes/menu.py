from dataclasses import dataclass
from ..devices.filesystem import filesystem

import pygame

@dataclass
class MenuOption:
    name: str
    image: pygame.Surface

@dataclass
class Carousel:
    camera: MenuOption
    music: MenuOption
    gallery: MenuOption
    pokedex: MenuOption

class Menu:
    def __init__(self):
        self.carousel = Carousel(
            MenuOption(
                "Camera",
                filesystem.load_image("camera.png"),
            ),
            MenuOption(
                "Music",
                filesystem.load_image("music.png"),
            ),
            MenuOption(
                "Gallery",
                filesystem.load_image("gallery.png"),
            ),
            MenuOption(
                "Pokedex",
                filesystem.load_image("pokedex.png"),
            ),
        )
        self.focused_option = 0

    def tick(self):
        pass