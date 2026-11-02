import json
import sys
import os
import glob
import time
import threading
import sqlite3

# Ensure UTF-8 I/O encoding
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

USER_HOME = os.path.expanduser("~")
BRAIN_DIR = os.path.join(USER_HOME, ".gemini", "antigravity", "brain")
DB_PATH = os.path.join(USER_HOME, ".gemini", "antigravity", "conversation_summaries.db")

state = {
    "conv_id": "",
    "conv_title": "Antigravity",
    "model_name": "Gemini 3.8 Flash",
    "total_tokens": 0,
    "input_tokens": 0,
    "cache_tokens": 0,
    "output_tokens": 0,
    "step_count": 0,
    "max_tokens": 1000000,
    "pct": 0.0,
    "conv_count": 0,
    "has_rate_limit": False,
    "last_mtime": 0
}

def log(msg):
    print(f"[antigravity-nook] {msg}", file=sys.stderr, flush=True)

def send(msg):
    print(json.dumps(msg, ensure_ascii=False), flush=True)

def get_active_conversation_info():
    conv_id = ""
    title = "Sessão Ativa"
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT conversation_id, title FROM conversation_summaries ORDER BY last_modified_time DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                conv_id = row[0]
                if row[1] and row[1].strip():
                    title = row[1].strip()
            conn.close()
    except Exception as e:
        log(f"DB read error: {e}")

    # Fallback to brain dir if summary DB wasn't updated yet
    if not conv_id and os.path.exists(BRAIN_DIR):
        transcripts = glob.glob(os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl"))
        if transcripts:
            transcripts.sort(key=os.path.getmtime, reverse=True)
            conv_id = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(transcripts[0]))))

    return conv_id, title

def collect_metrics():
    try:
        if not os.path.exists(BRAIN_DIR):
            return False

        conv_folders = [f for f in glob.glob(os.path.join(BRAIN_DIR, "*")) if os.path.isdir(f)]
        state["conv_count"] = len(conv_folders)

        conv_id, title = get_active_conversation_info()
        if not conv_id:
            return False

        transcript_file = os.path.join(BRAIN_DIR, conv_id, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_file):
            return False

        mtime = os.path.getmtime(transcript_file)
        is_changed = (mtime != state["last_mtime"] or conv_id != state["conv_id"] or title != state["conv_title"])
        state["last_mtime"] = mtime
        state["conv_id"] = conv_id
        state["conv_title"] = title

        model = "Gemini 3.8 Flash"
        input_tokens = 0
        cache_tokens = 0
        output_tokens = 0
        steps = 0
        rate_limit_detected = False

        with open(transcript_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                steps += 1
                if "Gemini 3.8 Pro" in line or "Gemini Pro" in line:
                    model = "Gemini Pro"
                elif "Claude" in line:
                    model = "Claude 3.5"
                elif "Gemini 3.8 Flash" in line:
                    model = "Gemini 3.8 Flash"

                try:
                    obj = json.loads(line)
                    if obj.get("status") == "ERROR" and obj.get("source") != "USER_EXPLICIT":
                        err_str = str(obj.get("content", ""))
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                            rate_limit_detected = True
                    
                    if "input_tokens" in obj:
                        input_tokens = obj.get("input_tokens", 0)
                        cache_tokens = obj.get("cache_read_tokens", 0)
                        output_tokens = obj.get("output_tokens", 0)
                except Exception:
                    pass

        max_ctx = 200000 if "Claude" in model else 1000000
        total = input_tokens + cache_tokens
        pct = (total / max_ctx) * 100.0 if max_ctx > 0 else 0.0

        state["model_name"] = model
        state["input_tokens"] = input_tokens
        state["cache_tokens"] = cache_tokens
        state["output_tokens"] = output_tokens
        state["total_tokens"] = total
        state["step_count"] = steps
        state["max_tokens"] = max_ctx
        state["pct"] = pct
        state["has_rate_limit"] = rate_limit_detected
        return is_changed
    except Exception as e:
        log(f"Error in collect_metrics: {e}")
        return False

def build_tile_view():
    pct = state["pct"]
    total_k = state["total_tokens"] // 1000
    max_k = state["max_tokens"] // 1000
    progress_val = min(max(pct / 100.0, 0.0), 1.0)
    
    color = "accent"
    if state["has_rate_limit"] or pct >= 80:
        color = "red"
    elif pct >= 60:
        color = "yellow"

    # Truncate title for notch tile
    short_title = state["conv_title"]
    if len(short_title) > 16:
        short_title = short_title[:15] + "…"

    return {
        "type": "row",
        "align": "center",
        "gap": 8,
        "children": [
            {
                "type": "ring",
                "value": progress_val,
                "label": f"{int(pct)}%",
                "size": 28,
                "color": color
            },
            {
                "type": "column",
                "gap": 0,
                "children": [
                    { "type": "text", "text": short_title, "size": "small", "color": "dim" },
                    { "type": "text", "text": f"{total_k}k / {max_k}k", "size": "title" }
                ]
            },
            { "type": "spacer" },
            { "type": "button", "id": "btn_refresh", "icon": "arrows-clockwise" }
        ]
    }

def build_page_view():
    pct = state["pct"]
    total = state["total_tokens"]
    max_t = state["max_tokens"]
    progress_val = min(max(pct / 100.0, 0.0), 1.0)
    
    status_label = "Contexto Saudável"
    status_color = "accent"
    if state["has_rate_limit"]:
        status_label = "Rate Limit Detectado"
        status_color = "red"
    elif pct >= 80:
        status_label = "Contexto Alto (/compact)"
        status_color = "red"
    elif pct >= 60:
        status_label = "Atenção (Contexto Moderado)"
        status_color = "yellow"

    return {
        "type": "column",
        "gap": 10,
        "scroll": True,
        "children": [
            {
                "type": "card",
                "children": [
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "icon", "icon": "chat-centered-text", "color": "accent", "size": 20 },
                            { "type": "text", "text": state["conv_title"], "size": "title", "bold": True },
                            { "type": "spacer" },
                            { "type": "text", "text": status_label, "color": status_color, "size": "small", "bold": True }
                        ]
                    },
                    {
                        "type": "progress",
                        "value": progress_val,
                        "color": status_color
                    },
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "text", "text": f"Janela de Contexto · {state['model_name']}", "size": "small", "color": "dim" },
                            { "type": "spacer" },
                            { "type": "text", "text": f"{total:,} / {max_t:,} tokens ({pct:.1f}%)", "size": "body", "bold": True, "mono": True }
                        ]
                    }
                ]
            },
            {
                "type": "card",
                "children": [
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "icon", "icon": "chat-circle-dots", "size": 16, "color": "dim" },
                            { "type": "text", "text": "Passos na Conversa", "size": "body" },
                            { "type": "spacer" },
                            { "type": "text", "text": f"{state['step_count']} passos", "size": "body", "mono": True }
                        ]
                    },
                    { "type": "divider" },
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "icon", "icon": "arrow-down-right", "size": 16, "color": "dim" },
                            { "type": "text", "text": "Prompt / Input Tokens", "size": "body" },
                            { "type": "spacer" },
                            { "type": "text", "text": f"{state['input_tokens']:,}", "size": "body", "mono": True }
                        ]
                    },
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "icon", "icon": "lightning", "size": 16, "color": "accent" },
                            { "type": "text", "text": "Cache Read Tokens (Otimizado)", "size": "body" },
                            { "type": "spacer" },
                            { "type": "text", "text": f"{state['cache_tokens']:,}", "size": "body", "mono": True }
                        ]
                    },
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "icon", "icon": "arrow-up-right", "size": 16, "color": "dim" },
                            { "type": "text", "text": "Tokens Gerados (Output)", "size": "body" },
                            { "type": "spacer" },
                            { "type": "text", "text": f"{state['output_tokens']:,}", "size": "body", "mono": True }
                        ]
                    }
                ]
            },
            {
                "type": "card",
                "children": [
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "icon", "icon": "shield-check", "size": 16, "color": "accent" },
                            { "type": "text", "text": "Cotas Globais da Conta Google", "size": "body", "bold": True },
                            { "type": "spacer" },
                            { "type": "text", "text": "Menu 'View Usage'", "size": "small", "color": "dim" }
                        ]
                    },
                    {
                        "type": "text",
                        "text": "As cotas de 5h e semanais da sua conta Google são consultadas internamente pelo Antigravity através dos servidores Cloud da Google.",
                        "size": "small",
                        "color": "dim",
                        "wrap": True
                    },
                    { "type": "divider" },
                    {
                        "type": "row",
                        "align": "center",
                        "children": [
                            { "type": "icon", "icon": "folders", "size": 16, "color": "dim" },
                            { "type": "text", "text": "Histórico de Conversas Locais", "size": "body" },
                            { "type": "spacer" },
                            { "type": "text", "text": f"{state['conv_count']} conversas salvas", "size": "body", "mono": True }
                        ]
                    }
                ]
            },
            {
                "type": "row",
                "gap": 8,
                "align": "center",
                "children": [
                    { "type": "button", "id": "btn_refresh", "label": "Atualizar", "icon": "arrows-clockwise", "primary": True },
                    { "type": "button", "id": "btn_copy", "label": "Copiar Resumo", "icon": "copy" },
                    { "type": "button", "id": "btn_open", "label": "Abrir Pasta Brain", "icon": "folder" }
                ]
            }
        ]
    }

