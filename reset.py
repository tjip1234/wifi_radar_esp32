import time
import queue
from data_acquisition import DataAcquisition  # Adjust import as necessary

def main():
    data_queue = queue.Queue()
    ports = ["/dev/ttyACM0", "/dev/ttyUSB0"]
    baudrate = 115200

    # Create a DataAcquisition thread for each port
    threads = []
    for port in ports:
        daq_thread = DataAcquisition(port, baudrate, data_queue, name=f"DataAcqThread-{port}")
        threads.append(daq_thread)
        daq_thread.start()
        print(f"[INFO] Started DataAcquisition on {port}")

    # Let the threads run for a short duration
    time.sleep(3)  # run for 3 seconds

    # Stop all threads
    for t in threads:
        t.stop()
        t.join()
        print(f"[INFO] Stopped DataAcquisition on {t.port}")

    print("[INFO] All serial connections closed. Exiting program.")

if __name__ == "__main__":
    main()
