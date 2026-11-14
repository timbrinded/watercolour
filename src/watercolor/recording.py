"""Frame capture during painting and encoding of the time-lapse video."""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

FRAME_SIZE = 720
OUTPUT_FRAME_RATE = 30
TARGET_DURATION = 75.0  # seconds; longer recordings are sped up to about this length


class FrameRecorder:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.count = sum(1 for _ in directory.glob("*.jpg"))

    def capture(self, picture: Image.Image, brush: tuple[float, float, float] | None = None) -> None:
        """Save a frame; brush is (x, y, radius) in sheet pixels when one is touching."""
        scale = FRAME_SIZE / max(picture.size)
        if scale < 1.0:
            size = (round(picture.width * scale), round(picture.height * scale))
            frame = picture.resize(size, Image.Resampling.LANCZOS)
        else:
            scale, frame = 1.0, picture.copy()
        if brush is not None:
            x, y, radius = (value * scale for value in brush)
            radius = max(radius, 2.0)
            box = (x - radius, y - radius, x + radius, y + radius)
            ImageDraw.Draw(frame, "RGBA").ellipse(box, outline=(30, 30, 30, 160))
        frame.save(self.directory / f"{self.count:06d}.jpg", quality=88)
        self.count += 1

    def rewind(self, count: int) -> None:
        """Discard the frames after a count: they show work that was cut short before it was saved."""
        for index in range(count, self.count):
            (self.directory / f"{index:06d}.jpg").unlink()
        self.count = min(count, self.count)


def encode_video(frame_directory: Path, output: Path) -> None:
    count = sum(1 for _ in frame_directory.glob("*.jpg"))
    if count == 0:
        raise ValueError("no frames were recorded")
    input_rate = max(float(OUTPUT_FRAME_RATE), count / TARGET_DURATION)
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", f"{input_rate:.3f}",
        "-i", str(frame_directory / "%06d.jpg"),
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2,tpad=stop_mode=clone:stop_duration=3",
        "-r", str(OUTPUT_FRAME_RATE),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        str(output),
    ]  # fmt: skip
    subprocess.run(command, check=True)
