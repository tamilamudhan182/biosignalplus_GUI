import time
import pandas as pd
import numpy as np
from io import BytesIO
from filters import apply_bandpass_filter, apply_lowpass_filter

class SignalRecorder:
    def __init__(self):
        self.is_recording = False
        self.start_time = None
        self.elapsed_time = 0.0
        
        # Buffer to store samples during recording
        # Each entry is a tuple: (timestamp, value)
        self.buffers = {
            'ecg': [],
            'emg': [],
            'resp': [],
            'eda': [],
            'fnirs_hbo': [],
            'fnirs_hbr': []
        }

    def start(self):
        self.is_recording = True
        self.start_time = time.time()
        self.elapsed_time = 0.0
        for key in self.buffers:
            self.buffers[key] = []

    def stop(self):
        if self.is_recording:
            self.is_recording = False
            self.elapsed_time = time.time() - self.start_time

    def add_sample(self, signal_type, timestamp, raw_val):
        if not self.is_recording:
            return
        self.buffers[signal_type].append((timestamp, raw_val))

    def get_duration(self):
        if self.is_recording:
            return time.time() - self.start_time
        return self.elapsed_time

    def export_to_csv(self):
        """
        Processes and filters full recorded buffers, resamples all channels 
        to a unified 1000 Hz timeline, and returns CSV bytes.
        """
        # Form base 1000 Hz grid using EMG or timeline bounds
        emg_data = self.buffers['emg']
        if not emg_data:
            all_ts = []
            for b in self.buffers.values():
                if b:
                    all_ts.extend([x[0] for x in b])
            if not all_ts:
                return b""  # Empty CSV
            min_t, max_t = min(all_ts), max(all_ts)
            target_ts = np.arange(min_t, max_t, 0.001)  # 1000 Hz
        else:
            target_ts = np.array([x[0] for x in emg_data])
            
        if len(target_ts) == 0:
            return b""

        df = pd.DataFrame({'Timestamp': target_ts})
        df['Time_Seconds'] = target_ts - target_ts[0]

        # Extract raw arrays
        def get_raw_arrays(key):
            buf = self.buffers[key]
            if not buf:
                return np.array([]), np.array([])
            ts = np.array([x[0] for x in buf])
            vals = np.array([x[1] for x in buf])
            return ts, vals

        # Pull raw signals
        ts_ecg, raw_ecg = get_raw_arrays('ecg')
        ts_emg, raw_emg = get_raw_arrays('emg')
        ts_resp, raw_resp = get_raw_arrays('resp')
        ts_eda, raw_eda = get_raw_arrays('eda')
        ts_hbo, raw_hbo = get_raw_arrays('fnirs_hbo')
        ts_hbr, raw_hbr = get_raw_arrays('fnirs_hbr')

        # Apply Filters on the complete raw arrays (full sequence) to avoid boundary issues
        filt_ecg = apply_bandpass_filter(raw_ecg, 0.5, 40.0, 250) if len(raw_ecg) > 15 else raw_ecg
        filt_emg = apply_bandpass_filter(raw_emg, 20.0, 450.0, 1000) if len(raw_emg) > 15 else raw_emg
        filt_resp = apply_lowpass_filter(raw_resp, 2.0, 50) if len(raw_resp) > 15 else raw_resp
        filt_eda = apply_lowpass_filter(raw_eda, 2.0, 20) if len(raw_eda) > 15 else raw_eda
        filt_hbo = apply_lowpass_filter(raw_hbo, 0.5, 10) if len(raw_hbo) > 15 else raw_hbo
        filt_hbr = apply_lowpass_filter(raw_hbr, 0.5, 10) if len(raw_hbr) > 15 else raw_hbr

        # Resample helper
        def resample(ts_src, vals_src):
            if len(ts_src) == 0 or len(vals_src) == 0:
                return np.full_like(target_ts, np.nan)
            return np.interp(target_ts, ts_src, vals_src)

        # Resample signals
        df['ECG_Raw'] = resample(ts_ecg, raw_ecg)
        df['ECG_Filtered'] = resample(ts_ecg, filt_ecg)
        
        df['EMG_Raw'] = resample(ts_emg, raw_emg)
        df['EMG_Filtered'] = resample(ts_emg, filt_emg)
        
        df['RESP_Raw'] = resample(ts_resp, raw_resp)
        df['RESP_Filtered'] = resample(ts_resp, filt_resp)
        
        df['EDA_Raw'] = resample(ts_eda, raw_eda)
        df['EDA_Filtered'] = resample(ts_eda, filt_eda)
        
        df['fNIRS_HbO_Raw'] = resample(ts_hbo, raw_hbo)
        df['fNIRS_HbO_Filtered'] = resample(ts_hbo, filt_hbo)
        df['fNIRS_HbR_Raw'] = resample(ts_hbr, raw_hbr)
        df['fNIRS_HbR_Filtered'] = resample(ts_hbr, filt_hbr)

        # Calculate features on resampled timelines for simplicity
        # Heart Rate estimation from ECG_Filtered
        df['ECG_HeartRate'] = np.nan
        if len(ts_ecg) > 250:
            # Simple threshold peaks on filtered ECG
            thresh = np.percentile(filt_ecg, 90) * 0.6
            peaks = []
            last_p = -100
            for i in range(1, len(filt_ecg) - 1):
                if filt_ecg[i] > thresh and filt_ecg[i] > filt_ecg[i-1] and filt_ecg[i] > filt_ecg[i+1]:
                    if i - last_p > 62: # 250 ms at 250Hz
                        peaks.append(ts_ecg[i])
                        last_p = i
            if len(peaks) >= 2:
                # Interpolate instantaneous HR to target timeline
                hr_ts = np.array(peaks[1:])
                hr_vals = 60.0 / np.diff(peaks)
                df['ECG_HeartRate'] = np.interp(target_ts, hr_ts, hr_vals, left=hr_vals[0], right=hr_vals[-1])

        # EMG RMS
        df['EMG_RMS'] = np.nan
        if len(filt_emg) > 100:
            # Sliding RMS window of 100 ms (100 samples)
            rms_vals = np.sqrt(np.convolve(filt_emg**2, np.ones(100)/100, mode='same'))
            df['EMG_RMS'] = resample(ts_emg, rms_vals)

        # Respiration Rate
        df['RESP_RespirationRate'] = np.nan
        if len(ts_resp) > 100:
            thresh = np.mean(filt_resp)
            peaks = []
            last_p = -100
            for i in range(1, len(filt_resp) - 1):
                if filt_resp[i] > thresh and filt_resp[i] > filt_resp[i-1] and filt_resp[i] > filt_resp[i+1]:
                    if i - last_p > 75: # 1.5s at 50Hz
                        peaks.append(ts_resp[i])
                        last_p = i
            if len(peaks) >= 2:
                rr_ts = np.array(peaks[1:])
                rr_vals = 60.0 / np.diff(peaks)
                df['RESP_RespirationRate'] = np.interp(target_ts, rr_ts, rr_vals, left=rr_vals[0], right=rr_vals[-1])

        # EDA Tonic SCL
        df['EDA_SCL'] = np.nan
        if len(filt_eda) > 0:
            scl_vals = apply_lowpass_filter(raw_eda, 0.05, 20) if len(raw_eda) > 15 else raw_eda
            df['EDA_SCL'] = resample(ts_eda, scl_vals)

        # fNIRS Brain Oxygenation Index
        df['fNIRS_BOI'] = df['fNIRS_HbO_Filtered'] - df['fNIRS_HbR_Filtered']

        # Output to CSV bytes
        output = BytesIO()
        df.to_csv(output, index=False)
        return output.getvalue()
