"""Standalone printable fabrication sheet. All user strings are HTML-escaped."""
from html import escape
from wirelog import normalize, normalize_meta, clean
from palette import color_background


def display(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def connector(row, end):
    kind = row[end + "接頭類型"]
    parts = ([kind] if kind != "無" else []) + [row[end + key] for key in
        ["接頭代號", "接頭型號", "接點形式", "接點料號", "端接方式"] if
        row[end + key] not in ["", "未指定"]]
    return "\n".join(parts)


def fabrication_html(rows, panel_name, meta):
    meta = normalize_meta(meta)
    groups = {}
    for source in rows:
        row = normalize(source)
        key = ("電纜", clean(row["電纜編號"]).casefold()) if clean(row["電纜編號"]) else ("線", row["線號"])
        groups.setdefault(key, []).append(row)
    output = ['''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>配電盤線材製作單</title><style>
body{font-family:"Microsoft JhengHei",sans-serif;color:#172b4d;margin:22px;background:white}
h1{font-size:23px}h2{font-size:17px;margin:24px 0 8px}p{font-size:12px;line-height:1.7}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:1400px;font-size:12px}
th,td{border:1px solid #384452;text-align:center;padding:7px 5px;vertical-align:middle;white-space:pre-line}
th{background:#edf4f6;font-weight:600}.notes{min-width:0;font-size:11px;margin:10px 0 24px}.notes td{text-align:left}
small{font-size:11px;color:#52647a}.empty{padding:30px;border:1px dashed #bac4d0}
@page{size:A3 landscape;margin:10mm}@media print{body{margin:0;font-size:10pt}.scroll{overflow:visible}
table{min-width:0;table-layout:fixed;font-size:8pt;overflow-wrap:anywhere}th,td{padding:4px 2px}
thead{display:table-header-group}tr{break-inside:avoid}h2{break-after:avoid}*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
</style></head><body>''']
    output.append(f"<h1>{escape(str(panel_name))}｜線材製作單</h1>")
    output.append("<p>" + "　".join(f"{escape(key)}：{escape(display(value))}" for key, value in meta.items()) + "</p>")
    output.append("<p>單位：線材、浪管長度為 cm；導體剝皮、外被剝除為 mm。空白／— 表示尚未指定，0 表示不剝除／不用。<br>芯線編號是線上印字；號碼圈為另外套印的兩端標識。接頭內容為紀錄資料，請依作業圖面核對。</p>")
    headers = ["線號", "起點導體剝皮\nmm", "起點外被剝除\nmm", "起點端子", "起點接頭", "線材規格",
               "線材長度\ncm", "浪管規格", "浪管長度\ncm", "顏色", "芯線印字", "對絞組／芯別",
               "起點號碼圈", "終點號碼圈", "終點導體剝皮\nmm", "終點外被剝除\nmm", "終點端子", "終點接頭"]
    if not groups:
        output.append('<p class="empty">尚無已儲存線材，請先新增並儲存紀錄。</p>')
    for members in groups.values():
        first = members[0]
        name = first["電纜編號"] or first["線號"]
        output.append(f"<h2>{escape(name)} · {escape(first['線材結構'])} · 已記錄 {len(members)} 芯／總芯數 {escape(display(first['電纜總芯數']))}</h2>")
        cells = []
        for row in members:
            spec = row["線材型號"] + f"\n芯線 {display(row['線徑（mm²）'])} mm²"
            pair = "/".join(value for value in [row["對絞組號"], row["對內芯別"]] if value)
            cells.append([row["線號"], row["起點導體剝皮（mm）"], row["起點外被剝除（mm）"], row["起點端末"], connector(row, "起點"),
                          spec, row["長度（cm）"], row["浪管規格"], row["浪管長度（cm）"], row["線色"], row["芯線編號"], pair,
                          row["起點號碼圈"], row["終點號碼圈"], row["終點導體剝皮（mm）"], row["終點外被剝除（mm）"], row["終點端末"], connector(row, "終點")])
        output.append('<div class="scroll"><table><thead><tr>' + "".join(f"<th>{escape(head)}</th>" for head in headers) + '</tr></thead><tbody>')
        for index, values in enumerate(cells):
            output.append("<tr>")
            for col, value in enumerate(values):
                merge = col not in [0, 9, 10, 11]
                if merge and index > 0 and cells[index - 1][col] == value:
                    continue
                span = 1
                if merge:
                    while index + span < len(cells) and cells[index + span][col] == value:
                        span += 1
                color = color_background(clean(value)) if col == 9 else ""
                style = f' style="background:{color}"' if color else ""
                label = escape(display(value))
                if color:
                    label = f'<span style="background:#ffffffeb;color:#172b4d;padding:1px 4px;border-radius:3px">{label}</span>'
                output.append(f'<td rowspan="{span}"{style}>{label}</td>')
            output.append("</tr>")
        output.append("</tbody></table></div>")
        output.append('<table class="notes"><thead><tr><th>線號</th><th>起點位置／加工要求</th><th>終點位置／加工要求</th><th>備註</th></tr></thead><tbody>')
        for row in members:
            details = []
            for end in ["起點", "終點"]:
                location = f"{display(row[end+'設備'])} → {display(row[end+'端子'])}"
                extra = "\n".join(f"{suffix}：{row[end+suffix]}" for suffix in ["熱縮套管", "屏蔽／接地處理", "尾夾／拉力固定", "作業圖號／規範", "加工要求"] if row[end + suffix])
                details.append(location + ("\n" + extra if extra else ""))
            output.append("<tr>" + "".join(f"<td>{escape(display(value))}</td>" for value in [row["線號"], *details, row["備註"]]) + "</tr>")
        output.append("</tbody></table>")
    output.append("<small>配電盤線材紀錄表 · 以已儲存紀錄產製</small></body></html>")
    return "".join(output)
