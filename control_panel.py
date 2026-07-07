from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLineEdit, QLabel, QComboBox

class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout()
        row1_layout = QHBoxLayout()
        row2_layout = QHBoxLayout()
        
        # Label styling
        label_style = """
            QLabel {
                color: #888888;
                font-weight: bold;
                font-size: 13px;
            }
        """
        
        # Input/Combo styling
        input_style = """
            QLineEdit, QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 6px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #007acc;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #ffffff;
                selection-background-color: #007acc;
            }
        """
        
        # Stylesheet for premium look matching the reference
        button_style = """
            QPushButton {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 6px 15px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #888888;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #555555;
                border-color: #555555;
            }
        """
        
        # ROW 1 elements
        self.mode_label = QLabel("Mode:")
        self.mode_label.setStyleSheet(label_style)
        
        self.mode_select = QComboBox()
        self.mode_select.setStyleSheet(input_style)
        self.mode_select.addItems(["Direct (USB/BTH)", "OpenSignals (LSL)"])
        self.mode_select.currentTextChanged.connect(self.on_mode_changed)
        
        self.address_label = QLabel("Device:")
        self.address_label.setStyleSheet(label_style)
        
        self.address_input = QLineEdit("BTH00:07:80:4D:2E:76")
        self.address_input.setStyleSheet(input_style)
        self.address_input.setMinimumWidth(180)
        
        row1_layout.addWidget(self.mode_label)
        row1_layout.addWidget(self.mode_select)
        row1_layout.addWidget(self.address_label)
        row1_layout.addWidget(self.address_input)
        
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.pause_button = QPushButton("Pause")
        self.theme_button = QPushButton("Theme: Dark")
        
        for btn in [self.connect_button, self.disconnect_button, self.start_button, 
                    self.stop_button, self.pause_button, self.theme_button]:
            btn.setStyleSheet(button_style)
            row1_layout.addWidget(btn)
            
        row1_layout.addStretch()
        
        # ROW 2 elements (Sample Rates & Recording Buttons)
        self.rate_label = QLabel("Rates (Hz):")
        self.rate_label.setStyleSheet(label_style)
        
        self.rate_ecg_lbl = QLabel("ECG:")
        self.rate_ecg_lbl.setStyleSheet(label_style)
        self.rate_ecg = QLineEdit("250")
        self.rate_ecg.setStyleSheet(input_style)
        self.rate_ecg.setMaximumWidth(50)
        
        self.rate_emg_lbl = QLabel("EMG:")
        self.rate_emg_lbl.setStyleSheet(label_style)
        self.rate_emg = QLineEdit("1000")
        self.rate_emg.setStyleSheet(input_style)
        self.rate_emg.setMaximumWidth(50)
        
        self.rate_resp_lbl = QLabel("RESP:")
        self.rate_resp_lbl.setStyleSheet(label_style)
        self.rate_resp = QLineEdit("50")
        self.rate_resp.setStyleSheet(input_style)
        self.rate_resp.setMaximumWidth(50)
        
        self.rate_eda_lbl = QLabel("EDA:")
        self.rate_eda_lbl.setStyleSheet(label_style)
        self.rate_eda = QLineEdit("20")
        self.rate_eda.setStyleSheet(input_style)
        self.rate_eda.setMaximumWidth(50)
        
        self.rate_fnirs_lbl = QLabel("fNIRS:")
        self.rate_fnirs_lbl.setStyleSheet(label_style)
        self.rate_fnirs = QLineEdit("10")
        self.rate_fnirs.setStyleSheet(input_style)
        self.rate_fnirs.setMaximumWidth(50)
        
        self.notch_lbl = QLabel("Notch:")
        self.notch_lbl.setStyleSheet(label_style)
        self.notch_select = QComboBox()
        self.notch_select.setStyleSheet(input_style)
        self.notch_select.addItems(["None", "50 Hz", "60 Hz"])
        self.notch_select.setCurrentIndex(1)  # Default to 50 Hz
        self.notch_select.setMaximumWidth(80)
        
        row2_layout.addWidget(self.rate_label)
        row2_layout.addWidget(self.rate_ecg_lbl)
        row2_layout.addWidget(self.rate_ecg)
        row2_layout.addWidget(self.rate_emg_lbl)
        row2_layout.addWidget(self.rate_emg)
        row2_layout.addWidget(self.rate_resp_lbl)
        row2_layout.addWidget(self.rate_resp)
        row2_layout.addWidget(self.rate_eda_lbl)
        row2_layout.addWidget(self.rate_eda)
        row2_layout.addWidget(self.rate_fnirs_lbl)
        row2_layout.addWidget(self.rate_fnirs)
        row2_layout.addWidget(self.notch_lbl)
        row2_layout.addWidget(self.notch_select)
        
        # Add space separator
        spacer = QLabel(" | ")
        spacer.setStyleSheet("color: #555555; font-weight: bold;")
        row2_layout.addWidget(spacer)
        
        self.record_button = QPushButton("Start Record")
        self.stop_record_button = QPushButton("Stop Record")
        self.save_button = QPushButton("Save CSV")
        
        for btn in [self.record_button, self.stop_record_button, self.save_button]:
            btn.setStyleSheet(button_style)
            row2_layout.addWidget(btn)
            
        row2_layout.addStretch()
        
        # Combine layouts
        main_layout.addLayout(row1_layout)
        main_layout.addLayout(row2_layout)
        self.setLayout(main_layout)
        
    def on_mode_changed(self, text):
        if "LSL" in text:
            self.address_input.setEnabled(False)
            self.address_label.setEnabled(False)
        else:
            self.address_input.setEnabled(True)
            self.address_label.setEnabled(True)

    def set_theme(self, theme):
        if theme == "light":
            label_color = "#555555"
            bg_input = "#ffffff"
            fg_input = "#121212"
            border_input = "#cccccc"
            bg_button = "#e0e0e0"
            fg_button = "#121212"
            border_button = "#cccccc"
            bg_button_hover = "#d6d6d6"
        else: # dark
            label_color = "#888888"
            bg_input = "#1e1e1e"
            fg_input = "#ffffff"
            border_input = "#555555"
            bg_button = "#2b2b2b"
            fg_button = "#ffffff"
            border_button = "#555555"
            bg_button_hover = "#3b3b3b"
            
        label_style = f"QLabel {{ color: {label_color}; font-weight: bold; font-size: 13px; }}"
        self.mode_label.setStyleSheet(label_style)
        self.address_label.setStyleSheet(label_style)
        self.rate_label.setStyleSheet(label_style)
        self.rate_ecg_lbl.setStyleSheet(label_style)
        self.rate_emg_lbl.setStyleSheet(label_style)
        self.rate_resp_lbl.setStyleSheet(label_style)
        self.rate_eda_lbl.setStyleSheet(label_style)
        self.rate_fnirs_lbl.setStyleSheet(label_style)
        self.notch_lbl.setStyleSheet(label_style)
        
        input_style = f"""
            QLineEdit, QComboBox {{
                background-color: {bg_input};
                color: {fg_input};
                border: 1px solid {border_input};
                padding: 6px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: #007acc;
            }}
            QComboBox::drop-down {{
                border: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_input};
                color: {fg_input};
                selection-background-color: #007acc;
            }}
        """
        self.mode_select.setStyleSheet(input_style)
        self.address_input.setStyleSheet(input_style)
        self.rate_ecg.setStyleSheet(input_style)
        self.rate_emg.setStyleSheet(input_style)
        self.rate_resp.setStyleSheet(input_style)
        self.rate_eda.setStyleSheet(input_style)
        self.rate_fnirs.setStyleSheet(input_style)
        self.notch_select.setStyleSheet(input_style)
        
        button_style = f"""
            QPushButton {{
                background-color: {bg_button};
                color: {fg_button};
                border: 1px solid {border_button};
                padding: 6px 15px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {bg_button_hover};
                border-color: #888888;
            }}
            QPushButton:pressed {{
                background-color: #1a1a1a;
            }}
            QPushButton:disabled {{
                background-color: {bg_button};
                color: #555555;
                border-color: {border_button};
            }}
        """
        for btn in [self.connect_button, self.disconnect_button, self.start_button, 
                    self.stop_button, self.pause_button, self.record_button, 
                    self.stop_record_button, self.save_button, self.theme_button]:
            btn.setStyleSheet(button_style)


