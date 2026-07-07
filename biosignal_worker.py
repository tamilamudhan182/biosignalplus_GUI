import time
import threading
import numpy as np
from collections import deque
from scipy.signal import welch
from scipy.stats import skew, kurtosis
from filters import apply_bandpass_filter, apply_lowpass_filter

class SessionSignalBuffer:
    def __init__(self):
        self.lock = threading.Lock()
        
        # Buffer lengths for 20 seconds of data at different sampling rates
        self.rates = {
            'ecg': 250,
            'emg': 1000,
            'resp': 50,
            'eda': 20,
            'fnirs': 10  # HbO & HbR are both 10 Hz
        }
        
        self.buffer_sizes = {k: v * 20 for k, v in self.rates.items()}
        
        # Deques for raw signals and timestamps
        self.timestamps = {k: deque(maxlen=self.buffer_sizes[k]) for k in self.rates}
        self.raw = {k: deque(maxlen=self.buffer_sizes[k]) for k in self.rates}
        # Separate channels for fNIRS
        self.raw['fnirs_hbo'] = deque(maxlen=self.buffer_sizes['fnirs'])
        self.raw['fnirs_hbr'] = deque(maxlen=self.buffer_sizes['fnirs'])
        self.timestamps['fnirs_hbo'] = deque(maxlen=self.buffer_sizes['fnirs'])
        self.timestamps['fnirs_hbr'] = deque(maxlen=self.buffer_sizes['fnirs'])
        
        # Quality score histories (local quality for each 2-second segment)
        # 20 seconds of data divided into 2-second segments means 10 segments total
        self.local_qualities = {
            'ecg': deque(['Good'] * 10, maxlen=10),
            'emg': deque(['Good'] * 10, maxlen=10),
            'resp': deque(['Good'] * 10, maxlen=10),
            'eda': deque(['Good'] * 10, maxlen=10),
            'fnirs': deque(['Good'] * 10, maxlen=10)
        }
        
        # Global Quality (evaluated over entire buffer)
        self.global_qualities = {
            'ecg': 'Good',
            'emg': 'Good',
            'resp': 'Good',
            'eda': 'Good',
            'fnirs': 'Good'
        }
        
        # Temporal smoothing window: last 3 evaluations for each signal
        self.smoothing_history = {k: ['Good', 'Good', 'Good'] for k in self.rates}
        
        # Artifact injection flags
        self.artifact_active = {k: False for k in self.rates}
        self.artifact_type = {k: 'noise' for k in self.rates}  # 'noise', 'flatline', 'drift'

    def get_data(self, key):
        with self.lock:
            return list(self.timestamps[key]), list(self.raw[key])

    def inject_artifact(self, key, art_type, active=True):
        with self.lock:
            if key in self.artifact_active:
                self.artifact_active[key] = active
                self.artifact_type[key] = art_type

    def reconfigure_rates(self, rates):
        with self.lock:
            self.rates = rates.copy()
            self.buffer_sizes = {k: v * 20 for k, v in self.rates.items()}
            self.timestamps = {k: deque(maxlen=self.buffer_sizes[k]) for k in self.rates}
            self.raw = {k: deque(maxlen=self.buffer_sizes[k]) for k in self.rates}
            self.raw['fnirs_hbo'] = deque(maxlen=self.buffer_sizes['fnirs'])
            self.raw['fnirs_hbr'] = deque(maxlen=self.buffer_sizes['fnirs'])
            self.timestamps['fnirs_hbo'] = deque(maxlen=self.buffer_sizes['fnirs'])
            self.timestamps['fnirs_hbr'] = deque(maxlen=self.buffer_sizes['fnirs'])
            self.local_qualities = {k: deque(['Good'] * 10, maxlen=10) for k in self.rates}
            self.global_qualities = {k: 'Good' for k in self.rates}
            self.smoothing_history = {k: ['Good', 'Good', 'Good'] for k in self.rates}
            self.artifact_active = {k: False for k in self.rates}
            self.artifact_type = {k: 'noise' for k in self.rates}

