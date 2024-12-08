# Branchement

Numérotation physique des broches du Pi (1 à 40) + numéro BCM entre parenthèses.
Le code utilise les numéros BCM.

## Pi -> ADS1299

| Pi | | ADS1299 | remarque |
|---|---|---|---|
| 1 | 3V3 | DVDD | logique 3,3 V |
| 2 | 5V | AVDD (via le régulateur du module) | analogique |
| 6 | GND | DGND / AGND | masse commune, en étoile près de la carte |
| 19 | MOSI (GPIO10) | DIN | |
| 21 | MISO (GPIO9) | DOUT | |
| 23 | SCLK (GPIO11) | SCLK | |
| 24 | CE0 (GPIO8) | CS | |
| 11 | GPIO17 | DRDY | actif bas, pull-up côté Pi |
| 15 | GPIO22 | RESET | |
| 13 | GPIO27 | START | |
| | | PWDN | tiré au 3V3 (jamais en power-down) |

SPI mode 1 (CPOL=0, CPHA=1). Si tu lis `0x00` ou `0xFF` comme ID, c'est le mode SPI
ou un fil de MISO. J'ai perdu une soirée entière sur le mode.

## Électrodes -> ADS1299

| voie | entrée | position 10-20 |
|---|---|---|
| CH1 | IN1P | Fp1 |
| CH2 | IN2P | Fp2 |
| CH3 | IN3P | F3 |
| CH4 | IN4P | F4 |
| CH5 | IN5P | C3 |
| CH6 | IN6P | C4 |
| CH7 | IN7P | O1 |
| CH8 | IN8P | O2 |
| référence | SRB1 | clip lobe d'oreille gauche |
| BIAS | BIASOUT | clip lobe d'oreille droit |

Toutes les entrées négatives sont reliées à SRB1 en interne (registre MISC1 = 0x20),
donc tout est en référence commune sur l'oreille gauche.

## Sorties GPIO (cues)

```
GPIO18 (pin 12) ──[330 Ω]──>|── GND          LED rouge 5 mm, derrière un masque de nuit
                                           (PWM, 15 % max dans le code)

GPIO23 (pin 16) ──[1 kΩ]── base 2N2222
                            collecteur ── vibreur ── 3V3
                            émetteur ── GND
                            1N4148 en inverse aux bornes du vibreur
```

## Schéma d'ensemble

```
   bonnet (8 électrodes sèches)
        │  nappe 10 fils (8 voies + SRB1 + BIAS)
        ▼
 ┌───────────────┐   SPI + DRDY/RESET/START   ┌──────────────────┐
 │  ADS1299      │ ─────────────────────────> │ Raspberry Pi     │ ── wifi ── MQTT / SSH
 │  8 voies      │                            │ Zero 2 W         │
 └───────────────┘                            └──────────────────┘
        ▲                                        │        │
        │ 3V3 / 5V / GND                        LED    vibreur
        └──────────────── batterie USB ──────────┘
            (tout ça scotché sur une boîte à chaussures)
```
