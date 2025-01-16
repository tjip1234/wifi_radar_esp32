import time
import threading
import numpy as np
from scipy import signal

class RadarAnalyzer(threading.Thread):
    """
    A background thread that periodically:
      - Pulls snapshots (device data) from DeviceStatus
      - Performs Doppler analysis on all available CSI subcarriers
      - Computes a 'motion score' using aggregated subcarrier data
      - Stores the results for use by a RadarPlotter or other modules
    """

    def __init__(self, device_status, device_coords, interval=1.0, name="RadarAnalyzer"):
        super().__init__(name=name)
        self.device_status = device_status
        self.device_coords = device_coords
        self.interval = interval
        self._stop_event = threading.Event()

        # Store STFT results and motion scores per device
        self.heatmaps = {}      # { device_id: (f, t, Zxx_dB) aggregated across subcarriers }
        self.subcarrier_data = {}  # Detailed per-subcarrier data
        self.motion_scores = {} # { device_id: aggregated motion score }

    def run(self):
        while not self._stop_event.is_set():
            # Get the latest snapshot of all devices
            snapshot = self.device_status.get_all_devices()

            for device, coords in self.device_coords.items():
                # Check if this device is in the snapshot and has CSI data
                if device in snapshot and "CSI" in snapshot[device]:
                    csi_frames = snapshot[device]["CSI"]
                    try:
                        # 1) Calculate sampling rate
                        sampling_rate = self.calculate_sampling_rate(csi_frames)

                        # 2) Run Doppler analysis on all subcarriers
                        subcarrier_results, aggregated_motion_score = self.doppler_analysis_all_subcarriers(
                            frames=csi_frames,
                            sampling_rate=sampling_rate
                        )

                        # 3) Store the results
                        self.subcarrier_data[device] = subcarrier_results
                        self.motion_scores[device] = aggregated_motion_score

                    except ValueError as e:
                        print(f"[WARN] Device {device}: {e}")
                        continue

            # Sleep until the next interval
            time.sleep(self.interval)

    def stop(self):
        """Signal the thread to stop."""
        self._stop_event.set()

    def calculate_sampling_rate(self, csi_frames):
        """Estimate the sampling rate based on CSI frame timestamps."""
        if len(csi_frames) < 2:
            raise ValueError("Not enough CSI frames to calculate sampling rate.")

        timestamps = [frame["Timestamp"] / 1e6 for frame in csi_frames]
        intervals = np.diff(timestamps)

        if len(intervals) < 1 or np.mean(intervals) <= 0:
            raise ValueError("Invalid or zero intervals in timestamps.")

        return 1.0 / np.mean(intervals)

    def doppler_analysis_all_subcarriers(self, frames, sampling_rate):
        """
        Perform STFT-based Doppler analysis on all available subcarriers,
        ignoring subcarriers with only zero values.

        :param frames: list of dicts, each with "Timestamp" and "CSI".
                    Example: frames[i]["CSI"] -> list/array of subcarrier amplitudes.
        :param sampling_rate: Approximate packets/sec.

        :return:
        subcarrier_results (dict): Detailed results per subcarrier.
            { subcarrier_index: (f, t_stft, Zxx_dB, motion_score) }
        aggregated_motion_score (float): Aggregate score from all subcarriers.
        """
        subcarrier_results = {}
        aggregated_motion_score = 0.0
        total_subcarriers = len(frames[0]["CSI"])
        valid_subcarriers = 0

        for subcarrier_index in range(total_subcarriers):
            # Extract amplitude data for this subcarrier, ignoring zeros
            amp_vals = [
                entry["CSI"][subcarrier_index]
                for entry in frames
                if subcarrier_index < len(entry["CSI"]) and entry["CSI"][subcarrier_index] != 0
            ]

            if len(amp_vals) < 2:  # Skip subcarriers with insufficient valid data
                print(f"[INFO] Skipping subcarrier {subcarrier_index} due to insufficient data.")
                continue

            amp_vals = np.array(amp_vals, dtype=np.float32)
            noverlap = min(min(len(amp_vals),64) // 2, 32)  # Ensure noverlap is always less than nperseg

            # Perform STFT
            f, t_stft, Zxx = signal.stft(
                amp_vals,
                fs=sampling_rate,
                nperseg=min(len(amp_vals), 64),
                noverlap=noverlap
            )

            # Convert magnitude to dB
            Zxx_dB = 20 * np.log10(np.abs(Zxx) + 1e-6)

            # Compute motion score for this subcarrier
            if Zxx_dB.shape[1] > 0:
                motion_score = float(np.mean(Zxx_dB[:, -1]))
            else:
                motion_score = 0.0

            # Store individual subcarrier results
            subcarrier_results[subcarrier_index] = (f, t_stft, Zxx_dB, motion_score)

            # Aggregate motion score
            aggregated_motion_score += motion_score
            valid_subcarriers += 1

        # Normalize the aggregated motion score
        if valid_subcarriers > 0:
            aggregated_motion_score /= valid_subcarriers
        else:
            print("[WARN] No valid subcarriers with data to process.")
            aggregated_motion_score = 0.0

        return subcarrier_results, aggregated_motion_score


