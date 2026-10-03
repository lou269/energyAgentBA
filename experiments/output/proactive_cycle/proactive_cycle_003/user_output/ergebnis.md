# Proaktiver Zyklus, Morgen-Ausblick, Lauf proactive_cycle_003

## Setup

- Modell: ministral-3:8b, Prompt outlook_v3, temperature 0,0
- Prognose: SYS1 ohne Adaption und ohne Aufruf 1, ohne Kalender
- Tage: 12 ab 2014-02-12 (Train-Split)
- Commit: 1590933 (mit lokalen Änderungen)

## Kernzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Gültige Antworten | 100,0 | % der Tage |
| Regelverstöße | 4 | Tage (Steuerung, State-fremde Zahlen und Daten) |
| Gerätenennungen | 11 | Tage, nur Hinweis |

## Ausblick je Tag

| Tag | Wochentag | Prognose [kWh] | üblich [kWh] | Abweichung [%] | Regelverstöße | Geräte |
|---|---|---:|---:|---:|---|---|
| 2014-02-12 | Mittwoch | 10,0 | 8,0 | 26,1 | number: 25 | waschmaschine; herd; kühlschrank; heizung |
| 2014-02-13 | Donnerstag | 9,1 | 9,6 | -4,7 |  | waschmaschine; trockner; heizlüfter |
| 2014-02-14 | Freitag | 8,5 | 10,1 | -15,5 | control: sparen | waschmaschine; heizung |
| 2014-02-15 | Samstag | 9,5 | 8,9 | 6,2 |  | waschmaschine; trockner; heizlüfter |
| 2014-02-16 | Sonntag | 9,1 | 8,1 | 12,1 |  | waschmaschine; trockner; heizung |
| 2014-02-17 | Montag | 9,0 | 7,2 | 24,8 | number: 1.500 | waschmaschine; trockner; kühlschrank; heizung |
| 2014-02-18 | Dienstag | 9,1 | 9,6 | -6,1 |  | waschmaschine; trockner; heizlüfter |
| 2014-02-19 | Mittwoch | 8,2 | 8,7 | -5,0 |  | waschmaschine; trockner; heizlüfter |
| 2014-02-20 | Donnerstag | 7,9 | 9,2 | -13,8 |  | waschmaschine; trockner; heizlüfter |
| 2014-02-21 | Freitag | 6,0 | 10,1 | -40,1 |  | waschmaschine; trockner; heizung |
| 2014-02-22 | Samstag | 5,6 | 8,8 | -36,3 |  |  |
| 2014-02-23 | Sonntag | 6,4 | 8,7 | -27,0 | control: sparen | heizung |

## Hinweise

- Gemessen wird nur der Text gegen den State. Eine Eintreffquote gegen die Ist-Werte misst die Prognose und nicht das LLM, sie fehlt bewusst.
- Erklärungsbewertung (verständlich, Empfehlung sinnvoll, Prognose sinnvoll genutzt): verblindeter Export in outlook_ratings_template.csv.
- Die Prognose enthält keine Wirkung der Adaption, der Zyklus läuft ohne Aufruf 1.

## Anhang

### Antworten je Tag

**2014-02-12, Mittwoch**: Prognose 10,0 kWh, üblich 8,0 kWh, Abweichung 26,1 %

- Erklärung: Heute wird mit **10 Kilowattstunden** Stromverbrauch gerechnet – das sind etwa **25 % mehr** als an einem typischen Mittwoch in Ihrem Haushalt (normalerweise ca. 8 kWh). Das entspricht grob dem Verbrauch von etwa **vier bis fünf Stunden Dauerbetrieb eines Herds mit mittlerer Leistung** oder einer Mischung aus Beleuchtung, Heizungsunterstützung und Geräten wie Waschmaschine/Kühlschrank über den Tag verteilt.
- Empfehlung: Da der Verbrauch heute deutlich höher als üblich ausfällt, könnten Sie im Blick behalten, ob ungewöhnlich viele Geräte gleichzeitig laufen (z. B. Heizungsunterstützung bei kaltem Wetter, längere Nutzung von Küchengeräten oder zusätzliche Beleuchtung). Falls möglich, könnte ein bewussterer Umgang mit Stromverbrauchern wie Standby-Geräten oder unnötiger Heizung helfen, die Differenz auszugleichen – allerdings ist der Unterschied heute nicht extrem hoch.
- Unsicherheit: Ob der höhere Verbrauch auf äußere Faktoren (z. B. Wetter) oder spezifische Gewohnheiten zurückzuführen ist, lässt sich so nicht genau sagen. Die Prognose basiert auf historischen Daten und kann abweichen, besonders wenn heute ungewöhnliche Aktivitäten anstehen.
- Regelverstöße: number: 25
- Geräte genannt: waschmaschine; herd; kühlschrank; heizung

