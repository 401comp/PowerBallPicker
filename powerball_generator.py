#!/usr/bin/env python3
"""
Powerball Number Generator
Pulls 10 years of historical draws, provides multiple generation modes,
and save-to-file functionality.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import random
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
from datetime import datetime, timedelta
from collections import Counter
import threading
import queue
import os
import sys
import html
import tempfile
import webbrowser
from pathlib import Path


class PowerballApp:
    WHITE_MAX = 69
    PB_MAX = 26
    WHITE_COUNT = 5
    JACKPOT_ODDS = 292_201_338
    DEFAULT_TICKET_PRICE = 2.00

    def __init__(self, root):
        self.root = root
        self.root.title("Powerball Playbook")
        self.root.resizable(True, True)
        self.root.minsize(1060, 760)
        # Prefer a high-legibility face and a larger default than Tk's small,
        # thin system rendering. Explicit sizes below keep the hierarchy clear.
        self.sans = "Arial"

        self.draws = []
        self.white_freq = Counter()
        self.pb_freq = Counter()
        self.white_trend = Counter()
        self.pb_trend = Counter()
        self.generated_results = []
        self.generated_combinations = set()
        self.data_loaded = False
        self.ui_events = queue.Queue()

        # Colors
        self.bg = "#1a1a2e"
        self.panel_bg = "#16213e"
        self.accent = "#7c5cff"
        self.accent_hover = "#6a4ae8"
        self.pb_red = "#ef476f"
        self.white_ball = "#ffffff"
        self.text_light = "#eaeaea"
        self.text_dim = "#c8d2e5"
        self.btn_bg = "#0f3460"

        self.root.configure(bg=self.bg)
        self._configure_styles()
        self._build_ui()
        self._center_window(1120, 800)

        self.status_var.set("Ready — Pure Random available now, weighted modes loading...")
        threading.Thread(target=self._fetch_data, daemon=True).start()
        self._poll_ui_events()
        self.root.after_idle(self._show_internet_notice)

    def _notice_path(self):
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        return base / "PowerballGenerator" / "preferences.json"

    def _show_internet_notice(self):
        path = self._notice_path()
        try:
            preferences = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(preferences, dict):
                preferences = {}
        except (OSError, ValueError):
            preferences = {}
        if preferences.get("hide_internet_notice") is True:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Internet connection")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(padx=24, pady=20)
        tk.Label(dialog, text="Powerball Picker needs an internet connection to load historical records.\n\nPure Random mode is available offline.", justify="left", wraplength=400).pack(anchor="w")
        hide = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="Don’t show this again", variable=hide).pack(anchor="w", pady=(16, 12))

        def close_notice():
            if hide.get():
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    preferences["hide_internet_notice"] = True
                    path.write_text(json.dumps(preferences, indent=2), encoding="utf-8")
                except OSError:
                    messagebox.showwarning("Preference not saved", "The choice could not be saved, so this message may appear again.", parent=dialog)
            dialog.destroy()

        ttk.Button(dialog, text="OK", command=close_notice).pack(anchor="e")
        dialog.protocol("WM_DELETE_WINDOW", close_notice)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.grab_set()
        dialog.focus_set()

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Title
        tk.Label(
            self.root, text="POWERBALL PLAYBOOK",
            font=(self.sans, 29, "bold"), bg=self.bg, fg=self.white_ball
        ).pack(pady=(18, 2))

        tk.Label(
            self.root, text="Data-guided picks, smarter coverage, and a budget that does not wander off drunk",
            font=(self.sans, 13, "bold"), bg=self.bg, fg=self.text_dim
        ).pack(pady=(0, 14))

        # ── Live summary ───────────────────────────────────────────────
        summary = tk.Frame(self.root, bg=self.bg)
        summary.pack(fill="x", padx=30, pady=(0, 14))
        self.batch_cost_var = tk.StringVar(value="THIS BATCH  $0.00")
        self.session_cost_var = tk.StringVar(value="SESSION TOTAL  $0.00")
        self.coverage_var = tk.StringVar(value="UNIQUE LINES  0")
        for text_var, detail in (
            (self.batch_cost_var, "Cost of the last generation"),
            (self.session_cost_var, "All lines still on screen"),
            (self.coverage_var, "No duplicate combinations"),
        ):
            card = tk.Frame(summary, bg=self.panel_bg, highlightbackground="#29324f", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=5)
            tk.Label(card, textvariable=text_var, font=(self.sans, 14, "bold"),
                     bg=self.panel_bg, fg=self.white_ball, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            tk.Label(card, text=detail, font=(self.sans, 11, "bold"),
                     bg=self.panel_bg, fg=self.text_dim, anchor="w").pack(fill="x", padx=12, pady=(0, 8))

        # ── Controls ───────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg=self.bg)
        ctrl.pack(pady=(0, 6), padx=30)

        tk.Label(ctrl, text="Mode:", font=(self.sans, 14, "bold"),
                 bg=self.bg, fg=self.text_light).pack(side="left", padx=(0, 6))

        self.mode_var = tk.StringVar(value="Pure Random")
        ttk.Combobox(
            ctrl, textvariable=self.mode_var,
            values=["Trend Signal", "Pure Random", "Pattern Guard", "Hot Numbers", "Cold Numbers", "Balanced Mix"],
            state="readonly", width=16, font=(self.sans, 14), style="Readable.TCombobox"
        ).pack(side="left", padx=(0, 16))

        tk.Label(ctrl, text="Lines:", font=(self.sans, 14, "bold"),
                 bg=self.bg, fg=self.text_light).pack(side="left", padx=(0, 6))

        self.qty_var = tk.StringVar(value="1")
        tk.Spinbox(ctrl, from_=1, to=20, textvariable=self.qty_var,
                   width=4, font=(self.sans, 14), justify="center"
                   ).pack(side="left", padx=(0, 16))

        tk.Label(ctrl, text="$/line:", font=(self.sans, 14, "bold"),
                 bg=self.bg, fg=self.text_light).pack(side="left", padx=(0, 6))
        self.price_var = tk.StringVar(value=f"{self.DEFAULT_TICKET_PRICE:.2f}")
        price_entry = tk.Entry(ctrl, textvariable=self.price_var, width=5,
                               font=(self.sans, 14), justify="center",
                               bg="#24304d", fg=self.text_light, insertbackground=self.text_light,
                               relief="flat")
        price_entry.pack(side="left", padx=(0, 16), ipady=3)
        price_entry.bind("<FocusOut>", lambda _event: self._update_cost_summary(0))

        tk.Label(ctrl, text="Budget:", font=(self.sans, 14, "bold"),
                 bg=self.bg, fg=self.text_light).pack(side="left", padx=(0, 6))
        self.budget_var = tk.StringVar(value="20.00")
        budget_entry = tk.Entry(ctrl, textvariable=self.budget_var, width=5,
                                font=(self.sans, 14), justify="center",
                                bg="#24304d", fg=self.text_light, insertbackground=self.text_light,
                                relief="flat")
        budget_entry.pack(side="left", padx=(0, 16), ipady=3)
        budget_entry.bind("<FocusOut>", lambda _event: self._update_cost_summary(0))

        ttk.Button(
            ctrl, text="Generate Picks", style="Primary.TButton", command=self._generate
        ).pack(side="left", padx=(0, 10))

        actions = tk.Frame(self.root, bg=self.bg)
        actions.pack(pady=(0, 6))

        ttk.Button(
            actions, text="Save Play Slip", style="Secondary.TButton", command=self._save_results
        ).pack(side="left", padx=(0, 10))

        ttk.Button(
            actions, text="Print", style="Secondary.TButton", command=self._print_results
        ).pack(side="left", padx=(0, 10))

        ttk.Button(
            actions, text="Clear", style="Secondary.TButton", command=self._clear_results
        ).pack(side="left")

        # ── Mode description ───────────────────────────────────────────
        self.mode_desc_var = tk.StringVar(value="Every valid line has the same jackpot odds. $2 is the standard price; adjust for your jurisdiction or add-ons.")
        tk.Label(
            self.root, textvariable=self.mode_desc_var,
            font=(self.sans, 12, "bold"), bg=self.bg, fg=self.text_dim,
            wraplength=1040, justify="center"
        ).pack(pady=(0, 8))
        self.mode_var.trace_add("write", self._update_mode_desc)
        self.coach_var = tk.StringVar(value="Coverage coach: add distinct lines for broader combination coverage; duplicates only repeat the same shot.")
        tk.Label(
            self.root, textvariable=self.coach_var,
            font=(self.sans, 12, "bold"), bg=self.bg, fg="#8df0c8",
            wraplength=1040, justify="center"
        ).pack(pady=(0, 10))

        # ── Hand-picked line ──────────────────────────────────────────
        manual = tk.Frame(self.root, bg=self.panel_bg,
                          highlightbackground="#2a4268", highlightthickness=1)
        manual.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(manual, text="ADD MY NUMBERS", font=(self.sans, 13, "bold"),
                 bg=self.panel_bg, fg=self.white_ball).pack(side="left", padx=(14, 10), pady=9)
        tk.Label(manual, text="White balls", font=(self.sans, 12, "bold"),
                 bg=self.panel_bg, fg=self.text_dim).pack(side="left", padx=(0, 6))
        self.manual_white_vars = [tk.StringVar() for _ in range(self.WHITE_COUNT)]
        white_number = self.root.register(self._validate_white_number)
        for var in self.manual_white_vars:
            entry = tk.Entry(manual, textvariable=var, width=3, font=(self.sans, 14, "bold"),
                             justify="center", bg="#24304d", fg=self.text_light,
                             insertbackground=self.text_light, relief="flat",
                             validate="key", validatecommand=(white_number, "%P"))
            entry.pack(side="left", padx=2, ipady=4)
            entry.bind("<Return>", lambda _event: self._add_manual_pick())
            entry.bind("<Tab>", self._focus_next)
            entry.bind("<Shift-Tab>", self._focus_previous)
        tk.Label(manual, text="Powerball", font=(self.sans, 12, "bold"),
                 bg=self.panel_bg, fg=self.text_dim).pack(side="left", padx=(14, 6))
        self.manual_pb_var = tk.StringVar()
        powerball_number = self.root.register(self._validate_powerball_number)
        pb_entry = tk.Entry(manual, textvariable=self.manual_pb_var, width=3,
                            font=(self.sans, 14, "bold"), justify="center",
                            bg="#5a1e35", fg="white", insertbackground="white", relief="flat",
                            validate="key", validatecommand=(powerball_number, "%P"))
        pb_entry.pack(side="left", padx=(0, 12), ipady=4)
        pb_entry.bind("<Return>", lambda _event: self._add_manual_pick())
        pb_entry.bind("<Tab>", self._focus_next)
        pb_entry.bind("<Shift-Tab>", self._focus_previous)
        ttk.Button(manual, text="Add to Play Slip", style="Secondary.TButton",
                   command=self._add_manual_pick).pack(side="left", padx=(0, 10), pady=4)
        ttk.Button(manual, text="What is coverage?", style="Tertiary.TButton",
                   command=self._show_coverage_help).pack(side="right", padx=(0, 12), pady=4)

        # ── Results area ───────────────────────────────────────────────
        rf = tk.Frame(self.root, bg=self.panel_bg,
                      highlightbackground="#2a2a4a", highlightthickness=1)
        rf.pack(padx=24, pady=(0, 6), fill="both", expand=True)

        header = tk.Frame(rf, bg=self.panel_bg)
        header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(header, text="YOUR PLAY SLIP", font=(self.sans, 13, "bold"),
                 bg=self.panel_bg, fg=self.text_dim).pack(side="left")
        self.result_count_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.result_count_var,
                 font=(self.sans, 12, "bold"), bg=self.panel_bg, fg=self.text_dim
                 ).pack(side="right")

        self.canvas = tk.Canvas(rf, bg=self.panel_bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(rf, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=self.panel_bg)

        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._cw = self.canvas.create_window((0, 0), window=self.inner, anchor="n")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        def _resize(e):
            self.canvas.itemconfig(self._cw, width=e.width)
            self.canvas.coords(self._cw, e.width // 2, 0)
        self.canvas.bind("<Configure>", _resize)

        self.canvas.pack(side="left", fill="both", expand=True, padx=12, pady=(0, 10))
        scrollbar.pack(side="right", fill="y", pady=(0, 10))
        self.canvas.bind("<MouseWheel>",
                         lambda e: self.canvas.yview_scroll(-1 * e.delta, "units"))

        # ── Bottom section (packed bottom-up) ──────────────────────────
        # Status bar (very bottom)
        self.status_var = tk.StringVar(value="Starting up...")
        tk.Label(
            self.root, textvariable=self.status_var, font=(self.sans, 12, "bold"),
            bg="#111", fg=self.text_dim, anchor="w", padx=12, pady=5
        ).pack(fill="x", side="bottom")

        # Progress bar (above status bar)
        self.progress_frame = tk.Frame(self.root, bg=self.bg)
        self.progress_frame.pack(fill="x", side="bottom", padx=24, pady=(4, 2))
        self.progress_label = tk.Label(
            self.progress_frame, text="Loading historical data...",
            font=(self.sans, 11, "bold"), bg=self.bg, fg=self.text_dim, anchor="w"
        )
        self.progress_label.pack(fill="x")
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate")
        self.progress_bar.pack(fill="x", pady=(2, 2))

    # ── Data fetching ──────────────────────────────────────────────────

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        # Aqua widgets ignore several color options and can render white text on
        # white controls in dark windows. "clam" styles own every state instead.
        style.configure("Readable.TCombobox", fieldbackground="#24304d", background="#24304d",
                        foreground=self.text_light, arrowcolor=self.text_light, padding=6,
                        bordercolor="#526486", lightcolor="#526486", darkcolor="#526486",
                        font=(self.sans, 14))
        style.map("Readable.TCombobox",
                  fieldbackground=[("readonly", "#24304d"), ("disabled", "#28334d")],
                  foreground=[("readonly", "#ffffff"), ("disabled", "#c8d2e5")],
                  selectbackground=[("readonly", "#24304d")],
                  selectforeground=[("readonly", "#ffffff")])
        style.configure("Primary.TButton", font=(self.sans, 15, "bold"), foreground="#ffffff",
                        background=self.accent, borderwidth=0, padding=(16, 9), focusthickness=2,
                        focuscolor="#ffffff")
        style.map("Primary.TButton", background=[("active", self.accent_hover), ("disabled", "#4b5068")],
                  foreground=[("disabled", "#d5d9e5")])
        style.configure("Secondary.TButton", font=(self.sans, 14, "bold"), foreground="#ffffff",
                        background="#31456f", borderwidth=0, padding=(14, 9), focusthickness=2,
                        focuscolor="#ffffff")
        style.map("Secondary.TButton", background=[("active", "#456096"), ("disabled", "#4b5068")],
                  foreground=[("disabled", "#d5d9e5")])
        style.configure("Tertiary.TButton", font=(self.sans, 12, "bold"), foreground="#b9c9e8",
                        background=self.panel_bg, borderwidth=0, padding=(8, 6))
        style.map("Tertiary.TButton", background=[("active", "#24304d")],
                  foreground=[("active", "#ffffff")])
        style.configure("Horizontal.TProgressbar", troughcolor="#24304d", background=self.accent,
                        bordercolor="#24304d", lightcolor=self.accent, darkcolor=self.accent)

    def _post_ui(self, callback):
        """Pass work from the network thread to Tk's main thread safely."""
        self.ui_events.put(callback)

    def _poll_ui_events(self):
        try:
            while True:
                self.ui_events.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(50, self._poll_ui_events)

    def _fetch_data(self):
        self._post_ui(lambda: self._set_progress(5, "Connecting to data source..."))

        cutoff = datetime.now() - timedelta(days=365 * 10)
        cutoff_str = cutoff.strftime("%Y-%m-%dT00:00:00.000")
        query = urllib.parse.urlencode({
            "$where": f"draw_date >= '{cutoff_str}'",
            "$order": "draw_date DESC",
            "$limit": "5000",
        })
        url = f"https://data.ny.gov/resource/d6yy-54nr.json?{query}"

        ctx = ssl.create_default_context()
        try:
            ctx.load_default_certs()
        except Exception:
            print("Warning: SSL cert load failed, disabling verification for data.ny.gov")
            ctx = ssl._create_unverified_context()

        raw = None

        # Attempt 1: JSON API
        try:
            self._post_ui(lambda: self._set_progress(15, "Requesting draw history..."))
            req = urllib.request.Request(url, headers={
                "Accept": "application/json", "User-Agent": "PowerballGenerator/1.0"
            })
            with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
                self._post_ui(lambda: self._set_progress(40, "Downloading data..."))
                raw = json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

        # Attempt 2: CSV fallback
        if raw is None:
            try:
                self._post_ui(lambda: self._set_progress(20, "Trying CSV fallback..."))
                csv_url = "https://data.ny.gov/api/views/d6yy-54nr/rows.csv?accessType=DOWNLOAD"
                req2 = urllib.request.Request(csv_url, headers={"User-Agent": "PowerballGenerator/1.0"})
                with urllib.request.urlopen(req2, timeout=30, context=ctx) as resp:
                    self._post_ui(lambda: self._set_progress(40, "Downloading CSV..."))
                    text = resp.read().decode("utf-8")

                import csv as csv_mod
                raw = []
                lines = text.strip().split("\n")
                if len(lines) > 1:
                    for row in csv_mod.DictReader(lines):
                        date_val = row.get("Draw Date", "")
                        nums_val = row.get("Winning Numbers", "")
                        if date_val and nums_val:
                            try:
                                dt = datetime.strptime(date_val.strip(), "%m/%d/%Y")
                                if dt >= cutoff:
                                    raw.append({"draw_date": dt.strftime("%Y-%m-%d"),
                                                "winning_numbers": nums_val.strip()})
                            except ValueError:
                                continue
            except Exception:
                raw = None

        # Failed both
        if not raw:
            self._post_ui(lambda: self.status_var.set(
                "Could not reach data.ny.gov — using pure random only"))
            self._post_ui(lambda: self._set_progress(100, "Connection failed"))
            self._fill_uniform()
            self._post_ui(lambda: self.root.after(2000, self._hide_progress))
            return

        # Parse draws
        try:
            self._post_ui(lambda: self._set_progress(60, "Parsing draw results..."))
            for row in raw:
                nums = row.get("winning_numbers", row.get("Winning Numbers", ""))
                parts = nums.strip().split()
                if len(parts) >= 6:
                    whites = sorted(int(x) for x in parts[:5])
                    pb = int(parts[5])
                    date = row.get("draw_date", row.get("Draw Date", ""))[:10]
                    self.draws.append({"date": date, "whites": whites, "pb": pb})

            self._post_ui(lambda: self._set_progress(80, "Building frequency tables..."))
            for d in self.draws:
                for w in d["whites"]:
                    self.white_freq[w] += 1
                self.pb_freq[d["pb"]] += 1

            # The API is requested newest-first. This gives the last 120 draws
            # progressively more weight than decade-old results.
            recent_draws = self.draws[:120]
            for position, d in enumerate(recent_draws):
                recency_weight = 3.0 - (2.0 * position / max(1, len(recent_draws) - 1))
                for w in d["whites"]:
                    self.white_trend[w] += recency_weight
                self.pb_trend[d["pb"]] += recency_weight

            self.data_loaded = True
            self._post_ui(lambda: self._set_progress(100, "Complete"))
            self._post_ui(lambda: self.status_var.set(
                f"Loaded {len(self.draws)} draws ({self.draws[-1]['date']} — {self.draws[0]['date']}) — all modes ready"
            ))
            self._post_ui(lambda: self.root.after(800, self._hide_progress))

        except Exception as e:
            self._post_ui(lambda: self.status_var.set(f"Parse error: {e} — using pure random"))
            self._post_ui(lambda: self._set_progress(100, "Parse failed"))
            self._fill_uniform()
            self._post_ui(lambda: self.root.after(2000, self._hide_progress))

    def _fill_uniform(self):
        for i in range(1, self.WHITE_MAX + 1):
            self.white_freq[i] = 1
        for i in range(1, self.PB_MAX + 1):
            self.pb_freq[i] = 1

    def _set_progress(self, val, label):
        self.progress_bar["value"] = val
        self.progress_label.config(text=label)

    def _hide_progress(self):
        self.progress_frame.pack_forget()

    # ── Mode descriptions ──────────────────────────────────────────────

    def _update_mode_desc(self, *_):
        descs = {
            "Trend Signal": "Recent draws get up to 3× the weight of older history. A data-guided heuristic, not a guarantee.",
            "Pure Random": "Every valid line is equally likely. The clean, honest Quick Pick.",
            "Pattern Guard": "Avoids birthday-heavy and obvious runs. It cannot improve draw odds; it may reduce jackpot-sharing if lightning strikes.",
            "Hot Numbers": "Entertainment view: favors recently frequent numbers. History does not predict the next draw.",
            "Cold Numbers": "Entertainment view: favors less frequent numbers. Nothing is actually overdue.",
            "Balanced Mix": "Entertainment view: blends hot and cold history without claiming predictive power.",
        }
        self.mode_desc_var.set(descs.get(self.mode_var.get(), ""))

    # ── Number generation ──────────────────────────────────────────────

    def _weighted_sample(self, freq, pool_max, count, invert=False):
        weights = {}
        for n in range(1, pool_max + 1):
            w = freq.get(n, 0) + 1
            if invert:
                w = 1.0 / w
            weights[n] = w
        chosen, remaining = [], dict(weights)
        for _ in range(count):
            nums = list(remaining.keys())
            pick = random.choices(nums, weights=[remaining[n] for n in nums], k=1)[0]
            chosen.append(pick)
            del remaining[pick]
        return sorted(chosen)

    def _weighted_single(self, freq, pool_max, invert=False):
        weights = {}
        for n in range(1, pool_max + 1):
            w = freq.get(n, 0) + 1
            if invert:
                w = 1.0 / w
            weights[n] = w
        nums = list(weights.keys())
        return random.choices(nums, weights=[weights[n] for n in nums], k=1)[0]

    def _weighted_from_pool(self, freq, pool, count, invert=False):
        weights = {}
        for n in pool:
            w = freq.get(n, 0) + 1
            if invert:
                w = 1.0 / w
            weights[n] = w
        chosen, remaining = [], dict(weights)
        for _ in range(count):
            nums = list(remaining.keys())
            pick = random.choices(nums, weights=[remaining[n] for n in nums], k=1)[0]
            chosen.append(pick)
            del remaining[pick]
        return sorted(chosen)

    def _pick_numbers(self, mode):
        if mode == "Pure Random":
            whites = sorted(random.sample(range(1, self.WHITE_MAX + 1), self.WHITE_COUNT))
            pb = random.randint(1, self.PB_MAX)
        elif mode == "Trend Signal":
            whites = self._weighted_sample(self.white_trend, self.WHITE_MAX, self.WHITE_COUNT)
            pb = self._weighted_single(self.pb_trend, self.PB_MAX)
        elif mode == "Pattern Guard":
            whites, pb = self._pattern_guard_pick()
        elif mode == "Hot Numbers":
            whites = self._weighted_sample(self.white_freq, self.WHITE_MAX, self.WHITE_COUNT)
            pb = self._weighted_single(self.pb_freq, self.PB_MAX)
        elif mode == "Cold Numbers":
            whites = self._weighted_sample(self.white_freq, self.WHITE_MAX, self.WHITE_COUNT, invert=True)
            pb = self._weighted_single(self.pb_freq, self.PB_MAX, invert=True)
        elif mode == "Balanced Mix":
            hot3 = self._weighted_sample(self.white_freq, self.WHITE_MAX, 3)
            pool = [n for n in range(1, self.WHITE_MAX + 1) if n not in hot3]
            cold2 = self._weighted_from_pool(
                {n: self.white_freq.get(n, 0) for n in pool}, pool, 2, invert=True)
            whites = sorted(hot3 + cold2)
            pb = self._weighted_single(self.pb_freq, self.PB_MAX, invert=True)
        else:
            whites = sorted(random.sample(range(1, self.WHITE_MAX + 1), self.WHITE_COUNT))
            pb = random.randint(1, self.PB_MAX)
        return whites, pb

    def _pattern_guard_pick(self):
        """Avoid choices players commonly make; this affects sharing, never draw odds."""
        for _ in range(250):
            whites = sorted(random.sample(range(1, self.WHITE_MAX + 1), self.WHITE_COUNT))
            # Keep more than one number above 31, reject consecutive runs and neat 5-number patterns.
            consecutive_pairs = sum(b == a + 1 for a, b in zip(whites, whites[1:]))
            if sum(n > 31 for n in whites) >= 2 and consecutive_pairs < 2:
                return whites, random.randint(1, self.PB_MAX)
        # This should never be reached, but random remains a safe fallback.
        return sorted(random.sample(range(1, self.WHITE_MAX + 1), self.WHITE_COUNT)), random.randint(1, self.PB_MAX)

    def _ticket_price(self):
        try:
            price = float(self.price_var.get().strip().replace("$", ""))
            if price < 0:
                raise ValueError
        except ValueError:
            price = self.DEFAULT_TICKET_PRICE
            self.price_var.set(f"{price:.2f}")
        return price

    def _budget_limit(self):
        value = self.budget_var.get().strip().replace("$", "")
        if not value:
            return None
        try:
            budget = float(value)
            if budget < 0:
                raise ValueError
            return budget
        except ValueError:
            self.budget_var.set("")
            return None

    def _refresh_coach(self):
        line_count = len(self.generated_combinations)
        if not line_count:
            self.coach_var.set("Coverage coach: add distinct lines for broader combination coverage; duplicates only repeat the same shot.")
            return
        coverage_percent = (line_count / self.JACKPOT_ODDS) * 100
        effective_odds = self.JACKPOT_ODDS / line_count
        all_whites = [n for r in self.generated_results for n in r["whites"]]
        high_count = sum(n > 31 for n in all_whites)
        high_share = high_count / len(all_whites) if all_whites else 0
        self.coach_var.set(
            f"Coverage: {line_count:,} distinct line(s) • 1 in {effective_odds:,.0f} jackpot coverage "
            f"({coverage_percent:.6f}%) • {high_share:.0%} of white balls above 31")

    def _update_cost_summary(self, batch_qty):
        price = self._ticket_price()
        batch_cost = batch_qty * price
        session_cost = len(self.generated_results) * price
        unique_count = len(self.generated_combinations)
        self.batch_cost_var.set(f"THIS BATCH  ${batch_cost:,.2f}")
        self.session_cost_var.set(f"SESSION TOTAL  ${session_cost:,.2f}")
        self.coverage_var.set(f"UNIQUE LINES  {unique_count:,}")
        self._refresh_coach()

    def _show_coverage_help(self):
        messagebox.showinfo(
            "Coverage Coach",
            "Coverage means how many different six-number combinations are on your play slip.\n\n"
            "Each distinct line covers one of 292,201,338 possible jackpot combinations. "
            "For example, 10 unique lines cover 10 different combinations; two identical lines "
            "still cover only one combination.\n\n"
            "This does not predict the next draw or make a specific line luckier. It simply makes "
            "sure you can see—and avoid wasting money on—duplicate coverage."
        )

    @staticmethod
    def _validate_number_limit(proposed, maximum):
        """Allow a blank field while editing; otherwise keep only game-valid digits."""
        return not proposed or (proposed.isdigit() and len(proposed) <= 2 and int(proposed) <= maximum)

    @classmethod
    def _validate_white_number(cls, proposed):
        return cls._validate_number_limit(proposed, cls.WHITE_MAX)

    @classmethod
    def _validate_powerball_number(cls, proposed):
        return cls._validate_number_limit(proposed, cls.PB_MAX)

    @staticmethod
    def _focus_next(event):
        event.widget.tk_focusNext().focus_set()
        return "break"

    @staticmethod
    def _focus_previous(event):
        event.widget.tk_focusPrev().focus_set()
        return "break"

    def _add_manual_pick(self):
        try:
            whites = sorted(int(var.get().strip()) for var in self.manual_white_vars)
            pb = int(self.manual_pb_var.get().strip())
        except ValueError:
            messagebox.showerror("Enter six numbers", "Enter five white-ball numbers and one Powerball number.")
            return

        if (len(whites) != self.WHITE_COUNT or len(set(whites)) != self.WHITE_COUNT
                or any(number < 1 or number > self.WHITE_MAX for number in whites)):
            messagebox.showerror(
                "Check the white balls",
                "Enter five different white-ball numbers from 1 through 69."
            )
            return
        if not 1 <= pb <= self.PB_MAX:
            messagebox.showerror("Check the Powerball", "Enter a Powerball number from 1 through 26.")
            return

        combination = (*whites, pb)
        if combination in self.generated_combinations:
            messagebox.showwarning("Already on your play slip", "That exact line is already listed.")
            return

        price = self._ticket_price()
        budget = self._budget_limit()
        projected_cost = (len(self.generated_results) + 1) * price
        if budget is not None and projected_cost > budget:
            should_continue = messagebox.askyesno(
                "Budget check",
                f"Adding this line brings the play slip to ${projected_cost:,.2f}, over your "
                f"${budget:,.2f} budget.\n\nAdd it anyway?",
                icon="warning",
            )
            if not should_continue:
                self.status_var.set("Custom line not added — budget guard held the line.")
                return

        result = {"whites": whites, "pb": pb, "mode": "My Numbers",
                  "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.generated_results.append(result)
        self.generated_combinations.add(combination)
        self._render_pick(result, len(self.generated_results))
        self.result_count_var.set(f"{len(self.generated_results)} pick(s)")
        self._update_cost_summary(1)
        for var in [*self.manual_white_vars, self.manual_pb_var]:
            var.set("")
        self.status_var.set("Added your custom line to the play slip.")
        self.root.after(50, lambda: self.canvas.yview_moveto(1.0))

    # ── Generate & display ─────────────────────────────────────────────

    def _generate(self):
        mode = self.mode_var.get()
        fell_back = False
        if mode != "Pure Random" and not self.data_loaded:
            mode = "Pure Random"
            fell_back = True

        try:
            qty = max(1, min(20, int(self.qty_var.get())))
        except ValueError:
            qty = 1

        price = self._ticket_price()
        budget = self._budget_limit()
        projected_cost = (len(self.generated_results) + qty) * price
        if budget is not None and projected_cost > budget:
            overage = projected_cost - budget
            should_continue = messagebox.askyesno(
                "Budget check",
                f"This generation would bring the play slip to ${projected_cost:,.2f}, "
                f"which is ${overage:,.2f} over your ${budget:,.2f} budget.\n\n"
                "Generate anyway?",
                icon="warning",
            )
            if not should_continue:
                self.status_var.set("Generation skipped — budget guard held the line.")
                return

        generated_now = 0
        for _ in range(qty):
            # Distinct lines are the one odds-related improvement available here:
            # duplicate tickets do not widen coverage of possible combinations.
            for _attempt in range(500):
                whites, pb = self._pick_numbers(mode)
                combination = (*whites, pb)
                if combination not in self.generated_combinations:
                    break
            else:
                self.status_var.set("Could not find another unique line. Try clearing the play slip.")
                break
            result = {"whites": whites, "pb": pb, "mode": mode,
                      "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            self.generated_results.append(result)
            self.generated_combinations.add(combination)
            self._render_pick(result, len(self.generated_results))
            generated_now += 1

        self.result_count_var.set(f"{len(self.generated_results)} pick(s)")
        self._update_cost_summary(generated_now)
        if fell_back:
            self.status_var.set("Historical data still loading — used Pure Random")
        elif generated_now:
            self.status_var.set(
                f"Added {generated_now} unique line(s). Every line has the same draw odds — no crystal ball bullshit included.")
        self.root.after(50, lambda: self.canvas.yview_moveto(1.0))

    def _render_pick(self, result, index):
        row = tk.Frame(self.inner, bg=self.panel_bg)
        row.pack(pady=4, padx=8, anchor="center")

        # Pick number
        tk.Label(row, text=f"#{index}", font=("Menlo", 13, "bold"),
                 bg=self.panel_bg, fg=self.text_dim, width=4
                 ).pack(side="left", padx=(0, 10))

        # White balls
        for num in result["whites"]:
            tk.Label(row, text=f"{num:>2}", font=(self.sans, 19, "bold"),
                     bg=self.white_ball, fg="#1a1a2e", width=3,
                     padx=4, pady=3, relief="flat"
                     ).pack(side="left", padx=3)

        # Powerball
        tk.Label(row, text=f"{result['pb']:>2}", font=(self.sans, 19, "bold"),
                 bg=self.pb_red, fg="white", width=3,
                 padx=4, pady=3, relief="flat"
                 ).pack(side="left", padx=(12, 8))

        # Mode tag and per-line cost
        tk.Label(row, text=result["mode"], font=(self.sans, 12, "bold"),
                 bg=self.panel_bg, fg=self.text_dim
                 ).pack(side="left", padx=(8, 0))
        tk.Label(row, text=f"${self._ticket_price():.2f}", font=("Menlo", 12, "bold"),
                 bg=self.panel_bg, fg="#65d6ad", width=7, anchor="e"
                 ).pack(side="left", padx=(10, 0))

    # ── Save / Clear ───────────────────────────────────────────────────

    def _save_results(self):
        if not self.generated_results:
            messagebox.showinfo("Nothing to save", "Generate some picks first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"powerball_picks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if not path:
            return
        with open(path, "w") as f:
            f.write("=" * 60 + "\n")
            f.write("  POWERBALL GENERATOR — SAVED PICKS\n")
            f.write(f"  Saved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if self.draws:
                f.write(f"  Data: {len(self.draws)} draws"
                        f" ({self.draws[-1]['date']} — {self.draws[0]['date']})\n")
            price = self._ticket_price()
            f.write(f"  Price per line: ${price:,.2f}\n")
            f.write(f"  Total cost: ${len(self.generated_results) * price:,.2f}\n")
            f.write("=" * 60 + "\n\n")
            for i, r in enumerate(self.generated_results, 1):
                whites_str = "  ".join(f"{n:>2}" for n in r["whites"])
                f.write(f"  #{i:>3}   {whites_str}   PB: {r['pb']:>2}   [{r['mode']}]\n")
            f.write("\n" + "=" * 60 + "\n")
            f.write("  Every unique line has the same draw odds. Play responsibly.\n")
            f.write("=" * 60 + "\n")
        self.status_var.set(f"Saved {len(self.generated_results)} picks → {path}")

    def _print_results(self):
        if not self.generated_results:
            messagebox.showinfo("Nothing to print", "Generate or add some picks first.", parent=self.root)
            return
        price = self._ticket_price()
        rows = []
        for index, result in enumerate(self.generated_results, 1):
            whites = "  ".join(f"{number:02d}" for number in result["whites"])
            rows.append(f"<tr><td>{index}</td><td>{whites}</td>"
                        f"<td>{result['pb']:02d}</td><td>{html.escape(result['mode'])}</td></tr>")
        document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Powerball Play Slip</title>
<style>body {{ font: 14px Arial, sans-serif; color: #111; margin: 2em; }}
h1 {{ font-size: 22px; }} table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #aaa; padding: 8px; text-align: left; }}
th {{ background: #eee; }} td:nth-child(2) {{ white-space: pre; }}
@media print {{ .controls {{ display: none; }} tr {{ break-inside: avoid; }} }}</style></head>
<body><div class="controls"><button onclick="window.print()">Print / Save as PDF</button>
<p>Choose your printer or save as PDF in the print dialog.</p></div>
<h1>Powerball Play Slip</h1><p>Created: {datetime.now():%Y-%m-%d %H:%M:%S}<br>
Lines: {len(self.generated_results)} &nbsp; | &nbsp; Price per line: ${price:,.2f}
&nbsp; | &nbsp; Total: ${len(self.generated_results) * price:,.2f}</p>
<table><thead><tr><th>Line</th><th>White balls</th><th>Powerball</th><th>Mode</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p>Every unique line has the same draw odds. Play responsibly.</p>
<script>window.addEventListener('load', () => window.print());</script></body></html>"""
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html",
                                             prefix="powerball-play-slip-", delete=False) as output:
                output.write(document)
                path = Path(output.name)
            if not webbrowser.open(path.as_uri()):
                raise OSError("No web browser was available.")
        except OSError as error:
            messagebox.showerror("Could not open print preview", str(error), parent=self.root)
            return
        self.status_var.set("Print preview opened in your browser.")

    def _clear_results(self):
        self.generated_results.clear()
        self.generated_combinations.clear()
        for w in self.inner.winfo_children():
            w.destroy()
        self.result_count_var.set("")
        self._update_cost_summary(0)
        self.status_var.set("Results cleared.")

    # ── Window centering ───────────────────────────────────────────────

    def _center_window(self, w, h):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")


if __name__ == "__main__":
    root = tk.Tk()
    PowerballApp(root)
    root.mainloop()
