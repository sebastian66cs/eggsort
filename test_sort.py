#!/usr/bin/env python3
"""
EggSort — Calibration & Mock Weight Testing Utility
A helper app to test the physical sorting and return timings of the C-mechanism
by sending simulated weight values (e.g. M55.5) directly to the Arduino,
bypassing the need for a physical HX711 sensor connection.
"""

import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading
import time

# ─── Globals ─────────────────────────────────────────────────────
ser = None
connected = False
_slider_timers = {}  # debounce timers for slider commands

# ─── Palette — Sleek Dark Industrial Design ───────────────────────
BG       = "#0B0B0F"
CARD     = "#12121A"
CARD_HI  = "#1C1C28"
BORDER   = "#242436"
AMBER    = "#F59E0B"
AMBER_DK = "#92400E"
GREEN    = "#10B981"
RED      = "#EF4444"
CYAN     = "#06B6D4"
TEXT     = "#F3F4F6"
TEXT2    = "#9CA3AF"
TEXT3    = "#4B5563"
MONO     = "DejaVu Sans Mono"
SANS     = "Helvetica"

# ═══════════════════════════════════════════════════════════════
#  Serial Connection & Communication
# ═══════════════════════════════════════════════════════════════

def get_ports():
    return [p.device for p in serial.tools.list_ports.comports()]

def connect():
    global ser, connected
    port = port_var.get()
    if not port:
        messagebox.showwarning("No Port", "Please select a serial port.")
        return
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(1.5)  # Wait for Arduino reset
        connected = True
        conn_dot.config(fg=GREEN)
        conn_lbl.config(text=f"CONNECTED — {port}")
        btn_conn.config(state="disabled")
        btn_disc.config(state="normal")
        enable_controls(True)
        log("✓ Connected to " + port)
        threading.Thread(target=serial_reader, daemon=True).start()
        # Request current status
        send_cmd("?")
    except Exception as e:
        messagebox.showerror("Connection Error", str(e))
        log("✗ " + str(e))

def disconnect():
    global ser, connected
    connected = False
    if ser and ser.is_open:
        send_cmd("S")
        ser.close()
    ser = None
    conn_dot.config(fg=RED)
    conn_lbl.config(text="DISCONNECTED")
    btn_conn.config(state="normal")
    btn_disc.config(state="disabled")
    enable_controls(False)
    log("○ Disconnected")

def send_cmd(cmd):
    if ser and ser.is_open:
        try:
            ser.write((cmd + "\n").encode())
            log(f"→ {cmd}")
        except Exception as e:
            log(f"✗ Failed to send command: {e}")

def serial_reader():
    global ser, connected
    while ser and ser.is_open and connected:
        try:
            raw = ser.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            # Log all incoming serial data
            root.after(0, lambda l=raw: log(f"← {l}"))
            # Parse responses to update UI if needed
            if "STATUS" in raw or "READY" in raw or "ms" in raw:
                root.after(0, lambda l=raw: parse_status(l))
        except Exception:
            break

def update_entry(entry, val):
    entry.delete(0, tk.END)
    entry.insert(0, val)

def parse_status(line):
    # e.g., STATUS AUTO=OFF LIVE=OFF CAL=420.0 NEUTRAL=90 T_S=500ms T_M=700ms T_L=900ms ms R_S=500ms R_M=700ms R_L=900ms
    # Or setup printed parameters
    try:
        parts = line.split()
        for p in parts:
            if p.startswith("NEUTRAL="):
                neutral_val.config(text=p.split("=")[1])
            elif p.startswith("VCW="):
                vcw_val.config(text=p.split("=")[1])
            elif p.startswith("VCCW="):
                vccw_val.config(text=p.split("=")[1])
            elif p.startswith("T_S="):
                update_entry(ts_entry, p.split("=")[1].replace("ms", ""))
            elif p.startswith("T_M="):
                update_entry(tm_entry, p.split("=")[1].replace("ms", ""))
            elif p.startswith("T_L="):
                update_entry(tl_entry, p.split("=")[1].replace("ms", ""))
            elif p.startswith("R_S="):
                update_entry(rs_entry, p.split("=")[1].replace("ms", ""))
            elif p.startswith("R_M="):
                update_entry(rm_entry, p.split("=")[1].replace("ms", ""))
            elif p.startswith("R_L="):
                update_entry(rl_entry, p.split("=")[1].replace("ms", ""))
            elif p.startswith("TW="):
                update_entry(tw_entry, p.split("=")[1].replace("ms", ""))
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
#  UI Control Handlers
# ═══════════════════════════════════════════════════════════════

