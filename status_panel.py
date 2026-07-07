from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout

class StatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QHBoxLayout()
        
        self.connection_label = QLabel("Connection : 🔴 Disconnected")
        self.connection_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        self.streaming_label = QLabel("Streaming : ⚪ Idle")
        self.streaming_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        self.recording_label = QLabel("Recording : ⚪ Not Recording")
        self.recording_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        self.quality_label = QLabel("Signal Quality: ECG ⚪ N/A | EMG ⚪ N/A | RESP ⚪ N/A | EDA ⚪ N/A | fNIRS ⚪ N/A")
        self.quality_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        layout.addWidget(self.connection_label)
        layout.addWidget(self.streaming_label)
        layout.addWidget(self.recording_label)
        layout.addWidget(self.quality_label)
        
        self.setLayout(layout)

    def set_theme(self, theme):
        text_color = "#ffffff" if theme == "dark" else "#121212"
        style = f"color: {text_color}; font-size: 13px; font-weight: bold;"
        self.connection_label.setStyleSheet(style)
        self.streaming_label.setStyleSheet(style)
        self.recording_label.setStyleSheet(style)
        self.quality_label.setStyleSheet(style)

