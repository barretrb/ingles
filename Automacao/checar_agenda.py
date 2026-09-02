# -*- coding: utf-8 -*-
"""
Orquestrador Inteligente de Aulas de Inglês (Google Calendar → Windows Automation)

Arquitetura:
  1. Roda 1x ao dia (07:00) e ao fazer logon no Windows
  2. Consulta o Google Calendar via iCal
  3. Se NÃO tem aula hoje → encerra imediatamente
  4. Se TEM aula hoje → cria tarefas pontuais (one-shot) no Task Scheduler:
     - T-30min: Alerta pré-aula (WhatsApp + tela + Tracker)
     - T-0: Gravação + transcrição + análise IA
  5. Encerra imediatamente (sem time.sleep)

Modos de execução:
  (sem args)   → Consulta agenda e agenda tarefas pontuais
  --pre-aula   → Envia WhatsApp, alerta visual, abre Tracker
  --gravar     → Inicia gravação + pipeline de transcrição e análise
"""

import os
import sys
import json
import subprocess
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# Garante saída compatível no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Configurações ──────────────────────────────────────────────────
ICAL_URL = "https://calendar.google.com/calendar/ical/rafaelferreirabarreto%40gmail.com/private-53c7f76409468a222f0ca4b41fc4d536/basic.ics"
ALVO_SUMMARY = "Rafa - EF"
ALVO_ORGANIZER = "patricia.ibiapina25@gmail.com"

BASE_DIR = r"I:\Meu Drive\Estudos\Inglês\Advanced"
TRACKER_PATH = os.path.join(BASE_DIR, "Tracker_Aulas.md")
SCRIPT_GRAVAR = os.path.join(BASE_DIR, "Automacao", "gravar_e_analisar_aula.py")
CONFIG_PATH = os.path.join(BASE_DIR, "Automacao", "config_ia.json")
ESTADO_PATH = os.path.join(BASE_DIR, "Automacao", "estado_dia.json")

# Nomes das tarefas pontuais
TASK_ALERTA = "Ingles_Alerta_PreAula"
TASK_GRAVACAO = "Ingles_Gravacao_Aula"


# ── Utilitários ────────────────────────────────────────────────────
def log(tag, msg):
    print(f"[{tag}] [{datetime.now().strftime('%H:%M:%S')}] {msg}")


