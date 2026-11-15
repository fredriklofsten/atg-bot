"""
Bygger webbappen docs/index.html av botens data (en enda fil, ingen server behövs).
GitHub Pages visar den sedan i mobilen.
"""
import json
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd

import config
from papper import Papperskassa

ETIKETT = {
    "auto": "Autostart", "spar_inner": "Innerspår (auto)", "spar_ytter": "Ytterspår 6–8 (auto)",
    "andra_led": "Andra ledet (auto)", "volt_spar_dalig": "Ytterspår på volten", "tillagg_20m": "Tillägg (per 20 m)",
    "alder": "Ålder", "ar_3": "3-åring", "hingst": "Hingst", "sto": "Sto", "log_intjanat": "Intjänade pengar",
    "log_starter": "Antal starter", "seger_pct": "Segerprocent", "topp3_pct": "Topp 3-procent",
    "log_per_start": "Pengar per start", "ar_seger_pct": "Årets segrar", "ar_starter_log": "Årets starter",
    "ar_form_saknas": "Ingen start i år", "rekord_km": "Rekordtid", "rekord_saknas": "Saknar rekord",
    "rekord_rel": "Långsammare rekord än fältet", "kusk_seger_pct": "Kuskens segerprocent",
    "kusk_starter_log": "Kuskens antal starter", "tranare_seger_pct": "Tränarens segerprocent",
    "barfota_fram": "Barfota fram", "barfota_bak": "Barfota bak", "skobyte": "Skobyte",
    "amerikansk_vagn": "Amerikansk vagn", "log_snittodds5": "Snittodds senaste 5", "snittodds_saknas": "Ny häst (inga odds)",
    "startpoang": "Startpoäng", "lang_distans": "Lång distans", "kort_distans": "Kort distans",
}

CSS = """
:root{--bg:#f1f4ef;--paper:#fff;--ink:#16261d;--soft:#4f6157;--line:#d8e0d6;--up:#2b8a3e;--down:#c92a2a;
--acc:#1f7a4d;--gold:#d08c00;--track:#e4ebe2;--chip:#eef3ec}
@media (prefers-color-scheme:dark){:root{--bg:#0e1712;--paper:#16231b;--ink:#e6efe8;--soft:#a6b8ac;--line:#28392e;
--up:#51cf66;--down:#ff8787;--acc:#4cc38a;--gold:#f2b84b;--track:#223228;--chip:#1d2c23}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 "Figtree",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.top{background:var(--ink);color:var(--bg);padding:14px 20px}
@media (prefers-color-scheme:dark){.top{background:#07100b;color:var(--ink)}}
.top-in{max-width:680px;margin:auto;display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.brand{font:800 20px/1 "Bricolage Grotesque",sans-serif;letter-spacing:-.01em}
.top small{opacity:.75;font-size:14px}
main{max-width:680px;margin:auto;padding:8px 20px 60px}
section{padding:28px 0;border-bottom:1px solid var(--line)}
section:last-child{border-bottom:0}
h1,h2,h3{font-family:"Bricolage Grotesque",sans-serif;line-height:1.1;margin:0 0 10px}
h1{font-size:clamp(40px,11vw,58px);font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
h2{font-size:24px;font-weight:800}
h3{font-size:17px;font-weight:700;margin:0}
p{margin:0 0 12px;max-width:62ch}
.kicker{color:var(--soft);font-size:15px;margin-bottom:6px}
.lede{font-size:18px;color:var(--soft)}
.note{font-size:15px;color:var(--soft)}
.up{color:var(--up)}.down{color:var(--down)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0 6px}
.stat{background:var(--paper);border-radius:14px;padding:12px 14px}
.stat b{display:block;font:800 22px/1.1 "Bricolage Grotesque",sans-serif;font-variant-numeric:tabular-nums}
.stat span{font-size:14px;color:var(--soft)}
.chart{background:var(--paper);border-radius:14px;padding:14px 10px 6px;margin-top:14px}
.chart svg{display:block;width:100%;height:auto}
.cards{display:grid;gap:14px;margin-top:16px}
.card{background:var(--paper);border-radius:14px;padding:14px 16px}
.card-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:10px}
.time{font:800 20px/1 "Bricolage Grotesque",sans-serif;color:var(--acc);font-variant-numeric:tabular-nums}
.horse{display:grid;grid-template-columns:28px 1fr 56px;gap:8px;align-items:center;margin:7px 0;font-size:15px}
.nr{font:800 15px/1 "Bricolage Grotesque",sans-serif;background:var(--chip);border-radius:7px;text-align:center;padding:5px 0}
.bar{height:8px;background:var(--track);border-radius:4px;position:relative;margin-top:4px}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:var(--acc)}
.bar u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--gold);text-decoration:none}
.pct{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
.bet{border-left:5px solid var(--gold);background:var(--chip);border-radius:10px;padding:9px 12px;margin-top:10px;font-size:15px}
.bet b{font-weight:700}
.chip{display:inline-block;font-size:13px;font-weight:700;padding:2px 9px;border-radius:999px;background:var(--chip);color:var(--soft)}
.chip.vunnen{background:color-mix(in srgb,var(--up) 18%,transparent);color:var(--up)}
.chip.förlorad{background:color-mix(in srgb,var(--down) 15%,transparent);color:var(--down)}
.chip.öppen{background:color-mix(in srgb,var(--gold) 20%,transparent);color:var(--gold)}
.list{list-style:none;padding:0;margin:14px 0 0}
.list li{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--line);font-size:15px}
.list li:last-child{border-bottom:0}
.list .r{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.sys{font:700 16px/1.4 ui-monospace,Menlo,Consolas,monospace;background:var(--chip);border-radius:10px;padding:10px 12px;margin:8px 0;word-break:break-word}
.legend{font-size:13px;color:var(--soft);display:flex;gap:14px;margin-top:6px}
.legend i{display:inline-block;width:12px;height:8px;border-radius:3px;background:var(--acc);margin-right:5px}
.legend u{display:inline-block;width:3px;height:12px;background:var(--gold);margin-right:5px;vertical-align:-2px}
table{width:100%;border-collapse:collapse;font-size:15px;margin-top:12px;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:8px 6px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{font-weight:600;color:var(--soft);font-size:13px}
.warn{background:color-mix(in srgb,var(--down) 12%,var(--paper));border-radius:12px;padding:12px 14px;margin-top:14px}
.empty{color:var(--soft);font-style:italic}
"""


