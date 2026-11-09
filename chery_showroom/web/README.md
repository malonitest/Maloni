# MALONI Automotive Gallery — světlý fotorealistický showroom

Z kořene projektu spusťte `bash start_showroom.sh`. Otevřete vypsaný panel
v Chrome nebo Edge a po aktualizaci použijte Ctrl+F5. Pro běžný provoz není
potřeba Node.js, přístup k internetu ani vývojový server; dodává se hotový dist/.

## Co je ve scéně

Zachována jsou tři původní auta (BMW X1, Volvo XC60, CHERY Tiggo 8 Pro), jejich
rozměry a polohy ze simulace. Nová grafika zahrnuje fotografické PBR materiály
neutrálního vápence (odvozeného z mramoru) a ořechové dýhy, plně modelovanou recepci s pracovní plochou/monitorem,
prostorové kovové logo, prosklené průčelí a střešní atrium, denní panorama a
široká stropní světla. Volitelná Večerní galerie mění světlo i statické odrazy. Detaily nábytku pocházejí z původních CC0 modelů Poly Haven.

Před pultem stojí detailní texturovaná zákaznice (zdroj Mei / Innerscene / MakeHuman CC0),
v reálné výšce 1,68 m. Jde o statickou 3D postavu, nikoliv živého člověka nebo
nového konverzačního agenta. Tlačítko **Zákaznice** ji zobrazí zblízka; **Recepce**
ukáže pult s obsluhou. Přepínač **Kamera simulace** zachovává původní náhled.

Původní robot, návštěva, hlas a STOP zůstávají řízené MuJoCo. Výběr vozu a kamery
v grafické scéně neposílá příkazy simulaci. Vizuální budova i zákaznice nemění
kolize/navigaci. Webová scéna zatím nepřebírá živé pózy G1 ani zákazníka.

## Vykreslování a ovládání

Výchozí pohled **Interiér** ukazuje prostor ze vstupního rohu včetně stropu a všech
tří vozů. **Recepce** dál nabízí srovnatelně velký pohled na zákaznici a G1.

- Interiér, Od vstupu, Recepce, Lounge a barvy, Zákaznice, Humanoid a detaily vozů zobrazují celou místnost. Celý
  showroom je architektonický řez se skrytým průčelím a stropem.
- Myší/dotykem se otáčí kamera, kolečkem/pinchem přibližuje. Přechody trvají
  0,8 s; ruční zásah je okamžitě přeruší. Vnitřní kamera má meze stěn a podlahy.
- Slunce vrhá stíny přes rámy/skylight; plošná světla vytvářejí široké odlesky.
  Odrazy se při načtení a přepnutí atmosféry vypočítají místními cubemap/PMREM
  sondami pro tři auta a humanoida v celé zařízené místnosti. Neaktualizují se každý snímek. Podlaha a stěny mají levnou
  statickou ambientní okluzi. Podlahový kontaktní maskovací povrch navíc ukotvuje
  kola a nábytek i na přímo osvětlené podlaze; nevytváří další stínové světlo.
- Úsporný profil: jeden forward render, pixel ratio nejvýše 1, stíny 1024.
- Vyšší profil: pixel ratio nejvýše 1,5, stíny 2048, GTAO kontaktní stínování,
  denoising a FXAA vyhlazování. Je výrazně náročnější; na Iris Xe začněte úsporným.
- V nečinnosti/skryté záložce se znovu nevykresluje. Během přechodu nebo měření
  se vykresluje průběžně. Stálé odrazy jsou určeny pro tuto statickou scénu;
  budoucí pohybující se robot vyžaduje samostatné řešení odrazů.

Automobilové sklo nepoužívá drahý transmission a nepřibyla plošná zrcadla. Odrazy
podlahy neobsahují dynamické screen-space zrcadlení aut. Zdrojové modely vozů
zůstávají zjednodušené a limitují extrémní detaily karoserií.

## Build a reprodukce assetů

Pro vývoj je potřeba Node.js 22.16+; v tomto adresáři:

```bash
npm ci
npm run build
```

Původní auta a nábytek obnovte podle SHOWROOM.md. Z kořene lze připravit vše znovu:

```bash
.venv/bin/python -m chery_showroom.furnishings --restore
.venv/bin/python chery_showroom/web/prepare_assets.py
.venv/bin/python chery_showroom/web/prepare_realism.py --restore
.venv/bin/python chery_showroom/web/prepare_daylight.py
```

