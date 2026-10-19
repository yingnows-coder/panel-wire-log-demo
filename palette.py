"""Fixed 64 wire-color cards, including sixteen striped wire combinations."""
SOLIDS = [
    ("黑", "#000000"), ("白", "#FFFFFF"), ("紅", "#FF0000"), ("黃", "#FFFF00"),
    ("橘", "#FF8000"), ("綠", "#008000"), ("藍", "#0000FF"), ("灰", "#808080"),
    ("棕", "#964B00"), ("紫", "#800080"), ("粉紅", "#FF69B4"), ("青", "#00FFFF"),
    ("米白", "#FFFDD0"), ("銀", "#C0C0C0"), ("金", "#D4AF37"), ("透明", "#E8EDF2"),
    ("深紅", "#8B0000"), ("淺紅", "#FF8080"), ("酒紅", "#800020"), ("玫瑰紅", "#C21E56"),
    ("橙紅", "#FF4500"), ("珊瑚", "#FF7F50"), ("桃紅", "#FF1493"), ("淺粉", "#FFC0CB"),
    ("深橘", "#D2691E"), ("淺橘", "#FFB366"), ("深黃", "#D4A000"), ("淺黃", "#FFFACD"),
    ("橄欖", "#808000"), ("黃綠", "#9ACD32"), ("淺綠", "#90EE90"), ("深綠", "#006400"),
    ("草綠", "#32CD32"), ("墨綠", "#004D40"), ("藍綠", "#008080"), ("淺青", "#AFEEEE"),
    ("淺藍", "#87CEFA"), ("天藍", "#00BFFF"), ("深藍", "#000080"), ("靛藍", "#4B0082"),
    ("淺紫", "#D8BFD8"), ("深紫", "#4B006E"), ("薰衣草", "#E6E6FA"), ("褐", "#8B4513"),
    ("淺棕", "#D2B48C"), ("深棕", "#4A2511"), ("淺灰", "#D3D3D3"), ("深灰", "#404040"),
]
STRIPES = ["白／藍", "白／橘", "白／綠", "白／棕", "白／紅", "白／黑", "白／黃", "白／紫",
           "紅／黑", "紅／白", "藍／黑", "綠／黃", "黃／黑", "黑／白", "黑／橘", "灰／粉紅"]
BASE = dict(SOLIDS)
PALETTE = [{"name": name, "background": color} for name, color in SOLIDS] + [
    {"name": name, "background": f"linear-gradient(135deg, {BASE[name.split('／')[0]]} 0% 50%, {BASE[name.split('／')[1]]} 50% 100%)"}
    for name in STRIPES]
COLOR_NAMES = [item["name"] for item in PALETTE]
COLOR_BACKGROUNDS = {item["name"]: item["background"] for item in PALETTE}


def color_background(value):
    name = str(value).replace("/", "／")
    return COLOR_BACKGROUNDS.get("橘" if name == "橙" else name, "")


def merge_colors(rows, selections):
    """Only accept predefined cards; retain existing historical color text unchanged."""
    output = [dict(row) for row in rows]
    for row in output:
        if row.get("線號") in selections:
            value = selections[row["線號"]]
            if value not in COLOR_NAMES and value != row.get("線色", ""):
                raise ValueError("請從 64 色色卡中選擇線色。")
            row["線色"] = value
    return output
