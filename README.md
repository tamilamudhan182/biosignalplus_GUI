# BioSignalsPlux Live Dashboard

A standalone, multi-threaded PyQt6/pyqtgraph application for real-time acquisition, digital filtering, and feature extraction of physiological signals from a BioSignalsPlux device.

## Core Features
*   **Direct Hardware Connection**: Communicates directly over Bluetooth/COM port using the precompiled PLUX C++ API. No external manufacturer software required.
*   **Network Sync**: Supports streaming via Lab Streaming Layer (LSL).
*   **Multi-Modal Monitoring**: Dedicated processing and visualization tabs for:
    *   **ECG**: High-pass & notch filters, real-time R-peak markers, and live statistics (Heart Rate, Mean RR, SDNN, RMSSD).
    *   **EMG**: Bandpass filtering, RMS, MAV, IEMG, Median Frequency, and muscle state classification (Active vs. Rest).
    *   **RESP**: Lowpass filtering, Inhalation Peaks & Exhalation Valleys tracking, Respiration Rate, and I:E Ratio.
    *   **EDA**: Lowpass filtering, Tonic SCL/Phasic SCR decomposition, stress index estimation.
    *   **fNIRS**: Lowpass filtering, Oxy-Hb (HbO) & Deoxy-Hb (HbR) trend tracking, and Brain Oxygenation Index (BOI).
*   **Real-time SQI (Signal Quality Index)**: Multi-segment signal evaluation with colored overlay bands on the live graphs (Green = Good, Red = Poor).
*   **Recording**: Direct export of session streams to structured CSV files.

## Tech Stack
*   Python 3.13 (64-bit)
*   PyQt6 & pyqtgraph
*   Scipy & Numpy
*   Pandas

## Setup & Running
1. Install Python 3.13 (64-bit).
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```
   *(For offline verification without hardware, run `python verify_rates.py`)*
