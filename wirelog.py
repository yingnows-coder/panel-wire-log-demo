"""Validation, CSV exchange, and transactional SQLite persistence."""
import csv
import io
import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

LEGACY_FIELDS = [
    "線號", "迴路／用途", "起點設備", "起點端子", "終點設備", "終點端子",
    "線材型號", "線徑（mm²）", "線色", "長度（m）", "起點端末", "終點端末",
    "電纜編號", "芯線編號", "配線狀態", "查驗結果", "備註",
]
STRUCTURES = ["單芯線", "多芯電纜", "雙絞電纜"]
IDENTIFIERS = ["顏色", "印字號碼", "號碼＋顏色"]
CONNECTORS = ["無", "端子台", "軍規接頭", "動力接頭", "其他接頭"]
TERMINATIONS = ["未指定", "鎖附", "壓接", "焊接", "直接插接", "其他"]
CONTACTS = ["未指定", "針（Pin）", "孔（Socket）", "其他"]
ENDS = ["起點", "終點"]
CORE_FIELDS = ["線號", "迴路／用途", "電纜編號", "線材結構", "電纜總芯數", "線材型號",
               "線徑（mm²）", "長度（cm）", "浪管規格", "浪管長度（cm）", "芯線識別方式", "芯線編號", "線色",
               "對絞組號", "對內芯別"]
END_SUFFIXES = ["設備", "端子", "號碼圈", "導體剝皮（mm）", "外被剝除（mm）", "接頭類型", "接頭代號",
                "接頭型號", "接點形式", "接點料號", "端接方式", "端末", "熱縮套管", "屏蔽／接地處理",
                "尾夾／拉力固定", "作業圖號／規範", "加工要求"]
END_FIELDS = {end: [end + suffix for suffix in END_SUFFIXES] for end in ENDS}
FIELDS = CORE_FIELDS + END_FIELDS["起點"] + END_FIELDS["終點"] + ["配線狀態", "查驗結果", "備註"]
V2_FIELDS = FIELDS[:FIELDS.index("芯線識別方式")] + ["外被顏色"] + FIELDS[FIELDS.index("芯線識別方式"):]
OPTIONAL_NUMBERS = [end + suffix for end in ENDS for suffix in ["導體剝皮（mm）", "外被剝除（mm）"]] + ["浪管長度（cm）"]
NUMBERS = ["線徑（mm²）", "長度（cm）", "電纜總芯數"] + OPTIONAL_NUMBERS
REQUIRED = ["線號", "起點設備", "終點設備", "線材型號"]
STATES = ["未配線", "已配線", "待修改", "完成"]
CHECKS = ["待查驗", "合格", "待改善"]
META = ["機型", "位置", "圖面版次", "施工日期", "配線人員", "查驗人員"]
SHARED_FIELDS = ["線材結構", "電纜總芯數", "浪管規格", "浪管長度（cm）"]
SETTINGS_FIELDS = ["電纜編號"] + SHARED_FIELDS


class ConflictError(ValueError):
    pass


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def normalize_meta(source):
    result = {key: clean(source.get(key)) for key in META}
    if "機型" not in source:
        result["機型"] = clean(source.get("案場名稱"))
    if "位置" not in source:
        result["位置"] = clean(source.get("圖號"))
    return result


def cable_settings(rows):
    settings = {}
    for source in rows:
        row = normalize(source)
        cable = clean(row["電纜編號"]) or clean(row["線號"])
        if cable:
            settings.setdefault(cable.casefold(), {"電纜編號": cable,
                "線材結構": row["線材結構"],
                "電纜總芯數": row["電纜總芯數"] or (1 if row["線材結構"] == "單芯線" else 2),
                "浪管規格": row["浪管規格"], "浪管長度（cm）": row["浪管長度（cm）"]})
    return list(settings.values())


