"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Markdown } from "@/components/ui/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatBubble } from "@/components/chat/ChatBubble";
import { Modal } from "@/components/ui/modal";
import { Copy, MessageSquare, Activity, Shield, AlertTriangle, Search, Phone, Filter, ArrowUpDown, Download } from "lucide-react";
import { useUIStatus } from "@/lib/ui-status";
import { useHotkeys } from "@/lib/useHotkeys";
import { JsonBlock } from "@/components/ui/json-block";
import { TypingDots } from "@/components/ui/typing-dots";
import { useIncrementalStream } from "@/lib/useIncrementalStream";
// animations provided in subcomponents

type Alert = Record<string, unknown>;
type BackendState = {
  logs?: string[];
  agent_responses?: unknown[];
  dialogue_history?: { role?: string; question?: string; user?: string }[];
  dialogue_analysis?: string;
  risk_assessment?: string;
  risk_assessment_summary?: string;
  policy_decision?: string;
  final_policy_decision?: string;
  regulatory_compliance?: unknown;
  case_id?: string;
  streaming_agent?: string;
  current_step?: number;
  total_steps?: number;
  latest_risk_assessment?: string;
  xai_decision?: unknown;
  transaction_context?: unknown;
  anomaly_context?: unknown;
  audit_log?: unknown[];
};

