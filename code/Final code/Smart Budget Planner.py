import sys, os, json
from datetime import datetime, timedelta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import *

# Configuration & Styling
DATA_FILE = "users_data.json"

# CSS-like styling for the UI (QSS)
STYLE_SHEET = """
QMainWindow, QWidget { background-color: #0F172A; color: #E5E7EB; font-family: 'Arial'; }
#SidebarBox { background-color: #111827; border-radius: 10px; padding: 10px; }
#NavBtn { background-color: #334155; color: white; border-radius: 8px; padding: 10px; border: none; font-weight: bold; margin-bottom: 8px; }
#NavBtn:hover { background-color: #3B82F6; }
#LogoutBtn { background-color: #F97316; color: white; border-radius: 8px; padding: 10px; border: none; font-weight: bold; }
#MainCard { background-color: #1E293B; border-radius: 10px; padding: 20px; }
QLineEdit, QComboBox, QDateEdit { padding: 10px; background-color: #0F172A; color: white; border: 1px solid #334155; border-radius: 6px; margin: 5px 0; }
#BalanceLabel { color: #22C55E; font-size: 45px; font-weight: bold; }
#AddBtn { background-color: #22C55E; color: white; font-weight: bold; border-radius: 8px; height: 40px; }
#SpendBtn { background-color: #EF4444; color: white; font-weight: bold; border-radius: 8px; height: 40px; }
#ActionBtn { background-color: #3B82F6; color: white; border-radius: 6px; padding: 5px 10px; font-weight: bold; }
#DeleteBtn { background-color: #EF4444; color: white; border-radius: 6px; padding: 5px 10px; font-weight: bold; }
#VaultBtn { background-color: #EAB308; color: #000000; font-weight: 900; border-radius: 8px; height: 45px; }
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Initialize data and state tracking
        self.users = self.load_data()
        self.current_user = None
        self.editing_id = None # Tracks if we are creating a new bill or updating an old one
        
        self.setWindowTitle("Smart Budget Planner")
        self.resize(1200, 950)
        self.setStyleSheet(STYLE_SHEET)
        self.setup_ui()

    # --- DATA PERSISTENCE ---
    def load_data(self):
        """ Reads the JSON file. Returns an empty dict if file doesn't exist or is corrupt. """
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        """ Writes all user data back to the JSON file. """
        with open(DATA_FILE, "w") as f: json.dump(self.users, f, indent=4)

    # --- UI CONSTRUCTION ---
    def setup_ui(self):
        """ Builds the multi-page interface using QStackedWidget. """
        self.root_stack = QStackedWidget() 
        self.setCentralWidget(self.root_stack)
        
        # PAGE 1: LOGIN/REGISTER
        login_page = QWidget(); l_lay = QVBoxLayout(login_page); l_lay.addStretch()
        title = QLabel("BUDGET PLANNER"); title.setStyleSheet("font-size: 45px; font-weight: bold; color: #3B82F6;")
        l_lay.addWidget(title, alignment=Qt.AlignCenter)
        
        self.u_in = QLineEdit(); self.u_in.setPlaceholderText("Username")
        self.p_in = QLineEdit(); self.p_in.setPlaceholderText("Password"); self.p_in.setEchoMode(QLineEdit.Password)
        
        btn_l = QPushButton("Login / Make Account"); btn_l.setObjectName("NavBtn"); btn_l.setFixedHeight(45)
        btn_l.clicked.connect(self.handle_login)
        
        for w in (self.u_in, self.p_in, btn_l): 
            w.setFixedWidth(320); l_lay.addWidget(w, alignment=Qt.AlignCenter)
        l_lay.addStretch(); self.root_stack.addWidget(login_page)

        # PAGE 2: MAIN APPLICATION AREA
        main_page = QWidget(); main_hbox = QHBoxLayout(main_page)
        
        # Sidebar Navigation
        sidebar_w = QFrame(); sidebar_w.setObjectName("SidebarBox"); sidebar_w.setFixedWidth(200)
        sidebar = QVBoxLayout(sidebar_w)
        for txt, idx in [("Dashboard", 0), ("Recurring Bills", 1), ("One-Time Dues", 2)]:
            btn = QPushButton(txt); btn.setObjectName("NavBtn")
            # When clicked, change the sub-page and refresh the lists
            btn.clicked.connect(lambda _, x=idx: self.content_stack.setCurrentIndex(x) or self.refresh_ui())
            sidebar.addWidget(btn)
        
        logout = QPushButton("Logout"); logout.setObjectName("LogoutBtn"); logout.clicked.connect(self.handle_logout)
        sidebar.addStretch(); sidebar.addWidget(logout); main_hbox.addWidget(sidebar_w)

        # Sub-Pages Stack (Dashboard, Recurring, One-Time)
        self.content_stack = QStackedWidget()
        
        # SUB-PAGE: DASHBOARD (Overview & Manual Transactions)
        dash = QFrame(); dash.setObjectName("MainCard"); d_lay = QVBoxLayout(dash)
        self.net_worth_label = QLabel("Total Net Worth: ₱0.00")
        self.bal_label = QLabel("₱0.00"); self.bal_label.setObjectName("BalanceLabel")
        d_lay.addWidget(self.net_worth_label); d_lay.addWidget(self.bal_label)
        
        d_lay.addWidget(QLabel("⚠️ URGENT DUES:"))
        self.due_summary = QListWidget(); self.due_summary.setMaximumHeight(120); d_lay.addWidget(self.due_summary)
        
        self.item_in = QLineEdit(); self.item_in.setPlaceholderText("Description")
        self.amt_in = QLineEdit(); self.amt_in.setPlaceholderText("Amount")
        d_lay.addWidget(self.item_in); d_lay.addWidget(self.amt_in)
        
        b_row = QHBoxLayout()
        add_b = QPushButton("ADD INCOME"); add_b.setObjectName("AddBtn"); add_b.clicked.connect(lambda: self.process_money("plus"))
        sp_b = QPushButton("SPEND MONEY"); sp_b.setObjectName("SpendBtn"); sp_b.clicked.connect(lambda: self.process_money("minus"))
        b_row.addWidget(add_b); b_row.addWidget(sp_b); d_lay.addLayout(b_row)
        
        # Vault feature: Locks money away for a short period
        self.v_btn = QPushButton("INCOME VAULT"); self.v_btn.setObjectName("VaultBtn"); self.v_btn.clicked.connect(self.manage_vault)
        d_lay.addWidget(self.v_btn); d_lay.addWidget(QLabel("HISTORY:"))
        
        self.history_list = QListWidget(); d_lay.addWidget(self.history_list)
        self.content_stack.addWidget(dash)

        # SUB-PAGE: RECURRING BILLS (Manager for Subs/Rent)
        rec_card = QFrame(); rec_card.setObjectName("MainCard"); r_lay = QVBoxLayout(rec_card)
        r_lay.addWidget(QLabel("RECURRING BILLS MANAGER"))
        self.r_name = QLineEdit(); self.r_name.setPlaceholderText("Bill Name")
        self.r_amt = QLineEdit(); self.r_amt.setPlaceholderText("Amount")
        self.r_date = QDateEdit(); self.r_date.setCalendarPopup(True); self.r_date.setDate(datetime.now().date())
        self.r_cycle = QComboBox(); self.r_cycle.addItems(["Daily", "Weekly", "Monthly", "Yearly"])
        self.r_mode = QComboBox(); self.r_mode.addItems(["Manual", "Automatic"])
        self.save_r_btn = QPushButton("SAVE RECURRING BILL"); self.save_r_btn.setObjectName("AddBtn"); self.save_r_btn.clicked.connect(self.save_recurring)
        
        for w in (self.r_name, self.r_amt, self.r_date, self.r_cycle, self.r_mode, self.save_r_btn): r_lay.addWidget(w)
        self.rec_list = QListWidget(); r_lay.addWidget(self.rec_list)
        self.content_stack.addWidget(rec_card)

        # SUB-PAGE: ONE-TIME DUES
        one_card = QFrame(); one_card.setObjectName("MainCard"); o_lay = QVBoxLayout(one_card)
        o_lay.addWidget(QLabel("ONE-TIME PAYMENTS"))
        self.o_name = QLineEdit(); self.o_name.setPlaceholderText("Description")
        self.o_amt = QLineEdit(); self.o_amt.setPlaceholderText("Amount")
        self.o_date = QDateEdit(); self.o_date.setCalendarPopup(True); self.o_date.setDate(datetime.now().date())
        self.save_o_btn = QPushButton("ADD ONE-TIME DUE"); self.save_o_btn.setObjectName("AddBtn"); self.save_o_btn.clicked.connect(self.save_one_time)
        
        for w in (self.o_name, self.o_amt, self.o_date, self.save_o_btn): o_lay.addWidget(w)
        self.one_list = QListWidget(); o_lay.addWidget(self.one_list)
        self.content_stack.addWidget(one_card)

        main_hbox.addWidget(self.content_stack, 4); self.root_stack.addWidget(main_page)

    # --- VALIDATION HELPERS ---
    def validate_inputs(self, name, amt, qdate):
        """ Prevents empty names, non-numeric amounts, or historical dates for future bills. """
        if not name.strip() or not amt.strip():
            QMessageBox.warning(self, "Input Error", "Name and Amount cannot be empty.")
            return False
        try:
            if float(amt) <= 0: raise ValueError
        except:
            QMessageBox.warning(self, "Input Error", "Enter a valid positive number.")
            return False
        if qdate.toPython() < datetime.now().date():
            QMessageBox.critical(self, "Date Error", "Past dates are not allowed. The system tracks future payments.")
            return False
        return True

    # --- CORE LOGIC ---
    def handle_login(self):
        """ Manages user session. Creates a new user entry if the name doesn't exist. """
        u, p = self.u_in.text().strip(), self.p_in.text().strip()
        if not u or not p: return
        
        if u not in self.users:
            self.users[u] = {"password":p, "balance":0.0, "history":[], "vault_bal":0.0, "vault_time":"", "subs":[], "one_times":[], "last_open": datetime.now().isoformat()}
        elif self.users[u]["password"] != p:
            QMessageBox.warning(self, "Error", "Wrong password."); return
        
        self.current_user = u
        self.process_auto_bills() # Catch up on missed payments while the app was closed
        self.users[u]["last_open"] = datetime.now().isoformat()
        self.save_data(); self.refresh_ui(); self.root_stack.setCurrentIndex(1)

    def handle_logout(self): 
        self.current_user = None; self.root_stack.setCurrentIndex(0)

    def process_auto_bills(self):
        """ 
        Background Logic: Checks if 'Automatic' bills are due or overdue.
        Uses a while loop to handle cases where the app wasn't opened for months.
        """
        user = self.users[self.current_user]
        now = datetime.now().date()
        
        for b in user.get("subs", []):
            if b.get("mode") == "Automatic":
                while datetime.fromisoformat(b["next_date"]).date() <= now:
                    self.pay_item(b, "subs", silent=True)

    def pay_item(self, item, cat, silent=False):
        """
        Deducts money from balance and creates a history record.
        If it's a subscription, it calculates the next billing date.
        """
        user = self.users[self.current_user]
        user["balance"] -= item["amt"]
        user["history"].insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "amt": item["amt"], "note": f"System/User Paid: {item['name']}"})
        
        if cat == "one_times":
            # Remove from list once paid
            user["one_times"] = [i for i in user["one_times"] if i["id"] != item["id"]]
        else:
            # Shift the date forward based on cycle
            days = {"Daily": 1, "Weekly": 7, "Monthly": 30, "Yearly": 365}[item["cycle"]]
            next_d = datetime.fromisoformat(item["next_date"]) + timedelta(days=days)
            item["next_date"] = next_d.date().isoformat()
        
        if not silent: self.save_data(); self.refresh_ui()

    def refresh_ui(self):
        """ Updates all labels, lists, and colors on the screen based on current data. """
        user = self.users[self.current_user]
        nw = user['balance'] + user.get('vault_bal', 0.0)
        
        self.net_worth_label.setText(f"Total Net Worth: ₱{nw:,.2f}")
        self.bal_label.setText(f"₱{user['balance']:,.2f}")
        
        # Color the balance red if in debt (negative)
        self.bal_label.setStyleSheet(f"font-size: 45px; font-weight: bold; color: {'#EF4444' if user['balance'] < 0 else '#22C55E'};")
        
        self.due_summary.clear(); self.rec_list.clear(); self.one_list.clear(); self.history_list.clear()
        now = datetime.now().date()
        
        # Populate History
        for h in user["history"]: 
            self.history_list.addItem(f"{h['time']} | {h['note']} (₱{h['amt']:,.2f})")

        # Populate Recurring Bills & check for overdue
        for b in user.get("subs", []):
            if datetime.fromisoformat(b["next_date"]).date() <= now: 
                self.due_summary.addItem(f"OVERDUE: {b['name']} (₱{b['amt']})")
            self.render_row(self.rec_list, b, "subs")
            
        # Populate One-Time Dues
        for o in user.get("one_times", []):
            if datetime.fromisoformat(o["date"]).date() <= now: 
                self.due_summary.addItem(f"DUE NOW: {o['name']} (₱{o['amt']})")
            self.render_row(self.one_list, o, "one_times")

    def render_row(self, list_w, data, cat):
        """ 
        Creates a custom widget for each list item containing 
        the description and action buttons (Pay, Edit, Del). 
        """
        item = QListWidgetItem(list_w); row = QWidget(); lay = QHBoxLayout(row)
        d_key = "next_date" if cat == "subs" else "date"
        lay.addWidget(QLabel(f"<b>{data['name']}</b> | ₱{data['amt']:,.2f} | Due: {data[d_key]}"))
        
        p_btn = QPushButton("Pay Now"); p_btn.setObjectName("ActionBtn")
        p_btn.clicked.connect(lambda _, x=data, c=cat: self.pay_item(x, c))
        
        e_btn = QPushButton("Edit"); e_btn.setObjectName("ActionBtn")
        e_btn.clicked.connect(lambda _, x=data, c=cat: self.start_edit(x, c))
        
        d_btn = QPushButton("Del"); d_btn.setObjectName("DeleteBtn")
        d_btn.clicked.connect(lambda _, x=data['id'], c=cat: self.delete_item(c, x))
        
        lay.addStretch(); lay.addWidget(p_btn); lay.addWidget(e_btn); lay.addWidget(d_btn)
        item.setSizeHint(row.sizeHint()); list_w.setItemWidget(item, row)

    def save_recurring(self):
        """ Logic to either append a new bill or update an existing one in the subs list. """
        if not self.validate_inputs(self.r_name.text(), self.r_amt.text(), self.r_date.date()): return
        user = self.users[self.current_user]
        bill = {"id": self.editing_id or str(datetime.now().timestamp()), "name": self.r_name.text(), 
                "amt": float(self.r_amt.text()), "next_date": self.r_date.date().toPython().isoformat(), 
                "cycle": self.r_cycle.currentText(), "mode": self.r_mode.currentText()}
        
        if self.editing_id: 
            user["subs"] = [bill if b["id"] == self.editing_id else b for b in user["subs"]]
        else: 
            user["subs"].append(bill)
            
        self.editing_id = None
        self.save_r_btn.setText("SAVE RECURRING BILL")
        self.save_data(); self.refresh_ui()
        self.r_name.clear(); self.r_amt.clear()

    def save_one_time(self):
        """ Logic to save one-time payment entries. """
        if not self.validate_inputs(self.o_name.text(), self.o_amt.text(), self.o_date.date()): return
        user = self.users[self.current_user]
        due = {"id": self.editing_id or str(datetime.now().timestamp()), "name": self.o_name.text(), 
               "amt": float(self.o_amt.text()), "date": self.o_date.date().toPython().isoformat()}
        
        if self.editing_id: 
            user["one_times"] = [due if o["id"] == self.editing_id else o for o in user["one_times"]]
        else: 
            user["one_times"].append(due)
            
        self.editing_id = None
        self.save_o_btn.setText("ADD ONE-TIME DUE")
        self.save_data(); self.refresh_ui()
        self.o_name.clear(); self.o_amt.clear()

    def process_money(self, mode):
        """ Manual income/expense entry from the dashboard. """
        try:
            amt = float(self.amt_in.text())
            user = self.users[self.current_user]
            user["balance"] += amt if mode == "plus" else -amt
            user["history"].insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "amt": amt, "note": self.item_in.text()})
            self.save_data(); self.refresh_ui(); self.amt_in.clear(); self.item_in.clear()
        except: QMessageBox.warning(self, "Error", "Invalid Amount.")

    def manage_vault(self):
        """ 
        Unique Feature: Locks money for 10 seconds. 
        If the vault is empty, you can put money in. 
        If 10s has passed, you can withdraw it back to balance. 
        """
        user = self.users[self.current_user]
        # Check if the timer has expired to allow withdrawal
        if user.get("vault_time") and datetime.now() >= datetime.fromisoformat(user["vault_time"]):
            user["balance"] += user["vault_bal"]; user["vault_bal"], user["vault_time"] = 0.0, ""
            self.save_data(); self.refresh_ui(); return
            
        # Otherwise, offer to lock money
        amt, ok = QInputDialog.getDouble(self, "Vault", "Amount to lock (10s):", 0, 0, 1000000, 2)
        if ok and amt > 0:
            user["vault_bal"], user["vault_time"] = amt, (datetime.now() + timedelta(seconds=10)).isoformat()
            self.save_data(); self.refresh_ui()

    def start_edit(self, b, cat):
        """ Populates input forms with existing data to allow modifications. """
        self.editing_id = b["id"]
        if cat == "subs":
            self.r_name.setText(b["name"]); self.r_amt.setText(str(b["amt"]))
            self.r_date.setDate(datetime.fromisoformat(b["next_date"]).date())
            self.save_r_btn.setText("UPDATE RECURRING BILL"); self.content_stack.setCurrentIndex(1)
        else:
            self.o_name.setText(b["name"]); self.o_amt.setText(str(b["amt"]))
            self.o_date.setDate(datetime.fromisoformat(b["date"]).date())
            self.save_o_btn.setText("UPDATE ONE-TIME DUE"); self.content_stack.setCurrentIndex(2)

    def delete_item(self, cat, item_id):
        """ Removes an item from the user's list and saves. """
        self.users[self.current_user][cat] = [i for i in self.users[self.current_user][cat] if i["id"] != item_id]
        self.save_data(); self.refresh_ui()

# Application Entry Point
if __name__ == "__main__":
    app = QApplication([]); win = MainWindow(); win.show(); app.exec()
