from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget
import pyqtgraph as pg

from status_panel import StatusPanel
from control_panel import ControlPanel
from signal_panel import SignalPanel

from pages.ecg_page import ECGPanel
from pages.emg_page import EMGPanel
from pages.resp_page import RESPPanel
from pages.eda_page import EDAPanel
from pages.fnirs_page import FNIRSPanel

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()

        # =========================================
        # WINDOW SETTINGS
        # =========================================
        self.setWindowTitle("BioSignalsPlux Live Dashboard")
        self.resize(1600, 1000)
        self.current_theme = "dark"

        # Set pyqtgraph styling
        pg.setConfigOption('background', 'k')
        pg.setConfigOption('foreground', 'w')

        # =========================================
        # MAIN LAYOUT
        # =========================================
        central_widget = QWidget()
        layout = QVBoxLayout()

        # =========================================
        # TOP PANELS
        # =========================================
        self.status_panel = StatusPanel()
        self.control_panel = ControlPanel()

        # =========================================
        # SENSOR TABS
        # =========================================
        self.tabs = QTabWidget()
        
        self.ecg_panel = ECGPanel()
        self.emg_panel = EMGPanel()
        self.resp_panel = RESPPanel()
        self.eda_panel = EDAPanel()
        self.fnirs_panel = FNIRSPanel()

        self.tabs.addTab(self.ecg_panel, "ECG")
        self.tabs.addTab(self.emg_panel, "EMG")
        self.tabs.addTab(self.resp_panel, "RESP")
        self.tabs.addTab(self.eda_panel, "EDA")
        self.tabs.addTab(self.fnirs_panel, "fNIRS")

        # =========================================
        # SIGNAL CONTROLLER
        # =========================================
        self.signal_panel = SignalPanel(self)

        # =========================================
        # BUTTON CONNECTIONS
        # =========================================
        self.control_panel.connect_button.clicked.connect(self.signal_panel.connect_device)
        self.control_panel.disconnect_button.clicked.connect(self.signal_panel.disconnect_device)
        self.control_panel.start_button.clicked.connect(self.signal_panel.start_stream)
        self.control_panel.stop_button.clicked.connect(self.signal_panel.stop_stream)
        self.control_panel.pause_button.clicked.connect(self.signal_panel.pause_stream)
        
        self.control_panel.record_button.clicked.connect(self.signal_panel.start_recording)
        self.control_panel.stop_record_button.clicked.connect(self.signal_panel.stop_recording)
        self.control_panel.save_button.clicked.connect(self.signal_panel.save_data)
        self.control_panel.theme_button.clicked.connect(self.toggle_theme)

        # =========================================
        # FINAL LAYOUT
        # =========================================
        layout.addWidget(self.status_panel)
        layout.addWidget(self.control_panel)
        layout.addWidget(self.tabs)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Apply default theme
        self.apply_theme("dark")

    def toggle_theme(self):
        if self.current_theme == "dark":
            self.current_theme = "light"
            self.control_panel.theme_button.setText("Theme: Light")
        else:
            self.current_theme = "dark"
            self.control_panel.theme_button.setText("Theme: Dark")
        self.apply_theme(self.current_theme)

    def apply_theme(self, theme):
        bg_color = "#121212" if theme == "dark" else "#f5f5f5"
        self.setStyleSheet(f"background-color: {bg_color};")
        
        # Update tabs stylesheet dynamically
        if theme == "dark":
            tabs_style = """
                QTabWidget::panel {
                    border: 1px solid #333333;
                    background-color: #121212;
                }
                QTabBar::tab {
                    background: #1e1e1e;
                    color: #888888;
                    border: 1px solid #333333;
                    padding: 8px 16px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    font-weight: bold;
                }
                QTabBar::tab:selected {
                    background: #007acc;
                    color: #ffffff;
                    border-bottom-color: #007acc;
                }
                QTabBar::tab:hover {
                    background: #2b2b2b;
                    color: #ffffff;
                }
            """
        else:
            tabs_style = """
                QTabWidget::panel {
                    border: 1px solid #cccccc;
                    background-color: #f5f5f5;
                }
                QTabBar::tab {
                    background: #e0e0e0;
                    color: #555555;
                    border: 1px solid #cccccc;
                    padding: 8px 16px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    font-weight: bold;
                }
                QTabBar::tab:selected {
                    background: #007acc;
                    color: #ffffff;
                    border-bottom-color: #007acc;
                }
                QTabBar::tab:hover {
                    background: #d6d6d6;
                    color: #121212;
                }
            """
        self.tabs.setStyleSheet(tabs_style)
        
        # Update children panels
        self.status_panel.set_theme(theme)
        self.control_panel.set_theme(theme)
        self.ecg_panel.set_theme(theme)
        self.emg_panel.set_theme(theme)
        self.resp_panel.set_theme(theme)
        self.eda_panel.set_theme(theme)
        self.fnirs_panel.set_theme(theme)

