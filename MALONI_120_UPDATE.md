# MALONI Humanoid 120 — showroom a blog

**Navazující aktualizace:** vlastní fyzika MALONI a zachovaný režim G1 jsou popsány v [MALONI_120_PHYSICS.md](MALONI_120_PHYSICS.md). Níže je historický popis první vizualizační etapy.

Aktualizace: 9. listopadu 2026.

## Dodané podklady

- `Maloni Humanoid 120 – vnitřní uspořádání1.png`: koncepční vnitřní uspořádání pro HELIOS.
- `MALONI HUMANOID 120 — konstrukční podklad HELIOS1.png`: revize 02 pro konstrukční konzultaci.

Pro vizualizaci má přednost revize 02: výška 1200 mm, hlava 2 osy, každá paže 3 osy, pevné lehké dlaně a kolový podvozek. Šířka, hloubka, hmotnost, materiály a pohony nejsou potvrzené. Oba obrázky jsou koncepty bez CAD a výpočtů.

## Co je implementováno

`chery_showroom/web/src/maloni120.ts` vytváří prostorový model v Three.js přímo z geometrie. Nahrazuje viditelnou postavu G1 v `interior.ts`. Má výšku 1,2 m, dvě hnací kola, opěrná kolečka, displej, optickou lištu, pevné dlaně, modré akcenty a označení MALONI. Osy modelu: Z vzhůru, +X dopředu. Kamera robota využívá nový uzel hlavy.

Model sleduje pouze rovinnou polohu a natočení původní navigace. Kola se otáčejí podle ujeté vzdálenosti. Klouby nohou ani vertikální pohyb G1 se nepřenášejí. Jde o vizualizaci konceptu: backend, kolizní proxy, navigační obrys a pohybová politika stále vycházejí z G1. Není implementován diferenciální pohon ani fyzikální ověření MALONI 120. Paže a hlava zatím nemají řízená gesta.

Spuštění: `bash start_showroom.sh` v kořeni workspace. Obnovte stránku showroomu, pokud byla otevřená před aktualizací.

## Ověření

- TypeScript: `node node_modules/typescript/bin/tsc --noEmit` v `chery_showroom/web` — prošlo.
- Produkční sestavení: `node node_modules/vite/bin/vite.js build` — prošlo; výstup v `web/dist`.
- `node tests/maloni120.cjs` — prošlo: výška, kontakt s podlahou, šířka, pohyb kol, reset a označení konceptu.
- Sestavení upozorňuje na velikost JS balíčku a existující klasický `/locale.js` script.
- Vzhled v běžícím prohlížeči a kompletní scénář návštěvy nebyly v této aktualizaci ověřeny.

V tomto prostředí je Linux Node pro opakování kontrol dočasně v `/tmp/node-v22.16.0-linux-x64/bin/node`; běžný `npm` směřuje na nefunkční Windows instalaci.

## Připravený blog

Článek: `docs/blog/maloni-humanoid-120-showroom.md`. Obsahuje název, slug, meta description, návrh textu, popisky a alt texty. Stav je draft; nebyl publikován na web.

Postup publikace do stávajícího webu:

1. V redakčním systému vytvořit nový článek vývojového deníku s připraveným názvem a slugem. Metadata v úvodu souboru převést do polí redakce; sekci „Redakční podklady“ nevkládat do veřejného textu.
2. Z dodaných PNG připravit webové kopie WebP/AVIF a ponechat původní soubory. Zachovat čitelnost technických popisků; nabídnout zvětšení. Před zveřejněním zkontrolovat vhodnost veřejného uvedení HELIOS a interních konstrukčních informací.
3. Doplnit skutečný snímek aktualizovaného showroomu a označit jej jako simulaci. Nevydávat jej za fyzický prototyp.
4. Propojit článek ze stránky projektu a odkázat zpět na ni. Nastavit český jazyk, skutečného autora, datum publikace, kanonickou URL a Open Graph obrázek. Pro případný překlad vytvořit samostatnou jazykovou verzi.
5. Pokud web používá strukturovaná data, vyplnit BlogPosting podle skutečného autora, dat, obrázku a výsledné URL. Nepřidávat neověřené specifikace ani produktovou dostupnost.
6. Zkontrolovat mobilní náhled, odkazy, popisky a čitelnost obrázků; následně publikovat přes obvyklý postup webu.

Pro fyzikální další etapu jsou potřeba především rozchod a poloměr kol, rozměry obrysu, hmotnosti a těžiště, momenty/setrvačnosti, limity pohonů a poloha senzorů. Z ilustrací nelze tyto údaje spolehlivě určit.
