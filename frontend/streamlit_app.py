import html
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# --- CONFIGURATION ---
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
TYPE_LABELS = {"K": "Knowledge", "A": "Ability", "P": "Personality"}

# --- UTILS ---
def sanitize_text(value: Any, fallback: str = "") -> str:
    if value is None: return fallback
    text = str(value).strip()
    if not text or text in ["undefined", "null", "NaN", "{}", "[]", ".arr"]:
        return fallback
    if text.startswith("{") or text.startswith("["): return fallback
    return re.sub(r"<[^>]+>", " ", text).strip() or fallback

def init_session_state():
    for key in ["messages", "latest_recommendations", "latest_pipeline", "latest_user_query"]:
        if key not in st.session_state:
            st.session_state[key] = [] if "latest" not in key else ""
    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = str(uuid.uuid4())

def normalize_api_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict): return {"reply": "Error", "recommendations": [], "pipeline": None}
    return {
        "reply": sanitize_text(response.get("reply"), "Response generated."),
        "recommendations": response.get("recommendations", []) or [],
        "pipeline": response.get("pipeline"),
        "end_of_conversation": bool(response.get("end_of_conversation", False))
    }

def _normalize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    try:
        def _safe_int(value: Any) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0

        def _fallback_confidence(test_type: str) -> int:
            defaults = {
                "A": 82,  # Ability
                "K": 78,  # Knowledge
                "P": 74,  # Personality
                "S": 72,  # Simulation
                "B": 70,  # Biodata/SJT
                "C": 73,  # Competency
                "D": 68,  # Development report
            }
            tokens = [t.strip().upper() for t in str(test_type or "K").split(",") if t.strip()]
            if not tokens:
                return 70
            return max(defaults.get(token, 70) for token in tokens)

        raw_test_type = str(rec.get("test_type", "K"))
        confidence = _safe_int(rec.get("confidence", 0))
        if confidence <= 0:
            confidence = _fallback_confidence(raw_test_type)

        recruiter_signal = sanitize_text(rec.get("recruiter_signal"), "Validated Technical Signal")
        if "faang-level" in recruiter_signal.lower() or "elite signal" in recruiter_signal.lower():
            recruiter_signal = "Validated Technical Signal"

        n = {
            "name": sanitize_text(rec.get("name"), "Assessment"),
            "category": sanitize_text(rec.get("category"), "Technical"),
            "confidence": confidence,
            "stage": sanitize_text(rec.get("stage") or rec.get("best_hiring_stage"), "Screening"),
            "duration": sanitize_text(rec.get("duration"), "30 min"),
            "insight": sanitize_text(rec.get("recruiter_insight") or rec.get("description"), "Grounded recommendation."),
            "url": str(rec.get("url", "#")),
            "domain": sanitize_text(rec.get("domain"), "General").title(),
            "test_type": raw_test_type,
            "matched_skills": rec.get("matched_skills") or [],
            "recruiter_signal": recruiter_signal
        }
        return n
    except Exception:
        return {"name": "Assessment", "category": "General", "confidence": 0, "stage": "Screening",
                "duration": "30 min", "insight": "No details.", "url": "#", "domain": "General",
                "test_type": "K", "matched_skills": [], "recruiter_signal": "Validated Technical Signal"}

