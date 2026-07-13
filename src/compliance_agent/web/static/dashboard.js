/* ComplianceAgent dashboard client.
 *
 * Two data modes, one UI:
 *  - static export: the scan envelope is embedded as window.__SCAN_DATA__;
 *  - server mode (window.__SERVER_MODE__): data comes from the local API,
 *    which also exposes scan history and re-scanning.
 *
 * Every value derived from the scanned repository (paths, messages, titles)
 * is inserted via textContent — never innerHTML — so a hostile repo cannot
 * inject markup into its own compliance report.
 */
(function () {
  "use strict";

  var SERVER = Boolean(window.__SERVER_MODE__);
  var TIERS = {
    minimal: { label: "MINIMAL", color: "var(--tier-minimal)" },
    limited: { label: "LIMITED", color: "var(--tier-limited)" },
    high: { label: "HIGH", color: "var(--tier-high)" },
    unacceptable: { label: "UNACCEPTABLE", color: "var(--tier-unacceptable)" },
  };
  var PILLS = {
    met: ["Met", "pill-met"],
    partial: ["Partial", "pill-partial"],
    unverified: ["Unverified", "pill-unverified"],
    missing: ["Missing", "pill-missing"],
    not_applicable: ["Not assessed", "pill-na"],
  };
  var SEVERITIES = ["critical", "high", "warning", "info"];
  var GAP_COLORS = {
    critical: "var(--sev-critical)",
    high: "var(--sev-high)",
    warning: "var(--sev-warning)",
    info: "var(--sev-info)",
  };

  var state = {
    envelope: null,
    severityFilter: new Set(SEVERITIES),
    search: "",
    currentHistoryId: null,
    entries: [],
  };

  var DIFF_LABEL = {
    improved: "Compliance improved",
    regressed: "Compliance regressed",
    mixed: "Mixed — some gains, some regressions",
    unchanged: "No change since the previous scan",
  };

  function $(id) { return document.getElementById(id); }

  /* Build an element; strings become text nodes (safe for untrusted values). */
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") el.className = attrs[k];
      else if (k === "style" && typeof attrs[k] === "object") {
        Object.keys(attrs[k]).forEach(function (p) { el.style.setProperty(p, attrs[k][p]); });
      } else el.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      if (c === null || c === undefined) return;
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }

  /* ---------- theme ---------- */

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var btn = $("btn-theme");
    btn.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    btn.setAttribute("aria-pressed", String(theme === "dark"));
    try { localStorage.setItem("ca-theme", theme); } catch (e) { /* private mode */ }
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem("ca-theme"); } catch (e) { /* private mode */ }
    var preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    applyTheme(saved || preferred);
    $("btn-theme").addEventListener("click", function () {
      var now = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(now);
    });
  }

  /* ---------- rendering ---------- */

  function fmtWhen(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  function render(envelope) {
    state.envelope = envelope;
    var r = envelope.scan_result;
    var tier = TIERS[r.risk_tier] || TIERS.minimal;

    $("empty-state").hidden = true;
    ["cover", "summary", "coverage", "findings", "gaps", "recommendations", "disclaimer"]
      .forEach(function (id) { $(id).hidden = false; });

    /* The comparison view is per-scan and stale once a different scan loads;
       hide it until the user explicitly compares again. */
    $("comparison").hidden = true;
    $("toc-comparison").hidden = true;

    renderCover(envelope, r, tier);
    renderSummary(r);
    renderCoverage(r);
    renderFrameworks(r);
    renderFindings(r);
    renderGaps(r);
    renderRecs(r);

    $("disclaimer").textContent = envelope.disclaimer || "";
    $("rail-version").textContent =
      (envelope.tool_name || "ComplianceAgent") + " v" + (envelope.tool_version || "");
    updateCompareControl();
  }

  function renderCover(envelope, r, tier) {
    $("cover-project").textContent = r.project_path;
    var meta = $("cover-meta");
    clear(meta);
    meta.appendChild(h("span", {}, ["Scanned " + fmtWhen(r.scan_time)]));
    meta.appendChild(h("span", {}, [String(r.files_scanned) + " files"]));
    meta.appendChild(h("span", { class: "mono" }, ["schema " + (envelope.schema_version || "?")]));

    var stamp = $("stamp");
    stamp.style.setProperty("--tier-color", tier.color);
    stamp.setAttribute("aria-label", "Risk tier: " + tier.label);
    $("stamp-tier").textContent = tier.label;
    var conf = r.risk_assessment ? Math.round(r.risk_assessment.confidence * 100) : null;
    $("stamp-conf").textContent =
      conf === null ? "" : conf + "% confidence (heuristic)";

    var errBanner = $("scan-errors-banner");
    if (r.scan_errors && r.scan_errors.length) {
      clear(errBanner);
      errBanner.appendChild(h("strong", {}, ["Incomplete scan. "]));
      errBanner.appendChild(document.createTextNode(
        r.scan_errors.length + " file(s) could not be fully analyzed; " +
        "results may be missing findings."));
      errBanner.hidden = false;
    } else {
      errBanner.hidden = true;
    }

    var caveat = $("tier-caveat");
    if (r.risk_tier === "minimal" || r.risk_tier === "limited") {
      caveat.textContent =
        "Keyword-based domain check — it can miss high-risk uses. If this system is " +
        "used for hiring, credit, biometrics, education, or other Annex III domains, " +
        "treat it as HIGH and verify manually.";
      caveat.hidden = false;
    } else {
      caveat.hidden = true;
    }
  }

  function renderSummary(r) {
    var providers = {};
    (r.findings || []).forEach(function (f) {
      if (f.category && f.category.indexOf("provider:") === 0) {
        providers[f.category.slice(9)] = true;
      }
    });
    var assessed = (r.coverage || []).filter(function (c) { return c.status !== "not_applicable"; });
    var met = assessed.reduce(function (n, c) { return n + c.requirements_met; }, 0);
    var total = assessed.reduce(function (n, c) { return n + c.requirements_total; }, 0);

    var metrics = $("metrics");
    clear(metrics);
    [
      [String(r.files_scanned), "Files scanned"],
      [String(Object.keys(providers).length), "AI providers"],
      [String((r.findings || []).length), "Findings"],
      [String((r.gaps || []).length), "Gaps"],
      [total ? met + " / " + total : "n/a", "Requirements met"],
    ].forEach(function (m) {
      metrics.appendChild(h("div", { class: "metric" }, [
        h("div", { class: "value" }, [m[0]]),
        h("div", { class: "label" }, [m[1]]),
      ]));
    });

    var reasoning = $("reasoning");
    clear(reasoning);
    if (r.risk_assessment && r.risk_assessment.reasoning && r.risk_assessment.reasoning.length) {
      reasoning.appendChild(h("div", {}, ["Why this tier:"]));
      reasoning.appendChild(h("ul", {},
        r.risk_assessment.reasoning.map(function (line) { return h("li", {}, [line]); })));
    }
  }

  function renderCoverage(r) {
    var countNote = $("coverage-count-note");
    if (countNote) {
      var count = (r.coverage || []).length;
      countNote.textContent = count + (count === 1 ? " EU AI Act article" : " EU AI Act articles");
    }
    var ledger = $("coverage-ledger");
    clear(ledger);
    (r.coverage || []).forEach(function (c) {
      var pill = PILLS[c.status] || PILLS.not_applicable;
      var detail = c.status === "not_applicable"
        ? (c.reason || "")
        : c.requirements_met + " / " + c.requirements_total + " requirements met";
      ledger.appendChild(h("div", { class: "ledger-row" }, [
        h("span", { class: "art" }, [c.article]),
        h("span", { class: "title" }, [c.title]),
        h("span", { class: "pill " + pill[1] }, [pill[0]]),
        h("span", { class: "detail" }, [detail]),
      ]));
    });
  }

  function renderFrameworks(r) {
    var section = $("frameworks");
    var list = $("frameworks-list");
    clear(list);
    var frameworks = r.frameworks_detected || [];
    section.hidden = frameworks.length === 0;
    frameworks.forEach(function (fw) {
      var heading = [fw.name];
      if (fw.version) heading.push(h("span", { class: "fw-version" }, ["v" + fw.version]));
      list.appendChild(h("div", { class: "framework" }, [
        h("h3", {}, heading),
        h("div", { class: "patterns" }, [(fw.patterns || []).join(", ")]),
        h("ul", {}, (fw.risk_notes || []).map(function (n) { return h("li", {}, [n]); })),
      ]));
    });
  }

  function buildChips(r) {
    var counts = {};
    SEVERITIES.forEach(function (s) { counts[s] = 0; });
    (r.findings || []).forEach(function (f) { counts[f.severity] = (counts[f.severity] || 0) + 1; });
    var chips = $("severity-chips");
    clear(chips);
    SEVERITIES.forEach(function (sev) {
      var chip = h("button", {
        class: "chip", type: "button",
        "aria-pressed": String(state.severityFilter.has(sev)),
      }, [sev + " (" + counts[sev] + ")"]);
      chip.addEventListener("click", function () {
        if (state.severityFilter.has(sev)) state.severityFilter.delete(sev);
        else state.severityFilter.add(sev);
        chip.setAttribute("aria-pressed", String(state.severityFilter.has(sev)));
        renderFindingRows(state.envelope.scan_result);
      });
      chips.appendChild(chip);
    });
  }

  function renderFindings(r) {
    buildChips(r);
    var search = $("finding-search");
    search.value = state.search;
    search.oninput = function () {
      state.search = search.value;
      renderFindingRows(r);
    };
    renderFindingRows(r);
  }

  var SEV_RANK = { critical: 0, high: 1, warning: 2, info: 3 };
  var SEV_ICON = { critical: "✗", high: "✗", warning: "⚠", info: "ℹ" };

  /* Strip parentheticals so the article column stays narrow:
     "Art. 3 (definitions), Art. 6 (…)" -> "Art. 3, Art. 6". */
  function shortArticle(article) {
    return (article || "—").replace(/\s*\([^)]*\)/g, "");
  }

  function renderFindingRows(r) {
    var list = $("findings-list");
    clear(list);
    var all = r.findings || [];
    var q = state.search.trim().toLowerCase();
    var visible = all.filter(function (f) {
      if (!state.severityFilter.has(f.severity)) return false;
      if (!q) return true;
      return [f.file_path, f.category, f.message, f.article || ""].join(" ")
        .toLowerCase().indexOf(q) !== -1;
    });

    var count = $("findings-count");
    count.textContent = all.length
      ? "Showing " + visible.length + " of " + all.length
      : "";

    if (!all.length) {
      list.appendChild(h("p", { class: "none-note ok" }, ["No AI usage patterns detected."]));
      return;
    }
    if (!visible.length) {
      list.appendChild(h("p", { class: "none-note" },
        ["No findings match the current filters."]));
      return;
    }

    /* Most severe first, then by file and line — priority order, not file order. */
    visible.sort(function (a, b) {
      var s = SEV_RANK[a.severity] - SEV_RANK[b.severity];
      if (s) return s;
      if (a.file_path !== b.file_path) return a.file_path < b.file_path ? -1 : 1;
      return (a.line_number || 0) - (b.line_number || 0);
    });

    var tbody = h("tbody", {}, visible.map(function (f) {
      var msgCell = h("td", {}, [h("div", { class: "f-msg" }, [f.message])]);
      var tagRow = h("div", {}, [h("span", { class: "f-cat" }, [f.category])]);
      if (f.occurrences > 1) {
        tagRow.appendChild(h("span", { class: "f-occ" }, ["×" + f.occurrences]));
      }
      msgCell.appendChild(tagRow);
      return h("tr", { class: "row-" + f.severity }, [
        h("td", {}, [h("span", { class: "sev-badge sev-" + f.severity }, [
          h("span", { class: "ico", "aria-hidden": "true" }, [SEV_ICON[f.severity] || ""]),
          f.severity,
        ])]),
        h("td", {}, [
          h("div", { class: "loc-file" }, [f.file_path]),
          f.line_number ? h("div", { class: "loc-line" }, ["line " + f.line_number]) : null,
        ]),
        msgCell,
        h("td", {}, [h("span", { class: "f-art" }, [shortArticle(f.article)])]),
      ]);
    }));

    list.appendChild(h("table", { class: "ftable" }, [
      h("thead", {}, [h("tr", {}, [
        h("th", { class: "col-sev" }, ["Severity"]),
        h("th", { class: "col-loc" }, ["Location"]),
        h("th", {}, ["Finding"]),
        h("th", { class: "col-art" }, ["Article"]),
      ])]),
      tbody,
    ]));
  }

  function renderGaps(r) {
    var list = $("gaps-list");
    clear(list);
    var gaps = r.gaps || [];
    if (!gaps.length) {
      list.appendChild(h("p", { class: "none-note ok" }, [
        "No gaps detected by static analysis. This is not a determination of " +
        "compliance — verify manually.",
      ]));
      return;
    }
    gaps.forEach(function (gap) {
      var color = GAP_COLORS[gap.severity] || "var(--rule)";
      var details = h("details", { class: "gap", style: { "--gap-color": color } }, [
        h("summary", {}, [
          h("span", { class: "art" }, [gap.article]),
          h("span", { class: "gap-title" }, [gap.title]),
          h("span", { class: "status" }, [gap.status]),
        ]),
        h("div", { class: "gap-body" }, [
          h("div", {}, [gap.description]),
          h("div", { class: "fix" }, [h("strong", {}, ["Fix: "]), gap.recommendation]),
        ]),
      ]);
      list.appendChild(details);
    });
  }

  function renderRecs(r) {
    var section = $("recommendations");
    var list = $("recs-list");
    clear(list);
    var recs = r.recommendations || [];
    if (!recs.length) {
      list.appendChild(h("p", { class: "none-note" }, [
        "No fix templates for this scan. Run `compliance-agent recommend <path>` " +
        "after addressing the gaps above.",
      ]));
      return;
    }
    section.hidden = false;
    recs.forEach(function (rec, i) {
      var block = h("div", { class: "rec" }, [
        h("h3", {}, [(i + 1) + ". " + rec.title + "  ",
          h("span", { class: "rec-art" }, [rec.article])]),
        h("p", {}, [rec.description]),
        h("div", { class: "tpl" }, ["Template: templates/" + rec.template_path]),
        h("ol", {}, (rec.steps || []).map(function (s) { return h("li", {}, [s]); })),
      ]);
      if (rec.template_content) {
        var preview = rec.template_content.split("\n").slice(0, 12).join("\n");
        block.appendChild(h("pre", {}, [preview + "\n…"]));
      }
      list.appendChild(block);
    });
  }

  /* ---------- server mode ---------- */

  function setScanStatus(text, isError) {
    var el = $("scan-status");
    el.textContent = text;
    el.classList.toggle("error", Boolean(isError));
  }

  function api(path, options) {
    return fetch(path, options).then(function (resp) {
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      return resp.json();
    });
  }

  function renderHistory(entries) {
    state.entries = entries;
    var block = $("history-block");
    var list = $("history-list");
    clear(list);
    block.hidden = entries.length === 0;
    updateCompareControl();
    entries.forEach(function (e) {
      var tier = TIERS[e.risk_tier] || TIERS.minimal;
      var btn = h("button", {
        type: "button",
        "aria-current": String(e.id === state.currentHistoryId),
      }, [
        h("span", { class: "dot", style: { background: tier.color } }),
        h("span", { class: "when" }, [fmtWhen(e.scan_time)]),
        h("span", { class: "counts" }, [e.findings + "f " + e.gaps + "g"]),
      ]);
      btn.addEventListener("click", function () {
        api("/api/history/" + encodeURIComponent(e.id)).then(function (envelope) {
          state.currentHistoryId = e.id;
          render(envelope);
          refreshHistory();
        }).catch(function (err) { setScanStatus("Could not load that scan: " + err.message, true); });
      });
      list.appendChild(h("li", {}, [btn]));
    });
    renderTrend(entries);
  }

  function renderTrend(entries) {
    var holder = $("trend");
    clear(holder);
    if (entries.length < 2) return;
    var pts = entries.slice(0, 20).reverse().map(function (e) { return e.gaps; });
    var max = Math.max.apply(null, pts.concat([1]));
    var w = 220, hgt = 30, step = w / (pts.length - 1);
    var d = pts.map(function (v, i) {
      var x = (i * step).toFixed(1);
      var y = (hgt - 3 - (v / max) * (hgt - 8)).toFixed(1);
      return (i ? "L" : "M") + x + " " + y;
    }).join(" ");
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + w + " " + (hgt + 4));
    var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    svg.appendChild(path);
    var lastX = ((pts.length - 1) * step).toFixed(1);
    var lastY = (hgt - 3 - (pts[pts.length - 1] / max) * (hgt - 8)).toFixed(1);
    var dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", lastX);
    dot.setAttribute("cy", lastY);
    dot.setAttribute("r", "2.4");
    svg.appendChild(dot);
    holder.appendChild(svg);
    holder.setAttribute("title", "Gap count across the last " + pts.length + " scans");
  }

  function refreshHistory() {
    return api("/api/history").then(function (payload) {
      renderHistory(payload.entries || []);
      return payload.entries || [];
    });
  }

  /* ---------- comparison (server mode) ---------- */

  /* Index of the currently-viewed scan within the newest-first history list. */
  function currentEntryIndex() {
    for (var i = 0; i < state.entries.length; i++) {
      if (state.entries[i].id === state.currentHistoryId) return i;
    }
    return -1;
  }

  /* The compare control is only meaningful when the viewed scan has an older
     scan immediately before it to diff against. */
  function updateCompareControl() {
    var control = $("compare-control");
    if (!control) return;
    var idx = currentEntryIndex();
    var hasPrev = idx !== -1 && idx + 1 < state.entries.length;
    control.hidden = !hasPrev;
    setCompareStatus("");
  }

  function setCompareStatus(text, isError) {
    var el = $("compare-status");
    el.textContent = text;
    el.classList.toggle("error", Boolean(isError));
  }

  function compareWithPrevious() {
    var idx = currentEntryIndex();
    if (idx === -1 || idx + 1 >= state.entries.length) {
      setCompareStatus("No earlier scan to compare against.", true);
      return;
    }
    var target = state.entries[idx].id;
    var base = state.entries[idx + 1].id;
    var btn = $("btn-compare");
    btn.disabled = true;
    setCompareStatus("Comparing…");
    api("/api/diff?base=" + encodeURIComponent(base) + "&target=" + encodeURIComponent(target))
      .then(function (diff) {
        renderDiff(diff);
        setCompareStatus("");
      })
      .catch(function (err) { setCompareStatus("Compare failed: " + err.message, true); })
      .then(function () { btn.disabled = false; });
  }

  function diffCounts(diff) {
    return h("div", { class: "diff-grid" }, [
      diffTile(diff.gaps_resolved.length, "Gaps resolved", "good"),
      diffTile(diff.gaps_new.length, "New gaps", diff.gaps_new.length ? "bad" : null),
      diffTile((diff.gaps_status_changed || []).length, "Status changed", null),
      diffTile(
        diff.requirements_met_base + " → " + diff.requirements_met_target,
        "Requirements met", null),
      diffTile(diff.findings_removed.length, "Findings removed", null),
      diffTile(diff.findings_added.length, "Findings added", null),
    ]);
  }

  function diffTile(value, label, tone) {
    return h("div", { class: "diff-tile" + (tone ? " diff-" + tone : "") }, [
      h("div", { class: "value" }, [String(value)]),
      h("div", { class: "label" }, [label]),
    ]);
  }

  function gapDeltaList(title, gaps, cls) {
    if (!gaps.length) return null;
    return h("div", { class: "diff-gaps " + cls }, [
      h("h3", {}, [title + " (" + gaps.length + ")"]),
      h("ul", {}, gaps.map(function (g) {
        return h("li", {}, [
          h("span", { class: "art" }, [g.article]),
          h("span", { class: "gap-title" }, [g.title]),
        ]);
      })),
    ]);
  }

  function renderDiff(diff) {
    var body = $("comparison-body");
    clear(body);

    var verdict = diff.verdict || "unchanged";
    body.appendChild(h("div", { class: "diff-verdict diff-" + verdict }, [
      DIFF_LABEL[verdict] || verdict,
    ]));

    var baseTier = TIERS[diff.base_tier] || { label: "n/a" };
    var targetTier = TIERS[diff.target_tier] || { label: "n/a" };
    body.appendChild(h("div", { class: "diff-tier" }, [
      "Risk tier: ",
      h("strong", {}, [baseTier.label]),
      " → ",
      h("strong", {}, [targetTier.label]),
      " (" + diff.tier_direction + ")",
    ]));

    body.appendChild(diffCounts(diff));
    var resolved = gapDeltaList("Resolved", diff.gaps_resolved, "resolved");
    var added = gapDeltaList("New", diff.gaps_new, "new");
    var changed = gapDeltaList("Status changed", diff.gaps_status_changed || [], "changed");
    if (resolved) body.appendChild(resolved);
    if (added) body.appendChild(added);
    if (changed) body.appendChild(changed);

    $("comparison").hidden = false;
    $("toc-comparison").hidden = false;
    $("comparison").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function runScan() {
    var btn = $("btn-scan");
    btn.disabled = true;
    setScanStatus("Scanning…");
    /* The custom header is required by the server: it forces a CORS
       preflight for any cross-origin caller (which the app never grants),
       so another open tab/website can never silently trigger a scan. */
    api("/api/scan", { method: "POST", headers: { "X-Compliance-Dashboard": "1" } })
      .then(function (envelope) {
        state.currentHistoryId = envelope.history_id || null;
        render(envelope);
        setScanStatus("Scan finished " + fmtWhen(new Date().toISOString()) + ".");
        return refreshHistory();
      })
      .catch(function (err) { setScanStatus("Scan failed: " + err.message, true); })
      .then(function () { btn.disabled = false; });
  }

  /* ---------- export (server mode) ---------- */

  function setExportStatus(text, isError) {
    var el = $("export-status");
    el.textContent = text;
    el.classList.toggle("error", Boolean(isError));
  }

  /* Fetch the export and hand it to the browser as a download. Fetch (not a
     plain navigation) so a server error surfaces as a status message in the
     rail instead of replacing the dashboard with an error page. */
  function downloadExport(fmt, btn) {
    if (!state.envelope) {
      setExportStatus("Run a scan first.", true);
      return;
    }
    var url = "/api/export/" + fmt +
      (state.currentHistoryId ? "?entry=" + encodeURIComponent(state.currentHistoryId) : "");
    btn.disabled = true;
    setExportStatus("Preparing " + fmt.toUpperCase() + "…");
    fetch(url)
      .then(function (resp) {
        if (!resp.ok) {
          return resp.json().then(
            function (body) { throw new Error(body.detail || ("HTTP " + resp.status)); },
            function () { throw new Error("HTTP " + resp.status); }
          );
        }
        return resp.blob();
      })
      .then(function (blob) {
        var name = (fmt === "html" ? "compliance-dashboard" : "compliance-report") + "." + fmt;
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 10000);
        setExportStatus("Saved " + name + ".");
      })
      .catch(function (err) { setExportStatus("Export failed: " + err.message, true); })
      .then(function () { btn.disabled = false; });
  }

  function initServerMode() {
    $("scan-control").hidden = false;
    $("btn-scan").addEventListener("click", runScan);
    $("btn-compare").addEventListener("click", compareWithPrevious);
    $("api-docs-link").hidden = false;
    $("export-control").hidden = false;
    $("btn-export-html").addEventListener("click", function () {
      downloadExport("html", $("btn-export-html"));
    });
    $("btn-export-pdf").addEventListener("click", function () {
      downloadExport("pdf", $("btn-export-pdf"));
    });
    api("/api/meta").then(function (meta) {
      var proj = $("rail-project");
      proj.textContent = meta.project_path;
      proj.setAttribute("title", meta.project_path);
      $("rail-version").textContent = "ComplianceAgent v" + meta.tool_version;
    });
    refreshHistory().then(function (entries) {
      if (entries.length) {
        state.currentHistoryId = entries[0].id;
        return api("/api/history/" + encodeURIComponent(entries[0].id)).then(render);
      }
      $("empty-state").hidden = false;
      runScan();
    }).catch(function (err) {
      $("empty-state").hidden = false;
      setScanStatus("Could not reach the scanner: " + err.message, true);
    });
  }

  /* ---------- boot ---------- */

  initTheme();
  if (window.__SCAN_DATA__) {
    render(window.__SCAN_DATA__);
  } else if (SERVER) {
    initServerMode();
  } else {
    $("empty-state").hidden = false;
  }
})();
