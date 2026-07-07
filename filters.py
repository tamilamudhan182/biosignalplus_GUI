import numpy as np
from scipy.signal import butter, sosfiltfilt, iirnotch, filtfilt

def apply_bandpass_filter(data, lowcut, highcut, fs, order=4):
    """
    Applies a zero-phase Butterworth bandpass filter to the data.
    """
    data = np.asarray(data)
    if len(data) <= 15:  # Too short for stable zero-phase filtering
        return data
    
    # Ensure cutoffs are valid and less than Nyquist frequency (fs / 2)
    nyquist = 0.5 * fs
    lowcut = max(0.01, lowcut)
    highcut = min(nyquist - 0.01, highcut)
    
    if lowcut >= highcut:
        return data
        
    try:
        sos = butter(order, [lowcut, highcut], btype='band', fs=fs, output='sos')
        return sosfiltfilt(sos, data)
    except Exception:
        return data

def apply_lowpass_filter(data, cutoff, fs, order=4):
    """
    Applies a zero-phase Butterworth lowpass filter to the data.
    """
    data = np.asarray(data)
    if len(data) <= 15:
        return data
        
    nyquist = 0.5 * fs
    cutoff = min(nyquist - 0.01, cutoff)
    cutoff = max(0.01, cutoff)
    
    try:
        sos = butter(order, cutoff, btype='low', fs=fs, output='sos')
        return sosfiltfilt(sos, data)
    except Exception:
        return data

def apply_notch_filter(data, notch_freq, fs, Q=30.0):
    """
    Applies a zero-phase notch filter to remove powerline interference.
    """
    data = np.asarray(data)
    if len(data) <= 15:
        return data
        
    nyquist = 0.5 * fs
    # Notch frequency must be strictly less than Nyquist frequency
    if notch_freq >= nyquist - 0.01 or notch_freq <= 0.01:
        return data
        
    try:
        b, a = iirnotch(notch_freq, Q, fs=fs)
        return filtfilt(b, a, data)
    except Exception:
        return data