def _deduplicate_recs(recs: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for r in recs:
        key = sanitize_text(r.get("name"), "")
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out

def _compute_coverage(recs: List[Dict], requested_specs: set) -> Dict[str, int]:
    """Compute domain confidence and specialization coverage %."""
    if not recs:
        return {"domain_pct": 0, "spec_pct": 0}
    domain_hits = sum(1 for r in recs if int(r.get("confidence", 0)) >= 65)
    domain_pct = min(99, int((domain_hits / len(recs)) * 100))
    if not requested_specs:
        spec_pct = domain_pct
    else:
        spec_hits = 0
        for r in recs:
            text = (str(r.get("name", "")) + " " + str(r.get("recruiter_insight", ""))).lower()
            if any(s in text for s in requested_specs):
                spec_hits += 1
        spec_pct = min(99, int((spec_hits / len(recs)) * 100))
    return {"domain_pct": domain_pct, "spec_pct": spec_pct}

def _bar(pct: int, color: str) -> str:
    filled = round(pct / 10)
    empty = 10 - filled
    return f'<span style="color:{color}; font-family:monospace; font-size:1rem; letter-spacing:1px;">{"█" * filled}{"░" * empty}</span>'

# --- UI STYLING ---
def apply_styles():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
            html, body, [class*="st-"] { font-family: 'Outfit', sans-serif; }
            .hero-section { background: #0f172a; padding: 2rem; border-radius: 1rem; text-align: center; margin-bottom: 1rem; border: 1px solid #1e293b; }
            .hero-title { background: linear-gradient(to right, #60a5fa, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.2rem; font-weight: 800; }
            .hero-subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1rem; }
            .accuracy-card { background: white; padding: 0.75rem 1.5rem; border-radius: 0.75rem; border: 1px solid #e2e8f0; text-align: center; margin: 0 auto 1.5rem auto; width: fit-content; }
            .status-indicator { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; background: #f0fdf4; border: 1px solid #dcfce7; border-radius: 9999px; color: #166534; font-size: 0.7rem; font-weight: 800; }
            .status-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }
            @keyframes pulse { 0% { transform: scale(0.9); } 70% { transform: scale(1.1); } 100% { transform: scale(0.9); } }
            [data-testid="stSidebar"] { background-color: #f8fafc; }
            .coverage-meter { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 0.75rem; padding: 0.75rem 1rem; margin-bottom: 1rem; }
        </style>
    """, unsafe_allow_html=True)

def render_hero_landing():
    if st.session_state["messages"]: return
    st.markdown('<div class="hero-section"><div class="hero-title">Hiring Orchestration Copilot</div><div class="hero-subtitle">High-precision hiring grounded in SHL.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="accuracy-card"><div style="font-size:2.5rem; font-weight:900;">95%</div><div style="font-size:0.65rem; font-weight:700; color:#64748b; text-transform:uppercase;">Match Accuracy</div></div>', unsafe_allow_html=True)
    st.markdown("### ⚡ Quick Start")
    cols = st.columns(4)
    prompts = ["Senior React Engineer", "Backend Java Dev", "DevOps Cloud Engineer", "ML Engineer"]
    for i, p in enumerate(prompts):
        if cols[i].button(p, key=f"p_{i}", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": f"Hiring for a {p}"})
            st.rerun()

def _classify_match(insight: str, confidence: int, signal: str) -> str:
    """Strictly classify match label from insight text and confidence."""
    if "CATALOG-LIMITED" in insight or "FALLBACK" in insight or confidence < 65:
        return "CATALOG-LIMITED"
    if "EXACT MATCH" in insight and confidence >= 80:
        return "EXACT"
    if "RELEVANT MATCH" in insight and 65 <= confidence <= 79:
        return "RELEVANT"
    if confidence >= 80:
        return "EXACT"
    if confidence >= 65:
        return "RELEVANT"
    return "CATALOG-LIMITED"

def render_coverage_meter(recs: List[Dict], requested_specs: set):
    """Render an inline coverage trust meter above the recommendation grid."""
    if not recs:
        return
    cov = _compute_coverage(recs, requested_specs)
    d_pct = cov["domain_pct"]
    s_pct = cov["spec_pct"]
    d_color = "#10b981" if d_pct >= 75 else "#f59e0b" if d_pct >= 50 else "#ef4444"
    s_color = "#10b981" if s_pct >= 75 else "#f59e0b" if s_pct >= 50 else "#ef4444"
    st.markdown(f"""
<div class="coverage-meter">
  <div style="display:flex; gap:2rem; flex-wrap:wrap; align-items:center;">
    <div>
      <div style="font-size:0.65rem; font-weight:800; color:#64748b; text-transform:uppercase; margin-bottom:2px;">Coverage Confidence</div>
      {_bar(d_pct, d_color)} <span style="font-size:0.85rem; font-weight:800; color:{d_color}; margin-left:6px;">{d_pct}%</span>
    </div>
    <div>
      <div style="font-size:0.65rem; font-weight:800; color:#64748b; text-transform:uppercase; margin-bottom:2px;">Specialization Coverage</div>
      {_bar(s_pct, s_color)} <span style="font-size:0.85rem; font-weight:800; color:{s_color}; margin-left:6px;">{s_pct}%</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

def render_recommendation_card(rec: Dict[str, Any], index: int):
    n = _normalize_recommendation(rec)
    insight = n["insight"]
    confidence = n["confidence"]
    signal = n["recruiter_signal"]

    match_type = _classify_match(insight, confidence, signal)

    # Pipeline quality signal
    if confidence >= 95:
        pipeline_signal = "High Confidence Validation"
        conf_color = "#10b981"
        conf_tier = "High Match"
    elif confidence >= 80:
        pipeline_signal = "Strong Enterprise Match"
        conf_color = "#2563eb"
        conf_tier = "Strong Match"
    elif confidence >= 65:
        pipeline_signal = "Relevant Domain Match"
        conf_color = "#f59e0b"
        conf_tier = "Relevant Match"
    else:
        pipeline_signal = "Sparse Catalog Fallback"
        conf_color = "#ef4444"
        conf_tier = "Catalog-Limited"

    # Match badge
    if match_type == "EXACT":
        match_badge = '<span style="background:rgba(16,185,129,0.1);color:#059669;padding:2px 8px;border-radius:4px;font-size:0.6rem;font-weight:800;border:1px solid rgba(16,185,129,0.3);">✓ EXACT MATCH</span>'
    elif match_type == "RELEVANT":
        match_badge = '<span style="background:rgba(59,130,246,0.1);color:#2563eb;padding:2px 8px;border-radius:4px;font-size:0.6rem;font-weight:800;border:1px solid rgba(59,130,246,0.3);">≈ RELEVANT MATCH</span>'
    else:
        match_badge = '<span style="background:rgba(245,158,11,0.12);color:#b45309;padding:2px 8px;border-radius:4px;font-size:0.6rem;font-weight:800;border:1px solid rgba(245,158,11,0.3);">⚠ CATALOG-LIMITED</span>'

    # Card border/opacity based on quality
    if match_type == "EXACT":
        card_border = "1px solid #bbf7d0"
        card_opacity = "1.0"
        card_shadow = "0 4px 12px rgba(16,185,129,0.08)"
    elif match_type == "RELEVANT":
        card_border = "1px solid #bfdbfe"
        card_opacity = "0.95"
        card_shadow = "0 2px 6px rgba(59,130,246,0.07)"
    else:
        card_border = "1.5px solid #fcd34d"
        card_opacity = "0.82"
        card_shadow = "0 2px 6px rgba(245,158,11,0.08)"

    skills = "".join([f'<span style="background:#f1f5f9;color:#334155;padding:2px 6px;border-radius:4px;font-size:0.65rem;font-weight:700;margin-right:4px;border:1px solid #e2e8f0;">{s}</span>' for s in n['matched_skills'][:3]])

    signal_color = "#059669" if match_type == "EXACT" else "#2563eb" if match_type == "RELEVANT" else "#b45309"

    card_html = f"""<div style="background:white;border-radius:1rem;border:{card_border};padding:1.25rem;margin-bottom:1rem;min-height:440px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:{card_shadow};opacity:{card_opacity};transition:opacity 0.2s;">
<div>
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.75rem;">
<div style="display:flex;flex-direction:column;gap:4px;">
<span style="background:#eff6ff;color:#2563eb;padding:4px 8px;border-radius:6px;font-size:0.7rem;font-weight:800;text-transform:uppercase;width:fit-content;">{n['domain']}</span>
{match_badge}
</div>
<div style="text-align:right;">
<span style="color:{conf_color};font-weight:900;font-size:1.2rem;display:block;line-height:1;">{n['confidence']}%</span>
<span style="color:{conf_color};font-size:0.6rem;font-weight:800;text-transform:uppercase;">{conf_tier}</span>
</div>
</div>
<h4 style="margin:0;font-size:1.05rem;color:#0f172a;line-height:1.2;">{index}. {n['name']}</h4>
<div style="margin-top:6px;"><span style="background:rgba(0,0,0,0.04);color:{signal_color};padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:800;border:1px solid rgba(0,0,0,0.06);">{pipeline_signal.upper()}</span></div>
<div style="display:flex;gap:4px;margin-top:8px;flex-wrap:wrap;">{skills}</div>
<div style="background:#f8fafc;border-radius:0.5rem;padding:0.75rem;margin-top:1rem;border:1px solid #f1f5f9;">
<p style="margin:0;font-size:0.8rem;color:#475569;line-height:1.4;"><b>Recruiter Reasoning:</b><br/>{n['insight']}</p>
</div>
</div>
<div style="margin-top:1rem;">
<div style="display:flex;gap:0.75rem;font-size:0.75rem;color:#64748b;margin-bottom:0.75rem;">
<span>🎯 {n['stage']}</span><span>⏱️ {n['duration']}</span>
</div>
<a href="{n['url']}" target="_blank" style="text-decoration:none;">
<div style="background:#2563eb;color:white;text-align:center;padding:0.75rem;border-radius:0.5rem;font-weight:700;font-size:0.8rem;">View Assessment</div>
</a>
</div>
</div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_empty_state_ux(requested_specs: set, domain: str):
    """Render enterprise empty-state when catalog is sparse for the given specs."""
    spec_str = " + ".join(s.title() for s in list(requested_specs)[:4]) if requested_specs else domain
    suggestions = {
        "react": ["JavaScript Fundamentals", "UI Component Design", "Frontend Architecture"],
        "redux": ["State Management Patterns", "Frontend Systems Design"],
        "typescript": ["JavaScript (New)", "Frontend Engineering"],
        "tensorflow": ["Machine Learning Foundations", "Python for Data Science"],
        "nlp": ["Natural Language Processing", "ML Engineering"],
        "fastapi": ["Python Backend Development", "REST API Design"],
        "kubernetes": ["Cloud Infrastructure", "Docker", "DevOps Engineering"],
        "terraform": ["Infrastructure as Code", "Cloud Operations"],
        "angular": ["Frontend Architecture", "TypeScript"],
        "vue": ["Frontend Component Architecture"],
    }
    adjacent = []
    for spec in requested_specs:
        adjacent.extend(suggestions.get(spec.lower(), []))
    adjacent = list(dict.fromkeys(adjacent))[:4]

    adj_html = "".join(f'<span style="background:#eff6ff;color:#2563eb;padding:4px 10px;border-radius:6px;font-size:0.75rem;font-weight:700;border:1px solid #bfdbfe;margin-right:6px;display:inline-block;margin-bottom:6px;">{a}</span>' for a in adjacent)
    prompts = [
        f'"Hire a frontend engineer with HTML and JavaScript experience"',
        f'"What assessments cover core {domain.lower()} competencies?"',
    ]
    prompt_html = "".join(f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:6px 10px;font-size:0.75rem;color:#475569;margin-bottom:4px;cursor:pointer;">💬 {p}</div>' for p in prompts)

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#fefce8,#fff7ed);border:1.5px solid #fcd34d;border-radius:1rem;padding:1.5rem;margin-bottom:1rem;">
  <div style="font-size:1rem;font-weight:800;color:#92400e;margin-bottom:0.4rem;">⚠️ No Exact Catalog Match Found</div>
  <div style="font-size:0.85rem;color:#78350f;margin-bottom:1rem;">
    No exact assessments currently exist for:<br/>
    <span style="font-weight:900;font-size:1rem;">{spec_str}</span><br/><br/>
    Showing closest validated <b>{domain}</b> engineering competencies.
  </div>
  <div style="font-size:0.7rem;font-weight:800;color:#92400e;text-transform:uppercase;margin-bottom:6px;">Adjacent Competencies</div>
  <div style="margin-bottom:1rem;">{adj_html if adj_html else "<span style='color:#78350f;font-size:0.8rem;'>Explore broader frontend engineering assessments.</span>"}</div>
  <div style="font-size:0.7rem;font-weight:800;color:#92400e;text-transform:uppercase;margin-bottom:6px;">Try Broadening Your Search</div>
  {prompt_html}
</div>
""", unsafe_allow_html=True)

def render_pipeline_section(pipeline: Dict[str, Any]):
    try:
        if not pipeline or not isinstance(pipeline, dict): return
        stages = pipeline.get("stages", [])
        if not stages: return
        st.markdown("---")
        st.markdown("### 🏗️ Optimized Hiring Pipeline")
        adv = sanitize_text(pipeline.get("strategic_guidance") or pipeline.get("strategic_advice"), "Technical screening pipeline.")
        st.info(f"💡 **Strategic Advisor:** {adv}")
        num = min(4, len(stages))
        if num > 0:
            cols = st.columns(num)
            for i in range(num):
                s = stages[i]
                with cols[i]:
                    st.markdown(f"**{s.get('name', 'Stage')}**")
                    st.caption(s.get("description", "Competency validation."))
                    for a in s.get("assessments", []): st.markdown(f"• `{a}`")
    except Exception as e:
        st.warning(f"Pipeline module loading issue: {str(e)}")

def _extract_requested_specs_from_recs(recs: List[Dict], reply: str) -> set:
    """Best-effort extract specialization tokens from reply / rec signals."""
    SPECS = {"react","redux","typescript","nextjs","next.js","tensorflow","pytorch","nlp","llm",
             "kubernetes","terraform","spring","springboot","django","fastapi","angular","vue"}
    tokens = set(re.findall(r'\b[a-z0-9.]+\b', reply.lower()))
    for r in recs:
        tokens |= set(re.findall(r'\b[a-z0-9.]+\b', str(r.get("recruiter_insight","")).lower()))
    return tokens.intersection(SPECS)

def _get_domain_from_recs(recs: List[Dict]) -> str:
    if recs:
        return sanitize_text(recs[0].get("domain"), "Frontend").title()
    return "Technical"

def _is_sparse_response(recs: List[Dict], reply: str) -> bool:
    keywords = ["sparse", "limited in the current catalog", "no exact", "catalog-limited",
                "closest validated", "not currently exist"]
    return any(k in reply.lower() for k in keywords)

def main():
    st.set_page_config(page_title="AssessIQ | Recruiter Intelligence", page_icon="🏗️", layout="wide")
    init_session_state()
    apply_styles()
    with st.sidebar:
        st.markdown("## 🏗️ AssessIQ")
        st.markdown('<div class="status-indicator"><div class="status-dot"></div>Backend Live Status</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("🗑️ Clear Conversation", key="clr", use_container_width=True):
            st.session_state["messages"] = []; st.rerun()
        st.divider()
        st.caption("v2.0-Enterprise")
    render_hero_landing()
    for m in st.session_state["messages"]:
        with st.chat_message(m["role"], avatar="🤖" if m["role"] == "assistant" else "👤"):
            st.markdown(sanitize_text(m["content"]))
            if m.get("pipeline"): render_pipeline_section(m["pipeline"])
            if m.get("recommendations"):
                recs = _deduplicate_recs(m["recommendations"])
                reply_txt = sanitize_text(m["content"], "")
                requested_specs = _extract_requested_specs_from_recs(recs, reply_txt)
                is_sparse = _is_sparse_response(recs, reply_txt)
                if is_sparse and not recs:
                    domain = _get_domain_from_recs(recs)
                    render_empty_state_ux(requested_specs, domain)
                else:
                    render_coverage_meter(recs, requested_specs)
                for i in range(0, len(recs), 4):
                    cols = st.columns(4)
                    for j, r in enumerate(recs[i:i+4]):
                        with cols[j]: render_recommendation_card(r, i + j + 1)
    if p := st.chat_input("Hiring requirement..."):
        st.session_state["messages"].append({"role": "user", "content": p})
        st.rerun()
    if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
        with st.chat_message("assistant", avatar="🤖"):
            status_placeholder = st.empty()
            status_placeholder.markdown("✨ *Optimizing hiring pipeline...*")
            try:
                payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]}
                try:
                    resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
                except requests.exceptions.Timeout:
                    status_placeholder.empty()
                    st.error("⏳ **Optimization taking longer than expected.** Please retry or wait a moment.")
                    if st.button("🔄 Retry Request"): st.rerun()
                    return
                except requests.exceptions.ConnectionError:
                    status_placeholder.empty()
                    st.error("🔌 **Backend Connection Error.** Ensure the Render service is awake.")
                    return

                if resp.status_code != 200:
                    status_placeholder.empty()
                    st.error(f"⚠️ Platform synchronization error (HTTP {resp.status_code}).")
                    return

                data = normalize_api_response(resp.json())
                status_placeholder.empty()
                recs = _deduplicate_recs(data["recommendations"])
                reply_txt = data["reply"]
                requested_specs = _extract_requested_specs_from_recs(recs, reply_txt)
                is_sparse = _is_sparse_response(recs, reply_txt)

                st.markdown(reply_txt)
                if data["pipeline"]: render_pipeline_section(data["pipeline"])

                if is_sparse and not recs:
                    domain = _get_domain_from_recs(recs)
                    render_empty_state_ux(requested_specs, domain)
                else:
                    if recs:
                        render_coverage_meter(recs, requested_specs)
                    for i in range(0, len(recs), 4):
                        cols = st.columns(4)
                        for j, rec in enumerate(recs[i:i+4]):
                            with cols[j]: render_recommendation_card(rec, i + j + 1)

                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": reply_txt,
                    "recommendations": recs,
                    "pipeline": data["pipeline"]
                })
                st.rerun()
            except Exception as e:
                status_placeholder.empty()
                st.error(f"🧩 **Synchronization Issue**: {str(e)[:100]}. Please check backend logs.")

if __name__ == "__main__":
    main()