def kr(x):
    return f"{x:,.0f} kr".replace(",", " ")


def _kurva(df):
    """SVG-linje för bankrullen över tid."""
    r = df[df.status.isin(["vunnen", "förlorad"])].copy()
    if len(r) < 2:
        return '<p class="empty">Kurvan dyker upp när boten har rättat några spel.</p>'
    r["netto"] = r.utbetalning - r.insats
    r = r.sort_values("skapad")
    y = [config.BANKRULLE_START] + list(config.BANKRULLE_START + r.netto.cumsum())
    lo, hi = min(y + [config.BANKRULLE_START]), max(y + [config.BANKRULLE_START])
    if hi - lo < 1:
        hi = lo + 1
    W, H, P = 640, 180, 8
    pts = [(P + i * (W - 2 * P) / (len(y) - 1), P + (hi - v) * (H - 2 * P) / (hi - lo)) for i, v in enumerate(y)]
    linje = " ".join(f"{x:.1f},{v:.1f}" for x, v in pts)
    yb = P + (hi - config.BANKRULLE_START) * (H - 2 * P) / (hi - lo)
    farg = "var(--up)" if y[-1] >= config.BANKRULLE_START else "var(--down)"
    return (f'<div class="chart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Bankrullen över tid">'
            f'<line x1="{P}" x2="{W-P}" y1="{yb:.1f}" y2="{yb:.1f}" stroke="var(--soft)" stroke-dasharray="4 5" opacity=".5"/>'
            f'<polyline points="{linje}" fill="none" stroke="{farg}" stroke-width="3" stroke-linejoin="round"/></svg>'
            f'<div class="legend">Streckad linje = startkassan {kr(config.BANKRULLE_START)}</div></div>')


