import os
from gravar_e_analisar_aula import carregar_config, transcrever_com_groq_whisper, analisar_com_groq_llama, atualizar_tracker, BASE_DIR

def recuperar():
    cfg = carregar_config()
    api_key = cfg.get("GROQ_API_KEY")
    if not api_key:
        print("API Key não encontrada.")
        return

    # Procura o áudio com o nome e data de hoje ou ajusta se necessário
    audio_path = os.path.join(BASE_DIR, "Gravacoes", "2026-09-21_Rafa-EF.wav")
    if not os.path.exists(audio_path):
        print(f"Áudio não encontrado em {audio_path}")
        # Tenta listar para ver o nome exato
        dir_gravacoes = os.path.join(BASE_DIR, "Gravacoes")
        if os.path.exists(dir_gravacoes):
            print("Arquivos na pasta:", os.listdir(dir_gravacoes))
        return
            
    print(f"Iniciando recuperação a partir de: {audio_path}")
    
    # 1. Transcrever
    transcricao = transcrever_com_groq_whisper(
        audio_path, 
        api_key, 
        cfg.get("MODELO_AUDIO", "whisper-large-v3-turbo")
    )
    if not transcricao:
        return
        
    # 2. Analisar
    relatorio = analisar_com_groq_llama(
        transcricao, 
        api_key, 
        cfg.get("MODELO_TEXTO", "llama-3.3-70b-versatile")
    )
    
    # 3. Salvar
    if relatorio:
        # Salva backup local primeiro pra garantir
        local_backup = os.path.join(os.path.dirname(__file__), "Relatorio_Recuperado_Backup.md")
        with open(local_backup, "w", encoding="utf-8") as f:
            f.write(relatorio)
        print(f"Backup salvo localmente em: {local_backup}")
        
        try:
            atualizar_tracker(relatorio)
            print("Tracker atualizado com sucesso no Google Drive!")
        except Exception as e:
            print(f"Erro ao tentar salvar no Tracker do Drive: {e}")

if __name__ == "__main__":
    recuperar()
