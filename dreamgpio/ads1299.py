"""
Driver minimal pour l'ADS1299 (TI), 8 voies, sur le SPI du Raspberry Pi.

Datasheet : https://www.ti.com/product/ADS1299 (SBAS499)
J'ai tout lu. Deux fois. Le chapitre 9 trois fois.

Branchement : voir hardware/wiring.md
"""

import time

try:
    import spidev
    from gpiozero import DigitalInputDevice, DigitalOutputDevice
except ImportError:  # pour pouvoir lancer les tests sur un laptop
    spidev = None

# --- commandes SPI (datasheet 9.5.2) ---
WAKEUP = 0x02
STANDBY = 0x04
RESET = 0x06
START = 0x08
STOP = 0x0A
RDATAC = 0x10
SDATAC = 0x11
RDATA = 0x12
RREG = 0x20
WREG = 0x40

# --- registres (datasheet 9.6) ---
REG_ID = 0x00
REG_CONFIG1 = 0x01
REG_CONFIG2 = 0x02
REG_CONFIG3 = 0x03
REG_LOFF = 0x04
REG_CH1SET = 0x05  # CH1SET..CH8SET = 0x05..0x0C
REG_BIAS_SENSP = 0x0D
REG_BIAS_SENSN = 0x0E
REG_MISC1 = 0x15

EXPECTED_ID = 0x3E  # ADS1299 8 voies. si tua s 0x00 ou 0xFF, c'est ton cablage

# CONFIG1 : bits 7 et 4 réservés à 1, DR[2:0] = débit
SAMPLE_RATES = {250: 0x96, 500: 0x95, 1000: 0x94}

# CHnSET : gain sur les bits 6:4
GAINS = {1: 0x00, 2: 0x10, 4: 0x20, 6: 0x30, 8: 0x40, 12: 0x50, 24: 0x60}

VREF = 4.5
FRAME_BYTES = 27  # 3 octets de status + 8 voies x 3 octets
N_CHANNELS = 8


def counts_to_uv(raw, gain):
    """Code 24 bits signé -> microvolts."""
    return raw * (2 * VREF / gain) / (2 ** 24) * 1e6


def parse_frame(frame, gain=24):
    """Découpe une trame de 27 octets. Retourne (status, [8 valeurs en uV])."""
    if len(frame) != FRAME_BYTES:
        raise ValueError(f"trame de {len(frame)} octets, j'en attends {FRAME_BYTES}")
    status = (frame[0] << 16) | (frame[1] << 8) | frame[2]
    # les 4 premiers bits du status valent toujours 1100, sinon on est désynchro
    if (status >> 20) != 0b1100:
        raise ValueError(f"status bizarre : {status:06X} (désynchro SPI ?)")
    values = []
    for ch in range(N_CHANNELS):
        i = 3 + ch * 3
        raw = (frame[i] << 16) | (frame[i + 1] << 8) | frame[i + 2]
        if raw & 0x800000:  # complément à deux
            raw -= 1 << 24
        values.append(counts_to_uv(raw, gain))
    return status, values


class ADS1299:
    def __init__(self, bus=0, device=0, drdy_pin=17, reset_pin=22, start_pin=27,
                 sample_rate=250, gain=24):
        if spidev is None:
            raise RuntimeError("spidev/gpiozero absents : ça tourne que sur le Pi")
        if sample_rate not in SAMPLE_RATES:
            raise ValueError(f"débit non géré : {sample_rate}")
        self.sample_rate = sample_rate
        self.gain = gain

        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = 1_000_000  # 1 MHz, largement assez pour 250 SPS
        self.spi.mode = 0b01  # CPOL=0, CPHA=1. j'ai perdu une soirée là-dessus

        self.drdy = DigitalInputDevice(drdy_pin, pull_up=True)
        self.reset_line = DigitalOutputDevice(reset_pin, initial_value=True)
        self.start_line = DigitalOutputDevice(start_pin, initial_value=False)

    # --- bas niveau ---
    def command(self, cmd):
        self.spi.xfer2([cmd])
        time.sleep(0.00001)

    def read_reg(self, addr):
        resp = self.spi.xfer2([RREG | addr, 0x00, 0x00])
        return resp[2]

    def write_reg(self, addr, value):
        self.spi.xfer2([WREG | addr, 0x00, value])

    # --- init ---
    def reset(self):
        self.reset_line.off()
        time.sleep(0.001)
        self.reset_line.on()
        time.sleep(0.01)  # 18 tCLK suffisent, je mets large
        self.command(SDATAC)  # au reset la puce est en RDATAC, faut sortir de là pour écrire

    def configure(self, test_signal=False):
        self.reset()
        chip_id = self.read_reg(REG_ID)
        if chip_id != EXPECTED_ID:
            raise RuntimeError(f"ID = 0x{chip_id:02X}, attendu 0x{EXPECTED_ID:02X}. Vérifie le SPI.")

        # référence interne + buffer BIAS
        self.write_reg(REG_CONFIG3, 0xEC)
        time.sleep(0.15)  # la ref interne met un moment à se stabiliser

        self.write_reg(REG_CONFIG1, SAMPLE_RATES[self.sample_rate])
        # CONFIG2 : 0xD0 = signal de test interne, 0xC0 = normal
        self.write_reg(REG_CONFIG2, 0xD0 if test_signal else 0xC0)

        # entrées : 0x05 = signal de test, 0x00 = électrode normale
        mux = 0x05 if test_signal else 0x00
        for ch in range(N_CHANNELS):
            self.write_reg(REG_CH1SET + ch, GAINS[self.gain] | mux)

        # SRB1 relié à toutes les entrées négatives = référence commune (lobe d'oreille gauche)
        self.write_reg(REG_MISC1, 0x20)
        # BIAS calculé sur toutes les voies
        self.write_reg(REG_BIAS_SENSP, 0xFF)
        self.write_reg(REG_BIAS_SENSN, 0x00)

    # --- acquisition ---
    def start(self):
        self.start_line.on()
        self.command(RDATAC)

    def stop(self):
        self.command(SDATAC)
        self.start_line.off()

    def read_frame(self, timeout=1.0):
        """Attend DRDY (actif bas) puis lit une trame."""
        t0 = time.monotonic()
        while self.drdy.value:  # pull-up : 1 tant que pas prêt
            if time.monotonic() - t0 > timeout:
                raise TimeoutError("pas de DRDY. START est bien à 1 ?")
        frame = self.spi.xfer2([0x00] * FRAME_BYTES)
        return parse_frame(bytes(frame), self.gain)

    def close(self):
        try:
            self.stop()
        finally:
            self.spi.close()
            self.drdy.close()
            self.reset_line.close()
            self.start_line.close()
