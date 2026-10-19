"""配電盤線材紀錄表 — run with streamlit run streamlit_app.py."""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from wirelog import (CHECKS, FIELDS, META, STATES, NUMBERS, ConflictError, Store,
                     csv_bytes, read_csv, sample_rows, assembly_rows, normalize,
                     normalize_meta, material_items, cable_overview)
from fabrication import fabrication_html
from sheet_editor import sheet_editor

st.set_page_config(page_title="配電盤線材紀錄表", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")
st.html("""<style>
[data-testid="stMain"] .block-container{padding:1.2rem 1.4rem 2rem;max-width:none}
h1{font-size:1.85rem!important;padding-top:0!important}
div[data-testid="stForm"]{border-color:#c9d5df}
</style>""")
demo_mode = True
if demo_mode:
    from demo_store import DemoStore
    if "_demo_store" not in st.session_state:
        st.session_state["_demo_store"] = DemoStore()
    store = st.session_state["_demo_store"]
else:
    store = Store(os.environ.get("WIRELOG_DB", str(Path(__file__).parent / "data" / "wirelog.db")))


def dataframe(rows):
    frame = pd.DataFrame([normalize(row) for row in rows], columns=FIELDS)
    for field in NUMBERS:
        frame[field] = pd.to_numeric(frame[field], errors="coerce").astype(float)
    for field in set(FIELDS) - set(NUMBERS):
        frame[field] = frame[field].fillna("").astype(str)
    return frame


def refresh(message):
    st.session_state.pop("snapshot", None)
    for key in list(st.session_state):
        if key.startswith(("draft_", "wires_", "cables_", "colors_", "meta_", "actor_", "reason_", "view_", "sheet_")):
            del st.session_state[key]
    st.session_state["notice"] = message
    st.rerun()


def show_error(error):
    for line in str(error).splitlines():
        st.error(line)


with st.sidebar:
    st.title("⚡ 線材紀錄")
    st.caption("每條線一筆，查修有依據。")
    if demo_mode:
        if st.button("重設展示資料"):
            st.session_state["_demo_store"] = DemoStore()
            st.session_state.pop("panel_id", None)
            refresh("已重設為示範資料。")
    with st.expander("新增配電盤", expanded=not store.panels()):
        with st.form("new_panel", clear_on_submit=True):
            panel_name = st.text_input("盤體名稱／編號", placeholder="例如：MCC-01", key="new_panel_name")
            if st.form_submit_button("建立配電盤", type="primary"):
                try:
                    new_id = store.create(panel_name)
                    st.session_state["panel_id"] = new_id
                    refresh("配電盤已建立，請填寫基本資料與線材明細。")
                except ValueError as error:
                    show_error(error)
panels = store.panels()
if not panels:
    st.title("配電盤線材紀錄表")
    st.info("從左側新增第一個配電盤，開始建立配線紀錄。")
    st.write("每條線記錄起終點、規格與查驗狀態，並可隨時查詢用料及修改紀錄。")
    st.stop()
with st.sidebar:
    names = {panel["id"]: panel["name"] for panel in panels}
    selected = st.selectbox("目前配電盤", list(names), format_func=names.get, key="panel_id")
    st.caption("切換配電盤前，請先儲存表單。")
    if st.button("重新載入", help="捨棄未儲存內容，取得最新資料"):
        refresh("已重新載入最新資料。")

if "snapshot" not in st.session_state or st.session_state.snapshot["id"] != selected:
    st.session_state.snapshot = store.load(selected)
snapshot = st.session_state.snapshot
snapshot["meta"] = normalize_meta(snapshot["meta"])
version = snapshot["version"]
prefix = f"{selected}_{version}"
rows = [normalize(row) for row in snapshot["wires"]]
frame = dataframe(rows)
physical_items = material_items(rows)

st.title("配電盤線材紀錄表")
if demo_mode:
    st.info("展示版｜僅使用示範資料。你可以自由試填，修改只保留於目前連線，不影響其他訪客；重新整理或連線結束後可能重設。請勿輸入正式工程或個人資料。")
st.caption(f"{snapshot['name']} · 版本 {version} · 最後更新 {snapshot['updated']}（UTC+8）")
if "notice" in st.session_state:
    st.success(st.session_state.pop("notice"))
st.caption(f"已儲存 {len(physical_items)} 條線材 · {len(rows)} 芯 · 長度 cm／剝皮 mm")

edit, search, totals, fabrication, history, exchange = st.tabs(["✎ 編輯紀錄", "⌕ 查詢", "▥ 用料統計", "▤ 製作單", "◷ 修改紀錄", "⇅ 匯入／匯出"])
with edit:
    st.caption("像 Excel 一樣填寫：選線材 → 左右端對照填寫 → 一次儲存。")
    draft_key = f"draft_{prefix}"
    draft = st.session_state.get(draft_key, {})
    with st.form(f"edit_{prefix}"):
        meta = {}
        columns = st.columns([1, 2, 1])
        for index, field in enumerate(META[:3]):
            value = draft.get("meta", snapshot["meta"]).get(field, "")
            if field == "機型":
                options = ["盤內", "盤外"]
                meta[field] = columns[index].selectbox(field, options,
                    index=options.index(value) if value in options else None,
                    placeholder="請選擇盤內／盤外", key=f"meta_{field}_{prefix}")
            else:
                meta[field] = columns[index].text_input(field, value, key=f"meta_{field}_{prefix}")
        prepared_rows = sheet_editor(draft.get("rows", rows), key=f"sheet_{prefix}")
        with st.expander("日期與施工／查驗人員"):
            columns = st.columns(3)
            for index, field in enumerate(META[3:]):
                meta[field] = columns[index].text_input(field, draft.get("meta", snapshot["meta"]).get(field, ""),
                    key=f"meta_{field}_{prefix}", placeholder="YYYY-MM-DD" if field == "施工日期" else None)
        a, b = st.columns([1, 2])
        actor = a.text_input("紀錄人員", draft.get("actor", ""), key=f"actor_{prefix}")
        reason = b.text_input("本次修改說明", draft.get("reason", ""), placeholder="例如：新增控制線、修正端子", key=f"reason_{prefix}")
        submitted = st.form_submit_button("儲存紀錄", type="primary", width="stretch")
    if submitted:
        st.session_state[draft_key] = {"rows": prepared_rows, "meta": meta, "actor": actor, "reason": reason}
        try:
            if meta["機型"] not in ["盤內", "盤外"]:
                raise ValueError("請選擇機型：盤內或盤外。")
            changed = store.save(selected, version, meta, prepared_rows, actor, reason)
            if changed:
                refresh("已儲存全部線材，並建立修改紀錄。")
            else:
                st.info("資料沒有變更。")
        except (ValueError, ConflictError) as error:
            show_error(error)
            draft_export = {"盤體": snapshot["name"], "基本資料": meta, "線材明細": prepared_rows}
            st.download_button("下載未儲存草稿", json.dumps(draft_export, ensure_ascii=False, default=str),
                               file_name="wirelog-draft.json", mime="application/json")

with search:
    st.subheader("查詢已儲存紀錄")
    query = st.text_input("搜尋線號、設備、端子或備註", key=f"search_{selected}")
    c1, c2 = st.columns(2)
    statuses = c1.multiselect("配線狀態", STATES, key=f"states_{selected}")
    checks = c2.multiselect("查驗結果", CHECKS, key=f"checks_{selected}")
    filtered = frame.copy()
    if query:
        filtered = filtered[filtered.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False)).any(axis=1)]
    if statuses:
        filtered = filtered[filtered["配線狀態"].isin(statuses)]
    if checks:
        filtered = filtered[filtered["查驗結果"].isin(checks)]
    st.caption(f"符合 {len(filtered)} 筆／共 {len(frame)} 筆")
    st.dataframe(filtered, hide_index=True, width="stretch")
    st.download_button("匯出查詢結果 CSV", csv_bytes(filtered.to_dict("records")),
                       "wirelog-filtered.csv", "text/csv")

