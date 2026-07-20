(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Nav shadow + scroll progress bar, one rAF-throttled scroll handler.
  // scrollHeight is cached and only recomputed on resize — reading it every
  // scroll frame forces a synchronous layout recalculation each time (layout
  // thrashing), which is what made the nav feel jumpy/stuttery while scrolling.
  const nav = document.querySelector(".nav");
  const progressBar = document.querySelector("[data-progress-bar]");
  const heroTerminal = document.querySelector(".terminal");
  let scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
  const recomputeScrollableHeight = () => {
    scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
  };
  window.addEventListener("resize", recomputeScrollableHeight);
  // The hero-in entrance animation (styles.css) ends on transform:none with
  // fill-mode:both, which holds that value in the cascade forever — it
  // permanently outranks both .terminal's own resting rotate(-0.6deg) and
  // the scroll-parallax transform set below, so neither ever painted.
  // Dropping the animation once it finishes hands transform back to the
  // normal cascade (base rule + this handler).
  heroTerminal?.addEventListener("animationend", () => { heroTerminal.style.animation = "none"; }, { once: true });
  let scrollTicking = false;
  const onScroll = () => {
    const y = window.scrollY;
    if (nav) nav.classList.toggle("scrolled", y > 8);
    if (progressBar) progressBar.style.width = `${scrollableHeight > 0 ? (y / scrollableHeight) * 100 : 0}%`;
    if (heroTerminal && !reduceMotion && y < window.innerHeight) {
      heroTerminal.style.transform = `translateY(${Math.min(y * 0.08, 40)}px) rotate(-0.6deg)`;
    }
    scrollTicking = false;
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!scrollTicking) {
        requestAnimationFrame(onScroll);
        scrollTicking = true;
      }
    },
    { passive: true }
  );
  onScroll();

  // Mobile nav toggle (slide-in drawer + backdrop)
  const navToggle = document.querySelector(".nav-toggle");
  const navLinks = document.querySelector(".nav-links");
  const navBackdrop = document.querySelector("[data-nav-backdrop]");
  const setNavOpen = (open) => {
    navLinks.classList.toggle("nav-links--open", open);
    navToggle.setAttribute("aria-expanded", String(open));
    if (navBackdrop) navBackdrop.classList.toggle("show", open);
    document.body.style.overflow = open ? "hidden" : "";
  };
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => setNavOpen(navLinks.classList.contains("nav-links--open") ? false : true));
    navBackdrop?.addEventListener("click", () => setNavOpen(false));
    navLinks.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => setNavOpen(false)));
    window.addEventListener("keydown", (e) => { if (e.key === "Escape") setNavOpen(false); });
  }

  // SPA-style router: one .page visible at a time, driven by location.hash.
  // Progressive enhancement — without this, every .page is display:block
  // (see styles.css) and the site is just one long scrolling page.
  //
  // Two kinds of hash: a top-level page ("commands", "docs") swaps the whole
  // .page; a home anchor ("how-it-works", "risk-tiers", "frameworks", "faq")
  // stays on the "home" page and scrolls to that section instead, since those
  // are just chapters of one landing-page scroll, not separate app screens.
  const pages = Array.from(document.querySelectorAll(".page"));
  const navLinkEls = document.querySelectorAll("[data-navlink]");
  const DOC_FILES = {
    architecture: { file: "ARCHITECTURE.md", title: "Architecture" },
    articles: { file: "ARTICLES.md", title: "Article reference" },
    detectors: { file: "DETECTORS.md", title: "Detectors" },
    "ci-cd": { file: "CI-CD.md", title: "CI/CD integration" },
    configuration: { file: "CONFIGURATION.md", title: "Configuration" },
    mcp: { file: "MCP.md", title: "MCP integration" },
    "web-dashboard": { file: "WEB-DASHBOARD.md", title: "Web dashboard" },
    glossary: { file: "GLOSSARY.md", title: "Glossary" },
    troubleshooting: { file: "TROUBLESHOOTING.md", title: "Troubleshooting" },
  };
  const slugForFile = (filename) => {
    const found = Object.entries(DOC_FILES).find(([, v]) => v.file.toLowerCase() === filename.toLowerCase());
    return found ? found[0] : null;
  };

  if (pages.length) {
    const pageIds = pages.map((p) => p.id);
    const homeAnchors = ["home", "how-it-works", "risk-tiers", "frameworks", "faq"];

    const parseHash = () => {
      const raw = (location.hash || "").replace(/^#\/?/, "");
      if (raw.startsWith("docs/")) {
        const [slug, innerAnchor] = raw.slice(5).split("#");
        return { page: "docs", docSlug: DOC_FILES[slug] ? slug : "architecture", innerAnchor };
      }
      if (raw === "docs") return { page: "docs", docSlug: "architecture" };
      if (pageIds.includes(raw)) return { page: raw };
      if (homeAnchors.includes(raw)) return { page: "home", anchor: raw === "home" ? null : raw };
      return { page: "home" };
    };

    let currentDoc = null;
    const loadDoc = async (slug) => {
      if (currentDoc === slug) return;
      currentDoc = slug;
      const entry = DOC_FILES[slug];
      const content = document.querySelector("[data-docs-content]");
      if (!content) return;
      // Fade the existing content down instead of blanking it to a "Loading…"
      // placeholder — for local/fast fetches that read as a full page reload;
      // a quick crossfade reads as switching docs within the same app.
      content.classList.add("is-loading");
      document.querySelectorAll("[data-docs-nav] a").forEach((a) => a.classList.toggle("active", a.getAttribute("data-doc") === slug));
      try {
        const res = await fetch(`docs/${entry.file}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const md = await res.text();
        if (currentDoc !== slug) return; // a newer request won the race
        content.innerHTML = window.renderMarkdown ? window.renderMarkdown(md, { slugForFile }) : `<pre>${md}</pre>`;
      } catch (err) {
        if (currentDoc !== slug) return;
        content.innerHTML = `<p class="docs-status error">Couldn't load this doc (${err.message}). If you opened this file directly from disk, serve it from a local web server instead — or <a href="https://github.com/latreon/compliance-agent/blob/main/docs/${entry.file}" target="_blank" rel="noopener">view it on GitHub</a>.</p>`;
      } finally {
        if (currentDoc === slug) content.classList.remove("is-loading");
        recomputeScrollableHeight();
      }
    };

    let currentPage = null;
    const showPage = ({ page, anchor, docSlug, innerAnchor }) => {
      const pageChanged = page !== currentPage;
      currentPage = page;

      if (pageChanged) {
        pages.forEach((p) => {
          p.classList.remove("page-transition-in");
          p.classList.toggle("active", p.id === page);
        });
      }
      navLinkEls.forEach((l) => {
        const target = l.getAttribute("data-navlink");
        l.classList.toggle("active", page === "home" ? target === (anchor || "home") : target === page);
      });
      if (page === "docs" && docSlug) {
        loadDoc(docSlug).then(() => {
          if (innerAnchor) document.getElementById(innerAnchor)?.scrollIntoView();
        });
      }
      // Only reset scroll / replay the page-entrance animation when the page
      // itself changed — switching docs, or re-clicking the current page,
      // should never yank the viewport back to the top or fade the whole
      // screen out, or it reads as a full reload instead of an in-app switch.
      if (pageChanged) {
        if (anchor) {
          document.getElementById(anchor)?.scrollIntoView();
        } else {
          window.scrollTo(0, 0);
        }
        if (!reduceMotion) {
          const active = document.getElementById(page);
          if (active) {
            void active.offsetWidth; // restart the animation on repeat visits
            active.classList.add("page-transition-in");
          }
        }
        requestAnimationFrame(recomputeScrollableHeight);
      }
    };

    const navigate = () => {
      const route = parseHash();
      const pageWillChange = route.page !== currentPage;
      if (pageWillChange && !reduceMotion && document.startViewTransition) {
        document.startViewTransition(() => showPage(route));
      } else {
        showPage(route);
      }
    };
    document.body.classList.add("js-routed");
    window.addEventListener("hashchange", navigate);
    navigate();
  }

  // Scroll reveal — only engages once JS has actually run; see styles.css.
  const revealEls = document.querySelectorAll(".reveal");
  if (!reduceMotion && "IntersectionObserver" in window) {
    revealEls.forEach((el) => el.classList.add("pending"));
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }
    );
    revealEls.forEach((el) => io.observe(el));
  }

  // Hero terminal: stagger the report lines once in view
  const terminalBody = document.querySelector("[data-terminal-body]");
  if (terminalBody) {
    const lines = Array.from(terminalBody.querySelectorAll(".terminal-line"));
    const play = () => {
      lines.forEach((line, i) => {
        line.style.animationDelay = reduceMotion ? "0ms" : `${i * 70}ms`;
      });
    };
    if (reduceMotion || !("IntersectionObserver" in window)) {
      play();
    } else {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              play();
              io.disconnect();
            }
          });
        },
        { threshold: 0.4 }
      );
      io.observe(terminalBody);
    }
  }

  // Count-up stats
  const countEls = document.querySelectorAll("[data-count]");
  const runCount = (el) => {
    const target = parseInt(el.getAttribute("data-count"), 10) || 0;
    if (reduceMotion) {
      el.textContent = String(target);
      return;
    }
    const duration = 900;
    const start = performance.now();
    const step = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = String(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  if (countEls.length) {
    if (!("IntersectionObserver" in window)) {
      countEls.forEach(runCount);
    } else {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              runCount(entry.target);
              io.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.6 }
      );
      countEls.forEach((el) => io.observe(el));
    }
  }

  // Tabs (command reference, install methods) — WAI-ARIA tabs pattern:
  // roving tabindex (only the selected tab is in the Tab order) plus
  // arrow/Home/End to move focus and activate in one step.
  document.querySelectorAll("[data-tabs]").forEach((group) => {
    const buttons = Array.from(group.querySelectorAll(".tab-btn"));
    const panels = Array.from(group.querySelectorAll(".tab-panel"));
    const activate = (btn) => {
      const target = btn.getAttribute("data-tab");
      buttons.forEach((b) => {
        const selected = b === btn;
        b.setAttribute("aria-selected", String(selected));
        b.tabIndex = selected ? 0 : -1;
      });
      panels.forEach((p) => p.classList.toggle("active", p.getAttribute("data-panel") === target));
    };
    buttons.forEach((btn, i) => {
      btn.addEventListener("click", () => activate(btn));
      btn.addEventListener("keydown", (e) => {
        const moves = { ArrowRight: 1, ArrowLeft: -1, Home: -Infinity, End: Infinity };
        if (!(e.key in moves)) return;
        e.preventDefault();
        const next =
          e.key === "Home" ? buttons[0]
          : e.key === "End" ? buttons[buttons.length - 1]
          : buttons[(i + moves[e.key] + buttons.length) % buttons.length];
        next.focus();
        activate(next);
      });
    });
  });

  // Copy-to-clipboard — delegated on document, not bound per-button at load,
  // since docs pages inject their own [data-copy] buttons into the DOM later
  // (after the markdown fetch resolves) and a one-time querySelectorAll would
  // never see those.
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    const text = btn.getAttribute("data-copy") || "";
    const label = btn.textContent;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      document.body.removeChild(area);
    }
    btn.textContent = "Copied";
    btn.classList.add("copied");
    setTimeout(() => {
      btn.textContent = label;
      btn.classList.remove("copied");
    }, 1600);
  });
})();
