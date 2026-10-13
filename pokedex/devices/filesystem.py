import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .camera import CapturedPhoto


@dataclass(frozen=True)
class ImageAsset:
    name: str
    data: bytes
    is_photo: bool = False
    is_thumbnail: bool = False
    is_music_cover: bool = False
    is_pokemon: bool = False


class Filesystem:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent
        self.files_dir = self.root_dir / "files"
        self.photos_dir = self.files_dir / "photos"
        self.thumbnails_dir = self.photos_dir / ".thumbnails"
        self.music_dir = self.files_dir / "music"
        self.assets_dir = self.root_dir / "assets"
        self.png_dir = self.assets_dir / "png"

    def prepare_user_directories(self) -> None:
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def load_image_asset(self, name: str) -> ImageAsset:
        path = self.png_dir / name
        return ImageAsset(name, path.read_bytes())

    def load_backgrounds(self) -> dict[str, ImageAsset]:
        backgrounds_dir = self.png_dir / "backgrounds"
        return {
            path.stem.lower(): ImageAsset(
                f"backgrounds/{path.name}",
                path.read_bytes(),
            )
            for path in sorted(backgrounds_dir.glob("*.png"))
        }

    def list_pokemon_primary_types(self) -> dict[int, str]:
        database_path = self.root_dir / "pokemon.db"
        with sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "SELECT id, primary_type FROM pokemon"
            ).fetchall()
        return {
            int(pokemon_id): primary_type.lower()
            for pokemon_id, primary_type in rows
            if pokemon_id is not None and primary_type
        }

    def list_music(self) -> list[str]:
        return sorted(path.name for path in self.music_dir.glob("*.mp3"))

    def music_path(self, name: str) -> Path:
        return self.music_dir / name

    def load_music_cover_asset(self, name: str) -> ImageAsset | None:
        path = self.music_dir / f"{Path(name).stem}.png"
        if not path.is_file():
            return None
        return ImageAsset(
            f"music-cover/{path.name}",
            path.read_bytes(),
            is_music_cover=True,
        )

    def list_pokemon(self) -> list[str]:
        return sorted(
            (
                path.name
                for path in (self.png_dir / "pokemon").glob("*.png")
                if path.stem.isdigit()
            ),
            key=lambda name: int(Path(name).stem),
        )

    def load_pokemon_asset(self, name: str) -> ImageAsset:
        path = self.png_dir / "pokemon" / name
        return ImageAsset(
            f"pokemon/{name}",
            path.read_bytes(),
            is_pokemon=True,
        )

    def list_photos(self) -> list[str]:
        return sorted(
            (path.name for path in self.photos_dir.glob("*.png")),
            reverse=True,
        )

    def load_photo_asset(self, name: str) -> ImageAsset:
        path = self.photos_dir / name
        return ImageAsset(name, path.read_bytes(), is_photo=True)

    def load_photo_thumbnail_asset(self, name: str) -> ImageAsset:
        photo_path = self.photos_dir / name
        thumbnail_path = self._thumbnail_path(name)
        if not thumbnail_path.exists():
            self._create_thumbnail(photo_path, thumbnail_path)
        return ImageAsset(
            f"thumbnail/{name}",
            thumbnail_path.read_bytes(),
            is_photo=True,
            is_thumbnail=True,
        )

    def save_photo(self, photo: CapturedPhoto) -> ImageAsset:
        filename = datetime.now().strftime("photo-%Y%m%d-%H%M%S-%f.png")
        path = self.photos_dir / filename
        path.write_bytes(photo.full_size_png)
        self._thumbnail_path(filename).write_bytes(photo.thumbnail_jpeg)
        return ImageAsset(filename, photo.full_size_png, is_photo=True)

    def _thumbnail_path(self, photo_name: str) -> Path:
        return self.thumbnails_dir / f"{Path(photo_name).stem}.jpg"

    @staticmethod
    def _create_thumbnail(photo_path: Path, thumbnail_path: Path) -> None:
        import cv2

        frame = cv2.imread(str(photo_path))
        if frame is None:
            raise OSError(f"Could not read photo: {photo_path}")

        height, width = frame.shape[:2]
        target_ratio = 3 / 2
        if width / height > target_ratio:
            crop_width = int(height * target_ratio)
            left = (width - crop_width) // 2
            frame = frame[:, left : left + crop_width]
        else:
            crop_height = int(width / target_ratio)
            top = (height - crop_height) // 2
            frame = frame[top : top + crop_height, :]

        thumbnail = cv2.resize(frame, (150, 100), interpolation=cv2.INTER_AREA)
        if not cv2.imwrite(
            str(thumbnail_path),
            thumbnail,
            [cv2.IMWRITE_JPEG_QUALITY, 82],
        ):
            raise OSError(f"Could not write photo thumbnail: {thumbnail_path}")
