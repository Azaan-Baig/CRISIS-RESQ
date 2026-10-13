from __future__ import annotations
import os
from groq import Groq
from src.mesh import priority_score

DEFAULT_MODEL = os.getenv("GROQ_MODEL", 
            "openai/gpt-oss-20b")

def groq_is_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())

def _fallback_brief(packets: list[dict]) -> str:
    ordered = sorted(packets, key=lambda p: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}.get(p.get("priority"),4))
    lines = ["## Priority-ordered SOS overview", "", "**Prototype note:** This is a rule-based summary because Groq is not configured or unavailable. Validate all details with a human responder.", ""]
    for p in ordered:
        lines.append(f"- **{p.get('priority','UNRANKED')} · {p.get('emergency_type','Unknown')}** — {p.get('message_id','N/A')}; {p.get('people_count',1)} person/people; location: {p.get('location_text') or 'not provided'}; message: {p.get('message') or 'no message'}; status: {p.get('status','Queued')}.")
    lines += ["", "### Suggested operational checks", "- Confirm location and callback/identity details where possible.", "- Check critical/high alerts first, while applying trained responder protocols.", "- Do not infer medical diagnoses or treat missing information as confirmed facts."]
    return "\n".join(lines)

def generate_triage_brief(packets: list[dict], use_llm: bool=True) -> dict:
    fallback = _fallback_brief(packets)
    if not use_llm or not groq_is_configured(): return {"text":fallback,"method":"rule-based fallback"}
    safe_packets = [{k:p.get(k) for k in ("message_id","created_at","emergency_type","people_count","battery","latitude","longitude","location_text","message","priority","status")} for p in packets]
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=0.8,
            max_tokens=900,
            messages=[
                {"role":"system","content":"You assist a disaster-response dashboard by summarizing structured SOS reports. Do not invent facts, diagnoses, locations, or resources. Preserve message IDs and rule-based priorities. Order reports by urgency, state uncertainty and missing data, give concise verification steps, and clearly say a human responder must make decisions. Never claim that you dispatched help."},
                {"role":"user","content":"Prepare a concise incident triage brief from these SOS records. Treat them as unverified reports:\n" + str(safe_packets)}
            ],
        )
        content = response.choices[0].message.content or fallback
        return {"text":content,"method":f"Groq LLM ({DEFAULT_MODEL})"}
    except Exception as exc:
        return {"text":fallback + f"\n\n**LLM unavailable:** {type(exc).__name__}: {exc}","method":"rule-based fallback (Groq request failed)"}
