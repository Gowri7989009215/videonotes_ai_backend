"""
Multi-provider AI service for generating notes, summaries, flashcards, etc.
Supports OpenAI, Google Gemini, and Anthropic Claude.
"""

from typing import Optional, List, Dict, Any
from config.settings import settings


def _get_available_provider() -> Optional[Dict[str, str]]:
    """Determine which AI provider is available."""
    if settings.openai_api_key:
        return {"provider": "openai", "model": "gpt-4o-mini"}
    if settings.gemini_api_key:
        return {"provider": "gemini", "model": "gemini-1.5-flash"}
    if settings.anthropic_api_key:
        return {"provider": "anthropic", "model": "claude-3-haiku-20240307"}
    return None


def _call_ai_sync(system_prompt: str, user_prompt: str) -> Dict[str, str]:
    """Call AI provider synchronously (runs in worker thread)."""
    info = _get_available_provider()
    if not info:
        return {"text": "", "provider": "none", "model": "none"}

    try:
        if info["provider"] == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=info["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=4000,
            )
            return {
                "text": resp.choices[0].message.content or "",
                "provider": info["provider"],
                "model": info["model"],
            }

        if info["provider"] == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(info["model"])
            resp = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
            return {
                "text": resp.text if resp.text else "",
                "provider": info["provider"],
                "model": info["model"],
            }

        if info["provider"] == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            resp = client.messages.create(
                model=info["model"],
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = resp.content[0].text if resp.content and resp.content[0].type == "text" else ""
            return {
                "text": text,
                "provider": info["provider"],
                "model": info["model"],
            }

    except Exception as e:
        print(f"[AI] {info['provider']} call failed: {e}")
        return {"text": "", "provider": info["provider"], "model": info["model"]}

    return {"text": "", "provider": "none", "model": "none"}


# ============================================================
# Transcript helpers
# ============================================================

def _format_transcript(segments: List[Dict]) -> str:
    if not segments:
        return "No transcript available."
    lines = []
    for s in segments:
        mins = int(s["start"] // 60)
        secs = int(s["start"] % 60)
        lines.append(f"[{mins}:{secs:02d}] {s['text']}")
    return "\n".join(lines)


def _truncate_transcript(text: str, max_chars: int = 30000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Transcript truncated for AI processing...]"


# ============================================================
# Note generation functions
# ============================================================

def generate_detailed_notes(segments: List[Dict], title: str = "Untitled") -> Dict:
    transcript = _truncate_transcript(_format_transcript(segments))
    system = "You are an expert note-taker. Generate comprehensive, well-structured notes from video transcripts. Use markdown formatting with headers, bullet points, and bold for key terms."
    user = f"Video title: {title}\n\nTranscript:\n{transcript}\n\nGenerate detailed, well-organized notes covering all key topics discussed in this video. Include section headers, main points, supporting details, and examples mentioned."
    return _call_ai_sync(system, user)


def generate_summary(segments: List[Dict], title: str = "Untitled") -> Dict:
    transcript = _truncate_transcript(_format_transcript(segments))
    system = "You are a concise summarizer. Create clear, informative summaries of video content."
    user = f"Video title: {title}\n\nTranscript:\n{transcript}\n\nWrite a 3-paragraph summary: (1) Overview and main thesis, (2) Key points and arguments, (3) Conclusions and takeaways."
    return _call_ai_sync(system, user)


def _parse_json_response(result: Dict) -> Dict:
    """Try to parse JSON from AI response text."""
    import json
    text = result["text"]
    # Remove markdown code fences
    text = text.replace("```json\n", "").replace("```json", "").replace("```\n", "").replace("```", "").strip()
    try:
        parsed = json.loads(text)
        return {**result, "parsed": parsed}
    except Exception:
        return {**result, "parsed": []}


def generate_chapters(segments: List[Dict], title: str = "Untitled") -> Dict:
    transcript = _truncate_transcript(_format_transcript(segments))
    system = "You are a video chapter creator. Analyze transcripts and create timestamped chapter breakdowns. Return valid JSON only."
    user = f'Video title: {title}\n\nTranscript:\n{transcript}\n\nCreate a JSON array of chapters. Each chapter should have: {{"timestamp": "MM:SS", "title": "Chapter Title", "summary": "Brief 1-2 sentence summary"}}. Identify 5-15 natural topic changes.'
    return _parse_json_response(_call_ai_sync(system, user))


def generate_key_points(segments: List[Dict], title: str = "Untitled") -> Dict:
    transcript = _truncate_transcript(_format_transcript(segments))
    system = "You are an analyst who extracts key takeaways from content. Return valid JSON only."
    user = f"Video title: {title}\n\nTranscript:\n{transcript}\n\nExtract 8-15 key points as a JSON array of strings. Each point should be a complete, actionable insight."
    return _parse_json_response(_call_ai_sync(system, user))


def generate_flashcards(segments: List[Dict], title: str = "Untitled") -> Dict:
    transcript = _truncate_transcript(_format_transcript(segments))
    system = "You are an expert educator creating study flashcards. Return valid JSON only."
    user = f'Video title: {title}\n\nTranscript:\n{transcript}\n\nCreate 10-20 flashcards as a JSON array. Each flashcard: {{"question": "...", "answer": "..."}}. Cover key concepts, definitions, and important facts.'
    return _parse_json_response(_call_ai_sync(system, user))


def generate_quiz(segments: List[Dict], title: str = "Untitled") -> Dict:
    transcript = _truncate_transcript(_format_transcript(segments))
    system = "You are a quiz creator. Generate multiple-choice questions. Return valid JSON only."
    user = f'Video title: {title}\n\nTranscript:\n{transcript}\n\nCreate 10 multiple-choice quiz questions as a JSON array. Each question: {{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correctAnswer": "A", "explanation": "Brief explanation"}}.'
    return _parse_json_response(_call_ai_sync(system, user))


def generate_action_items(segments: List[Dict], title: str = "Untitled") -> Dict:
    transcript = _truncate_transcript(_format_transcript(segments))
    system = "You are a productivity assistant. Extract actionable items from content. Return valid JSON only."
    user = f'Video title: {title}\n\nTranscript:\n{transcript}\n\nExtract actionable items from this video as a JSON array. Each item: {{"action": "...", "priority": "high|medium|low", "category": "..."}}.'
    return _parse_json_response(_call_ai_sync(system, user))


def generate_all_notes(segments: List[Dict], title: str = "Untitled") -> Optional[Dict]:
    """Generate all note types at once (used by video processor worker)."""
    provider = _get_available_provider()
    if not provider:
        print("[AI] No AI provider configured — skipping notes generation.")
        return None

    print(f"[AI] Generating notes using {provider['provider']}/{provider['model']}...")

    results = {}
    generators = {
        "detailed_notes": generate_detailed_notes,
        "summary": generate_summary,
        "chapters": generate_chapters,
        "key_points": generate_key_points,
        "flashcards": generate_flashcards,
        "quiz": generate_quiz,
        "action_items": generate_action_items,
    }

    for note_type, generator in generators.items():
        try:
            result = generator(segments, title)
            content = result.get("parsed", result.get("text", ""))
            results[note_type] = {
                "content": content,
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
            }
        except Exception as e:
            print(f"[AI] Failed to generate {note_type}: {e}")
            results[note_type] = {"content": "", "provider": "error", "model": ""}

    return results
