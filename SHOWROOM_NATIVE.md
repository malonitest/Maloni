# Stávající showroom na vlastním backendu

Cíl po upřesnění: funkční autosalon se **stávajícím designem**, bez MuJoCo.
Nejde o návrh nového showroomu ani o dokončení samostatného univerzálního
robotického simulátoru/Buddha benchmarku.

## Spuštění

```bash
cd /home/maloni/humanoid_ws
bash start_showroom.sh
```

Otevře se původní panel s původní 3D Automotive Gallery na
`http://127.0.0.1:8765`. Stejně funguje `start_chery_showroom.sh`.
`--port 0` vybere volný port; `--no-browser` pouze vytiskne adresu.
Prohlížeč je jediné grafické okno. MuJoCo viewer ani jeho renderer se nespouští.

```bash
# Sestavení nativní fyziky, pokud chybí lokální build:
bash scripts/build_maloni_sim.sh
# Automatický příchod zákazníka, bez grafiky:
bash start_showroom.sh --headless --scenario customer_arrival --duration 90 \
  --output /tmp/showroom-arrival.json
# Návštěva konkrétního místa:
bash start_showroom.sh --headless --tour tiggo8 --duration 120 \
  --output /tmp/showroom-tour.json
```

Launchery případně sestaví chybějící nebo zastaralé nativní jádro.
Frontend je předem sestavený v `chery_showroom/web/dist`; pro samotné spuštění
není potřeba Node.js. Fyzika potřebuje lokálně sestavenou knihovnu, NumPy,
původní datové modely a ONNX runner. Systémové knihovny: Eigen3 a Bullet
Collision. Bullet Dynamics se nepoužívá. Závislost `mujoco` není potřeba.
Složka `unitree_mujoco` zůstává zdrojem licencovaných XML/STL dat.

## Zachované prostředí a funkce

- Původní BMW X1 2013, Volvo XC60 2023 a CHERY Tiggo 8 Pro 2023, interiér,
  nábytek, povrchy, světla, přepínání den/večer, kamery a katalog.
- Původní panel, rozhovor s humanoidem, otázky u recepce, výběr vozidla,
  průvodce, prezentace, kvíz, shrnutí pro prodejce a reset.
  Kalibrace rychlostního řízení je samostatná v `chery_showroom/native_velocity.json`;
  původní MuJoCo benchmarková kalibrace zůstala zachovaná.
- Vlastní C++ dynamika G1, původní ONNX politika a momentové PD řízení.
  Navigace i hlášení příchodu používají stav fyziky, nikoli text rozhovoru.
- Stávající 3D humanoid nyní zobrazuje transformace z nativní fyziky.
  Zákazník v interaktivní návštěvě používá původní detailní model.
- Tlačítko Simulation camera a původní výběr kamer používají tutéž
  existující 3D scénu. Kamera robota sleduje jeho pohyb; není potřeba
  offscreen MuJoCo JPEG ani druhé grafické prostředí.
- Stop, přerušení návštěvy, ochrana před zastaralými příkazy po resetu a
  zastavení při odpojení panelu. Neaktivní showroom neprovádí fyziku na pozadí.
- Volitelná browser speech a původní cloudové hlasové rozhraní. Textový
  rozhovor funguje bez API klíče; placené cloudové volání testy neprovádějí.

Původní 55sekundový scénář obsahuje stejné texty a zvukové úseky. Jeho
vyprávění počká na skutečné dosažení místa a zastavení robota. Celkový
simulovaný čas tak může být mírně delší; JSON uvádí `timeline_delay` a
`sim_elapsed`. Příchod není vynucen přepsáním polohy robota.

## Kolize a souřadnice

Viditelné modely nebyly zjednodušené. Pro kolize se používají samostatné
konvexní proxy robotických meshů z 122 deterministických podpůrných směrů
(včetně zachování všech osových mezí), původní kulové kontakty chodidel a
statické boxy odpovídající existujícím autům, recepci a nábytku. Proxy mají
celkem přibližně 2 537 vrcholů místo více než 100 tisíc zdrojových vrcholů.
Jde o aproximační fyziku demonstračního showroomu.

Fyzika používá SI jednotky, Z vzhůru a světové rychlosti základny. Stávající
Three.js převod souřadnic a původní vizuální měřítko postav zůstávají zachované.
Dialog neovládá fyziku přímo; validované příkazy procházejí frontou jediného
vlastníka simulace. Server naslouchá pouze na 127.0.0.1, ovládání vyžaduje token
původního panelu a kontrolu lokálního Host.

## Ověření

Výsledky: [SHOWROOM_NATIVE_VALIDATION.md](SHOWROOM_NATIVE_VALIDATION.md).

Novější změny, opakovatelné zkoušky stability a společná definice scény:
[SHOWROOM_IMPROVEMENTS.md](SHOWROOM_IMPROVEMENTS.md).

Navazující trénovací rozhraní, ověřované reference katalogu a browserový hlas:
[SHOWROOM_LEARNING_CATALOG_VOICE.md](SHOWROOM_LEARNING_CATALOG_VOICE.md).

```bash
.venv/bin/python -m unittest discover -s maloni_sim/tests -v
.venv/bin/python -m unittest chery_showroom.tests.test_native_runtime -v
.venv/bin/python -m unittest chery_showroom.tests.test_visit.VisitTests -v
```

Původní testy specifické pro MuJoCo renderer a kompilovaný MuJoCo model
neověřují tento backend. Aktuální integrační testy naopak blokují import
MuJoCo a ověřují nativní spuštění, reálný doprovod, prezentaci, rozhovor,
interaktivní návštěvu, odchod zákazníka, odpojení, Stop a reset.
Historické reporty jiných benchmarků dál popisují původní backend.

Dvojjazyčná návštěva s fyzickým návratem a technickým záznamem:
[SHOWROOM_BILINGUAL.md](SHOWROOM_BILINGUAL.md).

Ovládání a diagnostika nové etapy: [SHOWROOM_OPERATOR.md](SHOWROOM_OPERATOR.md).

Chůze zákaznice: [SHOWROOM_CUSTOMER_GAIT.md](SHOWROOM_CUSTOMER_GAIT.md).
