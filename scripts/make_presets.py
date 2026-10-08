"""Build the 10 preset JSON files (scratchpad), validate with pydantic, print audit."""
import json, pathlib, sys
from md2doc import tone
from md2doc.theme import Theme, audit

OUT = pathlib.Path(__file__).resolve().parents[1] / "src" / "md2doc" / "themes"
OUT.mkdir(exist_ok=True)

SANS_SYS = '"Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'
MONO_SYS = '"Cascadia Mono", Consolas, "Liberation Mono", monospace'
INTER = '"Inter", "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'
JBM = '"JetBrains Mono", "Cascadia Mono", Consolas, monospace'
SERIF = '"Source Serif 4", Georgia, "Times New Roman", serif'
ACAD = '"Latin Modern Roman", "CMU Serif", "Source Serif 4", Cambria, Georgia, serif'


def adm(bg, mode, note, tip, imp, warn, caution):
    d = {}
    for k, bar in dict(note=note, tip=tip, important=imp, warning=warn, caution=caution).items():
        a = tone.mix(bg, bar, 0.08 if mode == "light" else 0.14)
        d[k] = dict(bar=bar, bg=a, title=tone.ensure_contrast(bar, a, 4.5))
    return d


def colors(**k):
    return k


P = {}
P["github-light"] = dict(id="github-light", name="GitHub Light", mode="light",
    colors=dict(page_bg="#ffffff", text="#1f2328", text_muted="#59636e", heading="#1f2328", link="#0969da", accent="#0969da",
                border="#d1d9e0", code_bg="#f6f8fa", code_fg="#1f2328", inline_code_bg="#eff1f3", quote_bar="#d1d9e0",
                quote_bg="#ffffff", table_head_bg="#f6f8fa", table_stripe="#f6f8fa", selection="#b6e3ff",
                admonition=adm("#ffffff", "light", "#0969da", "#1a7f37", "#8250df", "#9a6700", "#d1242f")),
    fonts=dict(body=SANS_SYS, mono=MONO_SYS, size_pt=11, line_height=1.6, heading_scale=1.25, heading_weight=600),
    code=dict(tokens=dict(keyword="#cf222e", string="#0a3069", number="#0550ae", function="#6639ba", type="#953800",
                          builtin="#0550ae", tag="#116329", attr="#0550ae", comment="#59636e")),
    layout=dict(table_style="zebra"))
P["github-dark"] = dict(id="github-dark", name="GitHub Dark", mode="dark",
    colors=dict(page_bg="#0d1117", text="#f0f6fc", text_muted="#9198a1", heading="#f0f6fc", link="#4493f8", accent="#4493f8",
                border="#3d444d", code_bg="#151b23", code_fg="#f0f6fc", inline_code_bg="#1f232a", quote_bar="#3d444d",
                quote_bg="#0d1117", table_head_bg="#151b23", table_stripe="#151b23", selection="#1b3a66",
                admonition=adm("#0d1117", "dark", "#4493f8", "#3fb950", "#ab7df8", "#d29922", "#f85149")),
    fonts=dict(body=SANS_SYS, mono=MONO_SYS, size_pt=11, line_height=1.6, heading_scale=1.25, heading_weight=600),
    code=dict(pygments_style="github-dark"))
P["solarized-light"] = dict(id="solarized-light", name="Solarized Light", mode="light",
    colors=dict(page_bg="#fdf6e3", text="#42575e", text_muted="#566c74", heading="#073642", link="#0076bb", accent="#268bd2",
                border="#d9d2bc", code_bg="#eee8d5", code_fg="#42575e", inline_code_bg="#eee8d5", quote_bar="#93a1a1",
                quote_bg="#f7f0dc", table_head_bg="#eee8d5", table_stripe="#f7f0dc", selection="#d3e3e6",
                admonition=adm("#fdf6e3", "light", "#268bd2", "#859900", "#6c71c4", "#b58900", "#dc322f")),
    fonts=dict(body=INTER, mono=JBM, size_pt=11, line_height=1.65, heading_weight=700))
P["solarized-dark"] = dict(id="solarized-dark", name="Solarized Dark", mode="dark",
    colors=dict(page_bg="#002b36", text="#a7b5b5", text_muted="#8fa1a3", heading="#eee8d5", link="#3194db", accent="#268bd2",
                border="#0f4552", code_bg="#073642", code_fg="#a7b5b5", inline_code_bg="#073642", quote_bar="#586e75",
                quote_bg="#032f3b", table_head_bg="#073642", table_stripe="#04303b", selection="#08404f",
                admonition=adm("#002b36", "dark", "#268bd2", "#859900", "#6c71c4", "#b58900", "#dc322f")),
    fonts=dict(body=INTER, mono=JBM, size_pt=11, line_height=1.65, heading_weight=700))
P["nord"] = dict(id="nord", name="Nord", mode="dark",
    colors=dict(page_bg="#2e3440", text="#d8dee9", text_muted="#a8b2c4", heading="#eceff4", link="#88c0d0", accent="#81a1c1",
                border="#4c566a", code_bg="#3b4252", code_fg="#d8dee9", inline_code_bg="#434c5e", quote_bar="#81a1c1",
                quote_bg="#333a47", table_head_bg="#3b4252", table_stripe="#323947", selection="#434c5e",
                admonition=adm("#2e3440", "dark", "#81a1c1", "#a3be8c", "#b48ead", "#ebcb8b", "#bf616a")),
    fonts=dict(body=INTER, mono=JBM, size_pt=11, line_height=1.65, heading_weight=700),
    code=dict(pygments_style="nord"))