Pak znovu spusťte npm run build v adresáři web. prepare_assets.py obnovuje vlastní
procedurální mapy a původní GLB nábytku. prepare_realism.py ověřuje pevné kontrolní
součty podle assets/realism/sources.json a při --restore stáhne chybějící CC0
zdroje. Fotografické mapy a HDR zachovává beze změny; textury recepční zmenší na
1K a zachová alfa kanály, geometrii, UV a původní materiály. Oprava neprůhledné
korneální vrstvy očí se provádí pouze v rendereru. Originální stažené soubory se
nemění a jsou oddělené od hotových webových assetů.

Provenience, SHA-256 a úpravy jsou v public/realism-assets.json a
public/premium-assets.json a public/daylight-assets.json. Použité fonty mají zachovanou licenci MAGENTA
v public/FONT_LICENSE.txt. Všechny zdroje jsou uvedené v public/CREDITS.txt.
Runtime poskytuje konkrétní povolené /graphics/ soubory a /web/ bundle; žádné CDN,
API klíče ani řídicí tokeny grafická scéna nevyužívá. Čtení assetů neobnovuje heartbeat.

## Ověření a výkon

Z kořene: `.venv/bin/python -m unittest chery_showroom.tests.test_web_assets -v`.
Testy kontrolují assety, hashe, geometrii/materiály recepční, rozlišení map,
bezpečné cesty, nezměněnou autentizaci, STOP a heartbeat.

V adresáři web nainstalujte Chromium (`npx playwright install chromium`) a proti
spuštěnému showroomu použijte:

```bash
SHOWROOM_URL=http://127.0.0.1:PORT npm run test:browser
```

Browser test pokrývá všechny vozy a kamery, řez budovou, přerušení přechodu,
meze kamery, skutečné rozměry/polohu a texturovanou geometrii zaměstnankyně,
vyšší kvalitu, měření, mobilní viewport a chyby modelů/WebGL. Snímky ukládá do
assets/review/realism/after. CHROMIUM_EXECUTABLE zvolí vlastní Chromium;
SOFTWARE_WEBGL=1 slouží pouze k funkčnímu ověření přes SwiftShader.

Pro měření na notebooku otevřete /web/ samostatně v Edge/Chrome ve Windows,
nastavte viewport 1280 × 720 a zvolte úsporný profil. V **Měření a zdroje** vyberte
statický pohled nebo automatický pohyb kamery a spusťte **Měřit 60 s**. Po 3 s
zahřátí proběhne 60 s měření a stáhne se JSON s FPS/p95, profilem, rozlišením,
kamerou a režimem. Ruční změna kamery/nastavení měření přeruší. Výkon na Iris Xe je nyní ověřen přímo ve Windows (viz níže); snímky ze SwiftShaderu samy o sobě nedokládají FPS na notebooku.

## Historické měření předchozí etapy na Intel GPU

24. října 2026: Windows Chrome 156.0.0.0, headless,
Intel Iris Xe přes ANGLE / Direct3D 11. Viewport 1280 × 720, pixel ratio 1,
úsporný profil, pohled Celý showroom. Každý běh měl 3 s zahřátí a 60 s skutečného
uplynulého času; nepoužil se virtuální čas ani softwarový GPU renderer.

| Režim | Aplikační FPS | p95 intervalu snímků |
|---|---:|---:|
| Statický pohled | 119.9 | 8.5 ms |
| Pohybující se kamera | 119.7 | 8.5 ms |

JSON a informace o GPU jsou v assets/review/realism/windows. Jde o aplikační
měření requestAnimationFrame při průběžném skutečném renderování, nikoliv
o počet opakování nečinného obrázku. Výsledek je pro samostatnou webovou scénu
v headless Chrome; není zárukou stejného FPS při současném běhu MuJoCo vieweru,
v jiném rozlišení nebo vyšším profilu.

Na Windows lze měření opakovat pomocí nainstalovaného Node.js:

```powershell
node tests/windows-benchmark.cjs --url=http://127.0.0.1:PORT
```