def send_mock_weight():
    try:
        w_val = float(weight_entry.get())
        if w_val < 0 or w_val > 1000:
            raise ValueError()
        send_cmd(f"M{w_val:.1f}")
    except ValueError:
        messagebox.showwarning("Invalid Input", "Please enter a valid weight between 0 and 1000 grams.")

def send_quick_weight(w):
    weight_entry.delete(0, tk.END)
    weight_entry.insert(0, f"{w:.1f}")
    send_cmd(f"M{w:.1f}")

def send_neutral():
    try:
        n = int(neutral_entry.get())
        if n < 80 or n > 140:
            raise ValueError()
        send_cmd(f"N{n}")
    except ValueError:
        messagebox.showwarning("Invalid Input", "Neutral point must be between 80 and 140.")

def send_vcw():
    try:
        n = int(vcw_entry.get())
        if n < 0 or n > 89:
            raise ValueError()
        send_cmd(f"VCW{n}")
    except ValueError:
        messagebox.showwarning("Invalid Input", "VCW must be between 0 and 89.")

def send_vccw():
    try:
        n = int(vccw_entry.get())
        if n < 91 or n > 180:
            raise ValueError()
        send_cmd(f"VCCW{n}")
    except ValueError:
        messagebox.showwarning("Invalid Input", "VCCW must be between 91 and 180.")

def send_slider_cmd(prefix, value):
    val = int(float(value))
    send_cmd(f"{prefix}{val}")

def send_pulse():
    try:
        ms_val = int(pulse_ms_entry.get())
        if ms_val < 1 or ms_val > 10000:
            raise ValueError()
        direction = pulse_dir_var.get()
        send_cmd(f"GP{direction}{ms_val}")
    except ValueError:
        messagebox.showwarning("Invalid Input", "Pulse duration must be between 1 and 10000 ms.")

def refresh_ports():
    ports = get_ports()
    port_dd["values"] = ports
    if ports:
        port_var.set(ports[0])
    log("↻ Ports list refreshed")

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    log_box.config(state="normal")
    log_box.insert("end", f"[{ts}] {msg}\n")
    log_box.see("end")
    log_box.config(state="disabled")

def clear_log():
    log_box.config(state="normal")
    log_box.delete("1.0", "end")
    log_box.config(state="disabled")

def enable_controls(enabled):
    state = "normal" if enabled else "disabled"
    btn_send_w.config(state=state)
    btn_w_s.config(state=state)
    btn_w_m.config(state=state)
    btn_w_l.config(state=state)
    btn_send_n.config(state=state)
    btn_ts.config(state=state)
    btn_tm.config(state=state)
    btn_tl.config(state=state)
    btn_rs.config(state=state)
    btn_rm.config(state=state)
    btn_rl.config(state=state)
    btn_tw.config(state=state)
    btn_stop.config(state=state)
    btn_status.config(state=state)
    btn_tare.config(state=state)
    btn_test_cw.config(state=state)
    btn_test_ccw.config(state=state)
    btn_pulse.config(state=state)
    btn_send_vcw.config(state=state)
    btn_send_vccw.config(state=state)
    btn_save.config(state=state)