def _plats_text(r):
    """'2026-11-08_14_10' -> 'lopp 10'. 'V85_2026-11-14_14_5' -> 'V85'."""
    lid = r.lopp_id if isinstance(r.lopp_id, str) and r.lopp_id else ""
    if lid:
        return f"lopp {lid.split('_')[-1]}"
    return str(r.spel_id).split("_")[0]


def _hast_rad(nr, namn, p, streck=None, skala=1.0):
    bredd = min(p / skala, 1) * 100
    markor = f'<u style="left:{min(streck / skala, 1) * 100:.1f}%"></u>' if streck is not None else ""
    return (f'<div class="horse"><span class="nr">{nr}</span><div>{escape(str(namn))}'
            f'<div class="bar"><i style="width:{bredd:.1f}%"></i>{markor}</div></div>'
            f'<span class="pct">{p*100:.0f} %</span></div>')


def _lopp_kort(an):
    tid = str(an["start"])[11:16]
    huvud = (f'<div class="card-head"><h3>{escape(an["bana"])} · lopp {an["nr"]}</h3>'
             f'<span class="time">{tid}</span></div>')
    if an["for_lite_pengar"]:
        return (f'<div class="card">{huvud}<p class="note">För lite pengar i poolen än '
                f'({kr(an["omsattning"])}). Boten tittar igen närmare start.</p></div>')
    rader = "".join(_hast_rad(f["nr"], f["hast"], f["p"], skala=max(an["favoriter"][0]["p"], 0.01))
                    for f in an["favoriter"][:3])
    spel = "".join(
        f'<div class="bet"><b>{escape(s["typ"])} {escape(s["val"])}</b> {escape(s["hast"])} · odds {s["odds"]:.2f} · '
        f'chans {s["chans"]*100:.0f} % · övervärde <b>{s["overvarde"]*100:+.0f} %</b> · {s["insats"]} kr</div>'
        for s in an["spel"][:5]) or '<p class="note" style="margin-top:8px">Inget värdespel – boten avstår.</p>'
    return f'<div class="card">{huvud}{rader}{spel}<p class="note" style="margin:8px 0 0">Analyserad {an.get("analyserad","")}</p></div>'


def _system_kort(an):
    tid = str(an["start"])[11:16]
    sy = an["system"]["Balanserad"]
    avd = ""
    for a in an["avdelningar"]:
        topp = a["hastar"][:3]
        skala = max(max(h["p"] for h in topp), max(h["streck"] for h in topp), 0.01)
        avd += (f'<p class="kicker" style="margin:14px 0 2px">Avd {a["avd"]}{" · spikkandidat" if a["spik"] else ""}</p>'
                + "".join(_hast_rad(h["nr"], h["hast"], h["p"], h["streck"], skala) for h in topp))
    status = ("" if an["odds_oppna"] else
              '<p class="note">Tidigt läge: oddsen är inte mogna, chanserna bygger på streck + egen analys.</p>')
    bra = sy["vardeindex"] >= an["kravs"]
    return (f'<div class="card"><div class="card-head"><h3>{escape(an["typ"])} · {escape(an["bana"])}</h3>'
            f'<span class="time">{tid}</span></div>{status}'
            f'<p class="kicker" style="margin:4px 0 0">Balanserat system · {sy["rader"]:.0f} rader · {kr(sy["kostnad"])}</p>'
            f'<div class="sys">{escape(sy["val"].replace("/", " / "))}</div>'
            f'<p class="note">Värdeindex <b class="{"up" if bra else "down"}">{sy["vardeindex"]:.2f}</b> '
            f'(behövs ~{an["kravs"]:.2f}) · chans alla rätt {sy["traffchans"]*100:.2f} %</p>'
            f'{avd}<div class="legend"><span><i></i>Botens chans</span><span><u></u>Streck (vad folket tror)</span></div></div>')


