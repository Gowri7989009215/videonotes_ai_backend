"""
Video processing worker — handles the full pipeline:
1. Download YouTube video (yt-dlp) or use uploaded file
2. Extract frames with ffmpeg
3. Fetch/generate transcript
4. Generate PDF
5. Generate AI notes
6. Send completion email
7. Cleanup temp files
"""

import os
import subprocess
import shutil
import asyncio
from typing import List, Dict, Optional
from config.settings import settings
from config.database import query_one, execute as db_execute


from utils.background import run_async_in_main as _run_async

async def _update_progress(job_id: str, progress: int):
    """Update job progress in database."""
    from models.video import update_job_progress
    await update_job_progress(job_id, progress)


async def _mark_processing(job_id: str):
    from models.video import update_job_status
    await update_job_status(job_id, "processing")


async def _mark_completed(job_id: str, pdf_path: str, frame_count: int):
    from models.video import update_job_status, create_output
    await update_job_status(job_id, "completed")
    await create_output(job_id, pdf_path, frame_count)


async def _mark_failed(job_id: str, error_message: str):
    from models.video import update_job_status
    await update_job_status(job_id, "failed", error_message)


async def _create_note(job_id: str, user_id: str, note_type: str, content, provider: str, model: str):
    from models.video import create_note
    await create_note(job_id, user_id, note_type, content, provider, model)


async def _get_user_email(user_id: str) -> Optional[str]:
    row = await query_one("SELECT email FROM users WHERE id = $1::uuid", [user_id])
    return row["email"] if row else None


# ============================================================
# FFmpeg helpers
# ============================================================

def extract_frames(video_path: str, interval_seconds: int, frames_dir: str) -> None:
    """Extract frames from a video at given intervals using ffmpeg."""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{interval_seconds}",
        os.path.join(frames_dir, "frame_%06d.png"),
        "-y",  # overwrite
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"[FFmpeg] stderr: {result.stderr[:500]}")
        # Don't raise if some frames were extracted
        frame_files = [f for f in os.listdir(frames_dir) if f.endswith(".png")]
        if not frame_files:
            raise RuntimeError(f"FFmpeg frame extraction failed: {result.stderr[:200]}")


def extract_audio(video_path: str, audio_path: str) -> None:
    """Extract audio as WAV from video using ffmpeg."""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn",  # no video
        "-acodec", "pcm_s16le",
        "-ac", "1",  # mono
        "-ar", "16000",  # 16kHz
        audio_path,
        "-y",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[:200]}")


# ============================================================
# Transcript matching
# ============================================================

def match_transcript_to_frames(
    frames_dir: str,
    segments: List[Dict],
    interval_seconds: int,
) -> List[Dict]:
    """Match transcript segments to extracted frames by timestamp."""
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    pages = []
    for idx, file in enumerate(frame_files):
        frame_start_time = idx * interval_seconds
        frame_end_time = frame_start_time + interval_seconds
        
        interval_text = []
        for seg in segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", seg_start + interval_seconds)
            
            # Check if segment overlaps with the frame's time interval
            if seg_start < frame_end_time and seg_end > frame_start_time:
                text_content = seg.get("text", "").strip()
                if text_content:
                    interval_text.append(text_content)
                    
        pages.append({
            "filePath": os.path.join(frames_dir, file),
            "text": " ".join(interval_text).replace("  ", " "),
        })
    return pages


# ============================================================
# PDF generation
# ============================================================

