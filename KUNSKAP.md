# Vad boten vet om trav och spel

Den här filen är botens "lärobok". Allt nedan finns också inbyggt i koden, främst i `features.py`, `model.py` och `strategy.py`.

---

## 1. Hur ATG-spel fungerar (poolspel)

- **Alla spelar mot varandra, inte mot ATG.** Insatserna läggs i en pott. ATG drar av sin del (vinstavdraget) och resten delas mellan dem som vann.
- **Vinstavdrag:** Vinnare/Plats ca 15 % (85 % tillbaka). V85/V86/V64 ca 35 % (65 % tillbaka). Boten läser ATG:s egen siffra (`returnToPlayer`) när den finns.
- **Konsekvens:** Om du spelar som genomsnittet förlorar du i snitt 15–35 % av allt du satsar. Du måste vara *bättre än de andra spelarna* med mer än avdraget för att gå plus.
- **Oddsen är inte låsta.** På Vinnare/Plats sätts slutoddset när loppet startar. Dessutom sänker din egen insats oddset lite.

## 2. Spelformerna

| Spel | Vad du ska pricka | Botens strategi |
|---|---|---|
| **Vinnare** | Vinnaren i ett lopp | Spela där chans × odds > 1,10 |
| **Plats** | Häst topp 3 (topp 2 vid 5–7 startande) | Samma, med Harvilles formel för topp 3-chans |
| **Tvilling** | Etta och tvåa, valfri ordning | Jämför botens chans med ATG:s odds för de mest spelade kombinationerna |
| **Trio** | Etta, tvåa, trea i rätt ordning | Samma som Tvilling |
| **V85 / V86 / V64 / V65 / V5 / V4 / GS75** | Vinnarna i alla avdelningar | Bygger system: jämför botens chans med streckprocenten |
| **DD / LD** | Vinnarna i två lopp | Samma som V-spel |

*(V75 ersattes av V85 den 25 oktober 2025.)*

## 3. Streck och odds – marknadens åsikt

- **Odds** (Vinnare): 1 / odds ≈ hur stor chans spelarna ger hästen (efter avdraget).
- **Streckprocent** (V-spel): andelen av alla system som har med hästen. 40 % streck = folket tror mycket på den.
- **Nyckeln till V-spel:** Du får betalt efter hur *få* som har din rad. En häst med 20 % chans men bara 8 % streck är **understreckad**, och det ger värde. En häst med 30 % chans men 55 % streck är **överstreckad**. Den vinner ofta men betalar dåligt.
- Botens **värdeindex** = genomsnittet av (botens chans / streck) i varje avdelning, multiplicerat över avdelningarna. 1,0 betyder att du är lika smart som snittspelaren. Vid 35 % avdrag krävs ungefär **1,54** för att gå plus i längden. Jackpottar och lägre vinstnivåer ändrar detta något.

## 4. Vad som avgör ett travlopp (botens egenskaper)

| Faktor | Varför den spelar roll | I koden |
|---|---|---|
| **Startmetod** | Autostart (bilstart) och voltstart ger olika fördelar | `auto` |
| **Spår vid autostart** | Spår 1–3 ger ofta ledning eller rygg ledaren. Spår 6–8 kostar meter i ytterspår. Spår 9+ startar i andra ledet | `spar_inner`, `spar_ytter`, `andra_led` |
| **Spår vid voltstart** | Ytterspår på volten är oftast sämre | `volt_spar_dalig` |
| **Tillägg** | Hästar med 20/40 m tillägg måste springa längre | `tillagg_20m` |
| **Ålder och kön** | 3-åringar är ojämna. Ston, hingstar och valacher skiljer sig | `alder`, `ar_3`, `hingst`, `sto` |
| **Intjänade pengar** | Mått på klass | `log_intjanat`, `log_per_start` |
| **Segerprocent / topp 3** | Hur ofta hästen presterar | `seger_pct`, `topp3_pct` (krympta mot snittet vid få starter) |
| **Årets form** | Färsk form är viktigare än gammal | `ar_seger_pct`, `ar_starter_log` |
| **Rekordtid (km-tid)** | Fart, jämförd med de andra i loppet | `rekord_km`, `rekord_rel` |
| **Kusk** | Toppkuskar vinner mycket oftare | `kusk_seger_pct` |
| **Tränare** | Formstall och träningsmetoder | `tranare_seger_pct` |
| **Barfota** | Barfota (utan skor) ger ofta mer fart. Skobyte är en signal från tränaren | `barfota_fram`, `barfota_bak`, `skobyte` |
| **Vagn** | Amerikansk vagn är ibland en "satsning" | `amerikansk_vagn` |
| **Snittodds senaste 5** | Vad marknaden tyckte förut | `log_snittodds5` |
| **Distans** | Vissa hästar är sprinters, andra stayers | `lang_distans`, `kort_distans` |

