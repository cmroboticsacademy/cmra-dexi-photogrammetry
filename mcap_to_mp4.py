#!/usr/bin/env python3

"""Convert a ROS 2 CompressedImage topic in an MCAP file to H.264 MP4."""

import argparse
import shutil
import subprocess
from itertools import chain
from pathlib import Path

from mcap_ros2.reader import read_ros2_messages


FLIP_FILTERS = {
    "none": None,
    "horizontal": "hflip",
    "vertical": "vflip",
    "180": "hflip,vflip",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a ROS 2 CompressedImage topic from an MCAP file "
            "into an H.264 MP4 video."
        )
    )

    parser.add_argument("input", help="Path to the input MCAP file.")
    parser.add_argument("output", help="Path for the output MP4 file.")
    parser.add_argument(
        "--topic",
        default="/cam0/image_raw/compressed",
        help="CompressedImage topic to convert.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Output video frame rate. Default: 30",
    )
    parser.add_argument(
        "--flip",
        choices=tuple(FLIP_FILTERS),
        default="none",
        help="Orientation adjustment. Use '180' for an upside-down camera.",
    )

    return parser.parse_args()


def build_ffmpeg_command(
    output_path: Path,
    fps: float,
    flip: str,
) -> list[str]:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        str(fps),
        "-vcodec",
        "mjpeg",
        "-i",
        "pipe:0",
        "-an",
    ]

    video_filter = FLIP_FILTERS[flip]
    if video_filter is not None:
        command.extend(["-vf", video_filter])

    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )

    return command


def main() -> None:
    args = parse_arguments()

    if args.fps <= 0:
        raise SystemExit("--fps must be greater than zero.")

    if shutil.which("ffmpeg") is None:
        raise SystemExit(
            "ffmpeg was not found. Activate the dexi-video Conda environment."
        )

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    if not input_path.is_file():
        raise SystemExit(f"Input MCAP file does not exist: {input_path}")

    if input_path == output_path:
        raise SystemExit("The input and output paths must be different.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    messages = read_ros2_messages(str(input_path), topics=[args.topic])
    first_message = next(messages, None)

    if first_message is None:
        raise SystemExit(f"No messages were found on topic: {args.topic}")

    command = build_ffmpeg_command(output_path, args.fps, args.flip)

    print(f"Reading: {input_path}")
    print(f"Topic: {args.topic}")
    print(f"Frame rate: {args.fps:g} FPS")
    print(f"Flip mode: {args.flip}")
    print(f"Writing: {output_path}")

    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:
        process.kill()
        raise SystemExit("Could not open the FFmpeg input pipe.")

    frame_count = 0

    try:
        for recorded_message in chain((first_message,), messages):
            frame_data = getattr(recorded_message.ros_msg, "data", None)
            if frame_data is None:
                continue

            process.stdin.write(bytes(frame_data))
            frame_count += 1

            if frame_count % 100 == 0:
                print(f"Processed {frame_count} frames...")
    except BrokenPipeError:
        pass
    finally:
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass

    return_code = process.wait()

    if return_code != 0:
        raise SystemExit(f"FFmpeg failed with exit code {return_code}.")

    print(f"Finished: {output_path}")
    print(f"Frames written: {frame_count}")


if __name__ == "__main__":
    main()
