"""
gps_extractor.py – Extract GPS from GPS Map Camera app photos.
Strategy: EXIF first → OCR fallback (Tesseract).
"""
import re, os
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class GPSResult:
    lat:        float
    lng:        float
    address:    str  = ""
    timestamp:  str  = ""
    method:     str  = ""
    confidence: str  = ""


def extract_gps(image_path: str) -> Optional[GPSResult]:
    if not os.path.exists(image_path):
        return None
    return _try_exif(image_path) or _try_ocr(image_path)


def extract_gps_from_images(image_paths: list) -> Optional[GPSResult]:
    exif_r = ocr_r = None
    for p in image_paths:
        r = extract_gps(p)
        if r is None:
            continue
        if r.method == "EXIF" and exif_r is None:
            exif_r = r
        elif r.method == "OCR" and ocr_r is None:
            ocr_r = r
    return exif_r or ocr_r


# ── EXIF ───────────────────────────────────────────────────────────────────────

def _try_exif(path: str) -> Optional[GPSResult]:
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        raw = Image.open(path)._getexif()
        if not raw:
            return None
        gps_info = dt = None
        for tid, val in raw.items():
            tag = TAGS.get(tid, tid)
            if tag == "GPSInfo":
                gps_info = {GPSTAGS.get(k, k): v for k, v in val.items()}
            elif tag == "DateTime":
                dt = str(val)
        if not gps_info:
            return None
        lat = _dms(gps_info.get("GPSLatitude"),  gps_info.get("GPSLatitudeRef",  "N"))
        lng = _dms(gps_info.get("GPSLongitude"), gps_info.get("GPSLongitudeRef", "E"))
        if lat is None or lng is None:
            return None
        return GPSResult(lat=lat, lng=lng, timestamp=dt or "", method="EXIF", confidence="high")
    except Exception:
        return None


def _dms(dms, ref) -> Optional[float]:
    if not dms or len(dms) < 3:
        return None
    try:
        def f(v):
            if hasattr(v, 'numerator'): return v.numerator / v.denominator
            if isinstance(v, tuple) and len(v) == 2: return v[0] / v[1]
            return float(v)
        dec = f(dms[0]) + f(dms[1]) / 60 + f(dms[2]) / 3600
        return round(-dec if ref in ("S", "W") else dec, 7)
    except Exception:
        return None


# ── OCR ────────────────────────────────────────────────────────────────────────

def _try_ocr(path: str) -> Optional[GPSResult]:
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        img  = Image.open(path).convert("RGB")
        w, h = img.size

        # GPS Map Camera puts overlay in the bottom ~40%; try multiple crop zones
        crop_ratios = [0.60, 0.55, 0.65, 0.50, 0.70]
        preprocessors = [_prep_dark, _prep_invert]

        for ratio in crop_ratios:
            crop = img.crop((0, int(h * ratio), w, h))
            if crop.width < 1200:
                scale = 1200 / crop.width
                crop  = crop.resize((int(crop.width * scale),
                                     int(crop.height * scale)), Image.LANCZOS)
            for prep in preprocessors:
                text = pytesseract.image_to_string(prep(crop),
                                                   config='--psm 6 --oem 3')
                lat, lng = _parse_coords(text)
                if lat is not None:
                    addr = _parse_address(text)
                    ts   = _parse_timestamp(text)
                    return GPSResult(lat=lat, lng=lng, address=addr,
                                     timestamp=ts, method="OCR",
                                     confidence="medium" if addr else "low")
        return None
    except ImportError:
        return None
    except Exception:
        return None