# ═══════════════════════════════════════════════════════════════
#  GUI Setup
# ═══════════════════════════════════════════════════════════════

root = tk.Tk()
root.title("EggSort — Mock Weight Test Harness")
root.geometry("860x850")
root.configure(bg=BG)

# Styles
style = ttk.Style()
style.theme_use("clam")
style.configure("TCombobox", fieldbackground=CARD_HI, background=CARD_HI, foreground=TEXT, arrowcolor=AMBER)

# Top Title Bar
top_bar = tk.Frame(root, bg=CARD, height=60, highlightthickness=1, highlightbackground=BORDER)
top_bar.pack(fill="x")
top_bar.pack_propagate(False)

tk.Label(top_bar, text="EGGSORT TEST HARNESS", font=(SANS, 14, "bold"), bg=CARD, fg=AMBER).pack(side="left", padx=20)
tk.Label(top_bar, text="Simulated Weight & Parameter Calibration", font=(SANS, 9), bg=CARD, fg=TEXT2).pack(side="left", pady=(4, 0))

conn_dot = tk.Label(top_bar, text="●", font=(SANS, 12), bg=CARD, fg=RED)
conn_dot.pack(side="right", padx=(0, 10))
conn_lbl = tk.Label(top_bar, text="DISCONNECTED", font=(MONO, 9, "bold"), bg=CARD, fg=TEXT2)
conn_lbl.pack(side="right", padx=(0, 20))

# Main Workspace Grid
body = tk.Frame(root, bg=BG)
body.pack(fill="both", expand=True, padx=15, pady=15)
body.columnconfigure(0, weight=1)
body.columnconfigure(1, weight=1)
body.rowconfigure(0, weight=1)

# Left Column (Testing controls)
col_left = tk.Frame(body, bg=BG)
col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))

# Right Column (Console log & Setup)
col_right = tk.Frame(body, bg=BG)
col_right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

# ── Left Column: Serial Setup ──
f_serial = tk.Frame(col_left, bg=CARD, highlightthickness=1, highlightbackground=BORDER, pady=10, padx=15)
f_serial.pack(fill="x", pady=(0, 10))

tk.Label(f_serial, text="SERIAL CONNECTION", font=(SANS, 10, "bold"), bg=CARD, fg=AMBER).pack(anchor="w", pady=(0, 8))
row_ser = tk.Frame(f_serial, bg=CARD)
row_ser.pack(fill="x")

port_var = tk.StringVar()
ports = get_ports()
port_dd = ttk.Combobox(row_ser, textvariable=port_var, values=ports, width=12, state="readonly", style="TCombobox")
if ports:
    port_var.set(ports[0])
port_dd.pack(side="left", padx=(0, 5))

btn_ref = tk.Button(row_ser, text="↻", command=refresh_ports, bg=CARD_HI, fg=AMBER, activebackground=BORDER, activeforeground=TEXT, relief="flat", cursor="hand2", width=3)
btn_ref.pack(side="left", padx=(0, 8))

btn_conn = tk.Button(row_ser, text="Connect", command=connect, bg=GREEN, fg="#0F172A", activebackground="#34D399", font=(SANS, 9, "bold"), relief="flat", cursor="hand2", padx=12)
btn_conn.pack(side="left", padx=(0, 4))

btn_disc = tk.Button(row_ser, text="Disconnect", command=disconnect, bg=RED, fg=TEXT, activebackground="#F87171", font=(SANS, 9, "bold"), relief="flat", cursor="hand2", state="disabled")
btn_disc.pack(side="left")

# ── Left Column: Simulated Weight ──
f_mock = tk.Frame(col_left, bg=CARD, highlightthickness=1, highlightbackground=BORDER, pady=12, padx=15)
f_mock.pack(fill="x", pady=(0, 10))

tk.Label(f_mock, text="ARTIFICIAL WEIGHT INPUT", font=(SANS, 10, "bold"), bg=CARD, fg=AMBER).pack(anchor="w", pady=(0, 8))

