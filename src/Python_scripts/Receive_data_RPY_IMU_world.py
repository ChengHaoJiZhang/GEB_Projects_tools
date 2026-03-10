import socket
import json
import time
import threading
import tkinter as tk

from robodk.robolink import *
from robodk.robomath import *

# -----------------------------
# GLOBAL CONFIG
# -----------------------------
UDP_IP = "0.0.0.0"
UDP_PORT = 12345
BUFFER_SIZE = 2048

TARGET_DEVICE = "G1_Endo" # Change to the group number

object_NAME = "plane"   # RoboDK Object
world_NAME  = "world"     # RoboDK Frame

# Apply/update frequency
ACQ_HZ = 10.0
ACQ_PERIOD_S = 1.0 / ACQ_HZ

# Translation speed along LOCAL +Z/-Z (mm/s)
Z_SPEED_MM_S = 5.0

# RPY rotation angles
ANGLE_LIMIT_DEG = 90.0

# -----------------------------
# RoboDK init
# -----------------------------
RDK = Robolink()

obj = RDK.Item(object_NAME, ITEM_TYPE_OBJECT)
world = RDK.Item(world_NAME,  ITEM_TYPE_FRAME)

if not obj.Valid():
    raise Exception(f'RoboDK object not found: "{object_NAME}"')
if not world.Valid():
    raise Exception(f'RoboDK frame not found: "{world_NAME}"')

# Save initial poses (absolute). Restore on exit.
pose0_obj = obj.PoseAbs()
pose0_world = world.PoseAbs()

# Optional: start world at same pose as object (only at startup)
world.setPoseAbs(pose0_obj)

# Shared state for GUI
latest = {
    "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
    "s3": 0, "s4": 0,
    "device": "", "hz": 0.0,
    "status": "waiting"
}
lock = threading.Lock()
stop_flag = False

# -----------------------------
# Helpers
# -----------------------------
def wrap_deg(a):
    # [-180, 180)
    a = float(a)
    a = a % 360.0
    if a >= 180.0:
        a -= 360.0
    return a

def clamp(v, vmin, vmax):
    return max(vmin, min(vmax, v))

def rot_of_pose(pose4):
    return Mat([[pose4[0,0], pose4[0,1], pose4[0,2], 0.0],
                [pose4[1,0], pose4[1,1], pose4[1,2], 0.0],
                [pose4[2,0], pose4[2,1], pose4[2,2], 0.0],
                [0.0,        0.0,        0.0,        1.0]])

# Reference orientation: IMU (0,0,0) -> object initial orientation
R0 = rot_of_pose(pose0_obj)

def read_orientation(sock):
    try:
        data, _addr = sock.recvfrom(BUFFER_SIZE)
    except socket.timeout:
        return None

    try:
        pkt = json.loads(data.decode(errors="replace"))
    except json.JSONDecodeError:
        return None

    if pkt.get("device", "") != TARGET_DEVICE:
        return None

    # Treat incoming as ABS RPY (deg), same convention as IMU Euler output
    r = wrap_deg(pkt.get("roll", 0.0))
    p = wrap_deg(pkt.get("pitch", 0.0))
    y = wrap_deg(pkt.get("yaw", 0.0))

    # Optional safety clamp on ABS angles
    r = clamp(r, -ANGLE_LIMIT_DEG, ANGLE_LIMIT_DEG)
    p = clamp(p, -ANGLE_LIMIT_DEG, ANGLE_LIMIT_DEG)
    y = clamp(y, -ANGLE_LIMIT_DEG, ANGLE_LIMIT_DEG)

    return {
        "device": TARGET_DEVICE,
        "roll": r, "pitch": p, "yaw": y,
        "s3": int(pkt.get("s3", 0)),
        "s4": int(pkt.get("s4", 0)),
    }