def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def carregar_estado():
    """Carrega o estado do dia. Reseta se for de outro dia."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(ESTADO_PATH):
        try:
            with open(ESTADO_PATH, "r", encoding="utf-8") as f:
                estado = json.load(f)
            if estado.get("data") == hoje:
                return estado
        except Exception:
            pass
    return {"data": hoje}


def salvar_estado(estado):
    estado["data"] = datetime.now().strftime("%Y-%m-%d")
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


# ── Agenda (iCal) ─────────────────────────────────────────────────
def baixar_e_analisar_ics(url):
    log("AGENDA", "Consultando Google Calendar via iCal...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        ics_text = response.read().decode("utf-8")

    eventos = []
    bloco_evento = []
    in_event = False

    for linha in ics_text.splitlines():
        if linha.strip() == "BEGIN:VEVENT":
            in_event = True
            bloco_evento = []
        elif linha.strip() == "END:VEVENT":
            in_event = False
            eventos.append(bloco_evento)
        elif in_event:
            bloco_evento.append(linha)

    hoje_str = datetime.now().strftime("%Y%m%d")
    aulas_hoje = []

    for ev in eventos:
        summary = ""
        dtstart = ""
        dtend = ""
        organizer = ""
        for linha in ev:
            if linha.startswith("SUMMARY:"):
                summary = linha.split(":", 1)[1]
            elif linha.startswith("DTSTART"):
                dtstart = linha.split(":")[-1].strip()
            elif linha.startswith("DTEND"):
                dtend = linha.split(":")[-1].strip()
            elif "ORGANIZER" in linha:
                organizer = linha

        eh_aula = (ALVO_SUMMARY.lower() in summary.lower()) or (
            ALVO_ORGANIZER.lower() in organizer.lower()
        )
        if eh_aula and dtstart.startswith(hoje_str):
            aulas_hoje.append({
                "summary": summary,
                "start": dtstart,
                "end": dtend
            })

    return aulas_hoje


def parse_dt_aula(dt_str):
    """Converte string de data iCal para datetime local."""
    try:
        if dt_str.endswith("Z"):
            dt_utc = datetime.strptime(dt_str, "%Y%m%dT%H%M%SZ")
            return dt_utc - timedelta(hours=3)
        else:
            return datetime.strptime(dt_str[:15], "%Y%m%dT%H%M%S")
    except Exception:
        return None


# ── Notificações ───────────────────────────────────────────────────
def enviar_whatsapp(mensagem):
    cfg = carregar_config()
    phone = cfg.get("WHATSAPP_PHONE")
    apikey = cfg.get("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        log("WHATSAPP", "Configurações de telefone ou API Key não encontradas.")
        return

    log("WHATSAPP", "Enviando lembrete para WhatsApp...")
    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={urllib.parse.quote(mensagem)}&apikey={apikey}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            log("WHATSAPP", f"Mensagem enviada com sucesso (Status: {resp.status})")
    except Exception as e:
        log("WHATSAPP", f"Falha ao enviar mensagem: {e}")


def exibir_alerta_visual(titulo, mensagem):
    def _mostrar():
        try:
            import winsound
            import ctypes
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            ctypes.windll.user32.MessageBoxW(0, mensagem, titulo, 0x40 | 0x1000 | 0x10000)
        except Exception as e:
            log("ALERTA", f"Erro ao exibir janela: {e}")

    t = threading.Thread(target=_mostrar, daemon=True)
    t.start()


def obter_resumo_tracker():
    if not os.path.exists(TRACKER_PATH):
        return ""
    try:
        with open(TRACKER_PATH, "r", encoding="utf-8") as f:
            texto = f.read()
        partes = texto.split("\n## [")
        if len(partes) > 1:
            ultima = "## [" + partes[-1].strip()
        else:
            ultima = texto.strip()
        if len(ultima) > 1400:
            ultima = ultima[:1400] + "\n...(veja mais no Drive)"
        return ultima
    except Exception:
        return ""


# ── Task Scheduler (tarefas pontuais) ─────────────────────────────
def agendar_tarefa_pontual(nome, horario, args_extra):
    """Cria uma tarefa one-shot no Windows Task Scheduler."""
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    hora_str = horario.strftime("%H:%M")
    data_str = horario.strftime("%m/%d/%Y")

    # Remover tarefa existente (se houver)
    subprocess.run(
        f'schtasks /Delete /TN "{nome}" /F',
        shell=True, capture_output=True
    )

    # Criar tarefa one-shot
    cmd = (
        f'schtasks /Create /TN "{nome}" '
        f'/TR "\"{python_exe}\" \"{script_path}\" {args_extra}" '
        f'/SC ONCE /ST {hora_str} /SD {data_str} /F'
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        log("TASK", f"Tarefa '{nome}' agendada para {hora_str}")
    else:
        log("ERRO", f"Falha ao criar tarefa '{nome}': {result.stderr.strip()}")
    return result.returncode == 0


def limpar_tarefas_pontuais():
    """Remove tarefas pontuais de dias anteriores."""
    for nome in [TASK_ALERTA, TASK_GRAVACAO]:
        subprocess.run(
            f'schtasks /Delete /TN "{nome}" /F',
            shell=True, capture_output=True
        )


# ── MODO: Orquestrar (default) ────────────────────────────────────
def modo_orquestrar():
    """Consulta agenda. Se tem aula hoje, agenda tarefas pontuais."""
    estado = carregar_estado()

    # Se já agendou hoje, verificar se precisa agir diretamente
    if estado.get("tarefas_agendadas"):
        log("INFO", "Tarefas já foram agendadas hoje.")
        # Mas verificar se a aula está em andamento e a gravação não começou
        horario_aula = estado.get("horario_aula")
        if horario_aula and not estado.get("gravacao_iniciada"):
            dt_aula = datetime.fromisoformat(horario_aula)
            dt_fim = dt_aula + timedelta(minutes=65)
            agora = datetime.now()
            if dt_aula <= agora < dt_fim:
                log("ALERTA", "Aula em andamento e gravação não iniciada! Iniciando agora...")
                if not estado.get("alerta_enviado"):
                    _executar_pre_aula(dt_aula)
                    estado["alerta_enviado"] = True
                    salvar_estado(estado)
                modo_gravar()
        return

    # Consultar calendário
    try:
        aulas = baixar_e_analisar_ics(ICAL_URL)
    except Exception as e:
        log("ERRO", f"Falha ao consultar iCal: {e}")
        return

    if not aulas:
        log("INFO", f"Sem aula 'Rafa - EF' hoje ({datetime.now().strftime('%d/%m/%Y')}). Encerrando.")
        limpar_tarefas_pontuais()
        return

    # Pegar a primeira aula do dia
    aula = sorted(aulas, key=lambda x: x["start"])[0]
    dt_aula = parse_dt_aula(aula["start"])
    if not dt_aula:
        log("ERRO", "Não foi possível parsear o horário da aula.")
        return

    dt_fim = dt_aula + timedelta(minutes=65)
    dt_alerta = dt_aula - timedelta(minutes=30)
    agora = datetime.now()

    log("OK", f"Aula encontrada: {aula['summary']} às {dt_aula.strftime('%H:%M')}")

    if agora >= dt_fim:
        log("INFO", f"Aula de hoje ({dt_aula.strftime('%H:%M')}) já encerrou.")
        return

    # Salvar estado antes de agendar
    estado["tarefas_agendadas"] = True
    estado["horario_aula"] = dt_aula.isoformat()
    estado["summary"] = aula["summary"]

    # Decidir ações com base no horário atual
    if agora < dt_alerta:
        # Ainda dá tempo: agendar alerta E gravação
        agendar_tarefa_pontual(TASK_ALERTA, dt_alerta, "--pre-aula")
        agendar_tarefa_pontual(TASK_GRAVACAO, dt_aula, "--gravar")
        log("OK", f"Alerta agendado p/ {dt_alerta.strftime('%H:%M')}, gravação p/ {dt_aula.strftime('%H:%M')}")

    elif agora < dt_aula:
        # Dentro da janela de 30 min antes → alerta agora, gravação agendada
        log("ALERTA", "Dentro da janela pré-aula! Enviando alerta agora...")
        _executar_pre_aula(dt_aula)
        estado["alerta_enviado"] = True
        agendar_tarefa_pontual(TASK_GRAVACAO, dt_aula, "--gravar")

    else:
        # Aula em andamento → alerta + gravação imediatamente
        log("ALERTA", f"Aula em andamento! (Início: {dt_aula.strftime('%H:%M')})")
        _executar_pre_aula(dt_aula)
        estado["alerta_enviado"] = True
        salvar_estado(estado)
        modo_gravar()
        estado["gravacao_iniciada"] = True

    salvar_estado(estado)


# ── MODO: Pré-Aula ────────────────────────────────────────────────
def _executar_pre_aula(dt_aula):
    """Lógica de pré-aula: WhatsApp + alerta + abrir Tracker."""
    hora_aula_str = dt_aula.strftime("%H:%M")

    # WhatsApp
    conteudo_tracker = obter_resumo_tracker()
    corpo_resumo = f"\n\n━━━━━━━━━━━━━━━━━━━━\n📖 *RESUMO DO SEU TRACKER:*\n\n{conteudo_tracker}" if conteudo_tracker else ""
    msg_zap = (
        f"🔔 *Lembrete de Aula de Inglês!* 🇬🇧\n\n"
        f"Sua aula com a profa. Patrícia começa às *{hora_aula_str}* (em 30 min).\n"
        f"Abaixo estão os tópicos e vocabulários para revisão rápida:{corpo_resumo}"
    )
    enviar_whatsapp(msg_zap)

    # Alerta visual
    exibir_alerta_visual(
        "Inglês Avançado - Aula em 30 min",
        f"Sua aula de inglês começará às {hora_aula_str}.\nO Tracker de estudos foi aberto para aquecimento."
    )

    # Abrir Tracker
    if os.path.exists(TRACKER_PATH):
        os.startfile(TRACKER_PATH)

    log("OK", "Alertas pré-aula enviados com sucesso!")


def modo_pre_aula():
    """Modo --pre-aula: disparado pelo Task Scheduler 30 min antes."""
    estado = carregar_estado()
    if estado.get("alerta_enviado"):
        log("INFO", "Alerta já foi enviado hoje. Ignorando.")
        return

    horario_aula = estado.get("horario_aula")
    if horario_aula:
        dt_aula = datetime.fromisoformat(horario_aula)
    else:
        # Fallback: consultar agenda para pegar o horário
        try:
            aulas = baixar_e_analisar_ics(ICAL_URL)
            if aulas:
                aula = sorted(aulas, key=lambda x: x["start"])[0]
                dt_aula = parse_dt_aula(aula["start"])
            else:
                dt_aula = datetime.now() + timedelta(minutes=30)
        except Exception:
            dt_aula = datetime.now() + timedelta(minutes=30)

    _executar_pre_aula(dt_aula)
    estado["alerta_enviado"] = True
    salvar_estado(estado)


# ── MODO: Gravar ──────────────────────────────────────────────────
def modo_gravar():
    """Modo --gravar: inicia gravação + transcrição + análise."""
    estado = carregar_estado()
    if estado.get("gravacao_iniciada"):
        log("INFO", "Gravação já foi iniciada hoje. Ignorando.")
        return

    estado["gravacao_iniciada"] = True
    salvar_estado(estado)

    log("INFO", "Acionando script de gravação e análise IA...")
    python_exe = sys.executable
    result = subprocess.run(
        [python_exe, SCRIPT_GRAVAR],
        cwd=os.path.dirname(SCRIPT_GRAVAR)
    )
    if result.returncode == 0:
        log("OK", "Pipeline de gravação + análise concluído!")
    else:
        log("ERRO", f"Script de gravação encerrou com código {result.returncode}")


# ── MODO: Watcher de Zoom (Guardião em Background) ────────────────
def modo_watch():
    """Modo --watch: monitor leve em background que detecta abertura do Zoom."""
    log("WATCHER", "Guardião de Zoom ativo em segundo plano...")
    from gravar_e_analisar_aula import verificar_zoom_ativo

    zoom_estava_aberto = False

    while True:
        try:
            zoom_rodando = verificar_zoom_ativo()
            if zoom_rodando and not zoom_estava_aberto:
                log("WATCHER", "Zoom detectado! Verificando se é aula de inglês...")
                estado = carregar_estado()
                
                # Se ainda não gravou hoje:
                if not estado.get("gravacao_iniciada"):
                    log("WATCHER", "Iniciando gravação automática de aula pelo Zoom...")
                    modo_gravar()
                else:
                    log("WATCHER", "Aula de hoje já foi gravada ou está em andamento.")
                
            zoom_estava_aberto = zoom_rodando
            time.sleep(10)
        except Exception as e:
            log("WATCHER", f"Erro no watcher: {e}")
            time.sleep(15)


# ── Main ──────────────────────────────────────────────────────────
def main():
    os.makedirs(os.path.dirname(ESTADO_PATH), exist_ok=True)

    if "--pre-aula" in sys.argv:
        log("MODO", "Executando modo PRÉ-AULA")
        modo_pre_aula()
    elif "--gravar" in sys.argv:
        log("MODO", "Executando modo GRAVAÇÃO")
        modo_gravar()
    elif "--watch" in sys.argv:
        log("MODO", "Executando modo WATCHER DE ZOOM")
        modo_watch()
    else:
        log("MODO", "Executando modo ORQUESTRADOR")
        modo_orquestrar()


if __name__ == "__main__":
    main()
