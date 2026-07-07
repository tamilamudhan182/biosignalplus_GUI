import sys
import os
import time
from pathlib import Path
from types import ModuleType
import numpy as np

# 1. Mock the plux module before any other imports
mock_plux = ModuleType('plux')
class MockSignalsDev:
    def __init__(self, address):
        self.address = address
        print(f"[MOCK] SignalsDev connection initialized for {address}")
    def getBattery(self):
        return 85.0
    def close(self):
        print("[MOCK] SignalsDev connection closed")
    def getSensors(self):
        class MockSensor:
            def __init__(self, clas):
                self.clas = clas
        return {
            1: MockSensor(2), # ECG
            2: MockSensor(1), # EMG
            3: MockSensor(6), # RESP
            4: MockSensor(4), # EDA
            9: MockSensor(18) # fNIRS
        }

class MockSource:
    def __init__(self):
        self.port = 0
        self.freqDivisor = 1
        self.nBits = 16
        self.chMask = 0x01

mock_plux.SignalsDev = MockSignalsDev
mock_plux.Source = MockSource
sys.modules['plux'] = mock_plux

# 2. Import PyQt6 and Dashboard
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import pyqtgraph as pg

import biosignal_worker
from dashboard import Dashboard

# 3. Create Mock CustomPluxDevice to override the one in biosignal_worker
class MockCustomPluxDevice:
    def __init__(self, address):
        self.worker = None
        self.address = address
        self.running = False
        print(f"[MOCK] MockCustomPluxDevice created for {address}")

    def getBattery(self):
        return 85.0

    def getSensors(self):
        class MockSensor:
            def __init__(self, clas):
                self.clas = clas
        return {
            1: MockSensor(2), # ECG
            2: MockSensor(1), # EMG
            3: MockSensor(6), # RESP
            4: MockSensor(4), # EDA
            9: MockSensor(18) # fNIRS
        }

    def start(self, sampling_rate, sources):
        print(f"[MOCK] MockCustomPluxDevice started acquisition: {sampling_rate} Hz, sources: {sources}")
        self.sampling_rate = sampling_rate
        self.running = True

    def loop(self):
        print("[MOCK] MockCustomPluxDevice loop starting...")
        nSeq = 0
        t_start = time.time()
        
        while self.running and (self.worker and self.worker.running):
            t = time.time() - t_start
            
            # Generate simulated data for 6 channels
            # channel 0 (ECG): sine wave + QRS peaks
            val_ecg = 0.2 * np.sin(2 * np.pi * 1.2 * t)
            if (nSeq % 1000) < 50:
                val_ecg += 1.5 * np.exp(-((nSeq % 1000 - 25)/8.0)**2)
            else:
                # Add some small noise
                val_ecg += np.random.normal(0, 0.02)
                
            # channel 1 (EMG): high frequency noise with active bursts
            val_emg = np.random.normal(0, 0.05)
            if (nSeq % 2000) < 400: # active muscle
                val_emg += np.random.normal(0, 0.4)
                
            # channel 2 (RESP): slow sine wave at 0.25 Hz
            val_resp = 2.0 * np.sin(2 * np.pi * 0.25 * t) + np.random.normal(0, 0.02)
            
            # channel 3 (EDA): slow baseline with phasic peaks
            val_eda = 5.0 + 0.05 * np.sin(2 * np.pi * 0.03 * t)
            if (nSeq % 4000) < 1000:
                # Simulate a skin conductance response
                peak_phase = nSeq % 4000
                val_eda += 0.5 * (peak_phase / 1000.0) * np.exp(-((peak_phase - 500)/200.0)**2)
            val_eda += np.random.normal(0, 0.001)
            
            # channel 4 (fNIRS HbO): slow wave
            val_hbo = 12.0 + 0.3 * np.sin(2 * np.pi * 0.08 * t) + np.random.normal(0, 0.01)
            # channel 5 (fNIRS HbR): slow wave (out of phase)
            val_hbr = 8.0 - 0.1 * np.sin(2 * np.pi * 0.08 * t) + np.random.normal(0, 0.01)
            
            data = [val_ecg, val_emg, val_resp, val_eda, val_hbo, val_hbr]
            self.worker.on_frame_received(nSeq, data)
            
            nSeq += 1
            # Sleep tiny bit to simulate real-time rate without lockup
            time.sleep(0.001)
            
        print("[MOCK] MockCustomPluxDevice loop exited.")

    def stop(self):
        self.running = False
        print("[MOCK] MockCustomPluxDevice stopped")

    def close(self):
        print("[MOCK] MockCustomPluxDevice closed")

# Monkeypatch the worker's class
biosignal_worker.CustomPluxDevice = MockCustomPluxDevice

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    
    db = Dashboard()
    db.show()
    
    print("Dashboard loaded successfully.")
    
    # 1. Update target sample rates to custom values
    db.control_panel.rate_ecg.setText("250")
    db.control_panel.rate_emg.setText("500")
    db.control_panel.rate_resp.setText("50")
    db.control_panel.rate_eda.setText("25")
    db.control_panel.rate_fnirs.setText("20")
    
    # Select 50 Hz notch filter
    db.control_panel.notch_select.setCurrentText("50 Hz")
    
    # 2. Click connect
    print("Clicking Connect...")
    db.control_panel.connect_button.click()
    
    # 3. Click start
    print("Clicking Start...")
    db.control_panel.start_button.click()
    
    # Define verification step to run after 4 seconds of streaming
    def verify_and_capture():
        try:
            print("Verifying target rates reconfiguration...")
            
            # Verify rates inside buffer
            rates = db.signal_panel.buffer.rates
            assert rates['ecg'] == 250, f"ECG rate mismatch: {rates['ecg']}"
            assert rates['emg'] == 500, f"EMG rate mismatch: {rates['emg']}"
            assert rates['resp'] == 50, f"RESP rate mismatch: {rates['resp']}"
            assert rates['eda'] == 25, f"EDA rate mismatch: {rates['eda']}"
            assert rates['fnirs'] == 20, f"fNIRS rate mismatch: {rates['fnirs']}"
            
            # Verify local/global queues exist and have elements
            with db.signal_panel.buffer.lock:
                ecg_len = len(db.signal_panel.buffer.raw['ecg'])
                emg_len = len(db.signal_panel.buffer.raw['emg'])
                print(f"Data counts in buffers -> ECG: {ecg_len}, EMG: {emg_len}")
                assert ecg_len > 0, "No ECG data collected"
                assert emg_len > 0, "No EMG data collected"
                
            # Capture screenshot
            screenshot_path = "C:/Users/HP/.gemini/antigravity-ide/brain/d85c73ab-a84b-439d-86ce-4d7ad74d342f/custom_rates_screenshot.png"
            pixmap = db.grab()
            pixmap.save(screenshot_path)
            print(f"Screenshot successfully saved to: {screenshot_path}")
            
            print("All verification checks PASSED successfully!")
            
        except Exception as e:
            print(f"Verification FAILED: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Safely stop stream, disconnect, and close
            print("Stopping stream and closing dashboard...")
            db.signal_panel.stop_stream()
            db.signal_panel.disconnect_device()
            db.close()
            app.quit()
            
    # Run the verification after 4 seconds
    QTimer.singleShot(4000, verify_and_capture)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
