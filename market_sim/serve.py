"""Phase 12: serve the dashboard locally and answer chat questions with the local model.

Start::

    python -m market_sim.serve --dir runs --port 8770

then open http://localhost:8770/dashboard.html. Questions go to Ollama on this machine.
"""

from __future__ import annotations

import argparse
import json
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from market_sim.config import load_market_config
from market_sim.llm import OllamaClient, unchecked_numbers
from market_sim.texts import SYSTEM, context_for_question


def load_dashboard_data(path: Path) -> dict:
    html = path.read_text(encoding="utf-8")
    match = re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError(f"{path} contains no dashboard data")
    return json.loads(match.group(1).replace("<\\/", "</"))


def answer(data: dict, llm, question: str) -> dict:
    facts, sources = context_for_question(data, question)
    prompt = (f"FAKTEN:\n{facts}\n\nFRAGE: {question}\n\nBeantworte die Frage in höchstens 5 Sätzen mit diesen "
              f"Fakten. Fasse zusammen, was die Fakten zur Frage sagen. Wenn sie wirklich nichts dazu enthalten, "
              f"sage das ehrlich.")
    try:
        text = llm.generate(SYSTEM, prompt).replace("ß", "ss").strip()
    except Exception as error:  # Ollama not running or too slow
        return {"answer": f"Das lokale Modell antwortet nicht ({error.__class__.__name__}). Läuft Ollama?",
                "sources": [], "checked": False}
    bad = unchecked_numbers(text, facts)
    if bad:
        text += "\n\n(Hinweis: Einzelne Zahlen in dieser Antwort stehen nicht in den Daten und sind ungeprüft.)"
    return {"answer": text, "sources": sources, "checked": not bad}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, state=None, **kwargs):
        self.state = state
        super().__init__(*args, **kwargs)

    def do_POST(self):  # noqa: N802 (http.server naming)
        if self.path != "/api/chat":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            question = json.loads(self.rfile.read(length) or b"{}").get("question", "").strip()[:500]
        except ValueError:
            question = ""
        if not question:
            body = {"answer": "Bitte stelle eine Frage.", "sources": [], "checked": True}
        else:
            body = answer(self.state["data"], self.state["llm"], question)
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main(argv: list[str] | None = None) -> None:
    cfg = load_market_config().ollama
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="runs")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--model", default=cfg.chat_model)
    args = parser.parse_args(argv)
    directory = Path(args.dir)
    state = {"data": load_dashboard_data(directory / "dashboard.html"),
             "llm": OllamaClient(args.model, cfg.host, cfg.timeout_seconds, cfg.temperature, cfg.max_tokens)}
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 partial(Handler, directory=str(directory), state=state))
    print(f"Dashboard: http://localhost:{args.port}/dashboard.html (Modell {args.model})")
    server.serve_forever()


if __name__ == "__main__":
    main()