def resize_cables(rows, settings):
    """Synchronize per-cable counts and append blank cores; never discard existing work."""
    output = [normalize(row) for row in rows if any(clean(value) for value in row.values())]
    used_lines = {clean(row["線號"]).casefold() for row in output}
    known = set()
    for setting in settings:
        if not any(clean(value) for value in setting.values()):
            continue
        cable = clean(setting.get("電纜編號"))
        if not cable:
            raise ValueError("電纜共用設定：請填寫電纜編號。")
        if cable.casefold() in known:
            raise ValueError(f"電纜 {cable} 的共用設定重複，請只保留一格芯數。")
        known.add(cable.casefold())
        structure = clean(setting.get("線材結構")) or "多芯電纜"
        minimum = 1 if structure == "單芯線" else 2
        try:
            count = float(setting.get("電纜總芯數"))
            if not math.isfinite(count) or not count.is_integer() or count < minimum or (structure == "單芯線" and count != 1):
                raise ValueError
            count = int(count)
        except (TypeError, ValueError):
            raise ValueError(f"線材 {cable}：單芯線芯數為 1，多芯／雙絞電纜芯數必須是至少 2 的整數。") from None
        if structure not in STRUCTURES:
            raise ValueError(f"線材 {cable} 請選擇有效的線材結構。")
        members = [row for row in output if (clean(row["電纜編號"]) or clean(row["線號"])).casefold() == cable.casefold()]
        if len(members) > count:
            raise ValueError(f"電纜 {cable} 已有 {len(members)} 芯。請先刪除多餘芯線，再調低總芯數，避免遺失紀錄。")
        conduit = clean(setting.get("浪管規格", members[0]["浪管規格"] if members else ""))
        conduit_length = setting.get("浪管長度（cm）", members[0]["浪管長度（cm）"] if members else None)
        if clean(conduit_length):
            try:
                conduit_length = float(conduit_length)
                if not math.isfinite(conduit_length) or conduit_length < 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError(f"線材 {cable} 的浪管長度必須為非負數（cm）。") from None
        else:
            conduit_length = None
        for row in members:
            row.update({"電纜總芯數": count, "線材結構": structure, "浪管規格": conduit,
                        "浪管長度（cm）": conduit_length, "電纜編號": "" if structure == "單芯線" else cable})
        shared = {field: members[0][field] for field in ["迴路／用途", "線材型號", "線徑（mm²）", "長度（cm）", "浪管規格", "浪管長度（cm）"]} if members else {}
        used_cores = {clean(row["芯線編號"]).casefold() for row in members}
        used_pairs = {(clean(row["對絞組號"]).casefold(), clean(row["對內芯別"])) for row in members}
        next_line, next_core, next_pair = 1, 1, 0
        width = max([2] + [len(clean(row["芯線編號"])) for row in members if clean(row["芯線編號"]).isdigit()])
        for _ in range(count - len(members)):
            while f"w{next_line:03d}" in used_lines:
                next_line += 1
            while f"{next_core:0{width}d}".casefold() in used_cores:
                next_core += 1
            row = dict.fromkeys(FIELDS, "")
            row.update(shared)
            row.update({"線號": cable if structure == "單芯線" else f"W{next_line:03d}",
                        "電纜編號": "" if structure == "單芯線" else cable, "電纜總芯數": count,
                        "線材結構": structure, "芯線識別方式": "印字號碼", "芯線編號": f"{next_core:0{width}d}",
                        "浪管規格": conduit, "浪管長度（cm）": conduit_length,
                        "配線狀態": STATES[0], "查驗結果": CHECKS[0]})
            if row["線號"].casefold() in used_lines:
                raise ValueError(f"線號 {row['線號']} 已存在，請使用不同的線材編號。")
            if structure == "雙絞電纜":
                while (f"p{next_pair // 2 + 1:02d}", "AB"[next_pair % 2]) in used_pairs:
                    next_pair += 1
                row["對絞組號"], row["對內芯別"] = f"P{next_pair // 2 + 1:02d}", "AB"[next_pair % 2]
                used_pairs.add((row["對絞組號"].casefold(), row["對內芯別"]))
            output.append(normalize(row))
            used_lines.add(row["線號"].casefold())
            used_cores.add(row["芯線編號"].casefold())
    missing = {clean(row["電纜編號"]) or clean(row["線號"]) for row in output
               if (clean(row["電纜編號"]) or clean(row["線號"])).casefold() not in known}
    if missing:
        raise ValueError("請在電纜共用設定補上：" + "、".join(sorted(missing)))
    return output


