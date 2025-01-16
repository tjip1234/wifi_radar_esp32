import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
import numpy as np


def pad_csi_frames(csi_frames):
    """
    Ensure each frame in csi_frames is the same length by zero-padding.
    Returns a 2D numpy array of shape (#frames, max_len).
    """
    if not csi_frames:
        return np.array([[0]])  # a 1x1 just to avoid empty array edge-cases

    # Find the max subcarrier length among all frames
    max_len = max(len(frame) for frame in csi_frames)

    padded = []
    for frame in csi_frames:
        # If some frames are shorter, pad with 0s.
        # If some are longer, you could slice or handle them otherwise.
        needed = max_len - len(frame)
        if needed > 0:
            new_frame = list(frame) + [0]*needed
        else:
            new_frame = list(frame)  # same length or longer => no padding
        padded.append(new_frame)

    return np.array(padded)


class RadarPlotter:
    def __init__(self, device_status, analyzer):
        self.device_status = device_status
        self.analyzer = analyzer

        self.fig = plt.figure(figsize=(16, 10))
        gs = gridspec.GridSpec(nrows=3, ncols=2, figure=self.fig, height_ratios=[1, 1, 1.5])

        # RSSI subplot
        self.ax_rssi = self.fig.add_subplot(gs[0, 0])
        # Memory subplot
        self.ax_mem = self.fig.add_subplot(gs[0, 1])
        # Radar subplot
        self.ax_radar = self.fig.add_subplot(gs[1, :])
        self.ax_radar.set_aspect('equal', 'box')

        # Subcarrier spectrogram subplot
        self.ax_subcarriers = self.fig.add_subplot(gs[2, :])

        # Initialize spectrogram references
        self.spectrogram = None  # pcolormesh object for the spectrogram
        self.colorbar_spectrogram = None  # Colorbar for the spectrogram

        self.colorbar = None  # Store the colorbar reference for radar plot
        self.scatter = None  # Store the scatter plot reference
        self.anim = None

    def init_plots(self):
        # Initialize radar plot
        self.scatter = self.ax_radar.scatter([], [], c=[], cmap='jet', s=100, alpha=0.8)
        self.colorbar = self.fig.colorbar(self.scatter, ax=self.ax_radar)
        self.colorbar.set_label("Motion Score")
        return []

    def update_plots(self, frame):
        devices_data = self.device_status.get_all_devices()
        device_ids = list(devices_data.keys())

        # --------
        # RSSI
        # --------
        self.ax_rssi.clear()
        self.ax_rssi.set_title("RSSI (live)")
        self.ax_rssi.set_xlabel("Device")
        self.ax_rssi.set_ylabel("RSSI (dBm)")

        rssi_values = [devices_data[d_id].get("RSSI", 0) or 0 for d_id in device_ids]
        self.ax_rssi.bar(device_ids, rssi_values, color='blue')

        # --------
        # Memory
        # --------
        self.ax_mem.clear()
        self.ax_mem.set_title("Memory (FreeHeap)")
        self.ax_mem.set_xlabel("Device")
        self.ax_mem.set_ylabel("Bytes")

        mem_values = [devices_data[d_id].get("FreeHeap", 0) or 0 for d_id in device_ids]
        mem_bars = self.ax_mem.bar(device_ids, mem_values, color='green')

        for i, bar in enumerate(mem_bars):
            dev_id = device_ids[i]
            ip_addr = devices_data[dev_id].get("IPAddress", None)
            if ip_addr:
                height = bar.get_height()
                x_pos = bar.get_x() + bar.get_width() / 2
                self.ax_mem.text(
                    x_pos,
                    height + max(1000, 0.02 * height),
                    f"{ip_addr}",
                    ha='center',
                    va='bottom',
                    rotation=90,
                    fontsize=9
                )

        # --------
        # Radar
        # --------
        x_vals = []
        y_vals = []
        motion_vals = []

        for d_id in device_ids:
            coords = self.analyzer.device_coords.get(d_id, (0.0, 0.0))
            x_vals.append(coords[0])
            y_vals.append(coords[1])

            # Shift motion scores by 120 to ensure all values are positive
            motion_score = self.analyzer.motion_scores.get(d_id, 0.0)
            motion_vals.append(motion_score + 120)

        self.scatter.set_offsets(np.c_[x_vals, y_vals])
        self.scatter.set_array(np.array(motion_vals))
        self.scatter.set_clim(vmin=120, vmax=200)
        self.colorbar.update_normal(self.scatter)

        self.ax_radar.set_xlim(min(x_vals) - 10, max(x_vals) + 10)
        self.ax_radar.set_ylim(min(y_vals) - 10, max(y_vals) + 10)

        # --------
        # Subcarrier Spectrogram
        # --------
        self.ax_subcarriers.clear()
        self.ax_subcarriers.set_title("Subcarrier Spectrogram E9:9C:25:06:E9:80")
        self.ax_subcarriers.set_xlabel("Time (s)")
        self.ax_subcarriers.set_ylabel("Frequency (Hz)")

        example_device = "E9:9C:25:06:E9:80"
        if example_device and example_device in self.analyzer.subcarrier_data:
            subcarrier_results = self.analyzer.subcarrier_data[example_device]

            # Plot data for the first subcarrier as an example
            subcarrier_index = 0
            if subcarrier_index in subcarrier_results:
                f, t_stft, Zxx_dB, _ = subcarrier_results[subcarrier_index]

                # Ensure Zxx_dB has the correct shape
                if Zxx_dB.shape == (len(f), len(t_stft)):
                    # Create or update the spectrogram
                    self.spectrogram = self.ax_subcarriers.pcolormesh(
                        t_stft, f, Zxx_dB, shading='gouraud', cmap='jet'
                    )
                    if self.colorbar_spectrogram is None:
                        self.colorbar_spectrogram = plt.colorbar(
                            self.spectrogram, ax=self.ax_subcarriers, label="Power (dB)"
                        )
                    else:
                        self.colorbar_spectrogram.update_normal(self.spectrogram)
                else:
                    print(f"[WARN] Skipping spectrogram: shape mismatch for device {example_device}")

        return []


    def run(self):
        self.anim = animation.FuncAnimation(
            self.fig,
            self.update_plots,
            init_func=self.init_plots,
            blit=False,
            interval=100,
            save_count=300
        )
        plt.tight_layout()
        plt.show(block=True)
