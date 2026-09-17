"""绘图样式（对齐 vazyme fragmentation_test 分析报告）。"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import seaborn as sns

from cohort import METHOD_LABEL, METHOD_ORDER

METHOD_COLORS = {
    "cDNA_Frag_30C5Min": "#66c2a5",
    "RNA_Frag_94C7Min": "#fc8d62",
    "RNA_Frag_85C6Min": "#8da0cb",
}
HOST_COLORS_HEX = {"rat": "#e41a1c", "tick": "#377eb8", "mosquito": "#4daf4a"}
HOST_LABEL = {"rat": "大鼠", "tick": "蜱", "mosquito": "蚊虫"}
METHOD_PALETTE = [METHOD_COLORS[m] for m in METHOD_ORDER]

DPI = 140
PANEL_W, PANEL_H = 3.1, 2.6
QUAD_W, QUAD_H = 7.2, 5.8
FACET_W, FACET_H = 8.5, 2.8
WIDE_W, WIDE_H = 7.5, 3.2

_CJK_FONT: str | None = None
_CJK_FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def _resolve_cjk_font() -> str:
    global _CJK_FONT
    if _CJK_FONT:
        return _CJK_FONT
    from pathlib import Path

    path = Path(_CJK_FONT_PATH)
    if path.is_file():
        try:
            fm.fontManager.addfont(str(path))
            prop = fm.FontProperties(fname=str(path))
            _CJK_FONT = prop.get_name()
            return _CJK_FONT
        except Exception:
            pass
    available = {f.name for f in fm.fontManager.ttflist}
    for name in (
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
        "SimHei",
        "Microsoft YaHei",
    ):
        if name in available:
            _CJK_FONT = name
            return name
    _CJK_FONT = "DejaVu Sans"
    return _CJK_FONT


def apply_theme() -> None:
    font = _resolve_cjk_font()
    sns.set_theme(style="whitegrid", context="notebook", font_scale=0.92)
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [font, "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 7.5,
    })


def method_label_order(df, col: str = "method") -> list[str]:
    present = [m for m in METHOD_ORDER if m in df[col].astype(str).unique()]
    return [METHOD_LABEL[m] for m in present]


def save_close(fig, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