def generate_pdf(pages: List[Dict], pdf_path: str, mode: str) -> None:
    """Generate a PDF with frames and optional transcript text."""
    from fpdf import FPDF
    from PIL import Image

    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    
    # Try to load Arial font to support proper transcripts (unicode)
    try:
        pdf.add_font("Arial", "", r"C:\Windows\Fonts\arial.ttf")
        pdf.add_font("Arial", "B", r"C:\Windows\Fonts\arialbd.ttf")
        base_font = "Arial"
    except Exception as e:
        print(f"[PDF] Could not load Arial font: {e}")
        base_font = "Helvetica"

    for page_data in pages:
        file_path = page_data["filePath"]
        text = page_data.get("text", "")

        pdf.add_page()
        page_width = pdf.w - 40  # margins

        if os.path.exists(file_path):
            try:
                # Get image dimensions to fit properly
                with Image.open(file_path) as img:
                    img_w, img_h = img.size
                    # Calculate dimensions to fit in page
                    max_img_height = 120 if mode == "frames+transcript" and text else 200
                    ratio = min(page_width / img_w, max_img_height / img_h)
                    display_w = img_w * ratio
                    display_h = img_h * ratio
                    x = (pdf.w - display_w) / 2
                    pdf.image(file_path, x=x, y=20, w=display_w, h=display_h)
                    y_after_image = 20 + display_h + 10
            except Exception as e:
                print(f"[PDF] Error adding image {file_path}: {e}")
                y_after_image = 30
        else:
            y_after_image = 30

        if mode == "frames+transcript":
            pdf.set_y(y_after_image)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font(base_font, "B" if base_font == "Arial" else "BU", 12)
            pdf.cell(0, 8, "Transcript:", ln=True)
            pdf.set_font(base_font, "", 11)
            display_text = text if text else "(No transcript available for this segment)"
            pdf.multi_cell(0, 6, txt=display_text)

    pdf.output(pdf_path)


# ============================================================
# Main job handler
# ============================================================

