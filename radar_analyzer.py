import time
import threading
import scipy.signal as signal
import numpy as np

class RadarAnalyzer(threading.Thread):
   
    """
    A background thread that periodically pulls snapshots from DeviceStatus
    and updates a pandas DataFrame (or other structure) for 'radar' processing.
    """
    def __init__(self, device_status, device_coords, interval=1.0, name="RadarAnalyzer"):
        super().__init__(name=name)
        self.device_status = device_status
        self.device_coords = device_coords  
        self.interval = interval
        self._stop_event = threading.Event()

    def run(self):
        heatmaps = {}

        while not self._stop_event.is_set():
            snapshot = self.device_status.get_all_devices()

            for device, coords in self.device_coords.items():
                if device in snapshot:
                    try:
                        rate = calculate_sampling_rate(snapshot[device]["CSI"])
                        f, t_stft, Zxx_dB = doppler_analysis_csi(
                            snapshot[device]["CSI"], subcarrier_index=0, sampling_rate=rate
                        )

                        # Flatten the STFT into a 2D DataFrame for analysis
                        heatmap_df = pd.DataFrame(Zxx_dB, index=f, columns=t_stft)
                        heatmaps[device] = heatmap_df

                    except ValueError as e:
                        print(f"Device {device}: {e}")
                        continue

            time.sleep(self.interval)  # Wait before the next cycle


    def stop(self):
        self._stop_event.set()

    def calculate_sampling_rate(csi_frames):
        timestamps = [frame["Timestamp"] / 1e6 for frame in csi_frames]
        if len(timestamps) < 2:
            raise ValueError("Not enough timestamps to calculate sampling rate.")
        intervals = np.diff(timestamps)
        return 1.0 / np.mean(intervals)
    
    def doppler_analysis_csi(frames, subcarrier_index=0, sampling_rate=100):
        """
        frames: list of tuples (t, csi_dict) 
                where csi_dict = { "Timestamp": t, "CSI": [...subcarrier array...] } 
                or similar from your device_status snapshot.
        subcarrier_index: which subcarrier amplitude to analyze
        sampling_rate: approx. packets/sec for STFT
        
        Returns f, t, Zxx: STFT frequency axis, time axis, and STFT matrix
        """
        # 1) Extract amplitude over time
        #    If you only have amplitude, just pick that directly from the subcarrier
        #    Or do amplitude = np.abs(CSI) if it's complex.
        amp_vals = []
        for entry in frames:
            csi_entry = entry["CSI"]
            # you might need to handle out-of-range if subcarrier_index>len(csi_entry)-1
            amp = csi_entry[subcarrier_index]
            amp_vals.append(amp)
        
        amp_vals = np.array(amp_vals, dtype=np.float32)

        f, t_stft, Zxx = signal.stft(amp_vals, fs=sampling_rate, nperseg=64, noverlap=32)
        
        # 3) Convert magnitude to dB, for easier plotting
        Zxx_dB = 20 * np.log10(np.abs(Zxx) + 1e-6)

        return f, t_stft, Zxx_dB


