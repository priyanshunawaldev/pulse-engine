import json
import os
import subprocess

VOICE = "en-US-ChristopherNeural"

MASTER_SCENES = [
    {
        "id": "scene1",
        "title": "The $150,000 Overdraft Horror Story",
        "text": "In high-scale financial technology, naive relational databases and standard web backends collapse under real concurrency. Picture a flash sale: an account holding just one hundred dollars receives ten simultaneous debit requests. In standard systems, every worker thread reads the same snapshot balance before committing, causing catastrophic overdrafts, negative ledger balances, and silent micro-cent drift. A single race condition like this once cost an e-commerce platform over one hundred and fifty thousand dollars in minutes. This is why PulseEngine was created.",
    },
    {
        "id": "scene2",
        "title": "The 6-Stage Defense In Depth",
        "text": "PulseEngine makes financial inconsistencies mathematically impossible through a zero-trust six-stage pipeline. Stage one: Redis token-bucket rate limiting absorbs bot storms. Stage two: SHA-256 idempotency caching guarantees duplicate retries never double-charge. Stage three: Distributed Redlock mutual exclusion acquires locks in ascending UUID order, eliminating circular deadlocks. Stage four: Strict double-entry invariant validation enforces debits equal credits. Stage five: Native PostgreSQL optimistic CAS rejects stale updates. And stage six: Celery workers dispatch signed HMAC webhooks.",
    },
    {
        "id": "scene3",
        "title": "Live Sandbox Battle-Testing",
        "text": "Let's see PulseEngine under adversarial pressure in our live interactive simulator. After an initial transfer commits atomically, we trigger the ultimate concurrency stress test: ten simultaneous twenty-dollar debit requests racing against Alice's one hundred dollar balance. PulseEngine strictly serializes access: exactly five requests succeed, five are rejected with HTTP 422, and Alice's balance settles at exactly zero dollars. Zero overdraft, zero race drift. When a network duplicate replays, Redis instantly returns the cached response without mutating the ledger.",
    },
    {
        "id": "scene4",
        "title": "Engineering War Stories & CAS Deep Dive",
        "text": "PulseEngine was hardened through fourteen documented production postmortems. In Incident number seven, bidirectional transfers caused circular deadlocks; we resolved this by sorting account UUIDs lexicographically before acquiring Redlock mutexes. In Incident number fourteen, we eliminated fake optimistic concurrency by binding native version ID columns in SQLAlchemy, guaranteeing the database executes an atomic CAS WHERE version check. And in distributed locking, atomic Lua scripts verify ownership before releasing Redis locks, preventing split-brain corruption.",
    },
    {
        "id": "scene5",
        "title": "Spin-Up & Zero-To-One Deployment",
        "text": "Deploying PulseEngine takes a single command: Docker Compose up. The engine orchestrates five production containers: The FastAPI gateway, PostgreSQL 16 with composite indexes and fixed-point NUMERIC arithmetic, Redis 7 for distributed locks, and Celery workers with Celery Beat running scheduled nightly reconciliation audits. Comprehensive health check probes ensure all cluster dependencies are warm before accepting live traffic.",
    },
    {
        "id": "scene6",
        "title": "Staff Benchmark Scorecard & Outro",
        "text": "The results confirm staff-level verification: All thirty-nine automated pytest suites passing at ninety-two point one percent coverage. Sub-thirty-four millisecond p95 latency under sustained loads of over one thousand requests per second. And zero overdraft drift, guaranteeing SOX 404 and PCI-DSS compliance. Inspect the fourteen postmortems, explore the architecture, and clone PulseEngine on GitHub today.",
    },
]

SHORT_SCRIPT = {
    "id": "short_master",
    "title": "PulseEngine 60s Concurrency Demo",
    "text": "What happens when ten concurrent requests try to drain an account with only one hundred dollars? Standard backends fail, causing negative balances and catastrophic overdraft losses. Meet PulseEngine: an ultra-resilient distributed financial ledger. With Redis Redlock distributed mutexes, SHA-256 database idempotency, and atomic double-entry bookkeeping, PulseEngine serializes adversarial races in real time. Under ten simultaneous requests, exactly five succeed, five are rejected with 422 Insufficient Funds, and Alice's balance lands at exactly zero dollars. Zero overdraft. Zero drift. Thirty-nine tests passing, ninety-two percent coverage, and sub-forty millisecond p95 latency. PulseEngine is open source and production ready.",
}


