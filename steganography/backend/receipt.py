"""
receipt.py — Generate a print-ready PDF receipt with steganographic texture overlay.

Layout: thermal-printer style, 72 mm wide (~2.83 in), variable height.
The encoder's RGBA texture is composited over white to produce an RGB image,
then tiled as a full-page background before receipt text is drawn on top.
"""
from __future__ import annotations

import io
import os
import tempfile
from typing import Optional

from PIL import Image

from reportlab.lib import colors
from reportlab.lib.pagesizes import inch
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from schemas import Receipt


# ── Layout constants ─────────────────────────────────────────────────────────

PAGE_WIDTH: float = 72 * mm          # 72 mm thermal receipt width
MARGIN: float = 4 * mm               # left/right margin
LINE_H_NORMAL: float = 12            # points
LINE_H_SMALL: float = 10
LINE_H_BOLD: float = 13

FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_SMALL_SIZE = 7
FONT_NORMAL_SIZE = 8
FONT_BOLD_SIZE = 9


# ── Texture helpers ──────────────────────────────────────────────────────────

def _composite_rgba_over_white(texture_png_bytes: bytes) -> Image.Image:
    """
    reportlab cannot embed RGBA PNGs with transparency.
    Alpha-composite the texture over a white background → return RGB Image.
    """
    src = Image.open(io.BytesIO(texture_png_bytes)).convert("RGBA")
    background = Image.new("RGBA", src.size, (255, 255, 255, 255))
    background.paste(src, mask=src.split()[3])   # paste using alpha channel
    return background.convert("RGB")


