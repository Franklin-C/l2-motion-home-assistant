"""Small Windows desktop tester for the L2 Motion Bluetooth bridge."""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import ttk


CONFIG_PATH = Path(os.environ["LOCALAPPDATA"]) / "L2MotionBridge" / "config.json"


class BridgeClient:
    """Authenticated localhost client that never exposes the bridge token in the UI."""

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        self.base_url = f"http://127.0.0.1:{int(config.get('port', 8765))}"
        self.headers = {
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": "application/json",
        }

    def request(self, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=self.headers,
            method="GET" if payload is None else "POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            try:
                detail = json.load(error).get("error", error.reason)
            except (ValueError, AttributeError):
                detail = error.reason
            raise RuntimeError(str(detail)) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                "The Windows bridge is not reachable. Run install.ps1 or check its scheduled task."
            ) from error


class BedTestApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=24)
        self.master = master
        self.client: BridgeClient | None = None
        self.status = tk.StringVar(value="Checking the Windows bridge…")
        self.detail = tk.StringVar(value="")
        self._build()
        self.after(150, lambda: self._run("health", self._health))

    def _build(self) -> None:
        self.master.title("L2 Motion Bed Test")
        self.master.geometry("440x300")
        self.master.minsize(420, 280)
        self.pack(fill="both", expand=True)

        ttk.Label(self, text="L2 Motion Bed", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text="Safe Bluetooth test via the Windows bridge",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 22))

        self.status_label = ttk.Label(self, textvariable=self.status, font=("Segoe UI", 11, "bold"))
        self.status_label.pack(anchor="w")
        ttk.Label(self, textvariable=self.detail, wraplength=390).pack(anchor="w", pady=(4, 20))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        self.scan_button = ttk.Button(buttons, text="Scan for bed", command=lambda: self._run("scan", self._scan))
        self.scan_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.light_button = ttk.Button(
            buttons,
            text="Toggle under-bed light",
            command=lambda: self._run("light", self._light),
        )
        self.light_button.pack(side="left", fill="x", expand=True, padx=(6, 0))

        ttk.Separator(self).pack(fill="x", pady=22)
        ttk.Label(
            self,
            text="This tester intentionally has no motor controls.",
            foreground="#666666",
        ).pack(anchor="w")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.scan_button.configure(state=state)
        self.light_button.configure(state=state)

    def _run(self, action: str, operation) -> None:
        self._set_busy(True)
        self.status.set({"health": "Checking bridge…", "scan": "Scanning…", "light": "Sending light command…"}[action])
        self.detail.set("")

        def worker() -> None:
            try:
                message, detail = operation()
            except Exception as error:  # UI boundary
                message, detail = "Not connected", str(error)
            self.after(0, lambda: self._finish(message, detail))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, message: str, detail: str) -> None:
        self.status.set(message)
        self.detail.set(detail)
        self._set_busy(False)

    def _get_client(self) -> BridgeClient:
        if self.client is None:
            self.client = BridgeClient()
        return self.client

    def _health(self) -> tuple[str, str]:
        data = self._get_client().request("/health")
        return "Windows bridge is running", f"Configured bed: {data.get('device_name', 'Unknown')}"

    def _scan(self) -> tuple[str, str]:
        data = self._get_client().request("/scan", {})
        return "Bed found", f"{data.get('name', 'L2 Motion bed')} at {data.get('address', 'unknown address')}"

    def _light(self) -> tuple[str, str]:
        self._get_client().request("/command", {"command": "light"})
        return "Light command sent", "Check that the under-bed light changed."


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    BedTestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