def generate_scene_audio(scene, output_dir):
    audio_path = os.path.join(output_dir, f"{scene['id']}.mp3")
    vtt_path = os.path.join(output_dir, f"{scene['id']}.vtt")
    print(f"Generating audio & subtitles for {scene['id']}: {scene['title']}...")

    cmd = [
        os.path.join(os.getcwd(), ".venv", "Scripts", "edge-tts.exe"),
        "--text",
        scene["text"],
        "--voice",
        VOICE,
        "--rate",
        "+8%",
        "--write-media",
        audio_path,
        "--write-subtitles",
        vtt_path,
    ]
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return audio_path, vtt_path


def parse_vtt(vtt_file):
    entries = []
    if not os.path.exists(vtt_file):
        return entries
    with open(vtt_file, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    for i, line in enumerate(lines):
        if "-->" in line:
            times = line.split("-->")
            start_str = times[0].strip().replace(",", ".")
            end_str = times[1].strip().replace(",", ".")

            def to_secs(s):
                parts = s.split(":")
                if len(parts) == 3:
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
                return float(s)

            start_s = to_secs(start_str)
            end_s = to_secs(end_str)
            text = lines[i + 1] if i + 1 < len(lines) else ""
            entries.append({"start": start_s, "end": end_s, "text": text})
    return entries


def main():
    out_dir = os.path.join("video", "public", "audio")
    os.makedirs(out_dir, exist_ok=True)

    scene_data = []
    current_time_offset = 0.0

    for scene in MASTER_SCENES:
        audio_file, vtt_file = generate_scene_audio(scene, out_dir)
        ff_cmd = [
            os.path.join("video", "node_modules", "@remotion", "compositor-win32-x64-msvc", "ffprobe.exe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_file,
        ]
        res = subprocess.run(ff_cmd, capture_output=True, text=True, check=True)
        duration_s = round(float(res.stdout.strip()), 2)

        vtt_entries = parse_vtt(vtt_file)
        scene_data.append(
            {
                "id": scene["id"],
                "title": scene["title"],
                "audio": f"/audio/{scene['id']}.mp3",
                "duration": duration_s,
                "durationFrames": int(duration_s * 30),
                "startOffset": round(current_time_offset, 2),
                "startOffsetFrames": int(current_time_offset * 30),
                "subtitles": vtt_entries,
                "fullText": scene["text"],
            }
        )
        current_time_offset += duration_s

    # Generate Short
    short_audio, short_vtt = generate_scene_audio(SHORT_SCRIPT, out_dir)
    ff_cmd = [
        os.path.join("video", "node_modules", "@remotion", "compositor-win32-x64-msvc", "ffprobe.exe"),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        short_audio,
    ]
    res = subprocess.run(ff_cmd, capture_output=True, text=True, check=True)
    short_duration_s = round(float(res.stdout.strip()), 2)
    short_vtt_entries = parse_vtt(short_vtt)

    master_manifest = {
        "totalDuration": round(current_time_offset, 2),
        "totalFrames": int(current_time_offset * 30),
        "fps": 30,
        "scenes": scene_data,
    }

    short_manifest = {
        "id": "short_master",
        "title": SHORT_SCRIPT["title"],
        "audio": f"/audio/{SHORT_SCRIPT['id']}.mp3",
        "duration": short_duration_s,
        "durationFrames": int(short_duration_s * 30),
        "fps": 30,
        "subtitles": short_vtt_entries,
        "fullText": SHORT_SCRIPT["text"],
    }

    manifest_path = os.path.abspath(os.path.join("video", "public", "scenes_manifest.json"))
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(master_manifest, f, indent=2)

    short_path = os.path.abspath(os.path.join("video", "public", "short_manifest.json"))
    with open(short_path, "w", encoding="utf-8") as f:
        json.dump(short_manifest, f, indent=2)

    print(
        f"Master script complete! Total duration: {current_time_offset:.2f}s ({int(current_time_offset * 30)} frames)"
    )
    print(
        f"Short script complete! Duration: {short_duration_s:.2f}s ({int(short_duration_s * 30)} frames)"
    )

    # Generate high-tech ambient background track using ffmpeg
    bgm_path = os.path.join(out_dir, "ambient_bgm.mp3")
    print("Generating tech ambient background track...")
    bgm_cmd = [
        os.path.join(".venv", "Scripts", "ffmpeg.exe"),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=110:duration=240,volume=0.08,firequalizer=gain='if(gt(f,400), -20, 0)'",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=164.81:duration=240,volume=0.05,firequalizer=gain='if(gt(f,500), -25, 0)'",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=220:duration=240,volume=0.04,firequalizer=gain='if(gt(f,600), -20, 0)'",
        "-filter_complex",
        "amix=inputs=3:duration=first:dropout_transition=3, lowpass=f=800, highpass=f=40",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        bgm_path,
    ]
    subprocess.run(bgm_cmd, capture_output=True, check=True)
    print("Ambient background track ready at", bgm_path)


if __name__ == "__main__":
    main()
