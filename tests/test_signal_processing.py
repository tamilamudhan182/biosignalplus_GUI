import sys
from types import ModuleType

# Mock the plux module before any other imports to prevent DLL load errors
mock_plux = ModuleType('plux')
class MockSignalsDev:
    def __init__(self, address):
        self.address = address
    def getBattery(self):
        return 85.0
    def close(self):
        pass
    def getSensors(self):
        return {}

class MockSource:
    def __init__(self):
        self.port = 0
        self.freqDivisor = 1
        self.nBits = 16
        self.chMask = 0x01

mock_plux.SignalsDev = MockSignalsDev
mock_plux.Source = MockSource
sys.modules['plux'] = mock_plux

import unittest
import numpy as np
from filters import apply_bandpass_filter, apply_lowpass_filter, apply_notch_filter

class TestSignalProcessing(unittest.TestCase):
    def test_notch_filter(self):
        # Generate a test signal: 10 Hz sine wave + 50 Hz powerline interference
        fs = 500
        t = np.arange(0, 2, 1.0/fs)
        signal = np.sin(2 * np.pi * 10 * t) + 1.0 * np.sin(2 * np.pi * 50 * t)
        
        # Apply notch filter at 50 Hz
        filtered = apply_notch_filter(signal, 50.0, fs)
        
        self.assertEqual(len(filtered), len(signal))
        # Verify 50 Hz noise is significantly reduced in variance compared to raw
        # If we filter out 50 Hz, the filtered signal variance should be close to 0.5 (var of sin(2*pi*10*t) which is 0.5)
        # while original signal variance is ~1.0
        self.assertAlmostEqual(np.var(filtered), 0.5, delta=0.1)

    def test_lowpass_filter(self):
        # Generate a test signal: slow sine wave + high frequency noise
        fs = 100
        t = np.arange(0, 5, 1.0/fs)
        slow_freq = 1.0
        fast_freq = 40.0
        
        signal = np.sin(2 * np.pi * slow_freq * t) + 0.5 * np.sin(2 * np.pi * fast_freq * t)
        
        # Apply lowpass filter at 5 Hz (should remove 40 Hz noise)
        filtered = apply_lowpass_filter(signal, 5.0, fs)
        
        self.assertEqual(len(filtered), len(signal))
        # Ensure fast frequency power is significantly reduced
        raw_var = np.var(signal)
        filt_var = np.var(filtered)
        self.assertTrue(filt_var < raw_var)
        
    def test_bandpass_filter(self):
        # Generate a test signal: DC drift + bandpass component + high frequency noise
        fs = 200
        t = np.arange(0, 5, 1.0/fs)
        
        signal = 5.0 + np.sin(2 * np.pi * 10 * t) + np.random.normal(0, 0.5, len(t))
        
        # Bandpass between 5 and 15 Hz
        filtered = apply_bandpass_filter(signal, 5.0, 15.0, fs)
        
        self.assertEqual(len(filtered), len(signal))
        # Filtered signal mean should be close to 0 (DC drift removed)
        self.assertTrue(abs(np.mean(filtered)) < 0.2)
        
    def test_r_peak_detection_and_hrv(self):
        # Generate simulated ECG peaks at exactly 1.0 second intervals (60 BPM)
        fs = 250
        t = np.arange(0, 10, 1.0/fs)
        filt_arr = np.zeros_like(t)
        
        # Place synthetic peaks (amplitude 1.5) at seconds 1, 2, 3, 4, 5, 6, 7, 8, 9
        for peak_sec in range(1, 10):
            idx = int(peak_sec * fs)
            # Add Gaussian-like QRS peak
            filt_arr[idx-2:idx+3] = [0.2, 0.8, 1.5, 0.8, 0.2]
            
        # Run peak detection
        thresh = np.percentile(filt_arr, 90) * 0.6
        peaks = []
        last_peak = -100
        refractory = int(0.25 * fs)
        
        for i in range(1, len(filt_arr) - 1):
            if filt_arr[i] > thresh and filt_arr[i] > filt_arr[i-1] and filt_arr[i] > filt_arr[i+1]:
                if i - last_peak > refractory:
                    peaks.append(i)
                    last_peak = i
                    
        # Should detect exactly 9 peaks
        self.assertEqual(len(peaks), 9)
        
        # Calculate HRV metrics
        rr_intervals = np.diff(peaks) / float(fs) # seconds
        hr_bpm = 60.0 / np.mean(rr_intervals)
        sdnn = np.std(rr_intervals) * 1000.0
        rmssd = np.sqrt(np.mean(np.diff(rr_intervals)**2)) * 1000.0
        
        self.assertAlmostEqual(hr_bpm, 60.0, places=1)
        self.assertAlmostEqual(sdnn, 0.0, places=1) # Perfectly periodic -> 0 standard deviation
        self.assertAlmostEqual(rmssd, 0.0, places=1)
        
    def test_temporal_smoothing_logic(self):
        # Test temporal smoothing majority voting simulation
        # Given a history of last 3 raw evaluations, find the majority
        def get_smoothed(history):
            counts = {'Good': 0, 'Fair': 0, 'Poor': 0}
            for q in history:
                counts[q] += 1
            smoothed = max(counts, key=counts.get)
            if counts[smoothed] < 2:
                # Tie/no majority, fallback to the latest
                return history[-1]
            return smoothed
            
        self.assertEqual(get_smoothed(['Good', 'Good', 'Good']), 'Good')
        self.assertEqual(get_smoothed(['Good', 'Poor', 'Good']), 'Good')
        self.assertEqual(get_smoothed(['Poor', 'Fair', 'Poor']), 'Poor')
        self.assertEqual(get_smoothed(['Good', 'Fair', 'Poor']), 'Poor') # tie-breaker to the latest
        self.assertEqual(get_smoothed(['Poor', 'Good', 'Fair']), 'Fair') # tie-breaker to the latest

    def test_gui_initialization(self):
        # Initialize QApplication in offscreen mode
        from PyQt6.QtWidgets import QApplication
        from dashboard import Dashboard
        
        app = QApplication.instance() or QApplication(['-platform', 'offscreen'])
        
        db = Dashboard()
        self.assertIsNotNone(db.status_panel)
        self.assertIsNotNone(db.control_panel)
        self.assertIsNotNone(db.tabs)
        self.assertEqual(db.tabs.count(), 5) # 5 tabs (ECG, EMG, RESP, EDA, fNIRS)
        
        self.assertEqual(db.tabs.tabText(0), "ECG")
        self.assertEqual(db.tabs.tabText(1), "EMG")
        self.assertEqual(db.tabs.tabText(2), "RESP")
        self.assertEqual(db.tabs.tabText(3), "EDA")
        self.assertEqual(db.tabs.tabText(4), "fNIRS")
        
        db.close()

    def test_channel_mapping_and_hbr_fallback(self):
        # Initialize BiosignalWorker and mock environment
        from biosignal_worker import SessionSignalBuffer, BiosignalWorker
        buffer_obj = SessionSignalBuffer()
        worker = BiosignalWorker(buffer_obj)
        
        # Test default fallback channel map
        worker.channel_map = {
            'ecg': 0, 'emg': 1, 'resp': 2, 'eda': 3, 'fnirs_hbo': 4, 'fnirs_hbr': 5
        }
        worker.decimation = {'ecg': 1, 'emg': 1, 'resp': 1, 'eda': 1, 'fnirs': 1}
        
        # Scenario A: both HbO and HbR have values
        data_a = [1.0, 2.0, 3.0, 4.0, 15000.0, 12000.0]
        worker.on_frame_received(0, data_a)
        self.assertEqual(buffer_obj.raw['fnirs_hbo'][-1], 15000.0)
        self.assertEqual(buffer_obj.raw['fnirs_hbr'][-1], 12000.0)
        
        # Scenario B: HbR is missing/0.0 but HbO has values
        data_b = [1.0, 2.0, 3.0, 4.0, 15000.0, 0.0]
        worker.on_frame_received(worker.decimation['fnirs'], data_b)
        
        # The worker should have automatically synthesized a non-zero HbR value
        synth_hbr = buffer_obj.raw['fnirs_hbr'][-1]
        self.assertNotEqual(synth_hbr, 0.0)
        # Verify it falls within expected physiological range (approx 20000 - 0.5 * 15000 = 12500)
        self.assertTrue(11000.0 < synth_hbr < 14000.0)

if __name__ == '__main__':
    unittest.main()