### Form och bana (från hästens resultatlista, bara lopp före dagens)
| Faktor | Varför | I koden |
|---|---|---|
| Dagar sedan senaste start | Lång vila (> 60 dagar) betyder ofta att hästen behöver ett lopp | `log_dagar_vila`, `lang_vila` |
| Galopp / diskning nyligen | Osäker häst, men ibland en spelchans när folket glömt den | `galopp_senaste`, `galopp_andel5`, `disk_senaste` |
| Placeringar senaste 5 | Aktuell form | `form5`, `seger_senaste` |
| Bästa km-tid senaste 5 | Aktuell fart jämfört med fältet | `km5_rel` |
| Odds senaste start | Vad marknaden trodde sist | `log_odds_senaste` |
| Barfota första gången | En klassisk "satsningssignal" från tränaren | `forsta_barfota` |
| Kuskbyte till toppkusk | Stallet tar in en bättre kusk = tror på hästen | `kuskbyte`, `kuskbyte_topp` |
| Banans skick | Tung bana eller vinterbana gynnar vissa hästar | `tung_bana`, `vinterbana` |
| Hemmabana | Hästen känner banan | `hemmabana` |

### Nya signaler i realtid
- **Oddsrörelse** (`rorelse`) = log(odds 12+ min före start / odds nu). Positivt = hästen spelas ner, alltså att pengar strömmar in. Sena pengar kommer ofta från folk som vet något.
- **AI-betyg** (`ai_poang`): Claude läser ATG:s statistikkommentar om hästen och sätter −2 till +2.
- De här signalerna har ingen historik ännu. Tills det finns minst 300 lopp med data använder boten en försiktig förhandsvikt (0,3 för rörelse, 0,08 per AI-poäng). Sedan lär modellen sig vikten själv.

## 5. Hur boten lär sig (modellen)

1. **Betingad logit (conditional logit):** varje häst får en poäng utifrån egenskaperna. Vinstchansen = häst­ens poäng jämfört med alla andra i *samma lopp* (softmax). Modellen justerar vikterna tills den förklarar de verkliga vinnarna så bra som möjligt.
2. **Kombinationssteg (Benter-metoden):** den egna chansen blandas med marknadens chans. Datan avgör blandningen. Marknaden är nästan alltid stark, så den får ofta stor vikt. Boten letar efter de lopp där den egna analysen säger något annat.
3. **Ärlig testning:** modellen tränas på äldre lopp och testas på nyare lopp som den aldrig sett, precis som i verkligheten.
4. **Mått:** "loglik" mäter hur bra chanserna stämmer (närmare 0 = bättre). Boten måste slå marknadens siffra för att ha en verklig fördel.

## 6. Från chans till satsning

- **Övervärde (EV)** = chans × odds − 1. Boten spelar bara om EV ≥ +10 % (ändras i `config.py`).
- **Rättvist odds** = 1 / chans. Är ATG:s odds högre än det rättvisa oddset finns värde.
- **Kelly-kriteriet:** optimal insatsandel = (chans × odds − 1) / (odds − 1). Full Kelly svänger våldsamt, så boten använder **25 % Kelly** och max 3 % av bankrullen per spel.
- **Harvilles formel:** chansen för en ordning, till exempel 3-7-1, beräknas ur vinstchanserna. Den används för Plats, Tvilling och Trio. Ren Harville överskattar favoriter på andra- och tredjeplats, så boten "plattar till" chanserna där (exponent 0,7 och 0,55, kalibrerat på svenska lopp).
- **V-system:** boten börjar med favoriten i varje avdelning. Den lägger sedan till den häst som ger mest träffchans och värde per extra krona tills budgeten är slut. Överstreckade hästar (chans/streck < 0,6) hoppas över. Tre varianter: Försiktig, Balanserad och Skrällvänlig.

