# Ověření původního showroomu na nativním backendu

5. 11. 2026 — **cíl autosalonu se zachovaným designem splněn**.

Spuštění: `bash start_showroom.sh`. Lokální instance byla spuštěná a ověřená
na `http://127.0.0.1:8765`: HTTP 200, `backend=maloni-native`, bez chyby.

## Výsledky

- 48 testů prošlo: 21 fyzika/bindings, 22 katalog/dialogy/assety/HTTP,
  5 nativní integrace showroomu. Integrační test výslovně zakazuje import MuJoCo.
- V Chromiu prošlo načtení všech tří původních aut, původního stylesheetu,
  živého stavu humanoida, rozhovoru u recepce, kamery robota a resetu.
  Nebyly zaznamenané chyby JavaScriptu, chybné HTTP odpovědi ani externí requesty.
- Prošla interaktivní návštěva: zákazník přišel, potvrdil doprovod, absolvoval
  tři části prezentace, dostal shrnutí a odešel k východu.
- Stop, odpojení klienta, reset a odmítnutí příkazu ze starého běhu prošly.
- Všechny následující trasy prošly se skutečným stavem nativní fyziky.
  Tolerance dojezdu byla 0,18 m; doprovod vyžadoval také otočení k vozu.

| Vůz | Trasa | Čas simulace | Odchylka cíle | Výsledek |
|---|---|---:|---:|---|
| BMW X1 | K vozu | 27.82 s | 0.170 m | Prošlo |
| BMW X1 | Zpět na recepci | 25.76 s | 0.079 m | Prošlo |
| Volvo XC60 | K vozu | 31.46 s | 0.115 m | Prošlo |
| Volvo XC60 | Zpět na recepci | 36.62 s | 0.053 m | Prošlo |
| CHERY Tiggo 8 Pro | K vozu | 62.34 s | 0.085 m | Prošlo |
| CHERY Tiggo 8 Pro | Zpět na recepci | 72.96 s | 0.099 m | Prošlo |

Automatický příchod a prezentace: **prošlo**, 55.60 s
simulace. Původní slovní a zvukové úseky zůstávají stejné; vyprávění
čeká na potvrzený příjezd a zastavení (`timeline_delay`).

## Zachování designu

Původní vzhled, modely aut, materiály, nábytek, branding a rozmístění zůstaly
zachované. Browser test ověřil původní stylesheet `index-KaHz0SVI.css`;
regresní testy ověřily stávající modely, materiály a licenční manifesty.
Změnilo se propojení s nativní fyzikou, kamerami a pohybem, nikoli návrh interiéru.

[Snímek skutečného showroomu](build/showroom-native/browser/existing-showroom.png)

## Reprodukce a hranice ověření

```bash
.venv/bin/python -m unittest discover -s maloni_sim/tests -v
.venv/bin/python -m unittest chery_showroom.tests.test_native_runtime -v
.venv/bin/python -m unittest chery_showroom.tests.test_visit.VisitTests chery_showroom.tests.test_web_assets chery_showroom.tests.test_reception -v
.venv/bin/python -m chery_showroom.tests.accept_native --output /tmp/showroom-acceptance.json
```

HTTP a browser testy vyžadují lokální sockety. Browser harness:
`python -m chery_showroom.tests.browser_native`, proměnné `NODE_EXECUTABLE`
a `CHROMIUM_EXECUTABLE` umožňují zadat místní testovací instalace.

Textový rozhovor je ověřený. Placený cloudový hlas ani skutečný mikrofon
se během těchto testů nepoužívaly. Fyzika používá popsané kolizní aproximace;
nejde o certifikaci skutečného robota. Historické Buddha a univerzální
benchmarkové reporty se této akceptace autosalonu netýkají.

Naměřené časy závisí na stroji a jeho zátěži. Strojový report, scénáře a hashe
zdrojů: [SHOWROOM_NATIVE_VALIDATION.json](SHOWROOM_NATIVE_VALIDATION.json).
Spuštění a ovládání: [SHOWROOM_NATIVE.md](SHOWROOM_NATIVE.md).