def normalize(source):
    """Fill new fields for historical rows without changing stored data or audit history."""
    row = {field: source.get(field, "") for field in FIELDS}
    # v1 used metres. Convert on read; audit snapshots remain in their original schema.
    for old, new, factor in [("長度（m）", "長度（cm）", 100), ("浪管長度（m）", "浪管長度（cm）", 100)]:
        if new not in source and clean(source.get(old)):
            try:
                row[new] = float(source[old]) * factor
            except (TypeError, ValueError):
                row[new] = source[old]  # Preserve malformed values for validation to report.
    row["線材結構"] = clean(row["線材結構"]) or ("多芯電纜" if clean(row["電纜編號"]) else "單芯線")
    row["芯線識別方式"] = clean(row["芯線識別方式"]) or (
        "號碼＋顏色" if clean(row["芯線編號"]) and clean(row["線色"]) else
        "印字號碼" if clean(row["芯線編號"]) else "顏色")
    for end in ENDS:
        for suffix, default in [("接頭類型", "無"), ("端接方式", "未指定"), ("接點形式", "未指定")]:
            row[end + suffix] = clean(row[end + suffix]) or default
    return row


def validate(rows):
    """Return canonical rows or raise a readable error. Never silently drop bad rows."""
    output, errors, seen, cables, cores, pairs = [], [], set(), {}, set(), set()
    for index, source in enumerate(rows, 1):
        if not any(clean(value) for value in source.values()):
            continue
        row = {field: clean(value) for field, value in normalize(source).items()}
        for field in REQUIRED:
            if not row[field]:
                errors.append(f"第 {index} 列：請填寫{field}")
        code = row["線號"].casefold()
        if code and code in seen:
            errors.append(f"第 {index} 列：線號 {row['線號']} 重複（同一盤內不可重複）")
        seen.add(code)
        if row["線材結構"] not in STRUCTURES:
            errors.append(f"第 {index} 列：線材結構不在選單內")
        mode = row["芯線識別方式"]
        if mode not in IDENTIFIERS:
            errors.append(f"第 {index} 列：芯線識別方式不在選單內")
        if mode in ["顏色", "號碼＋顏色"] and not row["線色"]:
            errors.append(f"第 {index} 列：請填寫線色（可填白／藍等底色與條紋）")
        if mode in ["印字號碼", "號碼＋顏色"] and not row["芯線編號"]:
            errors.append(f"第 {index} 列：請填寫線上印字的芯線編號")
        for field in ["線徑（mm²）", "長度（cm）"]:
            try:
                value = float(row[field])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError
                row[field] = value
            except (TypeError, ValueError):
                errors.append(f"第 {index} 列：{field}必須為大於 0 的數字")
        for field in OPTIONAL_NUMBERS + ["電纜總芯數"]:
            if not row[field]:
                row[field] = None
                continue
            try:
                value = float(row[field])
                if not math.isfinite(value) or value < 0:
                    raise ValueError
                if field == "電纜總芯數":
                    if not value.is_integer() or value < 1:
                        raise ValueError
                    value = int(value)
                row[field] = value
            except (TypeError, ValueError):
                errors.append(f"第 {index} 列：{field}必須為{'正整數' if field == '電纜總芯數' else '大於或等於 0 的數字'}")
        cable = row["電纜編號"].casefold()
        if row["線材結構"] != "單芯線":
            if not cable:
                errors.append(f"第 {index} 列：多芯／雙絞電纜請填寫電纜編號")
            count = row["電纜總芯數"]
            if not isinstance(count, int) or count < 2:
                errors.append(f"第 {index} 列：多芯／雙絞電纜總芯數至少為 2；舊資料請補填")
        elif cable:
            errors.append(f"第 {index} 列：有電纜編號時請選擇多芯或雙絞電纜")
        if row["線材結構"] == "雙絞電纜":
            if not row["對絞組號"] or row["對內芯別"] not in ["A", "B"]:
                errors.append(f"第 {index} 列：雙絞電纜請填對絞組號及對內芯別 A／B")
            pair_key = (cable, row["對絞組號"].casefold(), row["對內芯別"])
            if cable and pair_key in pairs:
                errors.append(f"第 {index} 列：同一電纜的對絞組號／對內芯別重複")
            pairs.add(pair_key)
        elif row["對絞組號"] or row["對內芯別"]:
            errors.append(f"第 {index} 列：有對絞資訊時請選擇雙絞電纜")
        if cable:
            identity = (row["芯線編號"].casefold() if mode == "印字號碼" else
                        row["線色"].casefold() if mode == "顏色" else
                        (row["芯線編號"].casefold(), row["線色"].casefold()))
            core_key = (cable, row["對絞組號"].casefold(), identity)
            if identity and core_key in cores:
                errors.append(f"第 {index} 列：同一電纜／對絞組內的芯線識別重複")
            cores.add(core_key)
            cables.setdefault(cable, []).append(row)
        for end in ENDS:
            for suffix, options in [("接頭類型", CONNECTORS), ("端接方式", TERMINATIONS), ("接點形式", CONTACTS)]:
                if row[end + suffix] not in options:
                    errors.append(f"第 {index} 列：{end}{suffix}不在選單內")
            if row[end + "接頭類型"] in ["軍規接頭", "動力接頭", "其他接頭"]:
                for suffix in ["端子", "接頭代號", "接頭型號"]:
                    if not row[end + suffix]:
                        errors.append(f"第 {index} 列：請填寫{end}{suffix}")
                if row[end + "端接方式"] == "未指定":
                    errors.append(f"第 {index} 列：請指定{end}端接方式（焊接或壓接等）")
        row["配線狀態"] = row["配線狀態"] or STATES[0]
        row["查驗結果"] = row["查驗結果"] or CHECKS[0]
        if row["配線狀態"] not in STATES:
            errors.append(f"第 {index} 列：配線狀態不在選單內")
        if row["查驗結果"] not in CHECKS:
            errors.append(f"第 {index} 列：查驗結果不在選單內")
        output.append(row)
    for cable, members in cables.items():
        for field in ["線材結構", "線材型號", "電纜總芯數", "長度（cm）", "浪管規格", "浪管長度（cm）"] + [end + "外被剝除（mm）" for end in ENDS]:
            values = {row[field] for row in members if row[field] is not None and row[field] != ""}
            if len(values) > 1:
                errors.append(f"電纜 {members[0]['電纜編號']}：各芯的{field}不一致")
        count = members[0]["電纜總芯數"]
        if isinstance(count, int) and len(members) > count:
            errors.append(f"電纜 {members[0]['電纜編號']}：已記錄芯數超過電纜總芯數")
    if errors:
        raise ValueError("\n".join(errors))
    return output


