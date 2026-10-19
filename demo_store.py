"""Session-owned demo data: no disk, shared cache, or production database access."""
import copy
import json
from wirelog import ConflictError, assembly_rows, clean, normalize_meta, now, validate


class DemoStore:
    def __init__(self):
        self._panels = {}
        self._history = {}
        panel = self.create("展示盤（示範資料）")
        self.save(panel, 0, {"機型": "盤外", "位置": "示範設備"},
                  assembly_rows(), "展示系統", "載入示範資料")

    def panels(self):
        return [{"id": p["id"], "name": p["name"]} for p in self._panels.values()]

    def create(self, name):
        name = clean(name)
        if not name:
            raise ValueError("請輸入盤體名稱／編號。")
        if any(p["name"] == name for p in self._panels.values()):
            raise ValueError("此盤體名稱／編號已存在。")
        identifier = max(self._panels, default=0) + 1
        self._panels[identifier] = {"id": identifier, "name": name, "meta": {},
            "wires": [], "version": 0, "updated": now()}
        self._history[identifier] = []
        return identifier

    def load(self, panel_id):
        if panel_id not in self._panels:
            raise ValueError("找不到此配電盤。")
        return copy.deepcopy(self._panels[panel_id])

    def save(self, panel_id, version, meta, rows, actor, reason):
        rows, meta = validate(rows), normalize_meta(meta)
        actor, reason = clean(actor), clean(reason)
        if not actor or not reason:
            raise ValueError("請填寫紀錄人員及本次修改說明。")
        current = self._panels.get(panel_id)
        if current is None or current["version"] != version:
            raise ConflictError("展示資料版本已變更，請重新載入。")
        before = {"meta": current["meta"], "wires": current["wires"]}
        after = {"meta": meta, "wires": rows}
        if before == after:
            return False
        stamp = now()
        self._history[panel_id].insert(0, {"time": stamp, "actor": actor, "reason": reason,
            "before_json": json.dumps(before, ensure_ascii=False),
            "after_json": json.dumps(after, ensure_ascii=False)})
        current.update(copy.deepcopy(after))
        current.update(version=version + 1, updated=stamp)
        return True

    def history(self, panel_id):
        return copy.deepcopy(self._history.get(panel_id, []))