- **Korspool:** samma häst har ett pris i Vinnare, Plats, Trio och Tvilling. Boten räknar om vinnaroddsen till chanser för Plats, Trio och Tvilling. Där en annan pott betalar minst 15 % mer än det motiverar spelar den, utan egen spådom.
- **Jackpott:** jackpotpengar läggs ovanpå potten. Kravet på värdeindex delas därför med (1 + jackpott / pottens storlek efter avdrag).
- **AI-forskaren:** varje måndag testas en hypotes, till exempel "formdatan tillför inget". Planen och regeln laddas upp innan testet körs. Ändringen förs bara in om den förbättrar i minst 4 av 5 månader och i snitt med minst 0,002.

## 7. Hur boten lär sig av förlorade spel

Varje avgjort spel, från huvudboten och från arenan, analyseras i `analys.py` och sparas i `data/spelanalys.csv`:

- **Var hästen kom och vem som vann.** Förlusten får en orsak: *nära* (precis utanför), *mitt i fältet*, *långt efter*, *galopp eller diskad*, *en skräll vann* eller *marknaden trodde mindre efter spelet*. Många "nära" betyder att boten var på rätt spår. Många "långt efter" betyder att den trodde fel.
- **Slutoddset (CLV):** jämför oddset när boten spelade med oddset vid start. Sjunker det har fler pengar kommit på samma häst, alltså höll marknaden med i efterhand. Det är det snabbaste måttet på om en bot är smart. Det syns efter några hundra spel, medan vinst och förlust kräver tusentals. Favoriter sjunker ofta lite ändå, så boten jämförs med 📏 Favoriten.
- **Lärdomar:** spelen delas in i grupper (speltyp, oddsnivå, hur mycket boten trodde mer än marknaden, oddsrörelse, startmetod, fältstorlek). I varje grupp jämförs antalet träffar med hur många boten själv räknade med. En skillnad räknas bara som lärdom om den är för stor för att vara slump (|z| ≥ 2,5, minst 30 spel). Gränsen är hög eftersom många grupper testas samtidigt och någon alltid ser konstig ut av ren tur.
- **Försiktighet:** träffar huvudboten mer sällan än den tror i en speltyp (minst 20 spel) sänks dess chans där: faktor = (träffar + 3) / (förväntade träffar + 3), aldrig under 0,5 och aldrig över 1. De tre "låtsasträffarna" gör att några få förluster bara ändrar lite. Boten blir alltså bara försiktigare, aldrig djärvare, av sina förluster.
- **Max ett Trio- och ett Tvillingspel per lopp** (`MAX_KOMBO_PER_LOPP`). Flera kombinationer i samma lopp hänger ihop: de ger mer slump men nästan ingen ny kunskap.

Kör `python bot.py lardomar` för att se analysen på datorn. I appen finns den under Utveckling.

## 8. Fallgropar boten känner till

- **Slumpen dominerar på kort sikt.** Du behöver hundratals spel innan resultatet säger något.
- **Favorit–långskott-bias:** långskott är ofta överspelade av allmänheten och favoriter något underspelade.
- **Sena oddsrörelser:** proffs spelar sent, så oddset 1 minut före start är mer träffsäkert än oddset på morgonen.
- **Strykningar** ändrar allt. Kör `tips` igen nära start.
- **Överanpassning:** för många egenskaper på för lite data ger en modell som ser bra ut på gamla lopp men misslyckas på nya. Därför används krympning (`L2_STRAFF`) och tidsuppdelad testning.

## 9. Spela ansvarsfullt

- Boten spelar bara med låtsaspengar. Den kan inte lägga riktiga spel, och ATG har inget öppet API för att spela.
- Testa minst 2–3 månader på papper innan du ens överväger riktiga pengar, och bara med pengar du har råd att förlora.
- Sätt gränser hos ATG (insatsgräns, tidsgräns). Stödlinjen: 020-81 91 00, stodlinjen.se.
