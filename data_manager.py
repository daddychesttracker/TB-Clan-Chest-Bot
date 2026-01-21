import csv
import os
import datetime
import re

class DataManager:
    def __init__(self):
        self.chest_log = "chest_log.csv"
        self.roster_file = "roster_log.csv"
        self.roster_debug_file = "roster_debug.csv" # NEW
        self.event_file = "event_log.csv"
        self.ensure_files()
        self.strict_mode = True 

    def ensure_files(self):
        # ... standard init ...
        if not os.path.exists(self.chest_log):
            try:
                with open(self.chest_log, 'w', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(["Timestamp", "Player Name", "Chest Name", "Chest Source", "Raw Text"])
            except: pass
        
        if not os.path.exists(self.roster_file):
            try:
                with open(self.roster_file, 'w', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(["Scan Date", "Player Name", "Might"])
            except: pass
        
        # Ensure Debug File exists
        if not os.path.exists(self.roster_debug_file):
            try:
                with open(self.roster_debug_file, 'w', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(["Scan Date", "Player Name", "Might"])
            except: pass

    # ... (parse_and_save, clean_name_roster, clean_name_event, extract_roster_data REMAIN THE SAME as previous answer) ...
    # PASTE THOSE METHODS HERE OR USE PREVIOUS FILE CONTENT FOR THEM
    
    def parse_and_save(self, raw_text):
        if not raw_text or len(raw_text.strip()) < 5: return None
        clean_text = raw_text.replace('\n', ' ').strip()
        match = re.search(r'^(.*?)\s+From:\s+(.*?)\s+Source:\s+(.*)$', clean_text, re.IGNORECASE)
        if match:
            chest_name = match.group(1).strip()
            player_name = match.group(2).strip()
            chest_source = match.group(3).strip()
        else:
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            chest_name = lines[0] if lines else "Unknown"
            player_name = "Unknown"
            chest_source = "Unknown"
            for line in lines:
                if "From:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1: player_name = parts[1].strip()
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        try:
            with open(self.chest_log, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([timestamp, player_name, chest_name, chest_source, raw_text])
        except: pass
        return f"{player_name} -> {chest_name}"

    def clean_name_roster(self, raw_name):
        coord_match = re.search(r'(?:K|X|Y|Kingdom)[.:;iI\s-]*[oO\d]{1,5}', raw_name, re.IGNORECASE)
        if coord_match: raw_name = raw_name[:coord_match.start()]
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', raw_name).strip()
        if not self.strict_mode: return clean.strip()
        while True:
            match = re.search(r'\s+([a-zA-Z0-9]+)$', clean)
            if not match: break
            last_word = match.group(1)
            digits = sum(c.isdigit() for c in last_word)
            letters = sum(c.isalpha() for c in last_word)
            is_garbage = False
            if digits > 0:
                if digits >= letters: is_garbage = True
                elif re.match(r'^\d', last_word): is_garbage = True
                elif re.search(r'\d+[oOliI]', last_word) or re.search(r'[oOliI]\d+', last_word):
                    is_garbage = True
            if is_garbage: clean = clean[:match.start()].strip()
            else: break
        return clean.strip()

    def clean_name_event(self, raw_name):
        clean = re.sub(r'^\d{1,3}[.\s]+', '', raw_name)
        clean = re.sub(r'\bK\s*[:.\s]?\s*[0-9oOzZlIsS]{1,5}\b', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\b(?:K|X|Y)\s*[:.]?\s*\d{1,4}\b', '', clean, flags=re.IGNORECASE)
        match_score = re.search(r'(\d[\d,.]*)$', clean)
        if match_score:
            score_str = match_score.group(1)
            if sum(c.isdigit() for c in score_str) >= 3: clean = clean[:match_score.start()]
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', clean).strip()
        if not self.strict_mode: return clean.strip()
        clean = re.sub(r'\s\d{1,2}$', '', clean)
        return clean.strip()

    def extract_roster_data(self, raw_text):
        if not raw_text or len(raw_text) < 5: return None
        line = raw_text.replace('\n', ' ').strip()
        potential_numbers = re.findall(r'[\d][\d,.\s]*', line)
        valid_mights = []
        for num_str in potential_numbers:
            digit_count = sum(c.isdigit() for c in num_str)
            if digit_count >= 5: 
                clean_num = re.sub(r'[^\d]', '', num_str)
                formatted = "{:,}".format(int(clean_num))
                valid_mights.append((formatted, num_str))
        might_str_in_text = ""
        if valid_mights: might, might_str_in_text = max(valid_mights, key=lambda x: len(re.sub(r'[^\d]', '', x[0])))
        else: might = "0"
        if might_str_in_text and might_str_in_text in line: name_part = line.split(might_str_in_text)[0]
        else: name_part = line 
        final_name = self.clean_name_roster(name_part)
        if len(final_name) < 2: return None
        return {"name": final_name, "number": might}

    def append_roster_row(self, name, might):
        date_str = datetime.datetime.now().strftime("%d/%m/%Y")
        
        # --- NEW LOGIC: Route to correct file ---
        target_file = self.roster_file if self.strict_mode else self.roster_debug_file
        # ----------------------------------------
        
        try:
            with open(target_file, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([date_str, name, might])
            return True
        except: return False

    # ... (rest of file: initialize_event_file, append_event_row, parse_event_split) ...
    def initialize_event_file(self, event_name):
        filename = f"event_{re.sub(r'[^a-zA-Z0-9]', '_', event_name)}.csv"
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(["Scan Date", "Player Name", "Score"])
            return True
        except: return False

    def append_event_row(self, event_name, name, score):
        filename = f"event_{re.sub(r'[^a-zA-Z0-9]', '_', event_name)}.csv"
        date_str = datetime.datetime.now().strftime("%d/%m/%Y")
        try:
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([date_str, name, score])
            return True
        except: return False

    def parse_event_split(self, name_text, score_text):
        clean_s = re.sub(r'[^\d]', '', score_text)
        fmt_s = "{:,}".format(int(clean_s)) if clean_s else "0"
        raw = name_text.replace('\n', ' ').strip()
        final_name = self.clean_name_event(raw)
        if len(final_name) < 2: return None
        return {"name": final_name, "score": fmt_s}