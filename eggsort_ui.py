"""
EggSort — Weight Classification & Sorting System
Communicates with eggsort.ino over serial (9600 baud).
Requires: pip install pyserial
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
command_count = 0
current_weight = 0.0
current_category = None
cal_factor = 420.0
auto_on = False
live_on = False
counts = {"S": 0, "M": 0, "L": 0}

# ─── Palette — dark industrial instrument ────────────────────────
BG       = "#08080C"
CARD     = "#111118"
CARD_HI  = "#1A1A25"
BORDER   = "#1E1E30"
AMBER    = "#F59E0B"
AMBER_DK = "#92400E"
GREEN    = "#22C55E"
RED      = "#EF4444"
CYAN     = "#0EA5E9"
TEXT     = "#E8E8F0"
TEXT2    = "#9898A8"
TEXT3    = "#52526B"
MONO     = "Consolas"
SANS     = "Segoe UI"

CAT = {
    "S": {"color": "#F97316", "dark": "#7C2D12",
          "name": "SMALL",  "range": "< 53g",   "angle": "60°"},
    "M": {"color": "#22C55E", "dark": "#14532D",
          "name": "MEDIUM", "range": "53–62g",   "angle": "120°"},
    "L": {"color": "#3B82F6", "dark": "#1E3A5F",
          "name": "LARGE",  "range": "> 62g",    "angle": "180°"},
}


# ═══════════════════════════════════════════════════════════════
#  Serial
# ═══════════════════════════════════════════════════════════════

def get_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


def connect():
    global ser
    port = port_var.get()
    if not port:
        messagebox.showwarning("Sin puerto", "Selecciona un puerto COM.")
        return
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)
        conn_dot.config(fg=GREEN)
        conn_lbl.config(text=f"CONNECTED — {port}")
        btn_conn.config(state="disabled")
        btn_disc.config(state="normal")
        log("✓ Connected to " + port)
        threading.Thread(target=serial_reader, daemon=True).start()
    except Exception as e:
        messagebox.showerror("Error", str(e))
        log("✗ " + str(e))


def disconnect():
    global ser, auto_on, live_on
    auto_on = False
    live_on = False
    if ser and ser.is_open:
        send_cmd("S")
        ser.close()
    ser = None
    conn_dot.config(fg=RED)
    conn_lbl.config(text="DISCONNECTED")
    btn_conn.config(state="normal")
    btn_disc.config(state="disabled")
    update_mode_btns()
    log("○ Disconnected")


def send_cmd(cmd):
    global command_count
    if ser and ser.is_open:
        try:
            ser.write((cmd + "\n").encode())
            command_count += 1
            root.after(0, lambda: stat_cmds.config(text=str(command_count)))
            log(f"→ {cmd}")
        except Exception as e:
            log(f"✗ {e}")


def serial_reader():
    global current_weight, current_category, auto_on, live_on, cal_factor
    while ser and ser.is_open:
        try:
            raw = ser.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            root.after(0, lambda l=raw: log(f"← {l}"))

            if raw.startswith("R"):
                try:
                    w = float(raw[1:])
                    current_weight = w
                    root.after(0, lambda: render_weight(w, None))
                except ValueError:
                    pass
            elif raw.startswith("W"):
                try:
                    parts = raw[1:].split(":")
                    w, cat = float(parts[0]), parts[1]
                    current_weight = w
                    current_category = cat
                    root.after(0, lambda: render_weight(w, cat))
                except (ValueError, IndexError):
                    pass
            elif raw.startswith("DONE:"):
                cat = raw.split(":")[1]
                counts[cat] = counts.get(cat, 0) + 1
                root.after(0, render_counts)
            elif raw.startswith("OK AUTO="):
                auto_on = raw.endswith("ON")
                root.after(0, update_mode_btns)
            elif raw.startswith("OK LIVE="):
                live_on = raw.endswith("ON")
                root.after(0, update_mode_btns)
            elif raw.startswith("OK CAL="):
                try:
                    cal_factor = float(raw.split("=")[1])
                    root.after(0, lambda: [cal_entry.delete(0, "end"), cal_entry.insert(0, f"{cal_factor:.1f}")])
                except ValueError:
                    pass
        except Exception:
            break


# ═══════════════════════════════════════════════════════════════
#  UI update helpers
# ═══════════════════════════════════════════════════════════════

def render_weight(w, cat):
    """Redraw the weight display canvas with glow rings."""
    weight_canvas.delete("all")
    cx, cy = 200, 110

    if cat:
        clr = CAT[cat]["color"]
    elif w > 0:
        clr = AMBER
    else:
        clr = TEXT3

    # Concentric glow rings
    for i in range(3):
        r = 85 + i * 14
        weight_canvas.create_oval(
            cx-r, cy-r, cx+r, cy+r, outline=clr, width=1)

    # Weight number
    weight_canvas.create_text(
        cx, cy - 10, text=f"{w:.1f}",
        font=(MONO, 44, "bold"), fill=clr)
    weight_canvas.create_text(
        cx, cy + 36, text="gramos",
        font=(SANS, 11), fill=TEXT2)

    # Category tag
    if cat:
        c = CAT[cat]
        weight_canvas.create_text(
            cx, cy + 58,
            text=f"▸ {c['name']} ({c['range']}) → Servo {c['angle']}",
            font=(SANS, 10, "bold"), fill=c["color"])
    elif w > 0:
        pc = "S" if w < 53 else ("M" if w <= 62 else "L")
        weight_canvas.create_text(
            cx, cy + 58, text=f"~ {CAT[pc]['name']}",
            font=(SANS, 10), fill=TEXT3)

    highlight_cats(cat)


def highlight_cats(cat):
    for key in ("S", "M", "L"):
        c = CAT[key]
        on = (key == cat)
        bg = c["dark"] if on else CARD
        fg = c["color"] if on else TEXT3
        bdr = c["color"] if on else BORDER

        cat_frames[key].config(bg=bg, highlightbackground=bdr)
        for child in cat_frames[key].winfo_children():
            child.config(bg=bg)
        cat_ltrs[key].config(fg=fg)
        cat_rngs[key].config(fg=fg if on else TEXT3)
        cat_angs[key].config(fg=fg if on else TEXT3)
        cat_dots[key].config(fg=c["color"] if on else bg)


def render_counts():
    for key in ("S", "M", "L"):
        cat_cnts[key].config(text=str(counts[key]))
    total_val.config(text=str(sum(counts.values())))


def update_mode_btns():
    btn_auto.config(
        text="■ AUTO: ON" if auto_on else "▶ AUTO",
        bg=GREEN if auto_on else CARD_HI,
        fg="#000" if auto_on else TEXT2)
    btn_live.config(
        text="■ LIVE: ON" if live_on else "◉ LIVE",
        bg=CYAN if live_on else CARD_HI,
        fg="#000" if live_on else TEXT2)


# ═══════════════════════════════════════════════════════════════
#  Commands & helpers
# ═══════════════════════════════════════════════════════════════

def cmd_tare():    send_cmd("T")
def cmd_measure(): send_cmd("M")
def cmd_auto():    send_cmd("A")
def cmd_live():    send_cmd("L")
def cmd_stop():    send_cmd("S")
def cmd_query():   send_cmd("?")
def cmd_cal():
    try:
        val = float(cal_entry.get())
        send_cmd(f"K{val:.1f}")
    except ValueError:
        pass


def refresh_ports():
    ports = get_ports()
    port_dd["values"] = ports
    if ports:
        port_var.set(ports[0])
    log("↻ Ports refreshed")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    log_box.config(state="normal")
    log_box.insert("1.0", f"[{ts}] {msg}\n")
    if int(log_box.index("end-1c").split(".")[0]) > 500:
        log_box.delete("400.0", "end")
    log_box.config(state="disabled")


def clear_log():
    log_box.config(state="normal")
    log_box.delete("1.0", "end")
    log_box.config(state="disabled")


def hover(btn, on_bg, off_bg):
    btn.bind("<Enter>", lambda e: btn.config(bg=on_bg))
    btn.bind("<Leave>", lambda e: btn.config(bg=off_bg))


# ═══════════════════════════════════════════════════════════════
#  BUILD GUI
# ═══════════════════════════════════════════════════════════════

root = tk.Tk()
root.title("EggSort — Weight Classification System")
root.geometry("1080x740")
root.configure(bg=BG)
root.minsize(960, 680)

style = ttk.Style()
style.theme_use("clam")
style.configure("S.Horizontal.TScale",
                troughcolor=CARD_HI, background=AMBER,
                sliderthickness=16, borderwidth=0)
style.configure("TCombobox",
                fieldbackground=CARD_HI, background=CARD_HI,
                foreground=TEXT, arrowcolor=AMBER)

# ═════════════════ TOP BAR ═══════════════════════════════════
top = tk.Frame(root, bg=CARD, height=50)
top.pack(fill="x")
top.pack_propagate(False)

tk.Label(top, text="EGGSORT", font=(MONO, 16, "bold"),
         bg=CARD, fg=AMBER).pack(side="left", padx=(20, 6))
tk.Label(top, text="v1.0", font=(MONO, 9),
         bg=CARD, fg=TEXT3).pack(side="left", pady=(2, 0))

conn_dot = tk.Label(top, text="●", font=(SANS, 14), bg=CARD, fg=RED)
conn_dot.pack(side="right", padx=(0, 12))
conn_lbl = tk.Label(top, text="DISCONNECTED",
                     font=(MONO, 9, "bold"), bg=CARD, fg=TEXT2)
conn_lbl.pack(side="right", padx=(0, 4))

# ═════════════════ BODY ═════════════════════════════════════
body = tk.Frame(root, bg=BG)
body.pack(fill="both", expand=True, padx=14, pady=10)
body.columnconfigure(0, weight=3)
body.columnconfigure(1, weight=2)
body.rowconfigure(0, weight=1)

col_l = tk.Frame(body, bg=BG)
col_l.grid(row=0, column=0, sticky="nsew", padx=(0, 7))

col_r = tk.Frame(body, bg=BG)
col_r.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

# ═════════════════ LEFT — WEIGHT DISPLAY ═════════════════════
w_card = tk.Frame(col_l, bg=CARD,
                  highlightthickness=1, highlightbackground=BORDER)
w_card.pack(fill="x", pady=(0, 8))

tk.Label(w_card, text="WEIGHT READOUT", font=(MONO, 9, "bold"),
         bg=CARD, fg=TEXT3).pack(anchor="w", padx=14, pady=(10, 0))

weight_canvas = tk.Canvas(w_card, width=400, height=150,
                          bg=CARD, highlightthickness=0)
weight_canvas.pack(pady=(0, 8))

# ═════════════════ LEFT — CATEGORY CARDS ═════════════════════
cat_bar = tk.Frame(col_l, bg=BG)
cat_bar.pack(fill="x", pady=(0, 8))

cat_frames = {}
cat_ltrs   = {}
cat_rngs   = {}
cat_angs   = {}
cat_dots   = {}
cat_cnts   = {}

for i, key in enumerate(("S", "M", "L")):
    c = CAT[key]
    f = tk.Frame(cat_bar, bg=CARD,
                 highlightthickness=2, highlightbackground=BORDER)
    f.pack(side="left", fill="both", expand=True,
           padx=(0 if i == 0 else 3, 0 if i == 2 else 3))

    dot = tk.Label(f, text="●", font=(SANS, 8), bg=CARD, fg=CARD)
    dot.pack(anchor="e", padx=8, pady=(6, 0))

    ltr = tk.Label(f, text=key, font=(MONO, 26, "bold"),
                   bg=CARD, fg=TEXT3)
    ltr.pack(pady=(0, 2))

    tk.Label(f, text=c["name"], font=(MONO, 8, "bold"),
             bg=CARD, fg=TEXT3).pack()

    rng = tk.Label(f, text=c["range"], font=(MONO, 9),
                   bg=CARD, fg=TEXT3)
    rng.pack(pady=(4, 0))

    ang = tk.Label(f, text=f"→ {c['angle']}", font=(MONO, 9),
                   bg=CARD, fg=TEXT3)
    ang.pack(pady=(0, 4))

    cr = tk.Frame(f, bg=CARD)
    cr.pack(pady=(2, 8))
    tk.Label(cr, text="×", font=(MONO, 9),
             bg=CARD, fg=TEXT3).pack(side="left")
    cnt = tk.Label(cr, text="0", font=(MONO, 14, "bold"),
                   bg=CARD, fg=c["color"])
    cnt.pack(side="left", padx=2)

    cat_frames[key] = f
    cat_ltrs[key]   = ltr
    cat_rngs[key]   = rng
    cat_angs[key]   = ang
    cat_dots[key]   = dot
    cat_cnts[key]   = cnt

# ═════════════════ LEFT — CONTROLS ═══════════════════════════
ctrl = tk.Frame(col_l, bg=CARD,
                highlightthickness=1, highlightbackground=BORDER)
ctrl.pack(fill="x", pady=(0, 8))

tk.Label(ctrl, text="CONTROLS", font=(MONO, 9, "bold"),
         bg=CARD, fg=TEXT3).pack(anchor="w", padx=14, pady=(10, 8))

bs = dict(font=(SANS, 10, "bold"), relief="flat",
          padx=12, pady=7, cursor="hand2", activeforeground="#FFF")

r1 = tk.Frame(ctrl, bg=CARD)
r1.pack(fill="x", padx=14, pady=(0, 5))

b = tk.Button(r1, text="⚖ TARE", command=cmd_tare,
              bg="#5B21B6", fg="#FFF", activebackground="#7C3AED", **bs)
b.pack(side="left", fill="x", expand=True, padx=(0, 4))
hover(b, "#7C3AED", "#5B21B6")

b = tk.Button(r1, text="⬡ MEASURE", command=cmd_measure,
              bg=AMBER_DK, fg="#FFF", activebackground=AMBER, **bs)
b.pack(side="left", fill="x", expand=True, padx=(0, 4))
hover(b, AMBER, AMBER_DK)

b = tk.Button(r1, text="■ STOP", command=cmd_stop,
              bg="#991B1B", fg="#FFF", activebackground=RED, **bs)
b.pack(side="left", fill="x", expand=True)
hover(b, RED, "#991B1B")

r2 = tk.Frame(ctrl, bg=CARD)
r2.pack(fill="x", padx=14, pady=(0, 12))

btn_auto = tk.Button(r2, text="▶ AUTO", command=cmd_auto,
                     bg=CARD_HI, fg=TEXT2,
                     activebackground="#16A34A", **bs)
btn_auto.pack(side="left", fill="x", expand=True, padx=(0, 4))

btn_live = tk.Button(r2, text="◉ LIVE", command=cmd_live,
                     bg=CARD_HI, fg=TEXT2,
                     activebackground="#0284C7", **bs)
btn_live.pack(side="left", fill="x", expand=True, padx=(0, 4))

b = tk.Button(r2, text="? STATUS", command=cmd_query,
              bg=CARD_HI, fg=TEXT2, activebackground="#374151", **bs)
b.pack(side="left", fill="x", expand=True)

# ═════════════════ RIGHT — SERIAL CONNECTION ═════════════════
cn = tk.Frame(col_r, bg=CARD,
              highlightthickness=1, highlightbackground=BORDER)
cn.pack(fill="x", pady=(0, 8))

tk.Label(cn, text="SERIAL", font=(MONO, 9, "bold"),
         bg=CARD, fg=TEXT3).pack(anchor="w", padx=14, pady=(10, 8))

cn_row = tk.Frame(cn, bg=CARD)
cn_row.pack(fill="x", padx=14, pady=(0, 10))

port_var = tk.StringVar()
ports = get_ports()
port_dd = ttk.Combobox(cn_row, textvariable=port_var, values=ports,
                       width=10, state="readonly", style="TCombobox")
if ports:
    port_var.set(ports[0])
port_dd.pack(side="left", padx=(0, 4))

tk.Button(cn_row, text="↻", command=refresh_ports,
          bg=CARD_HI, fg=AMBER, font=(SANS, 11),
          relief="flat", width=3, cursor="hand2"
          ).pack(side="left", padx=(0, 8))

btn_conn = tk.Button(cn_row, text="CONNECT", command=connect,
                     bg=GREEN, fg="#000", font=(SANS, 9, "bold"),
                     relief="flat", padx=12, pady=3, cursor="hand2")
btn_conn.pack(side="left", padx=(0, 4))

btn_disc = tk.Button(cn_row, text="DISCONNECT", command=disconnect,
                     bg=RED, fg="#FFF", font=(SANS, 9, "bold"),
                     relief="flat", padx=12, pady=3,
                     state="disabled", cursor="hand2")
btn_disc.pack(side="left")

# ═════════════════ RIGHT — CALIBRATION ═══════════════════════
ca = tk.Frame(col_r, bg=CARD,
              highlightthickness=1, highlightbackground=BORDER)
ca.pack(fill="x", pady=(0, 8))

tk.Label(ca, text="CALIBRATION FACTOR", font=(MONO, 9, "bold"),
         bg=CARD, fg=TEXT3).pack(anchor="w", padx=14, pady=(10, 6))

cal_row = tk.Frame(ca, bg=CARD)
cal_row.pack(fill="x", padx=14, pady=(0, 6))

cal_entry = tk.Entry(cal_row, bg=CARD_HI, fg=AMBER, insertbackground=AMBER, font=(MONO, 14, "bold"), width=8, borderwidth=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
cal_entry.insert(0, "420.0")
cal_entry.pack(side="left", padx=(0, 10), ipady=3)

b_cal = tk.Button(cal_row, text="SEND K", command=cmd_cal,
              bg=CARD_HI, fg=TEXT, font=(SANS, 9, "bold"),
              relief="flat", padx=10, pady=4, cursor="hand2")
b_cal.pack(side="left")
hover(b_cal, BORDER, CARD_HI)

b_save = tk.Button(ca, text="💾 SAVE TO EEPROM", command=lambda: send_cmd("SAVE"),
              bg=AMBER_DK, fg="#FFF", font=(SANS, 9, "bold"),
              relief="flat", padx=10, pady=5, cursor="hand2")
b_save.pack(fill="x", padx=14, pady=(0, 10))
hover(b_save, AMBER, AMBER_DK)

# ═════════════════ RIGHT — STATS ═════════════════════════════
st = tk.Frame(col_r, bg=CARD,
              highlightthickness=1, highlightbackground=BORDER)
st.pack(fill="x", pady=(0, 8))

tk.Label(st, text="STATISTICS", font=(MONO, 9, "bold"),
         bg=CARD, fg=TEXT3).pack(anchor="w", padx=14, pady=(10, 6))

sg = tk.Frame(st, bg=CARD)
sg.pack(fill="x", padx=14, pady=(0, 4))

for i, key in enumerate(("S", "M", "L")):
    c = CAT[key]
    tk.Label(sg, text=f"● {c['name']}", font=(MONO, 9),
             bg=CARD, fg=c["color"]).grid(row=i, column=0,
                                          sticky="w", pady=1)
    tk.Label(sg, text=c["range"], font=(MONO, 8),
             bg=CARD, fg=TEXT3).grid(row=i, column=1,
                                     sticky="w", padx=(8, 0), pady=1)

tk.Frame(st, bg=BORDER, height=1).pack(fill="x", padx=14, pady=6)

sr = tk.Frame(st, bg=CARD)
sr.pack(fill="x", padx=14, pady=(0, 4))
tk.Label(sr, text="Commands", font=(MONO, 9),
         bg=CARD, fg=TEXT3).pack(side="left")
stat_cmds = tk.Label(sr, text="0", font=(MONO, 11, "bold"),
                     bg=CARD, fg=AMBER)
stat_cmds.pack(side="right")

sr2 = tk.Frame(st, bg=CARD)
sr2.pack(fill="x", padx=14, pady=(0, 10))
tk.Label(sr2, text="Sorted", font=(MONO, 9),
         bg=CARD, fg=TEXT3).pack(side="left")
total_val = tk.Label(sr2, text="0", font=(MONO, 11, "bold"),
                     bg=CARD, fg=GREEN)
total_val.pack(side="right")

# ═════════════════ RIGHT — LOG ═══════════════════════════════
lg = tk.Frame(col_r, bg=CARD,
              highlightthickness=1, highlightbackground=BORDER)
lg.pack(fill="both", expand=True)

lh = tk.Frame(lg, bg=CARD)
lh.pack(fill="x", padx=14, pady=(10, 6))
tk.Label(lh, text="LOG", font=(MONO, 9, "bold"),
         bg=CARD, fg=TEXT3).pack(side="left")
tk.Button(lh, text="✕", command=clear_log,
          font=(SANS, 8), bg="#991B1B", fg="#FFF",
          relief="flat", padx=6, pady=1, cursor="hand2"
          ).pack(side="right")

log_box = tk.Text(lg, font=(MONO, 8), bg=BG, fg=GREEN,
                  relief="flat", insertbackground=GREEN, wrap="word")
log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
log_box.config(state="disabled")

# ═════════════════ RIGHT — QUICK START ═══════════════════════
ht = tk.Frame(col_r, bg=CARD,
              highlightthickness=1, highlightbackground=BORDER)
ht.pack(fill="x", pady=(8, 0))

tk.Label(ht, text="QUICK START", font=(MONO, 9, "bold"),
         bg=CARD, fg=TEXT3).pack(anchor="w", padx=14, pady=(10, 4))

for h in [
    "1 → Connect & wait for EGGSORT_READY",
    "2 → TARE with empty scale",
    "3 → Place object → MEASURE",
    "4 → Servo sorts automatically",
    "5 → Use AUTO for continuous mode",
]:
    tk.Label(ht, text=h, font=(MONO, 8), bg=CARD,
             fg=TEXT3, anchor="w").pack(anchor="w", padx=14, pady=0)

tk.Label(ht, text="", bg=CARD).pack(pady=2)

# ═════════════════ LAUNCH ════════════════════════════════════
render_weight(0.0, None)
log("EggSort UI initialized")
log("Select a COM port and connect")
root.mainloop()
