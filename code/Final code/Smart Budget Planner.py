import sys, os, json, re, time
from datetime import datetime, timedelta
from google import genai
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import *
from PySide6.QtGui import QTextCursor

# ==========================================================
# CONFIGURATION
# ==========================================================
API_KEY = "PLACE YOUR API KEY HERE"
MODEL_ID = "gemini-3.1-flash-lite-preview"
DATA_FILE = "users_data.json"

STYLE_SHEET = """
QMainWindow, QWidget { 
    background-color: #0F172A; 
    color: #E5E7EB; 
    font-family: 'Arial'; 
}

#SidebarBox { background-color: #111827; border-radius: 10px; padding: 10px; }
#DashBtn { background-color: #3B82F6; color: white; border-radius: 8px; padding: 10px; border: none; font-weight: bold; }
#AIBtn { background-color: #A855F7; color: white; border-radius: 8px; padding: 10px; border: none; font-weight: bold; }
#SettingsBtn { background-color: #475569; color: white; border-radius: 8px; padding: 10px; border: none; font-weight: bold; }
#LogoutBtn { background-color: #F97316; color: white; border-radius: 8px; padding: 10px; border: none; font-weight: bold; }
#SignupBtn { background-color: #10B981; color: white; border-radius: 8px; padding: 10px; border: none; }

#MainCard { background-color: #1E293B; border-radius: 10px; padding: 20px; }

QLineEdit, QTextEdit, QComboBox { 
    padding: 10px; background-color: #0F172A; color: white; 
    border: 1px solid #334155; border-radius: 6px; margin: 5px 0;
}

#BalanceLabel { color: #22C55E; font-size: 45px; font-weight: bold; background: transparent; }
#NetWorthLabel { color: #94A3B8; font-size: 16px; background: transparent; }

#AddBtn { background-color: #22C55E; color: white; font-weight: bold; border-radius: 8px; height: 40px; }
#SpendBtn { background-color: #EF4444; color: white; font-weight: bold; border-radius: 8px; height: 40px; }
#VaultBtn { background-color: #EAB308; color: #000000; font-weight: 900; border-radius: 8px; height: 45px; margin-top: 10px; }

QListWidget { background-color: #0F172A; border-radius: 6px; border: none; padding: 5px; }

QTableWidget { background-color: #1E293B; color: white; border: 1px solid #334155; }
QHeaderView::section { background-color: #111827; color: #E5E7EB; padding: 5px; border: 1px solid #334155; }
"""