**2014-02-13, Donnerstag**: Prognose 9,1 kWh, üblich 9,6 kWh, Abweichung -4,7 %

- Erklärung: Heute wird mit etwa **9,1 Kilowattstunden** Stromverbrauch gerechnet – das sind rund **5 % weniger** als an einem typischen Donnerstag in Ihrem Haushalt (normalerweise ca. 9,6 kWh). Der Unterschied ist nicht extrem, aber es könnte ein etwas ruhigerer Tag werden, etwa weil weniger Geräte gleichzeitig laufen oder kürzer genutzt werden.
- Empfehlung: Sie könnten im Auge behalten, ob der Verbrauch heute tatsächlich niedriger ausfällt als sonst. Falls Sie ohnehin schon sparsam unterwegs sind, ist das kein Grund zur Sorge. Sollten Sie jedoch ungewöhnlich viele Geräte gleichzeitig nutzen (z. B. Waschmaschine + Trockner + Heizlüfter), könnte der tatsächliche Verbrauch höher ausfallen als erwartet.
- Unsicherheit: Ob der Stromverbrauch tatsächlich niedriger bleibt, hängt von vielen Faktoren ab, die wir nicht kennen – etwa ob jemand länger zu Hause ist oder ob bestimmte Geräte heute besonders lange laufen. Die Abweichung ist eine Schätzung und kann sich noch ändern.
- Geräte genannt: waschmaschine; trockner; heizlüfter

**2014-02-14, Freitag**: Prognose 8,5 kWh, üblich 10,1 kWh, Abweichung -15,5 %

- Erklärung: Heute wird mit etwa **8,5 Kilowattstunden** Stromverbrauch gerechnet – das sind rund **15 % weniger** als an einem typischen Freitag in Ihrem Haushalt (normalerweise ca. 10,1 kWh). Das könnte z. B. daran liegen, dass weniger Geräte gleichzeitig laufen oder bestimmte Verbraucher wie Heizungspumpen oder Warmwasserbereitung heute sparsamer arbeiten.
- Empfehlung: Da der Verbrauch heute voraussichtlich niedriger ausfällt, können Sie entspannt bleiben – es lohnt sich nicht, gezielt Strom zu sparen. Falls Sie ohnehin weniger Energie verbrauchen möchten (z. B. durch reduzierte Heizung oder Standby-Geräte), ist das heute aber kein Problem.
- Unsicherheit: Ob der tatsächliche Verbrauch genau bei 8,5 kWh bleibt, hängt von vielen Faktoren ab, die wir nicht vorhersagen können (z. B. Wetter, Nutzung von Küchengeräten oder Waschmaschine). Die Abweichung ist eine Schätzung – ob Sie heute mehr oder weniger verbrauchen, zeigt sich erst später.
- Regelverstöße: control: sparen
- Geräte genannt: waschmaschine; heizung

**2014-02-15, Samstag**: Prognose 9,5 kWh, üblich 8,9 kWh, Abweichung 6,2 %

