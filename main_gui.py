import customtkinter as ctk
import threading
import time
import datetime
import os
import cv2
import pyautogui
import numpy as np
import json
import keyboard
import re
import urllib.request 
from PIL import Image
import easyocr

from data_manager import DataManager
from master_compiler import MasterCompiler
from chest_mapper import ChestMapper
from clan_manager import ClanManager 

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "vision_config.json"

class TotalBattleBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("v1.0 Total Battle Clan Manager")
        self.geometry("1300x950")
        self.attributes('-topmost', True)

        self.data_manager = DataManager()
        self.clan_manager = ClanManager() 
        
        print("⚡ Loading EasyOCR Model...")
        self.reader = easyocr.Reader(['en'], gpu=False)
        print("✅ EasyOCR Ready.")

        self.settings = {
            "mode": "chests",
            "min_score": 1000,
            "discord_webhook": "",
            "chests": {"off_x": 600, "off_y": 10, "w": 550, "h": 100, "thresh": 150, "bw": False},
            "roster": {"off_x": 50, "off_y": -10, "w": 800, "h": 40, "thresh": 150, "bw": False, "margin_top": 200, "margin_bot": 800},
            "events": {
                "off_x": 50, "off_y": -10, "w": 800, "h": 40, 
                "thresh": 150, "bw": False, 
                "margin_top": 200, "margin_bot": 800,
                "split_x": 500
            },
            "accounts": { 
                "drag_start_x": 0,
                "drag_start_y": 450,
                "drag_end_y": 150,
                "drag_speed": 0.8,
                "scroll_attempts": 15
            },
            "event_thresholds": {}
        }
        self.load_settings()
        
        self.is_running = False        
        self.is_auto_active = False    
        self.stop_requested = False    
        
        self.captured_image = None 
        self.seen_player_names = set() 
        self.seen_player_numbers = set()
        self.selected_event = ctk.StringVar(value="None")
        
        self.event_list = [
            "Rise of the Ancients", "Ragnarok", "Olympus", 
            "Dark Omens - Remnants", "Dark Omens - Essence", "Other"
        ]

        self.next_gift_run = None
        self.next_roster_run = None
        self.next_excel_run = None

        keyboard.add_hotkey('f9', self.start_bot_safe)
        keyboard.add_hotkey('f10', self.stop_bot_safe)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        self.tab_dash = self.tabview.add("🤖 Dashboard")
        self.tab_auto = self.tabview.add("⚙️ Automation")
        self.tab_events = self.tabview.add("🏆 Event Manager")
        self.tab_clan = self.tabview.add("🛡️ Clan Mgmt") 
        self.tab_manager = self.tabview.add("🗃️ Chest Manager")
        self.tab_calib = self.tabview.add("📏 Calibration")

        self.setup_dashboard()
        self.setup_automation()
        self.setup_event_manager()
        self.setup_clan_manager() 
        self.setup_chest_manager()
        self.setup_calibration()

        threading.Thread(target=self.scheduler_loop, daemon=True).start()

    def send_discord_msg(self, message):
        url = self.settings.get("discord_webhook", "").strip()
        if not url: return
        try:
            payload = {"content": message}
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
            urllib.request.urlopen(req)
        except Exception as e: print(f"Discord Error: {e}")

    # =====================================================
    # ROBUSTNESS & NAVIGATION
    # =====================================================
    
    def check_connection_loss(self):
        try:
            if pyautogui.locateOnScreen("assets/connection_lost_check.png", confidence=0.8):
                self.log("⚠️ Connection Lost detected!")
                retry_btn = pyautogui.locateOnScreen("assets/connect_retry_btn.png", confidence=0.8)
                if retry_btn:
                    self.log("🔄 Clicking Retry...")
                    pyautogui.click(pyautogui.center(retry_btn))
                    time.sleep(10)
                    return True
        except: pass
        return False

    def handle_interruptions(self):
        if self.check_connection_loss(): time.sleep(2)
        try:
            while pyautogui.locateOnScreen("assets/check_loading1.png", confidence=0.8):
                self.log("⏳ Waiting for Loading 1...")
                time.sleep(1)
        except: pass
        try:
            while pyautogui.locateOnScreen("assets/check_loading2.png", confidence=0.8):
                self.log("⏳ Waiting for Loading 2...")
                time.sleep(1)
        except: pass
        try:
            if pyautogui.locateOnScreen("assets/check_shop_btn.png", confidence=0.8):
                self.log("🛍️ Shop detected. Closing in 3s...")
                time.sleep(3)
                close_btn = pyautogui.locateOnScreen("assets/close_shop_btn.png", confidence=0.8)
                if close_btn:
                    target = pyautogui.center(close_btn)
                    pyautogui.moveTo(target.x, target.y, duration=0.5)
                    pyautogui.click()
                    self.log("✅ Shop Closed.")
                    time.sleep(1)
        except: pass

    def verify_profile(self):
        """Checks profile and switches account using BLIND DRAG with CALIBRATION."""
        self.log("🔍 Verifying Profile...")
        
        # 1. Is the correct profile already active?
        try:
            if pyautogui.locateOnScreen("assets/check_profile.png", confidence=0.8):
                return True
        except: pass

        # 2. Is the game loaded?
        try:
            if not pyautogui.locateOnScreen("assets/btn_clan.png", confidence=0.8):
                self.log("❌ Game UI not found (btn_clan missing).")
                return False
        except: return False

        # 3. Wrong Profile Detected - Initiate Switch
        self.log("⚠️ Wrong Profile! Attempting to switch...")
        
        # Load custom calibration for drag
        s_acc = self.settings.get("accounts", {"drag_start_y": 450, "drag_end_y": 150, "drag_speed": 0.8, "scroll_attempts": 15})
        drag_x_offset = s_acc.get("drag_start_x", 0)
        drag_start_offset = s_acc.get("drag_start_y", 450)
        drag_end_offset = s_acc.get("drag_end_y", 150)
        drag_speed = s_acc.get("drag_speed", 0.8)
        max_attempts = int(s_acc.get("scroll_attempts", 15))

        try:
            # A. Click Account Button
            acc_btn = pyautogui.locateOnScreen("assets/acc_btn.png", confidence=0.8)
            if acc_btn:
                pyautogui.click(pyautogui.center(acc_btn))
                # MOVE MOUSE AWAY to prevent hover effect from blocking image match
                pyautogui.moveTo(10, 10) 
                self.log("🖱️ Clicked Account Button. Waiting 3s...")
                time.sleep(3.0)
            else:
                self.log("❌ Cannot find Account Button.")
                return False

            # B. Find Anchor (Header) - Retry Loop
            anchor_pos = None
            for _ in range(5): # Try 5 times
                acc_anchor = pyautogui.locateOnScreen("assets/acc_anchor.png", confidence=0.8)
                if acc_anchor:
                    anchor_pos = pyautogui.center(acc_anchor)
                    break
                time.sleep(0.5)
            
            # C. Fallback if Anchor Missing (Use Button Position)
            if not anchor_pos:
                self.log("⚠️ Anchor missing! Using Fallback.")
                # Fallback: Assume list is 200px below the button we just clicked
                if acc_btn:
                    btn_pos = pyautogui.center(acc_btn)
                    anchor_pos = pyautogui.Point(btn_pos.x, btn_pos.y + 200)
                else:
                    self.log("❌ Critical: No reference point found.")
                    return False
            
            # Use Calibrated Offsets relative to whatever anchor we found
            drag_x = anchor_pos.x + drag_x_offset
            drag_start_y = anchor_pos.y + drag_start_offset
            drag_end_y = anchor_pos.y + drag_end_offset
            
            found_target = False
            self.log(f"📜 Scanning Profile (X:{drag_x_offset} | Y:{drag_start_offset}->{drag_end_offset})...")
            
            for i in range(max_attempts): 
                target = pyautogui.locateOnScreen("assets/tbprofile_id.png", confidence=0.8)
                if target:
                    self.log("✅ Target Profile Found! Clicking...")
                    pyautogui.click(pyautogui.center(target))
                    found_target = True
                    break
                
                # Perform Blind Drag
                self.log(f"   ⬇️ Dragging List ({i+1}/{max_attempts})...")
                pyautogui.moveTo(drag_x, drag_start_y)
                pyautogui.mouseDown()
                time.sleep(0.2)
                pyautogui.moveTo(drag_x, drag_end_y, duration=drag_speed) # Pull up
                pyautogui.mouseUp()
                time.sleep(1.5) # Wait for animation

            if found_target:
                self.log("⏳ Waiting 60s for game reload...")
                time.sleep(60)
                return self.verify_profile()
            else:
                self.log("❌ Could not find 'tbprofile_id' in list.")
                self.send_discord_msg("🚨 **Error**: Could not find Target Profile.")
                return False

        except Exception as e:
            self.log(f"❌ Profile Switch Error: {e}")
            return False

    # =====================================================
    # UI SETUP
    # =====================================================
    def setup_dashboard(self):
        self.tab_dash.grid_columnconfigure(1, weight=1)
        self.tab_dash.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self.tab_dash, width=250, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(sidebar, text="TB CLAN MANAGER", font=("Arial", 20, "bold")).pack(pady=20)
        self.btn_start = ctk.CTkButton(sidebar, text="START (F9)", fg_color="green", command=self.start_bot)
        self.btn_start.pack(pady=10, padx=20)
        self.btn_stop = ctk.CTkButton(sidebar, text="STOP (F10)", fg_color="red", state="disabled", command=self.stop_bot)
        self.btn_stop.pack(pady=10, padx=20)
        ctk.CTkLabel(sidebar, text="Select Task:").pack(pady=(20,0))
        self.task_menu = ctk.CTkOptionMenu(sidebar, values=["Gift Muncher", "Roster Scan", "Event Scanner"])
        self.task_menu.pack(pady=5)
        ctk.CTkLabel(sidebar, text="Select Event Tag:").pack(pady=(20,0))
        self.event_menu = ctk.CTkOptionMenu(sidebar, values=["None"] + self.event_list, variable=self.selected_event)
        self.event_menu.pack(pady=5)
        def run_master_update_manual():
            if self.is_running or self.is_auto_active:
                self.log("⚠️ Bot is busy.")
                return
            self.run_excel_logic()
        self.btn_master = ctk.CTkButton(sidebar, text="📊 UPDATE MASTER EXCEL", fg_color="purple", command=run_master_update_manual)
        self.btn_master.pack(pady=20, padx=20)
        self.log_box = ctk.CTkTextbox(self.tab_dash, width=500)
        self.log_box.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def setup_clan_manager(self):
        # Configure Grid: 3 Main Sections
        self.tab_clan.grid_columnconfigure(0, weight=1)
        self.tab_clan.grid_rowconfigure(1, weight=1) # Alerts (Small)
        self.tab_clan.grid_rowconfigure(2, weight=3) # Verified Roster (Large)
        self.tab_clan.grid_rowconfigure(3, weight=2) # Unmatched (Medium)

        # --- HEADER & CONTROLS ---
        top_frame = ctk.CTkFrame(self.tab_clan)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkLabel(top_frame, text="🛡️ Clan Management", font=("Arial", 18, "bold")).pack(side="left", padx=10)
        
        # Strict Filter Toggle
        self.var_strict_filter = ctk.BooleanVar(value=True)
        def toggle_strict():
            self.data_manager.strict_mode = self.var_strict_filter.get()
            status = "ON" if self.var_strict_filter.get() else "OFF (Debug Mode)"
            self.log(f"🔧 Strict Name Filter: {status}")
            # Refresh lists to show/hide debug names immediately
            self.refresh_roster_list()
        
        cb_strict = ctk.CTkCheckBox(top_frame, text="Strict Name Filter (Uncheck to fix typos)", 
                                  variable=self.var_strict_filter, command=toggle_strict)
        cb_strict.pack(side="right", padx=10)

        # --- SECTION 1: AUTOMATED ALERTS ---
        f_alerts = ctk.CTkFrame(self.tab_clan)
        f_alerts.grid(row=1, column=0, sticky="nsew", padx=10, pady=2)
        
        head_alert = ctk.CTkFrame(f_alerts, fg_color="transparent")
        head_alert.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(head_alert, text="⚠️ Automated Checks (Leavers / Name Changes)", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkButton(head_alert, text="▶️ Run Checks", height=20, width=100, command=self.run_clan_analysis_manual).pack(side="right")

        self.scroll_alerts = ctk.CTkScrollableFrame(f_alerts, height=80) 
        self.scroll_alerts.pack(expand=True, fill="both", padx=5, pady=2)

        # --- SECTION 2: VERIFIED ROSTER ---
        ctk.CTkLabel(self.tab_clan, text="✅ Verified Roster (In Snapshot)", font=("Arial", 12, "bold")).grid(row=2, column=0, sticky="nw", padx=20, pady=(5,0))
        self.scroll_roster = ctk.CTkScrollableFrame(self.tab_clan)
        self.scroll_roster.grid(row=2, column=0, sticky="nsew", padx=10, pady=(25, 5))

        # --- SECTION 3: UNMATCHED NAMES ---
        mid_frame = ctk.CTkFrame(self.tab_clan, fg_color="transparent")
        mid_frame.grid(row=3, column=0, sticky="nw", padx=10, pady=0)
        ctk.CTkLabel(mid_frame, text="❓ Unmatched Names (Chest Log / Debug)", font=("Arial", 12, "bold")).pack(side="left", padx=10)
        ctk.CTkButton(mid_frame, text="🔄 Refresh Lists", height=20, width=100, command=self.refresh_roster_list).pack(side="right")

        self.scroll_unmatched = ctk.CTkScrollableFrame(self.tab_clan)
        self.scroll_unmatched.grid(row=3, column=0, sticky="nsew", padx=10, pady=(30, 5))

        # Initial Load
        self.refresh_roster_list()

    def run_clan_analysis_manual(self):
        # 1. Clear Alerts Box
        for w in self.scroll_alerts.winfo_children(): w.destroy()
        
        # 2. Run Analysis Logic
        alerts = self.clan_manager.run_analysis(days_lookback=1)
        
        if not alerts:
            ctk.CTkLabel(self.scroll_alerts, text="✅ No alerts found. Roster looks stable.").pack(pady=5)
        else:
            for alert in alerts:
                self.create_alert_card(alert)
        
        # 3. Refresh lists in case analysis auto-added people
        self.refresh_roster_list()

    def create_alert_card(self, alert):
        card = ctk.CTkFrame(self.scroll_alerts)
        card.pack(fill="x", pady=2)
        
        atype = alert.get('type', 'INFO')
        color = "orange"
        if atype == "LEAVER": color = "red"
        elif atype == "NEW_MEMBER": color = "green"
        
        ctk.CTkLabel(card, text=f"[{atype}] {alert.get('name', '?')}", text_color=color, font=("Arial", 11, "bold")).pack(side="left", padx=5)
        ctk.CTkLabel(card, text=alert.get('desc', ''), font=("Arial", 11)).pack(side="left", padx=5)

        # Quick Action Buttons inside the alert
        if atype == "LEAVER":
            def confirm_leaver():
                self.clan_manager.action_remove_leaver(alert['name'])
                self.run_clan_analysis_manual() # Refresh
            ctk.CTkButton(card, text="Remove", fg_color="red", width=60, height=20, command=confirm_leaver).pack(side="right", padx=5)

    def refresh_roster_list(self):
        # 1. Clear Both Lists
        for w in self.scroll_roster.winfo_children(): w.destroy()
        for w in self.scroll_unmatched.winfo_children(): w.destroy()
        
        # 2. Populate Verified Roster (Top List)
        snapshot = self.clan_manager.snapshot
        sorted_names = sorted(snapshot.keys(), key=lambda x: x.lower())
        for name in sorted_names:
            self.create_roster_row(self.scroll_roster, name, snapshot[name], is_verified=True)

        # 3. Populate Unmatched List (Bottom List)
        # Get names from Chest Log + Debug Log
        unmatched_chests = self.clan_manager.get_unmatched_chest_players()
        debug_roster = self.clan_manager.get_debug_roster_names()
        
        # Combine and remove anyone who is already verified
        combined = set(unmatched_chests)
        if not self.var_strict_filter.get(): # If filter OFF, show debug names
            combined.update(debug_roster)
            
        final_unmatched = sorted([n for n in combined if n not in snapshot and n not in self.clan_manager.mappings])
        
        for name in final_unmatched:
            # We don't have might data for chest-only players, so show "?"
            self.create_roster_row(self.scroll_unmatched, name, {"might": "?"}, is_verified=False)

    def create_roster_row(self, parent, name, data, is_verified):
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", pady=2)
        
        # Name Label
        lbl_name = ctk.CTkLabel(row, text=name, width=200, anchor="w", font=("Arial", 12, "bold"))
        lbl_name.pack(side="left", padx=10)
        
        # Might Info
        might_val = data.get('might', 0)
        lbl_info = ctk.CTkLabel(row, text=f"Might: {might_val}", width=120, text_color="gray")
        lbl_info.pack(side="left")
        
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=5)

        # --- SHARED ACTIONS ---

        def on_delete():
            # Adds to Ignore List
            self.clan_manager.action_ignore_player(name)
            row.destroy()

        def on_merge():
            # Turns label into dropdown
            lbl_name.destroy()
            # Options: All verified players (except self)
            options = sorted([n for n in self.clan_manager.snapshot.keys() if n != name])
            
            combo = ctk.CTkComboBox(row, values=options, width=180)
            combo.set("Merge into...")
            combo.pack(side="left", padx=10, before=lbl_info)
            
            actions.destroy()
            act_save = ctk.CTkFrame(row, fg_color="transparent")
            act_save.pack(side="right", padx=5)
            
            def save_merge():
                target = combo.get()
                if target and target in options:
                    self.clan_manager.action_merge(name, target) # Map name -> target
                    self.refresh_roster_list()
            
            ctk.CTkButton(act_save, text="Confirm", width=60, fg_color="blue", command=save_merge).pack(side="left", padx=2)
            ctk.CTkButton(act_save, text="X", width=30, fg_color="gray", command=self.refresh_roster_list).pack(side="left", padx=2)

        def on_rename():
            # Turns label into entry box
            lbl_name.destroy()
            ent = ctk.CTkEntry(row, width=150)
            ent.insert(0, name)
            ent.pack(side="left", padx=10, before=lbl_info)
            
            actions.destroy()
            act_save = ctk.CTkFrame(row, fg_color="transparent")
            act_save.pack(side="right", padx=5)
            
            def save_rename():
                new_n = ent.get().strip()
                if new_n:
                    self.clan_manager.action_confirm_name_change(name, new_n)
                    self.refresh_roster_list()
            
            ctk.CTkButton(act_save, text="Save", width=50, fg_color="green", command=save_rename).pack(side="left", padx=2)
            ctk.CTkButton(act_save, text="X", width=30, fg_color="gray", command=self.refresh_roster_list).pack(side="left", padx=2)

        # --- BUTTON RENDERING ---
        if is_verified:
            # Verified: Rename, Merge, Delete
            ctk.CTkButton(actions, text="✏️", width=30, fg_color="#444", command=on_rename).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="🔗", width=30, fg_color="blue", command=on_merge).pack(side="left", padx=2) # Added Merge Icon
            ctk.CTkButton(actions, text="🗑️", width=30, fg_color="red", command=on_delete).pack(side="left", padx=2)
        else:
            # Unmatched: Merge, Ignore
            ctk.CTkButton(actions, text="🔗 Merge", width=70, fg_color="blue", command=on_merge).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="🚫 Ignore", width=70, fg_color="red", command=on_delete).pack(side="left", padx=2)

    def setup_automation(self):
        self.tab_auto.grid_columnconfigure(0, weight=1)
        frame_notif = ctk.CTkFrame(self.tab_auto)
        frame_notif.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_notif, text="📢 Discord Notifications", font=("Arial", 14, "bold")).pack(pady=5)
        self.entry_webhook = ctk.CTkEntry(frame_notif, placeholder_text="Paste Discord Webhook URL Here", width=400)
        self.entry_webhook.insert(0, self.settings.get("discord_webhook", ""))
        self.entry_webhook.pack(pady=5)
        def save_webhook():
            self.settings["discord_webhook"] = self.entry_webhook.get().strip()
            with open(CONFIG_FILE, "w") as f: json.dump(self.settings, f)
            self.log("✅ Webhook Saved.")
            self.send_discord_msg("✅ Total Battle Bot: Test Notification Successful.")
        ctk.CTkButton(frame_notif, text="Save & Test", command=save_webhook, fg_color="#5865F2").pack(pady=10)
        frame_gift = ctk.CTkFrame(self.tab_auto)
        frame_gift.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_gift, text="🎁 Auto Gift Muncher", font=("Arial", 14, "bold")).pack(pady=5)
        self.var_auto_gift = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame_gift, text="Enable", variable=self.var_auto_gift, command=self.calc_next_runs).pack(pady=5)
        f_g_ctrl = ctk.CTkFrame(frame_gift, fg_color="transparent")
        f_g_ctrl.pack()
        ctk.CTkLabel(f_g_ctrl, text="Every:").pack(side="left", padx=5)
        self.opt_gift_int = ctk.CTkOptionMenu(f_g_ctrl, values=[str(i) for i in range(1, 25)], width=60, command=lambda _: self.calc_next_runs())
        self.opt_gift_int.pack(side="left", padx=5)
        ctk.CTkLabel(f_g_ctrl, text="Hours").pack(side="left", padx=5)
        ctk.CTkLabel(f_g_ctrl, text="Start At:").pack(side="left", padx=15)
        self.opt_gift_start = ctk.CTkOptionMenu(f_g_ctrl, values=["Now", ":00 (Top of Hour)", ":30 (Half Past)"], command=lambda _: self.calc_next_runs())
        self.opt_gift_start.pack(side="left", padx=5)
        self.lbl_next_gift = ctk.CTkLabel(frame_gift, text="Next Run: Disabled", text_color="gray")
        self.lbl_next_gift.pack(pady=5)
        frame_roster = ctk.CTkFrame(self.tab_auto)
        frame_roster.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_roster, text="📜 Auto Roster Scan", font=("Arial", 14, "bold")).pack(pady=5)
        self.var_auto_roster = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame_roster, text="Enable", variable=self.var_auto_roster, command=self.calc_next_runs).pack(pady=5)
        f_r_ctrl = ctk.CTkFrame(frame_roster, fg_color="transparent")
        f_r_ctrl.pack()
        ctk.CTkLabel(f_r_ctrl, text="Every:").pack(side="left", padx=5)
        self.opt_roster_int = ctk.CTkOptionMenu(f_r_ctrl, values=[str(i) for i in range(1, 25)], width=60, command=lambda _: self.calc_next_runs())
        self.opt_roster_int.pack(side="left", padx=5)
        ctk.CTkLabel(f_r_ctrl, text="Hours").pack(side="left", padx=5)
        ctk.CTkLabel(f_r_ctrl, text="Start At:").pack(side="left", padx=15)
        self.opt_roster_start = ctk.CTkOptionMenu(f_r_ctrl, values=["Now", ":00 (Top of Hour)", ":30 (Half Past)"], command=lambda _: self.calc_next_runs())
        self.opt_roster_start.pack(side="left", padx=5)
        self.lbl_next_roster = ctk.CTkLabel(frame_roster, text="Next Run: Disabled", text_color="gray")
        self.lbl_next_roster.pack(pady=5)
        frame_excel = ctk.CTkFrame(self.tab_auto)
        frame_excel.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_excel, text="📊 Auto Excel Update", font=("Arial", 14, "bold")).pack(pady=5)
        self.var_auto_excel = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame_excel, text="Enable", variable=self.var_auto_excel, command=self.calc_next_runs).pack(pady=5)
        f_e_ctrl = ctk.CTkFrame(frame_excel, fg_color="transparent")
        f_e_ctrl.pack()
        ctk.CTkLabel(f_e_ctrl, text="Every:").pack(side="left", padx=5)
        self.opt_excel_int = ctk.CTkOptionMenu(f_e_ctrl, values=["1", "2", "4", "6", "12", "24"], width=60, command=lambda _: self.calc_next_runs())
        self.opt_excel_int.pack(side="left", padx=5)
        ctk.CTkLabel(f_e_ctrl, text="Hours").pack(side="left", padx=5)
        self.lbl_next_excel = ctk.CTkLabel(frame_excel, text="Next Run: Disabled", text_color="gray")
        self.lbl_next_excel.pack(pady=5)

    def setup_event_manager(self):
        self.tab_events.grid_columnconfigure(0, weight=1)
        title_frame = ctk.CTkFrame(self.tab_events, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(title_frame, text="Set Minimum Score Targets", font=("Arial", 16, "bold")).pack()
        self.scroll_events = ctk.CTkScrollableFrame(self.tab_events)
        self.scroll_events.pack(expand=True, fill="both", padx=20, pady=10)
        self.event_entries = {}
        saved_thresholds = self.settings.get("event_thresholds", {})
        for i, ev_name in enumerate(self.event_list):
            row_frame = ctk.CTkFrame(self.scroll_events)
            row_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(row_frame, text=ev_name, width=200, anchor="w", font=("Arial", 12, "bold")).pack(side="left", padx=10)
            ent = ctk.CTkEntry(row_frame, placeholder_text="0")
            if ev_name in saved_thresholds: ent.insert(0, str(saved_thresholds[ev_name]))
            else: ent.insert(0, "0")
            ent.pack(side="right", padx=10)
            self.event_entries[ev_name] = ent
        btn_save = ctk.CTkButton(self.tab_events, text="💾 Save Targets", fg_color="green", height=40, command=self.save_event_targets)
        btn_save.pack(pady=20, padx=20, fill="x")

    def save_event_targets(self):
        thresholds = {}
        for ev_name, ent in self.event_entries.items():
            try: val = int(ent.get().replace(",", "")) 
            except: val = 0
            thresholds[ev_name] = val
        self.settings["event_thresholds"] = thresholds
        with open(CONFIG_FILE, "w") as f: json.dump(self.settings, f)
        self.log("✅ Event Targets Saved!")

    def setup_chest_manager(self):
        self.mapper = ChestMapper()
        self.tab_manager.grid_columnconfigure(0, weight=1)
        self.tab_manager.grid_columnconfigure(2, weight=1)
        self.tab_manager.grid_rowconfigure(0, weight=1)
        frame_left = ctk.CTkFrame(self.tab_manager)
        frame_left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(frame_left, text="❓ Found in Log (Unmapped)", font=("Arial", 14, "bold")).pack(pady=5)
        self.list_unmapped = ctk.CTkScrollableFrame(frame_left)
        self.list_unmapped.pack(expand=True, fill="both", padx=5, pady=5)
        frame_mid = ctk.CTkFrame(self.tab_manager)
        frame_mid.grid(row=0, column=1, sticky="ns", padx=5, pady=5)
        ctk.CTkLabel(frame_mid, text="--- Global Settings ---", text_color="yellow").pack(pady=(10,0))
        ctk.CTkLabel(frame_mid, text="Clan Minimum Score:").pack()
        self.entry_min_score_global = ctk.CTkEntry(frame_mid, placeholder_text="1000")
        self.entry_min_score_global.insert(0, str(self.settings.get("min_score", 1000)))
        self.entry_min_score_global.pack(pady=5)
        def save_global_min():
            try:
                val = int(self.entry_min_score_global.get())
                self.settings["min_score"] = val
                with open(CONFIG_FILE, "w") as f: json.dump(self.settings, f)
                self.log(f"💾 Min Score set to {val}")
            except: pass
        ctk.CTkButton(frame_mid, text="Save Global Min", command=save_global_min, fg_color="gray").pack(pady=5)
        ctk.CTkLabel(frame_mid, text="-----------------------").pack(pady=10)
        ctk.CTkLabel(frame_mid, text="Map Selected To:", font=("Arial", 14, "bold")).pack(pady=10)
        self.var_group = ctk.StringVar(value="Common Crypt")
        groups = ["Common Crypt", "Rare Crypt", "Epic Crypt", "Citadel", "Heroic", "Bank Chest", "Tartaros", "Other"]
        self.opt_group = ctk.CTkComboBox(frame_mid, variable=self.var_group, values=groups)
        self.opt_group.pack(pady=5)
        self.var_level = ctk.StringVar(value="5")
        levels = ["5", "10", "15", "20", "25", "30", "35", "16 - 25", "26 - 30", "31+", "Wooden", "Bronze", "Silver", "Golden", "Precious", "Magic", "Ragnarok", "Ancient", "Epics", "Olympus", "Other"]
        self.opt_level = ctk.CTkComboBox(frame_mid, variable=self.var_level, values=levels)
        self.opt_level.pack(pady=5)
        self.entry_points = ctk.CTkEntry(frame_mid, placeholder_text="Points (e.g. 10)")
        self.entry_points.pack(pady=5)
        self.btn_map = ctk.CTkButton(frame_mid, text="Select a Chest", state="disabled") 
        self.btn_map.pack(pady=20)
        frame_right = ctk.CTkFrame(self.tab_manager)
        frame_right.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(frame_right, text="✅ Mapped Chests", font=("Arial", 14, "bold")).pack(pady=5)
        self.list_mapped = ctk.CTkScrollableFrame(frame_right)
        self.list_mapped.pack(expand=True, fill="both", padx=5, pady=5)
        ctk.CTkButton(self.tab_manager, text="🔄 Refresh Lists", command=self.refresh_chest_lists).grid(row=1, column=0, columnspan=3, pady=10)
        self.selected_chest_id = None
        self.refresh_chest_lists()

    def refresh_chest_lists(self):
        for widget in self.list_unmapped.winfo_children(): widget.destroy()
        for widget in self.list_mapped.winfo_children(): widget.destroy()
        all_found = self.mapper.get_unique_chests_from_log()
        mapped_data = self.mapper.load_mappings()
        for src in all_found:
            if src not in mapped_data:
                btn = ctk.CTkButton(self.list_unmapped, text=src, fg_color="gray", command=lambda s=src: self.select_chest_to_map(s))
                btn.pack(fill="x", pady=2)
        for src, data in mapped_data.items():
            display = f"{src} \n-> {data['key']} ({data['points']} pts)"
            btn = ctk.CTkButton(self.list_mapped, text=display, fg_color="green", command=lambda s=src: self.delete_mapping(s))
            btn.pack(fill="x", pady=2)

    def select_chest_to_map(self, chest_id):
        self.selected_chest_id = chest_id
        self.btn_map.configure(text=f"SAVE MAP", state="normal", fg_color="blue", command=self.save_current_map)

    def save_current_map(self):
        if not self.selected_chest_id: return
        group = self.var_group.get()
        lvl = self.var_level.get()
        template_key = f"{group} {lvl}".lower() 
        try: points = int(self.entry_points.get())
        except: points = 0
        self.mapper.add_mapping(self.selected_chest_id, template_key, points)
        self.refresh_chest_lists()
        self.selected_chest_id = None
        self.btn_map.configure(text="Select a Chest", state="disabled", fg_color="gray")

    def delete_mapping(self, chest_id):
        self.mapper.remove_mapping(chest_id)
        self.refresh_chest_lists()
    
    def setup_calibration(self):
        self.tab_calib.grid_columnconfigure(1, weight=1)
        controls = ctk.CTkFrame(self.tab_calib, width=300)
        controls.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.calib_mode = ctk.CTkOptionMenu(controls, values=["chests", "roster", "events", "accounts"], command=self.switch_calib_mode) # Added "accounts"
        self.calib_mode.set(self.settings["mode"])
        self.calib_mode.pack(pady=5)
        self.sliders = {}
        def add_slider(key, label, min_v, max_v):
            ctk.CTkLabel(controls, text=label).pack(pady=(2,0))
            s = ctk.CTkSlider(controls, from_=min_v, to=max_v, command=lambda v: self.update_preview())
            s.pack(pady=2)
            self.sliders[key] = s
        
        self.controls_frame = controls
        self.dynamic_sliders = []
        
        # --- FIX: Create sliders FIRST ---
        self.slider_thresh = ctk.CTkSlider(controls, from_=0, to=255, command=lambda v: self.update_preview())
        self.slider_thresh.pack(pady=2)
        self.check_bw = ctk.CTkCheckBox(controls, text="B/W Filter", command=self.update_preview)
        self.check_bw.pack(pady=10)
        
        # --- THEN refresh them (populating values) ---
        self.refresh_sliders()

        ctk.CTkButton(controls, text="📸 Capture", command=self.capture_screen).pack(pady=10)
        ctk.CTkButton(controls, text="💾 Save", fg_color="green", command=self.save_settings).pack(pady=10)
        self.preview_frame = ctk.CTkFrame(self.tab_calib)
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.lbl_image = ctk.CTkLabel(self.preview_frame, text="Capture Screen")
        self.lbl_image.pack(expand=True, fill="both")
        self.lbl_ocr = ctk.CTkLabel(self.preview_frame, text="...", text_color="yellow", font=("Consolas", 14))
        self.lbl_ocr.pack(pady=10)

    def read_text_from_image(self, img_array, use_bw=False, thresh_val=150):
        try:
            # 1. UPSCALE (Critical for small game text)
            scale = 3
            h, w = img_array.shape[:2]
            # Resize 3x bigger with smooth interpolation
            img_array = cv2.resize(img_array, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

            # 2. GRAYSCALE (Standard best practice)
            # We convert to gray to simplify data, but we keep the "shades" of gray
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # 3. OPTIONAL B/W FILTER
            # Only runs if you check the box in the GUI (good for very low contrast text)
            if use_bw: 
                _, final_img = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
            else: 
                final_img = gray
            
            # 4. READ
            result_list = self.reader.readtext(final_img, detail=0, paragraph=True)
            text = " ".join(result_list)
            return text.strip(), final_img
        except: return "", img_array

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    self.settings.update(json.load(f))
            except: pass

    def save_settings(self):
        mode = self.calib_mode.get()
        self.settings["mode"] = mode
        
        # Save based on mode
        if mode == "accounts":
            s = self.settings.setdefault("accounts", {})
            s["drag_start_x"] = int(self.sliders["drag_start_x"].get()) # NEW X
            s["drag_start_y"] = int(self.sliders["drag_start_y"].get())
            s["drag_end_y"] = int(self.sliders["drag_end_y"].get())
            s["drag_speed"] = float(self.sliders["drag_speed"].get())
            s["scroll_attempts"] = int(self.sliders["scroll_attempts"].get())
        else:
            s = self.settings[mode]
            s["off_x"] = int(self.sliders["off_x"].get())
            s["off_y"] = int(self.sliders["off_y"].get())
            s["w"] = int(self.sliders["w"].get())
            s["h"] = int(self.sliders["h"].get())
            s["thresh"] = int(self.slider_thresh.get())
            s["bw"] = bool(self.check_bw.get())
            if mode in ["roster", "events"]:
                s["margin_top"] = int(self.sliders["margin_top"].get())
                s["margin_bot"] = int(self.sliders["margin_bot"].get())
            if mode == "events":
                s["split_x"] = int(self.sliders["split_x"].get())

        with open(CONFIG_FILE, "w") as f: json.dump(self.settings, f)
        self.log(f"✅ Settings saved for {mode}.")

    def switch_calib_mode(self, mode):
        self.settings["mode"] = mode
        self.refresh_sliders()

    def refresh_sliders(self):
        # Clear old sliders
        for s in self.dynamic_sliders: s.destroy()
        self.dynamic_sliders = []
        self.sliders = {}

        mode = self.settings["mode"]
        vals = self.settings.get(mode, {})

        def add_s(key, label, min_v, max_v, default_val=0):
            l = ctk.CTkLabel(self.controls_frame, text=label)
            l.pack(pady=(2,0))
            s = ctk.CTkSlider(self.controls_frame, from_=min_v, to=max_v, command=lambda v: self.update_preview())
            s.set(vals.get(key, default_val))
            s.pack(pady=2)
            self.sliders[key] = s
            self.dynamic_sliders.extend([l, s])

        if mode == "accounts":
            add_s("drag_start_x", "Drag X Offset", -500, 500, 0) # NEW SLIDER
            add_s("drag_start_y", "Drag Start Y (Down)", 100, 800, 450)
            add_s("drag_end_y", "Drag End Y (Up)", 0, 600, 150)
            add_s("drag_speed", "Drag Speed (sec)", 0.1, 2.0, 0.8)
            add_s("scroll_attempts", "Scroll Attempts", 1, 30, 15)
        else:
            add_s("off_x", "Offset X", -500, 1000, vals.get("off_x", 0))
            add_s("off_y", "Offset Y", -100, 500, vals.get("off_y", 0))
            add_s("w", "Width", 50, 1000, vals.get("w", 100))
            add_s("h", "Height", 10, 200, vals.get("h", 50))
            
            if mode in ["roster", "events"]:
                add_s("margin_top", "Top Limit", 0, 500, vals.get("margin_top", 200))
                add_s("margin_bot", "Bottom Limit", 500, 1080, vals.get("margin_bot", 800))
            if mode == "events":
                add_s("split_x", "Split X", 0, 800, vals.get("split_x", 400))
            
            self.slider_thresh.set(vals.get("thresh", 150))
            if vals.get("bw", False): self.check_bw.select()
            else: self.check_bw.deselect()

    def capture_screen(self):
        self.log("📸 Capture in 3s...")
        self.update()
        time.sleep(3)
        self.captured_image = pyautogui.screenshot()
        self.log("✅ Captured.")
        self.update_preview()

    def update_preview(self):
        if self.captured_image is None: return
        mode = self.calib_mode.get()
        
        # --- NEW: ACCOUNT CALIBRATION PREVIEW ---
        if mode == "accounts":
            img_np = np.array(self.captured_image)
            display_img = img_np.copy()
            anchor_img = "assets/acc_anchor.png"
            if os.path.exists(anchor_img):
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                template = cv2.imread(anchor_img, 0)
                res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= 0.8)
                target_pt = None
                for pt in zip(*loc[::-1]): 
                    target_pt = pt
                    break # Take first
                
                if target_pt:
                    ax, ay = target_pt
                    center_x = ax + (template.shape[1] // 2)
                    center_y = ay + (template.shape[0] // 2)
                    
                    # Get Slider Values
                    x_offset = int(self.sliders["drag_start_x"].get()) # NEW
                    start_y = center_y + int(self.sliders["drag_start_y"].get())
                    end_y = center_y + int(self.sliders["drag_end_y"].get())
                    
                    # Apply X Offset
                    drag_x = center_x + x_offset
                    
                    # Draw Arrow (With X offset applied)
                    cv2.arrowedLine(display_img, (drag_x, start_y), (drag_x, end_y), (255, 0, 0), 5, tipLength=0.3)
                    cv2.circle(display_img, (drag_x, start_y), 10, (0, 0, 255), -1) # Red Start
                    cv2.circle(display_img, (drag_x, end_y), 10, (0, 255, 0), -1)   # Green End
                    
            pil_img = Image.fromarray(display_img)
            ratio = 600 / display_img.shape[0]
            new_w = int(display_img.shape[1] * ratio)
            self.lbl_image.configure(image=ctk.CTkImage(pil_img, size=(new_w, 600)), text="")
            return

        # --- EXISTING PREVIEW LOGIC ---
        if mode == "chests": anchor_img = "assets/btn_claim.png"
        elif mode == "roster": anchor_img = "assets/anchor_roster.png"
        elif mode == "events": anchor_img = "assets/anchor_event.png"
        
        if not os.path.exists(anchor_img): 
            self.lbl_image.configure(text=f"Missing {anchor_img}")
            return
        img_np = np.array(self.captured_image)
        display_img = img_np.copy() 
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        template = cv2.imread(anchor_img, 0)
        res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.8)
        margin_top = int(self.sliders["margin_top"].get()) if mode != "chests" else 0
        margin_bot = int(self.sliders["margin_bot"].get()) if mode != "chests" else 9999
        cv2.line(display_img, (0, margin_top), (display_img.shape[1], margin_top), (255, 0, 0), 3)
        cv2.line(display_img, (0, margin_bot), (display_img.shape[1], margin_bot), (255, 0, 0), 3)
        target_pt = None
        for pt in zip(*loc[::-1]):
            y = pt[1]
            if margin_top < y < margin_bot:
                cv2.rectangle(display_img, pt, (pt[0]+30, pt[1]+30), (0, 255, 0), 2)
                if target_pt is None: target_pt = pt
            else:
                cv2.rectangle(display_img, pt, (pt[0]+30, pt[1]+30), (255, 0, 0), 2)
        if target_pt:
            ax, ay = target_pt
            off_x = int(self.sliders["off_x"].get())
            off_y = int(self.sliders["off_y"].get())
            w = int(self.sliders["w"].get())
            h = int(self.sliders["h"].get())
            if mode == "chests": box_x, box_y = ax - off_x, ay - off_y
            else: box_x, box_y = ax + off_x, ay + off_y
            cv2.rectangle(display_img, (box_x, box_y), (box_x+w, box_y+h), (0, 255, 255), 2)
            if mode == "events":
                split_x = int(self.sliders["split_x"].get())
                abs_split = box_x + split_x
                cv2.line(display_img, (abs_split, box_y), (abs_split, box_y+h), (0, 255, 0), 3)
                crop_name = img_np[box_y:box_y+h, box_x:abs_split]
                crop_score = img_np[box_y:box_y+h, abs_split:box_x+w]
                t_name, _ = self.read_text_from_image(crop_name, self.check_bw.get(), int(self.slider_thresh.get()))
                t_score, _ = self.read_text_from_image(crop_score, self.check_bw.get(), int(self.slider_thresh.get()))
                self.lbl_ocr.configure(text=f"NAME: '{t_name}' | SCORE: '{t_score}'")
            else:
                crop = img_np[box_y:box_y+h, box_x:box_x+w]
                text, _ = self.read_text_from_image(crop, self.check_bw.get(), int(self.slider_thresh.get()))
                self.lbl_ocr.configure(text=f"READ: {text}")
        pil_img = Image.fromarray(display_img)
        ratio = 600 / display_img.shape[0]
        new_w = int(display_img.shape[1] * ratio)
        self.lbl_image.configure(image=ctk.CTkImage(pil_img, size=(new_w, 600)), text="")

    def navigate_to_gifts(self):
        self.log("Navigating to Gifts...")
        self.handle_interruptions() 
        try:
            if pyautogui.locateOnScreen("assets/btn_clan.png", confidence=0.8):
                pyautogui.click(pyautogui.center(pyautogui.locateOnScreen("assets/btn_clan.png", confidence=0.8)))
                time.sleep(0.5)
            if pyautogui.locateOnScreen("assets/btn_gifts.png", confidence=0.8):
                pyautogui.click(pyautogui.center(pyautogui.locateOnScreen("assets/btn_gifts.png", confidence=0.8)))
                time.sleep(1.0)
        except: pass

    def navigate_to_gifts2(self):
        self.log("Switching to Page 2...")
        try:
            loc = pyautogui.locateOnScreen("assets/btn_gifts2.png", confidence=0.8)
            if loc:
                target = pyautogui.center(loc)
                pyautogui.moveTo(target.x, target.y, duration=0.3)
                time.sleep(0.2)
                pyautogui.mouseDown()
                time.sleep(0.2)
                pyautogui.mouseUp()
                time.sleep(1.0)
                return True
        except: pass
        return False

    def navigate_to_roster(self):
        self.log("Navigating to Roster...")
        self.handle_interruptions()
        try:
            if pyautogui.locateOnScreen("assets/btn_clan.png", confidence=0.8):
                pyautogui.click(pyautogui.center(pyautogui.locateOnScreen("assets/btn_clan.png", confidence=0.8)))
                time.sleep(1.0)
            if pyautogui.locateOnScreen("assets/btn_members.png", confidence=0.8):
                pyautogui.click(pyautogui.center(pyautogui.locateOnScreen("assets/btn_members.png", confidence=0.8)))
                time.sleep(1.0)
                pyautogui.moveRel(300, 0)
        except: pass
        
    def close_menu_action(self, task_name="action"):
        """ Checks for the close button, clicks it, and sends a success notification. """
        self.log("🔙 Closing Clan Menu...")
        try:
            time.sleep(0.5)
            # Looks for the X button to close the window
            btn = pyautogui.locateOnScreen("assets/close_clan_menu.png", confidence=0.8)
            if btn:
                pyautogui.click(pyautogui.center(btn))
                time.sleep(1.0) # Wait for menu to close animation
                
                # --- NEW: Send Specific Success Message to Discord ---
                success_msg = f"✅ Bot Success: clan menu closed {task_name} complete"
                self.log(success_msg) # Log locally
                self.send_discord_msg(success_msg) # Force send to Discord
            else:
                self.log("⚠️ 'close_clan_menu' button not found.")
        except: pass

    def process_gifts(self):
        s = self.settings["chests"]
        try: buttons = list(pyautogui.locateAllOnScreen("assets/btn_claim.png", confidence=0.8))
        except: return False
        if not buttons: return False
        buttons.sort(key=lambda b: b.top)
        batch = buttons[:4]
        for btn in batch:
            left = int(btn.left - s["off_x"])
            top = int(btn.top - s["off_y"])
            w = int(s["w"])
            h = int(s["h"])
            try:
                sc = pyautogui.screenshot(region=(left, top, w, h))
                img = np.array(sc)
                text, _ = self.read_text_from_image(img, s["bw"], s["thresh"])
                self.data_manager.parse_and_save(text)
            except: pass
        kill_spot = pyautogui.center(batch[0])
        pyautogui.moveTo(kill_spot.x, kill_spot.y, duration=0.2) 
        for _ in range(len(batch)):
            pyautogui.click() 
            time.sleep(0.2) 
        time.sleep(0.5)
        return True

    def process_generic_list(self, is_event=False):
        if is_event:
            anchor_file = "assets/anchor_event.png"
            s = self.settings["events"]
        else:
            anchor_file = "assets/anchor_roster.png"
            s = self.settings["roster"]
        try: anchors = list(pyautogui.locateAllOnScreen(anchor_file, confidence=0.8))
        except: return False
        if not anchors: return False
        m_top = s["margin_top"]
        m_bot = s["margin_bot"]
        valid_anchors = [a for a in anchors if m_top < a.top < m_bot]
        valid_anchors.sort(key=lambda x: x.top)
        new_data_count = 0
        for anchor in valid_anchors:
            if self.stop_requested: return False
            left = int(anchor.left + s["off_x"])
            top = int(anchor.top + s["off_y"])
            w = int(s["w"])
            h = int(s["h"])
            try:
                if is_event:
                    split_x = s.get("split_x", 400)
                    sc_name = pyautogui.screenshot(region=(left, top, split_x, h))
                    img_name = np.array(sc_name)
                    txt_name, _ = self.read_text_from_image(img_name, s["bw"], s["thresh"])
                    sc_score = pyautogui.screenshot(region=(left + split_x, top, w - split_x, h))
                    img_score = np.array(sc_score)
                    txt_score, _ = self.read_text_from_image(img_score, s["bw"], s["thresh"])
                    data = self.data_manager.parse_event_split(txt_name, txt_score)
                else:
                    sc = pyautogui.screenshot(region=(left, top, w, h))
                    img = np.array(sc)
                    txt, _ = self.read_text_from_image(img, s["bw"], s["thresh"])
                    data = self.data_manager.extract_roster_data(txt)
                if data:
                    name = data['name']
                    number = data.get('score', data.get('number'))
                    fingerprint = re.sub(r'[^a-z0-9]', '', name.lower())
                    number_clean = re.sub(r'[^\d]', '', number)
                    is_duplicate_name = fingerprint in self.seen_player_names
                    is_duplicate_num = (number_clean.isdigit() and int(number_clean) > 0 and number_clean in self.seen_player_numbers)
                    if is_event: is_new = not is_duplicate_name
                    else: is_new = not is_duplicate_name and (number_clean == "0" or not is_duplicate_num)
                    if is_new:
                        if is_event:
                            event_name = self.selected_event.get()
                            self.data_manager.append_event_row(event_name, name, number)
                        else:
                            self.data_manager.append_roster_row(name, number)
                        self.log(f"💾 {name} ({number})")
                        self.seen_player_names.add(fingerprint)
                        if number_clean.isdigit() and int(number_clean) > 0:
                            self.seen_player_numbers.add(number_clean)
                        new_data_count += 1
            except: pass
        return new_data_count > 0

    def run_gift_cycle(self):
        if not self.verify_profile():
            self.stop_bot()
            return
        no_data_streak = 0
        gift_page_state = 1
        while not self.stop_requested:
            if self.check_connection_loss():
                time.sleep(5)
                continue
            found = self.process_gifts()
            if found: no_data_streak = 0
            else:
                no_data_streak += 1
                self.log(f"Empty scan {no_data_streak}/3")
            if no_data_streak >= 3:
                if gift_page_state == 1:
                    self.log("Switching to Page 2...")
                    if self.navigate_to_gifts2():
                        gift_page_state = 2
                        no_data_streak = 0
                    else: break
                else: break
            time.sleep(1)
        
        # --- NEW: CLOSE MENU AFTER COMPLETION ---
        if not self.stop_requested:
            self.close_menu_action(task_name="gift count")

    def run_roster_cycle(self, is_event=False):
        if not self.verify_profile():
            self.stop_bot()
            return

        # --- DYNAMIC SAFE SPOT (RIGHT BIASED) ---
        s = self.settings["events"] if is_event else self.settings["roster"]
        
        # Default fallback (shifted right to 700)
        safe_x = 700 
        safe_y = int((s.get("margin_top", 200) + s.get("margin_bot", 800)) / 2)

        # Try to find an anchor to set the perfect position
        anchor_img = "assets/anchor_event.png" if is_event else "assets/anchor_roster.png"
        try:
            loc = pyautogui.locateOnScreen(anchor_img, confidence=0.8)
            if loc:
                # X = Anchor + Offset + Half Width + 100px (Nudge Right)
                safe_x = int(loc.left + s["off_x"] + (s["w"] / 2) + 100)
        except: pass

        no_data_streak = 0
        while not self.stop_requested:
            if self.check_connection_loss():
                time.sleep(5)
                continue

            if self.process_generic_list(is_event): 
                no_data_streak = 0
            else: 
                no_data_streak += 1
            
            if no_data_streak >= 3: break
            
            # --- MOVEMENT FIX ---
            pyautogui.moveTo(safe_x, safe_y)
            pyautogui.click()
            # --------------------

            for _ in range(3): 
                pyautogui.scroll(-2000)
                time.sleep(0.05)
            time.sleep(0.8)
        
        # --- NEW: CLOSE MENU ACTION ---
        if not self.stop_requested:
            self.close_menu_action(task_name="roster scan")
        
        # --- AUTOMATION CHAINING ---
        if not is_event and self.is_auto_active:
            self.log("🔄 Auto-Triggering Clan Analysis...")
            self.run_clan_analysis(auto=True)
            
            self.log("🔄 Auto-Triggering Master Excel Update...")
            self.run_excel_logic()

    def run_excel_logic(self):
        self.log("🔄 Compiling Excel...")
        min_score = int(self.settings.get("min_score", 1000))
        event_thresholds = self.settings.get("event_thresholds", {})
        mc = MasterCompiler()
        if mc.run_update(min_score, event_thresholds): self.log("✅ Excel Updated")
        else: self.log("❌ Excel Error")

    def start_bot_safe(self): 
        if not self.is_running: self.start_bot()
    def stop_bot_safe(self): 
        if self.is_running: self.stop_bot()

    def start_bot(self):
        if self.is_auto_active:
            self.log("⚠️ Cannot start manual: Automation active")
            return
        self.is_running = True
        self.stop_requested = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.seen_player_names = set()
        self.seen_player_numbers = set()
        task = self.task_menu.get()
        if task == "Event Scanner":
            ev_name = self.selected_event.get()
            self.data_manager.initialize_event_file(ev_name)
            self.log(f"🗑️ Wiped file for: {ev_name}")
        threading.Thread(target=self.bot_thread_manual).start()

    def stop_bot(self):
        self.stop_requested = True
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.log("🛑 Stopping...")

    def bot_thread_manual(self):
        task = self.task_menu.get()
        self.log(f"--- STARTED: {task} ---")
        time.sleep(1)
        if task == "Gift Muncher": 
            self.navigate_to_gifts()
            self.run_gift_cycle()
        elif task == "Roster Scan": 
            self.navigate_to_roster()
            self.run_roster_cycle(is_event=False)
        elif task == "Event Scanner":
            self.run_roster_cycle(is_event=True)
        self.log("✅ Complete.")
        self.stop_bot()

    def log(self, msg):
        self.log_box.insert("end", f"[{time.strftime('%H:%M')}] {msg}\n")
        self.log_box.see("end")
        
        if "❌" in msg or "Error" in msg:
            self.send_discord_msg(f"🚨 **Bot Error**: {msg}")

    def calc_next_runs(self):
        now = datetime.datetime.now()
        def get_next_time(interval_hours, start_mode):
            interval = int(interval_hours)
            target = now
            if start_mode == "Now": target = now + datetime.timedelta(hours=interval)
            elif start_mode == ":00 (Top of Hour)": target = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
            elif start_mode == ":30 (Half Past)":
                target = now.replace(minute=30, second=0, microsecond=0)
                if target < now: target += datetime.timedelta(hours=1)
            return target
        if self.var_auto_gift.get():
            if not self.next_gift_run or self.next_gift_run < now:
                self.next_gift_run = get_next_time(self.opt_gift_int.get(), self.opt_gift_start.get())
            self.lbl_next_gift.configure(text=f"Next Run: {self.next_gift_run.strftime('%H:%M:%S')}", text_color="green")
        else:
            self.next_gift_run = None
            self.lbl_next_gift.configure(text="Next Run: Disabled", text_color="gray")
        if self.var_auto_roster.get():
            if not self.next_roster_run or self.next_roster_run < now:
                self.next_roster_run = get_next_time(self.opt_roster_int.get(), self.opt_roster_start.get())
            self.lbl_next_roster.configure(text=f"Next Run: {self.next_roster_run.strftime('%H:%M:%S')}", text_color="green")
        else:
            self.next_roster_run = None
            self.lbl_next_roster.configure(text="Next Run: Disabled", text_color="gray")
        if self.var_auto_excel.get():
            if not self.next_excel_run or self.next_excel_run < now:
                self.next_excel_run = now + datetime.timedelta(hours=int(self.opt_excel_int.get()))
            self.lbl_next_excel.configure(text=f"Next Run: {self.next_excel_run.strftime('%H:%M:%S')}", text_color="green")
        else:
            self.next_excel_run = None
            self.lbl_next_excel.configure(text="Next Run: Disabled", text_color="gray")

    def scheduler_loop(self):
        while True:
            time.sleep(5)
            now = datetime.datetime.now()
            if self.is_running or self.is_auto_active: continue
            if self.next_gift_run and now >= self.next_gift_run:
                self.trigger_auto_task("gift")
                self.next_gift_run += datetime.timedelta(hours=int(self.opt_gift_int.get()))
                self.calc_next_runs()
            elif self.next_roster_run and now >= self.next_roster_run:
                self.trigger_auto_task("roster")
                self.next_roster_run += datetime.timedelta(hours=int(self.opt_roster_int.get()))
                self.calc_next_runs()
            elif self.next_excel_run and now >= self.next_excel_run:
                self.trigger_auto_task("excel")
                self.next_excel_run += datetime.timedelta(hours=int(self.opt_excel_int.get()))
                self.calc_next_runs()

    def trigger_auto_task(self, task_type):
        self.is_auto_active = True
        self.stop_requested = False  
        threading.Thread(target=self.run_auto_logic, args=(task_type,)).start()

    def run_auto_logic(self, task_type):
        self.log(f"⚙️ Auto Starting: {task_type.upper()}...")
        if task_type == "gift":
            self.navigate_to_gifts()
            time.sleep(2.0)
            self.run_gift_cycle()
        elif task_type == "roster":
            self.navigate_to_roster()
            time.sleep(2.0)
            self.run_roster_cycle()
        elif task_type == "excel":
            self.run_excel_logic()
        self.log(f"✅ Auto Complete: {task_type.upper()}")
        self.is_auto_active = False

if __name__ == "__main__":
    app = TotalBattleBotApp()
    app.mainloop()