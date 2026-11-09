# MALONI Humanoid 120 a showroom

Samostatný MALONI Humanoid 120 má vlastní diferenciální kolovou dynamiku, osm řízených os hlavy a paží, komunikaci v češtině/angličtině a napojení na návštěvu showroomu. Původní G1 zůstává dostupný.

```bash
git clone https://github.com/malonitest/Maloni.git humanoid_ws
cd humanoid_ws
python3 -m venv .venv
.venv/bin/python -m pip install numpy==2.5.3
bash start_showroom.sh --robot maloni120
```

MALONI nepotřebuje MuJoCo, ONNX ani nativní knihovnu pro G1. Hotové webové soubory a potřebné grafické podklady jsou součástí repozitáře. Node.js je potřeba pouze pro úpravy frontendu (`npm ci && npm run build` v `chery_showroom/web`).

Pro G1 nejprve obnovte původní závislosti podle návodu níže. Nativní showroom G1 navíc potřebuje CMake, Eigen3 a Bullet Collision (Ubuntu: `sudo apt-get install cmake libeigen3-dev libbullet-dev`). Potom spusťte `bash start_showroom.sh --robot g1`; launcher sestaví jeho nativní knihovnu.

- [Implementace, spuštění, výsledky testů a limity fyziky](MALONI_120_PHYSICS.md)
- [Souhrn ověření](MALONI_120_VALIDATION.json)
- [Návrh českého blogového článku](docs/blog/maloni-humanoid-120-showroom.md)
- [Postup publikace blogu](MALONI_120_UPDATE.md)
- [Původ a kontrolní součty grafických podkladů](MALONI_120_ASSET_PROVENANCE.json)

Fyzika MALONI je rovinná s odhadnutými parametry. Neověřuje převrácení, schody ani schopnosti fyzického prototypu. Blog zůstává návrhem, zveřejnění na webu není součástí této aktualizace.

---

# Maloni — Unitree G1 v MuJoCo

Simulace humanoidního robota Unitree G1: chůze řízená ONNX politikou,
ovládání klávesnicí, robotická laboratoř, tanec a asistovaný úkol přenesení
sošky Buddhy na stůl. Hlavní demonstrace běží bez ROS a DDS.

## Instalace a spuštění

Prostředí použité při vývoji: Ubuntu, Python 3.12, Linux x86_64.
ONNX Runtime přiložený v závislosti Unitree je pro Linux x86_64.
Pro grafické okno je potřeba funkční OpenGL a grafické prostředí.

```bash
sudo apt-get update
sudo apt-get install -y git g++ python3-venv libgl1 libglfw3 fonts-dejavu-core

git clone https://github.com/malonitest/Maloni.git humanoid_ws
cd humanoid_ws
bash scripts/setup.sh
bash start_g1_keyboard.sh
```

Instalace stáhne čtyři původní repozitáře Unitree na přesné commity,
obnoví uložené lokální úpravy a scény, vytvoří `.venv` a sestaví
`keyboard_walk/policy_runner`. Vyžaduje připojení k internetu.
Verze MuJoCo a NumPy v `requirements.txt` odpovídají původnímu prostředí.

```bash
# Ruční chůze
bash start_g1_keyboard.sh --task none
# Kontrola simulace bez grafického okna
bash start_g1_keyboard.sh --headless --task none --duration 10
# Reprodukovatelný úkol Buddha
bash start_g1_keyboard.sh --headless --task buddha --seed 0 --duration 180
# Testy scény a řadiče
.venv/bin/python -m unittest discover -s keyboard_walk -p 'test_*.py'
```

## Ovládání a dokumentace

Při ručním ovládání: W/S vpřed a vzad, A/D do stran, Q/E otáčení,
mezerník zastavení, R reset, F kamera a T tanec.
V úkolu Buddha mezerník pozastaví úkol a B pokračuje.

- [Podrobný návod a popis simulace](OVLADANI_G1.md)
- `keyboard_walk/`: řadiče, generátor scény, testy a měřicí skripty.
- `g1_arm_controller.cpp`: samostatná ukázka PD regulátoru v C++17.
- `inspect_g1.py`, `inspect_motors.py`, `view_g1.py`: pomocné programy pro model G1.

Úkol Buddha je asistovaná simulační demonstrace: používá stav simulace,
inverzní kinematiku a pomocné fyzikální vazby. Podrobnosti jsou v návodu.

## Závislosti a jejich lokální úpravy

Celý projekt je obnovitelný ze zdrojů. Původní knihovny nejsou duplikované
v tomto repozitáři; jejich URL a přesné commity jsou v
[`dependencies/lock.json`](dependencies/lock.json). Všechny změněné soubory,
nové XML scény a textury jsou uložené v `dependencies/overlays/`.

```bash
# Obnovení knihoven a lokálních úprav bez instalace Python balíčků
python3 scripts/restore_dependencies.py
# Kontrola commitů a shody uložených úprav bez změn na disku
python3 scripts/restore_dependencies.py --check
```

Skript odmítne přepsat další lokální změny nebo použít jiný commit knihovny.
Pokud upravíš soubor uvnitř knihovny Unitree, promítni změnu také do
`dependencies/overlays/` a aktualizuj jeho SHA-256 v `dependencies/lock.json`.
Samotné složky `unitree_*` jsou v `.gitignore`.

Použité projekty: [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco),
[unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab),
[unitree_ros](https://github.com/unitreerobotics/unitree_ros),
[unitree_sdk2](https://github.com/unitreerobotics/unitree_sdk2).
Jejich licence a licence přiložených modelů či knihoven zůstávají v původních
repozitářích; tento repozitář jim nepřiděluje novou licenci.

Virtuální prostředí, cache, sestavené programy, provozní logy a lokální
nastavení editoru se neukládají. Report, uložené výsledky měření a náhledy nejsou součástí veřejné kopie.
