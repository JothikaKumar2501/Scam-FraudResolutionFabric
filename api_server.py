import asyncio
import json
import threading
import uuid
from typing import Dict, Any
import os

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from langgraph_multi_agent import stream_langgraph_steps
from context_store import context_store
from mem0_integration import search_graph as mem0_graph_search, add_graph as mem0_graph_add, clear_case as mem0_graph_clear
from vector_utils import get_relevant_context
from vector_utils import ingest_documents

app = FastAPI(title="GenAI FraudOps API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def api_health():
    return {"ok": True}

@app.on_event("startup")
def _warmup_vector_store():
    # Prefer XAI dialogue by default unless explicitly disabled
    os.environ.setdefault("USE_INTELLIGENT_DIALOGUE", "1")
    # Enable fast mode defaults for lower token sizes and quicker responses
    os.environ.setdefault("FAST_MODE", "1")
    # Best-effort ingestion for local Qdrant stub to accelerate RAG
    try:
        ingest_documents(["datasets/SOP.md", "datasets/questions.md"])
    except Exception:
        pass
    # Ensure minimal mem0 graph health check doesn't block startup
    try:
        from mem0_integration import get_mem0_manager
        mgr = get_mem0_manager()
        if mgr and getattr(mgr, 'graph_memory', None) is None:
            print("[mem0] Graph store not configured; falling back to text memories only")
    except Exception:
        pass

class Session:
    def __init__(self, state: Dict[str, Any]):
        self.state = state
        self.generator = stream_langgraph_steps(state)
        self.lock = threading.Lock()
        self.closed = False


_sessions: Dict[str, Session] = {}
_sessions_lock = threading.Lock()


def _load_alerts() -> Dict[str, Any]:
    import json
    from pathlib import Path
    path = Path("datasets/FTP.json")
    if not path.exists():
        return {"alerts": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Normalize structure
    if isinstance(data, dict) and "alerts" in data:
        return data
    return {"alerts": data}


@app.get("/api/alerts")
def api_alerts():
    return _load_alerts()


class StartPayload(BaseModel):
    alert_id: str | None = None
    alert: Dict[str, Any] | None = None


@app.post("/api/start")
async def api_start(payload: StartPayload | None = None):
    body = payload.model_dump() if payload else {}
    alerts = _load_alerts().get("alerts", [])
    alert = body.get("alert")
    alert_id = body.get("alert_id")
    if not alert and alert_id:
        alert = next((a for a in alerts if a.get("alert_id") == alert_id or a.get("alertId") == alert_id), None)
    if not alert:
        # fallback to first
        alert = alerts[0] if alerts else {}
    # Compute a stable case_id for memory lookups
    raw = (
        (alert.get("alert_id") or alert.get("alertId") or str(uuid.uuid4())[:8]) if isinstance(alert, dict) else str(uuid.uuid4())[:8]
    )
    case_id = raw if isinstance(raw, str) and raw.startswith("ALRT-") else f"ALRT-{raw}"
    # Shared state dict used by the graph generator (IMPORTANT: same reference)
    state = {
        "transaction": alert,
        "logs": [],
        "agent_responses": [],
        "dialogue_history": [],
        "case_id": case_id,
    }
    sid = str(uuid.uuid4())
    with _sessions_lock:
        _sessions[sid] = Session(state)
    # Seed Mem0 memories best-effort with initial case data
    try:
        from context_store import context_store as _ctx
        _ctx.store_mem0_context(case_id, {"transaction": alert or {}, "note": "Case created"}, agent_name="System")
    except Exception:
        pass
    return {"session_id": sid}


@app.get("/api/status/{sid}")
def api_status(sid: str):
    sess = _sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return sess.state


@app.get("/api/mem0/summary/{case_id}")
def api_mem0_summary(case_id: str):
    try:
        summary = context_store.get_mem0_case_summary(case_id)
        return {"case_id": case_id, "summary": summary}
    except Exception as e:
        return JSONResponse({"case_id": case_id, "error": str(e)}, status_code=500)


@app.get("/api/mem0/memories/{case_id}")
def api_mem0_memories(case_id: str, limit: int = 10):
    try:
        items = context_store.retrieve_mem0_memories(case_id, limit=limit) or []
        return {"case_id": case_id, "items": items}
    except Exception as e:
        return JSONResponse({"case_id": case_id, "error": str(e)}, status_code=500)


@app.get("/api/rag")
def api_rag(query: str, top_k: int = 5):
    try:
        ctx = get_relevant_context(query, top_k=top_k)
        return {"query": query, "results": ctx}
    except Exception as e:
        return JSONResponse({"query": query, "error": str(e)}, status_code=500)

@app.get("/api/mem0/graph/search")
def api_mem0_graph_search(query: str, case_id: str | None = None, limit: int = 5):
    try:
        results = mem0_graph_search(case_id, query, limit)
        return {"case_id": case_id, "results": results}
    except Exception as e:
        return JSONResponse({"case_id": case_id, "error": str(e)}, status_code=500)

@app.post("/api/mem0/graph/add/{case_id}")
async def api_mem0_graph_add(case_id: str, req: Request):
    try:
        payload = await req.json()
        content = (payload or {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            return JSONResponse({"ok": False, "reason": "empty"}, status_code=400)
        ok = mem0_graph_add(case_id, content)
        return {"ok": ok}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/mem0/graph/clear/{case_id}")
def api_mem0_graph_clear(case_id: str):
    try:
        ok = mem0_graph_clear(case_id)
        return {"ok": ok}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/user_reply/{sid}")
async def api_user_reply(sid: str, req: Request):
    sess = _sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    # Tolerate missing/invalid JSON
    try:
        payload = await req.json()
    except Exception:
        payload = {}
    text = (payload or {}).get("text", "")
    if not isinstance(text, str) or not text.strip():
        return JSONResponse({"ok": False, "reason": "empty"})
    # Mutate the shared state so the running generator sees the update
    with sess.lock:
        # Append user response
        dh = sess.state.setdefault("dialogue_history", [])
        dh.append({"role": "user", "user": text})
        # Once we have a user turn, allow the generator loop to proceed on the next pull
        # Clear awaiting flags so graph can continue
        sess.state.pop('awaiting_user', None)
        sess.state['chat_done'] = False
        # Store user interaction into Mem0 best-effort
        try:
            from context_store import context_store as _ctx
            if sess.state.get('case_id'):
                _ctx.store_mem0_customer_interaction(sess.state['case_id'], text)
        except Exception:
            pass
    return {"ok": True}


@app.get("/api/stream/{sid}")
def api_stream(sid: str):
    sess = _sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    async def event_source():
        # Drive the underlying generator and yield JSON SSE frames
        while True:
            if sess.closed:
                break
            try:
                with sess.lock:
                    nxt = next(sess.generator)
                    sess.state.update(nxt or {})
                    # Best-effort Mem0 persistence for key milestones
                    try:
                        from context_store import context_store as _ctx
                        cid = sess.state.get('case_id')
                        if cid:
                            # Risk assessments
                            ra = sess.state.get('risk_assessment') or sess.state.get('risk_assessment_summary')
                            if ra and not sess.state.get('_mem0_risk_saved'):
                                _ctx.store_mem0_risk_assessment(cid, str(ra), confidence=0.9)
                                sess.state['_mem0_risk_saved'] = True
                            # Policy decision
                            pd = sess.state.get('policy_decision') or sess.state.get('final_policy_decision')
                            if pd and not sess.state.get('_mem0_policy_saved'):
                                _ctx.store_mem0_policy_decision(cid, str(pd))
                                sess.state['_mem0_policy_saved'] = True
                    except Exception:
                        pass
                data = json.dumps(sess.state)
                yield f"data: {data}\n\n"
            except StopIteration:
                sess.closed = True
                break
            except Exception:
                # transient errors, yield heartbeat
                yield "data: {}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.post("/api/finalize/{sid}")
def api_finalize(sid: str):
    """Signal the running session to finalize policy now.
    Clears awaiting flags so the stream can proceed to final steps immediately.
    """
    sess = _sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    with sess.lock:
        sess.state['finalization_requested'] = True
        sess.state['chat_done'] = True
        sess.state.pop('awaiting_user', None)
    return {"ok": True}


@app.post("/api/end/{sid}")
def api_end(sid: str):
    sess = _sessions.get(sid)
    if not sess:
        return {"ok": True}
    sess.closed = True
    with _sessions_lock:
        _sessions.pop(sid, None)
    return {"ok": True}


# Convenience local dev entrypoint: uvicorn api_server:app --reload

