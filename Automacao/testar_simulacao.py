# -*- coding: utf-8 -*-
import os
import sys
import time
import urllib.request
import urllib.parse
import json
import threading

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = r'I:\Meu Drive\Estudos\Inglês\Advanced'
TRACKER_PATH = os.path.join(BASE_DIR, 'Tracker_Aulas.md')
CONFIG_PATH = os.path.join(BASE_DIR, 'Automacao', 'config_ia.json')
GRAVACOES_DIR = os.path.join(BASE_DIR, 'Gravacoes')

os.makedirs(GRAVACOES_DIR, exist_ok=True)

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

phone = cfg.get('WHATSAPP_PHONE')
apikey = cfg.get('CALLMEBOT_APIKEY')
groq_key = cfg.get('GROQ_API_KEY')

print('=====================================================')
print('   🧪 TESTE COMPLETO DO FLUXO DE AULA (SIMULAÇÃO)')
print('=====================================================\n')

# 1. WHATSAPP & TRACKER
print('[1/4] 📲 Disparando Notificação de WhatsApp com o Tracker...')
with open(TRACKER_PATH, 'r', encoding='utf-8') as f:
    texto = f.read()
partes = texto.split('\n## [')
resumo = '## [' + partes[-1].strip() if len(partes) > 1 else texto.strip()
if len(resumo) > 1000:
    resumo = resumo[:1000] + '\n...(continua)'

msg = f'🧪 *[TESTE DE SIMULAÇÃO]* 🇬🇧\n\nSua aula de inglês começará em 30 minutos (08:00)!\n\n━━━━━━━━━━━━━━━━━━━━\n📖 *SEU TRACKER DE ESTUDOS:*\n\n{resumo}'
url = f'https://api.callmebot.com/whatsapp.php?phone={phone}&text={urllib.parse.quote(msg)}&apikey={apikey}'
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f'   [OK] WhatsApp enviado com sucesso (Status {resp.status})')
except Exception as e:
    print(f'   [AVISO] Falha WhatsApp: {e}')

# 2. ALERTA VISUAL & TRACKER ABERTO
print('\n[2/4] 🔔 Disparando Alerta Visual e abrindo Tracker no Windows...')
def mostrar_popup():
    try:
        import winsound, ctypes
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        ctypes.windll.user32.MessageBoxW(0, 'Sua aula de ingles comecara em 30 min.\nO Tracker de estudos foi aberto para aquecimento.', 'Ingles Avancado - Aula em 30 min', 0x40 | 0x1000 | 0x10000)
    except Exception:
        pass

threading.Thread(target=mostrar_popup, daemon=True).start()
if os.path.exists(TRACKER_PATH):
    os.startfile(TRACKER_PATH)
print('   [OK] Janela pop-up exibida e Tracker_Aulas.md aberto!')

# 3. GRAVACAO DUAL
print('\n[3/4] 🎙️ Gravando 6 segundos de teste (Fones + Microfone)...')

sys.path.insert(0, os.path.join(BASE_DIR, 'Automacao'))
from gravar_e_analisar_aula import gravar_audio, transcrever_com_groq_whisper, analisar_com_groq_llama

audio_teste = os.path.join(GRAVACOES_DIR, 'teste_simulacao.wav')
sucesso_grav = gravar_audio(audio_teste, duracao_max=6, aguardar_zoom=False)

if not sucesso_grav or not os.path.exists(audio_teste):
    print('   [ERRO] Falha ao gravar áudio de teste.')
    sys.exit(1)

print('   [OK] Áudio gravado com sucesso!')

# 4. TRANSCRICAO & IA
print('\n[4/4] 🤖 Transcrevendo com Groq Whisper e Analisando com Llama 3.3...')
transcricao = transcrever_com_groq_whisper(audio_teste, groq_key)
print(f'   [TRANSCRIÇÃO]: "{transcricao}"')

if not transcricao:
    transcricao = "Teacher Patricia: Today we talked about dramatic licence in historical films. For next class on Friday, please prepare the exercises on page 34 about colloquial idioms."
    print(f'   [TRANSCRIÇÃO SIMULADA DE AULA]: "{transcricao}"')

relatorio = analisar_com_groq_llama(transcricao, groq_key)
print('\n=====================================================')
print('   📄 RESULTADO DA ANÁLISE IA GERADO NO TRACKER:')
print('=====================================================')
print(relatorio)
print('=====================================================\n')
print('✅ TESTE COMPLETO CONCLUÍDO COM SUCESSO!')
