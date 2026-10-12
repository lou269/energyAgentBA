# E1 Erkennung, Lauf e1_005

## Setup

- Cutover: CO6 (2016-12-02), CO7 (2017-02-20)
- System: SYS1 ohne Adaption, die Regel ordnet ein, keine Adaption, kein LLM
- Commit: 3d72d3e

## Erkennung je Ereignis über alle Cutover

| Ereignis | erwartet | erkannt | Ø Tag | Tag min–max | Skala (Spitze) | Kontrolle mit Signal [Tage] |
|---|---|---|---:|---|---|---|
| Sprung +20 % | auffällig | 0/2 | - | - | - | 0 |
| Sprung −20 % | auffällig | 1/2 | 31,0 | 31 | - | 0 |
| Rampe über 28 Tage +20 % | auffällig | 1/2 | 50,0 | 50 | - | 0 |
| Rampe über 28 Tage −20 % | auffällig | 2/2 | 44,0 | 31–57 | - | 0 |
| Rampe über 56 Tage +20 % | unauffällig | 1/2 | 57,0 | 57 | - | 0 |
| Rampe über 56 Tage −20 % | unauffällig | 1/2 | 57,0 | 57 | - | 0 |
| Spitze +670 W über 6 h | auffällig | 1/2 | - | - | weekday | 0–1 |

## Hinweise

- Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet
- erkannt: Spitze = Einzeltag-Alarm (daily oder weekday) an Tag 1, dem Tag ihres Einbaus, Niveauänderung und Rampe = Streak auf mehreren Skalen gleichzeitig (weekly und long_term). Gezählt wird der erste Tag, an dem das Ereignis den Kennwert hat und der Kontrolllauf desselben Cutovers nicht
- erwartet: auffällig = der Vorfilter soll das Ereignis melden, unauffällig = still bleiben (Rampe über 56 Tage gilt nicht als Ereignis). Kein Maß für die Einordnung
- Ø Tag und Tag min–max nur über die erkannten Fälle, nicht erkannt = nie innerhalb des Fensters. Bei der Spitze entfallen sie, sie zählt nur an Tag 1
- Skala (Spitze): dominante Einzeltag-Skala am Erkennungstag, bei Niveau und Rampen gilt immer der Streak auf weekly und long_term
- Kontrolle mit Signal: Tage ab Cutover (Spitze: Tag 1), an denen der Kontrolllauf denselben Kennwert hat (echte Saison, Rauschen), min–max über die Cutover.

## Anhang

### Erkennung je Cutover und Ereignis

| Cutover | Ereignis | erkannt am Tag | Skala (Spitze) | Kontrolle mit Signal [Tage] |
|---|---|---:|---|---:|
| 2016-12-02 | Sprung +20 % | - | - | 0 |
| 2017-02-20 | Sprung +20 % | - | - | 0 |
| 2016-12-02 | Sprung −20 % | 31 | - | 0 |
| 2017-02-20 | Sprung −20 % | - | - | 0 |
| 2016-12-02 | Rampe über 28 Tage +20 % | 50 | - | 0 |
| 2017-02-20 | Rampe über 28 Tage +20 % | - | - | 0 |
| 2016-12-02 | Rampe über 28 Tage −20 % | 31 | - | 0 |
| 2017-02-20 | Rampe über 28 Tage −20 % | 57 | - | 0 |
| 2016-12-02 | Rampe über 56 Tage +20 % | 57 | - | 0 |
| 2017-02-20 | Rampe über 56 Tage +20 % | - | - | 0 |
| 2016-12-02 | Rampe über 56 Tage −20 % | - | - | 0 |
| 2017-02-20 | Rampe über 56 Tage −20 % | 57 | - | 0 |
| 2016-12-02 | Spitze +670 W über 6 h | - | - | 1 |
| 2017-02-20 | Spitze +670 W über 6 h | 1 | weekday | 0 |
