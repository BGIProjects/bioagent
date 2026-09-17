"""HTML 报告样式与脚本（对齐 vazyme RAT_COMPREHENSIVE_REPORT.html）。"""

REPORT_CSS = r"""
:root {
  --bg: #f0f4f8;
  --paper: #ffffff;
  --text: #1a202c;
  --muted: #718096;
  --accent: #2b6cb0;
  --accent-light: #ebf8ff;
  --border: #e2e8f0;
  --shadow: 0 2px 8px rgba(26, 32, 44, 0.08);
  --radius: 8px;
  --sidebar-w: 280px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; width: 100%; }
html, body { max-width: none !important; width: 100% !important; }
body {
  font-family: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  line-height: 1.7;
  margin: 0 !important;
  padding: 0 !important;
  color: var(--text);
  background: var(--bg);
  font-size: 15px;
}
.report-layout { display: flex; min-height: 100vh; width: 100%; }
.report-sidebar {
  position: fixed; left: 0; top: 0;
  width: var(--sidebar-w); height: 100vh; overflow-y: auto;
  background: var(--paper);
  border-right: 1px solid var(--border);
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.04);
  padding: 1.25rem 0.75rem 2rem;
  z-index: 200;
}
.sidebar-title {
  font-weight: 700; font-size: 1.05rem; color: #1a365d;
  padding: 0 0.75rem 0.75rem;
  border-bottom: 2px solid var(--accent);
  margin-bottom: 0.75rem;
}
.report-sidebar #TOC {
  background: transparent; border: none; box-shadow: none;
  padding: 0 0.25rem; margin: 0; max-width: none;
}
.report-sidebar #TOC > ul { padding-left: 0; list-style: none; margin: 0; }
.report-sidebar #TOC ul ul { padding-left: 0.85rem; margin-top: 0.15rem; }
.report-sidebar #TOC li { margin: 0.15rem 0; line-height: 1.45; font-size: 0.82rem; }
.report-sidebar #TOC a {
  display: block; padding: 0.3rem 0.6rem;
  color: #2c5282; text-decoration: none;
  border-radius: 4px; border-left: 3px solid transparent;
}
.report-sidebar #TOC a:hover { background: var(--accent-light); color: var(--accent); }
.report-sidebar #TOC a.active {
  background: var(--accent-light); color: var(--accent);
  border-left-color: var(--accent); font-weight: 600;
}
.report-main {
  margin-left: var(--sidebar-w); flex: 1;
  width: calc(100% - var(--sidebar-w));
  max-width: calc(100% - var(--sidebar-w));
  padding: 2rem 2.5rem 3rem;
}
header#title-block-header {
  text-align: center; padding: 0 0 1.5rem;
  margin-bottom: 1rem; border-bottom: 1px solid var(--border);
}
header#title-block-header .title {
  font-size: 1.85rem; font-weight: 700; color: #1a365d; margin: 0;
}
.report-main h1 { font-size: 1.5rem; color: #1a365d; margin-top: 0; }
.report-main h2 {
  font-size: 1.3rem; margin-top: 2.25rem;
  padding: 0.5rem 0 0.5rem 0.75rem;
  border-left: 4px solid var(--accent);
  background: linear-gradient(90deg, var(--accent-light) 0%, transparent 100%);
  border-radius: 0 var(--radius) var(--radius) 0;
  scroll-margin-top: 1rem;
}
.report-main h3 {
  font-size: 1.12rem; color: #2d3748;
  margin-top: 1.75rem; scroll-margin-top: 1rem;
}
.report-main h4 { font-size: 1rem; color: var(--muted); margin-top: 1.25rem; }
.report-main table, table {
  display: table !important;
  border-collapse: collapse;
  width: 100% !important; max-width: 100%;
  margin: 1rem 0 1.5rem;
  font-size: 0.9rem;
  background: var(--paper);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
}
.report-main thead { display: table-header-group !important; }
.report-main tbody { display: table-row-group !important; }
.report-main tr { display: table-row !important; }
.report-main th, .report-main td, th, td {
  display: table-cell !important;
  border: 1px solid var(--border);
  padding: 0.55rem 0.75rem;
  text-align: left; white-space: normal;
}
th { background: #edf2f7; font-weight: 600; color: #2d3748; }
tr:nth-child(even) td { background: #f7fafc; }
tr:hover td { background: #ebf8ff; }
table strong { color: #276749; }
code {
  background: #edf2f7; padding: 0.12rem 0.4rem;
  border-radius: 4px; font-size: 0.88em; color: #c53030;
}
hr { border: none; border-top: 1px solid var(--border); margin: 2rem 0; }
blockquote {
  border-left: 4px solid #cbd5e0;
  margin: 1rem 0; padding: 0.75rem 1.25rem;
  background: #f7fafc; color: #4a5568;
  border-radius: 0 var(--radius) var(--radius) 0;
}
a { color: var(--accent); }
.report-main figure, figure {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1rem; margin: 1.5rem 0;
  text-align: center; page-break-inside: avoid;
}
figure img, img.report-figure {
  display: block; max-width: 100%; width: auto; height: auto;
  margin: 0 auto; border-radius: 4px;
}
figure figcaption { display: none; }
figure + p > em:only-child, .report-main p em {
  display: block; text-align: center;
  font-size: 0.88rem; color: var(--muted);
  margin: -0.5rem 0 1.5rem;
}
.figure-row {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 1rem; margin: 0;
}
.figure-row figure { margin: 0; padding: 0.75rem; }
.meta-muted { color: var(--muted); font-size: 0.92rem; }
.sig { font-weight: 700; }
.sig1 { color: #d69e2e; } .sig2 { color: #dd6b20; } .sig3 { color: #c53030; } .ns { color: var(--muted); }
@media print {
  .report-sidebar { display: none; }
  .report-main { margin-left: 0; width: 100%; max-width: 100%; padding: 0; }
  body { background: #fff; font-size: 11pt; }
  figure img { max-width: 100% !important; max-height: 230mm !important; }
  table { box-shadow: none; font-size: 9pt; }
}
@media (max-width: 900px) {
  .report-sidebar { position: static; width: 100%; height: auto; max-height: 40vh; }
  .report-layout { flex-direction: column; }
  .report-main { margin-left: 0; width: 100%; max-width: 100%; padding: 1.25rem; }
  .figure-row { grid-template-columns: 1fr; }
  .fig-gallery { grid-template-columns: 1fr; }
}

/* 图表画廊 */
.fig-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.25rem;
  margin: 1.25rem 0 1.75rem;
}
.fig-card {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 0.75rem 0.85rem 0.5rem;
  page-break-inside: avoid;
}
.fig-card h4 {
  margin: 0 0 0.5rem;
  font-size: 0.92rem;
  color: #2d3748;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.35rem;
}
.fig-card.layout-panel img { max-height: 260px; width: 100%; object-fit: contain; }
.fig-card.layout-facet img { max-height: 200px; width: 100%; object-fit: contain; }
.fig-card.layout-wide img { max-height: 220px; width: 100%; object-fit: contain; }
.fig-card.layout-heatmap img { max-height: 240px; width: 100%; object-fit: contain; }
.fig-card.layout-compact img { max-height: 200px; width: 100%; object-fit: contain; }
.fig-card p.caption {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
  text-align: center;
}
.interp-block {
  background: #f7fafc;
  border-left: 3px solid #2b6cb0;
  padding: 0.65rem 1rem;
  margin: 0.75rem 0 1.25rem;
  font-size: 0.88rem;
  color: #4a5568;
}
.interp-block p { margin: 0.35rem 0; }
.dataset-tag {
  display: inline-block;
  background: #ebf8ff;
  color: #2c5282;
  font-size: 0.75rem;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  margin-right: 0.35rem;
}
"""

REPORT_JS = r"""
(function () {
  function initSidebarScrollSpy() {
    var sidebar = document.querySelector(".report-sidebar");
    if (!sidebar) return;
    var links = sidebar.querySelectorAll('#TOC a[href^="#"]');
    if (!links.length) return;
    var headings = [];
    links.forEach(function (link) {
      var id = link.getAttribute("href").slice(1);
      var el = document.getElementById(id);
      if (el) headings.push({ id: id, el: el, link: link });
    });
    function setActive(id) {
      links.forEach(function (l) {
        l.classList.toggle("active", l.getAttribute("href") === "#" + id);
      });
    }
    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) setActive(entry.target.id);
          });
        },
        { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
      );
      headings.forEach(function (h) { observer.observe(h.el); });
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSidebarScrollSpy);
  } else {
    initSidebarScrollSpy();
  }
})();
"""