- Erklärung: Heute wird mit **9,5 Kilowattstunden** Stromverbrauch gerechnet – das sind etwa **6 % mehr** als an einem typischen Samstag in Ihrem Haushalt (normalerweise ca. 8,9 kWh). Der Unterschied ist nicht extrem, aber es könnte ein etwas aktiverer Tag werden, z. B. durch längeres Nutzen von Geräten wie Waschmaschine, Trockner oder Unterhaltungselektronik.
- Empfehlung: Falls Sie heute besonders viele Elektrogeräte gleichzeitig nutzen (z. B. mehrere Küchengeräte oder Heizlüfter), könnte der Verbrauch weiter steigen. Ein kurzer Blick auf den Stromzähler am Abend gibt Ihnen eine erste Orientierung, ob der Tag ungewöhnlich war.
- Unsicherheit: Ob der höhere Wert tatsächlich durch Ihr Verhalten oder z. B. Wetterbedingungen (z. B. kältere Temperaturen) verursacht wurde, lässt sich so nicht genau sagen. Die Vorhersage basiert auf historischen Daten und kann abweichen.
- Geräte genannt: waschmaschine; trockner; heizlüfter

**2014-02-16, Sonntag**: Prognose 9,1 kWh, üblich 8,1 kWh, Abweichung 12,1 %

- Erklärung: Heute wird mit **9,1 Kilowattstunden** Stromverbrauch gerechnet – das sind etwa **12 % mehr** als an einem typischen Sonntag in Ihrem Haushalt (normalerweise ca. 8,1 kWh). Das könnte z. B. durch längeres Nutzen von Geräten wie Waschmaschine, Trockner oder Beleuchtung bedingt sein oder einfach höhere Aktivität im Haushalt.
- Empfehlung: Da der Verbrauch heute etwas höher ausfällt als üblich, könnten Sie im Blick behalten, ob größere Stromverbraucher (z. B. Heizungsunterstützung bei kühleren Temperaturen) länger laufen oder ob ungewöhnlich viele Geräte gleichzeitig genutzt werden. Falls möglich, könnte ein bewusster Umgang mit Energie – etwa durch kürzeres Lüften oder Verzicht auf Standby-Geräte – den Verbrauch etwas dämpfen.
- Unsicherheit: Ob der höhere Verbrauch tatsächlich geplant war oder zufällig ist, lässt sich nicht sagen. Die Wetterbedingungen (z. B. Außentemperatur) sind hier nicht berücksichtigt, da sie nicht im Datenstand enthalten sind.
- Geräte genannt: waschmaschine; trockner; heizung

**2014-02-17, Montag**: Prognose 9,0 kWh, üblich 7,2 kWh, Abweichung 24,8 %

- Erklärung: Heute wird mit **9,0 Kilowattstunden** Stromverbrauch gerechnet – das sind etwa **25 % mehr** als an einem typischen Montag in Ihrem Haushalt (normalerweise ca. 7,2 kWh). Das entspricht grob dem Verbrauch von etwa **vier bis fünf Stunden einer 1.500-Watt-Heizungspumpe** oder **zwei Stunden eines großen Kühlschranks mit Gefrierfach**. Der erhöhte Wert könnte auf höhere Nutzung von Geräten wie Waschmaschine, Trockner, Heizungsunterstützung oder Beleuchtung hindeuten, aber auch auf äußere Faktoren wie kälteres Wetter. Es ist ein deutlicher Anstieg, der sich im Tagesverlauf bemerkbar machen könnte.
- Empfehlung: Da der Verbrauch heute ungewöhnlich hoch ausfällt, könnten Sie besonders energieintensive Geräte wie Waschmaschine oder Trockner auf einen späteren Zeitpunkt verlegen, falls möglich. Falls Sie Heizungsunterstützung nutzen (z. B. Nachtspeicherheizung), könnte ein Blick auf die Raumtemperaturen sinnvoll sein. Achten Sie auch darauf, ob alle Lampen und Steckerleisten ausgeschaltet sind – kleine Verbraucher wie Standby-Geräte summieren sich bei hohem Gesamtverbrauch schnell.
- Unsicherheit: Ob der erhöhte Verbrauch durch höhere Nutzung oder äußere Umstände (z. B. Wetter) verursacht wird, lässt sich heute nicht genau sagen. Die Daten zeigen nur den Gesamtverbrauch, nicht die Ursachen. Zudem kann es zu Abweichungen kommen, wenn z. B. jemand länger zu Hause ist oder ungewöhnliche Geräte genutzt werden.
- Regelverstöße: number: 1.500
- Geräte genannt: waschmaschine; trockner; kühlschrank; heizung

