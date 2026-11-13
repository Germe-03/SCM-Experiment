"""Spielmodus: Server für das Cockpit im Browser.

Start::

    python -m market_sim.game.server --port 8771 --saves runs/spielstaende [--seed 0 --years N --days-per-year N]

dann http://localhost:8771/ öffnen (liefert cockpit.html). Statische Dateien kommen aus
``market_sim/game/static``, alle Antworten ohne Cache (``no-store``). Nur 127.0.0.1.
"""

from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from market_sim.game.controller import GameController

STATIC = Path(__file__).parent / "static"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, controller: GameController | None = None, **kwargs):
        self.controller = controller
        super().__init__(*args, **kwargs)  # directory kommt per partial herein

    def end_headers(self) -> None:
        # no-store für alle Antworten (auch statische Dateien); _send_json setzt ihn deshalb nicht selbst.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, body: dict, status: int = 200) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> dict:
        try:
            length = max(int(self.headers.get("Content-Length", 0)), 0)
        except ValueError:  # kaputter Header
            length = 0
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:  # ungültiges JSON
            return {}
        return body if isinstance(body, dict) else {}

    def do_GET(self):  # noqa: N802 (http.server naming)
        path = urlsplit(self.path).path
        if path == "/":
            self.path = "/cockpit.html"
            super().do_GET()
            return
        if path == "/dashboard":
            target = self.controller.dashboard_file()
            if target is None or not target.is_file():
                self.send_error(404, "Das Dashboard ist noch nicht fertig")
                return
            payload = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/api/game":
            self._send_json(self.controller.state())
        elif path == "/api/options":
            self._send_json(self.controller.options())
        elif path == "/api/saves":
            self._send_json(self.controller.saves())
        elif path.startswith("/api/view/"):
            from urllib.parse import parse_qs
            query = {key: values[0] for key, values in parse_qs(urlsplit(self.path).query).items()}
            self._send_json(self.controller.view(path[len("/api/view/"):], **query))
        elif path.startswith("/api/"):
            self.send_error(404)
        else:  # statische Dateien
            super().do_GET()

    def do_POST(self):  # noqa: N802 (http.server naming)
        path = urlsplit(self.path).path
        body = self._read_body()
        try:
            if path == "/api/new":
                result = self.controller.new_game(
                    str(body.get("branch", "")),
                    str(body.get("name", "")),
                    region=body.get("region"),
                    category=body.get("category"),
                    years=(int(body["years"]) if str(body.get("years") or "").lstrip("-").isdigit() else None),
                )
            elif path == "/api/round":
                settings = body.get("settings")
                choices = body.get("choices")
                result = self.controller.end_round(
                    settings if isinstance(settings, dict) else None,
                    choices if isinstance(choices, dict) else None,
                    body.get("orders") if isinstance(body.get("orders"), dict) else None,
                )
            elif path == "/api/skip_year":
                result = self.controller.skip_year(
                    body.get("settings") if isinstance(body.get("settings"), dict) else None,
                    body.get("choices") if isinstance(body.get("choices"), dict) else None,
                    body.get("orders") if isinstance(body.get("orders"), dict) else None,
                )
            elif path == "/api/run_to_end":
                result = self.controller.run_to_end(
                    body.get("settings") if isinstance(body.get("settings"), dict) else None,
                    body.get("choices") if isinstance(body.get("choices"), dict) else None,
                    body.get("orders") if isinstance(body.get("orders"), dict) else None,
                )
            elif path == "/api/reset":
                result = self.controller.reset()
            elif path == "/api/check":
                result = self.controller.check(
                    body.get("settings") if isinstance(body.get("settings"), dict) else None,
                    body.get("choices") if isinstance(body.get("choices"), dict) else None,
                    body.get("orders") if isinstance(body.get("orders"), dict) else None,
                )
            elif path == "/api/contract_counter":
                result = self.controller.contract_counter(body)
            elif path == "/api/sell":
                result = self.controller.sell()
            elif path == "/api/advice":
                result = self.controller.advise(str(body.get("question", "")))
            elif path == "/api/save":
                result = self.controller.save(str(body.get("name", "")))
            elif path == "/api/load":
                result = self.controller.load(str(body.get("name", "")))
            else:
                self.send_error(404)
                return
        except Exception as error:  # Controller meldet Fehler eigentlich selbst, das ist das Netz dahinter
            self._send_json({"error": str(error)})
            return
        self._send_json(result)


def make_server(controller: GameController, port: int = 8771) -> ThreadingHTTPServer:
    """Build the game server on 127.0.0.1 (port 0 picks a free port)."""
    return ThreadingHTTPServer(("127.0.0.1", port),
                               partial(Handler, directory=str(STATIC), controller=controller))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--saves", default="runs/spielstaende")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--years", type=int)
    parser.add_argument("--days-per-year", type=int, default=360,
                        help="Tage pro Jahr (nur zum Testen ändern, Standard 360)")
    args = parser.parse_args(argv)
    controller = GameController(Path(args.saves), seed=args.seed,
                                years=args.years, days_per_year=args.days_per_year)
    if (controller.save_dir / "automatisch.json").exists():
        controller.loading = True

        def _restore() -> None:
            try:
                controller.load("automatisch")
            except Exception:
                pass
            finally:
                controller.loading = False

        threading.Thread(target=_restore, daemon=True).start()
    server = make_server(controller, args.port)
    print(f"Spiel: http://localhost:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
