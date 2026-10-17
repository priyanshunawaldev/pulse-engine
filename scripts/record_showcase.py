import asyncio
import os
import subprocess

from playwright.async_api import async_playwright


async def record_showcase():
    video_out_dir = os.path.abspath(os.path.join("video", "public", "video"))
    screenshots_dir = os.path.abspath(os.path.join("video", "public", "screenshots"))
    os.makedirs(video_out_dir, exist_ok=True)
    os.makedirs(screenshots_dir, exist_ok=True)

    html_path = "file:///" + os.path.abspath("pulseengine_showcase.html").replace("\\", "/")
    print(f"Loading showcase HTML from {html_path}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1.0,
            record_video_dir=video_out_dir,
            record_video_size={"width": 1920, "height": 1080},
        )

        page = await context.new_page()
        await page.goto(html_path, wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(screenshots_dir, "01_initial_sim.png"))

        print("Triggering Scenario: Normal Transfer ($25)...")
        await page.evaluate("runScenario('transfer')")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=os.path.join(screenshots_dir, "02_transfer_done.png"))

        print("Triggering Scenario: 10 Concurrent $20 Debits (Race Condition)...")
        await page.evaluate("runScenario('race')")
        await page.wait_for_timeout(3500)
        await page.screenshot(path=os.path.join(screenshots_dir, "03_race_concurrency.png"))

        print("Triggering Scenario: Replay Duplicate Key...")
        await page.evaluate("runScenario('idempotency')")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=os.path.join(screenshots_dir, "04_idempotency_replay.png"))

        print("Triggering Scenario: Nightly Audit Reconciliation...")
        await page.evaluate("runScenario('reconcile')")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=os.path.join(screenshots_dir, "05_audit_reconcile.png"))

        print("Switching Tab: System Architecture...")
        await page.evaluate("switchTab('arch')")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(screenshots_dir, "06_tab_architecture.png"))

        print("Switching Tab: Founder & Executive Pitch...")
        await page.evaluate("switchTab('pitch')")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(screenshots_dir, "07_tab_pitch.png"))

        print("Switching Tab: 14 Engineering Incidents...")
        await page.evaluate("switchTab('incidents')")
        await page.wait_for_timeout(3500)
        await page.screenshot(path=os.path.join(screenshots_dir, "08_tab_incidents.png"))

        print("Switching Tab: Stress Test Scorecard...")
        await page.evaluate("switchTab('benchmarks')")
        await page.wait_for_timeout(3500)
        await page.screenshot(path=os.path.join(screenshots_dir, "09_tab_benchmarks.png"))

        print("Returning to Simulator Tab...")
        await page.evaluate("switchTab('sim')")
        await page.wait_for_timeout(2000)

        video = page.video
        await page.close()
        await context.close()
        await browser.close()

        if video:
            video_path = await video.path()
            print(f"Captured video saved at {video_path}")
            dest_mp4 = os.path.join(video_out_dir, "showcase_demo.mp4")
            print(f"Transcoding {video_path} -> {dest_mp4}...")
            subprocess.run(
                [
                    os.path.join(".venv", "Scripts", "ffmpeg.exe"),
                    "-y",
                    "-i",
                    video_path,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    dest_mp4,
                ],
                check=True,
            )
            print("Successfully encoded showcase_demo.mp4!")


if __name__ == "__main__":
    asyncio.run(record_showcase())
