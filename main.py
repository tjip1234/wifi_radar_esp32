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
        "/dev/ttyUSB0",
        "/dev/ttyACM0"
  
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
                    continue
                if device_id not in device_coords:
                    print(f"[WARN] Unknown device ID {device_id} detected. Ignoring.")
                    continue                    
                # Update your DeviceStatus with all incoming data
                device_status.update_device(device_id, data)

                # Drain the queue quickly
                while True:
                    try:
                        data = data_queue.get_nowait()
                        if "DeviceID" in data:
                            device_id = data["DeviceID"]
                        elif "MAC" in data:
                            device_id = data["MAC"]
                        else:
                            continue
                        if device_id not in device_coords:
                            print(f"[WARN] Unknown device ID {device_id} detected. Ignoring.")
                            continue    
                        device_status.update_device(device_id, data)

                    except queue.Empty:
                        break

            except queue.Empty:
                pass

    consumer_thread = threading.Thread(target=consumer_loop, daemon=True)
    consumer_thread.start()

    # Suppose you define coords for each device
    # (Only these devices are "required" to have 10+ packets.)
    device_coords = {
        # Adjust these for your real setup
        "E8:9C:25:06:E9:80": (50, 1),  # Master
        "E9:9C:25:06:E9:80": (50, 6),   # Slave
        # You can also define an "AP": (0, 0) if you like
    }
    time.sleep(1)
    # -- WAIT until each device has at least 10 packets of CSI data --
    wait_for_packets(device_status, device_coords, min_packets=10)

    # Once we have enough data from each device, proceed:
    analyzer = RadarAnalyzer(device_status, device_coords, interval=0.1)
    analyzer.start()

    radar_plotter = RadarPlotter(device_status, analyzer)
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

def wait_for_packets(device_status, device_coords, min_packets=10):
    """
    Blocks until each device in device_coords has at least 'min_packets' CSI frames.
    Then prints device info (IP and # of packets).
    """
    print(f"[INFO] Waiting for at least {min_packets} packets from each device...")
    # We'll poll the device_status until each device has enough CSI frames.
    required_devices = set(device_coords.keys())

    while True:
        
        all_ready = True
        current_data = device_status.get_all_devices()  # snapshot
        for dev_id in required_devices:
            # Get the CSI array from that device if present
            dev_csi = current_data.get(dev_id, {}).get("CSI", [])
            print(f"  Device: {dev_id}")
            print(f"    # of CSI Packets: {len(dev_csi)}\n")
            if len(dev_csi) < min_packets:
                all_ready = False
                break

        if all_ready:
            # Print info about each device once they meet the requirement
            print("[INFO] All devices have at least "
                  f"{min_packets} packets. Here is the summary:\n")

            for dev_id in required_devices:
                dev_data = current_data.get(dev_id, {})
                ip_addr = dev_data.get("IPAddress", "Unknown IP")
                csi_count = len(dev_data.get("CSI", []))
                print(f"  Device: {dev_id}")
                print(f"    IP: {ip_addr}")
                print(f"    # of CSI Packets: {csi_count}\n")

            break
        else:
            time.sleep(0.5)
              # Sleep briefly and check again

if __name__ == "__main__":
    main()
