# Samostatný MALONI Humanoid 120

Aktualizace 9. listopadu 2026. Tato etapa nahrazuje předchozí vizualizaci poháněnou stavem G1.

## Spuštění a zachování G1

```bash
cd /home/maloni/humanoid_ws
bash start_showroom.sh --robot maloni120
bash start_showroom.sh --robot g1
```

Výchozí volba launcheru je `maloni120`. Oba režimy mají stejný showroom, vozy, dialog a ovládání. Volba probíhá při startu; v běžícím okně se platforma nepřepíná. Pro paralelní spuštění použijte druhému procesu jiný `--port`. Původní implementace G1, ONNX politika, model a nativní fyzika zůstávají dostupné. Kvůli kompatibilitě testů a starších skriptů konstruktor `Showroom()` nadále volí G1; nový režim se zadává `Showroom(robot_model='maloni120')`.

MALONI nepotřebuje sestavovat C++ knihovnu pro G1 ani spouštět ONNX runner. Launcher knihovnu sestavuje pouze při `--robot g1`.

## Vlastní dynamika

Implementace: `chery_showroom/maloni120_simulation.py`. Parametry: `chery_showroom/robots/maloni120.json`.

- Diferenciální pohon: dvě kola, rozchod 0,50 m, poloměr kola 0,135 m. Tyto rozměry jsou odhadnuté.
- Regulace požadované rychlosti kol převádí odchylku rychlosti na omezený moment motoru. Síla je omezena dostupnou trakcí `mu * m * g / 2` na každém kole.
- Dopředná síla a rozdíl sil vytvářejí zrychlení a otáčení těla. Efektivní hmotnost a moment setrvačnosti zahrnují rotační setrvačnost kol. Tlumicí odpory zajišťují odpor pohybu; zastavení používá motorové brzdění.
- Fyzika se integruje po 2 ms; řízení běží po 20 ms. Poloha vzniká integrací rychlosti, není přepisována podle cílového waypointu.
- Robot neumí boční posun. Navigační dokončení trasy proto nejprve koriguje polohu pohybem vpřed a teprve potom dokončí otočení.
- Kolizní obrys je kruh o poloměru 0,35 m. Kontakty se počítají vůči orientovaným boxům ze sdílené definice showroomu a hranicím scény. Kontaktní impuls ruší dopředný pohyb do překážky. Otáčení kruhového obrysu může pokračovat.
- Výstup obsahuje momenty motorů, úhly a rychlosti obou kol, kontakty a stav nouzového zastavení. 3D kola přebírají přímo úhly z fyziky.

Jde o rovinnou dynamiku na pevné rovné podlaze s ideálním neprokluzujícím vazebním modelem kol. Trakční limit omezuje sílu, ale nepočítá samostatnou dynamiku prokluzu pneumatik. Model neověřuje převrácení, pružnost, schody, teplotu motorů, baterii, 3D kontakty ramen ani skutečnou bezpečnost hardwaru. Výstupy `tilt=0` a `fallen=False` vyjadřují tuto rovinnou vazbu, nikoli výsledek testu stability. Hmotnost 35 kg, setrvačnost, momenty motorů, tření a odpory jsou vývojové odhady, ne potvrzené specifikace. Před připojením skutečných pohonů je nutná identifikace parametrů a samostatné ověření.

## Hlava, paže a komunikace

Samostatných osm os odpovídá konstrukčnímu podkladu HELIOS revize 02: dvě osy hlavy a tři na každé paži. Každá má omezené zrychlení, rychlost a rozsah. Gesta pozdravu a prezentace řídí vlastní kloubové cíle; nejsou převzata z indexů motorů G1. Jde o zjednodušenou dynamiku serva, která nezahrnuje gravitaci, hmotnostní vazby ramen ani jejich kolize.

MALONI používá vlastní české/anglické odpovědi o své identitě, kolovém pohonu a koncepční fázi. Zachovává katalogový rozhovor, průvodce, prezentace, otázky u recepce a shrnutí návštěvy. Příkazy k pohybu zůstávají ve frontě vlastníka simulace. Text funguje lokálně bez placeného modelu. Dosavadní rozhraní browser speech a volitelné cloudové hlasové rozhraní zůstává zapojeno; skutečný mikrofon, reproduktory a placená cloudová relace nebyly v této etapě testovány.

Nouzové zastavení je nové tlačítko i akce `emergency_stop`. U MALONI zablokuje pohon a zmrazí cíle gest až do resetu. Robot brzdí s omezeným momentem, nezastaví okamžitým vynulováním rychlosti. Běžný Stop i ztráta spojení rovněž vedou k brzdění. Jde o softwarovou simulaci zastavení, nikoli ověřený bezpečnostní obvod.

## Ověření

- 8 testů `chery_showroom.tests.test_maloni120`: nezávislost na modelu/politice G1, zrychlení, brzdění, nulový boční pohyb, otočení na místě, omezení momentu a trakce, kontakt s překážkou, determinismus a limity os, dialog, nouzové zastavení, reset, odpojení a cesta k vozu i zpět.
- 20 regresních testů původního operátorského ovládání G1, recepce/HTTP a katalogového dialogu prošlo.
- Headless `customer_arrival` na MALONI dokončen; první kontrolní běh skončil v čase 55,02 s.
- Headless cesta k `tiggo8` dokončena v čase 63,34 s z výchozí recepce. Samostatný test ověřuje také návrat.
- Start G1 i MALONI přes oba režimy launcheru ověřen krátkým headless během.
- TypeScript, produkční build, test modelu a interpolace pohybu prošly.
- Browserový test prošel: galerie, správný backend, česká identita, pozdrav, nouzové zastavení a reset; bez JavaScriptových chyb. Snímky obrazovky nebyly dokončeny kvůli pomalému softwarovému vykreslování.

Opakování:

```bash
.venv/bin/python -m unittest chery_showroom.tests.test_maloni120 -v
.venv/bin/python -m unittest chery_showroom.tests.test_operator chery_showroom.tests.test_reception chery_showroom.tests.test_visit.VisitTests -v
bash start_showroom.sh --robot maloni120 --headless --scenario customer_arrival --duration 150 --output /tmp/maloni120-arrival.json
```

Pro browserový test: v `chery_showroom/web` spusťte `SHOWROOM_URL=http://127.0.0.1:PORT node tests/maloni120_browser.cjs` proti běžícímu MALONI showroomu. Výstupy ukládá do `build/maloni120/browser`.
