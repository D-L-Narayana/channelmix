"""CSV format detection + parsing for ad-platform exports.

Supported: Google Ads (UI report export), Meta Ads Manager (export with "Day" breakdown), LinkedIn Campaign
Manager, Amazon Ads campaign report and ChannelMix's generic template. Detection is header based: each
format has a weighted signature; the best score above a threshold wins, otherwise ``generic``.

The parser is tolerant of the real-world quirks of these exports: BOM / UTF-16, title + date-range preamble
lines (Google), ``Total:`` footer rows, thousands separators, currency symbols, ``--`` placeholders,
locale date formats, and ``;``/tab delimiters.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.auth import slugify
from app.models import CHANNELS, Channel

FIELDS = ("day", "campaign_name", "external_id", "channel", "impressions", "clicks", "conversions", "spend", "revenue")


def _norm(h: str) -> str:
    h = h.replace("\ufeff", "").strip().lower()
    h = re.sub(r"\s+", " ", h)
    return h


# ---- per-format column synonyms (normalised header -> field). Order = priority. ----
# A synonym may be a plain string (exact match) or a compiled regex (search).
_AMOUNT_SPENT = re.compile(r"^amount spent(?: \((?P<cur>[a-z]{3})\))?$")


@dataclass
class FormatSpec:
    name: str
    channel: Channel | None
    synonyms: dict[str, list]
    signature: dict[str, float]  # normalised header (or regex) -> weight
    threshold: float


GOOGLE = FormatSpec(
    name="google_ads",
    channel=Channel.google,
    synonyms={
        "day": ["day", "date", "week", "month"],
        "campaign_name": ["campaign", "campaign name"],
        "external_id": ["campaign id"],
        "impressions": ["impressions", "impr.", "impr"],
        "clicks": ["clicks", "interactions"],
        "conversions": ["conversions", "conv.", "all conv."],
        "spend": ["cost", "cost (usd)", re.compile(r"^cost \([a-z]{3}\)$")],
        "revenue": ["conv. value", "conversion value", "all conv. value", "total conv. value"],
        "currency": ["currency code", "currency"],
    },
    signature={"campaign": 1.5, "cost": 2.0, "day": 1.0, "impressions": 0.5, "impr.": 1.0, "clicks": 0.5,
               "conversions": 1.0, "conv. value": 1.0, "currency code": 1.5, "campaign id": 0.5,
               "campaign state": 1.0, "campaign status": 0.5, "campaign type": 1.0, "avg. cpc": 1.0, "ctr": 0.5},
    threshold=5.0,
)

META = FormatSpec(
    name="meta_ads",
    channel=Channel.meta,
    synonyms={
        "day": ["day", "date", "reporting starts"],
        "campaign_name": ["campaign name", "campaign"],
        "external_id": ["campaign id"],
        "impressions": ["impressions"],
        "clicks": ["link clicks", "clicks (all)", "clicks"],
        "conversions": ["results", "purchases", "website purchases", "conversions", "leads"],
        "spend": [_AMOUNT_SPENT, "amount spent"],
        "revenue": ["purchases conversion value", "website purchases conversion value",
                    "purchase conversion value", "conversion value"],
    },
    signature={"campaign name": 2.0, _AMOUNT_SPENT: 3.0, "link clicks": 2.0, "results": 1.0, "result type": 1.0,
               "reporting starts": 2.0, "reporting ends": 1.0, "impressions": 0.5, "day": 0.5, "reach": 1.0,
               "frequency": 0.5, "campaign delivery": 1.5, "cpm (cost per 1,000 impressions)": 1.0,
               "cost per results": 1.0, "clicks (all)": 1.0, "ad set name": 1.0},
    threshold=5.0,
)

LINKEDIN = FormatSpec(
    name="linkedin_ads",
    channel=Channel.linkedin,
    synonyms={
        "day": ["start date (in utc)", "start date", "date", "day"],
        "campaign_name": ["campaign name", "campaign"],
        "external_id": ["campaign id"],
        "impressions": ["impressions"],
        "clicks": ["clicks"],
        "conversions": ["conversions", "leads"],
        "spend": ["total spent", "spend"],
        "revenue": ["conversion value"],
        "currency": ["currency"],
    },
    signature={"start date (in utc)": 3.0, "total spent": 3.0, "campaign name": 1.0, "campaign group name": 2.0,
               "impressions": 0.5, "clicks": 0.5, "average ctr": 1.0, "average cpc": 1.0},
    threshold=5.0,
)

AMAZON = FormatSpec(
    name="amazon_ads",
    channel=Channel.amazon,
    synonyms={
        "day": ["date", "day", "start date"],
        "campaign_name": ["campaign name", "campaigns", "campaign"],
        "external_id": ["campaign id"],
        "impressions": ["impressions"],
        "clicks": ["clicks"],
        "conversions": ["7 day total orders (#)", "14 day total orders (#)", "orders", "conversions"],
        "spend": ["spend", "cost"],
        "revenue": ["7 day total sales", "14 day total sales", "sales", "revenue"],
        "currency": ["currency"],
    },
    signature={"7 day total sales": 3.0, "7 day total orders (#)": 3.0, "14 day total sales": 3.0,
               "total advertising cost of sales (acos)": 2.0, "total return on advertising spend (roas)": 2.0,
               "portfolio name": 1.0, "spend": 1.0, "campaign name": 1.0, "targeting": 0.5},
    threshold=5.0,
)

GENERIC = FormatSpec(
    name="generic",
    channel=None,
    synonyms={
        "day": ["day", "date", "dt"],
        "campaign_name": ["campaign", "campaign_name", "campaign name", "name"],
        "external_id": ["external_id", "campaign_id", "campaign id", "id"],
        "channel": ["channel", "platform", "source", "network"],
        "impressions": ["impressions", "impr", "views"],
        "clicks": ["clicks"],
        "conversions": ["conversions", "orders", "purchases", "leads"],
        "spend": ["spend", "cost", "amount_spent", "amount spent", "ad_spend"],
        "revenue": ["revenue", "sales", "conversion_value", "conversion value"],
        "currency": ["currency"],
    },
    signature={"spend": 1.0, "channel": 1.0, "campaign": 1.0, "day": 1.0, "revenue": 0.5},
    threshold=0.0,
)

FORMATS = {f.name: f for f in (GOOGLE, META, LINKEDIN, AMAZON, GENERIC)}

CHANNEL_ALIASES = {
    "google": Channel.google, "google ads": Channel.google, "adwords": Channel.google, "google adwords": Channel.google,
    "youtube": Channel.google, "search": Channel.google, "gads": Channel.google,
    "meta": Channel.meta, "facebook": Channel.meta, "facebook ads": Channel.meta, "meta ads": Channel.meta,
    "instagram": Channel.meta, "fb": Channel.meta, "ig": Channel.meta,
    "amazon": Channel.amazon, "amazon ads": Channel.amazon, "sponsored products": Channel.amazon,
    "linkedin": Channel.linkedin, "linkedin ads": Channel.linkedin,
}


def parse_channel(value: str | None) -> Channel | None:
    if not value:
        return None
    v = _norm(value)
    if v in CHANNELS:
        return Channel(v)
    return CHANNEL_ALIASES.get(v)


# ---------------------------------------------------------------- decoding / header detection
HEADER_TOKENS = {"campaign", "campaign name", "day", "date", "cost", "spend", "impressions", "impr.", "clicks",
                 "conversions", "results", "link clicks", "reporting starts", "channel", "revenue", "total spent"}


def decode(raw: bytes) -> str:
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def sniff_delimiter(sample: str) -> str:
    counts = {d: sample.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def find_header(lines: list[list[str]]) -> int:
    """Index of the header row: first row (within the first 25) that contains >= 2 known header tokens."""
    for i, row in enumerate(lines[:25]):
        cells = {_norm(c) for c in row if c}
        hits = sum(1 for c in cells if c in HEADER_TOKENS or _AMOUNT_SPENT.match(c) or c.startswith("cost ("))
        if hits >= 2 and len(cells) >= 3:
            return i
    return -1


# ---------------------------------------------------------------- format detection
def _sig_hits(spec: FormatSpec, headers: list[str]) -> float:
    score = 0.0
    for pat, w in spec.signature.items():
        if isinstance(pat, str):
            if pat in headers:
                score += w
        elif any(pat.match(h) for h in headers):
            score += w
    return score


def detect_format(headers: list[str]) -> tuple[str, float]:
    scored = []
    for spec in (GOOGLE, META, LINKEDIN, AMAZON):
        s = _sig_hits(spec, headers)
        total = sum(spec.signature.values())
        scored.append((s, s / total, spec))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_s, _best_ratio, best = scored[0]
    if best_s >= best.threshold:
        runner = scored[1][0]
        confidence = min(0.99, 0.6 + 0.4 * (best_s - runner) / max(best_s, 1))
        return best.name, round(confidence, 2)
    gen = _sig_hits(GENERIC, headers)
    return "generic", round(min(0.9, 0.3 + 0.15 * gen), 2)


def build_mapping(spec: FormatSpec, headers: list[str]) -> tuple[dict[str, str | None], str | None]:
    """Map our fields to original header names. Returns (mapping, currency-from-header)."""
    norm_to_orig = {}
    for h in headers:
        norm_to_orig.setdefault(_norm(h), h)
    mapping: dict[str, str | None] = {f: None for f in (*FIELDS, "currency")}
    currency = None
    for fld, syns in spec.synonyms.items():
        for syn in syns:
            if isinstance(syn, str):
                if syn in norm_to_orig:
                    mapping[fld] = norm_to_orig[syn]
                    break
            else:
                for n, orig in norm_to_orig.items():
                    m = syn.match(n)
                    if m:
                        mapping[fld] = orig
                        if "cur" in m.groupdict() and m.group("cur"):
                            currency = m.group("cur").upper()
                        break
                if mapping[fld]:
                    break
    # avoid mapping the same source column to two fields (e.g. 'campaign' as name and id)
    if mapping["external_id"] and mapping["external_id"] == mapping["campaign_name"]:
        mapping["external_id"] = None
    return mapping, currency


# ---------------------------------------------------------------- value parsing
_NUM_CLEAN = re.compile(r"[^0-9,.\-]")


def parse_number(raw: str | None, european: bool = False) -> Decimal | None:
    if raw is None:
        return None
    s = raw.strip()
    if s in ("", "--", "-", "n/a", "N/A", "NA", "null", "None"):
        return Decimal(0) if s in ("--", "-") else None
    s = _NUM_CLEAN.sub("", s.replace("\u00a0", ""))
    if not s:
        return None
    if european or ("," in s and "." not in s and re.search(r",\d{1,2}$", s)):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d %b %Y", "%b %d, %Y", "%B %d, %Y", "%d %B %Y",
                "%d-%b-%Y", "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")
_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$")


def infer_day_first(values: list[str]) -> bool:
    """For ambiguous d/m/y vs m/d/y columns: day-first if any first component exceeds 12."""
    for v in values:
        m = _SLASH.match(v.strip())
        if m and int(m.group(1)) > 12:
            return True
        if m and int(m.group(2)) > 12:
            return False
    return False


def parse_day(raw: str | None, day_first: bool = False) -> date | None:
    if not raw:
        return None
    s = raw.strip().strip('"')
    if not s:
        return None
    m = _SLASH.match(s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        d, mo = (a, b) if day_first else (b, a)
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s[: len(s)], fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------- main entry
@dataclass
class ParsedCSV:
    detected_format: str
    confidence: float
    channel: Channel | None
    currency: str | None
    delimiter: str
    mapping: dict[str, str | None]
    source_columns: list[str]
    unmapped_columns: list[str]
    rows: list[dict]
    skipped_rows: int
    warnings: list[str] = field(default_factory=list)


TOTAL_ROW = re.compile(r"^total\b", re.I)


def parse_csv(
    raw: bytes,
    *,
    format_override: str | None = None,
    channel_override: Channel | None = None,
) -> ParsedCSV:
    text = decode(raw)
    if not text.strip():
        raise ValueError("empty file")
    delimiter = sniff_delimiter("\n".join(text.splitlines()[:30]))
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    lines = [row for row in reader]
    h_idx = find_header(lines)
    if h_idx < 0:
        raise ValueError("could not find a header row (expected columns like Campaign, Day, Cost/Spend, Clicks)")
    headers = [h.replace("\ufeff", "").strip() for h in lines[h_idx]]
    norm_headers = [_norm(h) for h in headers]

    if format_override and format_override not in FORMATS:
        raise ValueError(f"unknown format '{format_override}'")
    fmt_name, confidence = (format_override, 1.0) if format_override else detect_format(norm_headers)
    spec = FORMATS[fmt_name]
    mapping, currency = build_mapping(spec, headers)
    if not mapping["currency"] and fmt_name != "generic" and currency is None:
        pass
    warnings: list[str] = []

    if not mapping["day"]:
        raise ValueError("no date column detected (expected 'Day' / 'Date' / 'Reporting starts')")
    if not mapping["campaign_name"] and not mapping["external_id"]:
        raise ValueError("no campaign column detected (expected 'Campaign' / 'Campaign name')")
    if not mapping["spend"]:
        warnings.append("No spend/cost column detected; spend set to 0")
    for fld, label in (("revenue", "revenue"), ("conversions", "conversions"), ("impressions", "impressions"),
                       ("clicks", "clicks")):
        if not mapping[fld]:
            warnings.append(f"No {label} column detected; {label} set to 0")

    default_channel = channel_override or spec.channel
    if fmt_name == "generic" and not mapping["channel"] and not channel_override:
        default_channel = Channel.other
        warnings.append("No channel column; rows imported as channel 'other' (pass channel=<google|meta|...> to override)")

    col_idx = {h: i for i, h in enumerate(headers)}

    def cell(row: list[str], fld: str) -> str | None:
        src = mapping.get(fld)
        if not src:
            return None
        i = col_idx.get(src)
        return row[i] if i is not None and i < len(row) else None

    data_rows = lines[h_idx + 1 :]
    day_first = infer_day_first([cell(r, "day") or "" for r in data_rows[:200]])
    european = delimiter == ";"

    rows: list[dict] = []
    skipped = 0
    unknown_channels: set[str] = set()
    for n, row in enumerate(data_rows, start=h_idx + 2):
        if not any(c.strip() for c in row):
            skipped += 1
            continue
        first = (row[0] or "").strip()
        if TOTAL_ROW.match(first) or TOTAL_ROW.match((cell(row, "campaign_name") or "")):
            skipped += 1
            continue
        day = parse_day(cell(row, "day"), day_first)
        if day is None:
            skipped += 1
            if len(warnings) < 25:
                warnings.append(f"Row {n}: unparseable day {cell(row, 'day')!r} - skipped")
            continue
        name = (cell(row, "campaign_name") or "").strip()
        ext = (cell(row, "external_id") or "").strip()
        if not name and not ext:
            skipped += 1
            continue
        ch = default_channel
        if mapping["channel"]:
            parsed = parse_channel(cell(row, "channel"))
            if parsed is None:
                unknown_channels.add((cell(row, "channel") or "").strip())
                ch = channel_override or Channel.other
            else:
                ch = parsed
        nums = {}
        for fld in ("impressions", "clicks", "conversions", "spend", "revenue"):
            v = parse_number(cell(row, fld), european) if mapping[fld] else None
            nums[fld] = v if v is not None and v >= 0 else Decimal(0)
        rows.append(
            {
                "day": day,
                "channel": ch or Channel.other,
                "external_id": (ext or slugify(name, 100))[:100],
                "campaign_name": (name or ext)[:200],
                "impressions": int(nums["impressions"]),
                "clicks": int(nums["clicks"]),
                "conversions": int(round(nums["conversions"])),
                "spend": nums["spend"].quantize(Decimal("0.0001")),
                "revenue": nums["revenue"].quantize(Decimal("0.0001")),
            }
        )
    if unknown_channels:
        warnings.append(f"Unknown channel values mapped to 'other': {sorted(unknown_channels)[:5]}")
    if not rows:
        raise ValueError("no data rows could be parsed")
    if fmt_name == "google_ads" and mapping["currency"]:
        cur_vals = {(cell(r, "currency") or "").strip().upper() for r in data_rows}
        cur_vals.discard("")
        currency = sorted(cur_vals)[0] if cur_vals else currency
    dup = len(rows) - len({(r["channel"], r["external_id"], r["day"]) for r in rows})
    if dup:
        warnings.append(f"{dup} rows share a campaign+day (segmented export?) and will be summed")

    mapped_cols = {v for v in mapping.values() if v}
    unmapped = [h for h in headers if h and h not in mapped_cols]
    return ParsedCSV(
        detected_format=fmt_name,
        confidence=confidence,
        channel=default_channel if not mapping["channel"] else None,
        currency=currency,
        delimiter=delimiter,
        mapping={k: mapping[k] for k in FIELDS},
        source_columns=headers,
        unmapped_columns=unmapped,
        rows=rows,
        skipped_rows=skipped,
        warnings=warnings,
    )
