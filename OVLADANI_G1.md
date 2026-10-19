# G1 v MuJoCo: autonomní úkol a ruční ovládání

```bash
cd humanoid_ws
./start_g1_keyboard.sh
```

Výchozí laboratorní režim spouští úkol **najít červeného Buddhu a položit ho na pravý stůl u prosklené stěny**. Soška se při spuštění a resetu objeví na náhodném volném místě na podlaze. Robot ji přinese na označené místo, po stabilním položení se otočí ke kameře a oslaví úspěch.

- **Mezerník**: pozastavení úkolu, držený předmět zůstane v ruce.
- **B**: pokračování úkolu.
- **R**: reset robota, předmětu i úkolu s novým náhodným umístěním.
- **F**: zapnutí/vypnutí sledování kamerou.

Jde o **asistovanou simulační demonstraci**, nikoli o vizuální rozpoznávání nebo ovládání prstů. Poloha cíle pochází ze simulace. Ruce se řídí inverzní kinematikou; při dostatečném přiblížení se soška přichytí fyzikální vazbou k levé ruce. Při stacionárním podřepu a pokládání pomáhá podpůrná vazba základny ke kinematickému bodu a kompenzace tíhy. Soška koliduje s místností, ale ne s pevnými dlaněmi; skutečné držení zajišťuje vazba. Chůzi po trase řídí původní ONNX politika. Při držení pomáhá také mírný moment udržující trup vzpřímený; pozorování paží pro politiku jsou nastavena na neutrální hodnoty, protože tato politika nebyla trénována na manipulační postoje. Úchopová vazba drží bod dlaně a samostatná momentová pomoc udržuje sošku vzpřímenou, takže se zápěstí může při přenášení přirozeně natočit. Podpůrná vazba pomáhá rovněž při závěrečném odstoupení, otočení a oslavě. Úspěch vyžaduje uvolněnou vazbu, kontakt s pravým stolem a nejméně sekundu stabilního spočinutí.

```bash
./start_g1_keyboard.sh --seed 0
./start_g1_keyboard.sh --headless --task buddha --seed 0 --duration 180
./start_g1_keyboard.sh --task none
```

`--seed` reprodukuje první umístění. R vytvoří nové umístění a vypíše nový seed. `--task none` zapne původní ruční ovládání, `--dance` samostatný rock’n’roll. Klasická scéna nemá úkol Buddha; explicitní `--task buddha --scene classic` vypíše chybu. Stav úkolu se vypisuje do terminálu a do rohu grafického okna. Robot začíná hledat po ustálení sošky.

## Ruční chůze

Spusť `./start_g1_keyboard.sh --task none`. Klikni do nového okna MuJoCo a používej klávesy v tomto okně. Řadič chůze běží od první simulované sekundy a robot začíná ve výchozím postoji modelu chůze. Ruční závěs ani přepínání režimů 1/2/8/9 se v tomto programu nepoužívají.

| Klávesa | Akce |
| --- | --- |
| W / šipka nahoru | Vpřed 0,5 m/s |
| S / šipka dolů | Vzad 0,3 m/s |
| A / D | Do stran: příkaz 0,3 m/s |
| Q / E nebo šipka vlevo / vpravo | Otáčení: vlevo 0,6 / vpravo 0,8 rad/s |
| T | Zapnutí/vypnutí tance; pohybové klávesy tanec ukončí |
| Mezerník | Zastavení pohybu; řadič stále udržuje postoj |
| R | Reset modelu i historie řadiče do výchozího postoje |
| F | Zapnutí/vypnutí kamery sledující robota |
| Zavření okna | Ukončení programu |

Klávesu stačí stisknout jednou. Pohyb pokračuje až do dalšího příkazu nebo mezerníku, i když přepneš do jiného okna. Před přepnutím okna proto použij mezerník. Terminál vypisuje přijaté příkazy, ovládání je v okně MuJoCo.

Starý proces `start_g1_keyboard.sh` po aktualizaci stále používá původní program. Ukonči jej v jeho terminálu pomocí Ctrl+C a zavři původní okno s padlým robotem. Nový program běží samostatně, bez DDS a bez ROS.

Implementace je v `keyboard_walk/g1_keyboard.py`. Ve výchozím režimu používá laboratoř `scene_lab.xml` s původním modelem robota a ONNX model z `unitree_rl_lab/deploy/robots/g1_29dof/config/policy/velocity/v0/exported/policy.onnx`. `policy_config.json` je kopie parametrů z odpovídajícího `params/deploy.yaml`; při změně modelu je nutné aktualizovat i parametry.