Skript vytvoří vlastní dočasný Chrome profil a po skončení jej odstraní; osobní
profil nepoužívá. Příznak --capture-only provede jen vizuální kontrolu nižší/vyšší
kvality a mobilního pohledu. Skript odmítne softwarový GPU a uloží skutečný
identifikátor rendereru spolu s výsledky.

Stíny se u této statické scény počítají při načtení a změně kvality, nikoli znovu
každý snímek. Jakmile se v budoucnu přidají pohybující se postavy nebo světla,
musí integrace zneplatnit stínovou mapu i příslušné reflexní sondy.

Integrační kontrola vloženého 3D pohledu musí běžet proti skutečnému panelu
`chery_showroom.runtime`, nikoli pouze proti serveru statických souborů:

```bash
SHOWROOM_URL=http://127.0.0.1:PORT node tests/panel.cjs
```

Kontroluje načtení iframe, kameru recepce, aktualizaci stavu simulace a chyby
HTTP/JavaScriptu. Volitelně nastavte `CHROMIUM_EXECUTABLE`, `SOFTWARE_WEBGL=1`
a `PANEL_SCREENSHOT` (cesta pro snímek). Softwarový renderer slouží pouze k
funkční kontrole.

## Světlá etapa · 25. října 2026

Parametry světla, expozice a povrchů jsou v `src/appearance.ts`. Podlaha má
234 desek 1 × 1 m, 3mm spáry a deterministický 16variantní atlas. Desky tvoří
jeden mesh; zvlášť se kreslí podklad spár a statická kontaktní maska. Atlas má 2K,
samostatné stěnové mapy 1K. Původní zdroje zůstávají beze změny. Příprava
`prepare_daylight.py` ověřuje vstupní hashe a zapisuje recepturu/provenienci
a výstupní SHA-256 do `daylight-assets.json`. Nevyžaduje síť.

Slunce je slabší, nepřímé světlo silnější, GTAO jemnější. Zůstává jedno stínové
a dvě plošná světla. Panely, prahy a rámy mají jemné spáry a zakončení; pult
používá samostatně orientovanou dýhu. Automobilové materiály mají oddělené
parametry odrazů. Také BMW používá neprůhledné sklo bez transmission.

Párové snímky obou profilů a mobilu: `assets/review/daylight/comparison.html`.
Architektonické kamery mají stejné pozice před/po; pohled Celý vůz má nový
úhel od uličky pro krajní stanoviště. Půdorys a pozice vozů se nemění.

Pro opakování snímků: `SHOWROOM_URL=http://127.0.0.1:PORT node tests/visual.cjs`.
`REVIEW_OUTPUT` přesměruje snímky i Windows benchmark mimo historické výsledky.
Benchmark může zaznamenat kontext pomocí `SIMULATION_ACTIVE=1` a
`SIMULATION_CONTEXT`; nejde o automatickou detekci běhu simulace.

### Výkon světlé etapy na notebooku

25. října 2026, nativní Windows Chrome 156, headless, ANGLE / Intel Iris Xe
(0xA7A0) / Direct3D 11. Úsporný profil, 1280 × 720, pixel ratio 1, celkový pohled.
Každý běh: 3 sekundy zahřátí a 60 sekund skutečného času.

| Režim | Aplikační FPS | p95 intervalu snímků |
|---|---:|---:|
| Statický pohled | 110.5 | 16.7 ms |
| Pohyb kamery | 114.4 | 8.8 ms |

Cíl alespoň 30 FPS byl v obou bězích splněn. Současně běžela skutečná fyzika
a řídicí politika `Showroom` ve WSL, s cílovým krokem smyčky 20 ms a původním
`runtime.server`. Během měření byla vypnutá kamera simulace a nebyl otevřený
pasivní MuJoCo viewer. Neprobíhaly současně Python testy ani další grafické testy.
Jde o aplikační rAF měření při průběžném renderování; nejde o GPU profiler ani
záruku výkonu v headed režimu se současně otevřeným viewerem.

Surové výsledky včetně příznaku a popisu souběhu simulace jsou v
`chery_showroom/assets/review/daylight/windows/static.json` a `motion.json`,
identifikace GPU/ovladače v `gpu.json`. Původní historická měření zůstávají
odděleně v `assets/review/realism/windows`.

## Klávesové ovládání kamery

