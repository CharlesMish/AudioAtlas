"""Lightweight static-report presentation modes.

Presentation changes the visual shell only. It never changes measurements,
findings, graph selection, or the PNG pixels written by AudioAtlas.
"""

from __future__ import annotations

from html import escape

VALID_PRESENTATION_MODES = ("focus", "studio")
DEFAULT_PRESENTATION_MODE = "studio"


def skip_link_html(target: str = "main-content") -> str:
    """Return the shared keyboard skip link for static reports."""

    return f'<a class="skip-link" href="#{escape(target, quote=True)}">Skip to report content</a>'


def validate_presentation_mode(mode: str | None) -> str:
    """Return a supported presentation mode or raise a bounded error."""

    selected = mode or DEFAULT_PRESENTATION_MODE
    if selected not in VALID_PRESENTATION_MODES:
        valid = ", ".join(VALID_PRESENTATION_MODES)
        raise ValueError(f"Unknown presentation mode {selected!r}. Valid modes: {valid}.")
    return selected


def presentation_controls_html(default_mode: str | None = None) -> str:
    """Return an accessible local-only Focus/Studio segmented control."""

    selected = validate_presentation_mode(default_mode)
    focus_pressed = "true" if selected == "focus" else "false"
    studio_pressed = "true" if selected == "studio" else "false"
    return (
        '<div class="presentation-controls" role="group" aria-label="Report appearance">'
        '<span class="presentation-label">View</span>'
        f'<button type="button" data-presentation-choice="focus" aria-pressed="{focus_pressed}">'
        'Focus</button>'
        f'<button type="button" data-presentation-choice="studio" aria-pressed="{studio_pressed}">'
        'Studio</button>'
        '</div>'
    )


def presentation_css() -> str:
    """Return CSS for the optional embellished Studio shell.

    The selectors only decorate report containers. They deliberately avoid
    filters, transforms, or overlays on the measured plot images themselves.
    """

    return r"""
.skip-link {
  position: fixed;
  z-index: 100001;
  top: 10px;
  left: 10px;
  padding: 10px 14px;
  border: 2px solid var(--accent);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-weight: 700;
  text-decoration: none;
  transform: translateY(-160%);
}
.skip-link:focus { transform: translateY(0); }
.sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}
a:focus-visible,
button:focus-visible,
summary:focus-visible,
textarea:focus-visible,
[tabindex]:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}
[id] { scroll-margin-top: 76px; }
.table-scroll {
  max-width: 100%;
  overflow-x: auto;
  border-radius: 8px;
}
.top-nav {
  position: sticky;
  z-index: 20;
  top: 0;
  background: var(--bg);
}
.presentation-controls {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px;
  margin: 0 0 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.presentation-label {
  padding: 0 8px 0 7px;
  color: var(--text-soft);
  font-size: 11.5px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.presentation-controls button {
  appearance: none;
  border: 0;
  border-radius: 999px;
  min-height: 36px;
  padding: 7px 12px;
  background: transparent;
  color: var(--text-muted);
  font: inherit;
  font-size: 12.5px;
  font-weight: 650;
  cursor: pointer;
}
.presentation-controls button[aria-pressed="true"] {
  background: var(--accent);
  color: var(--surface);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.16);
}
.presentation-controls button:focus-visible {
  outline: 3px solid var(--accent-muted);
  outline-offset: 2px;
}

body[data-presentation="focus"] .container {
  max-width: 1120px;
}
body[data-presentation="focus"] .presentation-controls {
  margin: 0 0 12px;
  background: var(--surface-muted);
  border-color: var(--border-soft);
  box-shadow: none;
}
body[data-presentation="focus"] .presentation-controls button {
  min-height: 34px;
  padding: 6px 12px;
}
body[data-presentation="focus"] .presentation-controls button[aria-pressed="true"] {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border-soft);
  box-shadow: none;
}

body[data-presentation="studio"] {
  background:
    radial-gradient(circle at 9% 2%, var(--accent-muted), transparent 28rem),
    radial-gradient(circle at 92% 11%, var(--pattern-accent), transparent 32rem),
    var(--bg);
}
body[data-presentation="studio"] .container { max-width: 1260px; }
body[data-presentation="studio"] header {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  margin: 14px 0 32px;
  padding: 34px 34px 20px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background:
    linear-gradient(135deg, var(--surface) 0%, var(--surface-muted) 100%);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.10), var(--shadow-card);
}
body[data-presentation="studio"] header::before,
body[data-presentation="studio"] header::after {
  content: "";
  position: absolute;
  z-index: -1;
  pointer-events: none;
}
body[data-presentation="studio"] header::before {
  width: 310px;
  height: 310px;
  right: -120px;
  top: -170px;
  border: 58px solid var(--accent-muted);
  border-radius: 50%;
  opacity: 0.65;
}
body[data-presentation="studio"] header::after {
  left: 0;
  right: 0;
  bottom: 0;
  height: 5px;
  background: linear-gradient(90deg, var(--accent), var(--callout-border), var(--pattern-accent));
}
body[data-presentation="studio"] h1 {
  font-size: clamp(32px, 5vw, 48px);
  letter-spacing: -0.035em;
}
body[data-presentation="studio"] h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom-color: var(--border-soft);
}
body[data-presentation="studio"] h2::before {
  content: "";
  width: 24px;
  height: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--callout-border));
  flex: 0 0 auto;
}
body[data-presentation="studio"] .metric-card,
body[data-presentation="studio"] .finding-card,
body[data-presentation="studio"] .plot-card,
body[data-presentation="studio"] details,
body[data-presentation="studio"] .note-box,
body[data-presentation="studio"] .context-card {
  border-radius: 14px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.075), var(--shadow-card);
}
body[data-presentation="studio"] .metric-card {
  position: relative;
  overflow: hidden;
  border-top: 3px solid var(--accent);
}
body[data-presentation="studio"] .metric-card::after {
  content: "";
  position: absolute;
  width: 74px;
  height: 74px;
  right: -40px;
  bottom: -46px;
  border: 14px solid var(--accent-muted);
  border-radius: 50%;
  opacity: 0.7;
}
body[data-presentation="studio"] .finding-card { border-left: 4px solid var(--callout-border); }
body[data-presentation="studio"] .plot-card { padding: 19px; }
body[data-presentation="studio"] .plot-card h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
}
body[data-presentation="studio"] .plot-card h3::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 4px var(--accent-muted);
}
body[data-presentation="focus"] .plot-card h3::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 4px var(--accent-muted);
}
body[data-presentation="studio"] .plot-image-wrapper {
  padding: 10px;
  border-radius: 11px;
  background: linear-gradient(145deg, var(--surface-muted), var(--surface));
  box-shadow: inset 0 0 0 1px var(--border-soft), 0 8px 22px rgba(15, 23, 42, 0.055);
}
body[data-presentation="studio"] .plot-image-wrapper img { border-radius: 7px; }
body[data-presentation="studio"] .how-to-read {
  border-radius: 14px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.055);
}
body[data-presentation="focus"] .how-to-read,
body[data-presentation="studio"] .how-to-read {
  border-top: 1px solid var(--border-soft);
}
body[data-presentation="studio"] .plot-image-wrapper:focus-visible,
body[data-presentation="focus"] .plot-image-wrapper:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

@media (max-width: 640px) {
  body[data-presentation="studio"] header { padding: 26px 20px 16px; border-radius: 14px; }
  .presentation-controls { margin-bottom: 12px; }
  .top-nav { position: static; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}
@media print {
  body, body[data-presentation="studio"] { background: #fff !important; color: #000 !important; }
  body[data-presentation="studio"] header,
  body[data-presentation="studio"] .metric-card,
  body[data-presentation="studio"] .finding-card,
  body[data-presentation="studio"] .plot-card,
  body[data-presentation="studio"] details,
  body[data-presentation="studio"] .note-box,
  body[data-presentation="studio"] .context-card {
    box-shadow: none !important;
  }
  body[data-presentation="studio"] header::before,
  body[data-presentation="studio"] header::after,
  .skip-link,
  .presentation-controls,
  .top-nav,
  .lightbox,
  .note-actions,
  .notes-status { display: none !important; }
  section, article, details, table, .card { break-inside: avoid; }
}
"""