def csv_bytes(rows, protect_formulas=True):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    for row in rows:
        safe = {}
        for key in FIELDS:
            value = row.get(key, "")
            if protect_formulas and isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return buffer.getvalue().encode("utf-8-sig")


def read_csv(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("請將 CSV 另存為 UTF-8 編碼後再匯入。") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames not in [FIELDS, LEGACY_FIELDS, V2_FIELDS]:
        raise ValueError("CSV 欄位或順序不符，請下載範本後填寫。")
    rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError("CSV 有超出欄位數的資料，請檢查分隔符號。")
    return validate(rows)


def material_items(rows):
    """Each cable is one physical item, irrespective of the number of recorded cores."""
    groups = {}
    for source in rows:
        row = normalize(source)
        cable = clean(row["電纜編號"])
        key = ("電纜", cable.casefold()) if cable else ("單芯", row["線號"].casefold())
        groups.setdefault(key, []).append(row)
    result = []
    for members in groups.values():
        first = members[0]
        result.append({"線材結構": first["線材結構"], "線材型號": first["線材型號"],
                       "電纜總芯數": first["電纜總芯數"],
                       "芯線線徑（mm²）": "／".join(sorted({str(row['線徑（mm²）']) for row in members})),
                       "顏色": "" if first["電纜編號"] else first["線色"],
                       "數量": 1, "總長度（cm）": float(first["長度（cm）"])})
    return result


def cable_overview(rows):
    groups = {}
    for source in rows:
        row = normalize(source)
        if clean(row["電纜編號"]):
            groups.setdefault(row["電纜編號"].casefold(), []).append(row)
    return [{"電纜編號": group[0]["電纜編號"], "線材結構": group[0]["線材結構"],
             "已記錄芯數": len(group), "電纜總芯數": group[0]["電纜總芯數"] or "待補填",
             "對絞組數": len({row["對絞組號"] for row in group if row["對絞組號"]}),
             "待補對絞組": "、".join(sorted({row["對絞組號"] for row in group if row["對絞組號"] and
                 {r["對內芯別"] for r in group if r["對絞組號"] == row["對絞組號"]} != {"A", "B"}}))}
            for group in groups.values()]


def sample_rows():
    row = dict.fromkeys(FIELDS, "")
    row.update({"線號": "W001", "迴路／用途": "控制訊號（示例）", "起點設備": "S1",
                "起點端子": "14", "終點設備": "KM1", "終點端子": "A1",
                "線材型號": "示例型號", "線徑（mm²）": 1.25, "線色": "黑",
                "長度（cm）": 120, "配線狀態": "未配線", "查驗結果": "待查驗",
                "備註": "僅示範格式，實際規格依核定圖面填寫"})
    return [row]


def assembly_rows():
    """Illustrative routing only; stripping/process values are intentionally unspecified."""
    rows = []
    for index, color in enumerate(["白／藍", "藍", "白／橘", "橘"], 1):
        row = sample_rows()[0]
        row.update({"線號": f"W{index:03d}", "電纜編號": "CBL-001", "線材結構": "雙絞電纜", "電纜總芯數": 4,
                    "線材型號": "示例：2P 雙絞電纜", "長度（cm）": 310, "浪管規格": '3/4"', "浪管長度（cm）": 250,
                    "線徑（mm²）": 0.5, "芯線識別方式": "號碼＋顏色", "芯線編號": f"{index:02d}", "線色": color,
                    "對絞組號": f"P{(index + 1) // 2:02d}", "對內芯別": "A" if index % 2 else "B",
                    "起點設備": "J1", "起點端子": "ABCD"[index - 1], "起點接頭類型": "軍規接頭",
                    "起點接頭代號": "J1", "起點接頭型號": "示例型號（請換為實際料號）", "起點端接方式": "焊接",
                    "起點號碼圈": f"X{index:02d}", "終點號碼圈": f"U{index:02d}", "終點設備": "P1", "終點端子": str(index),
                    "終點接頭類型": "動力接頭", "終點接頭代號": "P1", "終點接頭型號": "示例型號（請換為實際料號）",
                    "終點端接方式": "壓接", "備註": "僅示範欄位；實際剝皮、接點及端接要求依作業圖面填入"})
        rows.append(row)
    return rows


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS panels (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                    meta TEXT NOT NULL, wires TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY, panel_id INTEGER NOT NULL,
                    time TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
                    before_json TEXT NOT NULL, after_json TEXT NOT NULL,
                    FOREIGN KEY(panel_id) REFERENCES panels(id));
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def panels(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT id,name FROM panels ORDER BY id")]

    def create(self, name):
        name = clean(name)
        if not name:
            raise ValueError("請輸入盤體名稱／編號。")
        with self.connection() as db:
            try:
                cursor = db.execute("INSERT INTO panels(name,meta,wires,updated) VALUES(?,?,?,?)",
                                    (name, "{}", "[]", now()))
            except sqlite3.IntegrityError as exc:
                raise ValueError("此盤體名稱／編號已存在。") from exc
            return cursor.lastrowid

    def load(self, panel_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM panels WHERE id=?", (panel_id,)).fetchone()
        if row is None:
            raise ValueError("找不到此配電盤。")
        result = dict(row)
        result["meta"] = normalize_meta(json.loads(result["meta"]))
        result["wires"] = json.loads(result["wires"])
        return result

    def save(self, panel_id, version, meta, rows, actor, reason):
        rows = validate(rows)
        meta = normalize_meta(meta)
        actor, reason = clean(actor), clean(reason)
        if not actor or not reason:
            raise ValueError("請填寫紀錄人員及本次修改說明。")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT * FROM panels WHERE id=?", (panel_id,)).fetchone()
            if current is None or current["version"] != version:
                raise ConflictError("此配電盤已被其他視窗更新。請先匯出未儲存內容，再按「重新載入」核對。")
            before = {"meta": json.loads(current["meta"]), "wires": json.loads(current["wires"])}
            after = {"meta": meta, "wires": rows}
            if before == after:
                return False
            stamp = now()
            db.execute("UPDATE panels SET meta=?,wires=?,version=version+1,updated=? WHERE id=?",
                       (json.dumps(meta, ensure_ascii=False), json.dumps(rows, ensure_ascii=False), stamp, panel_id))
            db.execute("INSERT INTO history(panel_id,time,actor,reason,before_json,after_json) VALUES(?,?,?,?,?,?)",
                       (panel_id, stamp, actor, reason, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))
        return True

    def history(self, panel_id):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM history WHERE panel_id=? ORDER BY id DESC", (panel_id,))]
