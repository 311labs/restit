import pyqrcode
import io
import base64

def generateQRCode(data, error="H", version=None, mode=None, img_format="png", scale=1):
    # L, M, Q, or H; each level can correct up to 7, 15, 25, or 30
    c = pyqrcode.create(data, error=error)
    s = io.BytesIO()
    if img_format == "base64":
        c.png(s,scale=scale)
        return base64.b64encode(s.getvalue()).decode("ascii")
    elif img_format == "svg":
        c.svg(s, scale=scale) # module_color="#000000"
        return s.getvalue()
    c.png(s,scale=scale)
    return s.getvalue()