Ověření postoje a pohybu bez grafického okna:

```bash
./start_g1_keyboard.sh --task none --headless --duration 10
./start_g1_keyboard.sh --task none --headless --duration 10 --forward-speed .5
```

Pomocný program pro ONNX je možné znovu sestavit pomocí `keyboard_walk/build_policy_runner.sh`. Využívá ONNX Runtime již přiložený k projektu.

U tohoto modelu příkaz do strany 0,2 m/s téměř nevyvolal kroky; mapování A/D proto používá 0,3 m/s. Otáčení Q používá 0,6 rad/s a E používá −0,8 rad/s; model v pravém směru reaguje slaběji. Jde o požadované rychlosti, skutečný pohyb modelu se od nich může lišit. Hodnoty jsou ověřené v této lokální simulaci.

Samostatné ověření boční chůze a otáčení:

```bash
./start_g1_keyboard.sh --task none --headless --duration 15 --sideways-speed .3
./start_g1_keyboard.sh --task none --headless --duration 15 --sideways-speed -.3
./start_g1_keyboard.sh --task none --headless --duration 15 --turn-speed .6
./start_g1_keyboard.sh --task none --headless --duration 15 --turn-speed -.8
```

## Moderní robotická laboratoř

Laboratoř se načítá automaticky. Obsahuje pracovní stoly, přístroje a monitory, serverový rozvaděč, skříně, prosklenou fasádu, světlík, rostliny a značení testovací plochy. Textury a grafika na monitorech jsou lokální součásti projektu. Stoly, skříně a pevné stěny mají kolize. Středová plocha je rovná, s původními kontaktními parametry pro řadič chůze. Řadič nemá automatické vyhýbání překážkám; chůzi řídíš klávesnicí.

Kamera sleduje polohu robota. Klávesa F ji uvolní pro prohlížení laboratoře. Myší můžeš otáčet pohled a kolečkem měnit vzdálenost. MuJoCo panely jsou na začátku skryté; klávesa Tab přepíná levý panel.

Původní prostředí lze spustit:

```bash
./start_g1_keyboard.sh --scene classic
```

Scéna: `unitree_mujoco/unitree_robots/g1/scene_lab.xml`. Její textury jsou v přilehlé složce `lab_assets`. Pro úpravu a opětovné vytvoření scény slouží:

```bash
python3 keyboard_walk/build_lab_scene.py
```

Generátor používá systémový Python s NumPy a Pillow. Pro samotné spuštění scény generátor nepotřebuješ.

## Tanec

Spuštění s automatickým tancem po třech sekundách:

```bash
./start_g1_keyboard.sh --dance
```

Rock’n’roll má tempo 220 BPM, protichůdné švihy paží, střídání kroků vpřed a vzad, boční chassé se zvedáním kolen a střídavé otočky. Každých šestnáct dob robot přejde do podřepu a odrazí se do poskoku; poté řadič stabilizuje dopad. Poskoky vznikají pohybem kloubů ve fyzikální simulaci. Tempo lze nastavit například `./start_g1_keyboard.sh --dance --bpm 220` (120–260 BPM; stabilita ověřena při 220 BPM). Hudba se nepřehrává. T přepíná tanec, mezerník jej zastaví a R resetuje postoj. Jde o režim lokální simulace MuJoCo. Ověření bez okna: `./start_g1_keyboard.sh --headless --dance --duration 60`.

## Implementace a ověření úkolu Buddha

Řadič úkolu a plánovač tras jsou v `keyboard_walk/buddha_task.py`. Generátor `keyboard_walk/build_lab_scene.py` vytváří úkolovou scénu `scene_lab_task.xml`, sošku, cílovou značku a kopii modelu `g1_29dof_task.xml` s body dlaní. Původní model pro klasickou scénu zůstává samostatný.

```bash
python3 keyboard_walk/build_lab_scene.py
.venv/bin/python keyboard_walk/test_buddha_task.py
```

Testy kontrolují 100 rozmístění a přístupových tras, reprodukovatelnost seedu, blokovaný cíl, podmínku dosahu pro uchopení, pozastavení při držení, reset, upuštění a natočení k přemístěné kameře. Celý průchod se ověřuje headless spuštěním pro pevné seedy 0–9.

Kompletní opakovatelná validace včetně fyzikálních kontrol úchopu, položení, natočení a pauzy při přenášení:

```bash
.venv/bin/python keyboard_walk/verify_buddha.py --seeds 0 1 2 3 4 5 6 7 8 9
```


