import json
import os
import datetime
import difflib
import pandas as pd
import re

class ClanManager:
    def __init__(self):
        self.snapshot_file = "clan_snapshot.json"
        self.mappings_file = "player_mappings.json"
        self.ignore_file = "ignored_players.json"
        self.roster_log = "roster_log.csv"
        self.roster_debug = "roster_debug.csv"
        self.chest_log = "chest_log.csv"
        
        self.load_mappings()
        self.load_snapshot()
        self.load_ignored()

    def load_mappings(self):
        if os.path.exists(self.mappings_file):
            try:
                with open(self.mappings_file, 'r') as f: self.mappings = json.load(f)
            except: self.mappings = {}
        else: self.mappings = {}

    def save_mappings(self):
        with open(self.mappings_file, 'w') as f: json.dump(self.mappings, f, indent=4)

    def load_snapshot(self):
        if os.path.exists(self.snapshot_file):
            try:
                with open(self.snapshot_file, 'r') as f: self.snapshot = json.load(f)
            except: self.snapshot = {}
        else: self.snapshot = {}

    def save_snapshot(self):
        with open(self.snapshot_file, 'w') as f: json.dump(self.snapshot, f, indent=4)
        
    def load_ignored(self):
        if os.path.exists(self.ignore_file):
            try:
                with open(self.ignore_file, 'r') as f: self.ignored = set(json.load(f))
            except: self.ignored = set()
        else: self.ignored = set()

    def save_ignored(self):
        with open(self.ignore_file, 'w') as f: json.dump(list(self.ignored), f, indent=4)

    # --- LIST BUILDERS ---
    def get_unmatched_chest_players(self, days_lookback=14):
        """ Returns names in Chest Log that are NOT in Snapshot/Mappings/Ignore. """
        unmatched = set()
        if os.path.exists(self.chest_log):
            try:
                df = pd.read_csv(self.chest_log)
                df['dt'] = pd.to_datetime(df['Timestamp'], dayfirst=True, errors='coerce')
                cutoff = datetime.datetime.now() - datetime.timedelta(days=days_lookback)
                recent = df[df['dt'] >= cutoff]
                for raw_name in recent['Player Name'].dropna().unique():
                    clean = str(raw_name).strip()
                    if (clean not in self.mappings and 
                        clean not in self.snapshot and 
                        clean not in self.ignored):
                        unmatched.add(clean)
            except: pass
        return sorted(list(unmatched))
        
    def get_debug_roster_names(self):
        """ Returns names found in the Strict-Mode-OFF debug scan. """
        names = set()
        if os.path.exists(self.roster_debug):
            try:
                df = pd.read_csv(self.roster_debug)
                # Just get the last batch of scans (approx 200 rows)
                recent = df.tail(200)
                for n in recent['Player Name'].dropna().unique():
                    names.add(str(n).strip())
            except: pass
        return sorted(list(names))

    # --- ACTIONS ---
    def action_confirm_name_change(self, old_name, new_name):
        self.mappings[old_name] = new_name
        if old_name in self.snapshot:
            data = self.snapshot.pop(old_name)
            self.snapshot[new_name] = data
            self.snapshot[new_name]['last_seen'] = datetime.date.today().isoformat()
        else:
            self.snapshot[new_name] = {"might": 0, "last_seen": datetime.date.today().isoformat(), "missing_count": 0}
        self.save_mappings()
        self.save_snapshot()

    def action_merge(self, alias_name, target_name):
        self.mappings[alias_name] = target_name
        if alias_name in self.snapshot: del self.snapshot[alias_name]
        self.save_mappings()
        self.save_snapshot()

    def action_ignore_player(self, name):
        """ Adds player to global ignore list. """
        self.ignored.add(name)
        if name in self.snapshot: del self.snapshot[name]
        self.save_ignored()
        self.save_snapshot()

    def run_analysis(self, days_lookback=1):
        # ... (Existing logic for alerts, keep as is) ...
        # (Copied from previous answer for completeness)
        if not os.path.exists(self.roster_log): return [{"type": "INFO", "msg": "No roster log found."}]
        try:
            df = pd.read_csv(self.roster_log)
            df['dt'] = pd.to_datetime(df['Scan Date'], dayfirst=True, errors='coerce')
            now = datetime.datetime.now()
            cutoff = now - datetime.timedelta(days=days_lookback)
            recent_df = df[df['dt'] >= cutoff]
            if recent_df.empty: return []

            current_roster = {}
            for _, row in recent_df.iterrows():
                raw_name = str(row['Player Name']).strip()
                if raw_name in self.mappings or raw_name in self.ignored: continue 
                try: might = int(str(row['Might']).replace(',', '').replace('.', ''))
                except: might = 0
                if raw_name not in current_roster or might > current_roster[raw_name]:
                    current_roster[raw_name] = might
        except: return []

        alerts = []
        today_str = datetime.date.today().isoformat()
        
        # 2. Check New Names
        for new_name, new_might in current_roster.items():
            if new_name not in self.snapshot and new_name not in self.mappings:
                # Auto-add new members to snapshot
                self.snapshot[new_name] = {"might": new_might, "last_seen": today_str, "missing_count": 0}
                alerts.append({"type": "NEW_MEMBER", "name": new_name, "desc": f"Added: {new_name}"})

        self.save_snapshot()
        return alerts