with totals:
    st.subheader("實體線材用料統計")
    st.caption("多芯／雙絞電纜以電纜編號去重，同一條電纜只計一次長度；單芯線逐條計算。")
    if frame.empty:
        st.info("儲存線材明細後，即可查看用料統計。")
    else:
        summary = pd.DataFrame(physical_items).groupby(["線材結構", "線材型號", "電纜總芯數", "芯線線徑（mm²）", "顏色"], dropna=False).agg(
            數量=("數量", "sum"), **{"總長度（cm）": ("總長度（cm）", "sum")}).reset_index()
        st.dataframe(summary, hide_index=True, width="stretch")
        safe_summary = summary.map(lambda value: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value)
        st.download_button("匯出用料統計 CSV", safe_summary.to_csv(index=False).encode("utf-8-sig"), "wirelog-materials.csv", "text/csv")
        overview = cable_overview(rows)
        if overview:
            st.subheader("電纜芯線／對絞登錄進度")
            st.dataframe(pd.DataFrame(overview), hide_index=True, width="stretch")
            if any(row["待補對絞組"] for row in overview):
                st.warning("部分對絞組尚未同時登錄 A、B 兩芯，請依實際配線確認。")

with fabrication:
    st.subheader("電纜製作單")
    st.caption("依電纜分組，重複的共用資料合併顯示。各芯印字號碼與兩端號碼圈分開列出。")
    html = fabrication_html(rows, snapshot["name"], snapshot["meta"])
    st.iframe(html, height=650)
    st.download_button("下載可列印製作單 HTML", html, "wirelog-fabrication.html", "text/html")
    st.caption("下載後以瀏覽器開啟，可列印或另存 PDF；剝皮與外被剝除欄位固定以 mm 表示。")

