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
CONFIG_PATH = os.path.join(BASE_DIR, 'Automacao', 'config_ia.json')
GRAVACOES_DIR = os.path.join(BASE_DIR, 'Gravacoes')

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    cfg = json.load(f)
groq_key = cfg.get('GROQ_API_KEY')

print('=====================================================')
print('   🎙️ TESTE INTERATIVO DE VOZ E IA (15 SEGUNDOS)')
print('=====================================================\n')

def mostrar_aviso_gravando():
    try:
        import winsound, ctypes
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        ctypes.windll.user32.MessageBoxW(
            0,
            '🔴 GRAVANDO AGORA!\n\nFale algo em inglês durante os próximos 15 segundos.\n(Ex: "Hello, in today\'s lesson we discussed dramatic licence in movies...")',
            '🎙️ Gravação Iniciada - Fale Agora!',
            0x40 | 0x1000 | 0x10000
        )
    except Exception:
        pass

threading.Thread(target=mostrar_aviso_gravando, daemon=True).start()

sys.path.insert(0, os.path.join(BASE_DIR, 'Automacao'))
from gravar_e_analisar_aula import gravar_audio, transcrever_com_groq_whisper, analisar_com_groq_llama

audio_teste = os.path.join(GRAVACOES_DIR, 'teste_voz_usuario.wav')
print('🔴 GRAVANDO POR 15 SEGUNDOS... FALE AGORA NO MICROFONE!\n')

sucesso_grav = gravar_audio(audio_teste, duracao_max=15, aguardar_zoom=False)

if not sucesso_grav or not os.path.exists(audio_teste):
    print('❌ Falha na gravação.')
    sys.exit(1)

print('\n⏹️ Gravação concluída! Enviando para Groq Whisper e IA...')

transcricao = transcrever_com_groq_whisper(audio_teste, groq_key)
print(f'\n📝 [SUA VOZ TRANSCRIÇÃO]:\n"{transcricao}"\n')

if transcricao:
    relatorio = analisar_com_groq_llama(transcricao, groq_key)
    print('=====================================================')
    print('   📄 ANÁLISE PEDAGÓGICA DA IA GERADA COM A SUA VOZ:')
    print('=====================================================')
    print(relatorio)
    print('=====================================================\n')