Klikněte do 3D pohledu (nebo na canvas přejděte Tabem). Šipky ↑ / ↓ posouvají
kameru svisle, ← / → do stran vzhledem k pohledu; W / S dopředu a dozadu ve směru
pohledu. A / D otáčejí kameru na místě doleva a doprava rychlostí 60°/s. Přidržení znamená plynulý pohyb 2 m/s, kombinace kláves nezrychluje.
Pohyb respektuje meze místnosti a podlahy a přeruší kamerový přechod i benchmark.
Myš a kolečko fungují dál. Tlačítko připraveného pohledu obnoví jeho kameru.

Klávesy fungují pouze při zaměření samotného 3D canvasu. Výběry, tlačítka,
formuláře a ostatní dashboard si ponechávají své ovládání. Uvolnění klávesy,
ztráta zaměření nebo skrytí pohledu zastaví pohyb. Klávesy 3D kamery neposílají
příkazy robotovi. Nápověda je trvale v dolní liště i nad 3D pohledem v dashboardu.

Pro ověření vloženého pohledu proti skutečnému panelu:
`SHOWROOM_URL=http://127.0.0.1:PORT node tests/keyboard.cjs`.

## Humanoid u recepce

Za pultem stojí Unitree G1 jako recepční. Zákaznice stojí před pultem čelem k němu. Úvodní pohled
ukazuje recepci. Tlačítko **Humanoid** přiblíží asistenta a otevře okénko
**Zeptejte se humanoida G1**. Napište dotaz a stiskněte **Zeptat se** nebo Enter.
Odpověď je textová; přepínač **Číst odpovědi hlasem prohlížeče** v dashboardu
ji navíc předá české syntéze řeči. Při aktivním cloudovém rozhovoru se tento
souběžný prohlížečový hlas nepouští. Zdejší formulář neaktivuje mikrofon.

Recepční odpovědi používají současný místní dialog a katalog vystavených modelů,
nikoli nový obecný cloudový model. Neověřené ceny/výbavu odkazují na prodejce.
Rozhovor je oddělený od návštěvy a nikdy neodesílá pohybové příkazy ani neobnovuje
řídicí heartbeat. Prezentovaný G1 krátce reaguje kývnutím, jeho umístění je pevné;
nejde o přenos živých fyzikálních póz. Původní simulovaný robot zůstává ovládaný
stávajícím dashboardem. Zachovaná ženská postava je zákaznice před pultem, nikoli recepční.

Nové autentizované API: `POST /reception/chat`, hlavička `X-Showroom-Token`,
JSON `{text, car, run_id}`; odpověď `{reply, car, run_id}`. Text má 1–1000 znaků,
car je existující identifikátor vozu, neaktuální run_id se odmítne. Rozhovor se
po resetu automaticky založí znovu. Iframe zná jen run_id a posílá zprávy parentu;
token zůstává v dashboardu. Obě strany kontrolují původ a konkrétní okno. Chyba
API i timeout jsou viditelné, dotaz lze zopakovat. Samostatné /web/ odkazuje pro
rozhovor na dashboard a nezavádí vlastní polling /state.

G1 je exportovaný z místních původních vizuálních STL a neutrální kloubové pózy,
bez kolizní geometrie a při zachování metrů. Licence BSD-3-Clause je zachovaná
v `public/UNITREE_LICENSE.txt`; vstupní/výstupní SHA-256 v `humanoid-assets.json`.
Příprava z kořene projektu: `.venv/bin/python chery_showroom/web/prepare_humanoid.py`,
poté npm run build. Zdroje ani MuJoCo scéna se tím nemění.

Ověření rozhovoru: `.venv/bin/python -m unittest chery_showroom.tests.test_reception`.
Proti skutečnému panelu: `SHOWROOM_URL=http://127.0.0.1:PORT node tests/reception.cjs`.
Snímky umístění a mobilního okénka jsou v `assets/review/reception/`.
Po instalaci této změny restartujte Python launcher (nová assetová cesta a API),
pak v panelu Ctrl+F5. Běžný provoz dál nevyžaduje Node.js.

### Výkon po přidání G1

Dva běhy ve Windows Chrome 156 headless na skutečné Intel Iris Xe / D3D11,
úsporný profil, 1280 × 720, pixel ratio 1, celkový pohled včetně G1. Každý běh
měl 3 s zahřátí + 60 s reálného času. Statický pohled: 107.9 FPS
(p95 16.7 ms), pohyb kamery: 105.0 FPS
(p95 17.2 ms). Cíl 30 FPS je v obou režimech splněn.

