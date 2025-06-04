import network
import socket
import time
from utime import sleep
from machine import Pin, DAC, ADC
from umqtt.simple import MQTTClient

adc = ADC(Pin(32))
adc.atten(ADC.ATTN_11DB)
a = 1200
dac = DAC(Pin(25))

SSID = 'Aegis2.4GHz'
SENHA = 'Strudel#22'
BROKER = 'test.mosquitto.org'
TOPICO_VAZAO = b'esp32/VAZAO'
TOPICO_VAZAO_RESPOSTA = b'esp32/VAZAO/RESPOSTA'
TOPICO_VAZAO_CORRENTE = b'esp32/VAZAO/CORRENTE'
TOPICO_DAC = b'esp32/DAC'
TOPICO_DAC_FREQ = b'esp32/DAC/FREQ'
TOPICO_DAC_CORRENTE_FREQ = b'esp32/DAC/CORRENTE/FREQ'


wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(SSID, SENHA)

while not wifi.isconnected():
    print("Conectando ao Wi-Fi...")
    time.sleep(1)
    
print("Conectado")

vazao = 0.0

def atualizar_vazao():
    vazao_adc = adc.read()
    if vazao_adc >= a:
        vazao = (38 / (4095-a)) * (vazao_adc - a)
    else:
        vazao = 0.0
    return vazao
    
def callback(topic, msg):
    if topic == TOPICO_VAZAO:
        vazao = atualizar_vazao()
        corrente_vazao = 4 + adc.read() * (7.5/1023)
        print("Vazão = ", vazao)
        cliente.publish(TOPICO_VAZAO_RESPOSTA, str(vazao))
        cliente.publish(TOPICO_VAZAO_CORRENTE, str(corrente_vazao))
    elif topic == TOPICO_DAC:
        valor_dac = int(msg)
        if valor_dac <= 255 and valor_dac >= 0:
            dac.write(valor_dac)
            freq = valor_dac * (60 / 255)
            corrente_freq = valor_dac * (16/255) + 4
            print("Frequência:", freq)
            print("Corrente frequência:", corrente_freq)
            cliente.publish(TOPICO_DAC_FREQ, str(freq))
            cliente.publish(TOPICO_DAC_CORRENTE_FREQ, str(corrente_freq))
        else:
            print("erro no DAC")

#cliente
cliente = MQTTClient("esp32", BROKER, port=1883)
cliente.set_callback(callback)
cliente.connect()
cliente.subscribe(TOPICO_VAZAO)
cliente.subscribe(TOPICO_DAC)

#print(f"Conectado ao broker MQTT '{BROKER}', aguardando dados no tópico '{TOPICO.decode()}'")
dac.write(0)
try:
    while True:
        cliente.check_msg()
        print("vazão = ", vazao)
        time.sleep(0.1)
except KeyboardInterrupt:
    cliente.disconnect()
    print("Desconectado do broker")
