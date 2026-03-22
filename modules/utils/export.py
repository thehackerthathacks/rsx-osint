"""modules/utils/export.py — Save results to JSON, CSV, TXT"""

import os
import json
import csv
from datetime import datetime
from typing import List, Dict


class Exporter:
    def __init__(self, cfg: dict, query: str, qtype: str):
        self._cfg    = cfg
        self._query  = query
        self._qtype  = qtype
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in query)[:40]
        self.outdir = os.path.join(cfg.get("output_dir", "output/results"),
                                   f"{qtype}_{safe}_{ts}")
        if cfg.get("save_results", True):
            os.makedirs(self.outdir, exist_ok=True)

    def save(self, results: List[Dict]):
        if not self._cfg.get("save_results", True) or not results:
            return
        fmts = self._cfg.get("output_formats", ["json", "csv", "txt"])
        base = os.path.join(self.outdir, "results")
        if "json" in fmts:
            self._save_json(results, base + ".json")
        if "csv" in fmts:
            self._save_csv(results, base + ".csv")
        if "txt" in fmts:
            self._save_txt(results, base + ".txt")

    def _save_json(self, results, path):
        payload = {
            "query":     self._query,
            "type":      self._qtype,
            "scan_date": datetime.now().isoformat(),
            "total":     len(results),
            "results":   results,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _save_csv(self, results, path):
        if not results:
            return
        all_extra_keys = set()
        for r in results:
            all_extra_keys.update(r.get("extra", {}).keys())
        fieldnames = ["index","source","type","query","data"] + sorted(all_extra_keys)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in results:
                row = {k: r.get(k,"") for k in ["index","source","type","query","data"]}
                for k in all_extra_keys:
                    row[k] = r.get("extra", {}).get(k, "")
                w.writerow(row)

    def _save_txt(self, results, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("RSX-OSINT  —  Scan Report\n")
            f.write("=" * 60 + "\n")
            f.write(f"Query   : {self._query}\n")
            f.write(f"Type    : {self._qtype}\n")
            f.write(f"Date    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total   : {len(results)} results\n")
            f.write("=" * 60 + "\n\n")
            for r in results:
                f.write(f"[#{r['index']}]  {r['source'].upper()}\n")
                f.write(f"  Data    : {r['data']}\n")
                for k, v in r.get("extra", {}).items():
                    if v:
                        f.write(f"  {k.capitalize():<16}: {v}\n")
                f.write("-" * 50 + "\n")
