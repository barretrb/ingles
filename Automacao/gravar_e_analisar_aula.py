# -*- coding: utf-8 -*-
"""
Script de Gravação e Análise Automática com Groq AI (Whisper + Llama 3.3 70B)
1. Grava o áudio da aula em segundo plano
2. Transcreve o áudio via Whisper Large v3 Turbo da Groq
3. Extrai correções, vocabulário e gaps via Llama 3.3 70B Versatile
4. Atualiza automaticamente o Tracker_Aulas.md no Google Drive
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Garante saída UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = "H:\Meu Drive\\Estudos\\Ingl\u00eas\\Advanced"
GRAVACOES_DIR = os.path.join(BASE_DIR, "Gravacoes")
TRACKER_PATH = os.path.join(BASE_DIR, "Tracker_Aulas.md")
CONFIG_PATH = os.path.join(BASE_DIR, "Automacao", "config_ia.json")

DURACAO_MAXIMA_SEGUNDOS = 4500  # Até 75 minutos de limite de segurança


def garantir_diretorios():
    os.makedirs(GRAVACOES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)


def verificar_zoom_ativo():
    try:
        import subprocess
        output = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Zoom.exe'], capture_output=True, text=True).stdout
        return 'Zoom.exe' in output
    except Exception:
        return False


def gravar_audio(filepath, duracao_max=DURACAO_MAXIMA_SEGUNDOS, aguardar_zoom=True):
    print(f"[REC] [{datetime.now().strftime('%H:%M:%S')}] Preparando gravação da aula (Fone/Loopback + Microfone)...")
    
    # 1. Se configurado e o Zoom ainda não estiver aberto, aguarda o usuário entrar (até 20 min)
    if aguardar_zoom and not verificar_zoom_ativo():
        print("[ZOOM] Aguardando abertura do Zoom para iniciar gravação...")
        inicio_espera = time.time()
        while time.time() - inicio_espera < 1200:  # 20 minutos
            if verificar_zoom_ativo():
                print("[ZOOM] Aplicativo Zoom detectado em execução! Iniciando gravação...")
                break
            time.sleep(3)
    elif verificar_zoom_ativo():
        print("[ZOOM] Zoom já está ativo. Iniciando gravação imediatamente...")
    else:
        print("[AUDIO] Iniciando gravação direta de áudio...")

    try:
        import pyaudiowpatch as pyaudio
        import wave
        import numpy as np
        from scipy import signal

        p = pyaudio.PyAudio()
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info['defaultOutputDevice'])
            default_mic = p.get_device_info_by_index(wasapi_info['defaultInputDevice'])

            loopback = None
            for dev in p.get_loopback_device_info_generator():
                if default_speakers['name'] in dev['name']:
                    loopback = dev
                    break
            if not loopback:
                loopback_list = list(p.get_loopback_device_info_generator())
                if loopback_list:
                    loopback = loopback_list[0]

            loop_sr = int(loopback['defaultSampleRate']) if loopback else 48000
            loop_ch = loopback['maxInputChannels'] if loopback else 2
            mic_sr = int(default_mic['defaultSampleRate'])
            mic_ch = default_mic['maxInputChannels']

            print(f"[AUDIO] Capturando Fone/Saída: {loopback['name'] if loopback else 'N/A'}")
            print(f"[AUDIO] Capturando Microfone: {default_mic['name']}")

            loop_stream = None
            if loopback:
                loop_stream = p.open(format=pyaudio.paInt16, channels=loop_ch, rate=loop_sr,
                                     input=True, input_device_index=loopback['index'])
            
            mic_stream = p.open(format=pyaudio.paInt16, channels=mic_ch, rate=mic_sr,
                                input=True, input_device_index=default_mic['index'])

            loop_frames = []
            mic_frames = []

            start_time = time.time()
            ultimo_check_zoom = time.time()
            ultimo_print_status = time.time()
            zoom_estava_aberto = verificar_zoom_ativo()

            print("\n" + "="*60)
            print("[GRAVANDO] 🔴 Gravação ativa! Capturando fone e microfone...")
            print("[DICA] A gravação encerra automaticamente quando o Zoom fechar,")
            print("       ou pressione CTRL+C nesta janela para finalizar antes.")
            print("="*60 + "\n")

            try:
                while time.time() - start_time < duracao_max:
                    avail_mic = mic_stream.get_read_available()
                    if avail_mic > 0:
                        mic_frames.append(mic_stream.read(avail_mic, exception_on_overflow=False))
                    
                    if loop_stream:
                        avail_loop = loop_stream.get_read_available()
                        if avail_loop > 0:
                            loop_frames.append(loop_stream.read(avail_loop, exception_on_overflow=False))
                    
                    tempo_decorrido = time.time() - start_time

                    # Log visual a cada 30 segundos
                    if time.time() - ultimo_print_status >= 30:
                        ultimo_print_status = time.time()
                        minutos = int(tempo_decorrido // 60)
                        segundos = int(tempo_decorrido % 60)
                        print(f"[GRAVANDO] ⏱️ {minutos:02d}:{segundos:02d} min gravados... (capturando áudio)")

                    # A cada 5 segundos verifica se o Zoom encerrou
                    if time.time() - ultimo_check_zoom > 5:
                        ultimo_check_zoom = time.time()
                        zoom_rodando = verificar_zoom_ativo()
                        
                        # Se o Zoom estava aberto e fechou, e já gravamos pelo menos 5 minutos:
                        if zoom_estava_aberto and not zoom_rodando and tempo_decorrido > 300:
                            print(f"\n[ZOOM] [{datetime.now().strftime('%H:%M:%S')}] Zoom fechado. Encerrando gravação da aula ({tempo_decorrido/60:.1f} min gravados)...")
                            break
                        if zoom_rodando:
                            zoom_estava_aberto = True
                    
                    time.sleep(0.05)
            except KeyboardInterrupt:
                tempo_decorrido = time.time() - start_time
                print(f"\n[MANUAL] Finalização manual acionada pelo usuário ({tempo_decorrido/60:.1f} min gravados).")

            if loop_stream:
                loop_stream.stop_stream()
                loop_stream.close()
            mic_stream.stop_stream()
            mic_stream.close()

            # Processar e mesclar os áudios
            raw_mic = b''.join(mic_frames)
            raw_loop = b''.join(loop_frames) if loop_frames else b''

            arr_mic = np.frombuffer(raw_mic, dtype=np.int16).astype(np.float32) if raw_mic else np.array([], dtype=np.float32)
            if mic_ch > 1 and len(arr_mic) > 0:
                arr_mic = arr_mic.reshape(-1, mic_ch).mean(axis=1)

            arr_loop = np.frombuffer(raw_loop, dtype=np.int16).astype(np.float32) if raw_loop else np.array([], dtype=np.float32)
            if loop_ch > 1 and len(arr_loop) > 0:
                arr_loop = arr_loop.reshape(-1, loop_ch).mean(axis=1)

            target_sr = 16000
            if len(arr_mic) > 0 and mic_sr != target_sr:
                arr_mic = signal.resample(arr_mic, int(len(arr_mic) * target_sr / mic_sr))

            if len(arr_loop) > 0 and loop_sr != target_sr:
                arr_loop = signal.resample(arr_loop, int(len(arr_loop) * target_sr / loop_sr))

            max_len = max(len(arr_mic), len(arr_loop))
            if max_len == 0:
                print("[ERRO] Nenhum áudio capturado durante a aula.")
                return False

            if len(arr_mic) < max_len:
                arr_mic = np.pad(arr_mic, (0, max_len - len(arr_mic)))
            if len(arr_loop) < max_len:
                arr_loop = np.pad(arr_loop, (0, max_len - len(arr_loop)))

            mixed = np.clip((arr_mic + arr_loop) * 0.8, -32768, 32767).astype(np.int16)

            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(target_sr)
                wf.writeframes(mixed.tobytes())

            print(f"[OK] Gravação mista salva com sucesso: {filepath} ({len(mixed)/target_sr/60:.1f} min)")
            return True
        finally:
            p.terminate()

    except Exception as e:
        print(f"[AVISO] Falha na captura avançada com WASAPI Loopback ({e}). Tentando gravação padrão com sounddevice...")
        try:
            import sounddevice as sd
            from scipy.io import wavfile
            fs = 16000
            gravacao = sd.rec(int(duracao_max * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            wavfile.write(filepath, fs, gravacao)
            print(f"[OK] Gravação padrão concluída: {filepath}")
            return True
        except Exception as e2:
            print(f"[ERRO] Falha total na gravação: {e2}")
            return False


def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _transcrever_chunk(chunk_path, api_key, modelo_audio, url, headers):
    """Transcreve um único chunk de áudio via Groq Whisper."""
    with open(chunk_path, "rb") as audio_file:
        files = {"file": (os.path.basename(chunk_path), audio_file, "audio/wav")}
        data = {"model": modelo_audio, "language": "en", "response_format": "json"}
        res = requests.post(url, headers=headers, files=files, data=data)

    if res.status_code == 200:
        text = res.json().get("text", "").strip()
        print(f"[WHISPER] OK - {len(text)} chars de {os.path.basename(chunk_path)}")
        return text
    else:
        print(f"[ERRO] Whisper falhou para {os.path.basename(chunk_path)}: {res.status_code} - {res.text}")
        return None


def transcrever_com_groq_whisper(audio_filepath, api_key, modelo_audio="whisper-large-v3-turbo"):
    import wave
    import math
    import tempfile

    print(f"[WHISPER] [{datetime.now().strftime('%H:%M:%S')}] Transcrevendo áudio com Groq Whisper...")
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    file_size = os.path.getsize(audio_filepath)
    MAX_CHUNK_BYTES = 20 * 1024 * 1024  # 20MB

    # Arquivo pequeno: transcrição direta
    if file_size <= MAX_CHUNK_BYTES:
        return _transcrever_chunk(audio_filepath, api_key, modelo_audio, url, headers)

    # Arquivo grande: dividir em chunks
    print(f"[WHISPER] Arquivo grande ({file_size / 1024 / 1024:.1f} MB). Dividindo em chunks...")
    chunks = []
    try:
        with wave.open(audio_filepath, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()

            bytes_per_frame = n_channels * sampwidth
            max_frames_per_chunk = (MAX_CHUNK_BYTES - 1024) // bytes_per_frame
            n_chunks = math.ceil(n_frames / max_frames_per_chunk)

            print(f"[WHISPER] Dividindo em {n_chunks} chunk(s) de ~{max_frames_per_chunk / framerate / 60:.1f} min")

            for i in range(n_chunks):
                frames_to_read = min(max_frames_per_chunk, n_frames - i * max_frames_per_chunk)
                data = wf.readframes(frames_to_read)

                chunk_path = os.path.join(tempfile.gettempdir(), f"aula_chunk_{i}.wav")
                with wave.open(chunk_path, 'wb') as chunk_wf:
                    chunk_wf.setnchannels(n_channels)
                    chunk_wf.setsampwidth(sampwidth)
                    chunk_wf.setframerate(framerate)
                    chunk_wf.writeframes(data)
                chunks.append(chunk_path)

        # Transcrever cada chunk
        transcricoes = []
        for i, chunk_path in enumerate(chunks):
            print(f"[WHISPER] [{datetime.now().strftime('%H:%M:%S')}] Transcrevendo chunk {i + 1}/{len(chunks)}...")
            texto = _transcrever_chunk(chunk_path, api_key, modelo_audio, url, headers)
            if texto:
                transcricoes.append(texto)

        if not transcricoes:
            print("[ERRO] Nenhum chunk foi transcrito com sucesso.")
            return None

        texto_completo = "\n\n".join(transcricoes)
        print(f"[OK] Transcrição completa: {len(texto_completo)} caracteres")
        return texto_completo

    finally:
        # Limpar arquivos temporários
        for chunk_path in chunks:
            try:
                os.remove(chunk_path)
            except Exception:
                pass


def carregar_indice_livro():
    csv_path = os.path.join(BASE_DIR, "English_File_Advanced_por_Capitulo", "indice_capitulos.csv")
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""


def analisar_com_groq_llama(transcricao, api_key, modelo_texto="openai/gpt-oss-120b"):
    print(f"[IA] [{datetime.now().strftime('%H:%M:%S')}] Analisando aula com Groq AI ({modelo_texto})...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    indice_livro = carregar_indice_livro()

    prompt_sistema = f"""Você é um tutor nativo (C2) de inglês e especialista em aquisição de segunda língua para alunos de nível avançado (C1/C2).
