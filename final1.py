import network
import time
from utime import sleep
from machine import Pin, DAC, ADC
from umqtt.simple import MQTTClient
import machine

# ==== CONFIGURAÇÕES ====#
SSID = 'Aegis2.4GHz'
SENHA = 'Strudel#22'
BROKER = 'test.mosquitto.org'

TOPICO_VAZAO = b'esp32/VAZAO'
TOPICO_VAZAO_RESPOSTA = b'esp32/VAZAO/RESPOSTA'
TOPICO_VAZAO_CORRENTE = b'esp32/VAZAO/CORRENTE'
TOPICO_DAC = b'esp32/DAC'
TOPICO_DAC_FREQ = b'esp32/DAC/FREQ'
TOPICO_DAC_CORRENTE_FREQ = b'esp32/DAC/CORRENTE/FREQ'

# ==== CONFIGURAÇÕES ====#

ENVIAR_PERIODICAMENTE = False
INTERVALO_ENVIO_MS = 2000
DEBUG = True

# ==== HARDWARE ====#
adc = ADC(Pin(32))
adc.atten(ADC.ATTN_11DB)
dac = DAC(Pin(25))
dac.write(0)

# ==== VARIÁVEIS ====#
vazao = 0.0
limiar_adc = 1200
ultimo_envio = time.ticks_ms()

# ==== CONEXÃO WIFI ==== #
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(SSID, SENHA)

tentativas = 0
while not wifi.isconnected() and tentativas < 10:
    if DEBUG:
        print("Conectando ao Wi-Fi...")
    time.sleep(1)
    tentativas += 1

if not wifi.isconnected():
    print("Falha ao conectar Wi-Fi. Reiniciando...")
    machine.reset()

print("Wi-Fi conectado com IP:", wifi.ifconfig()[0])

# ==== FUNÇÕES AUXILIARES ==== #

def atualizar_vazao():
    leitura_adc = adc.read()
    if leitura_adc >= limiar_adc:
        return (38 / (4095 - limiar_adc)) * (leitura_adc - limiar_adc)
    else:
        return 0.0

def calcular_corrente_vazao():
    return 4 + adc.read() * (7.5 / 4095)

def calcular_freq_e_corrente(valor_dac):
    freq = valor_dac * (60 / 255)
    corrente = valor_dac * (16 / 255) + 4
    return freq, corrente

# ==== CALLBACK MQTT ==== #

def callback(topic, msg):
    global vazao
    try:
        if topic == TOPICO_VAZAO:
            vazao = atualizar_vazao()
            corrente_vazao = calcular_corrente_vazao()
            if DEBUG:
                print(f"[MQTT] Vazão: {vazao:.2f} L/min | Corrente: {corrente_vazao:.2f} mA")
            cliente.publish(TOPICO_VAZAO_RESPOSTA, str(vazao))
            cliente.publish(TOPICO_VAZAO_CORRENTE, str(corrente_vazao))

        elif topic == TOPICO_DAC:
            valor_dac = int(msg.decode())
            if 0 <= valor_dac <= 255:
                dac.write(valor_dac)
                freq, corrente_freq = calcular_freq_e_corrente(valor_dac)
                if DEBUG:
                    print(f"[MQTT] DAC: {valor_dac} | Freq: {freq:.2f} Hz | Corrente: {corrente_freq:.2f} mA")
                cliente.publish(TOPICO_DAC_FREQ, str(freq))
                cliente.publish(TOPICO_DAC_CORRENTE_FREQ, str(corrente_freq))
            else:
                print("[ERRO] Valor do DAC fora do intervalo (0-255)")
    except ValueError:
        print("[ERRO] Mensagem recebida não é um número inteiro válido.")
    except Exception as e:
        print(f"[ERRO] Callback: {e}")

# ==== CONEXÃO MQTT ==== #

def conectar_mqtt():
    global cliente
    while True:
        try:
            cliente = MQTTClient("esp32", BROKER, port=1883)
            cliente.set_callback(callback)
            cliente.connect()
            cliente.subscribe(TOPICO_VAZAO)
            cliente.subscribe(TOPICO_DAC)
            print(f"MQTT conectado ao broker '{BROKER}'.")
            break
        except Exception as e:
            print(f"[ERRO] Falha ao conectar MQTT: {e}, tentando novamente em 5s...")
            time.sleep(5)

# ==== INÍCIO ==== #

conectar_mqtt()

# ==== LOOP PRINCIPAL ==== #

try:
    while True:
        try:
            cliente.check_msg()
        except Exception as e:
            print(f"[ERRO] check_msg: {e}, tentando reconectar MQTT...")
            try:
                cliente.disconnect()
            except:
                pass
            conectar_mqtt()

        if ENVIAR_PERIODICAMENTE:
            agora = time.ticks_ms()
            if time.ticks_diff(agora, ultimo_envio) > INTERVALO_ENVIO_MS:
                vazao = atualizar_vazao()
                corrente_vazao = calcular_corrente_vazao()
                try:
                    cliente.publish(TOPICO_VAZAO_RESPOSTA, str(vazao))
                    cliente.publish(TOPICO_VAZAO_CORRENTE, str(corrente_vazao))
                    if DEBUG:
                        print(f"[MQTT] Publicado periodicamente: Vazão {vazao:.2f}, Corrente {corrente_vazao:.2f}")
                except Exception as e:
                    print(f"[ERRO] Publicação periódica MQTT: {e}, tentando reconectar...")
                    try:
                        cliente.disconnect()
                    except:
                        pass
                    conectar_mqtt()
                ultimo_envio = agora

        sleep(0.1)

except KeyboardInterrupt:
    print("Interrupção pelo usuário, desconectando MQTT...")
    try:
        cliente.disconnect()
    except:
        pass
    print("Desconectado do broker MQTT.")

except Exception as e:
    print(f"[ERRO] Loop principal: {e}")
    machine.reset()
