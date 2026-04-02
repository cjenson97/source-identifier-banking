from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from scheduled_checks import (
    OUTPUT_DIR,
    SEEN_SOURCES_FILE,
    build_domain_rollup,
    ensure_paths,
    load_config,
    load_current_source_domains,
    load_seen_sources,
    run_discovery,
    update_seen_sources,
)


class BankingComplianceDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Banking Compliance Source Finder")
        self.root.geometry("1180x720")
        self.root.minsize(980, 620)

        self.findings_df = pd.DataFrame()
        self.scan_in_progress = False
        self.last_scan_time = "Not run yet"

        ensure_paths()
        self.config = load_config()

        self._configure_styles()
        self._build_layout()

    def _configure_styles(self) -> None:
        self.root.configure(bg="#f5f9ff")
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Brand.TFrame", background="#f5f9ff")
        style.configure("Header.TFrame", background="#0e3a68")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")

        style.configure(
            "HeaderTitle.TLabel",
            background="#0e3a68",
            foreground="#ffffff",
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "HeaderSub.TLabel",
            background="#0e3a68",
            foreground="#dcecff",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Status.TLabel",
            background="#f5f9ff",
            foreground="#33597d",
            font=("Segoe UI", 10),
        )

        style.configure(
            "Run.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#ffffff",
            background="#0b5cab",
            borderwidth=0,
            padding=(14, 8),
        )
        style.map("Run.TButton", background=[("active", "#084b8a"), ("disabled", "#9bb9d8")])

        style.configure(
            "Export.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#ffffff",
            background="#00a86b",
            borderwidth=0,
            padding=(14, 8),
        )
        style.map("Export.TButton", background=[("active", "#008a58"), ("disabled", "#99d8c0")])

        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10), fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#e8f1fb", foreground="#0f172a")

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, style="Brand.TFrame", padding=12)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, style="Header.TFrame", padding=(16, 14))
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Banking Compliance Source Finder", style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Standalone desktop app: run scan, review findings, export CSV.",
            style="HeaderSub.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        action_row = ttk.Frame(container, style="Brand.TFrame")
        action_row.pack(fill="x", pady=(0, 8))

        self.run_button = ttk.Button(action_row, text="Run Now", style="Run.TButton", command=self.run_scan)
        self.run_button.pack(side="left")

        self.export_button = ttk.Button(
            action_row,
            text="Export Findings CSV",
            style="Export.TButton",
            command=self.export_csv,
            state="disabled",
        )
        self.export_button.pack(side="left", padx=(10, 0))

        self.notify_var = tk.BooleanVar(value=True)
        notify_checkbox = ttk.Checkbutton(
            action_row,
            text="Notify when scan completes",
            variable=self.notify_var,
        )
        notify_checkbox.pack(side="left", padx=(16, 0))

        self.status_var = tk.StringVar(value="Ready")
        self.scan_var = tk.StringVar(value="Last scan: Not run yet")

        ttk.Label(container, textvariable=self.status_var, style="Status.TLabel").pack(anchor="w")
        ttk.Label(container, textvariable=self.scan_var, style="Status.TLabel").pack(anchor="w", pady=(0, 8))

        table_card = ttk.Frame(container, style="Card.TFrame", padding=8)
        table_card.pack(fill="both", expand=True)

        columns = [
            "Source Domain",
            "Source Type",
            "Relevance",
            "Recent Mentions",
            "Last Seen",
            "Example Headline",
        ]

        self.tree = ttk.Treeview(table_card, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)

        self.tree.column("Source Domain", width=200, anchor="w")
        self.tree.column("Source Type", width=130, anchor="center")
        self.tree.column("Relevance", width=110, anchor="center")
        self.tree.column("Recent Mentions", width=120, anchor="center")
        self.tree.column("Last Seen", width=120, anchor="center")
        self.tree.column("Example Headline", width=460, anchor="w")

        yscroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

    def run_scan(self) -> None:
        if self.scan_in_progress:
            return

        self.scan_in_progress = True
        self.run_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.status_var.set("Running discovery scan. This can take a minute...")

        thread = threading.Thread(target=self._scan_worker, daemon=True)
        thread.start()

    def _scan_worker(self) -> None:
        try:
            findings = self._discover_findings()
            self.root.after(0, lambda: self._on_scan_success(findings))
        except Exception as exc:  # noqa: BLE001
            self.root.after(0, lambda: self._on_scan_error(str(exc)))

    def _discover_findings(self) -> pd.DataFrame:
        config = load_config()
        seen_sources = load_seen_sources()
        baseline_domains = load_current_source_domains()

        if seen_sources.empty and baseline_domains:
            seeded = update_seen_sources(seen_sources, baseline_domains)
            seeded.to_csv(SEEN_SOURCES_FILE, index=False)
            seen_sources = seeded

        seen_domains = set(seen_sources["domain"].astype(str).tolist())
        known_domains = seen_domains.union(baseline_domains)

        discovery_df = run_discovery(config)
        rollup = build_domain_rollup(discovery_df, known_domains, config)

        new_sources = rollup[rollup["is_new_source"]].copy()
        candidates = new_sources[
            (new_sources["max_relevance"] >= int(config.get("min_relevance_score", 2)))
            & (new_sources["article_count"] >= int(config.get("min_articles_per_domain", 1)))
        ].copy()

        candidates = candidates.sort_values(
            by=["priority_score", "max_relevance", "article_count", "latest_seen_date"],
            ascending=[False, False, False, False],
        )

        if not candidates.empty:
            updated_seen = update_seen_sources(seen_sources, candidates["domain"].tolist())
            updated_seen.to_csv(SEEN_SOURCES_FILE, index=False)

        display_df = self._format_findings(candidates)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        display_df.to_csv(OUTPUT_DIR / "latest_findings_table.csv", index=False)

        return display_df

    def _format_findings(self, candidates: pd.DataFrame) -> pd.DataFrame:
        if candidates.empty:
            return pd.DataFrame(
                columns=[
                    "Source Domain",
                    "Source Type",
                    "Relevance",
                    "Recent Mentions",
                    "Last Seen",
                    "Example Headline",
                ]
            )

        formatted = candidates.copy()

        def band(score: float) -> str:
            if score >= 4:
                return "Very Strong"
            if score >= 3:
                return "Strong"
            if score >= 2:
                return "Moderate"
            return "Early Signal"

        formatted["Last Seen"] = pd.to_datetime(formatted["latest_seen_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        formatted["Relevance"] = formatted["max_relevance"].astype(float).apply(band)

        return formatted[
            ["domain", "source_type", "Relevance", "article_count", "Last Seen", "sample_title"]
        ].rename(
            columns={
                "domain": "Source Domain",
                "source_type": "Source Type",
                "article_count": "Recent Mentions",
                "sample_title": "Example Headline",
            }
        )

    def _on_scan_success(self, findings: pd.DataFrame) -> None:
        self.scan_in_progress = False
        self.findings_df = findings

        self._populate_table(findings)

        self.last_scan_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.status_var.set(f"Scan complete. {len(findings)} findings ready.")
        self.scan_var.set(f"Last scan: {self.last_scan_time}")

        self.run_button.configure(state="normal")
        self.export_button.configure(state="normal")

        if self.notify_var.get():
            self.root.bell()
            messagebox.showinfo("Scan Completed", "Scan is complete. You can now export the findings CSV.")

    def _on_scan_error(self, error: str) -> None:
        self.scan_in_progress = False
        self.run_button.configure(state="normal")
        self.status_var.set("Scan failed. Please retry.")
        messagebox.showerror("Scan Failed", error)

    def _populate_table(self, findings: pd.DataFrame) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        if findings.empty:
            self.tree.insert("", "end", values=("No new findings", "-", "-", "-", "-", "-"))
            return

        for _, row in findings.iterrows():
            self.tree.insert(
                "",
                "end",
                values=(
                    row.get("Source Domain", ""),
                    row.get("Source Type", ""),
                    row.get("Relevance", ""),
                    row.get("Recent Mentions", ""),
                    row.get("Last Seen", ""),
                    row.get("Example Headline", ""),
                ),
            )

    def export_csv(self) -> None:
        if self.findings_df.empty:
            messagebox.showwarning("No Data", "Run a scan before exporting CSV.")
            return

        default_name = f"banking_compliance_findings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = filedialog.asksaveasfilename(
            title="Export Findings CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not file_path:
            return

        self.findings_df.to_csv(Path(file_path), index=False)
        messagebox.showinfo("Export Complete", f"Findings exported to:\n{file_path}")


def main() -> None:
    root = tk.Tk()
    app = BankingComplianceDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
