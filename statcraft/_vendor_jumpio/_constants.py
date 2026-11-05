"""Format constants for `.jmp` files. See docs/jmp_format.md."""

from datetime import datetime

MAGIC: bytes = bytes.fromhex("ffff00000700000004000000010001000200")
assert len(MAGIC) == 18

GZIP_MARKER: bytes = bytes.fromhex("efbefeca")

JMP_EPOCH: datetime = datetime(1904, 1, 1)

HEADER_ANCHOR: bytes = bytes.fromhex("070008000000")
HEADER_REWIND_FROM_ANCHOR_END: int = 38

ROWSTATE_MARKERS: tuple[str, ...] = (
    "\u2022", "+", "X", "\u25a1",
    "\u25ca", "\u25b3", "Y", "Z",
    "\u25ef", "\u25ad", "\u25af", "*",
    "\u26ab", "\u25ac", "\u25ae", "\u25a0",
    "\u29eb", "\u25bd", "\u25c1", "\u25b7",
    "\u25b2", "\u25bc", "\u25c0", "\u25b6",
    "\u2227", "\u2228", "<", ">",
    "\u2223", "\u2500", "/", "\\",
)
assert len(ROWSTATE_MARKERS) == 32

ROWSTATE_COLORS: tuple[str, ...] = (
    "#000000", "#555555", "#787878", "#C0C0C0", "#FFFFFF",
    "#A00922", "#C91629", "#F03246", "#FF5C76", "#FF98A6",
    "#904700", "#BC5B03", "#E57406", "#FF9138", "#FFB17D",
    "#706F00", "#AFA502", "#DAD109", "#F0E521", "#FFF977",
    "#516A00", "#729400", "#90BF04", "#A2DC06", "#C1FF3D",
    "#00670C", "#11981B", "#21BC2D", "#23E72E", "#6AFF6B",
    "#007254", "#019970", "#04C791", "#06E3AA", "#0FFFBC",
    "#006D71", "#01989C", "#0CBCBC", "#06E2E3", "#67FFF7",
    "#00638F", "#0380B4", "#05A1D2", "#08C5F7", "#75E4FF",
    "#034AB0", "#0557D6", "#2867FD", "#4E9CFF", "#7E89FF",
    "#6A02A7", "#8C05CF", "#AB08FC", "#C170FF", "#D29AFF",
    "#930195", "#B803B9", "#DC06E1", "#FA50FF", "#FD96FF",
    "#9D0170", "#C5048D", "#E906A4", "#FF49BC", "#FF8CCD",
)
assert len(ROWSTATE_COLORS) == 65