Současně běžela fyzika a řídicí politika Showroom ve WSL se smyčkou 20 ms;
bez pasivního MuJoCo vieweru a s vypnutou kamerou simulace. Jde o aplikační
rAF měření při průběžném renderování, ne o GPU profiler ani záruku stejného
výkonu s otevřeným viewerem. JSON, identifikace GPU a snímky jsou v
chery_showroom/assets/review/reception/windows/. Profil vyšší kvality i mobilní
záběr zaměstnankyně prošly navazující kontrolou bez shaderových chyb.

### Aktualizovaný frontend proti staršímu běžícímu serveru

Model G1 se načítá přes stabilní `/web/models/g1-reception.glb`, takže jeho
zobrazení nevyžaduje novou aliasovou cestu v již načteném Python modulu.
Chybějící G1 neblokuje ostatní showroom: zobrazí se upozornění, ostatní vozy,
kamery a přepnutí na simulaci zůstávají dostupné.

`/state` nového serveru obsahuje `reception_available: true`. Dashboard tuto
schopnost předá iframe stejnou zprávou jako run_id. Pokud příznak chybí, model
se zobrazí, ale dotazový formulář oznámí nutnost restartu a nevolá chybějící API.
Pro úplné zapnutí rozhovoru zastavte starý launcher pomocí Ctrl+C, spusťte jej
znovu a otevřete nově vypsanou adresu (port se může změnit). Pak použijte Ctrl+F5.

Regrese: `SHOWROOM_URL=http://127.0.0.1:PORT node tests/reception-compat.cjs`.
Skript normálně simuluje chybějící příznak; `LEGACY_SERVER=1` testuje skutečný
starší proces. Ověřuje i úplně chybějící GLB bez pádu ostatní scény.

### Role, měřítko a detaily u recepce

Na přání uživatele jsou obě postavy vysoké **1,68 m**. Jde o záměrné zvětšení
pouze grafického G1; původní export v metrech a MuJoCo model se nemění. Humanoid
stojí v (-2.2, -1.48), zákaznice v (-2.2, -4.05), na opačných stranách pultu.
G1 hledí k zákaznici, zákaznice je otočená směrem k němu. Tlačítko Zákaznice
nahrazuje původní zavádějící označení ženské postavy jako recepční.

Humanoid má samostatné kovové kryty, tmavé klouby, pryžové díly a lesklý tmavý
senzor. Jemná roughness struktura vzniká deterministicky v paměti. Senzorový
prstenec, stavová dioda a upevňovací detaily jsou umístěné raycastem na původní
povrchy, bez změny zdrojových STL/GLB. Doplňky nejsou tvrzením o přesné výrobní
konfiguraci G1. Čtvrtá statická PMREM sonda zachycuje interiér u humanoida ve
výšce 1,5 m; žádný odraz se nepočítá každý snímek. Sdílené materiály dostávají
intenzitu odrazů jednou, aby při průchodu několika díly postupně netmavly.

Import HDR používá aktuální HDRLoader z již uzamčené verze Three.js, bez
varování starého RGBELoader. Srovnávací snímky aktuální recepce a detailů jsou
v assets/review/reception-opposite/.


### MALONI Atelier · vybavení a atmosféra

`src/atelier.ts` rozšiřuje současný interiér o kávový kout s pracovní deskou,
kávovarem, šálky a úložnými skříňkami; šest zakřivených vzorků laku; vlastní
rámovanou automobilovou kresbu; akustické dřevěné lamely nad recepcí a kruhové
závěsné svítidlo nad posezením. Tlačítko **Lounge a barvy** přejde stejným
plynulým přechodem na boční stěnu s kávovým koutem a vzorníky. Vzorníky jsou
prezentační dekorace, nikoliv katalog skutečných konfigurací konkrétních vozů.

Recepce má tablet na podstavci, kabel monitoru, sdílenou instancovanou klávesnici,
myš a drobné pracovní vybavení. Koberec má vlastní deterministickou tkanou mapu;
na stolku leží magazín s vlastní kreslenou obálkou. U vstupu přibyla zeleň,
venku dlažba, truhlíky a nízká svítidla. Listy truhlíků používají původní
CC0 model Poly Haven, sdílené geometrie a materiály. Zdrojový GLB se nemění.
Všechny nové bitmapy vznikají deterministicky v canvasu, nejvýše 1K.

