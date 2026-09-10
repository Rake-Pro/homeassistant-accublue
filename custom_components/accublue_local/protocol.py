"""AccuBlue Home wire protocol: frame parsing and result math.

Pure python (stdlib only), no Home Assistant imports, so it can be unit tested
on its own. The parsing and the coefficients are taken verbatim from the
working reference client (IoT-Lab/devices/accublue-home/accublue.py); do not
"tidy" the numbers, they are the disc's published curves.
"""

from __future__ import annotations

import math
import struct

SVC = "00001500-0000-1000-8001-bbbd00000500"
TEST_DATA0 = "00001501-0000-1000-8001-bbbd00000500"   # notify: well set 0
CMD = "00001502-0000-1000-8001-bbbd00000500"          # write
STATUS = "00001503-0000-1000-8001-bbbd00000500"       # notify
TEST_DATA1 = "00001504-0000-1000-8001-bbbd00000500"   # read: well set 1
TEST_DATA2 = "00001505-0000-1000-8001-bbbd00000500"   # read: well set 2

CMD_RUN_TEST, CMD_FETCH_PENDING, CMD_CLEAR_ERROR, CMD_CALIBRATE = 2, 3, 4, 5
CMD_LEN = 12  # the meter ignores shorter writes; the vendor library zero-pads every command to 12 bytes

STATUS_LEN = 39
WELLS_LEN = 88


def cmd(*b):
    return bytes(b).ljust(CMD_LEN, b"\0")


ERRORS = {0: "none", 1: "lid_opened", 2: "speed_lock", 4: "motor_stall", 8: "byte_overflow"}
ERROR_CODES = {v: k for k, v in ERRORS.items()}

# Disk 203 layout: well id -> well index (0-based). Well id == test factor id. Id 0 is the blank.
WELL = {6: 0, 1: 1, 3: 1, 7: 2, 16: 3, 12: 4, 15: 5, 2: 6, 17: 6, 11: 7, 14: 8, 10: 9, 0: 10}
FACTOR = {1: "free_chlorine", 2: "total_chlorine", 3: "bromine", 6: "ph", 7: "alkalinity",
          10: "cyanuric_acid", 11: "iron", 12: "copper", 14: "phosphate", 15: "calcium_hardness",
          16: "salt", 17: "combined_chlorine"}
# (factor id, well set, decimals) in the app's evaluation order
RESULTS = {
    "chlorine": [(1, 0, 2), (2, 0, 2), (17, 0, 2), (7, 0, 0), (6, 0, 1), (15, 1, 0), (10, 1, 0), (12, 1, 1), (11, 1, 1), (14, 1, 0)],
    "salt":     [(1, 0, 2), (2, 0, 2), (17, 0, 2), (7, 0, 0), (6, 0, 1), (15, 1, 0), (10, 1, 0), (12, 1, 1), (11, 1, 1), (16, 1, 0), (14, 1, 0)],
    "bromine":  [(3, 0, 2), (7, 0, 0), (6, 0, 1), (15, 1, 0), (12, 1, 1), (11, 1, 1), (14, 1, 0)],
}

SANITIZERS = list(RESULTS)

# Every factor any sanitizer can produce, in a stable order for entity creation.
ALL_FACTORS = ["free_chlorine", "total_chlorine", "combined_chlorine", "bromine", "ph",
               "alkalinity", "calcium_hardness", "cyanuric_acid", "copper", "iron",
               "salt", "phosphate"]


def parse_status(b):
    u16 = lambda o: struct.unpack_from("<H", b, o)[0]
    sw = struct.unpack_from("<I", b, 0)[0]
    prog = b[17]
    return {
        "switches": sw, "pending_test_data": bool(sw & 8), "calibrating": bool(sw & 0x800),
        "measuring": bool(sw & 0x400), "cur_speed": u16(4), "cur_tach": u16(6), "ticks_to_lock": u16(8),
        "direction": "ccw" if b[10] else "cw", "started": b[11] == 1, "stopped": b[12] == 1,
        "motor_state": b[13], "speed_constant": b[14] == 1, "decelerate": b[15] == 1, "heartbeat": b[16],
        "progress": None if prog == 255 else prog, "fw": f"{b[18]}.{b[19]}",
        "error": ERRORS.get(b[20], b[20]), "last_error": ERRORS.get(b[21], b[21]),
        "test_counter": u16(22), "overflow_bits": u16(24),
        "serial": b[26:39].split(b"\0")[0].decode("ascii", "replace"),
    }


