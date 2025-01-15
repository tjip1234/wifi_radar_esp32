import threading
from collections import deque

MAX_CSI_FRAMES = 300
MASTER_ID = "E8:9C:25:06:E9:80"  # Adjust to your actual master MAC/ID

class DeviceStatus:
    def __init__(self):
        self.devices = {}
        self.lock = threading.Lock()

        # For the master, we keep a dict of sync_count -> master_timestamp
        # so slaves can find the matching sync and compute offset
        self.master_sync_history = {}

    def _ensure_device_exists(self, device_id):
        if device_id not in self.devices:
            self.devices[device_id] = {
                "RSSI": None,
                "CSI": deque(maxlen=MAX_CSI_FRAMES),
                "IPAddress": None,
                "Gateway": None,
                "Netmask": None,
                "FreeHeap": None,
                "FreeInternalHeap": None,
                "SyncCount": None,
                "LastSyncTimestamp": None,
                "Offset": 0  # This device’s offset to MASTER’s clock
            }

    def update_device(self, device_id, data):
        with self.lock:
            self._ensure_device_exists(device_id)
            dev = self.devices[device_id]

            # 1) MASTER vs SLAVE sync updates
            if "SyncCount" in data and "Timestamp" in data:
                sync_count = data["SyncCount"]
                ts = data["Timestamp"]

                if device_id == MASTER_ID:
                    # MASTER: record this sync in master_sync_history
                    self.master_sync_history[sync_count] = ts
                    dev["SyncCount"] = sync_count
                    dev["LastSyncTimestamp"] = ts
                else:
                    # SLAVE: we have a new sync. Compare to master’s sync_count if found.
                    dev["SyncCount"] = sync_count
                    dev["LastSyncTimestamp"] = ts

                    if sync_count in self.master_sync_history:
                        master_ts = self.master_sync_history[sync_count]
                        offset = master_ts - ts
                        old_offset = dev["Offset"]
                        dev["Offset"] = offset
                        # If offset changes drastically, you could warn
                        print(f"[DEBUG] offset now : {offset}")
                        if abs(offset - old_offset) > 1_000_000:
                            print(f"[WARN] {device_id}: Offset changed by "
                                  f"{offset - old_offset} us (now {offset})")
                    else:
                        # We don’t have a matching master sync_count yet
                        pass

            # 2) If this is a CSI or RSSI update, handle offset if needed
            if "Timestamp" in data:
                # Adjust the reported timestamp by the device’s offset
                # so we store “master-based” time.
                # For the master itself, offset=0 => no change.
                data["Timestamp"] = data["Timestamp"] + dev["Offset"]

            if "RSSI" in data:
                dev["RSSI"] = data["RSSI"]

            if "CSI" in data and isinstance(data["CSI"], list):
                # We assume offset is already applied to data["Timestamp"] if present
                dev["CSI"].append(data["CSI"])
                curr_size = len(dev["CSI"])
                if curr_size < MAX_CSI_FRAMES:
                    print(f"[DEBUG] Device {device_id}: CSI buffer size = "
                          f"{curr_size}/{MAX_CSI_FRAMES}")
                else:
                    print(f"[DEBUG] Device {device_id}: CSI buffer FULL at {MAX_CSI_FRAMES}!")

            # IP & memory
            for key in ["IPAddress","Gateway","Netmask","FreeHeap","FreeInternalHeap"]:
                if key in data:
                    dev[key] = data[key]

    def get_all_devices(self):
        with self.lock:
            snapshot = {}
            for d_id, vals in self.devices.items():
                snapshot[d_id] = {
                    "RSSI": vals["RSSI"],
                    "IPAddress": vals["IPAddress"],
                    "Gateway": vals["Gateway"],
                    "Netmask": vals["Netmask"],
                    "FreeHeap": vals["FreeHeap"],
                    "FreeInternalHeap": vals["FreeInternalHeap"],
                    "SyncCount": vals["SyncCount"],
                    "LastSyncTimestamp": vals["LastSyncTimestamp"],
                    "Offset": vals["Offset"],  # For debugging
                    "CSI": list(vals["CSI"])
                }
            return snapshot
