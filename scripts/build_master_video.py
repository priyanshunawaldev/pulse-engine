import json
import os
import shutil
import subprocess
import sys


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    video_dir = os.path.join(root_dir, "video")
    out_dir = os.path.join(root_dir, "out")
    os.makedirs(out_dir, exist_ok=True)

    manifest_path = os.path.join(video_dir, "public", "scenes_manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    print(
        f"Master Composition: {len(manifest['scenes'])} scenes, total duration: {manifest['totalDuration']:.2f}s ({manifest['totalFrames']} frames @ {manifest['fps']} fps)"
    )

    temp_render = "master_render.mp4"
    final_master = os.path.join(out_dir, "pulseengine_master_16x9.mp4")
    print(f"Rendering Remotion master composition to {temp_render} in video dir...")

    cmd = [
        "npx.cmd" if sys.platform == "win32" else "npx",
        "remotion",
        "render",
        "PulseEngineMaster16x9",
        temp_render,
        "--concurrency=4",
    ]
    res = subprocess.run(cmd, cwd=video_dir)
    if res.returncode != 0:
        print(f"Error: Remotion render failed with code {res.returncode}")
        sys.exit(res.returncode)

    temp_path = os.path.join(video_dir, temp_render)
    if os.path.exists(temp_path):
        print(f"Moving {temp_path} -> {final_master}...")
        shutil.move(temp_path, final_master)
        print(f"Successfully moved! Output size: {os.path.getsize(final_master):,} bytes")
    else:
        print(f"Error: Expected render output {temp_path} not found!")
        sys.exit(1)

    print(f"\nMaster 16:9 Video successfully rendered at: {final_master}")

    # Inspect stream with ffprobe
    ffprobe_path = os.path.join(
        video_dir, "node_modules", "@remotion", "compositor-win32-x64-msvc", "ffprobe.exe"
    )
    if os.path.exists(ffprobe_path):
        probe_cmd = [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,avg_frame_rate,duration,nb_frames",
            "-of",
            "json",
            final_master,
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
        print("Master video stream info:\n", probe_res.stdout)


if __name__ == "__main__":
    main()
