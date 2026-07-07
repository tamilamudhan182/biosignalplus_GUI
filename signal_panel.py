from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog

import numpy as np
import pandas as pd
import time
from scipy.signal import welch

from biosignal_worker import SessionSignalBuffer, BiosignalWorker
from recording import SignalRecorder
from filters import apply_bandpass_filter, apply_lowpass_filter, apply_notch_filter

class SignalPanel:
    def __init__(self, dashboard):
        self.dashboard = dashboard
        self.worker = None
        
        self.connected = False
        self.streaming = False
        self.recording = False
        
        self.buffer = None
        self.recorder = None
        
        # Timer to update GUI (25 FPS -> 40 ms)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        
    def connect_device(self):
        if self.connected:
            return
            
        mode = self.dashboard.control_panel.mode_select.currentText()
        
        if "LSL" in mode:
            print("Connecting physical BioSignalsPlux via LSL...")
            try:
                from pylsl import resolve_byprop, resolve_streams
                
                # Resolve stream with type='biosignals' or name='OpenSignals'
                streams = resolve_byprop('type', 'biosignals', timeout=2.0)
                if not streams:
                    streams = resolve_byprop('name', 'OpenSignals', timeout=2.0)
                if not streams:
                    # Search all active streams as a fallback
                    streams = resolve_streams(timeout=1.0)
                    streams = [s for s in streams if 'opensignals' in s.name().lower() or 'biosignals' in s.type().lower()]
                    
                if not streams:
                    print("LSL stream not found.")
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.critical(
                        self.dashboard,
                        "LSL Connection Error",
                        "Could not find any active OpenSignals LSL streams.\n\n"
                        "Please ensure:\n"
                        "1. OpenSignals is running on your computer.\n"
                        "2. Your BioSignalsPlux device is connected in OpenSignals.\n"
                        "3. Lab Streaming Layer is enabled under OpenSignals Settings -> Integrations.\n"
                        "4. Acquisition/Recording is actively running in OpenSignals."
                    )
                    return
                    
                self.buffer = SessionSignalBuffer()
                self.recorder = SignalRecorder()
                self.connected = True
                self.connection_mode = "LSL"
                self.lsl_stream = streams[0]
                self.device_address = None
                
                self.dashboard.status_panel.connection_label.setText("Connection : 🟢 Connected (LSL)")
                print("Physical board connected via LSL stream.")
            except Exception as e:
                print("Failed to connect via LSL:", e)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self.dashboard,
                    "LSL Connection Error",
                    f"Failed to connect via LSL: {str(e)}"
                )
        else:
            address = self.dashboard.control_panel.address_input.text().strip()
            if not address:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.dashboard, "Input Error", "Please enter a valid Bluetooth MAC address or COM port.")
                return
                
            print(f"Connecting physical BioSignalsPlux directly via Python API to address: {address}...")
            
            # Setup path and load plux
            import sys
            import os
            from pathlib import Path
            api_dir = Path(r"d:\biosignal\scratch_python_samples\PLUX-API-Python3\Win64_313")
            
            if str(api_dir) not in sys.path:
                sys.path.insert(0, str(api_dir))
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(api_dir))
                except Exception as e:
                    print("add_dll_directory failed:", e)
                    
            try:
                import plux
                
                # Test connection by creating device and getting battery status
                print("Initializing connection test...")
                device = plux.SignalsDev(address)
                battery = device.getBattery()
                device.close()
                print(f"Connection test succeeded. Battery level: {int(battery)}%")
                
                self.buffer = SessionSignalBuffer()
                self.recorder = SignalRecorder()
                self.device_address = address
                self.lsl_stream = None
                self.connected = True
                self.connection_mode = "Direct"
                
                self.dashboard.status_panel.connection_label.setText(f"Connection : 🟢 Connected ({address})")
                print("Physical BioSignalsPlux board connected directly.")
                
            except Exception as e:
                print("Failed to connect directly to BioSignalsPlux:", e)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self.dashboard,
                    "Connection Error",
                    f"Could not connect directly to the BioSignalsPlux device ({address}).\n\n"
                    f"Error Details: {str(e)}\n\n"
                    "Please verify:\n"
                    "1. If using USB (Option 1), ensure the USB cable is plugged in securely.\n"
                    "2. Check Device Manager to find the correct COM port (e.g. COM3, COM4) and type it in the 'Device' field.\n"
                    "3. If using Bluetooth, ensure your computer's Bluetooth is ON, the device is paired in Windows settings, and the MAC address is entered correctly (e.g., 'BTH00:07:80:4D:2E:76').\n"
                    "4. Ensure the physical BioSignalsPlux device is turned ON (green LED blinking/solid).\n"
                    "5. Ensure no other application (like OpenSignals) is currently connected to the device."
                )
            
    def disconnect_device(self):
        self.stop_stream()
        
        self.connected = False
        self.streaming = False
        self.recording = False
        
        self.buffer = None
        self.recorder = None
        self.device_address = None
        self.lsl_stream = None
        self.connection_mode = None
        
        self.dashboard.status_panel.connection_label.setText("Connection : 🔴 Disconnected")
        self.dashboard.status_panel.streaming_label.setText("Streaming : ⚪ Idle")
        self.dashboard.status_panel.recording_label.setText("Recording : ⚪ Not Recording")
        self.dashboard.status_panel.quality_label.setText("Signal Quality: ECG ⚪ N/A | EMG ⚪ N/A | RESP ⚪ N/A | EDA ⚪ N/A | fNIRS ⚪ N/A")
        print("Physical board disconnected.")
        
    def start_stream(self):
        if not self.connected:
            print("Please Connect the board first.")
            return
            
        if self.streaming:
            return
            
        # Read target rates from GUI inputs
        try:
            rates = {
                'ecg': int(self.dashboard.control_panel.rate_ecg.text().strip()),
                'emg': int(self.dashboard.control_panel.rate_emg.text().strip()),
                'resp': int(self.dashboard.control_panel.rate_resp.text().strip()),
                'eda': int(self.dashboard.control_panel.rate_eda.text().strip()),
                'fnirs': int(self.dashboard.control_panel.rate_fnirs.text().strip())
            }
        except Exception as e:
            print("Invalid target rates in GUI inputs, using defaults.", e)
            rates = {'ecg': 250, 'emg': 1000, 'resp': 50, 'eda': 20, 'fnirs': 10}
            
        self.buffer.reconfigure_rates(rates)
        
        # Reconfigure the UI plot window limits and overlay boundaries
        self.dashboard.ecg_panel.reconfigure_plots(rates['ecg'])
        self.dashboard.emg_panel.reconfigure_plots(rates['emg'])
        self.dashboard.resp_panel.reconfigure_plots(rates['resp'])
        self.dashboard.eda_panel.reconfigure_plots(rates['eda'])
        self.dashboard.fnirs_panel.reconfigure_plots(rates['fnirs'])

        self.streaming = True
        
        # Start background physical worker thread if not running
        if self.worker is None or not self.worker.is_alive():
            self.worker = BiosignalWorker(
                self.buffer, 
                self.recorder, 
                address=self.device_address,
                lsl_stream=self.lsl_stream,
                mode=self.connection_mode
            )
            self.worker.start()
            
        self.timer.start(40) # update every 40 ms
        self.dashboard.status_panel.streaming_label.setText("Streaming : 🟢 Active")
        print("Acquisition streaming started.")
        
    def stop_stream(self):
        if not self.streaming:
            return
            
        self.timer.stop()
        self.streaming = False
        
        if self.worker:
            self.worker.stop()
            self.worker.join(timeout=1.0)
            self.worker = None
            
        if self.recording:
            self.stop_recording()
            
        self.dashboard.status_panel.streaming_label.setText("Streaming : ⚪ Idle")
        print("Acquisition streaming stopped.")
        
    def pause_stream(self):
        if not self.streaming:
            return
            
        if self.timer.isActive():
            self.timer.stop()
            self.dashboard.status_panel.streaming_label.setText("Streaming : 🟡 Paused")
            print("Real-time graph updates paused.")
        else:
            self.timer.start(40)
            self.dashboard.status_panel.streaming_label.setText("Streaming : 🟢 Active")
            print("Real-time graph updates resumed.")
            
    def start_recording(self):
        if not self.streaming:
            print("Cannot record while acquisition is idle.")
            return
            
        if self.recording:
            return
            
        self.recorder.start()
        self.recording = True
        self.dashboard.status_panel.recording_label.setText("Recording : 🔴 Recording (0.0s)")
        print("Recording session started.")
        
    def stop_recording(self):
        if not self.recording:
            return
            
        self.recorder.stop()
        self.recording = False
        duration = self.recorder.get_duration()
        self.dashboard.status_panel.recording_label.setText(f"Recording : ⚪ Stopped ({duration:.1f}s)")
        print("Recording session stopped.")
        
    def save_data(self):
        if self.recording:
            print("Stop recording first before exporting CSV.")
            return
            
        if self.recorder is None or len(self.recorder.buffers['emg']) == 0:
            print("No recorded data available to save.")
            return
            
        path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Biosignal CSV Record",
            f"biosignal_record_{int(time.time())}.csv",
            "CSV Files (*.csv)"
        )
        
        if not path:
            return
            
        try:
            csv_bytes = self.recorder.export_to_csv()
            with open(path, "wb") as f:
                f.write(csv_bytes)
            print(f"Data saved to {path} successfully.")
        except Exception as e:
            print("Failed to save CSV file:", e)
            
    # ==================================================
    # MAIN UPDATE LOOP (RUNS AT 25 FPS)
    # ==================================================
    def update_data(self):
        if self.buffer is None:
            return
            
        try:
            # 1. ECG Panel Update
            self._update_ecg()
            
            # 2. EMG Panel Update
            self._update_emg()
            
            # 3. RESP Panel Update
            self._update_resp()
            
            # 4. EDA Panel Update
            self._update_eda()
            
            # 5. fNIRS Panel Update
            self._update_fnirs()
            
            # 6. Status and Quality indicators update
            self._update_status_panel()
            
        except Exception as e:
            print("Update loop error:", e)
            
    def _update_ecg(self):
        ecg_p = self.dashboard.ecg_panel
        fs = self.buffer.rates['ecg']
        
        # Pull ECG data under lock
        with self.buffer.lock:
            raw_ecg = list(self.buffer.raw['ecg'])
            timestamps = list(self.buffer.timestamps['ecg'])
            
        if len(raw_ecg) < 50:
            return
            
        # Get cutoff inputs
        try:
            lowcut = float(ecg_p.lowcut_input.text().strip())
            highcut = float(ecg_p.highcut_input.text().strip())
        except:
            lowcut, highcut = 0.5, 40.0
            
        # Get notch filter configuration
        notch_text = self.dashboard.control_panel.notch_select.currentText()
        notch_freq = None
        if "50 Hz" in notch_text:
            notch_freq = 50.0
        elif "60 Hz" in notch_text:
            notch_freq = 60.0

        # 1. Real-time plotting (last 300 * dec_factor samples, decimated to 300 points to match EDA speed)
        dec_factor = max(1, int(round(fs / 20.0)))
        window_size = 300 * dec_factor
        raw_plot = np.array(raw_ecg[-window_size:])
        raw_mean = np.mean(raw_plot)
        raw_centered = raw_plot - raw_mean
        
        # Apply bandpass to the visual chunk
        filt_centered = apply_bandpass_filter(raw_plot, lowcut, highcut, fs) - raw_mean
        if notch_freq is not None:
            filt_centered = apply_notch_filter(filt_centered, notch_freq, fs)
            
        # Decimate for plotting
        raw_centered_plot = raw_centered[::dec_factor]
        filt_centered_plot = filt_centered[::dec_factor]
        
        # Update curves
        ecg_p.ecg_raw_curve.setData(raw_centered_plot)
        ecg_p.ecg_curve.setData(filt_centered_plot)
        
        # 2. Feature analysis (on last 5 seconds of data)
        analysis_size = int(5.0 * fs)
        raw_analysis = np.array(raw_ecg[-analysis_size:])
        filt_analysis = apply_bandpass_filter(raw_analysis, lowcut, highcut, fs)
        if notch_freq is not None:
            filt_analysis = apply_notch_filter(filt_analysis, notch_freq, fs)
        
        # Peak Detection
        thresh = np.percentile(filt_analysis, 90) * 0.6
        peaks = []
        last_peak = -100
        refractory = int(0.25 * fs)
        for i in range(1, len(filt_analysis) - 1):
            if filt_analysis[i] > thresh and filt_analysis[i] > filt_analysis[i-1] and filt_analysis[i] > filt_analysis[i+1]:
                if i - last_peak > refractory:
                    peaks.append(i)
                    last_peak = i
                    
        # Update markers on plot (translate peak indices in visual range)
        visual_peaks = []
        visual_peaks_y = []
        for p in peaks:
            idx_in_visual = p - (len(filt_analysis) - len(filt_centered))
            if 0 <= idx_in_visual < len(filt_centered):
                dec_idx = idx_in_visual // dec_factor
                visual_peaks.append(dec_idx)
                visual_peaks_y.append(filt_centered_plot[min(dec_idx, len(filt_centered_plot)-1)])
                
        ecg_p.r_peak_curve.setData(visual_peaks, visual_peaks_y)
        
        # Compute HR and HRV SDNN/RMSSD
        if len(peaks) >= 2:
            rr_sec = np.diff(peaks) / float(fs)
            hr_bpm = 60.0 / np.mean(rr_sec)
            sdnn = np.std(rr_sec) * 1000.0
            rmssd = np.sqrt(np.mean(np.diff(rr_sec)**2)) * 1000.0
            
            ecg_p.lbl_hr.setText(f"Heart Rate: {hr_bpm:.1f} BPM")
            ecg_p.lbl_rr.setText(f"Mean RR: {np.mean(rr_sec)*1000:.1f} ms")
            ecg_p.lbl_sdnn.setText(f"SDNN: {sdnn:.1f} ms")
            ecg_p.lbl_rmssd.setText(f"RMSSD: {rmssd:.1f} ms")
        else:
            ecg_p.lbl_hr.setText("Heart Rate: -- BPM")
            ecg_p.lbl_rr.setText("Mean RR: -- ms")
            ecg_p.lbl_sdnn.setText("SDNN: -- ms")
            ecg_p.lbl_rmssd.setText("RMSSD: -- ms")
            
        # Auto-zoom and FFT
        ecg_p.update_auto_zoom(raw_centered_plot, filt_centered_plot)
        ecg_p.update_fft(filt_centered, fs)
        
        # Region Colors
        ecg_p.update_region_color(list(self.buffer.local_qualities['ecg']))
        
    def _update_emg(self):
        emg_p = self.dashboard.emg_panel
        fs = self.buffer.rates['emg']
        
        with self.buffer.lock:
            raw_emg = list(self.buffer.raw['emg'])
            
        if len(raw_emg) < 50:
            return
            
        try:
            lowcut = float(emg_p.lowcut_input.text().strip())
            highcut = float(emg_p.highcut_input.text().strip())
        except:
            lowcut, highcut = 20.0, 450.0
            
        # Get notch filter configuration
        notch_text = self.dashboard.control_panel.notch_select.currentText()
        notch_freq = None
        if "50 Hz" in notch_text:
            notch_freq = 50.0
        elif "60 Hz" in notch_text:
            notch_freq = 60.0

        # 1. Real-time plotting (last 300 * dec_factor samples, decimated to 300 points to match EDA speed)
        dec_factor = max(1, int(round(fs / 20.0)))
        window_size = 300 * dec_factor
        raw_plot = np.array(raw_emg[-window_size:])
        raw_centered = raw_plot - np.mean(raw_plot)
        
        # Apply bandpass filter to the raw visual chunk
        filt_centered = apply_bandpass_filter(raw_plot, lowcut, highcut, fs) - np.mean(raw_plot)
        if notch_freq is not None:
            filt_centered = apply_notch_filter(filt_centered, notch_freq, fs)
            
        # Decimate for plotting
        raw_centered_plot = raw_centered[::dec_factor]
        filt_centered_plot = filt_centered[::dec_factor]
        
        emg_p.emg_raw_curve.setData(raw_centered_plot)
        emg_p.emg_curve.setData(filt_centered_plot)
        
        # Analyze last 1.0 second of data
        analysis_size = int(1.0 * fs)
        raw_analysis = np.array(raw_emg[-analysis_size:])
        filt_analysis = apply_bandpass_filter(raw_analysis, lowcut, highcut, fs)
        if notch_freq is not None:
            filt_analysis = apply_notch_filter(filt_analysis, notch_freq, fs)
        
        rms = np.sqrt(np.mean(filt_analysis**2))
        mav = np.mean(np.abs(filt_analysis))
        iemg = np.sum(np.abs(filt_analysis)) * (1.0 / fs)
        
        # Active muscle state threshold
        state_str = "ACTIVE" if rms > 0.05 else "REST"
        
        # Compute Median Freq
        nperseg = min(len(filt_analysis), 1024)
        f, psd = welch(filt_analysis, fs=fs, nperseg=nperseg)
        median_freq = 0.0
        if len(psd) > 0:
            cumsum = np.cumsum(psd)
            if cumsum[-1] > 0:
                idx = np.where(cumsum >= 0.5 * cumsum[-1])[0]
                if len(idx) > 0:
                    median_freq = f[idx[0]]
                    
        emg_p.lbl_rms.setText(f"RMS: {rms * 1000:.1f} uV")
        emg_p.lbl_mav.setText(f"MAV: {mav * 1000:.1f} uV")
        emg_p.lbl_iemg.setText(f"IEMG: {iemg:.2f} mV·s")
        emg_p.lbl_med_freq.setText(f"Median Freq: {median_freq:.1f} Hz")
        emg_p.lbl_state.setText(f"Muscle State: {state_str}")
        
        emg_p.update_auto_zoom(raw_centered_plot, filt_centered_plot)
        emg_p.update_fft(filt_centered, fs)
        emg_p.update_region_color(list(self.buffer.local_qualities['emg']))
        
    def _update_resp(self):
        resp_p = self.dashboard.resp_panel
        fs = self.buffer.rates['resp']
        
        with self.buffer.lock:
            raw_resp = list(self.buffer.raw['resp'])
            
        if len(raw_resp) < 50:
            return
            
        try:
            cutoff = float(resp_p.cutoff_input.text().strip())
        except:
            cutoff = 2.0
            
        # Get notch filter configuration
        notch_text = self.dashboard.control_panel.notch_select.currentText()
        notch_freq = None
        if "50 Hz" in notch_text:
            notch_freq = 50.0
        elif "60 Hz" in notch_text:
            notch_freq = 60.0

        # 1. Real-time plotting (last 6 seconds of data)
        window_size = int(6.0 * fs)
        raw_plot = np.array(raw_resp[-window_size:])
        raw_centered = raw_plot - np.mean(raw_plot)
        filt_centered = apply_bandpass_filter(raw_plot, 0.05, cutoff, fs) - np.mean(raw_plot)
        if notch_freq is not None:
            filt_centered = apply_notch_filter(filt_centered, notch_freq, fs)
        
        resp_p.resp_raw_curve.setData(raw_centered)
        resp_p.resp_curve.setData(filt_centered)
        
        # Analyze last 15 seconds of data for respiration rate
        analysis_size = int(15.0 * fs)
        raw_analysis = np.array(raw_resp[-analysis_size:])
        filt_analysis = apply_bandpass_filter(raw_analysis, 0.05, cutoff, fs)
        if notch_freq is not None:
            filt_analysis = apply_notch_filter(filt_analysis, notch_freq, fs)
        
        # Peak / Valley indicators
        mean_v = np.mean(filt_analysis)
        std_v = np.std(filt_analysis)
        peak_th = mean_v + 0.1 * std_v
        valley_th = mean_v - 0.1 * std_v
        
        peaks = []
        valleys = []
        refractory = int(1.5 * fs)
        
        last_p = -100
        for i in range(1, len(filt_analysis) - 1):
            if filt_analysis[i] > peak_th and filt_analysis[i] > filt_analysis[i-1] and filt_analysis[i] > filt_analysis[i+1]:
                if i - last_p > refractory:
                    peaks.append(i)
                    last_p = i
                    
        last_v = -100
        for i in range(1, len(filt_analysis) - 1):
            if filt_analysis[i] < valley_th and filt_analysis[i] < filt_analysis[i-1] and filt_analysis[i] < filt_analysis[i+1]:
                if i - last_v > refractory:
                    valleys.append(i)
                    last_v = i
                    
        # Filter Peaks/Valleys to plot visual range
        vis_peaks, vis_peaks_y = [], []
        vis_valleys, vis_valleys_y = [], []
        offset = len(filt_analysis) - len(filt_centered)
        for p in peaks:
            idx = p - offset
            if 0 <= idx < len(filt_centered):
                vis_peaks.append(idx)
                vis_peaks_y.append(filt_centered[idx])
        for v in valleys:
            idx = v - offset
            if 0 <= idx < len(filt_centered):
                vis_valleys.append(idx)
                vis_valleys_y.append(filt_centered[idx])
                
        resp_p.peak_curve.setData(vis_peaks, vis_peaks_y)
        resp_p.valley_curve.setData(vis_valleys, vis_valleys_y)
        
        # Rate & IE math
        rr = 0.0
        insp_d, exp_d = 0.0, 0.0
        ie_str = "1:1"
        if len(peaks) >= 2:
            rr_sec = np.diff(peaks) / float(fs)
            rr = 60.0 / np.mean(rr_sec)
            
            # Simple I:E duration calculator
            insp_times, exp_times = [], []
            for p in peaks:
                priors = [v for v in valleys if v < p]
                posts = [v for v in valleys if v > p]
                if priors and posts:
                    insp_times.append((p - priors[-1]) / float(fs))
                    exp_times.append((posts[0] - p) / float(fs))
            if insp_times and exp_times:
                insp_d = np.mean(insp_times)
                exp_d = np.mean(exp_times)
                if exp_d > 0:
                    ie_str = f"1:{exp_d/insp_d:.1f}"
                    
        resp_p.lbl_rr.setText(f"Respiration Rate: {rr:.1f} Breaths/Min" if rr > 0 else "Respiration Rate: -- Breaths/Min")
        resp_p.lbl_insp.setText(f"Avg Inspiration: {insp_d:.2f} s" if insp_d > 0 else "Avg Inspiration: -- s")
        resp_p.lbl_exp.setText(f"Avg Expiration: {exp_d:.2f} s" if exp_d > 0 else "Avg Expiration: -- s")
        resp_p.lbl_ie.setText(f"I:E Ratio: {ie_str}")
        
        resp_p.update_auto_zoom(raw_centered, filt_centered)
        resp_p.update_fft(filt_centered)
        resp_p.update_region_color(list(self.buffer.local_qualities['resp']))
        
    def _update_eda(self):
        eda_p = self.dashboard.eda_panel
        fs = self.buffer.rates['eda']
        
        with self.buffer.lock:
            raw_eda = list(self.buffer.raw['eda'])
            
        if len(raw_eda) < 30:
            return
            
        try:
            cutoff = float(eda_p.cutoff_input.text().strip())
        except:
            cutoff = 2.0
            
        # Get notch filter configuration
        notch_text = self.dashboard.control_panel.notch_select.currentText()
        notch_freq = None
        if "50 Hz" in notch_text:
            notch_freq = 50.0
        elif "60 Hz" in notch_text:
            notch_freq = 60.0

        window_size = int(15.0 * fs)
        raw_plot = np.array(raw_eda[-window_size:])
        raw_mean = np.mean(raw_plot)
        raw_centered = raw_plot - raw_mean
        filt_centered = apply_lowpass_filter(raw_plot, cutoff, fs) - raw_mean
        if notch_freq is not None:
            filt_centered = apply_notch_filter(filt_centered, notch_freq, fs)
        
        # Tonic/Phasic decomposition using 0.05 Hz filter
        scl_centered = apply_lowpass_filter(raw_plot, 0.05, fs) - raw_mean
        scl_centered = np.minimum(scl_centered, filt_centered)
        scr_centered = filt_centered - scl_centered
        
        eda_p.eda_raw_curve.setData(raw_centered)
        eda_p.eda_curve.setData(filt_centered)
        # SCL Baseline
        eda_p.scl_curve.setData(scl_centered)
        
        # Phasic Peak Detection (Threshold = 0.05 uS)
        peaks = []
        refractory = int(1.0 * fs)
        last_p = -100
        for i in range(1, len(scr_centered) - 1):
            if scr_centered[i] > 0.05 and scr_centered[i] > scr_centered[i-1] and scr_centered[i] > scr_centered[i+1]:
                if i - last_p > refractory:
                    peaks.append(i)
                    last_p = i
                    
        eda_p.peak_curve.setData(peaks, filt_centered[peaks])
        
        # Absolute current values for label
        curr_scl = raw_plot[-1] # SCL baseline
        curr_scr = scr_centered[-1]
        active_peaks = len(peaks)
        
        stress_str = "LOW"
        if active_peaks >= 3:
            stress_str = "HIGH"
        elif active_peaks >= 1:
            stress_str = "MODERATE"
            
        eda_p.lbl_scl.setText(f"SCL: {curr_scl:.3f} uS")
        eda_p.lbl_scr.setText(f"SCR Phasic: {curr_scr:.3f} uS")
        eda_p.lbl_peaks.setText(f"SCR Peaks: {active_peaks}")
        eda_p.lbl_stress.setText(f"Stress Index: {stress_str}")
        
        eda_p.update_auto_zoom(raw_centered, filt_centered)
        eda_p.update_fft(filt_centered)
        eda_p.update_region_color(list(self.buffer.local_qualities['eda']))
        
    def _update_fnirs(self):
        fnirs_p = self.dashboard.fnirs_panel
        fs = self.buffer.rates['fnirs']
        
        with self.buffer.lock:
            hbo_raw = list(self.buffer.raw['fnirs_hbo'])
            hbr_raw = list(self.buffer.raw['fnirs_hbr'])
            
        if len(hbo_raw) < 20:
            return
            
        try:
            cutoff = float(fnirs_p.cutoff_input.text().strip())
        except:
            cutoff = 0.5
            
        # Get notch filter configuration
        notch_text = self.dashboard.control_panel.notch_select.currentText()
        notch_freq = None
        if "50 Hz" in notch_text:
            notch_freq = 50.0
        elif "60 Hz" in notch_text:
            notch_freq = 60.0

        window_size = int(30.0 * fs)
        raw_hbo_plot = np.array(hbo_raw[-window_size:])
        raw_hbr_plot = np.array(hbr_raw[-window_size:])
        
        # Center raw signals for baseline removal (only for raw plot display)
        hbo_raw_mean = np.mean(raw_hbo_plot)
        hbr_raw_mean = np.mean(raw_hbr_plot)
        raw_hbo_centered = raw_hbo_plot - hbo_raw_mean
        raw_hbr_centered = raw_hbr_plot - hbr_raw_mean
        
        # Apply lowpass filter
        hbo_filt_centered = apply_lowpass_filter(raw_hbo_plot, cutoff, fs) - hbo_raw_mean
        hbr_filt_centered = apply_lowpass_filter(raw_hbr_plot, cutoff, fs) - hbr_raw_mean
        if notch_freq is not None:
            hbo_filt_centered = apply_notch_filter(hbo_filt_centered, notch_freq, fs)
            hbr_filt_centered = apply_notch_filter(hbr_filt_centered, notch_freq, fs)
        
        fnirs_p.hbo_raw_curve.setData(raw_hbo_centered)
        fnirs_p.hbo_curve.setData(hbo_filt_centered)
        fnirs_p.hbr_raw_curve.setData(raw_hbr_centered)
        fnirs_p.hbr_curve.setData(hbr_filt_centered)
        
        # Trends & Brain activation detection (last 200 samples)
        analysis_size = int(20.0 * fs)
        raw_hbo_an = np.array(hbo_raw[-analysis_size:])
        raw_hbr_an = np.array(hbr_raw[-analysis_size:])
        filt_hbo_an = apply_lowpass_filter(raw_hbo_an, cutoff, fs)
        filt_hbr_an = apply_lowpass_filter(raw_hbr_an, cutoff, fs)
        if notch_freq is not None:
            filt_hbo_an = apply_notch_filter(filt_hbo_an, notch_freq, fs)
            filt_hbr_an = apply_notch_filter(filt_hbr_an, notch_freq, fs)
        
        trend_win = 5 * fs
        hbo_t = np.mean(filt_hbo_an[-trend_win:])
        hbr_t = np.mean(filt_hbr_an[-trend_win:])
        boi = filt_hbo_an[-1] - filt_hbr_an[-1]
        
        # Activation detection
        baseline_hbo = np.percentile(filt_hbo_an, 15)
        baseline_hbr = np.percentile(filt_hbr_an, 85)
        is_active = (filt_hbo_an[-1] - baseline_hbo) > 0.4 and (filt_hbr_an[-1] - baseline_hbr) < -0.1
        state_str = "ACTIVATED" if is_active else "RESTING"
        
        fnirs_p.lbl_hbo.setText(f"HbO Trend: {hbo_t:.2f} uM")
        fnirs_p.lbl_hbr.setText(f"HbR Trend: {hbr_t:.2f} uM")
        fnirs_p.lbl_boi.setText(f"BOI: {boi:.2f} uM")
        fnirs_p.lbl_state.setText(f"Hemodynamic State: {state_str}")
        
        fnirs_p.update_auto_zoom(raw_hbo_centered, raw_hbr_centered, hbo_filt_centered, hbr_filt_centered)
        fnirs_p.update_fft(hbo_filt_centered, hbr_filt_centered)
        fnirs_p.update_region_color(list(self.buffer.local_qualities['fnirs']))
        
    def _update_status_panel(self):
        # 1. Update streaming / recording counters in Status Panel
        if self.recording:
            dur = self.recorder.get_duration()
            self.dashboard.status_panel.recording_label.setText(f"Recording : 🔴 Recording ({dur:.1f}s)")
        else:
            if self.recorder and self.recorder.elapsed_time > 0:
                self.dashboard.status_panel.recording_label.setText(f"Recording : ⚪ Stopped ({self.recorder.elapsed_time:.1f}s)")
            else:
                self.dashboard.status_panel.recording_label.setText("Recording : ⚪ Not Recording")
                
        # 2. Update multi-rate Signal Quality Indicators label
        quals = {}
        for sig in ['ecg', 'emg', 'resp', 'eda', 'fnirs']:
            quals[sig] = self.buffer.global_qualities[sig]
            
        def get_dot(q):
            if q == 'Good': return '🟢'
            if q == 'Fair': return '🟡'
            return '🔴'
            
        quality_str = f"Signal Quality: ECG {get_dot(quals['ecg'])} {quals['ecg']} | EMG {get_dot(quals['emg'])} {quals['emg']} | RESP {get_dot(quals['resp'])} {quals['resp']} | EDA {get_dot(quals['eda'])} {quals['eda']} | fNIRS {get_dot(quals['fnirs'])} {quals['fnirs']}"
        self.dashboard.status_panel.quality_label.setText(quality_str)