def apply_pose_from_rpy_and_buttons(item_obj, item_world, roll_deg, pitch_deg, yaw_deg, s3, s4):
    """
    Apply ABS IMU Euler (extrinsic/world) and local-Z translation.
    IMU convention used here: R_imu = Rz(yaw) * Ry(pitch) * Rx(roll)  (ZYX extrinsic).
    """
    # --- 1) Absolute orientation from IMU Euler ---
    r = roll_deg  * pi / 180.0
    p = pitch_deg * pi / 180.0
    y = yaw_deg   * pi / 180.0

    R_imu = rotz(y) * roty(p) * rotx(r)   # extrinsic ZYX (world axes)

    # --- 2) Keep current translation, set absolute rotation (referenced to initial pose) ---
    pose_old = item_obj.PoseAbs()
    x, yy, z = pose_old[0, 3], pose_old[1, 3], pose_old[2, 3]

    pose_new = transl(x, yy, z) * (R0 * R_imu)

    # --- 3) LOCAL Z translation by buttons ---
    dz = 0.0
    if s3 == 1:
        dz += Z_SPEED_MM_S * ACQ_PERIOD_S
    if s4 == 1:
        dz -= Z_SPEED_MM_S * ACQ_PERIOD_S

    if dz != 0.0:
        pose_new = pose_new * transl(0, 0, dz)  # local Z of current pose_new

    item_obj.setPoseAbs(pose_new)
    # item_world.setPoseAbs(pose_new)  # optional

def udp_thread():
    global stop_flag

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((UDP_IP, UDP_PORT))
        sock.settimeout(0.02)

        last_pkt = None
        next_apply = time.time()

        n_apply = 0
        t_rate0 = time.time()
        hz = 0.0

        while not stop_flag:
            pkt = read_orientation(sock)
            if pkt is not None:
                last_pkt = pkt

            now = time.time()
            if now >= next_apply:
                next_apply += ACQ_PERIOD_S

                if last_pkt is not None:
                    apply_pose_from_rpy_and_buttons(
                        obj, world,
                        last_pkt["roll"], last_pkt["pitch"], last_pkt["yaw"],
                        last_pkt["s3"], last_pkt["s4"]
                    )

                    n_apply += 1
                    dt = now - t_rate0
                    if dt >= 1.0:
                        hz = n_apply / dt
                        n_apply = 0
                        t_rate0 = now

                    with lock:
                        latest["device"] = last_pkt["device"]
                        latest["roll"] = last_pkt["roll"]
                        latest["pitch"] = last_pkt["pitch"]
                        latest["yaw"] = last_pkt["yaw"]
                        latest["s3"] = last_pkt["s3"]
                        latest["s4"] = last_pkt["s4"]
                        latest["hz"] = hz
                        latest["status"] = "OK"
                else:
                    with lock:
                        latest["status"] = "waiting (no packets)"
                # If there are windows delays  we take the next acquisition value
                if now > next_apply + 2 * ACQ_PERIOD_S:
                    next_apply = now + ACQ_PERIOD_S

            time.sleep(0.001)

    finally:
        sock.close()

# -----------------------------
# GUI
# -----------------------------
def gui_update():
    with lock:
        dev = latest["device"]
        r = latest["roll"]
        p = latest["pitch"]
        y = latest["yaw"]
        s3 = latest["s3"]
        s4 = latest["s4"]
        hz = latest["hz"]
        status = latest["status"]

    lbl1.config(text=f"Device filter: {TARGET_DEVICE} | last rx: {dev}")
    lbl2.config(text=f"RPY (deg): {r:7.2f}  {p:7.2f}  {y:7.2f}")
    lbl3.config(text=f"s3={s3} (+Z)   s4={s4} (-Z)   | Z_SPEED={Z_SPEED_MM_S:.1f} mm/s")
    lbl4.config(text=f"Apply rate: {hz:5.1f} Hz (target {ACQ_HZ:.1f} Hz) | {status}")

    root.after(50, gui_update)

def on_close():
    global stop_flag
    stop_flag = True

    try:
        th.join(timeout=1.0)
    except Exception:
        pass

    try:
        obj.setPoseAbs(pose0_obj)
        world.setPoseAbs(pose0_world)
    except Exception as e:
        print(f"Warning: could not restore initial poses: {e}")

    root.destroy()

th = threading.Thread(target=udp_thread, daemon=True)
th.start()

root = tk.Tk()
root.title("Receive_data_needle (RoboDK) - IMU ABS RPY (extrinsic)")
root.geometry("680x170")

lbl1 = tk.Label(root, text="Device:", font=("Consolas", 11))
lbl1.pack(anchor="w", padx=10, pady=(10, 0))

lbl2 = tk.Label(root, text="RPY:", font=("Consolas", 14))
lbl2.pack(anchor="w", padx=10)

lbl3 = tk.Label(root, text="Buttons:", font=("Consolas", 12))
lbl3.pack(anchor="w", padx=10)

lbl4 = tk.Label(root, text="Rate:", font=("Consolas", 10))
lbl4.pack(anchor="w", padx=10, pady=(6, 0))

root.protocol("WM_DELETE_WINDOW", on_close)
gui_update()
root.mainloop()
