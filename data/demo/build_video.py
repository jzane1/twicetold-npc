"""Build the review cut from captured video, Ledger frames, and a real SSE trace.

Requires Pillow and ffmpeg. All inputs are retained; this edits presentation only.
Run with --take <run directory> --event-video <capture.mp4> --ffmpeg <ffmpeg.exe>.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
BG = (20, 22, 26)
INK = (231, 235, 243)
DIM = (158, 170, 190)
BLUE = (140, 174, 244)
GOLD = (225, 180, 104)
FONT_ROOT = Path("C:/Windows/Fonts")


def font(size, bold=False):
    return ImageFont.truetype(
        str(FONT_ROOT / ("segoeuib.ttf" if bold else "segoeui.ttf")), size
    )


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if line and draw.textlength(candidate, font=fnt) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return "\n".join(lines)


def text(draw, xy, value, size=32, color=INK, width=1700, bold=False):
    fnt = font(size, bold)
    draw.multiline_text(
        xy, wrap(draw, value, fnt, width), font=fnt, fill=color, spacing=12
    )


def title_card(title, sub):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    text(d, (90, 75), "TWICETOLD / ENGINEERING THE MEMORY", 23, BLUE, bold=True)
    text(d, (90, 180), title, 70, bold=True)
    text(d, (94, 290), sub, 30, DIM)
    return im


def run(command, **kwargs):
    subprocess.run(command, check=True, **kwargs)


def make_thumbnail(portrait, destination):
    im = Image.new("RGB", (W, H), BG)
    im.paste(portrait.crop((430, 0, 1510, 1080)), (840, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 915, H), fill=BG)
    text(d, (75, 90), "TWICETOLD", 37, BLUE, bold=True)
    d.multiline_text(
        (70, 260),
        "Same event.\nDifferent\nmemories.",
        font=font(91, True),
        fill=INK,
        spacing=12,
    )
    text(d, (77, 850), "Persistent memory for NPCs", 33, DIM, width=780)
    text(d, (77, 920), "UNITY + FASTAPI + POSTGRES", 23, BLUE)
    im.resize((1280, 720), Image.Resampling.LANCZOS).save(destination, quality=94)


def write_ass(srt_path):
    """Use explicit video coordinates so subtitle size survives renderers."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Segoe UI,34,&H00FFFFFF,&H00FFFFFF,&H0010141A,&H90000000,0,0,0,0,100,100,0,0,1,2,0,2,90,90,24,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for block in srt_path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.splitlines()
        start, end = lines[1].split(" --> ")
        start, end = (s.lstrip("0").replace(",", ".")[:-1] for s in (start, end))
        # ASS uses h:mm:ss.cc; retain the zero hour for this short film.
        start, end = ("0" + s if s.startswith(":") else s for s in (start, end))
        caption = " ".join(lines[2:]).replace("{", "").replace("}", "")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{caption}")
    srt_path.with_suffix(".ass").write_text(
        header + "\n".join(events) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--take", required=True, type=Path)
    parser.add_argument("--event-video", required=True, type=Path)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--output", type=Path, default=Path("data/demo/output"))
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error("ffmpeg was not found; pass --ffmpeg")
    take, out = args.take.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    ff = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    enc = [
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
    ]
    clips = []

    def clip_image(path, seconds, name):
        dest = out / (name + ".mp4")
        run(
            ff
            + [
                "-loop",
                "1",
                "-framerate",
                str(FPS),
                "-i",
                str(path),
                "-t",
                str(seconds),
            ]
            + enc
            + [str(dest)]
        )
        clips.append(dest)

    def clip_video(path, seconds, name, overlay=None, start=0):
        dest = out / (name + ".mp4")
        command = ff + ["-ss", str(start), "-i", str(path)]
        if overlay:
            command += [
                "-loop",
                "1",
                "-i",
                str(overlay),
                "-filter_complex",
                "[0:v][1:v]overlay=0:0:shortest=1",
            ]
        command += ["-t", str(seconds)] + enc + [str(dest)]
        run(command)
        clips.append(dest)

    def label(name, subtitle, filename, top=False):
        im = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(im)
        y = 65 if top else 735
        d.rounded_rectangle((65, y, 905, y + 220), radius=18, fill=(14, 19, 26, 235))
        text(d, (98, y + 22), name, 65, bold=True)
        text(d, (100, y + 115), subtitle, 30, DIM, width=770)
        path = out / filename
        im.save(path)
        return path

    clip_video(
        args.event_video.resolve(),
        15,
        "01-event",
        label("TWICETOLD", "Persistent memory for narrative agents", "title.png", True),
        start=2,
    )
    clip_video(
        take / "henry-portrait.mp4",
        6,
        "02-henry",
        label("Henry", "A merchant wary of easy money", "henry-label.png"),
    )
    clip_video(
        take / "joan-portrait.mp4",
        6,
        "03-joan",
        label(
            "Joan", "A neighbor who tries to see the best in people", "joan-label.png"
        ),
    )

    # The in-app browser's screenshot export carries an unused right/bottom
    # region at Windows display scaling. Crop only that empty capture region.
    # No text or other page content is changed.
    for day, seconds in ((0, 12), (60, 9), (90, 7), (180, 17)):
        im = Image.open(take / f"ledger-day{day}.png").convert("RGB")
        im = im.crop((0, 0, 1536, 864)).resize((W, H), Image.Resampling.LANCZOS)
        path = out / f"ledger-{day}.png"
        im.save(path)
        clip_image(path, seconds, f"ledger-{day}")

    rehearsal = json.loads((take / "rehearsal.json").read_text(encoding="utf-8-sig"))
    h = next(w for w in rehearsal["witnesses"] if w["stable_id"] == "henry")
    chain = sorted(h["ages"][-1]["chain"]["details"], key=lambda row: row["valid_at"])
    im = title_card(
        "One memory. Every version.", "The original observation remains unchanged."
    )
    d = ImageDraw.Draw(im)
    for i, row in enumerate(chain):
        x = 90 + i * 450
        d.rounded_rectangle(
            (x, 440, x + 410, 710),
            radius=18,
            fill=(28, 33, 43),
            outline=(61, 75, 97),
            width=2,
        )
        text(
            d,
            (x + 26, 470),
            ("Original" if i == 0 else ["", "+60 days", "+90 days", "+180 days"][i]),
            34,
            GOLD if i else BLUE,
            bold=True,
        )
        text(d, (x + 26, 540), row["write_cause"], 24, DIM, width=365)
        text(d, (x + 26, 606), "Version " + row["detail_id"][:8], 22, DIM, width=365)
    text(d, (95, 785), "Memory ID  " + h["ingest"]["memory_id"], 26, DIM)
    im.save(out / "chain.png")
    clip_image(out / "chain.png", 8, "08-chain")

    repeats = sorted((take / "live").glob("*_henry.json"))
    a, b = [json.loads(p.read_text(encoding="utf-8-sig")) for p in repeats[:2]]
    assert [(i["MemoryId"], i["Content"]) for i in a["Items"]] == [
        (i["MemoryId"], i["Content"]) for i in b["Items"]
    ]
    r = b["Instrumentation"]["Retrieval"]
    assert r["WriteBacks"] == 0 and r["ReconstructionOutputTokens"] == 0
    im = title_card(
        "Recall again. Reuse the memory.",
        "Verified on the same C# session and the same saved memory IDs.",
    )
    d = ImageDraw.Draw(im)
    for i, (number, heading) in enumerate(
        (
            (r["CacheHits"], "cache hits"),
            (r["WriteBacks"], "new tellings"),
            (0, "reconstruction calls"),
        )
    ):
        x = 95 + i * 610
        text(d, (x, 440), str(number), 130, BLUE if i == 0 else INK, bold=True)
        text(d, (x, 610), heading, 34, DIM, width=565)
    text(
        d,
        (98, 790),
        "Stored memory text: byte-identical. Spoken wording can still vary.",
        30,
        DIM,
    )
    im.save(out / "cache.png")
    clip_image(out / "cache.png", 9, "09-cache")

    stream = json.loads(
        (take / "live-gate-stream.json").read_text(encoding="utf-8-sig")
    )
    run(
        ff
        + [
            "-ss",
            "3",
            "-i",
            str(take / "henry-portrait.mp4"),
            "-frames:v",
            "1",
            str(out / "henry-still.png"),
        ]
    )
    background = Image.open(out / "henry-still.png").convert("RGB")
    make_thumbnail(background, out / "demo-thumbnail.jpg")
    gate_path = out / "10-gate.mp4"
    command = (
        ff
        + [
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{W}x{H}",
            "-framerate",
            str(FPS),
            "-i",
            "pipe:0",
        ]
        + enc
        + [str(gate_path)]
    )
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    for frame in range(17 * FPS):
        ms = frame * 1000 / FPS
        im = Image.new("RGB", (W, H), BG)
        im.paste(background, (-320, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((930, 55, 1865, 938), radius=18, fill=(18, 23, 31))
        text(d, (965, 86), "LIVE RECALL / HENRY", 24, BLUE, bold=True)
        text(d, (965, 140), stream["question"], 33, INK, width=850, bold=True)
        content = "".join(e.get("text", "") for e in stream["chunks"] if e["ms"] <= ms)
        text(
            d,
            (965, 272),
            content or "Reconstructing newly retrieved memories…",
            32,
            INK if content else DIM,
            width=845,
        )
        done = ms >= stream["elapsed_ms"]
        count = len(stream["loaded_after"] if done else stream["loaded_before"])
        text(d, (965, 756), f"Loaded memories: {count}", 28, GOLD, bold=True)
        if done:
            text(
                d,
                (965, 810),
                "Gate opened · novelty signal · 3 memories added",
                25,
                DIM,
                width=845,
            )
        text(d, (965, 886), "Recorded C# client stream · original timing", 20, DIM)
        process.stdin.write(im.tobytes())
    process.stdin.close()
    if process.wait():
        raise RuntimeError("ffmpeg stream encoding failed")
    clips.append(gate_path)

    im = title_card("Memory you can inspect.", "Twicetold / Built by Jackson Zane")
    d = ImageDraw.Draw(im)
    text(d, (95, 455), "FastAPI  +  PostgreSQL / pgvector  +  Unity C#", 43, INK)
    text(
        d,
        (95, 570),
        "Versioned memory · measured retrieval · persistent reconstruction",
        35,
        DIM,
    )
    text(d, (95, 750), "github.com/jzane1/twicetold-npc", 49, BLUE, bold=True)
    im.save(out / "end.png")
    clip_image(out / "end.png", 10, "11-end")

    captions = [
        (0, 7, "I built Twicetold, a persistent memory service for narrative agents."),
        (
            7,
            15,
            "Here, a fisherman leaves a pouch of gold behind. Henry and Joan witness the same event.",
        ),
        (15, 21, "Henry is a merchant who learned to distrust easy money."),
        (21, 27, "Joan tries to see the best in people."),
        (
            27,
            33,
            "The original observation is stored unchanged. A few essential spans become fixed gist.",
        ),
        (33, 39, "The rest is detail that can fade."),
        (
            39,
            48,
            "Sixty days later, recall reconstructs the memory using identity, surviving details, and the previous telling.",
        ),
        (
            48,
            55,
            "Each accepted reconstruction becomes the starting point for the next.",
        ),
        (
            55,
            64,
            "At six months, Henry suspects somebody has a reason for leaving that gold.",
        ),
        (
            64,
            72,
            "Joan is left wondering what happened to the fisherman. The remembered meaning diverges.",
        ),
        (
            72,
            80,
            "These are stored memories. Every earlier version remains inspectable beside the original.",
        ),
        (
            80,
            89,
            "Repeating recall reuses the same memory text: three cache hits, no new telling.",
        ),
        (
            89,
            99,
            "Change the subject to Rowan, and the retrieval gate loads history into the ongoing conversation.",
        ),
        (99, 106, "This is the real streamed response through the Unity C# client."),
        (
            106,
            116,
            "FastAPI, Postgres, and Unity. Code and reproduction steps are on GitHub.",
        ),
    ]

    def stamp(seconds):
        return f"00:{int(seconds) // 60:02}:{int(seconds) % 60:02},000"

    srt = "\n\n".join(
        f"{i + 1}\n{stamp(start)} --> {stamp(end)}\n"
        + "\n".join(textwrap.wrap(line, 78))
        for i, (start, end, line) in enumerate(captions)
    )
    (out / "rough.srt").write_text(srt + "\n", encoding="utf-8")
    write_ass(out / "rough.srt")
    (out / "clips.txt").write_text(
        "\n".join("file '" + p.name + "'" for p in clips), encoding="utf-8"
    )
    run(
        ff
        + [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            "clips.txt",
            "-c",
            "copy",
            "picture.mp4",
        ],
        cwd=out,
    )
    run(
        ff
        + [
            "-i",
            "picture.mp4",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-vf",
            "subtitles=rough.ass",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            "twicetold-rough-cut.mp4",
        ],
        cwd=out,
    )
    (out / "provenance.json").write_text(
        json.dumps(
            {
                "memory_take": rehearsal["take_id"],
                "event_capture": str(args.event_video.resolve()),
                "event_capture_note": "Camera reenactment of the canonical event; no memory text from its integration-test take is used.",
                "narration": "pending user recording",
                "stream": str(take / "live-gate-stream.json"),
                "duration_seconds": 116,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(out / "twicetold-rough-cut.mp4")


if __name__ == "__main__":
    main()