with history:
    st.subheader("修改紀錄")
    entries = store.history(selected)
    if not entries:
        st.info("尚無修改紀錄。")
    for entry in entries:
        with st.expander(f"{entry['time']} · {entry['actor']} · {entry['reason']}"):
            before, after = json.loads(entry["before_json"]), json.loads(entry["after_json"])
            left, right = st.columns(2)
            with left:
                st.write("修改前")
                st.json(normalize_meta(before["meta"]))
                st.dataframe(dataframe(before["wires"]), hide_index=True)
            with right:
                st.write("修改後")
                st.json(normalize_meta(after["meta"]))
                st.dataframe(dataframe(after["wires"]), hide_index=True)

with exchange:
    st.subheader("匯出與備份")
    a, b, c = st.columns(3)
    a.download_button("線材明細 CSV", csv_bytes(rows), "wirelog.csv", "text/csv")
    b.download_button("空白 CSV 範本", csv_bytes([]), "wirelog-template.csv", "text/csv")
    c.download_button("示例 CSV", csv_bytes(sample_rows()), "wirelog-example.csv", "text/csv")
    st.download_button("多芯雙絞／軍規焊接／動力壓接示例 CSV", csv_bytes(assembly_rows()), "wirelog-assembly-example.csv", "text/csv")
    backup = {"schema_version": 3, "panel": snapshot, "history": entries}
    st.download_button("下載此盤完整 JSON 備份", json.dumps(backup, ensure_ascii=False, indent=2),
                       "wirelog-backup.json", "application/json")
    st.caption("CSV 適合交換明細；JSON 包含盤體基本資料及修改紀錄，可供封存查閱。CSV 中以 =、+、-、@ 開頭的文字會加上單引號。")
    st.divider()
    st.subheader("匯入線材 CSV")
    st.caption("先下載範本填寫。UTF-8 CSV；端子編號請保留文字格式，例如 001。")
    if demo_mode:
        st.caption("展示版不開放檔案匯入，可直接在表格試填示範資料。")
    upload = None if demo_mode else st.file_uploader("選擇 CSV", type=["csv"], key=f"upload_{prefix}")
    if upload is not None:
        try:
            incoming = read_csv(upload.getvalue())
            st.dataframe(dataframe(incoming), hide_index=True, width="stretch")
            mode = st.radio("匯入方式", ["追加到現有明細", "取代此盤全部明細"], key=f"mode_{prefix}")
            with st.form(f"import_{prefix}"):
                author = st.text_input("匯入紀錄人員")
                note = st.text_input("匯入說明")
                confirmed = st.checkbox("已核對預覽；同意依上述方式更新此盤已儲存的明細")
                apply = st.form_submit_button("確認匯入", type="primary")
            if apply:
                if not confirmed:
                    st.warning("請先核對預覽並勾選確認。")
                else:
                    merged = rows + incoming if mode == "追加到現有明細" else incoming
                    store.save(selected, version, snapshot["meta"], merged, author, f"CSV {mode}：{note}" if note.strip() else "")
                    refresh("CSV 已匯入，並建立修改紀錄。")
        except ValueError as error:
            show_error(error)

st.caption("線徑與線色依核定圖面或實際規格記錄。本工具不進行線材選型或電氣設計計算。")
