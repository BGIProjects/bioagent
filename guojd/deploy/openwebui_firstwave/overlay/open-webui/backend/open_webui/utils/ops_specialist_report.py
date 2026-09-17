from __future__ import annotations

import html
from typing import Any


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def render_specialist_html(
    *,
    taxonomy: dict[str, Any] | None,
    rva: dict[str, Any] | None,
    citations: list[dict[str, Any]] | None,
    rules: dict[str, Any] | None,
    review: dict[str, Any] | None,
) -> str:
    tax = taxonomy or {}
    rva = rva or {}
    citations = citations or []
    rules = rules or {}
    review = review or {}

    tax_rows = [
        ["状态", tax.get("status") or "未提供"],
        ["科", tax.get("family") or "未提供"],
        ["属/种", tax.get("name") or tax.get("taxon") or "未提供"],
        ["模式", tax.get("mode") or "未提供"],
        ["知识发布", tax.get("knowledge_release") or "未提供"],
    ]
    rva_rows = [
        ["状态", rva.get("status") or "未提供"],
        ["科", rva.get("family") or "未提供"],
        ["特征数", rva.get("n_features") if rva.get("n_features") is not None else "未提供"],
        ["产物", rva.get("output") or "未提供"],
        ["GPU", ", ".join((rva.get("gpu") or {}).get("devices") or []) or "未提供"],
    ]
    cite_body = "".join(
        "<tr>"
        f"<td>{_e(item.get('corpus'))}</td>"
        f"<td>{_e(item.get('source_version') or item.get('knowledge_release'))}</td>"
        f"<td>{_e(item.get('locator'))}</td>"
        f"<td>{_e(item.get('content') or item.get('name'))}</td>"
        "</tr>"
        for item in citations
    ) or '<tr><td colspan="4">未提供</td></tr>'
    findings = rules.get("findings") or []
    find_body = "".join(
        "<tr>"
        f"<td>{_e(item.get('candidate_id'))}</td>"
        f"<td>{_e(item.get('code'))}</td>"
        f"<td>{_e(item.get('severity'))}</td>"
        f"<td>{_e(item.get('message'))}</td>"
        "</tr>"
        for item in findings
    ) or '<tr><td colspan="4">无规则命中</td></tr>'
    review_text = (
        f"{_e(review.get('decision') or '未审核')} · {_e(review.get('actor') or '')} · {_e(review.get('reason') or '')}"
    )
    return f"""
<section id="specialist">
  <h2>定种结论（virus_taxonomy）</h2>
  <table>{''.join(f'<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>' for k,v in tax_rows)}</table>
  <h2>RVA 摘要</h2>
  <table>{''.join(f'<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>' for k,v in rva_rows)}</table>
  <h2>kb.jsonl 引用</h2>
  <table><thead><tr><th>语料</th><th>发布</th><th>定位</th><th>内容</th></tr></thead><tbody>{cite_body}</tbody></table>
  <h2>候选矛盾 / 完整性</h2>
  <p>完整性：{_e(rules.get('completeness') or '未评估')}</p>
  <table><thead><tr><th>候选</th><th>规则</th><th>级别</th><th>说明</th></tr></thead><tbody>{find_body}</tbody></table>
  <h2>专家审核</h2>
  <p>{review_text or '未提供'}</p>
</section>
"""


def inject(document: str, specialist_html: str) -> str:
    marker = "</main>"
    if marker in document:
        return document.replace(marker, specialist_html + marker, 1)
    return document + specialist_html
