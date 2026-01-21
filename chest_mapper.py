import json
import os
import csv

class ChestMapper:
    def __init__(self):
        self.mapping_file = "chest_mappings.json"
        self.log_file = "chest_log.csv"
        self.mappings = self.load_mappings()

    def load_mappings(self):
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, 'r') as f: return json.load(f)
            except: pass
        return {}

    def save_mappings(self):
        with open(self.mapping_file, 'w') as f:
            json.dump(self.mappings, f, indent=4)

    def get_unique_chests_from_log(self):
        """
        Logic:
        - If 'bank' is in the Source: Return "Name | Source" (e.g. "Wooden Chest | Bank")
        - Otherwise: Return Source Only (e.g. "Level 20 Crypt")
        """
        if not os.path.exists(self.log_file): return []
        
        unique_items = set()
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # Skip header
                for row in reader:
                    if len(row) >= 4:
                        # Row 2 = Name, Row 3 = Source
                        c_name = row[2].strip()
                        c_source = row[3].strip()
                        
                        if not c_source: continue

                        # --- THE NEW LOGIC ---
                        if "bank" in c_source.lower():
                            # Include Name for Bank items
                            unique_items.add(f"{c_name} | {c_source}")
                        else:
                            # Source only for everything else
                            unique_items.add(c_source)
                            
        except Exception as e:
            print(f"Error reading log: {e}")
            
        return sorted(list(unique_items))

    def add_mapping(self, identifier, template_key, points):
        self.mappings[identifier] = {
            "key": template_key,
            "points": points
        }
        self.save_mappings()

    def remove_mapping(self, identifier):
        if identifier in self.mappings:
            del self.mappings[identifier]
            self.save_mappings()