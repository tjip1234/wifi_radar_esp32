import threading
from collections import deque

MAX_CSI_FRAMES = 300
MASTER_ID = "E8:9C:25:06:E9:80"  # Adjust if your master MAC is different

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
                # Instead of storing just a list for 'CSI', we store
                # a deque of dicts: [{"Timestamp": ..., "CSI": [...]}, ...]
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

            # 1) Handle Sync data (Master vs. Slave)
            if "SyncCount" in data and "Timestamp" in data:
                sync_count = data["SyncCount"]
                ts = data["Timestamp"]

                if device_id == MASTER_ID:
                    # Master device => record in master_sync_history
                    self.master_sync_history[sync_count] = ts
                    dev["SyncCount"] = sync_count
                    dev["LastSyncTimestamp"] = ts
                else:
                    # Slave device => see if Master has same sync_count
                    dev["SyncCount"] = sync_count
                    dev["LastSyncTimestamp"] = ts

                    if sync_count in self.master_sync_history:
                        master_ts = self.master_sync_history[sync_count]
                        offset = master_ts - ts
                        old_offset = dev["Offset"]
                        dev["Offset"] = offset
                        print(f"[DEBUG] {device_id} offset now: {offset}")
                        if abs(offset - old_offset) > 1_000_000:
                            print(f"[WARN] {device_id}: Offset changed by "
                                  f"{offset - old_offset} us (now {offset})")
                    else:
                        # No matching master sync_count yet
                        pass

            # 2) Adjust any incoming Timestamp by the device's offset (if it exists)
            if "Timestamp" in data:
                data["Timestamp"] = data["Timestamp"] + dev["Offset"]

            # 3) Update RSSI if present
            if "RSSI" in data:
                dev["RSSI"] = data["RSSI"]

            # 4) If CSI is present, store {"Timestamp":..., "CSI":[...]} in the deque
            if "CSI" in data and isinstance(data["CSI"], list):
                # We'll store the already-offset timestamp (or None if not provided)
                csi_ts = data.get("Timestamp", None)
                csi_entry = {
                    "Timestamp": csi_ts,
                    "CSI": data["CSI"]
                }
                dev["CSI"].append(csi_entry)

                curr_size = len(dev["CSI"])
                #if curr_size < MAX_CSI_FRAMES:
                    #print(f"[DEBUG] Device {device_id}: CSI buffer size = {curr_size}/{MAX_CSI_FRAMES}")
                #else:
                    #print(f"[DEBUG] Device {device_id}: CSI buffer FULL at {MAX_CSI_FRAMES}!")

            # 5) IP & memory fields if present
            for key in ["IPAddress", "Gateway", "Netmask", "FreeHeap", "FreeInternalHeap"]:
                if key in data:
                    dev[key] = data[key]

    def get_all_devices(self):
        with self.lock:
            snapshot = {}
            for d_id, vals in self.devices.items():
                # For CSI, we convert the deque of dicts to a list of dicts
                csi_list = list(vals["CSI"])

                snapshot[d_id] = {
                    "RSSI": vals["RSSI"],
                    "IPAddress": vals["IPAddress"],
                    "Gateway": vals["Gateway"],
                    "Netmask": vals["Netmask"],
                    "FreeHeap": vals["FreeHeap"],
                    "FreeInternalHeap": vals["FreeInternalHeap"],
                    "SyncCount": vals["SyncCount"],
                    "LastSyncTimestamp": vals["LastSyncTimestamp"],
                    "Offset": vals["Offset"],
                    "CSI": csi_list
                }
            return snapshot
