# E1 Erkennung, Lauf e1_003

## Setup

- Cutover: CO1 (2014-07-31), CO2 (2015-02-12), CO3 (2015-05-24), CO4 (2015-09-26), CO5 (2016-01-12)
- System: SYS1 ohne Adaption, die Regel ordnet ein, keine Adaption, kein LLM
- Commit: 9ef1fd9 (mit lokalen Änderungen)

## Erkennung je Ereignis über alle Cutover

| Ereignis | erwartet | erkannt | Ø Tag | Tag min–max | Skala (Spitze) | Kontrolle mit Signal [Tage] |
|---|---|---|---:|---|---|---|
| Sprung +20 % | auffällig | 4/5 | 25,5 | 17–39 | - | 0 |
| Sprung −20 % | auffällig | 3/5 | 26,7 | 12–39 | - | 0 |
| Rampe über 28 Tage +20 % | auffällig | 3/5 | 29,7 | 20–39 | - | 0 |
| Rampe über 28 Tage −20 % | auffällig | 5/5 | 32,8 | 13–45 | - | 0 |
| Rampe über 56 Tage +20 % | unauffällig | 2/5 | 45,5 | 41–50 | - | 0 |
| Rampe über 56 Tage −20 % | unauffällig | 3/5 | 41,0 | 13–55 | - | 0 |
| Spitze +670 W über 6 h | auffällig | 4/5 | 10,8 | 1–40 | daily, weekday | 3–13 |

## Hinweise

- Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet
- erkannt: Spitze = Einzeltag-Alarm (daily oder weekday), Niveauänderung und Rampe = Streak auf mehreren Skalen gleichzeitig (weekly und long_term). Gezählt wird der erste Tag, an dem das Ereignis den Kennwert hat und der Kontrolllauf desselben Cutovers nicht
- erwartet: auffällig = der Vorfilter soll das Ereignis melden, unauffällig = still bleiben (Rampe über 56 Tage gilt nicht als Ereignis). Kein Maß für die Einordnung
- Ø Tag und Tag min–max nur über die erkannten Fälle, nicht erkannt = nie innerhalb des Fensters
- Skala (Spitze): dominante Einzeltag-Skala am Erkennungstag, bei Niveau und Rampen gilt immer der Streak auf weekly und long_term
- Kontrolle mit Signal: Tage ab Cutover, an denen der Kontrolllauf denselben Kennwert hat (echte Saison, Rauschen), min–max über die Cutover. Ohne Adaption wird die Referenz nie bereinigt, die Zahl ist daher höher als im Gesamtsystem

## Anhang

### Erkennung je Cutover und Ereignis

| Cutover | Ereignis | erkannt am Tag | Skala (Spitze) | Kontrolle mit Signal [Tage] |
|---|---|---:|---|---:|
| 2014-07-31 | Sprung +20 % | 39 | - | 0 |
| 2015-02-12 | Sprung +20 % | 17 | - | 0 |
| 2015-05-24 | Sprung +20 % | - | - | 0 |
| 2015-09-26 | Sprung +20 % | 28 | - | 0 |
| 2016-01-12 | Sprung +20 % | 18 | - | 0 |
| 2014-07-31 | Sprung −20 % | - | - | 0 |
| 2015-02-12 | Sprung −20 % | 29 | - | 0 |
| 2015-05-24 | Sprung −20 % | 12 | - | 0 |
| 2015-09-26 | Sprung −20 % | 39 | - | 0 |
| 2016-01-12 | Sprung −20 % | - | - | 0 |
| 2014-07-31 | Rampe über 28 Tage +20 % | 39 | - | 0 |
| 2015-02-12 | Rampe über 28 Tage +20 % | - | - | 0 |
| 2015-05-24 | Rampe über 28 Tage +20 % | - | - | 0 |
| 2015-09-26 | Rampe über 28 Tage +20 % | 30 | - | 0 |
| 2016-01-12 | Rampe über 28 Tage +20 % | 20 | - | 0 |
| 2014-07-31 | Rampe über 28 Tage −20 % | 29 | - | 0 |
| 2015-02-12 | Rampe über 28 Tage −20 % | 36 | - | 0 |
| 2015-05-24 | Rampe über 28 Tage −20 % | 13 | - | 0 |
| 2015-09-26 | Rampe über 28 Tage −20 % | 41 | - | 0 |
| 2016-01-12 | Rampe über 28 Tage −20 % | 45 | - | 0 |
| 2014-07-31 | Rampe über 56 Tage +20 % | 41 | - | 0 |
| 2015-02-12 | Rampe über 56 Tage +20 % | - | - | 0 |
| 2015-05-24 | Rampe über 56 Tage +20 % | - | - | 0 |
| 2015-09-26 | Rampe über 56 Tage +20 % | 50 | - | 0 |
| 2016-01-12 | Rampe über 56 Tage +20 % | - | - | 0 |
| 2014-07-31 | Rampe über 56 Tage −20 % | - | - | 0 |
| 2015-02-12 | Rampe über 56 Tage −20 % | 55 | - | 0 |
| 2015-05-24 | Rampe über 56 Tage −20 % | 13 | - | 0 |
| 2015-09-26 | Rampe über 56 Tage −20 % | - | - | 0 |
| 2016-01-12 | Rampe über 56 Tage −20 % | 55 | - | 0 |
| 2014-07-31 | Spitze +670 W über 6 h | 1 | weekday | 3 |
| 2015-02-12 | Spitze +670 W über 6 h | 1 | daily | 7 |
| 2015-05-24 | Spitze +670 W über 6 h | 40 | weekday | 4 |
| 2015-09-26 | Spitze +670 W über 6 h | - | - | 13 |
| 2016-01-12 | Spitze +670 W über 6 h | 1 | weekday | 5 |
