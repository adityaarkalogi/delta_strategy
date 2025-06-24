from datetime import datetime
import os
import sys
import time
import uuid
from dotenv import load_dotenv
import pytz
import redis
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLabel, QWidget, QTableWidget, 
    QTableWidgetItem, QGridLayout, QLineEdit, QPushButton, QComboBox, QHBoxLayout,
    QTabWidget, QTextEdit
)
from PyQt5.QtGui import QFont, QIcon, QKeyEvent
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QTimeEdit, QSpinBox, QMessageBox, QCheckBox, QHeaderView, QDoubleSpinBox
from PyQt5.QtCore import QTime, QThread, pyqtSignal, QDateTime
from PyQt5.QtGui import QDoubleValidator, QIntValidator

load_dotenv(".env")

FE_ID = str(uuid.uuid4().hex)
USER_INPUT = "user_input"
BACKEND_COM = f"backend_com_{FE_ID}"
REDIS_HOST = os.environ.get("USER_COMM_HOST")
REDIS_PORT = os.environ.get("USER_COMM_PORT")


class RedisListener(QThread):
    new_message = pyqtSignal(dict)

    def __init__(self, pubsub):
        super().__init__()
        self.pubsub = pubsub
        self.running = True

    def run(self):
        while self.running:
            message = self.pubsub.get_message()
            if message and message['type'] == 'message':
                self.new_message.emit(json.loads(message['data']))  # Send safely to UI
            time.sleep(0.001)

    def stop(self):
        self.running = False

class NoPlusLineEdit(QLineEdit):
    def keyPressEvent(self, event: QKeyEvent):
        if event.text() == '+':
            return  # Do nothing. Block the key.
        super().keyPressEvent(event)

class TradingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.start_ui = False
        self.possible_restart = True
        self.setWindowTitle("Shifting Strategy")
        self.setWindowIcon(QIcon("logo.ico"))  # Set application icon
        # self.setMinimumSize(1200, 700)  # Ensure a minimum size

        # Tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Strategy Tab
        self.strategy_tab = QWidget()
        self.strategy_layout = QVBoxLayout()
        self.strategy_tab.setLayout(self.strategy_layout)
        self.tabs.addTab(self.strategy_tab, "Strategy")

        # Create a horizontal layout for the top section
        top_layout = QHBoxLayout()

        # LTP Label
        self.ltp_lable = QLabel("NIFTY:  0.0\nBANKNIFTY:  0.0", self)
        self.ltp_lable.setFont(QFont("Modern Sans-Serif", 12))
        self.ltp_lable.setAlignment(Qt.AlignLeft)
        self.ltp_lable.setFixedWidth(250)
        self.ltps = {}

        # P&L Label
        self.pnl_label = QLabel("P&L: ₹ 0.0", self)
        self.pnl_label.setFont(QFont("Modern Sans-Serif", 16, QFont.Bold))
        self.pnl_label.setStyleSheet("color: black;")  # Set text color for negative P&L
        self.pnl_label.setAlignment(Qt.AlignCenter)

        # Status & Message Layout (Stacked)
        status_layout = QVBoxLayout()

        # Status Label
        self.status_label = QLabel("STATUS: PENDING", self)
        self.status_label.setFont(QFont("Modern Sans-Serif", 15, QFont.Bold))
        self.status_label.setAlignment(Qt.AlignRight)

        # Message Label
        self.message_label = QLabel("Message:                        ", self)
        self.message_label.setFont(QFont("Modern Sans-Serif", 12))
        self.message_label.setAlignment(Qt.AlignRight)
        self.message_label.setFixedWidth(500)
        self.message_label.setWordWrap(True)


        # Add Status & Message into vertical layout
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.message_label)

        # Add widgets to the top layout
        top_layout.addWidget(self.ltp_lable)
        top_layout.addStretch(1)
        top_layout.addWidget(self.pnl_label)
        top_layout.addStretch(1)
        top_layout.addLayout(status_layout)

        # Add the top layout to the strategy layout
        self.strategy_layout.addLayout(top_layout)
        self.strategy_params = {
            "underlying": "NIFTY",
            "expiry_type": "WEEKLY",
            "lots": 1.0,
            "call_strike": "",
            "put_strike": "",
            "strike_diff_percentage": 20.0,
            "shift_diff_multiplier": 2.0,
            "take_profit": 0.0,
            "stop_loss": 0.0,
            "sq_off_time": "151500",
            "hedge_selected": False,
            "hedge_premium": 5,
            "hedge_comp_op": ">=",
            "shift_delay": 20.0,
            "sq_off_on_shift_after_same_strike": True,
            "no_shift_if_ltp_below_price": True
        }
        self.strategy_inputs = {}  
        self.key_name = {
            "underlying": "Underlying",
            "expiry_type": "Expiry Type",
            "lots": "Number of Lots",
            "call_strike": "Call Strike",
            "put_strike": "Put Strike",
            "hedge": "Hedge Price (₹)",
            "sq_off_on_shift_after_same_strike": "Same Strike-Based Auto Exit",
            "strike_diff_percentage": "Strike Difference (%)",
            "shift_diff_multiplier": "Shift Diff Multiplier",
            "shift_delay": "Shift Delay (Sec)",
            "take_profit": "Take Profit (₹)",
            "stop_loss": "Stop Loss (₹)",
            "sq_off_time": "Square Off Time",
            "reduce_qty" : "Reduce Quantity (%)",
            "no_shift_if_ltp_below_price" : "Don't Shift if LTP Below Entry"
        }
        self.fields_to_disable = [
            "underlying", "expiry_type", "lots", "call_strike",
            "put_strike", "hedge", "strike_diff_percentage",
            "sq_off_on_shift_after_same_strike"
        ]
        self.create_strategy_input_section()

        # Positions Table
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(8)
        self.positions_table.setHorizontalHeaderLabels(
            ["Symbol", "Average Sell Price", "Sell Quantity", "Average Buy Price", "Buy Quantity" , "Net Quantity" , "P&L", "LTP"]
        )
        self.setup_table(self.positions_table)
        self.strategy_layout.addWidget(self.positions_table)

        # SQ Off Positions Table
        self.sq_off_table = QTableWidget()
        self.sq_off_table.setColumnCount(8)
        self.sq_off_table.setHorizontalHeaderLabels(
            ["Symbol", "Average Sell Price", "Sell Quantity", "Average Buy Price", "Buy Quantity" , "Net Quantity" , "P&L", "LTP"]
        )
        self.setup_table(self.sq_off_table)
        self.strategy_layout.addWidget(self.sq_off_table)

        self.add_table_with_label("Open Positions", self.positions_table)
        self.add_table_with_label("Closed Positions", self.sq_off_table)

        # Redis Setup
        self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(BACKEND_COM)
        self.redis_client.delete(USER_INPUT)
        start_msg = {"type": "CONNECT", "fe_id":FE_ID}
        self.redis_client.rpush(USER_INPUT, json.dumps(start_msg))
        self.strategy_inputs['reduce_qty'].setDisabled(True)

        # Data storage
        self.positions = {}
        self.sq_off_positions = {}

        # Start Redis listener in a separate thread
        self.redis_listener = RedisListener(self.pubsub)
        self.redis_listener.new_message.connect(self.process_message)  # Connect signal
        self.redis_listener.start()  # Start thread

        # Timer to refresh UI
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_tables)
        self.timer.start(200)

        # Messages Tab
        self.messages_tab = QWidget()
        self.messages_layout = QVBoxLayout()
        self.messages_tab.setLayout(self.messages_layout)

        self.message_box = QTextEdit()
        self.message_box.setReadOnly(True)
        self.message_box.setFont(QFont("Modern Sans-Serif", 12))
        self.messages_layout.addWidget(self.message_box)
        self.tabs.addTab(self.messages_tab, "Messages")
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                font-size: 10pt;
                min-width: 140px;
            }
            QTabBar::tab:selected {
                font-weight: bold;
                color: #2c3e50;
                border-bottom: 2px solid #2c3e50;
            }
            QTabBar::tab:!selected {
                color: #7f8c8d;
            }
        """)


    def log_message(self, msg):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.message_box.append(f"[{timestamp}]: {msg}")

    def closeEvent(self, event):
        """Ask for confirmation before closing the application."""
        if self.status_label.text() == "STATUS: RUNNING":
            reply = QMessageBox.question(
                self, "Running Strategy", 
                "Strategy is Running, Are you sure you want to exit",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                reply = QMessageBox.question(
                    self, "Confirmation", 
                    "Are you sure?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
        else:
            reply = QMessageBox.question(
                self, "Exit Confirmation", 
                "Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
        if reply == QMessageBox.Yes:
            self.redis_listener.stop()
            self.redis_listener.stop()
            event.accept()
        else:
            event.ignore()

    def add_table_with_label(self, label_text, table_widget):
        """ Adds a table with a centered title above it """
        label = QLabel(label_text, self)
        label.setFont(QFont("Modern Sans-Serif", 14, QFont.Bold))
        label.setAlignment(Qt.AlignCenter)  # Center the label

        self.strategy_layout.addWidget(label)
        self.strategy_layout.addWidget(table_widget)

    def create_strategy_input_section(self):
        """Creates a grid layout for strategy parameters with 4 fields on the left and 5 on the right."""
        strategy_widget = QWidget()
        strategy_layout = QGridLayout()
        strategy_widget.setLayout(strategy_layout)

        self.strategy_layout.addWidget(strategy_widget)

        labels = [
            "underlying", "expiry_type", "lots", "call_strike",
            "put_strike", "hedge", "sq_off_on_shift_after_same_strike",
            "no_shift_if_ltp_below_price", "strike_diff_percentage", "shift_diff_multiplier", 
            "shift_delay", "take_profit", "stop_loss", "sq_off_time",
            "reduce_qty"
        ]


        left_fields = labels[:8]   # First half fields on the left
        right_fields = labels[8:]  # Last half fields on the right

        row = 0
        for key in left_fields:
            label = QLabel(self.key_name[key] + ":")
            label.setFont(QFont("Modern Sans-Serif", 11))  # Smaller font
            strategy_layout.addWidget(label, row, 0)

            input_field = self.create_input_field(key)
            strategy_layout.addWidget(input_field, row, 1)
            self.strategy_inputs[key] = input_field

            row += 1

        row = 0
        for key in right_fields:
            label = QLabel(self.key_name[key] + ":")
            label.setFont(QFont("Modern Sans-Serif", 12))  # Smaller font
            strategy_layout.addWidget(label, row, 2)

            input_field = self.create_input_field(key)
            strategy_layout.addWidget(input_field, row, 3)
            self.strategy_inputs[key] = input_field

            row += 1

        # Button Layout (Apply, Start, Update)
        button_layout = QHBoxLayout()

        apply_button = QPushButton("Apply")
        apply_button.setFont(QFont("Modern Sans-Serif", 12))
        apply_button.clicked.connect(self.apply_strategy)
        button_layout.addWidget(apply_button)

        self.start_button = QPushButton("Start")
        self.start_button.setFont(QFont("Modern Sans-Serif", 12))
        self.start_button.clicked.connect(self.start_strategy)
        button_layout.addWidget(self.start_button)

        self.update_button = QPushButton("Update")
        self.update_button.setFont(QFont("Modern Sans-Serif", 12))
        self.update_button.clicked.connect(self.update_strategy)
        button_layout.addWidget(self.update_button)
        self.update_button.setDisabled(True)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setFont(QFont("Modern Sans-Serif", 12))
        self.stop_button.clicked.connect(self.stop_strategy)
        button_layout.addWidget(self.stop_button)
        self.stop_button.setDisabled(True)

        strategy_layout.addLayout(button_layout, max(len(left_fields), len(right_fields)), 0, 1, 4)

    def create_input_field(self, key):
        """Creates the appropriate input field based on the key."""
        if key == "underlying":
            input_field = QComboBox()
            input_field.addItems(["NIFTY", "BANKNIFTY"])
            input_field.setCurrentText(self.strategy_params[key])
            input_field.currentTextChanged.connect(self.update_expiry_options)  # Link update function
            self.underlying_input = input_field  # Store reference

        elif key == "expiry_type":
            self.expiry_input = QComboBox()
            self.expiry_input.addItems(["WEEKLY", "NEXTWEEKLY", "MONTHLY"])  # Default all
            self.expiry_input.setCurrentText(self.strategy_params[key])
            self.expiry_input.setFont(QFont("Modern Sans-Serif", 12))
            return self.expiry_input

        elif key == "sq_off_time":
            input_field = QTimeEdit()
            input_field.setMinimumTime(QTime(9, 15))
            input_field.setMaximumTime(QTime(15, 29))
            input_field.setDisplayFormat("HH:mm")  # Display format without seconds
            input_field.setTime(QTime(int(self.strategy_params[key][:-4]), int(self.strategy_params[key][-4:-2])))  # Default value

        elif key == "lots":
            input_field = QSpinBox()
            input_field.setMinimum(1)  # Ensure positive numbers only
            input_field.setMaximum(100)  # Set an upper limit (adjust as needed)
            input_field.setValue(int(self.strategy_params.get(key, 1)))  # Default to 1
            input_field.setFont(QFont("Modern Sans-Serif", 12))
        
        elif key == "sq_off_on_shift_after_same_strike":
            input_field = QCheckBox()
            input_field.setFont(QFont("Modern Sans-Serif", 12))
            input_field.setChecked(self.strategy_params.get(key, True))

        elif key == "no_shift_if_ltp_below_price":
            input_field = QCheckBox()
            input_field.setFont(QFont("Modern Sans-Serif", 12))
            input_field.setChecked(self.strategy_params.get(key, False))

        elif key == "hedge":
            container = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)  # Remove extra padding

            # Dropdown for "<=" or ">="
            operator_dropdown = QComboBox()
            operator_dropdown.addItems(["<=", ">="])
            operator_dropdown.setFont(QFont("Modern Sans-Serif", 12))

            # Number input
            hedge_checkbox = QCheckBox()
            hedge_checkbox.setFont(QFont("Modern Sans-Serif", 12))
            hedge_checkbox.setChecked(False)  # Default checked

            # hedge_value = QLineEdit(str(self.strategy_params["hedge_premium"]))
            hedge_value = NoPlusLineEdit(str(self.strategy_params["hedge_premium"]))
            hedge_value.setFont(QFont("Modern Sans-Serif", 12))
            validator = QDoubleValidator(0.0, 9999999.99, 2)  # Min: 0.0, Max: Large, 2 decimal places
            validator.setNotation(QDoubleValidator.StandardNotation)
            hedge_value.setValidator(validator)

            hedge_checkbox.setChecked(self.strategy_params["hedge_selected"])
            def toggle_hedge_fields():
                is_checked = hedge_checkbox.isChecked()
                operator_dropdown.setEnabled(is_checked)
                hedge_value.setEnabled(is_checked)

            hedge_checkbox.stateChanged.connect(toggle_hedge_fields)
            toggle_hedge_fields()  # Set initial state

            layout.addWidget(hedge_checkbox)
            layout.addWidget(operator_dropdown)
            layout.addWidget(hedge_value)
            container.setLayout(layout)

            self.strategy_inputs[key] = (operator_dropdown, hedge_value)
            return container

        elif key == "shift_diff_multiplier":
            input_field = QDoubleSpinBox()
            input_field.setDecimals(1)
            input_field.setMinimum(1.0)
            input_field.setMaximum(100.0)
            input_field.setSingleStep(0.1)
            input_field.setValue(int(self.strategy_params[key]))
            input_field.setFont(QFont("Modern Sans-Serif", 12))
            return input_field

        elif key == "shift_delay":
            input_field = QDoubleSpinBox()
            input_field.setDecimals(1)
            input_field.setMinimum(0.0)
            input_field.setMaximum(100.0)
            input_field.setSingleStep(0.1)
            input_field.setValue(int(self.strategy_params[key]))
            input_field.setFont(QFont("Modern Sans-Serif", 12))

        elif key == "reduce_qty":
            container = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)  # Remove extra padding

            # Number input
            reduce_qty_checkbox = QCheckBox()
            reduce_qty_checkbox.setFont(QFont("Modern Sans-Serif", 12))
            reduce_qty_checkbox.setChecked(False)  # Default unchecked

            reduce_qty_precent_value = QDoubleSpinBox()
            reduce_qty_precent_value.setDecimals(1)
            reduce_qty_precent_value.setMinimum(0.0)
            reduce_qty_precent_value.setMaximum(100.0)
            reduce_qty_precent_value.setSingleStep(0.1)
            reduce_qty_precent_value.setFont(QFont("Modern Sans-Serif", 12))
            # reduce_qty_precent_value.setFixedWidth(680)

            layout.addWidget(reduce_qty_checkbox)
            layout.addWidget(reduce_qty_precent_value)
            container.setLayout(layout)

            self.strategy_inputs[key] = container
            return container

        else:
            input_field = NoPlusLineEdit(str(self.strategy_params[key]))
            input_field.setValidator(QDoubleValidator(0.01, 9999999.99, 2))

        input_field.setFont(QFont("Modern Sans-Serif", 12))
        return input_field
    
    def update_expiry_options(self, underlying):
        """ Update expiry type options based on selected underlying """
        self.expiry_input.clear()
        if underlying == "BANKNIFTY":
            self.expiry_input.addItem("MONTHLY")  # Only allow MONTHLY
        else:
            self.expiry_input.addItems(["WEEKLY", "NEXTWEEKLY", "MONTHLY"])  # Allow all options

    def apply_strategy(self):
        """Updates strategy locally."""
        for key, widget in self.strategy_inputs.items():
            if key in {"stop_loss", "take_profit"}:
                value = widget.text().strip()
                if not value:
                    self.strategy_params[key] = 99999999  # Set infinite value if empty
                else:
                    value = float(value)
                    if value == 0:
                        value = 99999999
                    self.strategy_params[key] = float(value)
            elif isinstance(widget, QCheckBox):
                self.strategy_params[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                self.strategy_params[key] = widget.currentText()
            elif isinstance(widget, QTimeEdit):
                time_value = widget.time()
                if time_value.toPyTime() < datetime.now(pytz.timezone('Asia/Kolkata')).time():
                    self.message_label.setText(f"Message: Square Off Time Expired")
                    self.start_button.setDisabled(True)
                    self.update_button.setDisabled(True)
                    return
                self.strategy_params[key] = f"{time_value.hour():02d}{time_value.minute():02d}00"  # Convert to HHMMSS
            elif isinstance(widget, QWidget) and key == "hedge":
                hedge_checkbox = widget.findChild(QCheckBox)
                operator_dropdown, number_field = widget.findChildren((QComboBox, QLineEdit))
                if hedge_checkbox and hedge_checkbox.isChecked():
                    self.strategy_params["hedge_selected"] = True
                    if number_field.text().strip() == "":
                        self.message_label.setText(f"Message: {self.key_name['hedge']} is Missing")
                        self.start_button.setDisabled(True)
                        self.update_button.setDisabled(True)
                        return
                    self.strategy_params["hedge_comp_op"] = operator_dropdown.currentText()  # Store operator
                    self.strategy_params["hedge_premium"] = number_field.text().strip()  # Store numeric input
                else:
                    self.strategy_params["hedge_selected"] = False
                    self.strategy_params["hedge_premium"] = None  # Set hedge_premium as None if checkbox is unchecked
                    self.strategy_params["hedge_comp_op"] = None  # Also set hedge operator as None
            elif isinstance(widget, QWidget) and key == "reduce_qty":
                reduce_qty_checkbox = widget.findChild(QCheckBox)
                number_field = widget.findChild(QLineEdit)
                if reduce_qty_checkbox and reduce_qty_checkbox.isChecked():
                    self.strategy_params["reduce_qty_check"] = True
                    if number_field.text().strip() == "":
                        self.message_label.setText(f"Message: {self.key_name['reduce_qty_precent']} is Missing")
                        self.start_button.setDisabled(True)
                        self.update_button.setDisabled(True)
                        return
                    self.strategy_params["reduce_qty_precent"] = number_field.text().strip()  # Store numeric input
                else:
                    self.strategy_params["reduce_qty_check"] = False
                    self.strategy_params["reduce_qty_precent"] = 0  # Set reduce_qty_precent as None if checkbox is unchecked
            else:
                value = widget.text().strip()
                if not value:
                    self.message_label.setText(f"Message: {self.key_name[key]} is Missing")
                    self.start_button.setDisabled(True)
                    self.update_button.setDisabled(True)
                    return
                else:
                    self.message_label.setText(f"Message:                        ")
                    self.strategy_params[key] = float(value)

            if self.status_label.text() == "STATUS: RUNNING":
                self.start_button.setDisabled(True)
                self.update_button.setDisabled(False)
            if self.status_label.text() == "STATUS: PENDING":
                self.start_button.setDisabled(False)
                self.update_button.setDisabled(True)
                self.message_box.clear()
            if self.status_label.text() == "STATUS: SQUARED OFF":
                self.start_button.setDisabled(False)
                self.update_button.setDisabled(True)
                self.clear_tables()
                self.message_box.clear()
                self.status_label.setText("STATUS: PENDING")
                self.status_label.setStyleSheet("color: black;")
            if self.status_label.text() == "STATUS: ERROR":
                self.start_button.setDisabled(False)
                self.update_button.setDisabled(True)
                self.clear_tables()
                self.message_box.clear()
                self.status_label.setText("STATUS: PENDING")
                self.status_label.setStyleSheet("color: black;")

        save_params = self.strategy_params.copy()
        save_params["hedge_premium"] = float(save_params["hedge_premium"]) if save_params["hedge_premium"] is not None else 5
        save_params["hedge_comp_op"] = save_params["hedge_comp_op"] if save_params["hedge_comp_op"] is not None else ">="
        save_params["call_strike"] = int(save_params["call_strike"])
        save_params["put_strike"] = int(save_params["put_strike"])
        save_params["take_profit"] = float(save_params["take_profit"]) if save_params["take_profit"] != 99999999 else 0.0
        save_params["stop_loss"] = float(save_params["stop_loss"]) if save_params["stop_loss"] != 99999999 else 0.0
        print("Strategy Applied Locally:", self.strategy_params)

    def start_strategy(self):
        """Sends a start message to Redis."""
        reply = QMessageBox.question(
            self, "Start Confirmation", "Are you sure you want to start the algo?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.No:
            return
        self.positions.clear()
        self.sq_off_positions.clear()
        self.positions_table.setRowCount(0)
        self.sq_off_table.setRowCount(0)
        self.pnl_label.setText(f"P&L: ₹ {0.0}")
        self.pnl_label.setStyleSheet("color: black;")
        self.message_label.setText("Message:                        ")
        self.strategy_params["hedge_premium"] = float(self.strategy_params["hedge_premium"]) if self.strategy_params["hedge_selected"] else None
        self.strategy_params["fe_id"] = FE_ID
        message = {"type": "START", "data": self.strategy_params , "fe_id": FE_ID}
        self.redis_client.rpush(USER_INPUT, json.dumps(message))
        self.start_button.setDisabled(True)
        self.disable_fields()
        self.message_box.clear()

    def stop_strategy(self):
        reply = QMessageBox.question(
            self, "Stop Confirmation", "Are you sure you want to Square off?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        message = {"type": "STOP", "fe_id": FE_ID}
        self.redis_client.rpush(USER_INPUT, json.dumps(message))
        self.stop_button.setDisabled(True)
    
    def update_strategy(self):
        """Sends an update message to Redis."""
        reply = QMessageBox.question(
            self, "Update Confirmation", "Are you sure you want to update the algo?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        message = {"type": "UPDATE", "data": self.strategy_params , "fe_id": FE_ID}
        self.redis_client.rpush(USER_INPUT, json.dumps(message))
        self.update_button.setDisabled(True)
        self.strategy_inputs['reduce_qty'].findChild(QCheckBox).setChecked(False)
        self.strategy_inputs['reduce_qty'].findChild(QLineEdit).setText("0")

    def setup_table(self, table: QTableWidget):
        table.setFont(QFont("Modern Sans-Serif", 13))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(True)

        # Set the first column larger, and others smaller
        column_widths = [450, 80, 80, 80, 80, 80, 80, 80]  # First column is wider
        for i, width in enumerate(column_widths):
            table.setColumnWidth(i, width)

        # Allow the first column to be fixed while others stretch dynamically
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        for i in range(1, table.columnCount()):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

    def process_message(self, msg):
        """Handle Redis messages safely in the UI thread"""
        if msg["type"] == "CONNECT":
            self.log_message(f"Connected to Backend")
            self.start_ui = True
        elif msg["type"] == "STRATEGY_UPDATE":
            strategy_message = msg["message"]
            self.log_message(strategy_message)
        elif msg["type"] == "STARTED":
            self.status_label.setText(f"STATUS: RUNNING")
            self.status_label.setStyleSheet("color: green;")
            if not self.stop_button.isEnabled():
                self.stop_button.setDisabled(False)
            self.strategy_inputs['reduce_qty'].setDisabled(False)
        elif msg["type"] == "ERROR":
            self.start_button.setDisabled(False)
            self.update_button.setDisabled(True)
            self.stop_button.setDisabled(True)
            self.status_label.setText("STATUS: ERROR")
            self.message_label.setText(f"Message: {msg["message"]}")
            self.status_label.setStyleSheet("color: red;")
            self.enable_fields()
        elif msg["type"] == "END":
            self.start_button.setDisabled(False)
            self.update_button.setDisabled(True)
            self.stop_button.setDisabled(True)
            self.status_label.setText("STATUS: SQUARED OFF")
            self.message_label.setText(f"Message: {msg["message"]}")
            self.status_label.setStyleSheet("color: grey;")
            self.enable_fields()
            # self.strategy_inputs['reduce_qty'].findChild(QCheckBox).setChecked(False)
            self.strategy_inputs['reduce_qty'].findChild(QCheckBox).setChecked(False)
            self.strategy_inputs['reduce_qty'].findChild(QLineEdit).setText("0")
            self.strategy_inputs['reduce_qty'].setDisabled(True)
        elif msg["type"] == "PNL":
            pnl_value = round(msg["data"]["PnL"], 4)
            self.pnl_label.setText(f"P&L: ₹ {pnl_value}")
            if pnl_value >= 0:
                self.pnl_label.setStyleSheet("color: green;")
            else:
                self.pnl_label.setStyleSheet("color: red;")
        elif msg["type"] == "POSITIONS":
            if self.possible_restart:
                self.status_label.setText("STATUS: RUNNING")
                self.status_label.setStyleSheet("color: green;")
                self.disable_fields()
                if self.start_button.isEnabled():
                    self.start_button.setDisabled(True)
                    self.stop_button.setDisabled(False)
                self.possible_restart = False
            data = msg['data']
            self.positions.clear()
            self.sq_off_positions.clear()
            for psn_id, psn_data in data.items():
                symbol = psn_data["symbol"]
                position_data = {
                    "symbol": symbol,
                    "avg_sell_price": round(psn_data["avg_sell_price"], 4),
                    "sell_qty": psn_data["sell_qty"],
                    "avg_buy_price": round(psn_data["avg_buy_price"], 4),
                    "buy_qty": psn_data["buy_qty"],
                    "net_qty": psn_data["buy_qty"] - psn_data["sell_qty"],
                    "pnl": round(psn_data["pnl"], 4),
                    "ltp": psn_data["ltp"]
                }

                if position_data["buy_qty"] == position_data["sell_qty"]:
                    self.sq_off_positions[psn_id] = position_data
                else:
                    self.positions[psn_id] = position_data
        elif msg["type"] == "LTP":
            ltp_data = msg["data"]
            self.ltps[ltp_data["symbol"]] = ltp_data["ltp"]
            self.ltp_lable.setText(f"NIFTY:  {self.ltps.get('NIFTY', '')}\nBANKNIFTY:  {self.ltps.get('BANKNIFTY', '')}")

    def refresh_tables(self):
        self.update_table(self.positions_table, self.positions)
        self.update_table(self.sq_off_table, self.sq_off_positions)


    def update_table(self, table, data_dict):
        table.clearContents()  # Clears existing content, preventing memory growth
        table.setRowCount(len(data_dict))

        for row, (symbol, data) in enumerate(data_dict.items()):
            for col, (key, value) in enumerate(data.items()):
                item = QTableWidgetItem(str(value))
                if key == "pnl":
                    item.setForeground(Qt.green if value >= 0 else Qt.red)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, col, item)

    def disable_fields(self):
        for key in self.fields_to_disable:
            if key in self.strategy_inputs:
                self.strategy_inputs[key].setDisabled(True)

    def enable_fields(self):
        for key in self.fields_to_disable:
            if key in self.strategy_inputs:
                self.strategy_inputs[key].setDisabled(False)

    def clear_tables(self):
        self.positions = {}
        self.sq_off_positions = {}
        self.refresh_tables()
        self.pnl_label.setText(f"P&L: ₹ {0.0}")
        self.pnl_label.setStyleSheet("color: black;")
        self.message_label.setText("Message:                        ")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingDashboard()
    def check_ui_ready():
        if window.start_ui:
            print(f"FrontEnd_ID: {FE_ID}")
            window.show()
        else:
            QTimer.singleShot(100, check_ui_ready)  # Check again in 100ms
    check_ui_ready() # Start checking when UI is ready
    sys.exit(app.exec_())

