# DEXI-3 Photogrammetry Workflow

This package provides an end-to-end workflow for:

1. Recording the DEXI-3 Arducam stream into a ROS 2 MCAP bag.
2. Moving the MCAP recording to another computer.
3. Converting the camera stream into an H.264 MP4.
4. Reconstructing the recorded area in 3D with the Map Anything Local Gradio Demo.


## Package contents

- `mcap_to_mp4.py` — converts the compressed ROS 2 camera topic to MP4.
- `environment.yml` — reproducible Conda environment for the converter.
- `requirements.txt` — converter dependency for developers not using Conda.

Map Anything is installed separately because it uses a different environment
and Python version from the MCAP converter.

## Workflow overview

```text
DEXI-3 camera
    -> ROS 2 MCAP recording
    -> transfer MCAP to Mac
    -> convert MCAP to corrected MP4
    -> upload MP4 to Map Anything
    -> inspect or save the reconstructed GLB
```

## Part 1: Record the camera on the DEXI-3

### 1. Connect and prepare for flight

1. Connect your computer to the DEXI network.
2. Perform the normal sensor calibration, flight checks, and mission setup.
3. Open a terminal in DEXI OS.

### 2. Create the recording directory

```bash
sudo mkdir -p /home/dexi/recordings
sudo chown dexi:dexi /home/dexi/recordings
```

### 3. Start a timestamped recording

Run the following as one block:

```bash
recording_name="flight_$(date +%Y%m%d_%H%M%S)"

sudo bash -c "
source /home/dexi/ros2_jazzy/install/setup.bash
source /home/dexi/dexi_ws/install/setup.bash

ros2 bag record \\
  --storage mcap \\
  -o /home/dexi/recordings/${recording_name} \\
  /cam0/image_raw/compressed \\
  /cam0/camera_info
"
```

Keep this terminal open while flying.

For a useful reconstruction:

- Fly slowly and keep the subject in view.
- Capture the same surfaces from multiple angles.
- Aim for roughly 70–80% overlap between neighboring views.
- Use an orbit, a lawnmower/grid pattern, or both.
- Avoid fast turns, motion blur, featureless surfaces, and large jumps in distance.
- Keep lighting as consistent as possible.

### 4. Stop and finalize the recording

Press `Control+C` in the recording terminal. Wait for the process to return to
the prompt so the MCAP index can finish writing.

Return ownership of the files to the `dexi` user:

```bash
sudo chown -R dexi:dexi "/home/dexi/recordings/${recording_name}"
```

Show the resulting MCAP file:

```bash
find "/home/dexi/recordings/${recording_name}" \
  -type f -name "*.mcap" -ls
```

Do not power off the drone while the recording process is still closing.

## Part 2: Transfer the MCAP to another computer

### Option A: Temporary HTTP server

This option does not require SSH or port 22. In the DEXI terminal, enter the
recording directory and start a temporary web server:

```bash
cd "/home/dexi/recordings/${recording_name}"
python3 -m http.server 8000 --bind 0.0.0.0
```

Keep that terminal open. On a Mac connected to the DEXI hotspot, open another
terminal and run:

```bash
cd ~/Downloads
curl -fLO http://192.168.4.1:8000/RECORDING_FILE.mcap
```

Replace `RECORDING_FILE.mcap` with the filename printed by `find`. Press
`Control+C` in the DEXI terminal after the transfer completes.

You can alternatively open <http://192.168.4.1:8000> in a browser and select
the MCAP file. The `curl` method is recommended if the browser leaves an
`Unconfirmed Download` file.

### Option B: SCP

If SSH is enabled on the DEXI-3, run this from the receiving computer:

```bash
scp dexi@192.168.4.1:/home/dexi/recordings/RECORDING_DIRECTORY/RECORDING_FILE.mcap ~/Downloads/
```

The `.mcap` file alone is sufficient for this converter. Keep `metadata.yaml`
as well if you want to replay the complete bag with `ros2 bag play`.

## Part 3: Set up the MCAP converter

### Prerequisite

Install Miniconda, Anaconda, or another compatible Conda distribution. Internet
access is required for the initial environment creation.

