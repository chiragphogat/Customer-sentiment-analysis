import os
import json
import csv
from pathlib import Path
from flask import Flask, request, render_template_string, redirect, url_for, send_file
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GROQ_AVAILABLE = True
try:
    from groq import Groq
except Exception:
    GROQ_AVAILABLE = False

APP = Flask(__name__)
CSV_PATH = Path("call_analysis.csv")

HTML_FORM = """
<!doctype html>
<title>Call Analyzer (Groq)</title>
<h2>Call Analyzer</h2>
<form method=post action="/analyze">
  <textarea name="transcript" rows="10" cols="80" placeholder="Paste call transcript here..."></textarea><br>
  <button type="submit">Analyze</button>
</form>
<p>Or POST JSON { "transcript": "..." } to /api/analyze</p>
<p><a href="/download">Download CSV</a></p>
"""

def analyze_with_groq(transcript: str):
    """Call Groq Chat Completions — ask model to return JSON with summary+sentiment.
       Returns dict: {'summary':..., 'sentiment':...} or raises/returns dict with fallback keys."""
    api_key = os.getenv("GROQ_API_KEY", "")
    model_name = os.getenv("GROQ_MODEL", "llama-3.1-70b")

    if not GROQ_AVAILABLE or not api_key:
    
        return heuristic_analyze(transcript, used_api=False)

    client = Groq(api_key=api_key)

    system_prompt = (
        "You are a concise assistant. Read the conversation and return a JSON object "
        "with exactly two keys: 'summary' (2-3 short sentences, factual) and 'sentiment' "
        "one of: Positive, Neutral, Negative. Your response must be pure JSON and nothing else."
    )

    user_prompt = f"Conversation:\n{transcript}"

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=200
        )
    except Exception as e:
       
        return {"summary": f"(Groq API error) {str(e)}", "sentiment": "Neutral", "used_api": True, "error": str(e)}
    def extract_content(resp):
      
        try:
           
            if isinstance(resp, dict):
                if "choices" in resp and resp["choices"]:
                    c = resp["choices"][0]
                    if isinstance(c, dict):
    
                        if "message" in c and isinstance(c["message"], dict) and "content" in c["message"]:
                            return c["message"]["content"]
                        if "text" in c:
                            return c["text"]
                if "output" in resp:
                    
                    out = resp["output"]
                    if isinstance(out, list) and out:
                        first = out[0]
                        if isinstance(first, dict) and "content" in first:
                            cont = first["content"]
                            if isinstance(cont, list) and cont:
                                return cont[0].get("text") if isinstance(cont[0], dict) else str(cont[0])
                            return str(cont)
            if hasattr(resp, "choices"):
                choices = getattr(resp, "choices")
                if choices and len(choices) > 0:
                    c0 = choices[0]
                    if hasattr(c0, "message"):
                        msg = getattr(c0, "message")
                        if isinstance(msg, dict) and "content" in msg:
                            return msg["content"]
                        if hasattr(msg, "content"):
                            return getattr(msg, "content")
                    if hasattr(c0, "text"):
                        return getattr(c0, "text")
            return str(resp)
        except Exception:
            return str(resp)

    raw_text = extract_content(response)

    parsed = None
    try:
        parsed = json.loads(raw_text)
    except Exception:
        import re
        m = re.search(r"\{.*\}", raw_text, flags=re.S)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None

    if parsed and isinstance(parsed, dict) and "summary" in parsed and "sentiment" in parsed:
        parsed["used_api"] = True
        return parsed

    return {"summary": raw_text.strip(), "sentiment": "Neutral", "used_api": True}

def heuristic_analyze(transcript: str, used_api=False):
    neg_words = ["fail", "failed", "not working", "frustrat", "angry", "disappointed", "refund", "complain", "problem", "error"]
    pos_words = ["thank", "thanks", "great", "awesome", "good", "resolved", "happy", "satisfied"]
    text = transcript.lower()
    score = 0
    for w in neg_words:
        if w in text:
            score -= 1
    for w in pos_words:
        if w in text:
            score += 1
    if score < 0:
        sentiment = "Negative"
    elif score > 0:
        sentiment = "Positive"
    else:
        sentiment = "Neutral"
    import re
    sents = re.split(r'(?<=[.!?])\s+', transcript.strip())
    summary = " ".join(sents[:2]) if len(sents) >= 1 else transcript.strip()
    if len(summary) > 300:
        summary = summary[:300].rsplit(' ',1)[0] + "..."
    return {"summary": summary, "sentiment": sentiment, "used_api": used_api}

def save_to_csv(transcript, summary, sentiment):
    header = ["Transcript", "Summary", "Sentiment", "Timestamp"]
    file_exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow([transcript, summary, sentiment, datetime.utcnow().isoformat()])

@APP.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_FORM)

@APP.route("/analyze", methods=["POST"])
def analyze_form():
    transcript = request.form.get("transcript", "").strip()
    if not transcript:
        return redirect(url_for("index"))
    result = analyze_with_groq(transcript)
    summary = result.get("summary", "")
    sentiment = result.get("sentiment", "")
    save_to_csv(transcript, summary, sentiment)
    # Display result
    return render_template_string(
        "<h3>Analysis result</h3>"
        "<p><b>Transcript</b></p><pre>{{t}}</pre>"
        "<p><b>Summary</b><br>{{s}}</p>"
        "<p><b>Sentiment</b><br>{{sent}}</p>"
        "<p><a href='/'>Back</a> | <a href='/download'>Download CSV</a></p>",
        t=transcript, s=summary, sent=sentiment
    )

@APP.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(force=True, silent=True) or {}
    transcript = data.get("transcript", "") or data.get("text", "")
    if not transcript:
        return {"error": "no transcript provided"}, 400
    result = analyze_with_groq(transcript)
    summary = result.get("summary", "")
    sentiment = result.get("sentiment", "")
    save_to_csv(transcript, summary, sentiment)
    return {"transcript": transcript, "summary": summary, "sentiment": sentiment}

@APP.route("/download")
def download_csv():
    if not CSV_PATH.exists():
        return "CSV not found. Submit an analysis first.", 404
    return send_file(str(CSV_PATH), as_attachment=True, download_name="call_analysis.csv")

if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=5000, debug=True)