def process_video_job(data: Dict) -> None:
    """
    Main video processing job handler.
    Runs synchronously in a worker thread.
    """
    job_id = data["jobId"]
    video_path = data["videoPath"]
    youtube_url = data.get("youtubeUrl")
    mode = data["mode"]
    interval_seconds = data["intervalSeconds"]
    user_id = data["userId"]
    video_title = data.get("title", "Untitled Video")

    storage_root = settings.storage_root
    frames_dir = os.path.join(storage_root, "frames", job_id)
    temp_dir = os.path.join(storage_root, "temp", job_id)
    pdf_dir = os.path.join(storage_root, "pdfs")

    active_ytdl_video_path = None

    try:
        _run_async(_mark_processing(job_id))
        _run_async(_update_progress(job_id, 5))

        os.makedirs(frames_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(pdf_dir, exist_ok=True)

        pages = []
        segments = []

        _run_async(_update_progress(job_id, 10))

        if youtube_url:
            # ── YouTube pipeline ──
            from services.youtube_service import extract_video_id, fetch_youtube_transcript_sync

            vid_id = extract_video_id(youtube_url) or "unknown"

            _run_async(_update_progress(job_id, 20))

            # Fetch transcript if needed
            if mode == "frames+transcript":
                segments = fetch_youtube_transcript_sync(vid_id)

            _run_async(_update_progress(job_id, 30))

            # Download video using yt-dlp
            from services.youtube_download import download_youtube_video
            active_ytdl_video_path = os.path.join(temp_dir, "ytdl_video.mp4")
            download_youtube_video(youtube_url, active_ytdl_video_path)

            _run_async(_update_progress(job_id, 45))

            # Extract frames
            extract_frames(active_ytdl_video_path, interval_seconds, frames_dir)

            _run_async(_update_progress(job_id, 50))

            frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
            if mode == "frames":
                pages = [{"filePath": os.path.join(frames_dir, f), "text": ""} for f in frame_files]
            else:
                pages = match_transcript_to_frames(frames_dir, segments, interval_seconds)

        else:
            # ── Local upload pipeline ──
            if mode == "frames+transcript":
                audio_path = os.path.join(temp_dir, "audio.wav")
                extract_audio(video_path, audio_path)

                # Try Whisper API for transcription
                if settings.openai_api_key:
                    print(f"[Worker] Starting OpenAI Whisper transcription for job {job_id}...")
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=settings.openai_api_key)
                        with open(audio_path, "rb") as audio_file:
                            resp = client.audio.transcriptions.create(
                                file=audio_file,
                                model="whisper-1",
                                response_format="verbose_json",
                                timestamp_granularities=["segment"],
                            )
                        segments_list = []
                        if isinstance(resp, dict) and "segments" in resp:
                            segments_list = resp["segments"]
                        elif hasattr(resp, "segments") and resp.segments:
                            segments_list = resp.segments

                        if segments_list:
                            segments = [
                                {
                                    "start": getattr(s, "start", s.get("start", 0) if isinstance(s, dict) else 0),
                                    "end": getattr(s, "end", s.get("end", 0) if isinstance(s, dict) else 0),
                                    "text": getattr(s, "text", s.get("text", "") if isinstance(s, dict) else "")
                                }
                                for s in segments_list
                            ]
                    except Exception as e:
                        print(f"[Worker] Whisper transcription failed: {e}")

                if not segments and settings.gemini_api_key:
                    print(f"[Worker] Starting Gemini transcription for job {job_id}...")
                    try:
                        import google.generativeai as genai
                        import json
                        genai.configure(api_key=settings.gemini_api_key)
                        
                        gemini_audio = genai.upload_file(path=audio_path)
                        
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        prompt = "Transcribe this audio exactly. Return ONLY a valid JSON array of objects, where each object has 'start' (float, in seconds), 'end' (float, in seconds), and 'text' (string). Do not include any other text or markdown formatting."
                        response = model.generate_content([prompt, gemini_audio])
                        
                        json_str = response.text.strip()
                        if json_str.startswith("```json"):
                            json_str = json_str[7:]
                        elif json_str.startswith("```"):
                            json_str = json_str[3:]
                        if json_str.endswith("```"):
                            json_str = json_str[:-3]
                        json_str = json_str.strip()
                        
                        segments_list = json.loads(json_str)
                        if segments_list:
                            segments = [
                                {
                                    "start": float(s.get("start", 0)),
                                    "end": float(s.get("end", 0)),
                                    "text": str(s.get("text", ""))
                                }
                                for s in segments_list
                            ]
                        
                        try:
                            gemini_audio.delete()
                        except Exception:
                            pass
                            
                    except Exception as e:
                        print(f"[Worker] Gemini transcription failed: {e}")

            _run_async(_update_progress(job_id, 25))
            extract_frames(video_path, interval_seconds, frames_dir)
            _run_async(_update_progress(job_id, 40))

            frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
            if mode == "frames":
                pages = [{"filePath": os.path.join(frames_dir, f), "text": ""} for f in frame_files]
            else:
                pages = match_transcript_to_frames(frames_dir, segments, interval_seconds)

        _run_async(_update_progress(job_id, 55))

        # ── Generate PDF ──
        pdf_path = os.path.join(pdf_dir, f"{job_id}.pdf")
        generate_pdf(pages, pdf_path, mode)

        _run_async(_update_progress(job_id, 65))

        # ── Generate AI notes ──
        if segments:
            print(f"[Worker] Generating AI notes for job {job_id}...")
            from services.ai_service import generate_all_notes
            notes = generate_all_notes(segments, video_title)

            if notes:
                _run_async(_update_progress(job_id, 80))

                for note_type, note_data in notes.items():
                    content = note_data.get("content")
                    if content and (isinstance(content, str) and len(content) > 0 or not isinstance(content, str)):
                        _run_async(_create_note(
                            job_id, user_id, note_type,
                            content, note_data["provider"], note_data["model"]
                        ))

        _run_async(_update_progress(job_id, 95))

        # ── Complete job ──
        _run_async(_mark_completed(job_id, pdf_path, len(pages)))
        _run_async(_update_progress(job_id, 100))

        # Send completion email
        try:
            email = _run_async(_get_user_email(user_id))
            if email:
                from utils.email import send_job_completion_email
                _run_async(send_job_completion_email(email, job_id))
        except Exception as e:
            print(f"[Worker] Failed to send completion email: {e}")

        print(f"[Worker] Job {job_id} completed successfully.")

    except Exception as e:
        print(f"[Worker] Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()
        _run_async(_mark_failed(job_id, str(e)))

    finally:
        # ── Cleanup ──
        try:
            if os.path.exists(frames_dir):
                shutil.rmtree(frames_dir, ignore_errors=True)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            # Purge uploaded local video
            if video_path and not youtube_url and os.path.exists(video_path):
                os.remove(video_path)
            # Purge downloaded YouTube video
            if active_ytdl_video_path and os.path.exists(active_ytdl_video_path):
                os.remove(active_ytdl_video_path)
        except Exception as cleanup_err:
            print(f"[Worker] Cleanup failed for job {job_id}: {cleanup_err}")
