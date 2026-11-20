# ATG-boten 🐎

En bot som lär sig trav från ATG:s egna data och föreslår spel där den tror att oddsen är för höga:

- **V-spel** (V85, V86, V64, V65, V5, V4, GS75, DD/LD): tre färdiga system per omgång
- **Vinnare / Plats:** värdespel med föreslagen insats
- **Trio / Tvilling:** kombinationer där ATG:s odds är högre än botens rättvisa odds

Boten spelar **bara med låtsaspengar** och rättar sig själv. Läs `KUNSKAP.md` för allt den vet.

> Boten levereras redan tränad på flera månaders svenska travlopp. Du kan köra `tips` direkt.

---

## Appen (körs automatiskt på GitHub)

GitHub kör boten i tre vaktpass per dag: 09:40, 14:10 och 18:40, 4,5 timmar vardera. Under passen kollar boten varje minut:

- **Oddsrörelser:** från 30 min före start loggas vinnaroddsen varje minut. Hästar som spelas ner ("smarta pengar") syns i appen och påverkar chansen.
- **AI-betyg:** Claude läser ATG:s kommentar om varje häst och ger −2 till +2. Kräver hemligheten `ANTHROPIC_API_KEY`.
- **Spel i sista minuten:** 3 min före start räknar boten och pappersspelar Vinnare, Plats, Trio och Tvilling med övervärde.
- **Korspool:** spel där ATG:s potter är oense med varandra, oberoende av botens egen spådom.
- **V-spel bara på jackpott:** jackpotten sänker kravet på värdeindex. Utan jackpott visas systemen bara.
- **Notiser:** starka spel (+30 %) och dagens resultat skickas till mobilen via appen ntfy. Kräver hemligheten `NTFY_AMNE`.
- **Måndagar:** boten hämtar förra veckans lopp och tränar om. AI-forskaren skriver ner veckans hypotes och regler, laddar upp dem och testar sedan. Ändringar förs bara in om de vinner enligt de förregistrerade reglerna.

Appen: https://fredriklofsten.github.io/atg-bot/ – välj "Lägg till på hemskärmen" i mobilen.

### Hemligheter (Settings → Secrets and variables → Actions → New repository secret)
| Namn | Värde | Behövs för |
|---|---|---|
| `ANTHROPIC_API_KEY` | samma nyckel som i tradingboten | AI-betyg av kommentarerna |
| `NTFY_AMNE` | ett hemligt ord, t.ex. `atg-fredrik-k7q2x9` | notiser. Prenumerera på samma ord i appen ntfy |

Boten fungerar utan dem. Då hoppar den bara över AI-betygen och notiserna.

Får du ett "issue" på GitHub om att boten kraschade: skicka länken till Claude.

## Kom igång på datorn (Windows)

1. **Installera Python** från python.org (3.10 eller nyare). Kryssa i **"Add Python to PATH"** under installationen.
2. **Packa upp** mappen `atg-bot`, till exempel på skrivbordet.
3. Öppna mappen, klicka i adressfältet, skriv `cmd` och tryck Enter. Ett svart fönster öppnas.
4. Installera det boten behöver (görs en gång):
   ```
   pip install -r requirements.txt
   ```
5. Se dagens förslag:
   ```
   python bot.py tips
   ```

*(Mac: öppna Terminal, skriv `cd ` och dra in mappen, tryck Enter. Använd `python3` och `pip3`.)*

## Daglig rutin

| När | Kommando | Vad händer |
|---|---|---|
| Före loppen | `python bot.py tips --spara` | Visar förslag och lägger dem som pappersspel |
| Strax före start | `python bot.py tips --typ lopp` | Färskare odds = bättre förslag |
| Efter loppen | `python bot.py ratta` | Rättar och visar hur det går |
| När som helst | `python bot.py saldo` | Bankrulle och ROI per speltyp |
| En gång i veckan | `python bot.py samla --dagar 10` och sedan `python bot.py trana` | Boten lär sig av de senaste loppen |

Förslagen sparas också i `rapporter/tips_DATUM.md`.

## Fler val

```
python bot.py tips --budget 500            # större V-system (kr per system)
python bot.py tips --typ system            # bara V-spel
python bot.py tips --datum 2026-11-21      # annan dag
python bot.py tips --visa-alla             # visa även troligaste trio/tvilling
python bot.py utforska V85_2026-11-14_14_5 # titta i rådata
python bot.py samla --dagar 365            # mer historik = bättre modell (tar ~1–2 h första gången)
```

Allt annat ställer du in i `config.py`: bankrulle, hur säker boten ska vara (`MIN_OVERVARDE`), Kelly-andel, länder och mer.

## Filerna

| Fil | Innehåll |
|---|---|
| `bot.py` | Kommandona ovan |
| `atg_api.py` | Hämtar data från ATG och sparar en kopia i `data/raw/` |
| `features.py` | Gör om rådata till egenskaper (spår, kusk, form …) |
| `model.py` | Modellen som lär sig och testar sig själv |
| `strategy.py` | Övervärde, Kelly-insats, Harville, V-systembygge |
| `papper.py` | Låtsaskassan och rättning |
| `config.py` | Alla inställningar |
| `KUNSKAP.md` | Botens lärobok om trav och spel |

## Ärligt talat

Marknaden (alla andra spelare) är mycket svår att slå, och ATG tar 15–35 % av varje krona. De flesta som spelar förlorar i längden, även med datorhjälp. Se boten som ett lärorikt projekt och ett sätt att *mäta* om du har ett försprång. Lita på den först när pappersspelet har gått plus över **flera hundra spel**.

Spela ansvarsfullt. Stödlinjen: 020-81 91 00.
