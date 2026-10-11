from pathlib import Path
import pygame
import os

class Filesystem:
    def __init__(self):
        self.root_dir: Path = Path(os.path.dirname(os.path.abspath(__file__))).parent
        self.files_dir: Path = self.root_dir / "files"
        self.photos_dir: Path = self.files_dir / "photos"
        self.music_dir: Path = self.files_dir / "music"
        self.assets_dir: Path = self.root_dir / "assets"
        self.png_dir: Path = self.assets_dir / "png"

        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.png_dir.mkdir(parents=True, exist_ok=True)

    def load_image(self, name: str) -> pygame.Surface:
        return pygame.image.load(self.png_dir / name).convert_alpha()

filesystem = Filesystem()
