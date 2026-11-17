# Traverse: Starlight & Prairie - Question Kanji Inspection Report

This document analyzes the two deformed/unconfirmed kanji marked with `？` in [`tables/manual_kanji.txt`](manual_kanji.txt):
1. **`$FBD0`** (Line 15, character 0: `？々訪待好済違婦忙料理洗濯掃除所`)
2. **`$FC13`** (Line 21, character 3: `陸移死？説偉乗腹丸時秋紅葉趣隣軟`)

---

## 1. Glyph `$FBD0` -> **敵** (Enemy / Opponent)

### Glyph Pixel Art (16x16)
```
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . # . . . # . . . . . . . . .
# # # # # . # . . . . . . . . .
. # . # . . # # # # # . . . . .
. # . # . . # . . # . . . . . .
# # # # # . # . . # . . . . . .
# . # . # . . . . # . . . . . .
# # # # # . # . . # . . . . . .
# . # . # . . # # . . . . . . .
# # # # # . . . # . . . . . . .
# # # # # . . # . # . . . . . .
# . . . # . # . . . # . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
```

### Visual Anatomy
- **Left Side**: Radical **`啇`** (top horizontal, box with vertical divisions, bottom box `口`).
- **Right Side**: Radical **`攵`** (the 4-stroke task radical: `ノ一ノ乀`).
- **Composite**: `啇` + `攵` = **敵** (Enemy / Opponent).

### In-Game Script Context (39 occurrences in dialogue)
`$FBD0` appears extensively in combat ability, magic, and item descriptions:

1. **PC 0x013A91 (Bank $C1 Battle Strings)**:
   - **HEX**: `fb d0 48 fb 26 fb 14 fb 0d 5c fc 42 62 58 ff`
   - **DECODED**: `<FBD0>の防御力を<FC42>げる`
   - **READING**: **敵の防御力を下げる** ("Lowers the enemy's defense power")

2. **PC 0x013AA0 (Bank $C1 Battle Strings)**:
   - **HEX**: `fb d0 48 fb f2 5c 37 56 4e 3d 58 ff`
   - **DECODED**: `<FBD0>の目をくらませる`
   - **READING**: **敵の目をくらませる** ("Dazzles/blinds the enemy")

3. **PC 0x013AF5 (Bank $C1 Battle Strings)**:
   - **HEX**: `fb d0 45 fd 7b 5c fd 80 33 58 ff`
   - **DECODED**: `<FBD0>に<FD7B>を<FD80>える`
   - **READING**: **敵にダメージを与える** ("Deals damage to the enemy")

4. **PC 0x1B6358 (Bank $DB Scenario Text)**:
   - **HEX**: `fb d0 fc aa fb 9e 5c fc 05 56 3d 4e 3c ff`
   - **DECODED**: `<FBD0><FCAA>体を眠らせます`
   - **READING**: **敵全体を眠らせます** ("Puts all enemies to sleep")

5. **PC 0x1B63DA (Bank $DB Scenario Text)**:
   - **HEX**: `fb d0 fb fc fb ca 48 32 40 fb 44 fb 01 5c ...`
   - **DECODED**: `<FBD0>味方のうち一人を...`
   - **READING**: **敵味方のうち一人を...** ("Target one combatant, enemy or ally...")

---

## 2. Glyph `$FC13` -> **婆** (Old Woman / Midwife)

### Glyph Pixel Art (16x16)
```
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. # # . . . # . . . . . . . . .
. . . # # # # # # # . . . . . .
# # . # . . # . . # . . . . . .
. . . # # # # # # . . . . . . .
. . # # . # . . # . . . . . . .
. # . # . . # # . . . . . . . .
. . # . # # . . # # . . . . . .
. # # # # # # # # # . . . . . .
. . . # . . . # # . . . . . . .
. . . . # # # # . . . . . . . .
. # # # # . . # # # . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . .
```

### Visual Anatomy
- **Top Half**: Radical **`皮`** (top diagonal slant `ノ`, horizontal `一`, vertical `丨`, `又`).
- **Bottom Half**: Radical **`女`** (`く` stroke crossed by horizontal `一`).
- **Composite**: `皮` + `女` = **婆** (Old woman / Grandmother / Midwife).

### In-Game Script Context (74 occurrences in dialogue)
`$FC13` appears in dialogue speaker names and story dialogue:

1. **PC 0x1BAA11 - 0x1BB70A (Bank $DB Intro Cutscene - Childbirth Scene)**:
   - **HEX**: `fb 61 fc 13 ff`
   - **DECODED**: `産<FC13>`
   - **READING**: **産婆** (さんば, *Sanba* = Midwife!)
   - **Context**: The prologue event where the midwife delivers the main character's baby:
     - `産婆: このままじゃあケッタは助からないねえ...` ("At this rate, Ketta won't make it...")
     - `産婆: まだそうと決まったわけじゃない。でも、お腹の子を...` ("It's not certain yet. But the child in her belly...")
     - `産婆: うまれてくる子に罪はないよ` ("The newborn child is blameless.")
     - `おい、ばあさん、起きろ！` ("Hey, old lady, wake up!")

2. **PC 0x31165D (Bank $F1 Scenario Dialogue)**:
   - **HEX**: `34 fc 13 3a 5d fe 00 32 40 48 fd 03 49 ...`
   - **DECODED**: `お<FC13>さん<wait_auto>うちの<FD03>は よく気の付く人じゃ...`
   - **READING**: **お婆さん**、うちの嫁はよく気の付く人じゃ。息子にはもったいないぐらいでのう... ("Grandma, our daughter-in-law is so thoughtful...")

3. **PC 0x311C6D (Bank $F1 Scenario Dialogue)**:
   - **HEX**: `34 fc 13 3a 5d fe 00 45 52 48 49 3f 7d 75 ...`
   - **DECODED**: `お<FC13>さん<wait_auto>にものはたっぷりの水で ゆっくりと...`
   - **READING**: **お婆さん**、煮物はたっぷりの水でゆっくりと... ("Grandma, simmer stews slowly in plenty of water...")

4. **PC 0x314C31 (Bank $F1 Scenario Dialogue)**:
   - **HEX**: `... 死んだお<FC13>さんが話してくれた 伝説の...`
   - **DECODED**: `死んだお<FC13>さんが話してくれた 伝説の...`
   - **READING**: **死んだお婆さんが話してくれた伝説の...** ("Just like the legend my late grandmother told me...")

---

## Summary & Action
Both unconfirmed characters match the script with 100% certainty:
- **`$FBD0` = 敵**
- **`$FC13` = 婆**

You can update [`tables/manual_kanji.txt`](manual_kanji.txt):
- Line 15: replace `？` with `敵`
- Line 21: replace `？` with `婆`
