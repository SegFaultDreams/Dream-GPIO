# test GPIO18 : la LED doit respirer. si elle respire, le Pi est vivant.
from signal import pause
from gpiozero import PWMLED

led = PWMLED(18)
led.pulse()
pause()
