import serial
import threading
import queue
import json

class DataAcquisition(threading.Thread):
    """
    Reads data from the serial port and accumulates curly braces to parse
    JSON objects. If the buffer grows too large (no closing brace found),
    we discard and log a warning to avoid indefinite growth.
    """
    def __init__(self, port, baudrate, data_queue, name="DataAcqThread", max_buffer_len=16000):
        super().__init__(name=name)
        self.port = port
        self.baudrate = baudrate
        self.data_queue = data_queue
        self._stop_event = threading.Event()
        self.serial_conn = None

        # Maximum characters we'll buffer before giving up on the current JSON
        self.MAX_BUFFER_LEN = max_buffer_len

    def run(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"[{self.name}] Connected on {self.port}")

            buffer = ""
            brace_level = 0

            while not self._stop_event.is_set():
                # Read a line (JSON may span multiple lines, so we parse char-by-char)
                line = self.serial_conn.readline().decode("utf-8", errors="ignore")
                if not line:
                    continue

                for char in line:
                    if char == '{':
                        # If this is a new JSON object, reset buffer
                        if brace_level == 0:
                            buffer = ""
                        brace_level += 1
                        buffer += char

                    elif char == '}':
                        brace_level -= 1
                        buffer += char

                        # If we've closed all braces, we have a complete JSON
                        if brace_level == 0:
                            try:
                                data = json.loads(buffer)
                                data["__port__"] = self.port
                                self.data_queue.put(data)
                            except json.JSONDecodeError:
                                print("[WARN] Failed to decode JSON, discarding buffer.")
                            buffer = ""  # reset buffer for the next potential object

                    else:
                        # If we're inside a JSON object, accumulate
                        if brace_level > 0:
                            buffer += char

                            # Check if buffer is getting too large
                            if len(buffer) > self.MAX_BUFFER_LEN:
                                print("[WARN] JSON buffer exceeded max length, discarding..." + buffer)
                                buffer = ""
                                brace_level = 0

        except serial.SerialException as e:
            print(f"[{self.name}] Serial exception on {self.port}: {e}")
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                print(f"[{self.name}] Closed {self.port}")

    def stop(self):
        self._stop_event.set()