row_weight = tk.Frame(f_mock, bg=CARD)
row_weight.pack(fill="x", pady=(0, 10))

weight_entry = tk.Entry(row_weight, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, font=(MONO, 12, "bold"), width=8, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
weight_entry.insert(0, "55.0")
weight_entry.pack(side="left", padx=(0, 6), ipady=3)

tk.Label(row_weight, text="g", font=(SANS, 11), bg=CARD, fg=TEXT2).pack(side="left", padx=(0, 15))

btn_send_w = tk.Button(row_weight, text="⬡ SEND WEIGHT", command=send_mock_weight, bg=AMBER, fg="#0F172A", activebackground="#FBBF24", font=(SANS, 9, "bold"), relief="flat", cursor="hand2")
btn_send_w.pack(side="left", fill="x", expand=True)

# Preset weight buttons
row_presets = tk.Frame(f_mock, bg=CARD)
row_presets.pack(fill="x")

btn_w_s = tk.Button(row_presets, text="Small (45.0g)", command=lambda: send_quick_weight(45.0), bg=CARD_HI, fg="#F97316", activebackground=BORDER, font=(SANS, 9), relief="flat", cursor="hand2")
btn_w_s.pack(side="left", fill="x", expand=True, padx=(0, 4))

btn_w_m = tk.Button(row_presets, text="Medium (57.5g)", command=lambda: send_quick_weight(57.5), bg=CARD_HI, fg=GREEN, activebackground=BORDER, font=(SANS, 9), relief="flat", cursor="hand2")
btn_w_m.pack(side="left", fill="x", expand=True, padx=(0, 4))

btn_w_l = tk.Button(row_presets, text="Large (68.0g)", command=lambda: send_quick_weight(68.0), bg=CARD_HI, fg="#3B82F6", activebackground=BORDER, font=(SANS, 9), relief="flat", cursor="hand2")
btn_w_l.pack(side="left", fill="x", expand=True)

# ── Left Column: Parameter Calibration ──
f_cal = tk.Frame(col_left, bg=CARD, highlightthickness=1, highlightbackground=BORDER, pady=12, padx=15)
f_cal.pack(fill="both", expand=True)

tk.Label(f_cal, text="PARAMETER TUNING (MANUAL TEXT INPUT)", font=(SANS, 10, "bold"), bg=CARD, fg=AMBER).pack(anchor="w", pady=(0, 8))

# Sub-layout for Params
sliders_frame = tk.Frame(f_cal, bg=CARD)
sliders_frame.pack(fill="both", expand=True)
sliders_frame.columnconfigure(0, weight=1)
sliders_frame.columnconfigure(1, weight=1)

def create_param_input(parent, label, prefix, col, row, default_val):
    f = tk.Frame(parent, bg=CARD)
    f.grid(row=row, column=col, sticky="ew", padx=5, pady=4)
    
    lbl_text = tk.Label(f, text=label, font=(SANS, 9, "bold"), bg=CARD, fg=TEXT2)
    lbl_text.pack(side="left")
    
    def send_cmd_local():
        try:
            v_int = int(entry.get())
            if v_int < 1: raise ValueError()
            send_cmd(f"{prefix}{v_int}")
        except ValueError:
            messagebox.showwarning("Invalid Input", f"{prefix} must be a positive integer.")

    btn = tk.Button(f, text="SET", command=send_cmd_local, bg=CARD_HI, fg=TEXT, activebackground=BORDER, font=(SANS, 8, "bold"), relief="flat", cursor="hand2")
    btn.pack(side="right")
    
    tk.Label(f, text="ms", font=(SANS, 9), bg=CARD, fg=TEXT2).pack(side="right", padx=(2, 5))
    
    entry = tk.Entry(f, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, font=(MONO, 10), width=6, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
    entry.insert(0, str(default_val))
    entry.pack(side="right", padx=2, ipady=1)
    
    return entry, btn

ts_entry, btn_ts = create_param_input(sliders_frame, "Forward S (TS)", "TS", 0, 0, 500)
tm_entry, btn_tm = create_param_input(sliders_frame, "Forward M (TM)", "TM", 0, 1, 700)
tl_entry, btn_tl = create_param_input(sliders_frame, "Forward L (TL)", "TL", 0, 2, 900)

rs_entry, btn_rs = create_param_input(sliders_frame, "Return S (RS)", "RS", 1, 0, 500)
rm_entry, btn_rm = create_param_input(sliders_frame, "Return M (RM)", "RM", 1, 1, 700)
rl_entry, btn_rl = create_param_input(sliders_frame, "Return L (RL)", "RL", 1, 2, 900)

# ── Wait Time (TW) — spans both columns ──
f_tw = tk.Frame(f_cal, bg=CARD)
f_tw.pack(fill="x", pady=(8, 0))

tk.Label(f_tw, text="Egg Wait Time (TW) — pause", font=(SANS, 9, "bold"), bg=CARD, fg=TEXT2).pack(side="left")

def tw_send():
    try:
        v_int = int(tw_entry.get())
        if v_int < 1: raise ValueError()
        send_cmd(f"TW{v_int}")
    except ValueError:
        messagebox.showwarning("Invalid Input", "TW must be a positive integer.")

btn_tw = tk.Button(f_tw, text="SET TW", command=tw_send, bg=CARD_HI, fg=TEXT, activebackground=BORDER, font=(SANS, 8, "bold"), relief="flat", cursor="hand2")
btn_tw.pack(side="right")

tk.Label(f_tw, text="ms", font=(SANS, 9), bg=CARD, fg=TEXT2).pack(side="right", padx=(2, 5))

tw_entry = tk.Entry(f_tw, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, font=(MONO, 10), width=6, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
tw_entry.insert(0, "1000")
tw_entry.pack(side="right", padx=2, ipady=1)

# Neutral Point Control
f_neutral = tk.Frame(f_cal, bg=CARD)
f_neutral.pack(fill="x", pady=(10, 0))

tk.Label(f_neutral, text="Servo Neutral Point (N)", font=(SANS, 9, "bold"), bg=CARD, fg=TEXT2).pack(side="left")
neutral_val = tk.Label(f_neutral, text="90", font=(MONO, 11, "bold"), bg=CARD, fg=AMBER)
neutral_val.pack(side="left", padx=5)

neutral_entry = tk.Entry(f_neutral, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, font=(MONO, 10), width=6, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
neutral_entry.insert(0, "90")
neutral_entry.pack(side="right", padx=(5, 0), ipady=1)

btn_send_n = tk.Button(f_neutral, text="SET N", command=send_neutral, bg=CARD_HI, fg=TEXT, activebackground=BORDER, font=(SANS, 8, "bold"), relief="flat", cursor="hand2")
btn_send_n.pack(side="right")

# VCW Control
f_vcw = tk.Frame(f_cal, bg=CARD)
f_vcw.pack(fill="x", pady=(5, 0))

tk.Label(f_vcw, text="CW Speed (VCW, 0-89)", font=(SANS, 9, "bold"), bg=CARD, fg=TEXT2).pack(side="left")
vcw_val = tk.Label(f_vcw, text="80", font=(MONO, 11, "bold"), bg=CARD, fg=AMBER)
vcw_val.pack(side="left", padx=5)

vcw_entry = tk.Entry(f_vcw, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, font=(MONO, 10), width=6, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
vcw_entry.insert(0, "80")
vcw_entry.pack(side="right", padx=(5, 0), ipady=1)

btn_send_vcw = tk.Button(f_vcw, text="SET VCW", command=send_vcw, bg=CARD_HI, fg=TEXT, activebackground=BORDER, font=(SANS, 8, "bold"), relief="flat", cursor="hand2")
btn_send_vcw.pack(side="right")

# VCCW Control
f_vccw = tk.Frame(f_cal, bg=CARD)
f_vccw.pack(fill="x", pady=(5, 0))

tk.Label(f_vccw, text="CCW Speed (VCCW, 91-180)", font=(SANS, 9, "bold"), bg=CARD, fg=TEXT2).pack(side="left")
vccw_val = tk.Label(f_vccw, text="100", font=(MONO, 11, "bold"), bg=CARD, fg=AMBER)
vccw_val.pack(side="left", padx=5)

vccw_entry = tk.Entry(f_vccw, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, font=(MONO, 10), width=6, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
vccw_entry.insert(0, "100")
vccw_entry.pack(side="right", padx=(5, 0), ipady=1)

btn_send_vccw = tk.Button(f_vccw, text="SET VCCW", command=send_vccw, bg=CARD_HI, fg=TEXT, activebackground=BORDER, font=(SANS, 8, "bold"), relief="flat", cursor="hand2")
btn_send_vccw.pack(side="right")

# ── Left Column: Manual Servo Test (Timed Pulse) ──
f_pulse = tk.Frame(col_left, bg=CARD, highlightthickness=1, highlightbackground=BORDER, pady=12, padx=15)
f_pulse.pack(fill="x", pady=(10, 0))

tk.Label(f_pulse, text="MANUAL SERVO TEST (TIMED PULSE)", font=(SANS, 10, "bold"), bg=CARD, fg=AMBER).pack(anchor="w", pady=(0, 8))

row_pulse = tk.Frame(f_pulse, bg=CARD)
row_pulse.pack(fill="x", pady=(0, 6))

# Direction toggle
pulse_dir_var = tk.StringVar(value="CW")

def set_pulse_dir(d):
    pulse_dir_var.set(d)
    if d == "CW":
        btn_dir_cw.config(bg=AMBER, fg="#0F172A")
        btn_dir_ccw.config(bg=CARD_HI, fg=TEXT2)
    else:
        btn_dir_ccw.config(bg=AMBER, fg="#0F172A")
        btn_dir_cw.config(bg=CARD_HI, fg=TEXT2)

btn_dir_cw = tk.Button(row_pulse, text="CW ↻", command=lambda: set_pulse_dir("CW"), bg=AMBER, fg="#0F172A", activebackground="#FBBF24", font=(SANS, 9, "bold"), relief="flat", cursor="hand2", width=6)
btn_dir_cw.pack(side="left", padx=(0, 4))

btn_dir_ccw = tk.Button(row_pulse, text="CCW ↺", command=lambda: set_pulse_dir("CCW"), bg=CARD_HI, fg=TEXT2, activebackground="#FBBF24", font=(SANS, 9, "bold"), relief="flat", cursor="hand2", width=6)
btn_dir_ccw.pack(side="left", padx=(0, 10))

# Duration entry
pulse_ms_entry = tk.Entry(row_pulse, bg=CARD_HI, fg=TEXT, insertbackground=TEXT, font=(MONO, 12, "bold"), width=6, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
pulse_ms_entry.insert(0, "500")
pulse_ms_entry.pack(side="left", padx=(0, 4), ipady=3)

tk.Label(row_pulse, text="ms", font=(SANS, 11), bg=CARD, fg=TEXT2).pack(side="left", padx=(0, 10))

# Pulse button
btn_pulse = tk.Button(row_pulse, text="▶ PULSE", command=send_pulse, bg="#059669", fg=TEXT, activebackground="#10B981", font=(SANS, 10, "bold"), relief="flat", cursor="hand2")
btn_pulse.pack(side="left", fill="x", expand=True)

# ── Right Column: Diagnostic Console / Logs ──
f_console = tk.Frame(col_right, bg=CARD, highlightthickness=1, highlightbackground=BORDER, pady=12, padx=15)
f_console.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
col_right.rowconfigure(0, weight=4)

tk.Label(f_console, text="DIAGNOSTIC SERIAL LOG", font=(SANS, 10, "bold"), bg=CARD, fg=AMBER).pack(anchor="w")

log_box = tk.Text(f_console, font=(MONO, 8), bg=BG, fg="#10B981", relief="flat", insertbackground="#10B981", wrap="word", borderwidth=0)
log_box.pack(fill="both", expand=True, pady=8)
log_box.config(state="disabled")

row_log_btns = tk.Frame(f_console, bg=CARD)
row_log_btns.pack(fill="x")

btn_clear = tk.Button(row_log_btns, text="Clear Log", command=clear_log, bg=CARD_HI, fg=TEXT2, activebackground=BORDER, font=(SANS, 8), relief="flat", cursor="hand2")
btn_clear.pack(side="right")

# ── Right Column: Emergency & Manual Controls ──
f_manual = tk.Frame(col_right, bg=CARD, highlightthickness=1, highlightbackground=BORDER, pady=12, padx=15)
f_manual.grid(row=1, column=0, sticky="ew")
col_right.rowconfigure(1, weight=1)

tk.Label(f_manual, text="QUICK ACTIONS / OVERRIDES", font=(SANS, 10, "bold"), bg=CARD, fg=AMBER).pack(anchor="w", pady=(0, 8))

row_actions = tk.Frame(f_manual, bg=CARD)
row_actions.pack(fill="x", pady=(0, 6))

btn_stop = tk.Button(row_actions, text="■ STOP ALL (S)", command=lambda: send_cmd("S"), bg=RED, fg=TEXT, activebackground="#F87171", font=(SANS, 9, "bold"), relief="flat", cursor="hand2")
btn_stop.pack(side="left", fill="x", expand=True, padx=(0, 4))

btn_status = tk.Button(row_actions, text="? QUERY STATUS", command=lambda: send_cmd("?"), bg=CARD_HI, fg=TEXT, activebackground=BORDER, font=(SANS, 9, "bold"), relief="flat", cursor="hand2")
btn_status.pack(side="left", fill="x", expand=True, padx=(0, 4))

btn_tare = tk.Button(row_actions, text="⚖ TARE SCALE", command=lambda: send_cmd("T"), bg="#6D28D9", fg=TEXT, activebackground="#8B5CF6", font=(SANS, 9, "bold"), relief="flat", cursor="hand2")
btn_tare.pack(side="left", fill="x", expand=True)

row_tests = tk.Frame(f_manual, bg=CARD)
row_tests.pack(fill="x")

btn_test_cw = tk.Button(row_tests, text="Test CW Continuo", command=lambda: send_cmd("TCCW"), bg=CARD_HI, fg=TEXT2, activebackground=BORDER, font=(SANS, 9), relief="flat", cursor="hand2")
btn_test_cw.pack(side="left", fill="x", expand=True, padx=(0, 4))

btn_test_ccw = tk.Button(row_tests, text="Test CCW Continuo", command=lambda: send_cmd("TCCCW"), bg=CARD_HI, fg=TEXT2, activebackground=BORDER, font=(SANS, 9), relief="flat", cursor="hand2")
btn_test_ccw.pack(side="left", fill="x", expand=True)

row_sys = tk.Frame(f_manual, bg=CARD)
row_sys.pack(fill="x", pady=(10, 0))

btn_save = tk.Button(row_sys, text="💾 SAVE CALIBRATION TO EEPROM", command=lambda: send_cmd("SAVE"), bg=AMBER, fg="#0F172A", activebackground="#FBBF24", font=(SANS, 9, "bold"), relief="flat", cursor="hand2")
btn_save.pack(side="left", fill="x", expand=True)

# Initial Setup: Disable controls since we are disconnected
enable_controls(False)

# Make executable permissions on exit
log("Test Harness UI initialized. Ready to connect.")
root.mainloop()
