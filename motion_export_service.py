import base64
import os
import re
import shutil
import subprocess
import tempfile


class MotionExportError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        super().__init__(payload.get("message", "motion export error"))


DATA_URL_RE = re.compile(r"^data:(?P<mime>[-\w.+/]+);base64,(?P<data>.+)$", re.S)


def clean_filename(value, fallback="mrk-motion.m4v"):
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "-", str(value or "")).strip(".-")
    if not name:
        name = fallback
    if not name.lower().endswith(".m4v"):
        name = re.sub(r"\.[^.]+$", "", name) + ".m4v"
    return name


def transcode_m4v(payload):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise MotionExportError(503, {
            "error": "missing_ffmpeg",
            "message": "当前服务没有 ffmpeg，无法把浏览器录制结果转成 M4V。",
        })

    match = DATA_URL_RE.match(str(payload.get("video_data_url") or ""))
    if not match:
        raise MotionExportError(400, {
            "error": "bad_video",
            "message": "缺少可转码的视频 data URL。",
        })

    try:
        video_bytes = base64.b64decode(match.group("data"), validate=True)
    except Exception as exc:
        raise MotionExportError(400, {
            "error": "bad_video",
            "message": f"视频数据解析失败：{exc}",
        })

    max_bytes = int(os.environ.get("MOTION_EXPORT_MAX_BYTES", str(80 * 1024 * 1024)))
    if len(video_bytes) > max_bytes:
        raise MotionExportError(413, {
            "error": "video_too_large",
            "message": "视频太大，无法在本地接口里转码。",
        })

    filename = clean_filename(payload.get("filename"))
    with tempfile.TemporaryDirectory(prefix="mrk-motion-") as tmpdir:
        source_path = os.path.join(tmpdir, "source.webm")
        output_path = os.path.join(tmpdir, filename)
        with open(source_path, "wb") as file:
            file.write(video_bytes)

        command = [
            ffmpeg,
            "-y",
            "-i", source_path,
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
            raise MotionExportError(502, {
                "error": "ffmpeg_failed",
                "message": "M4V 转码失败：" + " / ".join(detail),
            })

        with open(output_path, "rb") as file:
            encoded = base64.b64encode(file.read()).decode("ascii")

    return {
        "filename": filename,
        "mime": "video/x-m4v",
        "video_data_url": f"data:video/x-m4v;base64,{encoded}",
    }