Sua missão é analisar a transcrição completa de uma aula de inglês do aluno Rafael com a professora Patrícia (curso English File Advanced).

ESTRUTURA DO LIVRO ENGLISH FILE ADVANCED (ÍNDICE DE CAPÍTULOS E PÁGINAS):
{indice_livro}

REGRA CRÍTICA DE ANTI-ALUCINAÇÃO:
Baseie-se ESTRITAMENTE no que foi dito na transcrição. Se a transcrição for muito curta, contiver apenas ruídos, ou não tiver conteúdo de aula suficiente, NÃO INVENTE E NÃO ADIVINHE NADA. Nesse caso, responda APENAS com a palavra: ERRO_TRANSCRICAO_INSUFICIENTE

DIRETRIZES DE ANÁLISE (Só siga se houver aula real na transcrição):
1. Identifique os tópicos e páginas trabalhados na aula de hoje.
2. ANALISE COM ATENÇÃO O FINAL DA AULA (onde a professora Patrícia e o Rafael combinam onde pararam, lição de casa ou o que farão na próxima aula).
3. Cruze o que foi falado com a estrutura do livro para mapear com precisão o próximo capítulo/páginas.
4. Gere o relatório de hoje E crie o planejamento da PRÓXIMA AULA com metas e vocabulário-alvo para revisão prévia no WhatsApp.

