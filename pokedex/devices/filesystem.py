from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageAsset:
    name: str
    data: bytes


class Filesystem:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent
        self.files_dir = self.root_dir / "files"
        self.photos_dir = self.files_dir / "photos"
        self.music_dir = self.files_dir / "music"
        self.assets_dir = self.root_dir / "assets"
        self.png_dir = self.assets_dir / "png"

    def prepare_user_directories(self) -> None:
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def load_image_asset(self, name: str) -> ImageAsset:
        path = self.png_dir / name
        return ImageAsset(name, path.read_bytes())