def _make_tiled_texture(
    texture_png_bytes: bytes,
    page_width_pt: float,
    page_height_pt: float,
) -> bytes:
    """
    Tile the 512×512 texture across the full page dimensions (in points, ~1/72 in).
    Returns JPEG bytes suitable for reportlab's drawImage.

    Points ≈ pixels at 72 dpi, so the tile is already roughly 1:1 at screen
    resolution.  We tile it to cover the whole page without stretching.
    """
    tile_rgb = _composite_rgba_over_white(texture_png_bytes)
    tile_w, tile_h = tile_rgb.size                  # 512 × 512 (default)

    # Page in pixels at 72 dpi: 1 pt == 1 px
    page_px_w = int(page_width_pt) + 1
    page_px_h = int(page_height_pt) + 1

    # How many times to repeat
    cols = -(-page_px_w // tile_w)   # ceiling division
    rows = -(-page_px_h // tile_h)

    tiled = Image.new("RGB", (tile_w * cols, tile_h * rows), (255, 255, 255))
    for r in range(rows):
        for c in range(cols):
            tiled.paste(tile_rgb, (c * tile_w, r * tile_h))

    # Crop to exact page size
    tiled = tiled.crop((0, 0, page_px_w, page_px_h))

    buf = io.BytesIO()
    tiled.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ── Text drawing helpers ─────────────────────────────────────────────────────

def _draw_divider(c: canvas.Canvas, y: float) -> float:
    """Draw a dashed horizontal rule, return new y position."""
    c.setDash(2, 2)
    c.setLineWidth(0.5)
    c.setStrokeColor(colors.black)
    c.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
    c.setDash()
    return y - 4


def _draw_centered(
    c: canvas.Canvas,
    text: str,
    y: float,
    font: str = FONT_NORMAL,
    size: float = FONT_NORMAL_SIZE,
) -> float:
    c.setFont(font, size)
    c.setFillColor(colors.black)
    c.drawCentredString(PAGE_WIDTH / 2, y, text)
    return y - (size + 3)


def _draw_two_col(
    c: canvas.Canvas,
    left: str,
    right: str,
    y: float,
    font: str = FONT_NORMAL,
    size: float = FONT_NORMAL_SIZE,
    indent: float = 0,
) -> float:
    c.setFont(font, size)
    c.setFillColor(colors.black)
    c.drawString(MARGIN + indent, y, left)
    c.drawRightString(PAGE_WIDTH - MARGIN, y, right)
    return y - (size + 3)


def _draw_line(
    c: canvas.Canvas,
    text: str,
    y: float,
    font: str = FONT_NORMAL,
    size: float = FONT_NORMAL_SIZE,
    indent: float = 0,
) -> float:
    c.setFont(font, size)
    c.setFillColor(colors.black)
    c.drawString(MARGIN + indent, y, text)
    return y - (size + 3)


# ── Receipt layout ───────────────────────────────────────────────────────────

def _estimate_height(receipt: Receipt) -> float:
    """
    Estimate the page height in points needed for this receipt.
    Errs on the tall side so nothing gets clipped.
    """
    # header block
    pts = 60
    # divider
    pts += 8
    # items: each has a name+price line and a qty line
    pts += len(receipt.items) * (LINE_H_NORMAL + LINE_H_SMALL + 4)
    # divider + totals (subtotal, tax, total)
    pts += 8 + 3 * (LINE_H_NORMAL + 4)
    # divider + payment / cashier
    pts += 8 + 2 * (LINE_H_NORMAL + 4)
    # bottom padding
    pts += 20
    return max(pts, 200)


def generate_receipt_pdf(
    receipt: Receipt,
    texture_png_bytes: bytes,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Generate a thermal-style receipt PDF with the steganographic texture as
    the full-page background.

    Parameters
    ----------
    receipt           : Receipt data model
    texture_png_bytes : Raw PNG bytes from encoder.encode()
    output_path       : If given, also write the PDF to this path

    Returns
    -------
    PDF bytes
    """
    page_height = _estimate_height(receipt)
    page_size = (PAGE_WIDTH, page_height)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=page_size)

    # ── 1. Background: tiled steganographic texture ──────────────────────────
    tiled_jpeg = _make_tiled_texture(texture_png_bytes, PAGE_WIDTH, page_height)

    # Write texture to a temp file — reportlab's drawImage works best with paths
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(tiled_jpeg)
        tmp_path = tmp.name

    try:
        c.drawImage(
            tmp_path,
            x=0, y=0,
            width=PAGE_WIDTH,
            height=page_height,
            preserveAspectRatio=False,
        )
    finally:
        os.unlink(tmp_path)

    # ── 2. Receipt text on top ───────────────────────────────────────────────
    # reportlab's y=0 is bottom-left; we work from the top down.
    y = page_height - 10

    # Store name
    y = _draw_centered(c, receipt.store_name, y, font=FONT_BOLD, size=FONT_BOLD_SIZE + 2)

    # Address
    if receipt.store_address:
        y = _draw_centered(c, receipt.store_address, y, size=FONT_SMALL_SIZE)

    # Date · txn_id
    date_txn = receipt.date
    if receipt.transaction_id:
        date_txn += f"  ·  {receipt.transaction_id}"
    y = _draw_centered(c, date_txn, y, size=FONT_SMALL_SIZE)

    y -= 4
    y = _draw_divider(c, y)

    # Items
    for item in receipt.items:
        # Item name + total (right-aligned)
        y = _draw_two_col(
            c,
            item.name,
            f"${item.total:.2f}",
            y,
            font=FONT_NORMAL,
            size=FONT_NORMAL_SIZE,
        )
        # qty × unit_price (indented, small)
        qty_label = f"{item.qty:g} × ${item.unit_price:.2f}"
        y = _draw_line(c, qty_label, y, size=FONT_SMALL_SIZE, indent=4)

    y -= 2
    y = _draw_divider(c, y)

    # Subtotal
    y = _draw_two_col(c, "Subtotal:", f"${receipt.subtotal:.2f}", y)

    # Tax
    if receipt.tax_rate is not None:
        tax_label = f"Tax ({receipt.tax_rate * 100:.2f}%):"
    else:
        tax_label = "Tax:"
    y = _draw_two_col(c, tax_label, f"${receipt.tax_amount:.2f}", y)

    # Total (bold)
    y = _draw_two_col(
        c, "TOTAL:", f"${receipt.total:.2f}", y,
        font=FONT_BOLD, size=FONT_BOLD_SIZE,
    )

    y -= 2
    y = _draw_divider(c, y)

    # Payment method
    if receipt.payment_method:
        y = _draw_two_col(c, "Payment:", receipt.payment_method, y)

    # Cashier
    if receipt.cashier:
        y = _draw_two_col(c, "Cashier:", receipt.cashier, y)

    y -= 2
    _draw_divider(c, y)

    c.save()
    pdf_bytes = buf.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes


# ── Convenience wrapper ──────────────────────────────────────────────────────

def encode_and_generate(
    receipt: Receipt,
    output_path: Optional[str] = None,
) -> tuple[bytes, bytes]:
    """
    Encode receipt → steganographic texture PNG, then render to PDF.

    Returns
    -------
    (pdf_bytes, texture_png_bytes)
    """
    from encoder import encode as _encode

    texture_png_bytes, _payload_len, _cap = _encode(receipt)
    pdf_bytes = generate_receipt_pdf(receipt, texture_png_bytes, output_path=output_path)
    return pdf_bytes, texture_png_bytes


# ── CLI smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from schemas import LineItem

    sample = Receipt(
        store_name="Almond Farm Market",
        store_address="123 Grove Ln, Sacramento CA 95814",
        date="2026-04-14",
        transaction_id="TXN-0042",
        items=[
            LineItem(name="Raw Almonds 1lb",  sku="ALM-001", qty=2, unit_price=12.99, total=25.98),
            LineItem(name="Local Honey 12oz", sku="HON-003", qty=1, unit_price=8.49,  total=8.49),
            LineItem(name="Olive Oil 500ml",  sku="OIL-007", qty=1, unit_price=14.99, total=14.99),
        ],
        subtotal=49.46,
        tax_rate=0.0875,
        tax_amount=4.33,
        total=53.79,
        payment_method="Visa •••• 4242",
        cashier="Jordan",
    )

    out = "/tmp/sample_receipt.pdf"
    pdf_bytes, texture_bytes = encode_and_generate(sample, output_path=out)

    print(f"Texture PNG : {len(texture_bytes):,} bytes")
    print(f"Receipt PDF : {len(pdf_bytes):,} bytes")
    print(f"Saved to    : {out}")
