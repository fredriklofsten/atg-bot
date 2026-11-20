"""
Bygger webbappen i docs/ av botens data: Översikt, Lopp, Veckan, Arenan, Utveckling och Hjälp.
Rena HTML-filer – GitHub Pages visar dem i mobilen.
"""
import json
import math
from datetime import datetime
from html import escape
from pathlib import Path

import numpy as np
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
table.nw td,table.nw th{white-space:nowrap}
table{width:100%;border-collapse:collapse;font-size:15px;margin-top:12px;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:8px 6px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{font-weight:600;color:var(--soft);font-size:13px}
.warn{background:color-mix(in srgb,var(--down) 12%,var(--paper));border-radius:12px;padding:12px 14px;margin-top:14px}
.empty{color:var(--soft);font-style:italic}
nav.tabs{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
nav.tabs div{max-width:680px;margin:auto;display:flex;gap:6px;overflow-x:auto;padding:10px 20px;scrollbar-width:none}
nav.tabs a{flex:none;text-decoration:none;color:var(--ink);background:var(--paper);border-radius:999px;padding:7px 14px;
font-size:15px;font-weight:600}
nav.tabs a:active{background:var(--chip)}
section{scroll-margin-top:60px}
.nu{background:var(--paper);border-radius:14px;padding:14px 16px;margin:18px 0 4px;font-size:16px}
.nu b{font-weight:700}
.plain{font-size:16px;margin:0 0 4px}
.plain b{font-weight:700}
details{background:var(--paper);border-radius:12px;padding:12px 14px;margin:8px 0}
details summary{cursor:pointer;font-weight:700;list-style:none}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"＋ ";color:var(--acc)}
details[open] summary::before{content:"－ "}
details p{margin:8px 0 0;color:var(--soft);font-size:15px}
body{padding-bottom:84px}
:root{--s1:#1f7a4d;--s2:#c27c00;--s3:#2f6fd0;--s4:#a23bb8;--s5:#7a8580}
@media (prefers-color-scheme:dark){:root{--s1:#2e9a66;--s2:#b9852a;--s3:#5b95e8;--s4:#c77ddc;--s5:#97a39c}}
.bottom{position:fixed;left:0;right:0;bottom:0;z-index:9;background:var(--paper);border-top:1px solid var(--line);
padding-bottom:env(safe-area-inset-bottom)}
.bottom div{max-width:680px;margin:auto;display:grid;grid-template-columns:repeat(6,1fr)}
.bottom a{display:flex;flex-direction:column;align-items:center;gap:2px;padding:9px 0 10px;text-decoration:none;
color:var(--soft);font-size:11px;font-weight:600;min-width:0;overflow:hidden}
.bottom a span{font-size:21px;line-height:1}
.bottom a.aktiv{color:var(--acc)}
.knapp{display:inline-block;margin-top:12px;text-decoration:none;background:var(--acc);color:#fff;font-weight:700;
border-radius:999px;padding:9px 16px;font-size:15px}
.race{background:var(--paper);border-radius:14px;margin:10px 0;padding:0}
.race>summary{padding:13px 16px;list-style:none;cursor:pointer}
.race>summary::-webkit-details-marker{display:none}
.race>summary::before,.race[open]>summary::before{content:none!important}
.race[open]>summary{border-bottom:1px solid var(--line)}
.rhead{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.rbody{padding:4px 16px 14px}
.starter{border-bottom:1px solid var(--line);padding:11px 0}
.starter:last-child{border-bottom:0}
.srad{display:grid;grid-template-columns:30px 1fr auto;gap:10px;align-items:start}
.sinfo{font-size:13.5px;color:var(--soft);line-height:1.45}
.sinfo b{color:var(--ink);font-weight:600}
.odds{text-align:right;font-variant-numeric:tabular-nums;font-size:14px;color:var(--soft);white-space:nowrap}
.odds b{display:block;font:800 17px/1.2 "Bricolage Grotesque",sans-serif;color:var(--ink)}
.skal{margin-top:6px;display:flex;flex-wrap:wrap;gap:5px}
.skal span{font-size:12.5px;padding:2px 8px;border-radius:999px;background:var(--chip)}
.skal .plus{color:var(--up)}.skal .minus{color:var(--down)}
.vinst{background:color-mix(in srgb,var(--up) 14%,var(--paper))}
.dag{margin:22px 0 4px;font:800 18px/1.2 "Bricolage Grotesque",sans-serif}
.figur{background:var(--paper);border-radius:14px;padding:14px 12px 10px;margin-top:14px}
.figur h3{margin:0 4px 2px}
.figur .note{margin:0 4px 6px}
.figur svg{display:block;width:100%;height:auto;overflow:visible}
.figur svg text{font:11px "Figtree",sans-serif;fill:var(--soft)}
.figur svg .lbl{font-weight:700}
.tag{font-size:12px;font-weight:700;padding:1px 7px;border-radius:999px;background:var(--chip);color:var(--soft);white-space:nowrap}
.tag.up{color:var(--up)}.tag.down{color:var(--down)}
.rb{display:grid;grid-template-columns:118px 1fr 64px;gap:8px;align-items:center;margin:9px 0;font-size:14.5px}
.rb .zon{position:relative;height:18px;background:var(--track);border-radius:5px}
.rb .zon:before{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:2px;background:var(--soft);opacity:.6}
.rb .zon i{position:absolute;top:2px;bottom:2px;border-radius:3px}
.rb .zon i.plus{background:var(--up);left:50%}
.rb .zon i.minus{background:var(--down);right:50%}
.rb .v{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.rb.bas{opacity:.8}
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


TYPNAMN = {"Plats-pool": "Plats (korspool)", "Trio-pool": "Trio (korspool)", "Tvilling-pool": "Tvilling (korspool)"}


def _klartext(typ, val, hast=""):
    """Gör om ett spel till en mening alla förstår."""
    bas = str(typ).split("-")[0]
    namn = f" {escape(str(hast))}" if hast and str(hast) != "nan" else ""
    if bas == "Vinnare":
        return f"att <b>{escape(str(val))}{namn}</b> vinner"
    if bas == "Plats":
        return f"att <b>{escape(str(val))}{namn}</b> kommer topp 3"
    if bas == "Trio":
        return "att ordningen blir <b>" + " → ".join(escape(x) for x in str(val).split("-")) + "</b>"
    if bas == "Tvilling":
        a = str(val).split("-")
        return f"att <b>{escape(a[0])} och {escape(a[-1])}</b> blir etta och tvåa (valfri ordning)"
    return f"alla avdelningar rätt i <b>{escape(str(typ))}</b>"


def _hast_rad(nr, namn, p, streck=None, skala=1.0, rorelse=None, ai=None):
    bredd = min(p / skala, 1) * 100
    markor = f'<u style="left:{min(streck / skala, 1) * 100:.1f}%"></u>' if streck is not None else ""
    extra = ""
    if rorelse is not None and abs(rorelse) >= 0.1:
        extra += (f' <span class="tag up">▲ spelas ner</span>' if rorelse > 0
                  else f' <span class="tag down">▼ spelas upp</span>')
    if ai:
        extra += f' <span class="tag">AI {ai:+.0f}</span>'
    return (f'<div class="horse"><span class="nr">{nr}</span><div>{escape(str(namn))}{extra}'
            f'<div class="bar"><i style="width:{bredd:.1f}%"></i>{markor}</div></div>'
            f'<span class="pct">{p*100:.0f} %</span></div>')


def _lopp_kort(an):
    tid = str(an["start"])[11:16]
    huvud = (f'<div class="card-head"><h3>{escape(an["bana"])} · lopp {an["nr"]}</h3>'
             f'<span class="time">{tid}</span></div>')
    if an["for_lite_pengar"]:
        return (f'<div class="card">{huvud}<p class="note">För lite pengar i poolen än '
                f'({kr(an["omsattning"])}). Odds så tidigt är opålitliga – boten tittar igen närmare start.</p></div>')
    rader = "".join(_hast_rad(f["nr"], f["hast"], f["p"], skala=max(an["favoriter"][0]["p"], 0.01),
                              rorelse=f.get("rorelse"), ai=f.get("ai"))
                    for f in an["favoriter"][:3])
    pengar = [r for r in an.get("rorelser", []) if r["rorelse"] > 0]
    if pengar:
        rader += ('<p class="note" style="margin:8px 0 0">💰 Pengar strömmar in på: '
                  + ", ".join(f'{r["nr"]} {escape(r["hast"])} (odds −{(1 - math.exp(-r["rorelse"]))*100:.0f} %)'
                              for r in pengar) + '</p>')
    spel = "".join(
        f'<div class="bet"><p class="plain">{"🔀 " if "-pool" in s["typ"] else ""}Satsar <b>{s["insats"]} kr</b> på '
        f'{_klartext(s["typ"], s["val"], s["hast"])}.</p>'
        f'<span class="note">Rätt ger {kr(s["insats"] * s["odds"])} tillbaka · botens chans {s["chans"]*100:.0f} % · '
        f'det är värt <b>{s["overvarde"]*100:+.0f} %</b> mer än det kostar</span></div>'
        for s in an["spel"][:5]) or ('<p class="note" style="margin-top:8px">Inget spel här – oddsen är inte '
                                     'tillräckligt bra. Att avstå är också ett beslut.</p>')
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
    if an.get("jackpott"):
        status += (f'<p class="note">🎰 <b>Jackpott {kr(an["jackpott"])}</b> – potten blir ca '
                   f'{(an.get("jp_faktor", 1) - 1) * 100:.0f} % större, så kravet på värdeindex sänks.</p>')
    elif config.SYSTEM_BARA_JACKPOTT:
        status += '<p class="note">Ingen jackpott – boten pappersspelar inte den här omgången, bara visar.</p>' 
    bra = sy["vardeindex"] >= an["kravs"]
    return (f'<div class="card"><div class="card-head"><h3>{escape(an["typ"])} · {escape(an["bana"])}</h3>'
            f'<span class="time">{tid}</span></div>{status}'
            f'<p class="plain" style="margin-top:6px">Botens förslag: <b>{sy["rader"]:.0f} rader för {kr(sy["kostnad"])}</b>. '
            f'Siffrorna är startnummer, en grupp per avdelning:</p>'
            f'<div class="sys">{escape(sy["val"].replace("/", " / "))}</div>'
            f'<p class="note">Värdeindex <b class="{"up" if bra else "down"}">{sy["vardeindex"]:.2f}</b> '
            f'(behövs ~{an["kravs"]:.2f}) · chans alla rätt {sy["traffchans"]*100:.2f} %</p>'
            f'<p class="note" style="margin-top:10px">Grön stapel = botens chans. Gult streck = hur många som spelat hästen. '
            f'Går den gröna stapeln förbi det gula strecket är hästen <b>understreckad</b> – där finns värdet.</p>'
            f'{avd}<div class="legend"><span><i></i>Botens chans</span><span><u></u>Streck (vad folket tror)</span></div></div>')



# ---------------- Förklaringar i klartext ----------------
# (text när hästen har HÖGRE värde än fältet, text när den har LÄGRE)
FRASER = {
    "auto": ("autostart", "voltstart"), "spar_inner": ("bra innerspår", "inte innerspår"),
    "spar_ytter": ("ytterspår", "inte ytterspår"), "andra_led": ("startar i andra ledet", "startar i första ledet"),
    "volt_spar_dalig": ("dåligt voltspår", "bra voltspår"), "tillagg_20m": ("har tillägg", "inget tillägg"),
    "alder": ("äldre än fältet", "yngre än fältet"), "ar_3": ("3-åring", "äldre häst"),
    "hingst": ("hingst", "ej hingst"), "sto": ("sto", "ej sto"),
    "log_intjanat": ("har tjänat mycket", "har tjänat lite"), "log_starter": ("många starter", "få starter"),
    "seger_pct": ("vinner ofta", "vinner sällan"), "topp3_pct": ("ofta topp 3", "sällan topp 3"),
    "log_per_start": ("mycket pengar per start", "lite pengar per start"),
    "ar_seger_pct": ("vunnit mycket i år", "vunnit lite i år"), "ar_starter_log": ("många starter i år", "få starter i år"),
    "ar_form_saknas": ("inte startat i år", "startat i år"), "rekord_km": ("långsamt rekord", "snabbt rekord"),
    "rekord_saknas": ("saknar rekord", "har rekord"), "rekord_rel": ("sämre rekord än fältet", "bättre rekord än fältet"),
    "kusk_seger_pct": ("toppkusk", "svagare kusk"), "kusk_starter_log": ("rutinerad kusk", "ovan kusk"),
    "tranare_seger_pct": ("formstark tränare", "svagare tränare"),
    "barfota_fram": ("barfota fram", "skor fram"), "barfota_bak": ("barfota bak", "skor bak"),
    "skobyte": ("skobyte", "samma skor"), "amerikansk_vagn": ("amerikansk vagn", "vanlig vagn"),
    "log_snittodds5": ("höga odds senaste", "låga odds senaste"), "snittodds_saknas": ("ny häst, få lopp", "har startat förut"),
    "startpoang": ("många startpoäng", "få startpoäng"), "lang_distans": ("lång distans", "inte lång distans"),
    "kort_distans": ("kort distans", "inte kort distans"),
    "log_dagar_vila": ("lång vila", "startade nyss"), "lang_vila": ("vilat över 2 mån", "inte långvilad"),
    "vila_saknas": ("ingen formdata", "har formdata"), "galopp_senaste": ("galopp senast", "felfri senast"),
    "galopp_andel5": ("galopperar ofta", "galopperar sällan"), "disk_senaste": ("diskad senast", "ej diskad senast"),
    "form5": ("bra form", "svag form"), "seger_senaste": ("vann senast", "vann inte senast"),
    "km5_rel": ("långsammare tider senaste", "snabba tider senaste"),
    "log_odds_senaste": ("höga odds senast", "låga odds senast"), "forsta_barfota": ("barfota för första gången", "ej barfotabyte"),
    "kuskbyte": ("bytt kusk", "samma kusk"), "kuskbyte_topp": ("bytt till toppkusk", "ej bytt till toppkusk"),
    "tung_bana": ("tung bana", "lätt bana"), "vinterbana": ("vinterbana", "ej vinterbana"),
    "hemmabana": ("hemmabana", "bortabana"), "rorelse": ("spelas ner just nu", "spelas upp just nu"),
    "ai_poang": ("bra AI-betyg", "svagt AI-betyg"),
}


def _skal_html(skal):
    ut = []
    for item in skal or []:
        f, bidrag, riktning = (list(item) + [1])[:3]
        hog, lag = FRASER.get(f, (ETIKETT.get(f, f), ETIKETT.get(f, f)))
        text = hog if riktning > 0 else lag
        ut.append(f'<span class="{"plus" if bidrag > 0 else "minus"}">{"✓" if bidrag > 0 else "✗"} {escape(text)}</span>')
    return f'<div class="skal">{"".join(ut)}</div>' if ut else ""


# ---------------- Grafer (SVG, ritade i Python) ----------------
W, H = 380, 190
PL, PR, PT, PB = 44, 10, 12, 26


def _snygga(lo, hi, steg=4):
    """Runda axeln till jämna steg (1, 2, 2,5 eller 5 gånger tiopotens)."""
    rå = (hi - lo) / steg or 1
    pot = 10 ** math.floor(math.log10(abs(rå)))
    d = next(m * pot for m in (1, 2, 2.5, 5, 10) if m * pot >= rå)
    return math.floor(lo / d) * d, math.ceil(hi / d) * d, d


def _axlar(lo, hi, steg=4, fmt=lambda v: f"{v:.0f}"):
    ut = ""
    d = (hi - lo) / steg
    for i in range(steg + 1):
        v = lo + d * i
        y = PT + (hi - v) * (H - PT - PB) / (hi - lo)
        ut += (f'<line x1="{PL}" x2="{W-PR}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--line)"/>'
               f'<text x="{PL-6}" y="{y+4:.1f}" text-anchor="end">{fmt(v)}</text>')
    return ut


def _x(i, n):
    return PL + (i + 0.5) * (W - PL - PR) / max(n, 1)


def _y(v, lo, hi):
    return PT + (hi - v) * (H - PT - PB) / (hi - lo)


def figur(titel, forklaring, svg, tabell=""):
    return (f'<div class="figur"><h3>{titel}</h3><p class="note">{forklaring}</p>{svg}'
            + (f'<details><summary>Visa som tabell</summary>{tabell}</details>' if tabell else "") + '</div>')


def linjediagram(etiketter, serier, fmt=lambda v: f"{v:.0f}", nollinje=None):
    """serier: [(namn, värden, färgvariabel, streckad)] – en y-axel, direkta etiketter."""
    alla = [v for _, vs, _, _ in serier for v in vs if v is not None] + ([nollinje] if nollinje is not None else [])
    lo, hi = min(alla), max(alla)
    lo, hi, d = _snygga(lo, hi)
    if hi == lo:
        hi = lo + d
    n = len(etiketter)
    svg = f'<svg viewBox="0 0 {W} {H}" role="img">{_axlar(lo, hi, steg=round((hi - lo) / d), fmt=fmt)}'
    if nollinje is not None:
        y = _y(nollinje, lo, hi)
        svg += f'<line x1="{PL}" x2="{W-PR}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--soft)" stroke-dasharray="3 5"/>'
    steg = max(1, n // 4)
    for i, e in enumerate(etiketter):
        if i % steg == 0 or i == n - 1:
            svg += f'<text x="{_x(i, n):.1f}" y="{H-8}" text-anchor="middle">{escape(str(e))}</text>'
    for namn, vs, farg, streckad in serier:
        pts = [(_x(i, n), _y(v, lo, hi), v, etiketter[i]) for i, v in enumerate(vs) if v is not None]
        if not pts:
            continue
        svg += (f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)}" fill="none" stroke="var({farg})" '
                f'stroke-width="2" stroke-linejoin="round"{" stroke-dasharray=\"6 4\"" if streckad else ""}/>')
        for x, y, v, e in pts:
            svg += (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var({farg})" stroke="var(--paper)" stroke-width="2">'
                    f'<title>{escape(str(e))}: {namn} {fmt(v)}</title></circle>')
        x, y, v, _ = pts[-1]
        svg += f'<text class="lbl" x="{min(x + 6, W - 4):.1f}" y="{y - 8:.1f}" text-anchor="end">{escape(namn)}</text>'
    return svg + "</svg>"


def stapeldiagram(etiketter, varden, fmt=lambda v: f"{v:+.0f}"):
    """En stapel per etikett, grön över noll och röd under (plus +/− i tooltip)."""
    lo, hi = min(min(varden), 0), max(max(varden), 0)
    lo, hi, d = _snygga(lo, hi)
    if hi == lo:
        hi = lo + d
    n = len(varden)
    bredd = max(4, (W - PL - PR) / n - 4)
    svg = f'<svg viewBox="0 0 {W} {H}" role="img">{_axlar(lo, hi, steg=round((hi - lo) / d), fmt=fmt)}'
    y0 = _y(0, lo, hi)
    steg = max(1, n // 5)
    for i, (e, v) in enumerate(zip(etiketter, varden)):
        x = _x(i, n) - bredd / 2
        y = _y(v, lo, hi)
        farg = "var(--up)" if v >= 0 else "var(--down)"
        svg += (f'<rect x="{x:.1f}" y="{min(y, y0):.1f}" width="{bredd:.1f}" height="{max(abs(y0 - y), 1):.1f}" rx="3" '
                f'fill="{farg}"><title>{escape(str(e))}: {fmt(v)}</title></rect>')
        if i % steg == 0 or i == n - 1:
            svg += f'<text x="{_x(i, n):.1f}" y="{H-8}" text-anchor="middle">{escape(str(e))}</text>'
    return svg + f'<line x1="{PL}" x2="{W-PR}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="var(--soft)"/></svg>'


def kalibrering(punkter):
    """punkter: [(förutsagd, faktisk, antal)]. Prickar nära diagonalen = boten är ärlig om sina chanser."""
    hi = max([0.1] + [max(p, f) for p, f, _ in punkter]) * 1.1
    w = W
    svg = f'<svg viewBox="0 0 {w} {H}" role="img">{_axlar(0, hi * 100, fmt=lambda v: f"{v:.0f} %")}'
    x = lambda v: PL + v / hi * (w - PL - PR)
    y = lambda v: _y(v * 100, 0, hi * 100)
    svg += (f'<line x1="{x(0):.1f}" y1="{y(0):.1f}" x2="{x(hi):.1f}" y2="{y(hi):.1f}" stroke="var(--soft)" stroke-dasharray="4 5"/>'
            f'<text x="{x(hi*0.6):.1f}" y="{y(hi*0.6)-8:.1f}" text-anchor="end">perfekt</text>')
    for i in range(5):
        v = hi * i / 4
        svg += f'<text x="{x(v):.1f}" y="{H-8}" text-anchor="middle">{v*100:.0f} %</text>'
    for p, f, n in punkter:
        svg += (f'<circle cx="{x(p):.1f}" cy="{y(f):.1f}" r="{4 + min(n, 400) ** 0.5 / 4:.1f}" fill="var(--s1)" '
                f'stroke="var(--paper)" stroke-width="2" opacity=".85"><title>Boten sa {p*100:.0f} % – det blev '
                f'{f*100:.0f} % ({n} hästar)</title></circle>')
    return svg + "</svg>"


# ---------------- Sidskal ----------------
SIDOR = [("index.html", "🏠", "Översikt"), ("lopp.html", "🏇", "Lopp"), ("vecka.html", "📅", "Veckan"),
         ("arena.html", "🏁", "Arenan"), ("utveckling.html", "📈", "Utveckling"), ("hjalp.html", "❓", "Hjälp")]


def skal(titel, aktiv, uppdaterad, innehall, uppdatera=True):
    meny = "".join(f'<a href="{f}" class="{"aktiv" if f == aktiv else ""}"><span>{i}</span>{n}</a>' for f, i, n in SIDOR)
    return f"""<!DOCTYPE html>
<html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{escape(titel)} · ATG-boten</title>
{'<meta http-equiv="refresh" content="300">' if uppdatera else ''}
<link rel="manifest" href="manifest.json"><link rel="apple-touch-icon" href="ikon.png"><link rel="icon" href="ikon.png">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#16261d">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700&family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="top"><div class="top-in"><span class="brand">{escape(titel)}</span><small>Uppdaterad {escape(uppdaterad)}</small></div></div>
<main>{innehall}</main>
<nav class="bottom"><div>{meny}</div></nav>
</body></html>"""


# ---------------- Sida: Lopp (dagens program) ----------------
def _starter_html(h, lopp_klart):
    info = [f'<b>{escape(h["kusk"])}</b>' + (f' · tr. {escape(h["tranare"])}' if h.get("tranare") else "")]
    rad2 = [f'{escape(h.get("kon",""))} {h.get("alder","")} år', f'spår {h["spar"]}' + (f' · {h["avstand"]} m' if h.get("avstand") else "")]
    if h.get("rekord"):
        rad2.append(f'rek {escape(h["rekord"])}')
    info.append(" · ".join(rad2))
    rad3 = []
    if h.get("form"):
        rad3.append(f'form <b>{escape(h["form"])}</b>')
    if h.get("vila") is not None:
        rad3.append(f'{h["vila"]:.0f} d vila')
    if h.get("starter"):
        rad3.append(f'{h["starter"]} st {h.get("seg","")}')
    if h.get("intjanat"):
        rad3.append(kr(h["intjanat"]))
    if h.get("skor"):
        rad3.append(escape(h["skor"]))
    info.append(" · ".join(rad3))
    taggar = ""
    if h.get("rorelse") is not None and abs(h["rorelse"]) >= 0.1:
        taggar += ' <span class="tag up">▲ spelas ner</span>' if h["rorelse"] > 0 else ' <span class="tag down">▼ spelas upp</span>'
    if h.get("ai"):
        taggar += f' <span class="tag">AI {h["ai"]:+.0f}</span>'
    if h.get("varde") is not None and h["varde"] >= config.MIN_OVERVARDE and h["p"] >= config.MIN_SANNOLIKHET:
        taggar += f' <span class="tag up">värde {h["varde"]*100:+.0f} %</span>'
    plac = ""
    if lopp_klart and h.get("placering"):
        plac = f' <span class="chip {"vunnen" if h["placering"] == 1 else ""}">{h["placering"]:.0f}:a</span>'
    odds = f'<b>{h["odds"]:.2f}</b>' if h.get("odds") else "<b>–</b>"
    skala = 0.6
    return (f'<div class="starter{" vinst" if lopp_klart and h.get("placering") == 1 else ""}"><div class="srad">'
            f'<span class="nr">{h["nr"]}</span><div><b>{escape(h["hast"])}</b>{plac}{taggar}'
            f'<div class="sinfo">{"<br>".join(info)}</div>'
            f'<div class="bar" style="margin-top:7px"><i style="width:{min(h["p"]/skala,1)*100:.1f}%"></i>'
            f'<u style="left:{min(h.get("pm",0)/skala,1)*100:.1f}%"></u></div></div>'
            f'<div class="odds">{odds}odds<br><span style="color:var(--acc);font-weight:700">{h["p"]*100:.0f} %</span> boten</div>'
            f'</div>{_skal_html(h.get("skal"))}</div>')


def _tankar(pr):
    fav = next(h for h in pr["hastar"] if h["nr"] == pr["favorit"])
    mfav = next(h for h in pr["hastar"] if h["nr"] == pr["marknadsfavorit"])
    t = f'Boten tror mest på <b>{fav["nr"]} {escape(fav["hast"])}</b> ({fav["p"]*100:.0f} %).'
    if fav["nr"] != mfav["nr"]:
        t += f' Oddsen pekar i stället ut {mfav["nr"]} {escape(mfav["hast"])} ({mfav["pm"]*100:.0f} %).'
    else:
        t += f' Oddsen håller med ({fav["pm"]*100:.0f} %).'
    varde = [h for h in pr["hastar"] if h["nr"] in pr.get("varde", [])]
    if varde:
        t += " Värde: " + ", ".join(f'{h["nr"]} {escape(h["hast"])} (odds {h["odds"]:.1f}, chans {h["p"]*100:.0f} %)' for h in varde) + "."
    else:
        t += " Inget spelvärde just nu – oddsen stämmer ungefär."
    return t


def sida_lopp(program, uppdaterad):
    lopp = sorted((program or {}).get("lopp", {}).values(), key=lambda p: str(p["start"]))
    if not lopp:
        return skal("Dagens lopp", "lopp.html", uppdaterad, '<section><h2>Dagens lopp</h2><p class="empty">Programmet '
                    'fylls i när boten startar sitt första vaktpass för dagen (09:40).</p></section>')
    html = ('<section><h2>Dagens lopp</h2><p class="note">Alla svenska travlopp idag, som i programmet hos ett ombud. '
            'Tryck på ett lopp för startlistan. <b>Grön stapel</b> = botens chans, <b>gult streck</b> = vad oddsen säger. '
            '✓ och ✗ visar vad som drar upp eller ner just den hästen jämfört med de andra.</p>')
    for bana in dict.fromkeys(p["bana"] for p in lopp):
        html += f'<p class="dag">{escape(bana)}</p>'
        for pr in [p for p in lopp if p["bana"] == bana]:
            klart = pr.get("status") == "results"
            vinn = next((h for h in pr["hastar"] if h.get("placering") == 1), None)
            fav = next(h for h in pr["hastar"] if h["nr"] == pr["favorit"])
            if klart and vinn:
                rank = sorted(pr["hastar"], key=lambda h: -h["p"]).index(vinn) + 1
                rad = (f'Vann: <b>{vinn["nr"]} {escape(vinn["hast"])}</b> – '
                       + ("✅ botens favorit" if rank == 1 else f"botens {rank}:a val"))
            else:
                rad = f'Tror på <b>{fav["nr"]} {escape(fav["hast"])}</b> ({fav["p"]*100:.0f} %)'
                if pr.get("varde"):
                    rad += ' · <span class="tag up">värdespel finns</span>'
            html += (f'<details class="race"><summary><div class="rhead"><h3>Lopp {pr["nr"]}</h3>'
                     f'<span class="time">{str(pr["start"])[11:16]}</span></div>'
                     f'<p class="note" style="margin:2px 0 0">{pr["distans"]} m {pr["startmetod"]} · {pr["antal"]} hästar</p>'
                     f'<p class="plain" style="margin-top:4px">{rad}</p></summary><div class="rbody">'
                     f'<p class="note" style="margin-top:10px">{escape(pr.get("namn",""))}</p>'
                     f'<p class="plain">💭 {_tankar(pr)}</p>'
                     + "".join(_starter_html(h, klart) for h in sorted(pr["hastar"], key=lambda h: h["nr"]))
                     + '</div></details>')
    return skal("Dagens lopp", "lopp.html", uppdaterad, html + "</section>")


# ---------------- Sida: Veckan ----------------
def sida_vecka(vecka, uppdaterad):
    spel = (vecka or {}).get("spel", [])
    dagnamn = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
    html = ('<section><h2>Veckans V-spel</h2><p class="note">Kommande V-omgångar på svenska banor. Startlistorna '
            'kommer ut några dagar innan, så omgångar längre fram kan saknas än. Chanserna är tidiga – oddsen '
            'har knappt börjat röra sig – och blir skarpare närmare start.</p>')
    if not spel:
        html += '<p class="empty">Veckovyn fylls i under nästa vaktpass.</p>'
    for dag in dict.fromkeys(a["dag"] for a in spel):
        d = datetime.fromisoformat(dag)
        html += f'<p class="dag">{dagnamn[d.weekday()].capitalize()} {d.day}/{d.month}</p>'
        for an in [a for a in spel if a["dag"] == dag]:
            sy = an["system"]["Balanserad"]
            jp = f' · 🎰 jackpott {kr(an["jackpott"])}' if an.get("jackpott") else ""
            spikar = [a for a in an["avdelningar"] if a["spik"]]
            html += (f'<details class="race"><summary><div class="rhead"><h3>{escape(an["typ"])} · {escape(an["bana"])}</h3>'
                     f'<span class="time">{str(an["start"])[11:16]}</span></div>'
                     f'<p class="note" style="margin:2px 0 0">{len(an["avdelningar"])} avdelningar{jp}</p>'
                     f'<p class="plain" style="margin-top:4px">{"Spikkandidat" if len(spikar)==1 else "Spikkandidater"}: '
                     + (", ".join(f'avd {a["avd"]}: <b>{a["hastar"][0]["nr"]} {escape(a["hastar"][0]["hast"])}</b>' for a in spikar) or "inga än")
                     + f'</p></summary><div class="rbody">'
                     f'<p class="plain" style="margin-top:10px">Botens förslag: <b>{sy["rader"]:.0f} rader för {kr(sy["kostnad"])}</b></p>'
                     f'<div class="sys">{escape(sy["val"].replace("/", " / "))}</div>'
                     f'<p class="note">Värdeindex {sy["vardeindex"]:.2f} (behövs ~{an["kravs"]:.2f}). Grön stapel = botens chans, '
                     f'gult streck = andel som spelat hästen. Grönt förbi gult = understreckad.</p>')
            for a in an["avdelningar"]:
                topp = a["hastar"][:5]
                skala = max(max(h["p"] for h in topp), max(h["streck"] for h in topp), 0.01)
                html += f'<p class="kicker" style="margin:16px 0 2px">Avd {a["avd"]} (lopp {a["lopp_nr"]}){" · spikkandidat" if a["spik"] else ""}</p>'
                for h in topp:
                    under = f'<div class="sinfo" style="margin-left:36px">{escape(h.get("kusk",""))}' + \
                            (f' · form {escape(h["form"])}' if h.get("form") else "") + '</div>'
                    html += _hast_rad(h["nr"], h["hast"], h["p"], h["streck"], skala) + under + \
                        (f'<div style="margin-left:36px">{_skal_html(h.get("skal"))}</div>' if h.get("skal") else "")
            html += "</div></details>"
    return skal("Veckan", "vecka.html", uppdaterad, html + "</section>")


# ---------------- Sida: Utveckling ----------------
def sida_utveckling(df, data_dir, rapport, uppdaterad):
    html = ('<section><h2>Botens utveckling</h2><p class="note">Här ser du om boten blir bättre. Allt bygger på '
            'låtsaspengar och på lopp som avgjorts efter att boten bestämt sig.</p>')
    r = df[df.status.isin(["vunnen", "förlorad"])].copy() if not df.empty else df
    # 1. Kassan
    if len(r) >= 2:
        r["netto"] = r.utbetalning - r.insats
        r = r.sort_values("skapad")
        r["dag"] = r.skapad.astype(str).str[:10]
        per_dag = r.groupby("dag").netto.sum()
        kassa = config.BANKRULLE_START + per_dag.cumsum()
        etik = [d[5:].replace("-", "/") for d in per_dag.index]
        tab = "".join(f'<tr><td>{d}</td><td>{n:+.0f}</td><td>{k:.0f}</td></tr>' for d, n, k in zip(etik, per_dag, kassa))
        tabell = f'<table><tr><th>Dag</th><th>Netto</th><th>Kassa</th></tr>{tab}</table>'
        html += figur("Kassan dag för dag", f"Streckad linje = startkassan {kr(config.BANKRULLE_START)}.",
                      linjediagram(["start"] + etik, [("Kassan", [config.BANKRULLE_START] + list(kassa), "--s1", False)],
                                   nollinje=config.BANKRULLE_START), tabell)
        html += figur("Vinst eller förlust per dag", "Grönt = plusdag, rött = minusdag.",
                      stapeldiagram(etik, list(per_dag)), tabell)
        # per speltyp
        g = r.groupby("typ").agg(insats=("insats", "sum"), tillbaka=("utbetalning", "sum"), antal=("insats", "size"))
        g["roi"] = (g.tillbaka - g.insats) / g.insats * 100
        tab = "".join(f'<tr><td>{escape(TYPNAMN.get(t, t))}</td><td>{x.antal:.0f}</td><td>{x.roi:+.0f} %</td></tr>'
                      for t, x in g.iterrows())
        html += figur("Avkastning per speltyp", "Hur mycket varje spelform gett tillbaka per satsad krona.",
                      stapeldiagram([TYPNAMN.get(t, t).replace(" (korspool)", "*") for t in g.index], list(g.roi),
                                    fmt=lambda v: f"{v:+.0f} %"),
                      f'<table><tr><th>Spel</th><th>Antal</th><th>Avkastning</th></tr>{tab}</table>')
    else:
        html += '<div class="figur"><h3>Kassan dag för dag</h3><p class="empty">Graferna över kassan dyker upp när boten har avgjorda spel.</p></div>'

    # 2. Bot mot oddsen (från prognosloggen)
    pf, rf = Path(data_dir) / "prognoser.csv", Path(data_dir) / "resultat.csv"
    if pf.exists() and rf.exists():
        pr = pd.read_csv(pf).drop_duplicates(["lopp_id", "nr"], keep="last").merge(pd.read_csv(rf), on="lopp_id")
        pr["vann"] = (pr.nr == pr.vinnare).astype(int)
        lopp_n = pr.lopp_id.nunique()
        if lopp_n >= 5:
            vin = pr[pr.vann == 1].copy()
            vin["vecka"] = pd.to_datetime(vin.datum).dt.strftime("v%V")
            fav_b = pr.loc[pr.groupby("lopp_id").p.idxmax()].assign(vecka=lambda d: pd.to_datetime(d.datum).dt.strftime("v%V"))
            fav_m = pr.loc[pr.groupby("lopp_id").pm.idxmax()].assign(vecka=lambda d: pd.to_datetime(d.datum).dt.strftime("v%V"))
            veckor = sorted(vin.vecka.unique())
            bot = [fav_b[fav_b.vecka == v].vann.mean() * 100 for v in veckor]
            mark = [fav_m[fav_m.vecka == v].vann.mean() * 100 for v in veckor]
            fordel = (math.exp(np.mean(np.log(vin.p.clip(1e-6))) - np.mean(np.log(vin.pm.clip(1e-6)))) - 1) * 100
            tab = "".join(f'<tr><td>{v}</td><td>{b:.0f} %</td><td>{m:.0f} %</td></tr>' for v, b, m in zip(veckor, bot, mark))
            html += figur("Hur ofta vinner favoriten?",
                          f"Botens favorit (heldragen) mot oddsfavoriten (streckad), per vecka. Totalt {lopp_n} lopp. "
                          f"Botens chanser på vinnarna var i snitt <b>{fordel:+.1f} %</b> {'bättre' if fordel >= 0 else 'sämre'} än oddsens.",
                          linjediagram(veckor, [("Boten", bot, "--s1", False), ("Oddsen", mark, "--s2", True)],
                                       fmt=lambda v: f"{v:.0f} %"),
                          f'<table><tr><th>Vecka</th><th>Botens favorit</th><th>Oddsfavorit</th></tr>{tab}</table>')
            gr = pd.cut(pr.p, [0, .05, .1, .2, .3, .45, 1])
            kal = pr.groupby(gr, observed=True).agg(p=("p", "mean"), f=("vann", "mean"), n=("vann", "size"))
            kal = kal[kal.n >= 5]
            tab = "".join(f'<tr><td>{x.p*100:.0f} %</td><td>{x.f*100:.0f} %</td><td>{x.n}</td></tr>' for _, x in kal.iterrows())
            html += figur("Stämmer botens chanser?",
                          "Varje prick är en grupp hästar. Sa boten 20 % borde ungefär var femte vinna. Prickar nära "
                          "den streckade linjen betyder att boten är ärlig om sina chanser.",
                          kalibrering(list(zip(kal.p, kal.f, kal.n))),
                          f'<table><tr><th>Boten sa</th><th>Vann</th><th>Hästar</th></tr>{tab}</table>')
        else:
            html += f'<div class="figur"><h3>Boten mot oddsen</h3><p class="empty">{lopp_n} lopp avgjorda hittills – graferna kommer efter 5.</p></div>'
    else:
        html += '<div class="figur"><h3>Boten mot oddsen</h3><p class="empty">Fylls i när boten gjort sina första prognoser på riktiga lopp.</p></div>'

    # 3. Modellens test över tid
    hf = Path(data_dir) / "rapporthistorik.json"
    hist = json.loads(hf.read_text(encoding="utf-8")) if hf.exists() else []
    if hist:
        etik = [h["datum"][5:].replace("-", "/") for h in hist]
        ford = [(math.exp(h["loglik_bot"] - h["loglik_marknad"]) - 1) * 100 for h in hist]
        tab = "".join(f'<tr><td>{e}</td><td>{h["antal_lopp"]}</td><td>{f:+.2f} %</td></tr>' for e, h, f in zip(etik, hist, ford))
        html += figur("Försprång mot oddsen vid varje träning",
                      "Varje måndag tränar boten om och testas på lopp den aldrig sett. Över noll = bättre än oddsen.",
                      linjediagram(etik, [("Försprång", ford, "--s1", False)], fmt=lambda v: f"{v:+.1f} %", nollinje=0),
                      f'<table><tr><th>Datum</th><th>Lopp</th><th>Försprång</th></tr>{tab}</table>')

    # 4. Vad den tittar på
    if rapport:
        vikter = sorted(rapport.get("vikter", {}).items(), key=lambda t: -abs(t[1]))[:10]
        vrad = "".join(f'<li><span>{escape(ETIKETT.get(k, k))}</span><span class="r {"up" if w > 0 else "down"}">'
                       f'{"ökar" if w > 0 else "minskar"} chansen</span></li>' for k, w in vikter)
        html += f'<div class="figur"><h3>Det boten tittar mest på</h3><ul class="list">{vrad}</ul></div>'

    # 5. AI-forskaren
    bokfil, planfil = Path(data_dir) / "labbdagbok.json", Path(data_dir) / "forskning_plan.json"
    bok = json.loads(bokfil.read_text(encoding="utf-8")) if bokfil.exists() else []
    plan = json.loads(planfil.read_text(encoding="utf-8")) if planfil.exists() else None
    forsk = ""
    if plan:
        forsk += f'<li><span>⏳ {escape(plan["text"])}</span><span class="r note">planerad</span></li>'
    for b in reversed(bok[-8:]):
        forsk += (f'<li><span>{escape(b["text"])}<br><span class="note">{escape(b["datum"])} · bättre {b["battre_manader"]} av '
                  f'{len(b["manader"])} månader</span></span><span class="r"><span class="chip {"vunnen" if b["infors"] else "förlorad"}">'
                  f'{"infört" if b["infors"] else "förkastat"}</span></span></li>')
    html += ('<div class="figur"><h3>AI-forskaren</h3><p class="note">Varje måndag testas en idé. Reglerna laddas upp innan '
             f'testet körs, så slumpen inte kan lura boten.</p>{f"<ul class=list>{forsk}</ul>" if forsk else "<p class=empty>Första testet körs på måndag förmiddag.</p>"}</div>')
    return skal("Utveckling", "utveckling.html", uppdaterad, html + "</section>")


# ---------------- Sida: Arenan (flera bottar mot varandra) ----------------
def _pct_tecken(x):
    return f"{x * 100:+.0f} %"


def sida_arena(df, gissn, uppdaterad):
    import arena
    antal = len(arena.BOTTAR) - sum(1 for b in arena.BOTTAR if b["baslinje"])
    html = (f'<section><h2>Arenan</h2><p class="lede">{antal} bottar lär sig och spelar på olika sätt, på exakt samma '
            f'lopp. Alla satsar {arena.INSATS} kr med låtsaspengar strax före start. 📏 Favoriten och 🎲 Slumpen är '
            f'måttstockar: en bot är bara intressant om den slår båda.</p>'
            '<div class="warn"><b>Var försiktig med vinnarna.</b> När många bottar tävlar blir någon bäst av ren tur. '
            f'Lita först på en bot som leder över minst 300 spel och flera veckor. Under {arena.MIN_SPEL_FOR_DOM} rättade '
            'spel är siffrorna mest slump.</div>')
    # 0. Vem gissar bäst? (alla lopp, inte bara de man spelat på)
    if gissn:
        skala_g = min(max([3.0] + [abs(g["fors"]) * 100 for g in gissn if g["nyckel"] != "fundamental"]), 10.0)
        rg = ""
        for g in gissn:
            bredd = min(abs(g["fors"]) * 100 / skala_g, 1) * 50
            spann = f' title="{g["lopp"]} lopp, slumpspann ±{2 * g["se"] * 100:.1f} %"' if g["se"] is not None else ""
            rg += (f'<div class="rb{" bas" if g["nyckel"] == "fundamental" else ""}"><span>{escape(g["namn"])}</span>'
                   f'<div class="zon"{spann}><i class="{"plus" if g["fors"] >= 0 else "minus"}" style="width:{bredd:.1f}%"></i></div>'
                   f'<span class="v"><span class="{"up" if g["fors"] >= 0 else "down"}">{g["fors"] * 100:+.1f} %</span></span></div>')
        n_lopp = max(g["lopp"] for g in gissn)
        ses = [g["se"] for g in gissn if g["nyckel"] != "fundamental" and g["se"] is not None]
        spann_text = f" Slumpens spelrum är just nu ungefär ±{2 * min(ses) * 100:.1f} procentenheter." if ses else ""
        html += ('<div class="figur"><h3>Vem gissar vinnaren bäst?</h3><p class="note">Varje modell jämförs med oddsen på alla '
                 f'{n_lopp} lopp som avgjorts. 0 % = lika bra som oddsen, plus = bättre. Det här är det säkraste måttet, '
                 f'eftersom varje lopp räknas och inte bara de man satsat på.{spann_text}</p>' + rg + '</div>')
    else:
        html += ('<div class="figur"><h3>Vem gissar vinnaren bäst?</h3><p class="empty">Fylls i när de första loppen har '
                 'avgjorts efter att bottarna gissat.</p></div>')
    if df.empty or not len(df):
        return skal("Arenan", "arena.html", uppdaterad, html + '<p class="empty">Inga spel ännu. Bottarna spelar '
                    'första gången strax före nästa svenska travlopp.</p></section>')
    tavla = arena.sammanfatta(df)

    # 1. Rangordning: avkastning per bot
    rangordnade = sorted(tavla, key=lambda t: (t["roi"] is None, -(t["roi"] or 0)))
    skala = max([30.0] + [abs(t["roi"]) * 100 for t in tavla if t["roi"] is not None])
    skala = min(skala, 100.0)
    rader = ""
    for t in rangordnade:
        if t["roi"] is None:
            zon, v = "", '<span class="note">–</span>'
        else:
            bredd = min(abs(t["roi"]) * 100 / skala, 1) * 50
            zon = f'<i class="{"plus" if t["roi"] >= 0 else "minus"}" style="width:{bredd:.1f}%"></i>'
            v = f'<span class="{"up" if t["roi"] >= 0 else "down"}">{_pct_tecken(t["roi"])}</span>'
        rader += (f'<div class="rb{" bas" if t["baslinje"] else ""}"><span>{t["ikon"]} {escape(t["namn"])}</span>'
                  f'<div class="zon" title="{t["rattade"]} rättade spel">{zon}</div><span class="v">{v}</span></div>')
    html += ('<div class="figur"><h3>Avkastning per satsad krona</h3><p class="note">Grönt är plus, rött är minus. '
             'ATG tar 15 % av varje krona, så en bot som spelar blint hamnar kring −15 %.</p>' + rader + '</div>')

    # 2. Tabell
    tab = ""
    for t in rangordnade:
        spann = f' <span class="note">±{2 * t["se"] * 100:.0f}</span>' if t["se"] is not None else ""
        roi = _pct_tecken(t["roi"]) if t["roi"] is not None else "–"
        traff = f'{t["traff"] * 100:.0f} %' if t["traff"] is not None else "–"
        tab += (f'<tr><td>{t["ikon"]} {escape(t["namn"])}</td><td>{t["rattade"]}</td><td>{traff}</td>'
                f'<td>{roi}{spann}</td><td>{t["netto"]:+.0f}</td></tr>')
    html += ('<div class="figur"><h3>Ställning</h3><p class="note">Rättade spel, andel träffar och avkastning. '
             '± är slumpens spelrum: ligger botens avkastning inom det är skillnaden mot noll inte bevisad.</p>'
             f'<table class="nw"><tr><th>Bot</th><th>Spel</th><th>Träff</th><th>Avkastning</th><th>Netto kr</th></tr>{tab}</table></div>')

    # 3. Kassa dag för dag för de bästa och måttstockarna
    r = df[df.status.isin(["vunnen", "förlorad"])].copy()
    if len(r):
        r["dag"] = r.skapad.astype(str).str[:10]
        r["netto"] = r.utbetalning - r.insats
        dagar = sorted(r.dag.unique())
        if len(dagar) >= 2:
            bast = [t for t in rangordnade if not t["baslinje"] and t["roi"] is not None][:3]
            valda = bast + [t for t in tavla if t["baslinje"] and t["roi"] is not None]
            farger = {"favoriten": "--s5", "slumpen": "--s5"}
            fargvar = iter(["--s1", "--s2", "--s3", "--s4"])
            serier = []
            for t in valda:
                per = r[r.bot == t["nyckel"]].groupby("dag").netto.sum().reindex(dagar, fill_value=0).cumsum()
                serier.append((t["namn"], [float(v) for v in per], farger.get(t["nyckel"]) or next(fargvar), t["baslinje"]))
            etik = [d[5:].replace("-", "/") for d in dagar]
            tabell = "".join(f'<tr><td>{n}</td><td>{v[-1]:+.0f}</td></tr>' for n, v, _, _ in serier)
            html += figur("Vinst och förlust över tid",
                          "Hur många låtsaskronor varje bot tjänat eller förlorat sammanlagt. De tre bästa botarna och måttstockarna (streckade).",
                          linjediagram(etik, serier, fmt=lambda v: f"{v:+.0f}", nollinje=0),
                          f'<table><tr><th>Bot</th><th>Netto kr</th></tr>{tabell}</table>')

    # 4. Så tänker varje bot
    tank = ""
    for t in tavla:
        text, klass = arena.dom(t, tavla)
        tank += (f'<details><summary>{t["ikon"]} {escape(t["namn"])} <span class="chip {klass}">{escape(text)}</span></summary>'
                 f'<p>{escape(t["forklaring"])}</p></details>')
    html += f'<div class="figur"><h3>Så tänker varje bot</h3>{tank}</div>'

    # 5. Senaste spelen
    senaste = df.sort_values("skapad", kind="stable").tail(14).iloc[::-1]
    rad = ""
    for _, x in senaste.iterrows():
        b = arena.NAMN.get(x.bot, {"ikon": "", "namn": x.bot})
        chip = f'<span class="chip {x.status}">{escape(str(x.status))}</span>'
        rad += (f'<li><span>{b["ikon"]} {escape(b["namn"])} · lopp {escape(str(x.lopp_id).split("_")[-1])}<br>'
                f'<span class="note">{int(x.nr)} {escape(str(x.hast))} · odds {x.odds:.2f}</span></span>'
                f'<span class="r">{chip}</span></li>')
    html += f'<div class="figur"><h3>Senaste spelen</h3><ul class="list">{rad}</ul></div>'
    return skal("Arenan", "arena.html", uppdaterad, html + "</section>")


# ---------------- Sida: Hjälp ----------------
def sida_hjalp(uppdaterad):
    fragor = [
        ("Vad gör boten?", f"Tre gånger om dagen (09:40, 14:10, 18:40) startar den ett vaktpass. Från 30 minuter före varje "
         f"svenskt travlopp kollar den oddsen varje minut. {config.SPELA_FORE_MIN} minuter före start räknar den ut varje hästs chans "
         "och spelar med låtsaspengar om oddset är för bra för att stämma. Efter loppet rättar den sig själv."),
        ("Hur läser jag startlistan?", "Varje häst visar kusk och tränare, kön och ålder, spår och distans, rekord (km-tid, "
         "a = autostart, M/L/K = medel/lång/kort distans), form (senaste placeringarna, nyast först: 0 = oplacerad, "
         "g = galopp, d = diskad), dagar sedan senaste start, antal starter med segrar-andra-tredje, intjänat och skor. "
         "Till höger står oddset och botens chans."),
        ("Vad betyder ✓ och ✗?", "Det är botens skäl. ✓ drar upp chansen och ✗ drar ner den, jämfört med de andra hästarna "
         "i samma lopp. Till exempel '✓ toppkusk' eller '✗ har tillägg'. Boten väger också in oddsen, så skälen förklarar "
         "varför den ibland tror mer eller mindre än marknaden."),
        ("Odds", "Hur mycket du får tillbaka per krona. Odds 4,00 betyder att 10 kr blir 40 kr om du vinner."),
        ("Chans och värde", f"Har en häst 30 % chans men odds 4,00 får du i snitt tillbaka 0,30 × 4 = 1,20 kr per satsad krona, "
         f"alltså +20 % värde. Boten spelar bara när värdet är minst {config.MIN_OVERVARDE*100:.0f} %."),
        ("Vinnare, Plats, Trio, Tvilling", "Vinnare: hästen ska vinna. Plats: topp 3 (topp 2 om 5–7 hästar startar). "
         "Tvilling: två hästar blir etta och tvåa i valfri ordning. Trio: tre hästar i exakt rätt ordning."),
        ("🔀 Korspool", "ATG har en pott för varje spelform. Ibland är potterna oense, till exempel betalar Plats mer än "
         "vinnaroddsen säger att den borde. Då spelar boten utan att behöva lita på sin egen spådom."),
        ("▲ Spelas ner", "Oddset har sjunkit de senaste minuterna, alltså strömmar pengar in på hästen. Sena pengar kommer ofta "
         "från folk som vet något. ▼ betyder tvärtom."),
        ("AI-betyg", "Claude läser ATG:s korta kommentar om hästen och ger −2 till +2."),
        ("Streck och spikkandidat", "Streck = hur stor andel av V-spelarna som valt hästen. Har en häst högre chans än streck "
         "är den understreckad, och vinner den delar färre på potten. Spikkandidat = boten ger hästen minst 45 % chans."),
        ("Värdeindex och jackpott", "Hur mycket bättre botens V-system är än genomsnittsspelarens. ATG tar 35 % på V-spel, "
         "så det behövs ungefär 1,5 för att gå plus. På jackpottdagar finns extra pengar i potten och kravet blir lägre."),
        ("Grafen 'Stämmer botens chanser?'", "När boten säger 20 % ska ungefär var femte sådan häst vinna. Ligger prickarna "
         "nära den streckade linjen är boten ärlig om sina chanser."),
        ("Varför spelar boten så sällan?", "De flesta lopp saknar värde. ATG tar 15–35 % av varje insats, så den som spelar "
         "på allt förlorar. Att avstå är en del av strategin."),
        ("Vad är Arenan?", "Flera bottar spelar Vinnare på exakt samma lopp med 10 kr per spel och låtsaspengar. De skiljer sig "
         "åt i hur de lär sig (hård eller lös broms, bara färsk data, snitt av alla) och hur de väljer spel. Favoriten och "
         "Slumpen är måttstockar. Med många bottar blir någon bäst av ren tur, så lita bara på en som slår måttstockarna över "
         "många spel och flera veckor."),
        ("Notiser i mobilen", f"Starka spel (+{config.NOTIS_OVERVARDE*100:.0f} % eller mer) och dagens resultat kommer som notis "
         "i appen ntfy."),
    ]
    html = ('<section><h2>Hjälp och ordlista</h2>' + "".join(
        f"<details><summary>{escape(f)}</summary><p>{escape(s)}</p></details>" for f, s in fragor)
        + '<p class="note" style="margin-top:16px">Allt är låtsaspengar. De flesta som spelar på trav förlorar i längden. '
          'Spela ansvarsfullt – Stödlinjen 020-81 91 00.</p></section>')
    return skal("Hjälp", "hjalp.html", uppdaterad, html, uppdatera=False)


# ---------------- Sida: Översikt ----------------
def sida_oversikt(df, bank, status, program, nu, uppdaterad):
    rattade = df[df.status.isin(["vunnen", "förlorad"])] if not df.empty else df
    ins = float(rattade.insats.sum()) if len(rattade) else 0.0
    tillb = float(rattade.utbetalning.sum()) if len(rattade) else 0.0
    roi = (tillb - ins) / ins * 100 if ins else 0.0
    traff = (rattade.status == "vunnen").mean() * 100 if len(rattade) else 0.0
    oppna = int((df.status == "öppen").sum()) if not df.empty else 0
    diff = bank - config.BANKRULLE_START

    # Vad händer nu?
    try:
        senast = datetime.fromisoformat(status.get("senast", "2000-01-01 00:00"))
    except ValueError:
        senast = datetime(2000, 1, 1)
    if (nu - senast).total_seconds() < 15 * 60:
        nasta = status.get("nasta")
        nu_text = "🟢 <b>Boten vaktar just nu</b> och kollar oddsen varje minut."
        if nasta:
            nu_text += (f' Nästa lopp: <b>{escape(nasta["bana"])} lopp {nasta["nr"]} kl {str(nasta["start"])[11:16]}</b>. '
                        f'Den bestämmer sig {config.SPELA_FORE_MIN} min före start.')
    else:
        kl = nu.strftime("%H:%M")
        nasta_pass = next((t for t in ["09:40", "14:10", "18:40"] if t > kl), None)
        nu_text = f"😴 <b>Boten vilar.</b> Nästa vaktpass startar {'kl ' + nasta_pass if nasta_pass else 'i morgon kl 09:40'}."
    if oppna:
        nu_text += f" {oppna} spel väntar på resultat."
    idag = nu.date().isoformat()
    idag_df = df[df.skapad.astype(str).str.startswith(idag)] if not df.empty else df
    idag_r = idag_df[idag_df.status.isin(["vunnen", "förlorad"])] if len(idag_df) else idag_df
    if len(idag_r):
        n = idag_r.utbetalning.sum() - idag_r.insats.sum()
        nu_text += f' Idag: <b class="{"up" if n >= 0 else "down"}">{n:+,.0f} kr</b>.'.replace(",", " ")

    # Snart start
    def kommande(an):
        try:
            return datetime.fromisoformat(str(an["start"])[:19]) > nu
        except ValueError:
            return False
    lopp = sorted([a for a in status.get("lopp", {}).values() if kommande(a)], key=lambda a: a["start"])
    lopp_html = "".join(_lopp_kort(a) for a in lopp[:4]) or \
        '<p class="empty">Inga lopp inom 45 minuter just nu.</p>'
    system = sorted([a for a in status.get("system", {}).values() if kommande(a)], key=lambda a: a["start"])
    sys_html = "".join(_system_kort(a) for a in system[:2])

    # Dagens spel
    dagens = ""
    if len(idag_df):
        for _, r in idag_df.sort_values("skapad", ascending=False).iterrows():
            hast = r.kommentar if isinstance(r.kommentar, str) and "värdeindex" not in r.kommentar else ""
            res = (f'+{kr(r.utbetalning)}' if r.status == "vunnen" else
                   (f'−{kr(r.insats)}' if r.status == "förlorad" else kr(r.insats)))
            dagens += (f'<li><span>{kr(r.insats)} på {_klartext(r.typ, r.val, hast)}<br><span class="note">'
                       f'{escape(TYPNAMN.get(str(r.typ), str(r.typ)))} · {escape(_plats_text(r))} · {str(r.skapad)[11:16]}</span></span>'
                       f'<span class="r"><span class="chip {r.status}">{r.status}</span><br>{res}</span></li>')
    dagens = f'<ul class="list">{dagens}</ul>' if dagens else '<p class="empty">Inga spel ännu idag.</p>'

    # Hur gick botens favoriter idag?
    favtext = ""
    klara = [p for p in (program or {}).get("lopp", {}).values() if p.get("status") == "results"
             and any(h.get("placering") == 1 for h in p["hastar"])]
    if klara:
        ratt = sum(1 for p in klara if next(h for h in p["hastar"] if h["nr"] == p["favorit"]).get("placering") == 1)
        favtext = (f'<p class="plain" style="margin-top:14px">🎯 Botens favorit har vunnit <b>{ratt} av {len(klara)}</b> '
                   f'avgjorda lopp idag.</p>')

    html = f"""<section>
<div class="nu">{nu_text}</div>
<p class="kicker" style="margin-top:18px">Låtsaskassan · startade med {kr(config.BANKRULLE_START)}</p>
<h1>{kr(bank)}</h1>
<p class="lede"><b class="{"up" if diff >= 0 else "down"}">{diff:+,.0f} kr</b> sedan start</p>
<div class="stats"><div class="stat"><b class="{"up" if roi >= 0 else "down"}">{roi:+.0f} %</b><span>Avkastning</span></div>
<div class="stat"><b>{len(rattade)}</b><span>Avgjorda spel</span></div>
<div class="stat"><b>{traff:.0f} %</b><span>Andel vinster</span></div></div>
{_kurva(df) if not df.empty else ''}
{favtext}
<a class="knapp" href="utveckling.html">Se hela utvecklingen →</a>
</section>
<section><h2>Snart start</h2>
<p class="note">Botens nästa beslut. Den spelar bara när ATG:s odds är minst {config.MIN_OVERVARDE*100:.0f} % bättre än chansen motiverar.</p>
<div class="cards">{lopp_html}{sys_html}</div>
<a class="knapp" href="lopp.html">Alla lopp idag med startlistor →</a></section>
<section><h2>Dagens spel</h2>{dagens}</section>
<section><p class="note">Allt är låtsaspengar. Först efter ca 200 avgjorda spel går det att säga om boten är bra.</p></section>""".replace(",", ",")
    return skal("ATG-boten", "index.html", uppdaterad, html)


# ---------------- Bygg alla sidor ----------------
def bygg(data_dir="data", ut="docs/index.html"):
    from motor import nu as _nu
    mapp = Path(ut).parent
    mapp.mkdir(parents=True, exist_ok=True)
    kassa = Papperskassa(data_dir)
    df = kassa.df.copy()
    bank = kassa.bankrulle()
    las = lambda f: json.loads((Path(data_dir) / f).read_text(encoding="utf-8")) if (Path(data_dir) / f).exists() else {}
    status, program, vecka = las("idag.json"), las("program.json"), las("vecka.json")
    rf = Path("models/rapport.json")
    rapport = json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else {}
    import arena
    arena_df, arena_gissn = arena.las(data_dir), arena.gissning(data_dir)
    nu = _nu()
    uppd = status.get("senast", nu.strftime("%Y-%m-%d %H:%M"))
    if program.get("datum") != nu.date().isoformat():
        program = {}
    sidor = {
        "index.html": sida_oversikt(df, bank, status, program, nu, uppd),
        "lopp.html": sida_lopp(program, uppd),
        "vecka.html": sida_vecka(vecka, vecka.get("skapad", uppd)),
        "arena.html": sida_arena(arena_df, arena_gissn, uppd),
        "utveckling.html": sida_utveckling(df, data_dir, rapport, uppd),
        "hjalp.html": sida_hjalp(uppd),
    }
    for namn, html in sidor.items():
        (mapp / namn).write_text(html, encoding="utf-8")
    manifest = mapp / "manifest.json"
    if not manifest.exists():
        manifest.write_text(json.dumps({"name": "ATG-boten", "short_name": "ATG-boten", "start_url": ".",
                                        "display": "standalone", "background_color": "#f1f4ef",
                                        "theme_color": "#16261d",
                                        "icons": [{"src": "ikon.png", "sizes": "512x512", "type": "image/png"}]}),
                            encoding="utf-8")