P["dracula"] = dict(id="dracula", name="Dracula", mode="dark",
    colors=dict(page_bg="#282a36", text="#f8f8f2", text_muted="#a9b0d0", heading="#bd93f9", link="#8be9fd", accent="#ff79c6",
                border="#44475a", code_bg="#21222c", code_fg="#f8f8f2", inline_code_bg="#44475a", quote_bar="#bd93f9",
                quote_bg="#2c2e3b", table_head_bg="#343746", table_stripe="#2c2e3b", selection="#44475a",
                admonition=adm("#282a36", "dark", "#8be9fd", "#50fa7b", "#bd93f9", "#f1fa8c", "#ff5555")),
    fonts=dict(body=INTER, mono=JBM, size_pt=11, line_height=1.65, heading_weight=700),
    code=dict(pygments_style="dracula"))
P["paper-sepia"] = dict(id="paper-sepia", name="Paper (Sepia)", mode="light",
    colors=dict(page_bg="#f4ecd8", text="#3b2f22", text_muted="#6b5b49", heading="#2a1f14", link="#8a3b12", accent="#a8541d",
                border="#d8c9a6", code_bg="#ebe0c5", code_fg="#3b2f22", inline_code_bg="#e8dbbc", quote_bar="#b98a52",
                quote_bg="#efe4cb", table_head_bg="#e8dbbc", table_stripe="#efe4cb", selection="#e3cf9f",
                admonition=adm("#f4ecd8", "light", "#2f6690", "#4a7c3a", "#7a4e9a", "#9a6a00", "#a8321f")),
    fonts=dict(body=SERIF, mono=JBM, size_pt=11.5, line_height=1.7, heading_weight=700),
    layout=dict(page=dict(justify=True, hyphenate=True), heading_rules=False))
P["academic-serif"] = dict(id="academic-serif", name="Academic (LaTeX-like)", mode="light",
    colors=dict(page_bg="#ffffff", text="#111111", text_muted="#4d4d4d", heading="#000000", link="#0b3d91", accent="#0b3d91",
                border="#999999", code_bg="#f5f5f5", code_fg="#111111", inline_code_bg="#f0f0f0", quote_bar="#999999",
                quote_bg="#ffffff", table_head_bg="#ffffff", table_stripe="#ffffff", selection="#cfe0ff",
                admonition=adm("#ffffff", "light", "#0b3d91", "#1b6e2e", "#6a2c91", "#8a5a00", "#a31515")),
    fonts=dict(body=ACAD, heading=ACAD, mono=JBM, size_pt=11, line_height=1.45, heading_scale=1.2, heading_weight=700),
    layout=dict(table_style="booktabs", heading_rules=False,
                page=dict(margin_mm=[25, 25, 28, 25], justify=True, hyphenate=True, paragraph_gap_em=0.8)))
P["newspaper"] = dict(id="newspaper", name="Newspaper", mode="light",
    colors=dict(page_bg="#fbfaf6", text="#1c1c1c", text_muted="#555555", heading="#000000", link="#8b1a1a", accent="#8b1a1a",
                border="#1c1c1c", code_bg="#efede6", code_fg="#1c1c1c", inline_code_bg="#e9e6dd", quote_bar="#8b1a1a",
                quote_bg="#fbfaf6", table_head_bg="#efede6", table_stripe="#f5f3ec", selection="#e6d3b8",
                admonition=adm("#fbfaf6", "light", "#2a4d7a", "#2f6b3a", "#6a3a7a", "#8a6000", "#8b1a1a")),
    fonts=dict(body=SERIF, heading=SERIF, mono=JBM, size_pt=10, line_height=1.5, heading_scale=1.3, heading_weight=700),
    layout=dict(table_style="grid", page=dict(columns=2, column_gap_mm=9, justify=True, hyphenate=True, margin_mm=[18, 16, 20, 16])))
P["high-contrast"] = dict(id="high-contrast", name="High Contrast", mode="dark",
    colors=dict(page_bg="#000000", text="#ffffff", text_muted="#d0d0d0", heading="#ffff00", link="#6cc7ff", accent="#ffff00",
                border="#ffffff", code_bg="#0b0b0b", code_fg="#ffffff", inline_code_bg="#1a1a1a", quote_bar="#ffff00",
                quote_bg="#000000", table_head_bg="#1a1a1a", table_stripe="#0b0b0b", selection="#1a3a8a", on_accent="#000000",
                admonition=adm("#000000", "dark", "#6cc7ff", "#4dff88", "#d7a8ff", "#ffff00", "#ff6b6b")),
    fonts=dict(body=SANS_SYS, mono='Consolas, "Cascadia Mono", monospace', size_pt=12, line_height=1.7, heading_weight=700),
    code=dict(pygments_style="github-dark"))

if __name__ == "__main__":
    for k, d in P.items():
        t = Theme.model_validate(d)
        (OUT / f"{k}.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
        print(f"{k:16} audit:", audit(t) or "OK")
    print(json.dumps(P["github-light"], indent=1)[:200])
    print("schema keys:", list(Theme.model_json_schema()["properties"].keys()))