def parse_wells(b):
    """88 bytes -> [4 channels][11 wells] uint16 LE."""
    v = struct.unpack_from("<44H", b, 0)
    return [list(v[c * 11:(c + 1) * 11]) for c in range(4)]


def poly(x, a0, a1, a2, a3):
    return a0 + a1 * x + a2 * x * x + a3 * x * x * x


def calculate(wells, sanitizer):
    """wells: [3 sets][4 channels][11 wells]. Returns {name: value} exactly as the app computes."""
    def absb(fid, ch, ws):
        w, blank = WELL[fid], WELL[0]
        return -math.log10((wells[ws][ch][w] + 1e-7) / (wells[ws][ch][blank] + 1e-7))
    clamp0 = lambda v: v if v >= 0 else 0.0
    out, raw = {}, {}
    for fid, ws, prec in RESULTS[sanitizer]:
        if fid == 1:
            v = clamp0(poly(absb(1, 1, ws), -0.031197, 4.1519, 1.5095, 0))
        elif fid == 2:
            v = poly(absb(2, 1, ws), -0.1969, 5.0017, -0.6324, 0.3939)
            fc = raw.get(1, 0.0)
            v = fc if v < fc else clamp0(v)
        elif fid == 17:
            v = raw.get(2, 0.0) - raw.get(1, 0.0)
        elif fid == 3:
            v = clamp0(poly(absb(3, 1, ws), 0.087541, 14.27877, -2.29894, 1.182999))
        elif fid == 7:
            v = poly(absb(7, 3, ws), -25.57, 506.3, -728.7, 452.0)
            for lim, add in ((5, 2), (10, 4), (15, 6), (20, 8), (25, 10), (30, 8), (35, 6), (40, 4), (45, 2)):
                if v < lim:
                    v += add
                    break
            v = clamp0(v)
        elif fid == 6:
            a = absb(6, 2, ws)
            if sanitizer == "salt":
                c = [poly(a, 6.1296, 3.1919, -1.2284, 0.162), poly(a, 6.1694, 2.6316, -1.0218, 0.24722),
                     poly(a, 6.1876, 2.4509, -1.0248, 0.30122), poly(a, 6.2245, 2.1611, -0.73457, 0.22344)]
            else:
                c = [poly(a, 6.22949, 4.83038, -4.0049, 1.34407), poly(a, 6.28081, 2.9239, -1.15137, 0.19121),
                     poly(a, 6.23477, 3.23593, -1.78586, 0.46703), poly(a, 6.29424, 2.80984, -1.4919, 0.41843)]
            alk = raw.get(7, 0.0)
            if alk <= 55: v = (c[0] + c[2]) / 2
            elif alk <= 100: v = (c[1] + c[2]) / 2
            elif alk <= 160: v = c[2]
            else: v = (c[3] + c[2]) / 2
            v = min(max(v, 6.3), 8.7)
        elif fid == 15:
            a = absb(15, 2, ws) - 1.3 * absb(15, 3, ws)
            v = poly(a, -19.332, 374.84, -261.07, 167.02) if sanitizer == "salt" else poly(a, -11.706, 273.23, -191.15, 147.41)
            v = min(clamp0(v), 900.0)
        elif fid == 10:
            v = max(poly(absb(10, 3, ws), 1.3232, 83.352, -27.877, 22.954), 5.0)
        elif fid == 11:
            v = clamp0(poly(absb(11, 1, ws), -0.02386, 2.481, 0.19, 0))
        elif fid == 12:
            v = clamp0(poly(absb(12, 2, ws), -0.084626, 10.329, 0, 0))
        elif fid == 16:
            a = absb(16, 0, ws) / (absb(16, 2, ws) + 1e-8)
            v = min(clamp0(poly(a, -874.74, 2293.11, 194.84, 0)), 9999.0)
        elif fid == 14:
            v = clamp0(poly(absb(14, 3, ws), -365.4, 5296.9, 0, 0))
        raw[fid] = v
        out[FACTOR[fid]] = round(v, prec)
    return out