def presentation_script(default_mode: str) -> str:
    """Return the no-dependency presentation-toggle script."""

    selected = validate_presentation_mode(default_mode)
    safe_default = escape(selected, quote=True)
    return (
        '<script>(function(){"use strict";'
        f'var fallback="{safe_default}";'
        'var body=document.body;'
        'var buttons=document.querySelectorAll("[data-presentation-choice]");'
        'var key="audioatlas:presentation:"+(window.location.pathname||"report");'
        'function valid(value){return value==="focus"||value==="studio";}'
        'function apply(value){var mode=valid(value)?value:fallback;'
        'body.setAttribute("data-presentation",mode);'
        'for(var i=0;i<buttons.length;i++){var active=buttons[i].getAttribute('
        '"data-presentation-choice")===mode;buttons[i].setAttribute("aria-pressed",'
        'active?"true":"false");}}'
        'var stored=null;try{stored=window.localStorage.getItem(key);}catch(e){}'
        'apply(valid(stored)?stored:fallback);'
        'for(var i=0;i<buttons.length;i++){buttons[i].addEventListener("click",function(){'
        'var mode=this.getAttribute("data-presentation-choice");apply(mode);'
        'try{window.localStorage.setItem(key,mode);}catch(e){}});}'
        'var printOpened=[];'
        'window.addEventListener("beforeprint",function(){printOpened=[];'
        'var details=document.querySelectorAll("details:not([open])");'
        'for(var j=0;j<details.length;j++){details[j].open=true;printOpened.push(details[j]);}});'
        'window.addEventListener("afterprint",function(){'
        'for(var j=0;j<printOpened.length;j++){printOpened[j].open=false;}printOpened=[];});'
        '})();</script>'
    )