### Create the converter environment

Open a terminal in this package directory:

```bash
conda env create -f environment.yml
conda activate dexi-video
```

Verify the installation:

```bash
python -c "from mcap_ros2.reader import read_ros2_messages; print('MCAP reader ready')"
ffmpeg -version
```

If the `dexi-video` environment already exists, update it instead:

```bash
conda env update -f environment.yml --prune
conda activate dexi-video
```

## Part 4: Convert MCAP to MP4

From this package directory, run:

```bash
python mcap_to_mp4.py \
  ~/Downloads/flight_recording_0.mcap \
  ~/Downloads/flight.mp4 \
  --flip 180
```

`--flip 180` corrects video from a camera mounted upside down.

### Converter options

```text
--flip none
--flip horizontal
--flip vertical
--flip 180

--fps 30

--topic /cam0/image_raw/compressed
```

Display the complete help text with:

```bash
python mcap_to_mp4.py --help
```

Play `flight.mp4` before continuing. Confirm that it is upright, moves at the
expected speed, and contains the complete flight.

## Part 5: Install Map Anything on macOS

Map Anything performs the 3D reconstruction. Keep it in its own Conda
environment; do not install it into `dexi-video`.

### Requirements

- macOS with Apple silicon is recommended for local Mac inference.
- At least 16 GB of unified memory is recommended; larger reconstructions can
  need substantially more.
- Git, Conda, and an internet connection are required for installation and the
  first model download.
- NVIDIA CUDA on Linux is generally faster. CPU-only inference is possible but
  can be very slow.

### 1. Download Map Anything

Choose a directory for development projects, then run:

```bash
conda deactivate
git clone https://github.com/facebookresearch/map-anything.git
cd map-anything
```

### 2. Create its Conda environment

The current upstream quick start uses Python 3.12:

```bash
conda create -n mapanything python=3.12 -y
conda activate mapanything
```

### 3. Install PyTorch and the Local Gradio Demo

```bash
python -m pip install --upgrade pip
python -m pip install torch torchvision torchaudio
python -m pip install -e ".[gradio]"
```

Verify that PyTorch can see the Apple GPU:

```bash
python -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
```

`MPS available: True` means PyTorch can use the Apple GPU. If it prints
`False`, reconstruction will fall back to the CPU unless another supported
accelerator is available.

## Part 6: Run the Local Gradio Demo

Each time you want to use Map Anything, open a terminal and run:

```bash
cd ./map-anything
conda activate mapanything
python scripts/gradio_app.py
```

Leave the terminal open. Gradio will print a local URL, normally similar to:

```text
http://127.0.0.1:7860
```

Open that address in a browser.

The first reconstruction downloads the pretrained model, so remain connected
to the internet and expect the first run to take longer.

## Part 7: Reconstruct the DEXI flight

### 1. Upload the video

In the Local Gradio Demo:

1. Select **Upload Video**.
2. Choose `flight.mp4`.
3. Set **Sample time interval**.
4. Wait for the frame preview to populate.
5. Select **Reconstruct**.

The Gradio app extracts frames from the MP4 automatically. The sampling
interval means “use one frame every X seconds.”

| Flight/video length | Starting interval | Approximate frames |
| --- | ---: | ---: |
| 30 seconds | 1.0 seconds | 30 |
| 60 seconds | 1.5 seconds | 40 |
| 2 minutes | 2.0 seconds | 60 |
| 5 minutes | 5.0 seconds | 60 |

Start with approximately 30–60 well-overlapped frames. Lower the interval only
if important viewpoints are being skipped. More frames consume more memory and
do not automatically produce a better reconstruction.

### 2. Inspect the result

After reconstruction, use the demo controls to:

- Rotate, pan, and zoom the 3D view.
- Show or hide the estimated cameras.
- Toggle the mesh display.
- Raise the confidence percentile to remove low-confidence geometry.
- Filter black or white backgrounds when appropriate.
- Inspect the depth, normal, and measurement views.

If the model contains floating points or noisy surfaces, increase the
confidence threshold gradually. If parts of the subject disappear, reduce it.