Lamely a venkovní dlažba jsou sloučené geometrie, klávesy instancované. Závěsné
svítidlo i LED lišty používají emisní materiály bez dalšího světla nebo stínové
mapy. Stropní doplňky patří do skupiny stropu a venkovní úpravy do průčelí;
v celkovém architektonickém řezu se skrývají společně s nimi. Statické odrazy
zachytí nové vybavení při načtení; vykreslování podle potřeby a oba profily
zůstávají zachované. Backend, heartbeat i rozhovor se touto etapou nemění.

Snímky jsou v `assets/review/atelier/after`, kontrola skutečného panelu v
`atelier/panel`, prohlížečové regrese v `atelier/browser`. Referenční recepce
před úpravou je v `atelier/before` (stejná kamera a vložený viewport 1150 × 721).
Běžné spuštění dál používá připravené `dist/`; pro načtení nové grafiky v již
běžícím panelu stačí Ctrl+F5.

Výkon této etapy ve Windows Chrome 156 headless / Iris Xe D3D11, low,
1280 × 720, DPR 1: statický pohled **86.0 FPS**, pohyb **86.1 FPS**,
p95 v obou bězích **16.9 ms**. Každý běh 3 s zahřátí + 60 s měření;
současně běžela fyzika/politika ve WSL, bez MuJoCo vieweru a kamery simulace.
JSON a GPU jsou v `assets/review/atelier/windows/`. Podrobný protokol a podmínky
jsou v kořenovém `SHOWROOM_REALISM_REPORT.md`; galerie v `atelier/index.html`.


### Denní světlo a Večerní galerie

V hlavní liště vyberte **Denní světlo** nebo **Večerní galerie**. Výchozí denní
světlo má jemnější stíny a větší podíl nepřímého osvětlení. Večer používá
utlumené stávající HDR pozadí, teplejší stropní světla a samostatně vyváženou
expozici. Nepřibývají další světla, stínové mapy ani renderovací průchody.
Při změně atmosféry se jednorázově přepočítají statické odrazy a staré GPU
render targety se uvolní. Materiály si uchovávají původní intenzitu odrazů,
takže opakované přepínání nezpůsobuje postupné tmavnutí. Kamera, volba vozu
ani obsah rozhovoru se změnou atmosféry neresetují. Změna přeruší benchmark;
jeho JSON nově obsahuje také `ambience` (`day` nebo `evening`).

`src/finishes.ts` vytváří vlastní 512px mapy tmavého kamene pultu a jemné
omítky: barvu, roughness a bump. Úprava měřítka omítky respektuje rozměry stěn.
Informační stojany mají nakloněné podsvícené tabule s názvem a rokem skutečně
vystaveného modelu, vlastní původní SUV kresbou a bez neověřených parametrů.
Recepční monitor zobrazuje vlastní grafiku konzultace. Stanoviště vymezuje
9mm mosazná intarzie v podlaze, bez zvýšení aut nebo změny půdorysu.

PBR povrchy jsou v obou profilech; stíny používají jednu PCF mapu 1024/2048
s poloměrem odpovídajícím kvalitě. Úsporný profil zůstává bez postprocessingu.
Výchozí světlý směr, zdrojové modely/licence, API a MuJoCo se nemění.

Ověření atmosfér proti skutečnému runtime (Node.js v prostředí prohlížeče):

```bash
SHOWROOM_URL=http://127.0.0.1:PORT node tests/ambience.cjs
```

Snímky a porovnání se ukládají do `assets/review/gallery/atmospheres`.
Z kořene projektu porovnejte skutečné obrazové návraty do denního světla:

```bash
.venv/bin/python chery_showroom/web/tests/compare_ambience.py
```

Povolena je průměrná odchylka nejvýše 1 úroveň RGB z 255 mezi původním obrazem
a dvěma návraty; večerní režim se musí viditelně lišit. Test používá stejnou
kameru a canvas, nikoli pouze deklarované hodnoty konfigurace.