def bygg(data_dir="data", ut="docs/index.html"):
    kassa = Papperskassa(data_dir)
    df = kassa.df.copy()
    bank = kassa.bankrulle()
    status = {}
    sf = Path(data_dir) / "idag.json"
    if sf.exists():
        status = json.loads(sf.read_text(encoding="utf-8"))
    rapport = {}
    rf = Path("models/rapport.json")
    if rf.exists():
        rapport = json.loads(rf.read_text(encoding="utf-8"))

    rattade = df[df.status.isin(["vunnen", "förlorad"])] if not df.empty else df
    ins = float(rattade.insats.sum()) if len(rattade) else 0.0
    tillb = float(rattade.utbetalning.sum()) if len(rattade) else 0.0
    roi = (tillb - ins) / ins * 100 if ins else 0.0
    traff = (rattade.status == "vunnen").mean() * 100 if len(rattade) else 0.0
    oppna = int((df.status == "öppen").sum()) if not df.empty else 0
    diff = bank - config.BANKRULLE_START

    # ---------- Kommande lopp & V-spel ----------
    from motor import nu as _nu
    nu = _nu()

    def kommande(an):
        try:
            return datetime.fromisoformat(str(an["start"])[:19]) > nu
        except ValueError:
            return False
    lopp = sorted([a for a in status.get("lopp", {}).values() if kommande(a)], key=lambda a: a["start"])
    system = sorted([a for a in status.get("system", {}).values() if kommande(a)], key=lambda a: a["start"])
    lopp_html = "".join(_lopp_kort(a) for a in lopp[:8]) or \
        '<p class="empty">Inga svenska travlopp inom 45 minuter just nu. Boten kollar var tionde minut.</p>'
    sys_html = "".join(_system_kort(a) for a in system[:3]) or \
        '<p class="empty">Inga V-spel inom tre timmar.</p>'

    # ---------- Senaste spelen ----------
    senaste = ""
    if not df.empty:
        for _, r in df.sort_values("skapad", ascending=False).head(25).iterrows():
            plats = _plats_text(r)
            res = (f'+{kr(r.utbetalning)}' if r.status == "vunnen" else
                   (f'−{kr(r.insats)}' if r.status == "förlorad" else kr(r.insats)))
            senaste += (f'<li><span><b>{escape(str(r.typ))} {escape(str(r.val))[:40]}</b><br>'
                        f'<span class="note">{escape(plats)} · {str(r.skapad)[5:16].replace("T", " ")}</span></span>'
                        f'<span class="r"><span class="chip {r.status}">{r.status}</span><br>{res}</span></li>')
    senaste = f'<ul class="list">{senaste}</ul>' if senaste else '<p class="empty">Inga spel ännu.</p>'

    # ---------- Per speltyp ----------
    typer = ""
    if len(rattade):
        for typ, g in rattade.groupby("typ"):
            i, t = g.insats.sum(), g.utbetalning.sum()
            typer += (f'<tr><td>{escape(str(typ))}</td><td>{len(g)}</td><td>{(g.status=="vunnen").mean()*100:.0f} %</td>'
                      f'<td class="{"up" if t >= i else "down"}">{(t-i)/i*100:+.0f} %</td><td>{t-i:+,.0f}</td></tr>'
                      ).replace(",", " ")
        typer = (f'<table><tr><th>Spel</th><th>Antal</th><th>Träff</th><th>ROI</th><th>Netto kr</th></tr>{typer}</table>')
    else:
        typer = '<p class="empty">Tabellen fylls när de första spelen är rättade.</p>'

    # ---------- Hur smart är boten ----------
    smart = '<p class="empty">Ingen träningsrapport än.</p>'
    if rapport:
        m, b = rapport["loglik_marknad"], rapport["loglik_bot"]
        vinner = b > m
        vikter = sorted(rapport.get("vikter", {}).items(), key=lambda t: -abs(t[1]))[:8]
        vrad = "".join(f'<li><span>{escape(ETIKETT.get(k, k))}</span><span class="r {"up" if w > 0 else "down"}">'
                       f'{"ökar" if w > 0 else "minskar"} chansen</span></li>' for k, w in vikter)
        sim = rapport.get("sim_10", {})
        smart = (f'<p>Tränad {rapport.get("datum","")} på {rapport.get("antal_lopp",0):,} lopp. '
                 f'Testad på {rapport["testlopp"]:,} lopp den aldrig sett.</p>'.replace(",", " ") +
                 f'<div class="stats"><div class="stat"><b>{m:.3f}</b><span>Marknaden</span></div>'
                 f'<div class="stat"><b class="{"up" if vinner else "down"}">{b:.3f}</b><span>Boten</span></div>'
                 f'<div class="stat"><b>{rapport.get("blandning",[0,0])[1]:.1f}</b><span>Vikt på oddsen</span></div></div>'
                 f'<p class="note">Måttet visar hur väl chanserna stämde med vinnarna (närmare 0 är bättre). '
                 f'{"Boten slår marknaden en aning." if vinner else "Boten slår inte marknaden ännu."} '
                 f'I testet gav värdespelen {sim.get("roi",0)*100:+.0f} % på slutodds, men det är för optimistiskt: '
                 f'slutoddsen vet ingen i förväg. Det är låtsaskassan ovan som är det riktiga provet.</p>'
                 f'<h3 style="margin-top:18px">Det boten tittar mest på</h3><ul class="list">{vrad}</ul>')

    stopp = ('<div class="warn"><b>Stoppregeln är aktiv.</b> Boten har förlorat mer än '
             f'{kr(config.MAX_FORLUST_PER_VECKA)} senaste veckan och lägger inga nya spel just nu.</div>'
             if status.get("stopp") else "")
    tecken = "up" if diff >= 0 else "down"

    html = f"""<!DOCTYPE html>
<html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ATG-boten</title>
<meta http-equiv="refresh" content="300">
<link rel="manifest" href="manifest.json"><link rel="apple-touch-icon" href="ikon.png"><link rel="icon" href="ikon.png">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#16261d">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700&family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="top"><div class="top-in"><span class="brand">ATG-boten</span>
<small>Uppdaterad {escape(status.get("senast", datetime.now().strftime("%Y-%m-%d %H:%M")))}</small></div></div>
<main>
<section>
<p class="kicker">Låtsaskassan · startade med {kr(config.BANKRULLE_START)}</p>
<h1>{kr(bank)}</h1>
<p class="lede"><b class="{tecken}">{diff:+,.0f} kr</b> sedan start · {oppna} öppna spel</p>
<div class="stats"><div class="stat"><b class="{"up" if roi >= 0 else "down"}">{roi:+.1f} %</b><span>ROI</span></div>
<div class="stat"><b>{len(rattade)}</b><span>Rättade spel</span></div>
<div class="stat"><b>{traff:.0f} %</b><span>Träffar</span></div></div>
{_kurva(df) if not df.empty else '<p class="empty">Kurvan dyker upp när boten har rättat några spel.</p>'}
{stopp}
<p class="note" style="margin-top:12px">Under ca 200 rättade spel säger resultatet nästan ingenting – slumpen dominerar.</p>
</section>
<section><h2>Snart start</h2>
<p class="note">Boten spelar på papper när det är under {config.SPELFONSTER_MIN} minuter kvar och oddset ger minst
{config.MIN_OVERVARDE*100:.0f} % övervärde.</p>
<div class="cards">{lopp_html}</div></section>
<section><h2>V-spel</h2><div class="cards">{sys_html}</div></section>
<section><h2>Senaste spelen</h2>{senaste}</section>
<section><h2>Per speltyp</h2>{typer}</section>
<section><h2>Hur smart är boten?</h2>{smart}</section>
<section><h2>Så funkar det</h2>
<p>Var tionde minut under tävlingsdagen hämtar boten startlistor, odds och streck från ATG. Den räknar ut varje hästs
vinstchans och spelar bara när ATG:s odds är högre än chansen motiverar. Efter loppen rättar den sig själv.
Varje måndag lär den sig av förra veckans lopp.</p>
<p class="note">Allt är låtsaspengar. ATG behåller 15–35 % av varje insats, så de flesta förlorar i längden.
Spela ansvarsfullt – Stödlinjen 020-81 91 00.</p></section>
</main></body></html>"""
    Path(ut).parent.mkdir(parents=True, exist_ok=True)
    Path(ut).write_text(html, encoding="utf-8")
    manifest = Path(ut).parent / "manifest.json"
    if not manifest.exists():
        manifest.write_text(json.dumps({"name": "ATG-boten", "short_name": "ATG-boten", "start_url": ".",
                                        "display": "standalone", "background_color": "#f1f4ef",
                                        "theme_color": "#16261d",
                                        "icons": [{"src": "ikon.png", "sizes": "512x512", "type": "image/png"}]}),
                            encoding="utf-8")
