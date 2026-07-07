from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QButtonGroup, QLabel, QLineEdit
import pyqtgraph as pg
import numpy as np
from scipy.signal import welch

class RESPPanel(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        # ====================================
        # MODE SELECTION & CONTROLS
        # ====================================
        btn_layout = QHBoxLayout()
        
        self.btn_raw = QPushButton("Raw Data")
        self.btn_filtered = QPushButton("Filter Data")
        
        self.btn_raw.setCheckable(True)
        self.btn_filtered.setCheckable(True)
        
        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.btn_raw)
        self.btn_group.addButton(self.btn_filtered)
        self.btn_group.setExclusive(True)
        
        self.show_mode = "filtered"
        self.btn_filtered.setChecked(True)
        
        button_style = """
            QPushButton {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 6px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #888888;
            }
            QPushButton:checked {
                background-color: #007acc;
                border-color: #0098ff;
            }
        """
        self.btn_raw.setStyleSheet(button_style)
        self.btn_filtered.setStyleSheet(button_style)
        
        btn_layout.addWidget(self.btn_raw)
        btn_layout.addWidget(self.btn_filtered)
        
        # Lowpass filter cutoff input
        self.lbl_cutoff = QLabel("Filter Cutoff (Hz):")
        self.lbl_cutoff.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; margin-left: 15px;")
        
        self.cutoff_input = QLineEdit("2.0")
        self.cutoff_input.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                max-width: 60px;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
        """)
        
        btn_layout.addWidget(self.lbl_cutoff)
        btn_layout.addWidget(self.cutoff_input)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        # ====================================
        # PLOTS SETUP (RESP & FFT)
        # ====================================
        self.resp_plot = pg.PlotWidget(title="Respiration Signal")
        self.fft_plot = pg.PlotWidget(title="RESP FFT Spectrum")
        
        # Time Domain Plot Configuration
        plot_item = self.resp_plot.getPlotItem()
        view_box = plot_item.getViewBox()
        plot_item.showGrid(x=True, y=True, alpha=0.3)
        plot_item.addLegend()
        plot_item.setLabel('left', 'Amplitude', units='V')
        plot_item.setLabel('bottom', 'Samples')
        plot_item.setXRange(0, 300, padding=0)
        plot_item.setClipToView(True)
        view_box.setMouseEnabled(x=True, y=True)
        view_box.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)
        
        # Frequency Domain Plot Configuration
        fft_plot_item = self.fft_plot.getPlotItem()
        fft_view_box = fft_plot_item.getViewBox()
        fft_plot_item.showGrid(x=True, y=True, alpha=0.3)
        fft_plot_item.addLegend()
        fft_plot_item.setLabel('left', 'PSD', units='V²/Hz')
        fft_plot_item.setLabel('bottom', 'Frequency', units='Hz')
        fft_plot_item.setXRange(0, 2.0, padding=0)
        fft_plot_item.setClipToView(True)
        fft_view_box.setMouseEnabled(x=True, y=True)
        fft_view_box.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)
        
        # ====================================
        # 10 OVERLAY SEGMENTS SPANNING 300 SAMPLES
        # ====================================
        self.regions = []
        for i in range(10):
            reg = pg.LinearRegionItem(
                values=[i * 30, (i + 1) * 30],
                brush=pg.mkBrush(150, 150, 150, 40),
                pen=pg.mkPen(color=(150, 150, 150, 100), width=1),
                movable=False
            )
            plot_item.addItem(reg)
            self.regions.append(reg)
            
        # Curves
        self.resp_raw_curve = plot_item.plot(pen=pg.mkPen('#888888', width=1), name="RESP Raw")
        self.resp_curve = plot_item.plot(pen=pg.mkPen('#00e676', width=2), name="RESP Filtered")
        
        # Peak and Valley indicators
        self.peak_curve = plot_item.plot(pen=None, symbol='o', symbolPen='#ff1744', symbolBrush='#ff1744', symbolSize=8, name="Inhalation Peaks")
        self.valley_curve = plot_item.plot(pen=None, symbol='o', symbolPen='#2979ff', symbolBrush='#2979ff', symbolSize=8, name="Exhalation Valleys")
        
        # FFT Curve
        self.fft_curve = fft_plot_item.plot(pen=pg.mkPen('#ff9100', width=2), name="RESP FFT")
        
        # Connect slots
        self.btn_raw.clicked.connect(self.set_raw_mode)
        self.btn_filtered.clicked.connect(self.set_filtered_mode)
        self.set_filtered_mode()
        
        # Layout plots (70% vs 30% stretch)
        plots_layout = QHBoxLayout()
        plots_layout.addWidget(self.resp_plot, stretch=7)
        plots_layout.addWidget(self.fft_plot, stretch=3)
        layout.addLayout(plots_layout)
        
        # ====================================
        # ANALYTICS FEATURES ROW
        # ====================================
        feat_layout = QHBoxLayout()
        label_style = "color: #ffffff; font-size: 14px; font-weight: bold; padding: 10px;"
        
        self.lbl_rr = QLabel("Respiration Rate: -- Breaths/Min")
        self.lbl_rr.setStyleSheet(label_style)
        
        self.lbl_insp = QLabel("Avg Inspiration: -- s")
        self.lbl_insp.setStyleSheet(label_style)
        
        self.lbl_exp = QLabel("Avg Expiration: -- s")
        self.lbl_exp.setStyleSheet(label_style)
        
        self.lbl_ie = QLabel("I:E Ratio: --")
        self.lbl_ie.setStyleSheet(label_style)
        
        feat_layout.addWidget(self.lbl_rr)
        feat_layout.addWidget(self.lbl_insp)
        feat_layout.addWidget(self.lbl_exp)
        feat_layout.addWidget(self.lbl_ie)
        feat_layout.addStretch()
        
        layout.addLayout(feat_layout)
        self.setLayout(layout)

    def set_raw_mode(self):
        self.show_mode = "raw"
        self.resp_curve.setVisible(False)
        self.peak_curve.setVisible(False)
        self.valley_curve.setVisible(False)
        self.resp_raw_curve.setVisible(True)

    def set_filtered_mode(self):
        self.show_mode = "filtered"
        self.resp_curve.setVisible(True)
        self.peak_curve.setVisible(True)
        self.valley_curve.setVisible(True)
        self.resp_raw_curve.setVisible(True)
        
    def update_auto_zoom(self, raw, filtered):
        try:
            if self.show_mode == "raw":
                all_data = raw
            else:
                all_data = np.concatenate([raw, filtered])
            clean = all_data[np.isfinite(all_data)]
            if len(clean) == 0:
                return
            ymin, ymax = np.min(clean), np.max(clean)
            if ymin == ymax:
                ymin -= 0.1
                ymax += 0.1
            margin = (ymax - ymin) * 0.15
            self.resp_plot.getPlotItem().setYRange(ymin - margin, ymax + margin, padding=0)
        except Exception as e:
            print("RESP zoom error:", e)
            
    def update_fft(self, filtered):
        try:
            n = len(filtered)
            if n < 2:
                return
            fs = 50.0
            f, psd = welch(filtered, fs=fs, nperseg=min(n, 256))
            self.fft_curve.setData(f, psd)
            if len(psd) > 1:
                max_val = np.max(psd[1:])
                if max_val <= 0:
                    max_val = 1.0
                self.fft_plot.getPlotItem().setYRange(0, max_val * 1.1, padding=0)
        except Exception as e:
            print("RESP FFT error:", e)
            
    def update_region_color(self, local_quals):
        if local_quals is None:
            local_quals = ["N/A"] * 10
        elif isinstance(local_quals, str):
            local_quals = [local_quals] * 10
            
        def get_brush_pen(status):
            if status == "Good":
                return pg.mkBrush(0, 200, 0, 40), pg.mkPen(color=(0, 200, 0, 100), width=1)
            elif status == "Fair":
                return pg.mkBrush(200, 200, 0, 40), pg.mkPen(color=(200, 200, 0, 100), width=1)
            elif status == "Poor":
                return pg.mkBrush(200, 0, 0, 40), pg.mkPen(color=(200, 0, 0, 100), width=1)
            else:
                return pg.mkBrush(150, 150, 150, 20), pg.mkPen(color=(150, 150, 150, 50), width=1)
                
        for i in range(10):
            status = local_quals[i] if i < len(local_quals) else "N/A"
            brush, pen = get_brush_pen(status)
            if i < len(self.regions):
                self.regions[i].setBrush(brush)
                for line in self.regions[i].lines:
                    line.setPen(pen)

    def set_theme(self, theme):
        if theme == "light":
            bg = '#000000'
            fg = '#ffffff'
            label_fg = '#121212'
            text_style = "color: #121212; font-size: 14px; font-weight: bold; padding: 10px;"
            input_style = """
                QLineEdit {
                    background-color: #ffffff;
                    color: #121212;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 13px;
                    max-width: 60px;
                }
                QLineEdit:focus {
                    border-color: #007acc;
                }
            """
            button_style = """
                QPushButton {
                    background-color: #e0e0e0;
                    color: #121212;
                    border: 1px solid #cccccc;
                    padding: 6px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #d6d6d6;
                    border-color: #999999;
                }
                QPushButton:checked {
                    background-color: #007acc;
                    border-color: #0098ff;
                    color: #ffffff;
                }
            """
        else: # dark
            bg = '#000000'
            fg = '#ffffff'
            label_fg = '#ffffff'
            text_style = "color: #ffffff; font-size: 14px; font-weight: bold; padding: 10px;"
            input_style = """
                QLineEdit {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 13px;
                    max-width: 60px;
                }
                QLineEdit:focus {
                    border-color: #007acc;
                }
            """
            button_style = """
                QPushButton {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 6px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #3b3b3b;
                    border-color: #888888;
                }
                QPushButton:checked {
                    background-color: #007acc;
                    border-color: #0098ff;
                    color: #ffffff;
                }
            """

        self.resp_plot.setBackground(bg)
        self.fft_plot.setBackground(bg)
        
        self.resp_plot.getPlotItem().getAxis('left').setPen(fg)
        self.resp_plot.getPlotItem().getAxis('left').setTextPen(fg)
        self.resp_plot.getPlotItem().getAxis('bottom').setPen(fg)
        self.resp_plot.getPlotItem().getAxis('bottom').setTextPen(fg)
        self.fft_plot.getPlotItem().getAxis('left').setPen(fg)
        self.fft_plot.getPlotItem().getAxis('left').setTextPen(fg)
        self.fft_plot.getPlotItem().getAxis('bottom').setPen(fg)
        self.fft_plot.getPlotItem().getAxis('bottom').setTextPen(fg)

        self.resp_plot.getPlotItem().titleLabel.setAttr('color', fg)
        self.fft_plot.getPlotItem().titleLabel.setAttr('color', fg)

        self.btn_raw.setStyleSheet(button_style)
        self.btn_filtered.setStyleSheet(button_style)
        self.cutoff_input.setStyleSheet(input_style)
        
        self.lbl_cutoff.setStyleSheet(f"color: {label_fg}; font-size: 13px; font-weight: bold; margin-left: 15px;")
        
        self.lbl_rr.setStyleSheet(text_style)
        self.lbl_insp.setStyleSheet(text_style)
        self.lbl_exp.setStyleSheet(text_style)
        self.lbl_ie.setStyleSheet(text_style)

    def reconfigure_plots(self, fs):
        window_size = int(6.0 * fs)
        self.resp_plot.getPlotItem().setXRange(0, window_size, padding=0)
        reg_width = window_size / 10.0
        for i, reg in enumerate(self.regions):
            reg.setBounds([0, window_size])
            reg.setRegion([i * reg_width, (i + 1) * reg_width])


