"""
Publie le stade courant sur MQTT (topic dreamgpio/stage).

Chez moi ça part dans Home Assistant : en N3 les lumières du salon
passent en veille, au réveil le chauffe-eau du thé se lance.
Oui, c'est de la dreamIoT. Oui, le terme n'existe pas. Pas encore.
"""

import json
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


class StagePublisher:
    def __init__(self, host="localhost", port=1883, topic="dreamgpio/stage"):
        if mqtt is None:
            raise RuntimeError("pip install paho-mqtt")
        self.topic = topic
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dreamgpio")
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()

    def publish(self, stage, epoch_index, extra=None):
        payload = {"stage": stage, "epoch": epoch_index, "ts": int(time.time())}
        if extra:
            payload.update(extra)
        # retain : Home Assistant récupère le dernier stade s'il redémarre dans la nuit
        self.client.publish(self.topic, json.dumps(payload), qos=1, retain=True)

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
