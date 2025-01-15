import time
import queue
import threading

from data_acquisition import DataAcquisition
from device_status import DeviceStatus
from radar import RadarPlotter
from radar_analyzer import RadarAnalyzer

def main():
    data_queue = queue.Queue()
    device_status = DeviceStatus()

    ports = [
        "/dev/ttyACM0",
        "/dev/ttyUSB0"
    ]
    baudrate = 115200

    threads = []
    for idx, port in enumerate(ports):
        t = DataAcquisition(port, baudrate, data_queue, name=f"DataAcqThread-{idx}")
        t.start()
        threads.append(t)

    stop_flag = threading.Event()

    def consumer_loop():
        while not stop_flag.is_set():
            try:
                data = data_queue.get(timeout=0.5)
                # Identify device ID
                if "DeviceID" in data:
                    device_id = data["DeviceID"]
                elif "MAC" in data:
                    device_id = data["MAC"]
                else:
                    device_id = data.get("__port__", "UnknownDevice")
                device_status.update_device(device_id, data)

                # Drain the queue
                while True:
                    try:
                        data = data_queue.get_nowait()
                        if "DeviceID" in data:
                            device_id = data["DeviceID"]
                        elif "MAC" in data:
                            device_id = data["MAC"]
                        else:
                            device_id = data.get("__port__", "UnknownDevice")
                        device_status.update_device(device_id, data)
                    except queue.Empty:
                        break

            except queue.Empty:
                pass

    consumer_thread = threading.Thread(target=consumer_loop, daemon=True)
    consumer_thread.start()

    # Suppose you define coords for each device
    device_coords = {
        # Adjust these for your real setup
        "E8:9C:25:06:E9:80": (0.065, 0),  # Master at x=6.5cm
        "E9:9C:25:06:E9:80": (0.13, 0),   # Slave at x=13cm
        # You can also define an "AP": (0,0) if you like
    }

    # Start the radar analyzer
    analyzer = RadarAnalyzer(device_status, device_coords, interval=1.0)
    analyzer.start()

    # Optionally create and run a RadarPlotter
    radar_plotter = RadarPlotter(device_status)
    radar_plotter.run()

    # Once user closes the plot window, we stop everything
    stop_flag.set()
    analyzer.stop()
    analyzer.join()

    for t in threads:
        t.stop()
        t.join()

    consumer_thread.join()
    print("[INFO] Exiting main.")

if __name__ == "__main__":
    main()