const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8002";

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selected, setSelected] = useState<number>(0);
  const [state, setState] = useState<BackendState>({ logs: [], agent_responses: [], dialogue_history: [] });
  const streamRef = useRef<EventSource | null>(null);
  const [backendUrl, setBackendUrl] = useState<string>(DEFAULT_API_BASE);
  const { setUIStatus } = useUIStatus();
  const [localConnected, setLocalConnected] = useState<boolean>(false);
  const [localStatus, setLocalStatus] = useState<string>("Idle");
  const [mem0Summary, setMem0Summary] = useState<string>("");
  const [mem0Items, setMem0Items] = useState<unknown[]>([]);
  const [ragQuery, setRagQuery] = useState<string>("");
  const [ragResults, setRagResults] = useState<{ sop_rules?: string[]; questions?: string[] }>({});
  const [selectedLogIndex, setSelectedLogIndex] = useState<number | null>(null);
  const [openRows, setOpenRows] = useState<Record<number, boolean>>({});
  const chatRef = useRef<HTMLDivElement | null>(null);
  const [xaiOpen, setXaiOpen] = useState<boolean>(false);
  const [graphQuery, setGraphQuery] = useState<string>("");
  const [graphResults, setGraphResults] = useState<unknown[]>([]);
  const [alertSearch, setAlertSearch] = useState("");
  const [sortKey, setSortKey] = useState<"risk" | "amount" | "date">("risk");
  const [sortAsc, setSortAsc] = useState(false);
  const [alertsView, setAlertsView] = useState<"all" | "high" | "bec" | "investment" | "device">("all");
  const [alertDetailsOpen, setAlertDetailsOpen] = useState(false);
  const [alertDetails, setAlertDetails] = useState<any>(null);
  const VIEW_STORAGE_KEY = "ftp_alerts_view_settings";
  const copyXai = () => {
    try {
      const obj = state.xai_decision;
      navigator.clipboard.writeText(obj ? JSON.stringify(obj, null, 2) : "—");
    } catch {}
  };

  useEffect(() => {
    // Load saved backend URL
    try {
      const saved = localStorage.getItem("api_base");
      if (saved) setBackendUrl(saved);
    } catch {}
  }, []);

  useEffect(() => {
    fetch(`${backendUrl}/api/alerts`)
      .then(r => r.json())
      .then(d => {
        const arr = Array.isArray(d?.alerts) ? d.alerts : [];
        setAlerts(arr);
      })
      .catch(() => setAlerts([]));
  }, [backendUrl]);

  const connectStreamForSession = (sid: string) => {
    if (streamRef.current) {
      streamRef.current.close();
    }
    const es = new EventSource(`${backendUrl}/api/stream/${sid}`);
    es.onmessage = (evt: MessageEvent) => {
      try {
        const st = JSON.parse(evt.data || "{}") as BackendState;
        setState(st);
        setLocalConnected(true);
        setLocalStatus("Streaming");
        setUIStatus({
          connected: true,
          status: "Streaming",
          currentStep: st.current_step,
          totalSteps: st.total_steps || 9,
          streamingAgent: st.streaming_agent,
          sessionId: sid,
          caseId: st.case_id || null,
        });
        if (st.streaming_agent) {
          document.title = `Streaming · ${st.streaming_agent}`;
        }
      } catch {}
    };
    es.onerror = () => {
      es.close();
      setLocalConnected(false);
      setLocalStatus("Disconnected");
      setUIStatus({ connected: false, status: "Disconnected", streamingAgent: undefined });
    };
    streamRef.current = es;
  };

  const startForIndex = async (idx: number) => {
    if (!alerts.length || idx < 0 || idx >= alerts.length) return;
    setLoading(true);
    try {
      const alert: any = alerts[idx];
      const res = await fetch(`${backendUrl}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_id: alert?.alert_id || alert?.alertId, alert }),
      });
      const data = await res.json();
      const sid = data.session_id as string;
      setSessionId(sid);
      connectStreamForSession(sid);
      return sid;
    } finally {
      setLoading(false);
    }
  };

  const start = async () => {
    await startForIndex(selected);
  };

  const startAndFinalize = async (idx: number) => {
    const sid = await startForIndex(idx);
    const targetSid = sid || sessionId;
    if (!targetSid) return;
    try { await fetch(`${backendUrl}/api/finalize/${targetSid}`, { method: 'POST' }); } catch {}
  };

  const filteredAlerts = useMemo(() => {
    let list = alerts.slice();
    if (alertSearch.trim()) {
      const q = alertSearch.toLowerCase();
      list = list.filter((a: any) => String(a.alert_id || a.alertId || "").toLowerCase().includes(q) || String(a.description || "").toLowerCase().includes(q));
    }
    // View filters
    list = list.filter((a: any) => {
      const risk = a.risk_score || 0;
      const rule = String(a.rule_id || a.ruleId || '').toUpperCase();
      const reg = String(a.regulatory_alert_type || '').toLowerCase();
      if (alertsView === 'high') return risk >= 800;
      if (alertsView === 'bec') return reg.includes('business email compromise') || rule.includes('RUL-TX230') || rule.includes('RUL-BEC008');
      if (alertsView === 'investment') return reg.includes('investment') || rule.includes('RUL-TX488');
      if (alertsView === 'device') return rule.includes('RUL-TX817') || String(a.queue || '').toLowerCase().includes('device');
      return true;
    });
    const compare = (a: any, b: any) => {
      if (sortKey === "risk") return (a.risk_score || 0) - (b.risk_score || 0);
      if (sortKey === "amount") return (a.amount || 0) - (b.amount || 0);
      if (sortKey === "date") return new Date(a.alert_date || 0).getTime() - new Date(b.alert_date || 0).getTime();
      return 0;
    };
    list.sort(compare);
    if (!sortAsc) list.reverse();
    return list;
  }, [alerts, alertSearch, sortKey, sortAsc]);

  const kpis = useMemo(() => {
    const total = alerts.length;
    const high = alerts.filter((a: any) => (a.risk_score || 0) >= 800).length;
    const bec = alerts.filter((a: any) => String(a.regulatory_alert_type || '').toLowerCase().includes('business email compromise')).length;
    const open = alerts.filter((a: any) => String(a.status || '').toLowerCase() === 'open').length;
    return { total, high, bec, open };
  }, [alerts]);

  // Persist and restore alerts view settings
  useEffect(() => {
    try {
      const raw = localStorage.getItem(VIEW_STORAGE_KEY);
      if (raw) {
        const o = JSON.parse(raw);
        if (o && typeof o === 'object') {
          if (o.alertSearch != null) setAlertSearch(o.alertSearch);
          if (o.sortKey != null) setSortKey(o.sortKey);
          if (o.sortAsc != null) setSortAsc(o.sortAsc);
          if (o.alertsView != null) setAlertsView(o.alertsView);
        }
      }
    } catch {}
  }, []);
  useEffect(() => {
    try {
      const o = { alertSearch, sortKey, sortAsc, alertsView };
      localStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify(o));
    } catch {}
  }, [alertSearch, sortKey, sortAsc, alertsView]);

  const resetView = () => {
    setAlertSearch("");
    setSortKey("risk");
    setSortAsc(false);
    setAlertsView("all");
  };

  const exportCSV = () => {
    try {
      const rows = filteredAlerts.map((a: any) => ({
        alert_id: a.alert_id || a.alertId,
        customer_id: a.customer_id || a.customerId || '',
        rule_id: a.rule_id || a.ruleId || '',
        amount: a.amount || '',
        currency: a.currency || '',
        risk_score: a.risk_score || '',
        queue: a.queue || '',
        priority: a.priority || '',
        status: a.status || '',
        description: (a.description || '').replace(/\n/g, ' '),
      }));
      const headers = Object.keys(rows[0] || { alert_id: '', rule_id: '', amount: '', risk_score: '' });
      const csv = [headers.join(','), ...rows.map(r => headers.map(h => `"${String((r as any)[h] ?? '').replace(/"/g, '""')}"`).join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'ftp_alerts.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const sendReply = async (text: string) => {
    if (!sessionId || !text.trim()) return;
    await fetch(`${backendUrl}/api/user_reply/${sessionId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  };

  const stop = async () => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    setLocalConnected(false);
    setLocalStatus("Stopped");
    setUIStatus({ connected: false, status: "Stopped", streamingAgent: undefined });
    if (sessionId) {
      try { await fetch(`${backendUrl}/api/end/${sessionId}`, { method: "POST" }); } catch {}
    }
  };

  const reconnect = async () => {
    if (!sessionId) return;
    if (streamRef.current) streamRef.current.close();
    const es = new EventSource(`${backendUrl}/api/stream/${sessionId}`);
    es.onmessage = (evt: MessageEvent) => {
      try {
        const st = JSON.parse(evt.data || "{}") as BackendState;
        setState(st);
        setLocalConnected(true);
        setLocalStatus("Streaming");
        setUIStatus({
          connected: true,
          status: "Streaming",
          currentStep: st.current_step,
          totalSteps: st.total_steps || 9,
          streamingAgent: st.streaming_agent,
          caseId: st.case_id || null,
        });
        if (st.streaming_agent) {
          document.title = `Streaming · ${st.streaming_agent}`;
        }
      } catch {}
    };
    es.onerror = () => {
      es.close();
      setLocalConnected(false);
      setLocalStatus("Disconnected");
      setUIStatus({ connected: false, status: "Disconnected", streamingAgent: undefined });
    };
    streamRef.current = es;
  };

  const saveBackendUrl = () => {
    try { localStorage.setItem("api_base", backendUrl); } catch {}
  };

  const fetchMem0 = async () => {
    const cid = state.case_id;
    if (!cid) return;
    try {
      const [s, m] = await Promise.all([
        fetch(`${backendUrl}/api/mem0/summary/${cid}`).then(r => r.json()).catch(() => ({})),
        fetch(`${backendUrl}/api/mem0/memories/${cid}?limit=10`).then(r => r.json()).catch(() => ({})),
      ]);
      setMem0Summary((s && s.summary) || "");
      setMem0Items((m && m.items) || []);
    } catch {}
  };

  const fetchRag = async () => {
    if (!ragQuery.trim()) return;
    try {
      const res = await fetch(`${backendUrl}/api/rag?query=${encodeURIComponent(ragQuery)}&top_k=6`);
      const data = await res.json();
      setRagResults((data && data.results) || {});
    } catch {}
  };

  const latest = (state.agent_responses || []).slice(-1)[0] as string | undefined;
  const selectedAgentResponse = ((): string | undefined => {
    if (selectedLogIndex != null) {
      const list = state.agent_responses as unknown[];
      if (Array.isArray(list) && selectedLogIndex >= 0 && selectedLogIndex < list.length) {
        const val = list[selectedLogIndex];
        return typeof val === 'string' ? val : (val ? JSON.stringify(val) : undefined);
      }
    }
    return typeof latest === 'string' ? latest : (latest ? JSON.stringify(latest) : undefined);
  })();
  
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [state.dialogue_history, state.latest_risk_assessment]);
  const graphSearch = async () => {
    if (!graphQuery.trim()) return;
    try {
      const cid = state.case_id || "";
      const res = await fetch(`${backendUrl}/api/mem0/graph/search?query=${encodeURIComponent(graphQuery)}&case_id=${encodeURIComponent(cid)}`);
      const data = await res.json();
      setGraphResults((data && data.results) || []);
    } catch {}
  };
  const graphAdd = async (text: string) => {
    const cid = state.case_id;
    if (!cid || !text.trim()) return;
    try {
      await fetch(`${backendUrl}/api/mem0/graph/add/${cid}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: text }) });
      await graphSearch();
    } catch {}
  };
  const graphClear = async () => {
    const cid = state.case_id;
    if (!cid) return;
    try {
      await fetch(`${backendUrl}/api/mem0/graph/clear/${cid}`, { method: 'POST' });
      setGraphResults([]);
    } catch {}
  };
  const question = (() => {
    const dh = state.dialogue_history || [];
    const last = dh[dh.length - 1];
    if (last && last.role === "assistant" && last.question) return last.question as string;
    // Also show the non-streaming question text if available
    return state.dialogue_analysis as string | undefined;
  })();

  // Removed redundant caseId sync effect to avoid update loops. Case ID is set in SSE handlers.

  // Keyboard shortcuts
  useHotkeys({
    "ctrl+enter": (e) => { e.preventDefault(); const input = document.getElementById("chat-input") as HTMLInputElement | null; if (input) { const val = input.value; if (val?.trim()) { sendReply(val); input.value = ""; } } },
    "ctrl+r": (e) => { e.preventDefault(); reconnect(); },
    "escape": () => { stop(); },
    "alt+/": () => { const input = document.getElementById("chat-input"); if (input) (input as HTMLElement).focus(); },
    "alt+c": () => { copyXai(); },
  });

  // Animated streaming text: compute a key to trigger motion when new content appended
  const isViewingPast = selectedLogIndex != null && selectedLogIndex !== (state.agent_responses?.length || 1) - 1;
  const streamingKey = useMemo(() => `${state.streaming_agent || ""}-${(selectedAgentResponse || "").length}`, [state.streaming_agent, selectedAgentResponse]);
  const animatedLatestRaw = useIncrementalStream(selectedAgentResponse);
  const displayedLatest = isViewingPast ? selectedAgentResponse : animatedLatestRaw;

  // Quick actions: helper funcs
  const addGraphNote = async (text: string) => {
    const cid = state.case_id;
    if (!cid || !text.trim()) return;
    try {
      await fetch(`${backendUrl}/api/mem0/graph/add/${cid}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: text }) });
    } catch {}
  };
  const finalizeNow = async () => {
    if (!sessionId) return;
    try { await fetch(`${backendUrl}/api/finalize/${sessionId}`, { method: 'POST' }); } catch {}
  };

  return (
    <main className="max-w-6xl mx-auto py-6 sm:py-8 space-y-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gradient">GenAI FraudOps Suite</h1>
        <p className="text-muted-foreground">Live MAS streaming with LangGraph · Bedrock · Mem0 · Qdrant</p>
        <div className="text-xs text-muted-foreground">
          Status: <span className={(localConnected ? "text-green-600" : "text-red-600")}>{localConnected ? "Connected" : "Disconnected"}</span> · {localStatus} {sessionId ? `· SID: ${sessionId}` : ""}
          {state.current_step ? (
            <span> · Step {state.current_step}/{state.total_steps || 9}</span>
          ) : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Controls & FTP Alerts</CardTitle>
          <CardDescription>Search and sort alerts; connect to backend streaming</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="rounded border p-2 text-xs">
              <div className="text-muted-foreground">Total Alerts</div>
              <div className="text-lg font-semibold">{kpis.total}</div>
            </div>
            <div className="rounded border p-2 text-xs">
              <div className="text-muted-foreground">High Risk (≥800)</div>
              <div className="text-lg font-semibold">{kpis.high}</div>
            </div>
            <div className="rounded border p-2 text-xs">
              <div className="text-muted-foreground">BEC</div>
              <div className="text-lg font-semibold">{kpis.bec}</div>
            </div>
            <div className="rounded border p-2 text-xs">
              <div className="text-muted-foreground">Open</div>
              <div className="text-lg font-semibold">{kpis.open}</div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="grid gap-2">
              <Label>Alert</Label>
              <select aria-label="Select alert" className="border-input rounded-md border bg-transparent px-2 py-1 h-9" value={selected} onChange={(e) => setSelected(parseInt(e.target.value))}>
                {filteredAlerts.map((a: any, i: number) => (
                  <option key={i} value={alerts.indexOf(a)}>
                    {(a.alert_id || a.alertId || `Alert ${i + 1}`) as string}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label>Backend</Label>
              <Input value={backendUrl} onChange={(e) => setBackendUrl(e.target.value)} onBlur={saveBackendUrl} />
            </div>
            <div className="grid gap-2">
              <Label className="invisible">Start</Label>
              <Button onClick={start} disabled={loading || !alerts.length} className="w-full">
                {loading ? "Starting..." : "Start"}
              </Button>
            </div>
            <div className="grid gap-2">
              <Label className="invisible">Finalize</Label>
              <Button variant="secondary" className="w-full" onClick={async () => {
                if (!sessionId) return;
                try { await fetch(`${backendUrl}/api/finalize/${sessionId}`, { method: 'POST' }); } catch {}
              }} disabled={!sessionId}>Finalize</Button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <div className="col-span-2 flex items-center gap-2">
              <Input placeholder="Search alerts (ID or description)" value={alertSearch} onChange={(e) => setAlertSearch(e.target.value)} />
              <Filter className="size-4 text-muted-foreground" />
            </div>
            <div className="flex items-center gap-2">
              <Label>Sort</Label>
              <select className="border-input rounded-md border bg-transparent px-2 py-1 h-9" value={sortKey} onChange={(e) => setSortKey(e.target.value as any)}>
                <option value="risk">Risk</option>
                <option value="amount">Amount</option>
                <option value="date">Date</option>
              </select>
              <Button variant="outline" size="icon" onClick={() => setSortAsc((v) => !v)} title="Toggle sort direction"><ArrowUpDown className="size-4" /></Button>
            </div>
            <div className="flex items-center gap-2">
              <Label>View</Label>
              <select className="border-input rounded-md border bg-transparent px-2 py-1 h-9" value={alertsView} onChange={(e) => setAlertsView(e.target.value as any)}>
                <option value="all">All</option>
                <option value="high">High Risk</option>
                <option value="bec">BEC</option>
                <option value="investment">Investment</option>
                <option value="device">Device Anomaly</option>
              </select>
              <Button variant="outline" size="sm" onClick={resetView}>Reset</Button>
              <Button variant="outline" size="sm" onClick={exportCSV}><Download className="size-4 mr-1" />Export</Button>
            </div>
          </div>
          <div className="max-h-48 overflow-auto border rounded p-2">
            {!alerts.length ? <Skeleton className="h-16 w-full" /> : (
              <table className="w-full text-xs">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="text-left font-medium">Alert ID</th>
                    <th className="text-left font-medium">Rule</th>
                    <th className="text-right font-medium">Amount</th>
                    <th className="text-center font-medium">Risk</th>
                    <th className="text-left font-medium">Queue</th>
                    <th className="text-left font-medium">Priority</th>
                    <th className="text-left font-medium">Description</th>
                    <th className="text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAlerts.map((a: any, i: number) => (
                    <tr key={i} className={`cursor-pointer hover:bg-accent/50 ${alerts.indexOf(a) === selected ? 'bg-accent' : ''}`} onClick={() => setSelected(alerts.indexOf(a))}>
                      <td className="py-1 pr-2">{a.alert_id || a.alertId}</td>
                      <td className="py-1 pr-2">{a.rule_id || a.ruleId}</td>
                      <td className="py-1 pr-2 text-right">{typeof a.amount === 'number' ? a.amount.toLocaleString(undefined, { style: 'currency', currency: a.currency || 'AUD' }) : '—'}</td>
                      <td className="py-1 pr-2 text-center"><span className={`px-2 py-0.5 rounded text-[10px] ${ (a.risk_score||0) > 800 ? 'bg-red-200/70 text-red-900 dark:bg-red-200/20 dark:text-red-200' : (a.risk_score||0) > 700 ? 'bg-amber-200/70 text-amber-900 dark:bg-amber-200/20 dark:text-amber-200' : 'bg-green-200/70 text-green-900 dark:bg-green-200/20 dark:text-green-200'}`}>{a.risk_score}</span></td>
                      <td className="py-1 pr-2">
                        <span className="px-2 py-0.5 rounded bg-muted/60">{a.queue || '—'}</span>
                      </td>
                      <td className="py-1 pr-2">
                        <span className={`px-2 py-0.5 rounded ${ String(a.priority||'').toLowerCase()==='high' ? 'bg-red-200/70 text-red-900 dark:bg-red-200/20 dark:text-red-200' : String(a.priority||'').toLowerCase()==='medium' ? 'bg-amber-200/70 text-amber-900 dark:bg-amber-200/20 dark:text-amber-200' : 'bg-muted/60'}`}>{a.priority || '—'}</span>
                      </td>
                      <td className="py-1 pr-2 max-w-[320px] truncate" title={a.description}>{a.description}</td>
                      <td className="py-1 pl-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button size="xs" variant="outline" onClick={(e) => { e.stopPropagation(); setAlertDetails(a); setAlertDetailsOpen(true); }}>Open</Button>
                          <Button size="xs" variant="secondary" onClick={async (e) => { e.stopPropagation(); await startForIndex(alerts.indexOf(a)); }}>Start</Button>
                          <Button size="xs" variant="outline" onClick={async (e) => { e.stopPropagation(); await startAndFinalize(alerts.indexOf(a)); }}>Start+Finalize</Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="text-[11px] text-muted-foreground">
            Shortcuts: Ctrl+Enter Send · Esc Stop · Ctrl+R Reconnect · Alt+/ Focus Reply · Alt+C Copy XAI
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={stop}>Stop</Button>
            <Button variant="outline" onClick={reconnect}>Reconnect</Button>
            <Button variant="outline" onClick={() => setState({ logs: [], agent_responses: [], dialogue_history: [] })}>Clear</Button>
            <Button variant="outline" onClick={async () => { await addGraphNote("Escalation requested by analyst"); await finalizeNow(); }} disabled={!sessionId} title="Escalate"><AlertTriangle className="size-4 mr-1" />Escalate</Button>
            <Button variant="outline" onClick={async () => { await addGraphNote("Trace payment initiated by analyst"); }} disabled={!sessionId} title="Trace Payment"><Search className="size-4 mr-1" />Trace Payment</Button>
            <Button variant="outline" onClick={async () => { await addGraphNote("Vendor callback requested by analyst"); }} disabled={!sessionId} title="Call Vendor"><Phone className="size-4 mr-1" />Call Vendor</Button>
          </div>
        </CardContent>
      </Card>

      {/* Two-column layout on large screens: left (Stream + Live Chat), right (Latest + Insights) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-4">
          <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-muted-foreground" />
              <CardTitle className="text-base">Stream</CardTitle>
            </div>
            <CardDescription>Server events and agent execution steps</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground space-y-1 max-h-56 overflow-auto" aria-live="polite">
              {(!state.logs || state.logs.length === 0) && <Skeleton className="h-20 w-full" />}
              {(state.logs || []).map((l: string, idx: number) => {
                const isActive = selectedLogIndex === idx;
                return (
                  <div
                    key={idx}
                    title="Click to view this agent's response"
                    onClick={() => setSelectedLogIndex(idx)}
                    className={`border-b py-1 px-2 rounded-md cursor-pointer transition-colors ${
                      isActive ? 'bg-accent text-accent-foreground' : 'hover:bg-accent hover:text-accent-foreground'
                    }`}
                  >
                      <div className="flex items-center gap-2">
                        <MessageSquare className="size-3.5 opacity-70" />
                        <span>{l}</span>
                        {state.current_step === idx + 1 ? (
                          <span className="ml-auto flex items-center gap-2 text-[10px] text-foreground/60" aria-label="In progress">
                            <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary animate-pulse" /> in progress…
                          </span>
                        ) : null}
                      <Button
                        size="xs"
                        variant="ghost"
                        className="ml-auto"
                        onClick={(e) => { e.stopPropagation(); setOpenRows((prev) => ({ ...prev, [idx]: !prev[idx] })); }}
                        aria-expanded={!!openRows[idx]}
                        aria-controls={`log-details-${idx}`}
                      >
                        {openRows[idx] ? 'Collapse' : 'Expand'}
                      </Button>
                    </div>
                    {/* Per-agent collapsible details */}
                    {(isActive || openRows[idx]) ? (
                      <div id={`log-details-${idx}`} className="mt-2">
                        <JsonBlock value={(state as Record<string, unknown>)[l] ?? (Array.isArray(state.agent_responses) ? state.agent_responses[idx] : undefined)} initiallyOpen={false} />
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </CardContent>
          </Card>

          <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <div className="flex items-center gap-2">
              <MessageSquare className="size-4 text-muted-foreground" />
              <CardTitle className="text-base">Live Chat</CardTitle>
            </div>
            <CardDescription>Full conversation history for the current chat</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div ref={chatRef} className="max-h-72 overflow-y-auto flex flex-col gap-2 pr-1 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent hover:scrollbar-thumb-muted/80" aria-live="polite">
              {(!state.dialogue_history || state.dialogue_history.length === 0) && (
                <Skeleton className="h-12 w-full" />
              )}
              {(state.dialogue_history || []).map((turn, i) => {
                const role = ((turn?.role as string) || "assistant") as "assistant" | "user" | "system" | "risk";
                const text = (turn?.question as string) || (turn?.user as string) || "";
                const badge = role === "assistant" ? "Assistant" : "You";
                return (
                  <ChatBubble key={i} role={role} text={text} badge={badge} />
                );
              })}
              {state.latest_risk_assessment ? (
                <ChatBubble role="risk" text={state.latest_risk_assessment} badge="RiskAssessor" />
              ) : null}
            </div>
            <ChatInput onSend={sendReply} disabled={!sessionId} />
          </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="hover:shadow-md transition-shadow">
            <CardHeader>
              <CardTitle className="text-base">Latest Agent Response</CardTitle>
              <CardDescription>
                Streaming output from agents{state && state.streaming_agent ? ` · Now: ${state.streaming_agent}` : ''}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!selectedAgentResponse ? (
                <div className="flex items-center justify-between">
                  <Skeleton className="h-4 w-2/3" />
                  <TypingDots />
                </div>
              ) : (
                <div key={streamingKey} className="[&>*]:transition-opacity [&>*]:duration-200">
                  <div className="flex justify-end mb-2">
                    <Button size="xs" variant="ghost" onClick={() => { try { navigator.clipboard.writeText(String(displayedLatest || "")); } catch {} }}>
                      <Copy className="size-3.5 mr-1" /> Copy
                    </Button>
                  </div>
                  <Markdown>{String(displayedLatest || "")}</Markdown>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="hover:shadow-md transition-shadow">
            <CardHeader>
              <CardTitle className="text-base">Insights</CardTitle>
              <CardDescription>Key facts, indicators, and suggestions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-3 text-sm">
                <div>
                  <div className="text-muted-foreground">Gate Reason</div>
                  <div className="text-xs whitespace-pre-wrap border rounded p-2 bg-muted/30 min-h-16">
                    {'gate_reason' in state ? JSON.stringify(state.gate_reason, null, 2) : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Known Facts</div>
                  <div className="text-xs whitespace-pre-wrap border rounded p-2 bg-muted/30 min-h-16">
                    {(state.transaction_context || '').toString().slice(0, 220) || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Indicators</div>
                  <div className="text-xs whitespace-pre-wrap border rounded p-2 bg-muted/30 min-h-16">
                    {(state.anomaly_context || '').toString().slice(0, 220) || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Suggested Next Step</div>
                  <div className="text-xs whitespace-pre-wrap border rounded p-2 bg-muted/30 min-h-16">
                    {(question || '').toString() || '—'}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* removed duplicate Insights card */}

      <Card className="hover:shadow-md transition-shadow">
        <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="size-4 text-muted-foreground" />
              <CardTitle className="text-base">Final Decision</CardTitle>
            </div>
          <CardDescription>Risk, policy, and compliance summary</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-muted-foreground">Risk Assessment</div>
              <Markdown className="mt-1">{(state.risk_assessment || state.risk_assessment_summary || "") as string}</Markdown>
            </div>
            <div>
              <div className="text-muted-foreground">Policy Decision</div>
              <Markdown className="mt-1">{(state.policy_decision || state.final_policy_decision || "") as string}</Markdown>
            </div>
            <div>
              <div className="text-muted-foreground">Compliance</div>
              <div className="whitespace-pre-wrap text-xs">{JSON.stringify(state.regulatory_compliance || {}, null, 2)}</div>
            </div>
          </div>
          <div className="text-xs text-muted-foreground mt-2">{state.case_id ? `Case: ${state.case_id}` : ""}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">XAI Decision</CardTitle>
          <CardDescription>Explainability details for audit</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-foreground/80 whitespace-pre-wrap rounded-md border p-2 bg-muted/30 hover:bg-muted/50 transition-colors">
            {state && state.xai_decision
              ? JSON.stringify(state.xai_decision, null, 2)
              : "—"}
          </div>
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setXaiOpen(true)}>Open Details</Button>
            <Button size="sm" variant="ghost" onClick={copyXai} aria-label="Copy XAI JSON"><Copy className="size-4" /></Button>
          </div>
        </CardContent>
      </Card>

      <Modal open={xaiOpen} onOpenChange={setXaiOpen} title="XAI Details">
        <XAITabs state={state} onCopy={() => { try { navigator.clipboard.writeText(JSON.stringify(state.xai_decision || {}, null, 2)); } catch {} }} />
      </Modal>

      <Modal open={alertDetailsOpen} onOpenChange={setAlertDetailsOpen} title="Alert Details">
        <div className="space-y-3 text-sm">
          {!alertDetails ? <div className="text-muted-foreground">No details</div> : (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div><div className="text-muted-foreground text-xs">Alert ID</div><div>{alertDetails.alert_id || alertDetails.alertId}</div></div>
                <div><div className="text-muted-foreground text-xs">Customer</div><div>{alertDetails.customer_id || alertDetails.customerId || '—'}</div></div>
                <div><div className="text-muted-foreground text-xs">Rule</div><div>{alertDetails.rule_id || alertDetails.ruleId || '—'}</div></div>
                <div><div className="text-muted-foreground text-xs">Queue</div><div>{alertDetails.queue || '—'}</div></div>
                <div><div className="text-muted-foreground text-xs">Priority</div><div>{alertDetails.priority || '—'}</div></div>
                <div><div className="text-muted-foreground text-xs">Status</div><div>{alertDetails.status || '—'}</div></div>
                <div><div className="text-muted-foreground text-xs">Amount</div><div>{typeof alertDetails.amount === 'number' ? alertDetails.amount.toLocaleString(undefined, { style: 'currency', currency: alertDetails.currency || 'AUD' }) : '—'}</div></div>
                <div><div className="text-muted-foreground text-xs">Risk Score</div><div>{alertDetails.risk_score || '—'}</div></div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs mb-1">Description</div>
                <div className="text-xs whitespace-pre-wrap border rounded p-2 bg-muted/30">{alertDetails.description || '—'}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs mb-1">Lifecycle</div>
                <div className="text-xs whitespace-pre-wrap border rounded p-2 bg-muted/30">
                  {alertDetails.alert_lifecycle ? JSON.stringify(alertDetails.alert_lifecycle, null, 2) : '—'}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs mb-1">Timeline</div>
                <div className="space-y-2">
                  {(() => {
                    const lc = alertDetails.alert_lifecycle || {};
                    const entries = Object.entries(lc).map(([k, v]) => ({ key: k, ts: new Date(String(v)).getTime(), raw: v }));
                    entries.sort((a, b) => a.ts - b.ts);
                    if (!entries.length) return <div className="text-xs text-muted-foreground">—</div>;
                    return entries.map((e, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary" />
                        <span className="uppercase tracking-wide text-muted-foreground">{e.key}</span>
                        <span className="ml-auto">{new Date(e.ts).toLocaleString()}</span>
                      </div>
                    ));
                  })()}
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={async () => { setAlertDetailsOpen(false); const idx = alerts.indexOf(alertDetails); if (idx >= 0) { await startForIndex(idx); } }}>Start Case</Button>
                <Button size="sm" variant="secondary" onClick={async () => { setAlertDetailsOpen(false); const idx = alerts.indexOf(alertDetails); if (idx >= 0) { await startAndFinalize(idx); } }}>Start + Finalize</Button>
              </div>
            </>
          )}
        </div>
      </Modal>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">Mem0 Summary & Memories</CardTitle>
              <CardDescription>Investigative context from graph memory</CardDescription>
            </div>
            <Button size="sm" variant="outline" onClick={fetchMem0} disabled={!state.case_id}>Refresh</Button>
          </CardHeader>
          <CardContent>
            <div className="text-sm space-y-3 max-h-64 overflow-auto">
              {!state.case_id ? (
                <div className="text-xs text-amber-600 bg-amber-100/50 dark:text-amber-300 dark:bg-amber-300/10 border border-amber-200/60 rounded p-2">
                  Start a session to enable case-bound memories.
                </div>
              ) : null}
              {(mem0Summary?.trim()?.toLowerCase()?.startsWith('no memories') || (!mem0Items || (mem0Items as any[]).length === 0)) ? (
                <div className="text-xs text-muted-foreground rounded border p-2">
                  No memories found yet. Ensure Mem0 Graph is configured or interact with the dialogue to seed memories.
                  <div className="mt-1">
                    <a href="#" onClick={(e) => { e.preventDefault(); alert('Open docs: docs_md/mem0_docs.md'); }} className="underline">Graph setup guide</a>
                    <span> · </span>
                    <a href="#" onClick={(e) => { e.preventDefault(); setGraphQuery('case ' + (state.case_id || '')); graphSearch(); }} className="underline">Retry search</a>
                  </div>
                </div>
              ) : null}
              <div>
                <div className="text-muted-foreground">Case Summary</div>
                <Markdown className="mt-1">{mem0Summary}</Markdown>
              </div>
              <div>
                <div className="text-muted-foreground">Recent Memories</div>
                <ul className="list-disc pl-5 space-y-1">
                  {(mem0Items || []).map((m: unknown, i: number) => (
                    <li key={i} className="text-xs whitespace-pre-wrap">{typeof m === 'string' ? m : JSON.stringify(m)}</li>
                  ))}
                </ul>
              </div>
              <div className="border-t pt-3 space-y-2">
                <div className="font-medium">Graph Memory (CRUD)</div>
                <div className="flex gap-2">
                  <Input className="flex-1" placeholder="Search graph e.g., remote access risk" value={graphQuery} onChange={(e) => setGraphQuery(e.target.value)} />
                  <Button onClick={graphSearch}>Search</Button>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => graphAdd("Manual analyst note: potential social engineering detected.")}>Add Note</Button>
                  <Button variant="destructive" onClick={graphClear} disabled={!state.case_id}>Clear Case</Button>
                </div>
                <div className="max-h-28 overflow-auto text-xs space-y-1">
                  {(graphResults || []).map((g: unknown, i: number) => (
                    <div key={i} className="rounded border p-2">{typeof g === 'string' ? g : JSON.stringify(g)}</div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="text-base">RAG Suggestions (SOP & Questions)</CardTitle>
            <CardDescription>Search SOP rules and contextual questions</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-2">
              <Input className="flex-1" placeholder="e.g., authorized scam refund policy" value={ragQuery} onChange={(e) => setRagQuery(e.target.value)} />
              <Button onClick={fetchRag}>Search</Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm max-h-64 overflow-auto">
              <div>
                <div className="text-muted-foreground">SOP Rules</div>
                <ul className="list-disc pl-5 space-y-1">
                  {(ragResults.sop_rules || []).map((r, i) => (
                    <li key={i} className="text-xs whitespace-pre-wrap"><Markdown className="!text-xs !leading-snug">{r}</Markdown></li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="text-muted-foreground">Questions</div>
                <ul className="list-disc pl-5 space-y-1">
                  {(ragResults.questions || []).map((q, i) => (
                    <li key={i} className="text-xs whitespace-pre-wrap">{q}</li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Streaming chat transcript (bubbles) */}
         {/* Removed duplicate transcript card to avoid confusion; Live Chat now shows the conversation */}
    </main>
  );
}

function ChatInput({ onSend, disabled }: { onSend: (t: string) => void; disabled?: boolean }) {
  const [val, setVal] = useState("");
  return (
    <div className="flex gap-2">
      <Input id="chat-input" className="flex-1" aria-label="Your reply" placeholder="Type your reply... (Ctrl+Enter to send)" value={val} onChange={(e) => setVal(e.target.value)} disabled={disabled} />
      <Button onClick={() => { onSend(val); setVal(""); }} disabled={disabled} title="Send (Ctrl+Enter)">Send</Button>
    </div>
  );
}

function XAITabs({ state, onCopy }: { state: any; onCopy: () => void }) {
  const decision = state?.xai_decision || {};
  const compliance = state?.regulatory_compliance || {};
  const calls = Array.isArray(state?.logs) ? state.logs.slice(-10) : [];
  const audit = Array.isArray(state?.audit_log) ? state.audit_log : [];
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">Explainability</div>
        <Button size="xs" variant="ghost" onClick={onCopy}><Copy className="size-3.5 mr-1" /> Copy</Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-muted-foreground text-xs mb-1">Decision</div>
          <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(decision, null, 2)}</pre>
        </div>
        <div>
          <div className="text-muted-foreground text-xs mb-1">Compliance</div>
          <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(compliance, null, 2)}</pre>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-muted-foreground text-xs mb-1">Model Calls (recent)</div>
          <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(calls, null, 2)}</pre>
        </div>
        <div>
          <div className="text-muted-foreground text-xs mb-1">Audit Trail</div>
          <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(audit, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