Gere OBRIGATORIAMENTE no seguinte formato Markdown exato (se houver aula válida):

## [{{DATA_HOJE}}] Aula Concluída — [Nome do Capítulo e Páginas Trabalhadas]

* **Tópico / Resumo:** [Resumo claro de 2 linhas sobre o tema discutido na aula]
* **Ponto de Parada:** [Página exata e exercício onde pararam hoje]

### 🎯 Vocabulário Avançado & Expressões do Dia
1. **[Palavra/Expressão 1]** — [Significado / como foi usado no contexto]
2. **[Palavra/Expressão 2]** — [Significado / como foi usado no contexto]
3. **[Palavra/Expressão 3]** — [Significado / como foi usado no contexto]

### 🧠 Gap Log & Dúvidas (Oportunidades de Upgrade Gramatical)
| O que foi dito / dúvida | Forma nativa C1/C2 recomendada |
| :--- | :--- |
| [Exemplo real falado pelo Rafael] | [Alternativa mais formal/sofisticada recomendada] |

### 🛠️ Correções da Professora Patrícia
* [Correção pontual 1 feita pela professora]
* [Correção pontual 2 feita pela professora]

### 📝 Sugestão de Resumo Ativo (3 frases para fixação)
1. [Frase 1 com vocabulário da aula]
2. [Frase 2 com vocabulário da aula]
3. [Frase 3 com vocabulário da aula]

