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
    def __init__(self, device_status):
        """
        device_status: a reference to the DeviceStatus instance
        storing device data including RSSI, FreeHeap, IPAddress, CSI, etc.
        """
        self.device_status = device_status

        # Set up the figure with GridSpec: 2 rows, 2 columns
        # The bottom row spans both columns for the CSI heatmap.
        self.fig = plt.figure(figsize=(12, 8))
        gs = gridspec.GridSpec(nrows=2, ncols=2, figure=self.fig, height_ratios=[1, 1.2])

        # Top-left: RSSI bar chart
        self.ax_rssi = self.fig.add_subplot(gs[0, 0])
        self.ax_rssi.set_title("RSSI (live)")
        self.ax_rssi.set_xlabel("Device")
        self.ax_rssi.set_ylabel("RSSI (dBm)")

        # Top-right: Memory free bar chart + IP text
        self.ax_mem = self.fig.add_subplot(gs[0, 1])
        self.ax_mem.set_title("Memory (FreeHeap)")
        self.ax_mem.set_xlabel("Device")
        self.ax_mem.set_ylabel("Bytes")

        # Bottom (spanning 2 columns): CSI heatmap
        self.ax_csi = self.fig.add_subplot(gs[1, :])
        self.ax_csi.set_title("CSI Heatmap")
        self.ax_csi.set_xlabel("Subcarrier Index")
        self.ax_csi.set_ylabel("Frame # (oldest=top)")

        # We'll keep references to our artists
        self.anim = None

    def init_plots(self):
        """
        Called once at the start of FuncAnimation to set up our artists
        (if needed). Since we redraw everything in update_plots, we can leave 
        this empty or do minimal placeholders.
        """
        return []

    def update_plots(self, frame):
        """
        Called periodically by FuncAnimation to update the plots with new data.
        """
        devices_data = self.device_status.get_all_devices()
        device_ids = list(devices_data.keys())

        # ==============
        #  RSSI Subplot
        # ==============
        self.ax_rssi.clear()
        self.ax_rssi.set_title("RSSI (live)")
        self.ax_rssi.set_xlabel("Device")
        self.ax_rssi.set_ylabel("RSSI (dBm)")

        rssi_values = []
        for d_id in device_ids:
            rssi = devices_data[d_id].get("RSSI", 0)
            rssi_values.append(rssi if rssi is not None else 0)

        self.ax_rssi.bar(device_ids, rssi_values, color='blue')

        # =====================
        #  Memory + IP Subplot
        # =====================
        self.ax_mem.clear()
        self.ax_mem.set_title("Memory (FreeHeap)")
        self.ax_mem.set_xlabel("Device")
        self.ax_mem.set_ylabel("Bytes")

        mem_values = []
        for d_id in device_ids:
            free_heap = devices_data[d_id].get("FreeHeap", 0)
            mem_values.append(free_heap if free_heap is not None else 0)

        mem_bars = self.ax_mem.bar(device_ids, mem_values, color='green')

        # Place IP address text above each bar (if available)
        for i, bar in enumerate(mem_bars):
            dev_id = device_ids[i]
            ip_addr = devices_data[dev_id].get("IPAddress", None)
            if ip_addr:
                # The top of the bar
                height = bar.get_height()
                x_pos = bar.get_x() + bar.get_width()/2
                self.ax_mem.text(
                    x_pos, 
                    height + (0.02 * height if height else 1000),  # shift text above bar
                    f"{ip_addr}",
                    ha='center',
                    va='bottom',
                    rotation=90,
                    fontsize=9
                )

        # ===================
        #  CSI Heatmap Subplot
        # ===================
        self.ax_csi.clear()

        if device_ids:
            # For demonstration, pick the first device to show CSI
            first_device = device_ids[0]
            self.ax_csi.set_title(f"CSI Heatmap (device: {first_device})")

            csi_frames = devices_data[first_device].get("CSI", [])
            if csi_frames:
                # Pad frames so they all have the same length
                csi_matrix = pad_csi_frames(csi_frames)
            else:
                csi_matrix = np.zeros((1,1))

            self.ax_csi.imshow(
                csi_matrix,
                aspect='auto',
                origin='upper',  # newest at bottom if you keep frames in chronological order
                interpolation='nearest'
            )
            self.ax_csi.set_xlabel("Subcarrier Index")
            self.ax_csi.set_ylabel("Frame # (oldest=top)")
        else:
            self.ax_csi.set_title("CSI Heatmap (no devices)")
            self.ax_csi.imshow([[0]], aspect='auto')

        return []

    def run(self):
        """
        Start the animation loop. This blocks until the figure is closed.
        """
        self.anim = animation.FuncAnimation(
            self.fig,
            self.update_plots,
            init_func=self.init_plots,
            blit=False,
            interval=1000,    # update every 1 second (adjust as needed)
            save_count=300    # cap the frame cache to 300
        )
        plt.tight_layout()
        plt.show(block=True)