### 3. Find the saved results

The app creates a timestamped directory inside the Map Anything repository:

```text
~/Projects/map-anything/input_images_YYYYMMDD_HHMMSS_ffffff/
```

It contains:

- `images/` — frames extracted from the uploaded video.
- `predictions.npz` — reconstruction predictions.
- `glbscene_*.glb` — the reconstructed 3D scene.

The `.glb` file can be opened in tools such as Blender. Copy the entire
timestamped directory somewhere permanent before clearing inputs or deleting
the Map Anything checkout.

## Memory guidance for Apple silicon

The Local Gradio Demo currently runs its reconstruction without Map Anything's
memory-efficient inference mode. Long videos or short sampling intervals can
therefore use a large amount of unified memory.

If macOS reports `MPS backend out of memory`:

1. Close other memory-heavy applications.
2. Restart the Gradio process to release cached model and tensor memory.
3. Increase the video sampling interval so fewer frames are extracted.
4. Start with 20–40 frames and increase only after a successful test.
5. Use a shorter MP4 containing only the useful orbit or grid pass.

As a last resort, Map Anything can be started with the MPS allocation limit
disabled:

```bash
PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 python scripts/gradio_app.py
```

This can allow PyTorch to consume nearly all available unified memory and may
make macOS unstable. Save other work first. Reducing the number of input frames
is the safer solution.

## Troubleshooting

### `ModuleNotFoundError: No module named 'mcap_ros2'`

Activate the converter environment:

```bash
conda activate dexi-video
python -m pip show mcap-ros2-support
```

If the package is missing:

```bash
python -m pip install -r requirements.txt
```

### `ffmpeg` is not found

```bash
conda env update -f environment.yml --prune
conda activate dexi-video
```

### The converter found no messages

The default topic is `/cam0/image_raw/compressed`. If the recording used a
different topic, pass it explicitly:

```bash
python mcap_to_mp4.py input.mcap output.mp4 \
  --topic /different/image/topic
```

### The MP4 plays at the wrong speed

Set the output frame rate to match the recorded camera rate:

```bash
python mcap_to_mp4.py input.mcap output.mp4 --fps 15 --flip 180
```

### `conda: command not found`

Close and reopen Terminal after installing Conda. If it is still unavailable,
initialize Conda for the current shell and restart Terminal:

```bash
~/miniconda3/bin/conda init zsh
```

The path may be `~/anaconda3/bin/conda` if Anaconda was installed instead.

### The Gradio page does not open

Keep the Python process running and copy the exact local URL printed in the
terminal. Confirm that no other process is using the same port.

### Reconstruction is noisy or incomplete

- Confirm the MP4 is upright before upload.
- Use a slower section of the flight with less motion blur.
- Include views around the subject, not only from one direction.
- Keep consecutive frames overlapped while removing near-identical frames.
- Avoid reflective, transparent, uniformly colored, or moving subjects.
- Try a different sampling interval.

### Remove the environments

```bash
conda deactivate
conda env remove -n dexi-video
conda env remove -n mapanything
```

## Output and accuracy notes

Map Anything creates a metric 3D reconstruction, point cloud, estimated camera
poses, depth data, and a GLB visualization. It is not automatically a
survey-grade, georeferenced orthomosaic workflow. Validate measurements before
using them for engineering, navigation, inspection, or safety decisions.

MP4 is convenient because the Gradio app accepts video directly, but conversion
introduces another compression pass. Preserve the original MCAP as the source
recording.

## Map Anything licensing

The Local Gradio Demo currently uses `facebook/map-anything` by default. The
upstream project identifies this checkpoint as CC-BY-NC 4.0. An Apache 2.0
checkpoint is also available for commercial-friendly use. Review the upstream
model-selection and licensing notes before distributing or commercializing
results.

## Upstream references

- [Map Anything repository and current quick start](https://github.com/facebookresearch/map-anything)
- [Map Anything online demo](https://huggingface.co/spaces/facebook/map-anything)
- [PyTorch installation guide](https://pytorch.org/get-started/locally/)

