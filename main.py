import time
import queue
import threading

from data_acquisition import DataAcquisition
from device_status import DeviceStatus
from radar import RadarPlotter

def main():
    data_queue = queue.Queue()
    device_status = DeviceStatus()

    # Example: define your serial ports & their known device names or just let them self-identify
    ports = [
        "/dev/ttyACM0",
        "/dev/ttyUSB0"
        # "/dev/ttyACM1",
        # ...
    ]
    baudrate = 115200

    # Start data acquisition threads
    threads = []
    for idx, port in enumerate(ports):
        t = DataAcquisition(port, baudrate, data_queue, name=f"DataAcqThread-{idx}")
        t.start()
        threads.append(t)

    # Start a background thread that consumes the queue and updates DeviceStatus
    stop_flag = threading.Event()
    def consumer_loop():
        while not stop_flag.is_set():
            try:
                # Wait up to 0.5s for at least one item
                data = data_queue.get(timeout=0.5)
                # Process the first item
                if "DeviceID" in data:
                    device_id = data["DeviceID"]
                elif "MAC" in data:
                    device_id = data["MAC"]
                else:
                    device_id = data.get("__port__", "UnknownDevice")
                
                device_status.update_device(device_id, data)

                # Now drain the rest of the queue
                while True:
                    try:
                        data = data_queue.get_nowait()  # get remaining items
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
                # No data arrived this 0.5s
                pass




    consumer_thread = threading.Thread(target=consumer_loop, daemon=True)
    consumer_thread.start()

    # Create and run the live radar plot
    radar_plotter = RadarPlotter(device_status)
    radar_plotter.run()
    
    # Once the user closes the plot window, we stop everything
    stop_flag.set()
    for t in threads:
        t.stop()
        t.join()
    consumer_thread.join()
    print("[INFO] Exiting main.")

if __name__ == "__main__":
    main()
