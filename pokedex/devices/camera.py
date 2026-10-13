from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CameraFrame:
    width: int
    height: int
    rgb: bytes


@dataclass(frozen=True)
class CapturedPhoto:
    full_size_png: bytes
    thumbnail_jpeg: bytes


class Camera(Protocol):
    def start(self) -> bool: ...

    def read_frame(self) -> CameraFrame | None: ...

    def capture(self) -> CapturedPhoto | None: ...

    def stop(self) -> None: ...


class OpenCVCamera:
    """PC webcam adapter. OpenCV is imported only when the camera view opens."""

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self._cv2 = None
        self._capture = None
        self.error: str | None = None

    def start(self) -> bool:
        if self._capture is not None and self._capture.isOpened():
            return True

        try:
            import cv2
        except ImportError:
            self.error = "OpenCV is not installed"
            return False

        self._cv2 = cv2
        capture = cv2.VideoCapture(self.device_index)
        if not capture.isOpened():
            capture.release()
            self.error = "No camera is available"
            return False

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._capture = capture
        self.error = None
        return True

    def read_frame(self) -> CameraFrame | None:
        if self._capture is None or self._cv2 is None:
            return None

        ok, frame = self._capture.read()
        if not ok:
            self.error = "Could not read from camera"
            return None

        frame = self._cv2.resize(frame, (320, 240))
        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        return CameraFrame(320, 240, rgb.tobytes())

    def capture(self) -> bytes | None:
        if self._capture is None or self._cv2 is None:
            return None

        ok, frame = self._capture.read()
        if not ok:
            self.error = "Could not capture photo"
            return None

        ok, full_size = self._cv2.imencode(".png", frame)
        if not ok:
            self.error = "Could not encode photo"
            return None

        thumbnail = self._make_thumbnail(frame)
        ok, thumbnail_jpeg = self._cv2.imencode(
            ".jpg",
            thumbnail,
            [self._cv2.IMWRITE_JPEG_QUALITY, 82],
        )
        if not ok:
            self.error = "Could not encode photo thumbnail"
            return None
        return CapturedPhoto(full_size.tobytes(), thumbnail_jpeg.tobytes())

    def _make_thumbnail(self, frame):
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
        return self._cv2.resize(frame, (150, 100), interpolation=self._cv2.INTER_AREA)

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