Aktuální měření této světelné etapy: denní low, Windows Chrome 156 headless,
Iris Xe / D3D11, 1280 × 720, DPR 1: **79.1 FPS** staticky a **66.7 FPS**
při pohybu (p95 21.3/25.1 ms). Každý běh 3 + 60 s,
současná fyzika/politika ve WSL, bez MuJoCo vieweru a kamery simulace.
Večerní a vyšší profil mají vizuální/funkční kontrolu; tato čísla jsou pro
výchozí denní úsporný profil. Obnova světla/odrazů blokovala synchronní JS
obsluhu přibližně 131 ms. Výsledky a GPU: `assets/review/gallery/windows/`.
Galerie s posuvníkem den/večer je v `assets/review/gallery/index.html`.


### Konzultační zóna a architektonický pohled

`src/consultation.ts` vytváří na levé stěně konzultační zónu: tři oddělené
čalouněné sedáky a opěráky na dřevěném rámu s kovovými nohami, stolky s kamennou
deskou a keramickými květináči, ořechové lamely s tmavým podkladem a dvě původní
grafické studie doplňující stávající kresbu auta. Výška sedáku je 49 cm; lavice
ani stolky nenahrazují původní lounge a nezasahují do recepce nebo stanovišť.
Čalounění používá vlastní deterministickou tkanou mapu, listy původní CC0 model
Poly Haven se sdílenou geometrií a materiály.

Stěny zakončuje profilovaná římsa se světelnou spárou. Zůstává součástí budovy
viditelnou i v celkovém řezu. Značky na skle patří k průčelí a skryjí se s ním.
64 nových lamel je sloučeno do jednoho meshe a 300 drobných značek na skle je
instancovaných. Světelná spára je emisní materiál; nepřibylo další světlo ani
stínová mapa. Původní geometrie/assetové soubory a jejich licence se nemění.

Výchozí **Interiér** je široký architektonický pohled ze vstupního rohu; strop
zůstává viditelný. **Celý showroom** dál nabízí řez se skrytým stropem a průčelím.
Záběr **Od vstupu** je širší, aby lépe rámoval krajní auta. Přechody, jejich
přerušení a klávesové ovládání se nemění. Test klávesnice používá explicitně
pohled od vstupu, aby ověřoval směry nezávisle na výchozí kompozici.

Kontrolní snímky jsou v `assets/review/consultation/browser` a `atmospheres`.
Historické snímky `consultation/day` zachycují první verzi záběru; finální široká
kamera je v `browser/salon.png`. Referenční předchozí stav je v `consultation/before`.
Pro aktuální porovnání odrazů z kořene:

```bash
.venv/bin/python chery_showroom/web/tests/compare_ambience.py chery_showroom/assets/review/consultation/atmospheres
```

Výkon nového výchozího záběru lze v testovacím Windows prostředí změřit pomocí
`BENCHMARK_VIEW=salon` při spuštění `tests/windows-benchmark.cjs`; bez této
proměnné skript zachovává celkový řez `overview`. JSON obsahuje skutečný
`cameraView`, `ambience` a nastavení profilu. Běžný launcher používá připravené
dist a po této grafické aktualizaci stačí Ctrl+F5.

Aktuální měření **Interiéru**: staticky 71.0 FPS, při pohybu 69.6 FPS
(p95 24.9/23.9 ms). Windows Chrome 156 headless, Iris Xe / D3D11,
denní low, 1280 × 720, DPR 1; každý běh 3 + 60 s. Současná fyzika/politika
ve WSL bez vieweru a kamery simulace. Výsledky jsou pro nový výchozí pohled,
nikoli přímé srovnání s dřívějším řezem. JSON a GPU: `consultation/windows/`.
Galerie před/po a den/večer: `assets/review/consultation/index.html`.

## English interface (26 October 2026)

The dashboard, embedded 3D controls, generated signage, errors and local G1
dialogue are in English. Browser speech and recognition request `en-US`.
Restart the Python launcher after updating (`Ctrl+C`, then
`bash start_showroom.sh` from the workspace root), open the printed URL and
refresh with Ctrl+F5. An old running backend shows an English restart notice
and disables reception conversation until it advertises `language: "en"`.

The 55-second visit uses a separate `assets/arrival_audio_en` cache. Original
Czech recordings are preserved and excluded from English playback. Without
English cached WAVs, the panel uses English browser narration and subtitles;
Stop/reset cancel narration. No cloud audio is generated automatically.