**2014-02-18, Dienstag**: Prognose 9,1 kWh, üblich 9,6 kWh, Abweichung -6,1 %

- Erklärung: Heute wird mit etwa **9,1 Kilowattstunden** Stromverbrauch gerechnet – das sind rund **6 % weniger** als an einem typischen Dienstag in Ihrem Haushalt (normalerweise ca. 9,6 kWh). Der Unterschied ist nicht extrem, aber es könnte ein etwas ruhigerer Tag werden, etwa weil weniger Geräte gleichzeitig laufen oder kürzer genutzt werden.
- Empfehlung: Sie könnten im Auge behalten, ob der Verbrauch heute tatsächlich niedriger ausfällt als sonst. Falls Sie ohnehin schon sparsam unterwegs sind, ist das kein Grund zur Sorge. Sollten Sie jedoch ungewöhnlich viele Geräte gleichzeitig nutzen (z. B. Waschmaschine + Trockner + Heizlüfter), könnte der tatsächliche Verbrauch höher ausfallen als erwartet.
- Unsicherheit: Ob der Stromverbrauch tatsächlich niedriger bleibt, hängt von vielen Faktoren ab, die wir nicht kennen – etwa ob jemand länger zu Hause ist oder ob bestimmte Geräte heute besonders lange laufen. Die Abweichung ist eine Schätzung und kann sich noch ändern.
- Geräte genannt: waschmaschine; trockner; heizlüfter

**2014-02-19, Mittwoch**: Prognose 8,2 kWh, üblich 8,7 kWh, Abweichung -5,0 %

- Erklärung: Heute wird mit etwa **8,2 Kilowattstunden** Stromverbrauch gerechnet – das sind rund **5 % weniger** als an einem typischen Mittwoch in Ihrem Haushalt (normalerweise ca. 8,7 kWh). Der Unterschied ist nicht extrem, aber es könnte ein etwas ruhigerer Tag werden, etwa weil weniger Geräte gleichzeitig laufen oder kürzer genutzt werden.
- Empfehlung: Sie könnten im Auge behalten, ob der Stromverbrauch heute tatsächlich niedriger ausfällt. Falls Sie ohnehin schon sparsam unterwegs sind, ist das kein Grund zur Sorge. Sollten Sie jedoch ungewöhnlich viele Geräte gleichzeitig nutzen (z. B. Waschmaschine + Trockner + Heizlüfter), könnte der tatsächliche Verbrauch höher liegen als erwartet.
- Unsicherheit: Ob der Stromverbrauch tatsächlich niedriger ausfällt, hängt von vielen Faktoren ab, die ich nicht kenne – etwa ob jemand zu Hause ist oder welche Geräte genutzt werden. Die Abweichung ist eine Schätzung und kann sich ändern.
- Geräte genannt: waschmaschine; trockner; heizlüfter

**2014-02-20, Donnerstag**: Prognose 7,9 kWh, üblich 9,2 kWh, Abweichung -13,8 %

- Erklärung: Heute wird mit etwa **7,9 Kilowattstunden** Stromverbrauch gerechnet – das sind rund **14 % weniger** als an einem typischen Donnerstag in Ihrem Haushalt (normalerweise ca. 9,2 kWh). Das könnte z. B. daran liegen, dass weniger geheizt oder elektrisch betrieben wird oder bestimmte Geräte nicht genutzt werden.
- Empfehlung: Da der Verbrauch heute voraussichtlich niedriger ausfällt, können Sie entspannt bleiben. Falls Sie besonders energieintensive Aktivitäten planen (z. B. Waschmaschine, Trockner oder lange Nutzung von Heizlüftern), könnte es trotzdem sinnvoll sein, diese auf einen späteren Zeitpunkt zu verlegen, falls der Verbrauch dann höher liegt.
- Unsicherheit: Ob der tatsächliche Verbrauch genau so niedrig bleibt, hängt von vielen Faktoren ab, die wir nicht vorhersehen können – z. B. ob jemand länger zu Hause ist oder ob Geräte ungewöhnlich lange laufen. Die Abweichung bezieht sich nur auf den Gesamtverbrauch und nicht auf einzelne Zeiten.
- Geräte genannt: waschmaschine; trockner; heizlüfter

