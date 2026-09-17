"""Method labels/colors for portable W1 QC (no XvirBench dependency)."""
METHOD_ORDER = ["cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min"]
METHOD_LABEL = {
    "cDNA_Frag_30C5Min": "cDNA 30°C 5min",
    "RNA_Frag_85C6Min": "RNA 85°C 6min",
    "RNA_Frag_94C7Min": "RNA 94°C 7min",
}
METHOD_COLORS = {
    "cDNA_Frag_30C5Min": "#66c2a5",
    "RNA_Frag_94C7Min": "#fc8d62",
    "RNA_Frag_85C6Min": "#8da0cb",
}
HOST_ORDER = ["rat", "tick", "mosquito"]
HOST_LABEL = {"rat": "大鼠", "tick": "蜱", "mosquito": "蚊虫"}
