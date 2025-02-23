"""
La partie GPIO de Dream-GPIO.

Quand le staging voit du REM plusieurs époques d'affilée, on envoie un
signal discret : LED rouge qui pulse à travers les paupières, et/ou petit
vibreur au poignet. Idée classique des masques de rêve lucide des années 90,
en version bricolée. Le but : que le signal rentre dans le rêve et que
je me dise « tiens, je rêve ».

DÉSACTIVÉ PAR DÉFAUT. Un cue mal réglé = tu te réveilles toutes les
20 minutes et tu finis la nuit sur le canapé. (vécu)
"""

import time

try:
    from gpiozero import PWMLED, DigitalOutputDevice
except ImportError:
    PWMLED = DigitalOutputDevice = None


class RemCue:
    def __init__(self, led_pin=18, vib_pin=23, enabled=False,
                 min_rem_epochs=3, cooldown_s=600, led_max=0.15):
        self.enabled = enabled
        self.min_rem_epochs = min_rem_epochs
        self.cooldown_s = cooldown_s
        self.led_max = led_max  # 15 % max. au-delà ça réveille, point
        self._streak = 0
        self._last_cue = float("-inf")
        self.led = PWMLED(led_pin) if (enabled and PWMLED) else None
        self.vib = DigitalOutputDevice(vib_pin) if (enabled and DigitalOutputDevice) else None

    def update(self, stage, now=None):
        """À appeler à chaque époque. Retourne True si un cue est parti."""
        now = time.monotonic() if now is None else now
        self._streak = self._streak + 1 if stage == "REM" else 0
        ready = (self._streak >= self.min_rem_epochs
                 and now - self._last_cue >= self.cooldown_s)
        if ready:
            self._last_cue = now
            if self.enabled:
                self.fire()
            return True
        return False

    def fire(self, pulses=3):
        for _ in range(pulses):
            if self.led:
                # rampe à la main : pulse() de gpiozero monte à 100 %, beaucoup trop
                for k in list(range(0, 21)) + list(range(20, -1, -1)):
                    self.led.value = self.led_max * k / 20
                    time.sleep(0.04)
            if self.vib:
                self.vib.on()
                time.sleep(0.15)
                self.vib.off()
            time.sleep(0.6)

    def close(self):
        for d in (self.led, self.vib):
            if d:
                d.close()