class AIWorker(QThread):
    finished = Signal(str)
    def __init__(self, client, model_id, prompt):
        super().__init__()
        self.client, self.model_id, self.prompt = client, model_id, prompt
    def run(self):
        try:
            res = self.client.models.generate_content(model=self.model_id, contents=self.prompt)
            self.finished.emit(res.text if res.text else "AI returned no text.")
        except Exception as e: self.finished.emit(f"Error: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client = genai.Client(api_key=API_KEY)
        self.current_model = MODEL_ID
        self.users = self.load_data()
        self.current_user = None
        self.setWindowTitle("Smart Budget Planner")
        self.resize(1100, 850)
        self.setStyleSheet(STYLE_SHEET)
        self.setup_ui()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        with open(DATA_FILE, "w") as f: json.dump(self.users, f, indent=4)

    def setup_ui(self):
        self.root_stack = QStackedWidget(); self.setCentralWidget(self.root_stack)
        
        login_page = QWidget(); l_lay = QVBoxLayout(login_page); l_lay.addStretch()
        title = QLabel("BUDGET PLANNER"); title.setStyleSheet("font-size: 45px; font-weight: bold; color: #3B82F6;")
        l_lay.addWidget(title, alignment=Qt.AlignCenter)
        self.u_in = QLineEdit(); self.u_in.setPlaceholderText("Username")
        self.p_in = QLineEdit(); self.p_in.setPlaceholderText("Password"); self.p_in.setEchoMode(QLineEdit.Password)
        for w in (self.u_in, self.p_in): w.setFixedWidth(320); l_lay.addWidget(w, alignment=Qt.AlignCenter)
        btn_l = QPushButton("Login"); btn_l.setObjectName("DashBtn"); btn_l.clicked.connect(self.handle_login)
        btn_s = QPushButton("Create Account"); btn_s.setObjectName("SignupBtn"); btn_s.clicked.connect(self.handle_signup)
        for b in (btn_l, btn_s): b.setFixedWidth(320); l_lay.addWidget(b, alignment=Qt.AlignCenter)
        l_lay.addStretch(); self.root_stack.addWidget(login_page)

        main_page = QWidget(); main_hbox = QHBoxLayout(main_page)
        sidebar_w = QFrame(); sidebar_w.setObjectName("SidebarBox"); sidebar_w.setFixedWidth(200)
        sidebar = QVBoxLayout(sidebar_w)
        navs = [("Dashboard", "DashBtn", 0), ("AI Bot", "AIBtn", 1), ("Error Guide", "SettingsBtn", 2)]
        for text, obj, idx in navs:
            btn = QPushButton(text); btn.setObjectName(obj)
            btn.clicked.connect(lambda _, i=idx: self.content_stack.setCurrentIndex(i))
            sidebar.addWidget(btn)
        logout = QPushButton("Logout"); logout.setObjectName("LogoutBtn"); logout.clicked.connect(self.handle_logout)
        sidebar.addStretch(); sidebar.addWidget(logout); main_hbox.addWidget(sidebar_w)

        self.content_stack = QStackedWidget()
        
        dash_card = QFrame(); dash_card.setObjectName("MainCard"); d_lay = QVBoxLayout(dash_card)
        self.net_worth_label = QLabel("Total Net Worth: ₱0.00"); self.net_worth_label.setObjectName("NetWorthLabel")
        d_lay.addWidget(self.net_worth_label)
        d_lay.addWidget(QLabel("YOUR BALANCE:"))
        self.bal_label = QLabel("₱0.00"); self.bal_label.setObjectName("BalanceLabel")
        d_lay.addWidget(self.bal_label)
        
        self.item_in = QLineEdit(); self.item_in.setPlaceholderText("Description")
        self.amt_in = QLineEdit(); self.amt_in.setPlaceholderText("Amount")
        d_lay.addWidget(self.item_in); d_lay.addWidget(self.amt_in)
        
        b_row = QHBoxLayout()
        add_b = QPushButton("ADD"); add_b.setObjectName("AddBtn"); add_b.clicked.connect(lambda: self.process_money("plus"))
        exp_b = QPushButton("SPEND"); exp_b.setObjectName("SpendBtn"); exp_b.clicked.connect(lambda: self.process_money("minus"))
        b_row.addWidget(add_b); b_row.addWidget(exp_b); d_lay.addLayout(b_row)
        
        v_btn = QPushButton("INCOME VAULT"); v_btn.setObjectName("VaultBtn"); v_btn.clicked.connect(self.manage_vault)
        d_lay.addWidget(v_btn); d_lay.addWidget(QLabel("HISTORY"))
        self.history_list = QListWidget(); d_lay.addWidget(self.history_list)
        self.content_stack.addWidget(dash_card)

        ai_card = QFrame(); ai_card.setObjectName("MainCard"); ai_lay = QVBoxLayout(ai_card)
        self.ai_chat = QTextEdit(); self.ai_chat.setReadOnly(True)
        self.ai_input = QLineEdit(); self.ai_input.setPlaceholderText("Ask AI...")
        self.ai_input.returnPressed.connect(self.ask_ai)
        ai_lay.addWidget(self.ai_chat); ai_lay.addWidget(self.ai_input); self.content_stack.addWidget(ai_card)

        err_card = QFrame(); err_card.setObjectName("MainCard"); err_lay = QVBoxLayout(err_card)
        self.err_table = QTableWidget(4, 3); self.err_table.setHorizontalHeaderLabels(["Code", "Status", "Resolution"])
        self.err_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        err_data = [["404", "Model Missing", "Update AI"], ["503", "Overloaded", "Wait"], ["401", "Invalid Key", "Check API"], ["ValueErr", "Bad Input", "Numbers Only"]]
        for r, row in enumerate(err_data):
            for c, val in enumerate(row): 
                it = QTableWidgetItem(val); it.setFlags(Qt.ItemIsEnabled); self.err_table.setItem(r, c, it)
        err_lay.addWidget(QLabel("SYSTEM ERRORS")); err_lay.addWidget(self.err_table)
        self.model_box = QComboBox(); self.model_box.addItems(["gemini-3.1-flash-lite-preview", "gemini-2.0-flash"])
        up_btn = QPushButton("Switch Model"); up_btn.setObjectName("DashBtn"); up_btn.clicked.connect(self.update_model)
        err_lay.addWidget(QLabel("AI ENGINE:")); err_lay.addWidget(self.model_box); err_lay.addWidget(up_btn); err_lay.addStretch()
        self.content_stack.addWidget(err_card)

        main_hbox.addWidget(self.content_stack, 4); self.root_stack.addWidget(main_page)

    def handle_login(self):
        u, p = self.u_in.text().strip(), self.p_in.text().strip()
        if u in self.users:
            if self.users[u]["password"] == p:
                self.current_user = u
                self.refresh_ui(); self.root_stack.setCurrentIndex(1)
            else:
                QMessageBox.warning(self, "Login Failed", "Incorrect password. Please try again.")
        else:
            QMessageBox.warning(self, "Login Failed", "Username not found. Please create an account.")

    def handle_signup(self):
        u, p = self.u_in.text().strip(), self.p_in.text().strip()
        if not u or not p:
            QMessageBox.critical(self, "Signup Error", "Username and Password cannot be empty.")
            return
        if u in self.users:
            QMessageBox.warning(self, "Signup Error", f"The username '{u}' is already taken.")
            return
        self.users[u] = {"password": p, "balance": 0.0, "history": [], "vault_bal": 0.0, "vault_time": ""}
        self.save_data(); QMessageBox.information(self, "Success", "Account created successfully!")

    def handle_logout(self): self.current_user = None; self.root_stack.setCurrentIndex(0)

    def refresh_ui(self):
        user = self.users[self.current_user]
        nw = user['balance'] + user.get('vault_bal', 0.0)
        self.net_worth_label.setText(f"Total Net Worth: ₱{nw:,.2f}")
        self.bal_label.setText(f"₱{user['balance']:,.2f}")
        self.bal_label.setStyleSheet(f"font-size: 45px; font-weight: bold; color: {'#EF4444' if user['balance'] < 0 else '#22C55E'};")
        self.history_list.clear()
        for i, item in enumerate(user["history"]):
            li = QListWidgetItem(self.history_list)
            row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(5, 5, 5, 5)
            note = item.get('note', ''); is_v = "Vault" in note; is_i = "Initial" in note
            col = "#EAB308" if is_v else ("#22C55E" if item['mode'] == "plus" else "#EF4444")
            txt = QLabel(f"<span style='color:#94A3B8;'>{item['time']}</span> | <b>{note}</b> <span style='color:{col};'>(₱{item['amt']:,.2f})</span>")
            lay.addWidget(txt); lay.addStretch()
            if not is_v and not is_i:
                btn_s = "background-color: #334155; border-radius: 4px; padding: 2px;"
                ed = QPushButton("📝"); ed.setFixedSize(22, 22); ed.setStyleSheet(btn_s); ed.clicked.connect(lambda _, x=i: self.edit_entry(x))
                dl = QPushButton("✕"); dl.setFixedSize(22, 22); dl.setStyleSheet(btn_s); dl.clicked.connect(lambda _, x=i: self.delete_entry(x))
                lay.addWidget(ed); lay.addWidget(dl)
            li.setSizeHint(row.sizeHint()); self.history_list.addItem(li); self.history_list.setItemWidget(li, row)

    def process_money(self, mode):
        raw_amt = self.amt_in.text().strip()
        if not raw_amt:
            QMessageBox.critical(self, "Invalid Action", "The Amount field is empty. Please enter a value to proceed.")
            return
        try:
            amt = float(raw_amt)
        except ValueError:
            QMessageBox.warning(self, "Input Error", f"'{raw_amt}' contains invalid characters. Please enter numbers only.")
            return
        if amt <= 0:
            QMessageBox.information(self, "Calculation Error", "Amount must be greater than zero.")
            return
        user = self.users[self.current_user]
        if mode == "minus" and amt > user["balance"]:
            reply = QMessageBox.question(self, "Warning", "This will result in a negative balance. Proceed?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        user["balance"] += amt if mode == "plus" else -amt
        user["history"].insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "mode": mode, "amt": amt, "note": self.item_in.text() or "General"})
        self.save_data(); self.refresh_ui(); self.amt_in.clear(); self.item_in.clear()

    def manage_vault(self):
        user = self.users[self.current_user]
        if user.get("vault_time"):
            end = datetime.fromisoformat(user["vault_time"])
            if datetime.now() >= end:
                v = user["vault_bal"]; user["balance"] += v
                user["history"].insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "mode": "plus", "amt": v, "note": "Vault Release"})
                user["vault_bal"], user["vault_time"] = 0.0, ""; self.save_data(); self.refresh_ui()
                QMessageBox.information(self, "Vault", f"₱{v:,.2f} released!")
            else:
                rem = str(end - datetime.now()).split(".")[0]
                QMessageBox.warning(self, "Locked", f"Remaining: {rem}")
            return
        amt, ok1 = QInputDialog.getDouble(self, "Vault", "Amount:", 0)
        t_str, ok2 = QInputDialog.getText(self, "Timer", "Time (10s, 5m, 1h):")
        if ok1 and ok2:
            m = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000, "y": 31536000}
            try:
                val = int(''.join(filter(str.isdigit, t_str)))
                unit = ''.join(filter(str.isalpha, t_str))
                seconds = val * m.get(unit, 60)
                user["vault_bal"], user["vault_time"] = amt, (datetime.now() + timedelta(seconds=seconds)).isoformat()
                user["history"].insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "mode": "none", "amt": amt, "note": "Vault Locked"})
                self.save_data(); self.refresh_ui()
            except: pass

    def edit_entry(self, idx):
        user = self.users[self.current_user]; item = user["history"][idx]
        new, ok = QInputDialog.getDouble(self, "Edit", "New Amount:", item["amt"])
        if ok:
            diff = new - item["amt"]; user["balance"] += diff if item["mode"] == "plus" else -diff
            item["amt"] = new; self.save_data(); self.refresh_ui()

    def delete_entry(self, idx):
        user = self.users[self.current_user]; item = user["history"][idx]
        user["balance"] -= item["amt"] if item["mode"] == "plus" else -item["amt"]
        user["history"].pop(idx); self.save_data(); self.refresh_ui()

    def ask_ai(self):
        txt = self.ai_input.text().strip()
        if not txt: return
        self.ai_chat.append(f"<b>You:</b> {txt}")
        self.worker = AIWorker(self.client, self.current_model, f"Balance: {self.users[self.current_user]['balance']}. User: {txt}")
        self.worker.finished.connect(lambda r: self.ai_chat.append(f"<b>AI:</b> {r}<br>"))
        self.worker.start(); self.ai_input.clear()

    def update_model(self): self.current_model = self.model_box.currentText()

if __name__ == "__main__":
    app = QApplication(sys.argv); win = MainWindow(); win.show(); sys.exit(app.exec())