def _prep_dark(crop):
    from PIL import ImageEnhance, ImageFilter
    img = ImageEnhance.Contrast(crop).enhance(3.0)
    img = ImageEnhance.Brightness(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(2.5)
    return img.filter(ImageFilter.SHARPEN)


def _prep_invert(crop):
    from PIL import ImageEnhance, ImageOps, ImageFilter
    img = ImageOps.invert(crop)
    img = ImageEnhance.Contrast(img).enhance(2.0)
    return img.filter(ImageFilter.SHARPEN)


# ── Coordinate parsing ─────────────────────────────────────────────────────────

def _parse_coords(text: str) -> Tuple[Optional[float], Optional[float]]:
    # Pattern 1: "Lat 12.982756° Long 74.799452°"
    m = re.search(
        r'[Ll]at[\s:°]*(\d{1,3}\.\d+)[°\s,]+[Ll]o[ng]*[\s:°]*(\d{2,3}\.\d+)',
        text)
    if m:
        return _validate(float(m.group(1)), float(m.group(2)))

    # Pattern 2: "12.982756° N  74.799452° E"
    m = re.search(
        r'(\d{1,2}\.\d{4,})\s*°?\s*[Nn]\s+(\d{2,3}\.\d{4,})\s*°?\s*[Ee]',
        text)
    if m:
        return _validate(float(m.group(1)), float(m.group(2)))

    # Pattern 3: two standalone high-precision decimals
    decimals = re.findall(r'(\d{1,2}\.\d{5,})', text)
    for i in range(len(decimals) - 1):
        r = _validate(float(decimals[i]), float(decimals[i+1]))
        if r[0] is not None:
            return r

    return None, None


def _validate(lat, lng):
    if 6.0 <= lat <= 37.0 and 68.0 <= lng <= 98.0:  # India bbox
        return round(lat, 7), round(lng, 7)
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return round(lat, 7), round(lng, 7)
    return None, None


# ── Address parsing ────────────────────────────────────────────────────────────

# Known Indian location keywords
_LOC_KW = re.compile(
    r'(Mangaluru|Mumbai|Delhi|Bengaluru|Bangalore|Chennai|Hyderabad|Kochi|'
    r'Surathkal|Hubli|Mysuru|Mysore|Udupi|Belagavi|Pune|Kolkata|'
    r'India|Karnataka|Kerala|Maharashtra|Tamil Nadu|Goa|Andhra Pradesh|'
    r'Telangana|[A-Z][a-z]+ (?:Road|Street|Lane|Nagar|Circle|Bridge|'
    r'Colony|Layout|District|Taluk|Ward))',
    re.I
)
_LOC_BROAD = re.compile(
    r'India|Karnataka|Kerala|Maharashtra|Tamil|Goa|Andhra|'
    r'Mangaluru|Mumbai|Delhi|Bengaluru|Chennai|Hyderabad|Kochi|'
    r'Surathkal|Hubli|Mysuru|Belagavi|Udupi',
    re.I
)
_SKIP = re.compile(r'[Ll]at|[Ll]o[ng]|GMT|°|/202\d|GPS|Camera|Map|Google', re.I)


def _parse_address(text: str) -> str:
    clean_lines = []
    for raw in text.split('\n'):
        line = re.sub(r'[^\x20-\x7E]+', ' ', raw)   # strip non-ASCII
        line = re.sub(r'\s{2,}', ' ', line).strip()
        if len(line) < 8:
            continue
        if _SKIP.search(line):
            continue
        if not re.search(r'[A-Za-z]{3,}', line):
            continue
        # Strip leading OCR noise before first meaningful location word
        m = _LOC_KW.search(line)
        if m:
            line = line[m.start():].strip()
        clean_lines.append(line)

    # Collect lines that mention known locations
    best, capturing = [], False
    for line in clean_lines:
        if _LOC_BROAD.search(line):
            capturing = True
        if capturing and len(best) < 3:
            best.append(line)

    if best:
        return " | ".join(best)

    # Fallback: two longest clean lines
    clean_lines.sort(key=len, reverse=True)
    return " | ".join(clean_lines[:2]) if clean_lines else ""


def _parse_timestamp(text: str) -> str:
    m = re.search(
        r'(\w+day,?\s+\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AP]M'
        r'(?:\s+GMT[^\n]*)?)', text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'\d{1,2}/\d{1,2}/\d{4}', text)
    return m.group(0) if m else ""