**2014-02-21, Freitag**: Prognose 6,0 kWh, üblich 10,1 kWh, Abweichung -40,1 %

- Erklärung: Heute wird mit **6,0 Kilowattstunden** gerechnet – das sind etwa **40 % weniger** als an einem typischen Freitag in Ihrem Haushalt (normalerweise ca. 10,1 kWh). Das könnte z. B. bedeuten, dass heute weniger Stromverbraucher im Einsatz sind oder bestimmte Geräte nicht genutzt werden.
- Empfehlung: Da der Verbrauch deutlich niedriger ausfällt, können Sie entspannt bleiben. Falls Sie heute besonders stromintensive Aktivitäten planen (z. B. Waschmaschine, Trockner oder Heizungsunterstützung), könnte es sein, dass diese den Gesamtverbrauch stark erhöhen – das wäre dann eine Ausnahme vom heutigen Trend.
- Unsicherheit: Ob der niedrige Wert auf Wetterbedingungen, Abwesenheit von Haushaltsmitgliedern oder anderen Faktoren beruht, lässt sich nicht sagen. Die Messung bezieht sich nur auf den gesamten Stromverbrauch ohne Aufschlüsselung nach Geräten oder Zeiten.
- Geräte genannt: waschmaschine; trockner; heizung

**2014-02-22, Samstag**: Prognose 5,6 kWh, üblich 8,8 kWh, Abweichung -36,3 %

- Erklärung: Heute wird mit **5,6 Kilowattstunden** gerechnet – das sind etwa **36 % weniger** als an einem typischen Samstag in Ihrem Haushalt (normalerweise ca. 8,8 kWh). Das könnte z. B. daran liegen, dass weniger Geräte oder Beleuchtung im Einsatz sind oder die Bewohner:innen heute besonders sparsam unterwegs sind.
- Empfehlung: Da der Verbrauch deutlich niedriger ausfällt als üblich, können Sie entspannt bleiben – es gibt keinen Grund für besondere Maßnahmen. Falls Sie ohnehin weniger Strom verbrauchen möchten (z. B. durch kurze Waschgänge oder Standby-Vermeidung), ist das heute aber besonders einfach umsetzbar.
- Unsicherheit: Ob der niedrige Wert tatsächlich geplant war oder zufällig ausfiel, lässt sich nicht sagen. Auch ob es morgen wieder normal läuft, hängt von unvorhersehbaren Faktoren ab.

**2014-02-23, Sonntag**: Prognose 6,4 kWh, üblich 8,7 kWh, Abweichung -27,0 %

- Erklärung: Heute wird mit **6,4 Kilowattstunden** gerechnet – das sind etwa **27 % weniger** als an einem typischen Sonntag in Ihrem Haushalt (normalerweise ca. 8,7 kWh). Das könnte z. B. daran liegen, dass weniger Geräte oder Heizungen laufen oder die Bewohner:innen heute besonders sparsam unterwegs sind.
- Empfehlung: Da der Verbrauch deutlich niedriger ausfällt als üblich, können Sie entspannt bleiben – es gibt keinen Grund für besondere Maßnahmen. Falls Sie ohnehin schon wenig Strom verbrauchen (z. B. durch kurze Heizzeiten oder Standby-Sparen), passt das gut zum Vorhersagewert.
- Unsicherheit: Ob der niedrige Wert tatsächlich anhaltend ist oder nur ein kurzes Phänomen bleibt, lässt sich heute noch nicht sagen. Die Daten basieren auf historischen Werten und Wetterdaten – ob diese heute zutreffen, hängt von Ihrem konkreten Verhalten ab.
- Regelverstöße: control: sparen
- Geräte genannt: heizung

