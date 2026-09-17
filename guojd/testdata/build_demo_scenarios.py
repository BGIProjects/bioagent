#!/usr/bin/env python3
"""Build a small-batch demo pack for analysis-page scenarios."""

from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCEN = ROOT / "scenarios"
N_TINY = 200
N_VIRAL = 2500
READ_LEN = 100
READ_LEN_VIRAL = 150
FRAG_LEN_VIRAL = 280
N_HOST_SPIKE = 400


def iter_fastq(path: Path):
    opener = gzip.open if path.suffix == ".gz" or path.name.endswith(".gz") else open
    with opener(path, "rt") as handle:
        while True:
            name = handle.readline()
            if not name:
                return
            seq = handle.readline()
            plus = handle.readline()
            qual = handle.readline()
            if not qual:
                return
            yield name, seq, plus, qual


def write_fastq_gz(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as handle:
        for rec in records:
            handle.writelines(rec)


def subsample(src: Path, dst: Path, n: int):
    write_fastq_gz(dst, [rec for rec, _ in zip(iter_fastq(src), range(n))])


def read_fasta(path: Path) -> tuple[str, str]:
    header = "seq"
    chunks: list[str] = []
    with path.open() as handle:
        for line in handle:
            if line.startswith(">"):
                if not chunks:
                    header = line[1:].strip().split()[0]
                continue
            chunks.append(line.strip())
    return header, "".join(chunks).upper()


def simulate_pe(
    fasta: Path,
    out_r1: Path,
    out_r2: Path,
    n: int,
    read_len: int = READ_LEN,
    frag_len: int | None = None,
    name_prefix: str | None = None,
):
    name, seq = read_fasta(fasta)
    if frag_len is None:
        frag_len = min(max(read_len + 20, read_len), len(seq))
    if len(seq) < max(read_len, frag_len):
        raise SystemExit(f"{fasta} too short")
    step = max(1, (len(seq) - frag_len) // max(1, n))
    recs1 = []
    recs2 = []
    complement = str.maketrans("ACGTN", "TGCAN")
    prefix = name_prefix or name
    for i in range(n):
        start = min(i * step, len(seq) - frag_len)
        frag = seq[start : start + frag_len]
        r1 = frag[:read_len]
        r2 = frag[-read_len:].translate(complement)[::-1]
        recs1.append((f"@{prefix}_sim_{i+1}/1\n", r1 + "\n", "+\n", "I" * read_len + "\n"))
        recs2.append((f"@{prefix}_sim_{i+1}/2\n", r2 + "\n", "+\n", "I" * read_len + "\n"))
    write_fastq_gz(out_r1, recs1)
    write_fastq_gz(out_r2, recs2)
    return recs1, recs2


def write_mixed_pe(out_r1: Path, out_r2: Path, batches: list[tuple[list, list]]):
    recs1 = []
    recs2 = []
    for a, b in batches:
        recs1.extend(a)
        recs2.extend(b)
    write_fastq_gz(out_r1, recs1)
    write_fastq_gz(out_r2, recs2)


def main():
    single = ROOT / "reads" / "single"
    multi = ROOT / "reads" / "multi"
    contigs = ROOT / "contigs"
    s1 = SCEN / "S1_single_pe"
    s2 = SCEN / "S2_multi_sample"
    s3 = SCEN / "S3_hepacivirus_contigs"
    s4 = SCEN / "S4_hepacivirus_reads"
    s5 = SCEN / "S5_hepacivirus_w2w3w5"
    for d in (s1, s2, s3, s4, s5):
        d.mkdir(parents=True, exist_ok=True)

    subsample(single / "demoA_R1.fastq.gz", s1 / "demoA_R1.fastq.gz", N_TINY)
    subsample(single / "demoA_R2.fastq.gz", s1 / "demoA_R2.fastq.gz", N_TINY)

    subsample(multi / "demoA_R1.fastq.gz", s2 / "demoA_R1.fastq.gz", N_TINY)
    subsample(multi / "demoA_R2.fastq.gz", s2 / "demoA_R2.fastq.gz", N_TINY)
    subsample(multi / "demoB_R1.fastq.gz", s2 / "demoB_R1.fastq.gz", N_TINY)
    subsample(multi / "demoB_R2.fastq.gz", s2 / "demoB_R2.fastq.gz", N_TINY)

    for name in ("KP641127.fna", "KP325401.fna"):
        shutil.copy2(contigs / name, s3 / name)

    simulate_pe(contigs / "KP641127.fna", s4 / "KP641127_R1.fastq.gz", s4 / "KP641127_R2.fastq.gz", N_TINY)

    hepa_a1, hepa_a2 = simulate_pe(
        contigs / "KP641127.fna",
        s5 / "_tmp_hepaA_R1.fastq.gz",
        s5 / "_tmp_hepaA_R2.fastq.gz",
        N_VIRAL,
        read_len=READ_LEN_VIRAL,
        frag_len=FRAG_LEN_VIRAL,
        name_prefix="KP641127",
    )
    host1, host2 = simulate_pe(
        contigs / "host_ND1_spike.fna",
        s5 / "_tmp_host_R1.fastq.gz",
        s5 / "_tmp_host_R2.fastq.gz",
        N_HOST_SPIKE,
        read_len=READ_LEN_VIRAL,
        frag_len=min(FRAG_LEN_VIRAL, 280),
        name_prefix="hostND1",
    )
    write_mixed_pe(s5 / "hepaA_R1.fastq.gz", s5 / "hepaA_R2.fastq.gz", [(hepa_a1, hepa_a2), (host1, host2)])
    simulate_pe(
        contigs / "KP325401.fna",
        s5 / "hepaB_R1.fastq.gz",
        s5 / "hepaB_R2.fastq.gz",
        N_VIRAL,
        read_len=READ_LEN_VIRAL,
        frag_len=FRAG_LEN_VIRAL,
        name_prefix="KP325401",
    )
    for tmp in s5.glob("_tmp_*.fastq.gz"):
        tmp.unlink()

    manifest = {
        "version": "2026-09-16",
        "pair_count": N_TINY,
        "scenarios": [
            {
                "id": "S1_single_pe",
                "title": "单样本双端",
                "paths": [str(s1 / "demoA_R1.fastq.gz"), str(s1 / "demoA_R2.fastq.gz")],
                "goals": ["contig_filter", "virus_summary"],
                "notes": "1 个样本、1 对 FASTQ。用来测配对、建数据集、W1/W2。",
            },
            {
                "id": "S2_multi_sample",
                "title": "多样本双端",
                "paths": [
                    str(s2 / "demoA_R1.fastq.gz"),
                    str(s2 / "demoA_R2.fastq.gz"),
                    str(s2 / "demoB_R1.fastq.gz"),
                    str(s2 / "demoB_R2.fastq.gz"),
                ],
                "goals": ["contig_filter", "virus_summary", "microbe_summary"],
                "notes": "2 个样本、2 对 FASTQ。用来测多样本分组和并行方案。",
            },
            {
                "id": "S3_hepacivirus_contigs",
                "title": "contig 定种 + RVA",
                "paths": [str(s3 / "KP641127.fna"), str(s3 / "KP325401.fna")],
                "goals": ["virus_summary", "annotation_delivery"],
                "specialists": ["virus_taxonomy", "rva"],
                "family": "Flaviviridae",
                "notes": "Hepacivirus contig。右侧「知识/专项」做定种 dry-run / 确认，再 RVA。",
            },
            {
                "id": "S4_hepacivirus_reads",
                "title": "由 contig 模拟的小批量 reads",
                "paths": [str(s4 / "KP641127_R1.fastq.gz"), str(s4 / "KP641127_R2.fastq.gz")],
                "goals": ["contig_filter", "virus_summary", "annotation_delivery"],
                "specialists": ["virus_taxonomy", "rva"],
                "family": "Flaviviridae",
                "notes": "200 对模拟 PE，来自 KP641127。只用来打通界面；组装/W2 请用 S5。",
            },
            {
                "id": "S5_hepacivirus_w2w3w5",
                "title": "Hepacivirus 组装 + 宿主 spike（W1/W2/W3/W5）",
                "paths": [
                    str(s5 / "hepaA_R1.fastq.gz"),
                    str(s5 / "hepaA_R2.fastq.gz"),
                    str(s5 / "hepaB_R1.fastq.gz"),
                    str(s5 / "hepaB_R2.fastq.gz"),
                ],
                "goals": ["contig_filter", "virus_summary", "host_summary", "virus_rpm"],
                "family": "Flaviviridae",
                "notes": "hepaA=KP641127 2500×150bp PE + 400 对 ND1 宿主 spike；hepaB=KP325401 2500×150bp PE。用于跑通 W2（至少 1 条病毒序列）、W3、W5。W7 不在默认报告。",
            },
        ],
    }
    (SCEN / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {SCEN}")
    for p in sorted(SCEN.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(ROOT)}  {p.stat().st_size}")


if __name__ == "__main__":
    main()