---

## [Próxima Aula] Planejamento & Metas — [Próximo Capítulo e Páginas Previstas]

* **Foco Central Previsto:** [Assunto principal que a professora indicou ou o próximo tópico do livro]
* **Páginas / Material:** [Ex: English File Advanced, pág. XX-YY / Workbook / Colloquial]

### 🎯 2 Palavras-Alvo Recomendadas para Usar na Aula
1. **[Palavra-alvo 1 relevante para o tema]** ([tradução/dica rápida])
2. **[Palavra-alvo 2 relevante para o tema]** ([tradução/dica rápida])

### 🧠 Gap Log (Para preencher durante a aula)
| O que eu quis dizer / dúvida | Como falar de forma natural/avançada |
| :--- | :--- |
| | |
""".replace("{{DATA_HOJE}}", datetime.now().strftime("%Y-%m-%d"))

    payload = {
        "model": modelo_texto,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Aqui está a transcrição da aula de hoje:\n\n{transcricao}"}
        ],
        "temperature": 0.3
    }

    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        conteudo = res.json()["choices"][0]["message"]["content"].strip()
        if "ERRO_TRANSCRICAO_INSUFICIENTE" in conteudo:
            print("[ERRO] IA detectou que a transcrição tem apenas ruídos ou é muito curta. Abortando para evitar alucinações.")
            return None
        return conteudo
    else:
        print(f"[ERRO] Erro na análise Groq Llama: {res.status_code} - {res.text}")
        return None


def atualizar_tracker(markdown_texto):
    if not markdown_texto:
        return

    print("[INFO] Atualizando Tracker_Aulas.md com a análise da IA...")
    with open(TRACKER_PATH, "a", encoding="utf-8") as f:
        f.write("\n\n---\n\n")
        f.write(markdown_texto)

    print("[OK] Tracker_Aulas.md atualizado com sucesso!")


def main():
    garantir_diretorios()
    cfg = carregar_config()
    api_key = cfg.get("GROQ_API_KEY")
    if not api_key:
        print("[ERRO] Chave GROQ_API_KEY não configurada no config_ia.json")
        return

    data_str = datetime.now().strftime("%Y-%m-%d")
    audio_path = os.path.join(GRAVACOES_DIR, f"{data_str}_Rafa-EF.wav")

    # 1. Gravar Aula
    sucesso = gravar_audio(audio_path, DURACAO_MAXIMA_SEGUNDOS)
    if not sucesso or not os.path.exists(audio_path):
        return

    # 2. Transcrever com Groq Whisper
    transcricao = transcrever_com_groq_whisper(
        audio_path,
        api_key,
        cfg.get("MODELO_AUDIO", "whisper-large-v3-turbo")
    )
    if not transcricao:
        return

    # 3. Analisar com Groq Llama 3.3 70B
    relatorio_md = analisar_com_groq_llama(
        transcricao,
        api_key,
        cfg.get("MODELO_TEXTO", "llama-3.3-70b-versatile")
    )

    # 4. Escrever no Tracker
    if relatorio_md:
        atualizar_tracker(relatorio_md)
        print("\n" + "="*60)
        print("🎉 [SUCESSO] Aula gravada, transcrita e analisada com sucesso!")
        print("📖 Tracker_Aulas.md atualizado no Google Drive.")
        print("="*60)

        # Notificação Sonora e Visual
        try:
            import winsound
            import ctypes
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            # Notificação em thread para não travar
            def _notificar():
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "A análise da sua aula de inglês foi concluída e salva no Tracker_Aulas.md!",
                    "Inglês Avançado - Aula Concluída",
                    0x40 | 0x10000
                )
            threading.Thread(target=_notificar, daemon=True).start()
        except Exception:
            pass

        print("\n[INFO] Esta janela será fechada automaticamente em 8 segundos...")
        time.sleep(8)


if __name__ == "__main__":
    import threading
    main()

