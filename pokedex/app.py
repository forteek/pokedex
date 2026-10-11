from .devices.display import Display
from .devices.filesystem import Filesystem, filesystem
from .devices.camera import Camera
from .devices.speaker import Speaker
from .devices.button import Button
from .devices.led import Led

import pygame
from dataclasses import dataclass

@dataclass
class Views:
    left: pygame.Surface
    right: pygame.Surface

@dataclass
class Devices:
    filesystem: Filesystem
    camera: Camera
    speaker: Speaker
    display: Display

@dataclass
class Controls:
    left: Button
    right: Button
    up: Button
    down: Button
    ok: Button
    home: Button
    scan: Button

@dataclass
class Leds:
    red: Led
    yellow: Led
    green: Led

class App:
    def __init__(self):
        pygame.init()
        self.window = pygame.display.set_mode((640, 240))
        pygame.display.set_caption("Pokedex")
        self.views = Views(
            pygame.Surface((320, 240)),
            pygame.Surface((320, 240)),
        )
        self.devices = Devices(
            filesystem,
            Camera(),
            Speaker(),
            Display(),
        )
        self.controls = Controls(
            Button(pygame.K_LEFT),
            Button(pygame.K_RIGHT),
            Button(pygame.K_UP),
            Button(pygame.K_DOWN),
            Button(pygame.K_q),
            Button(pygame.K_w),
            Button(pygame.K_e),
        )
        self.leds = Leds(
            Led(0),
            Led(1),
            Led(2),
        )
        self.clock = pygame.time.Clock()
        self.running = True

    def run(self):
        try:
            while self.running:
                self.clock.tick(60)
        finally:
            pygame.quit()



def run():
    app = App()
    print(1)