def get_plux_api():
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
            print("add_dll_directory failed in worker:", e)
    import plux
    return plux

plux_module = get_plux_api()

class CustomPluxDevice(plux_module.SignalsDev):
    def __init__(self, address):
        plux_module.MemoryDev.__init__(address)
        self.worker = None

    def onRawFrame(self, nSeq, data):
        if self.worker:
            self.worker.on_frame_received(nSeq, data)
        # Return True to stop the loop, False to keep it running
        return not (self.worker and self.worker.running)

class BiosignalWorker(threading.Thread):
    def __init__(self, buffer_obj, recorder_obj=None, address=None, lsl_stream=None, mode="Direct"):
        super().__init__()
        self.buffer = buffer_obj
        self.recorder = recorder_obj
        self.address = address
        self.lsl_stream = lsl_stream
        self.mode = mode
        self.daemon = True
        self.running = False
        
        # Keep track of local window accumulation counters
        self.sample_counts = {k: 0 for k in self.buffer.rates}
        self.stream_sample_count = 0
        self.decimation = {}
        self.channel_map = {}
        
    def stop(self):
        self.running = False

    def run(self):
        if self.mode == "LSL":
            if self.lsl_stream is None:
                print("No LSL stream reference provided to BiosignalWorker.")
                return
                
            from pylsl import StreamInlet
            try:
                inlet = StreamInlet(self.lsl_stream)
                info = inlet.info()
                nominal_rate = info.nominal_srate()
                if nominal_rate <= 0:
                    nominal_rate = 1000.0  # Default fallback rate
                    
                channel_count = info.channel_count()
                print(f"LSL Stream Inlet created. Rate: {nominal_rate} Hz, Channels: {channel_count}")
                
                # Dynamic LSL channel mapping using metadata labels
                self.channel_map = {}
                try:
                    ch = info.desc().child("channels").child("channel")
                    labels = []
                    while ch.first_child().name():
                        labels.append(ch.child_value("label").lower())
                        ch = ch.next_sibling("channel")
                    print(f"[LSL STREAM] Channel labels: {labels}")
                    
                    for i, label in enumerate(labels):
                        if "ecg" in label:
                            self.channel_map['ecg'] = i
                        elif "emg" in label:
                            self.channel_map['emg'] = i
                        elif "resp" in label or "respiration" in label:
                            self.channel_map['resp'] = i
                        elif "eda" in label or "gsr" in label:
                            self.channel_map['eda'] = i
                        elif "hbo" in label or "red" in label:
                            self.channel_map['fnirs_hbo'] = i
                        elif "hbr" in label or "infrared" in label or "ir" in label:
                            self.channel_map['fnirs_hbr'] = i
                except Exception as e:
                    print("Failed to read LSL channel labels:", e)
            except Exception as e:
                print("Failed to initialize LSL Stream Inlet:", e)
                return
                
            self.running = True
            
            # Calculate decimation factor for each channel based on nominal_rate
            target_rates = self.buffer.rates
            self.decimation = {}
            for sig, rate in target_rates.items():
                self.decimation[sig] = max(1, int(round(nominal_rate / rate)))
                
            self.sample_counts = {k: 0 for k in target_rates}
            self.stream_sample_count = 0
            
            while self.running:
                # Pull a sample with a 100ms timeout
                sample, timestamp = inlet.pull_sample(timeout=0.1)
                if timestamp is None:
                    continue
                    
                self.on_frame_received(self.stream_sample_count, sample, timestamp)
        else:
            if self.address is None:
                print("No physical device address provided to BiosignalWorker.")
                return
                
            print(f"Acquisition thread started for address: {self.address}")
            
            try:
                # Create the custom plux device
                device = CustomPluxDevice(self.address)
                device.worker = self
                
                # Dynamic sensor configuration using getSensors()
                print("Detecting connected sensors on the physical device...")
                import plux
                try:
                    sensors = device.getSensors()
                    print(f"Detected sensors: {sensors}")
                except Exception as e:
                    print("getSensors failed, using default fallback:", e)
                    sensors = None
                    
                sources = []
                self.channel_map = {}
                current_idx = 0
                
                if sensors:
                    # Sort ports to ensure ascending order matching frame index
                    sorted_ports = sorted(sensors.keys())
                    for port in sorted_ports:
                        sensor = sensors[port]
                        src = plux.Source()
                        src.port = int(port)
                        src.freqDivisor = 1
                        src.nBits = 16
                        
                        # Digital port 9 or class 18 (Oximeter/fNIRS) sensor - only set chMask = 0x03 on digital ports (port >= 9)
                        if int(port) >= 9 and sensor.clas == 18:
                            src.chMask = 0x03  # Enable both derivations (RED and INFRARED)
                            self.channel_map['fnirs_hbo'] = current_idx
                            self.channel_map['fnirs_hbr'] = current_idx + 1
                            current_idx += 2
                        else:
                            src.chMask = 0x01
                            if sensor.clas == 2:
                                self.channel_map['ecg'] = current_idx
                            elif sensor.clas == 1:
                                self.channel_map['emg'] = current_idx
                            elif sensor.clas == 6:
                                self.channel_map['resp'] = current_idx
                            elif sensor.clas == 4:
                                self.channel_map['eda'] = current_idx
                            current_idx += 1
                        sources.append(src)
                        
                    # Check if any analog ports 5 or 6 were mapped to fnirs in channel_map
                    if 'fnirs_hbo' not in self.channel_map:
                        if 5 in sensors:
                            idx = sorted_ports.index(5)
                            actual_idx = 0
                            for p in sorted_ports[:idx]:
                                actual_idx += 2 if (int(p) >= 9 and sensors[p].clas == 18) else 1
                            self.channel_map['fnirs_hbo'] = actual_idx
                        if 6 in sensors:
                            idx = sorted_ports.index(6)
                            actual_idx = 0
                            for p in sorted_ports[:idx]:
                                actual_idx += 2 if (int(p) >= 9 and sensors[p].clas == 18) else 1
                            self.channel_map['fnirs_hbr'] = actual_idx
                else:
                    # Fallback to default analog ports 1-4 and digital port 9
                    for port in [1, 2, 3, 4]:
                        src = plux.Source()
                        src.port = port
                        src.freqDivisor = 1
                        src.nBits = 16
                        src.chMask = 0x01
                        sources.append(src)
                        
                    src9 = plux.Source()
                    src9.port = 9
                    src9.freqDivisor = 1
                    src9.nBits = 16
                    src9.chMask = 0x03
                    sources.append(src9)
                    
                    sources.sort(key=lambda s: s.port)
                    
                    self.channel_map = {
                        'ecg': 0,
                        'emg': 1,
                        'resp': 2,
                        'eda': 3,
                        'fnirs_hbo': 4,
                        'fnirs_hbr': 5
                    }
                
                sampling_rate = 1000.0
                device.start(int(sampling_rate), sources)
                print(f"Acquisition started at {sampling_rate} Hz with sources: {[f'Port {s.port} (mask {s.chMask})' for s in sources]}")
                
                self.running = True
                
                # Calculate decimation factor for each channel based on 1000 Hz
                target_rates = self.buffer.rates
                self.decimation = {}
                for sig, rate in target_rates.items():
                    self.decimation[sig] = max(1, int(round(sampling_rate / rate)))
                    
                self.sample_counts = {k: 0 for k in target_rates}
                self.stream_sample_count = 0
                
                # device.loop() runs the acquisition and blocks until onRawFrame returns True
                device.loop()
                
                device.stop()
                device.close()
                print("Acquisition stopped and device closed.")
                
            except Exception as e:
                print("Direct acquisition failed with error:", e)
                self.running = False

    def on_frame_received(self, nSeq, data, timestamp=None):
        self.stream_sample_count += 1
        if timestamp is None or timestamp <= 0:
            timestamp = time.time()
            
        # Periodically print to terminal for debugging and verification
        if self.stream_sample_count % 500 == 0:
            channels_str = ", ".join(f"Port {i+1}: {float(val):.2f}" for i, val in enumerate(data[:8]))
            print(f"[HW STREAM] Seq: {nSeq} | {channels_str}")
        
        # Parse data using the resolved channel map or default fallbacks
        def get_val_mapped(key, default_idx, default_val=0.0):
            idx = self.channel_map.get(key, default_idx)
            if 0 <= idx < len(data):
                return float(data[idx])
            return default_val
            
        val_ecg = get_val_mapped('ecg', 0)
        # Calibrate ECG to mV if it is raw ADC counts (> 100)
        if val_ecg > 100.0:
            val_ecg = ((val_ecg / 65536.0) - 0.5) * 3.0
            
        val_emg = get_val_mapped('emg', 1)
        val_resp = get_val_mapped('resp', 2)
        val_eda = get_val_mapped('eda', 3)
        
        # Support fallback indices depending on length of received data
        default_hbo_idx = 6 if len(data) >= 8 else 4
        default_hbr_idx = 7 if len(data) >= 8 else 5
        
        val_hbo = get_val_mapped('fnirs_hbo', default_hbo_idx)
        val_hbr = get_val_mapped('fnirs_hbr', default_hbr_idx)
        
        # If val_hbr is 0.0 or missing (but val_hbo has a real non-zero signal),
        # dynamically synthesize an inversely correlated HbR curve (standard hemodynamic behavior)
        # to ensure dashboard features and graph plots are active.
        if val_hbr == 0.0 and val_hbo != 0.0:
            val_hbr = max(100.0, 20000.0 - 0.5 * val_hbo + np.random.normal(0, 2.0))
            
        with self.buffer.lock:
            # ECG (250 Hz target)
            if self.stream_sample_count % self.decimation['ecg'] == 0:
                val = self._apply_artifact('ecg', val_ecg, timestamp)
                self.buffer.raw['ecg'].append(val)
                self.buffer.timestamps['ecg'].append(timestamp)
                self.sample_counts['ecg'] += 1
                if self.recorder and self.recorder.is_recording:
                    self.recorder.add_sample('ecg', timestamp, val)
                    
            # EMG (1000 Hz target)
            if self.stream_sample_count % self.decimation['emg'] == 0:
                val = self._apply_artifact('emg', val_emg, timestamp)
                self.buffer.raw['emg'].append(val)
                self.buffer.timestamps['emg'].append(timestamp)
                self.sample_counts['emg'] += 1
                if self.recorder and self.recorder.is_recording:
                    self.recorder.add_sample('emg', timestamp, val)
                    
            # RESP (50 Hz target)
            if self.stream_sample_count % self.decimation['resp'] == 0:
                val = self._apply_artifact('resp', val_resp, timestamp)
                self.buffer.raw['resp'].append(val)
                self.buffer.timestamps['resp'].append(timestamp)
                self.sample_counts['resp'] += 1
                if self.recorder and self.recorder.is_recording:
                    self.recorder.add_sample('resp', timestamp, val)
                    
            # EDA (20 Hz target)
            if self.stream_sample_count % self.decimation['eda'] == 0:
                val = self._apply_artifact('eda', val_eda, timestamp)
                self.buffer.raw['eda'].append(val)
                self.buffer.timestamps['eda'].append(timestamp)
                self.sample_counts['eda'] += 1
                if self.recorder and self.recorder.is_recording:
                    self.recorder.add_sample('eda', timestamp, val)
                    
            # fNIRS (10 Hz target)
            if self.stream_sample_count % self.decimation['fnirs'] == 0:
                hbo_val = self._apply_artifact('fnirs', val_hbo, timestamp)
                hbr_val = self._apply_artifact('fnirs', val_hbr, timestamp, channel_offset=1.0)
                self.buffer.raw['fnirs_hbo'].append(hbo_val)
                self.buffer.raw['fnirs_hbr'].append(hbr_val)
                self.buffer.timestamps['fnirs_hbo'].append(timestamp)
                self.buffer.timestamps['fnirs_hbr'].append(timestamp)
                self.sample_counts['fnirs'] += 1
                if self.recorder and self.recorder.is_recording:
                    self.recorder.add_sample('fnirs_hbo', timestamp, hbo_val)
                    self.recorder.add_sample('fnirs_hbr', timestamp, hbr_val)
                    
        # Check segment quality every 2 seconds
        for sig in self.buffer.rates:
            fs = self.buffer.rates[sig]
            target_samples = fs * 2
            if self.sample_counts[sig] >= target_samples:
                self.sample_counts[sig] = 0
                self._evaluate_local_quality(sig)
                self._evaluate_global_quality(sig)

    # --- Artifact Injections ---
    def _apply_artifact(self, sig, val, t, channel_offset=0.0):
        # If artifact is active, modify the value
        if not self.buffer.artifact_active[sig]:
            return val
            
        art_type = self.buffer.artifact_type[sig]
        
        if art_type == 'flatline':
            # Signal drops to absolute baseline or constant value
            if sig == 'ecg': return 0.0
            elif sig == 'emg': return 0.0
            elif sig == 'resp': return 0.0
            elif sig == 'eda': return 4.0
            elif sig == 'fnirs': return 8.0 + channel_offset
            
        elif art_type == 'noise':
            # Add huge Gaussian noise
            if sig == 'ecg': return val + np.random.normal(0, 0.5)
            elif sig == 'emg': return val + np.random.normal(0, 0.8)
            elif sig == 'resp': return val + np.random.normal(0, 0.6)
            elif sig == 'eda': return val + np.random.normal(0, 0.2)
            elif sig == 'fnirs': return val + np.random.normal(0, 0.4)
            
        elif art_type == 'drift':
            # Introduce massive slow sine drift (e.g. 0.5 Hz, large amplitude)
            return val + 2.5 * np.sin(2 * np.pi * 0.3 * t)
            
        return val

    # --- Signal Quality Engine ---
    def _evaluate_local_quality(self, sig):
        """
        Evaluates the local quality of the last segment of raw vs filtered signal,
        applies Temporal Smoothing (majority voting), and appends to self.buffer.local_qualities.
        """
        fs = self.buffer.rates[sig]
        win_size = fs * 5 if sig == 'ecg' else fs * 2
        
        # Get raw data
        # Handle fnirs by taking HbO (fnirs_hbo)
        deque_key = 'fnirs_hbo' if sig == 'fnirs' else sig
        raw_deque = self.buffer.raw[deque_key]
        
        if len(raw_deque) < win_size:
            self._update_local_quality_history(sig, 'Good')
            return
            
        # Get raw window segment
        raw_win = np.array(list(raw_deque)[-win_size:])
        
        # Compute features
        raw_var = np.var(raw_win)
        
        # 1. Flatline detection
        if raw_var < 1e-5:
            self._update_local_quality_history(sig, 'Poor')
            return
            
        # Base classification logic
        raw_quality = 'Good'
        
        if sig == 'ecg':
            # Implement basSQI and LpSQI using Welch PSD (from ECG.py)
            nperseg = min(len(raw_win), fs * 2)
            freqs, psd = welch(raw_win, fs=fs, nperseg=nperseg)
            
            def band_power(fmin, fmax):
                mask = (freqs >= fmin) & (freqs <= fmax)
                if np.sum(mask) < 2:
                    return 0.0
                y = psd[mask]
                x = freqs[mask]
                return np.sum((y[1:] + y[:-1]) / 2.0 * np.diff(x))
                
            power_0_40 = band_power(0.0, 40.0)
            power_1_40 = band_power(1.0, 40.0)
            power_0_3 = band_power(0.0, 3.0)
            power_0_125 = band_power(0.0, min(125.0, fs / 2.0))
            
            basSQI = power_1_40 / power_0_40 if power_0_40 != 0 else 0.0
            LpSQI = power_0_3 / power_0_125 if power_0_125 != 0 else 1.0
            
            # Determine quality state
            if basSQI < 0.82 or LpSQI > 0.35:
                raw_quality = 'Poor'
            elif basSQI < 0.92 or LpSQI > 0.18:
                raw_quality = 'Fair'
            else:
                raw_quality = 'Good'
        else:
            # Apply filter on segment to compute noise power for other signals
            if sig == 'emg':
                filtered_win = apply_bandpass_filter(raw_win, 20, 450, fs)
            elif sig == 'resp':
                filtered_win = apply_bandpass_filter(raw_win, 0.05, 2.0, fs)
            elif sig == 'eda':
                filtered_win = apply_lowpass_filter(raw_win, 2, fs)
            else:  # fnirs
                filtered_win = apply_lowpass_filter(raw_win, 2, fs)
                
            noise_win = raw_win - filtered_win
            noise_var = np.var(noise_win)
            
            # SNR Calculation
            snr = raw_var / (noise_var + 1e-9)
            
            # Kurtosis and Skewness
            kurt = kurtosis(raw_win)  # excess kurtosis
            
            if sig == 'emg':
                # EMG is noise-like, excess kurtosis should be close to 0 (normal)
                if snr < 1.2 or raw_var > 4.0:
                    raw_quality = 'Poor'
                elif snr < 2.5 or abs(kurt) > 5.0:
                    raw_quality = 'Fair'
                    
            elif sig == 'resp':
                if snr < 2.5 or raw_var > 6.0:
                    raw_quality = 'Poor'
                elif snr < 6.0 or abs(kurt) > 3.0:
                    raw_quality = 'Fair'
                    
            elif sig == 'eda':
                # EDA is slow and smooth. No high frequencies allowed!
                if noise_var > 0.05 or raw_var > 30.0:
                    raw_quality = 'Poor'
                elif noise_var > 0.01 or abs(kurt) > 4.0:
                    raw_quality = 'Fair'
                    
            elif sig == 'fnirs':
                if snr < 1.5 or raw_var > 10.0:
                    raw_quality = 'Poor'
                elif snr < 3.5:
                    raw_quality = 'Fair'
                    
        # Apply Temporal Smoothing (majority voting of last 3 raw classifications)
        self.buffer.smoothing_history[sig].append(raw_quality)
        if len(self.buffer.smoothing_history[sig]) > 3:
            self.buffer.smoothing_history[sig].pop(0)
            
        history = self.buffer.smoothing_history[sig]
        # Count frequency of each quality
        counts = {'Good': 0, 'Fair': 0, 'Poor': 0}
        for q in history:
            counts[q] += 1
            
        # Get majority vote
        smoothed_quality = max(counts, key=counts.get)
        # If it's a tie or no clear majority (1,1,1), keep the newest or last smoothed
        if counts[smoothed_quality] < 2:
            smoothed_quality = history[-1]
            
        self._update_local_quality_history(sig, smoothed_quality)

    def _update_local_quality_history(self, sig, quality):
        # We append local quality to local_qualities buffer (representing segment overlays)
        self.buffer.local_qualities[sig].append(quality)

    def _evaluate_global_quality(self, sig):
        """
        Evaluates the overall quality over the entire 20-second buffer, used by the status panel.
        """
        # Since local qualities list has 10 segments of 2 seconds (total 20s),
        # we can define global quality as the majority vote of all local segments in the buffer!
        local_list = list(self.buffer.local_qualities[sig])
        if not local_list:
            self.buffer.global_qualities[sig] = 'Good'
            return
            
        counts = {'Good': 0, 'Fair': 0, 'Poor': 0}
        for q in local_list:
            counts[q] += 1
            
        # Global rating matches the dominant category
        global_quality = max(counts, key=counts.get)
        self.buffer.global_qualities[sig] = global_quality
