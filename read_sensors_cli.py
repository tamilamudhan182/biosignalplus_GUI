import sys
import os
import time
import traceback
from pathlib import Path

# Add PLUX API path and DLL search directory
api_dir = Path(r"d:\biosignal\scratch_python_samples\PLUX-API-Python3\Win64_313")
sys.path.insert(0, str(api_dir))
if hasattr(os, "add_dll_directory"):
    try:
        os.add_dll_directory(str(api_dir))
    except Exception as e:
        print("add_dll_directory failed:", e)

import plux

class CLIPluxDevice(plux.SignalsDev):
    def __init__(self, address):
        # Do not call base __init__ since SWIG's __new__ already initialized the C++ object
        self.running = True

    def onRawFrame(self, nSeq, data):
        # Print every 200 samples (approx. 5 times per second)
        if nSeq % 200 == 0:
            print(f"[RAW FLOW] Seq: {nSeq} | Port1 (ECG): {data[0]} | Port2 (EMG): {data[1]} | Port3 (RESP): {data[2]} | Port4 (EDA): {data[3]} | Port5 (HbO): {data[4]} | Port6 (HbR): {data[5]}")
        return not self.running

def main():
    address = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    
    print(f"==================================================")
    print(f"Connecting to BioSignalsPlux on: {address}")
    print(f"==================================================")
    
    try:
        device = CLIPluxDevice(address)
        battery = device.getBattery()
        print(f"Battery level: {int(battery)}%")
        
        sampling_rate = 1000
        device.start(sampling_rate, 0x3F, 16)
        print("Acquisition started! Press Ctrl+C to stop.")
        print("-" * 50)
        
        while device.running:
            try:
                device.loop()
            except KeyboardInterrupt:
                print("\nStopping acquisition...")
                device.running = False
                
        device.stop()
        device.close()
        print("Device connection closed safely.")
        
    except Exception as e:
        print("Error during direct acquisition:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