def push_updates():
    send({"type": "tile", "view": build_tile_view()})
    send({
        "type": "page",
        "view": build_page_view(),
        "actions": [
            { "id": "btn_refresh", "icon": "arrows-clockwise", "tooltip": "Atualizar métricas" }
        ]
    })

def watcher_loop():
    while True:
        time.sleep(3)
        try:
            changed = collect_metrics()
            if changed:
                push_updates()
        except Exception:
            pass

def main():
    collect_metrics()
    push_updates()

    # Background file watcher
    t = threading.Thread(target=watcher_loop, daemon=True)
    t.start()

    # Process events from Nook via stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            mtype = msg.get("type")

            if mtype in ("hello", "page_open"):
                collect_metrics()
                push_updates()
            elif mtype == "event":
                eid = msg.get("id")
                if eid in ("btn_refresh", "refresh"):
                    collect_metrics()
                    push_updates()
                elif eid == "btn_copy":
                    summary = (
                        f"📊 Antigravity - {state['conv_title']}\n"
                        f"- Modelo: {state['model_name']}\n"
                        f"- Contexto: {state['total_tokens']:,} / {state['max_tokens']:,} tokens ({state['pct']:.1f}%)\n"
                        f"- Passos na sessão: {state['step_count']}\n"
                        f"- Input: {state['input_tokens']:,} | Cache: {state['cache_tokens']:,} | Output: {state['output_tokens']:,}\n"
                        f"- Conversas no Histórico: {state['conv_count']}"
                    )
                    send({"type": "copy", "text": summary})
                elif eid == "btn_open":
                    send({"type": "open", "target": BRAIN_DIR})
            elif mtype == "shutdown":
                break
        except Exception as e:
            log(f"Error handling event: {e}")

if __name__ == "__main__":
    main()
