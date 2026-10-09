# Contexto do Sistema de Gravação e Análise de Aulas de Inglês

Este documento registra a arquitetura completa, configurações, histórico de alterações e instruções para retomada contínua do ecossistema de automação de aulas de inglês do Rafael.

---

## 🎯 1. Visão Geral e Propósito

O sistema automatiza o ciclo completo das aulas particulares de inglês (curso *English File Advanced* com a professora Patrícia):
1. **Lembrete Pré-Aula (T-30min)**: Consulta a agenda no Google Calendar, extrai os últimos tópicos/metas do `Tracker_Aulas.md` e envia para o WhatsApp do Rafael via CallMeBot, além de abrir o arquivo local para aquecimento.
2. **Gravação Inteligente (T-0)**: Captura simultânea em alta fidelidade via WASAPI Loopback (áudio da professora no fone de ouvido) + Microfone (fala do Rafael).
3. **Transcrição em Nuvem**: Groq Whisper Large v3 Turbo com divisão automática em chunks (<20MB) para contornar limites de API.
4. **Análise Pedagógica com IA**: Modelo Llama 3.3 70B / GPT-OSS 120B na Groq que extrai:
   - Resumo e ponto exato de parada no livro.
   - Vocabulário avançado & expressões C1/C2.
   - Gap Log e oportunidades de upgrade gramatical.
   - Correções pontuais da professora Patrícia.
   - Resumo ativo para fixação.
   - Planejamento e 2 palavras-alvo para a próxima aula.
5. **Atualização Automática do Tracker**: Salva a análise diretamente no `Tracker_Aulas.md` no Google Drive.

---

## 📁 2. Caminhos e Estrutura de Arquivos

* **Workspace Local**: `C:\Users\rafae\.gemini\antigravity\playground\PESSOAL\Inglês`
* **Google Drive**: `I:\Meu Drive\Estudos\Inglês\Advanced`

### Arquivos Principais:
| Arquivo | Localização | Função |
| :--- | :--- | :--- |
| `checar_agenda.py` | `Automacao/checar_agenda.py` | Orquestrador principal de agenda e Guardião de Zoom em background |
| `gravar_e_analisar_aula.py` | `Automacao/gravar_e_analisar_aula.py` | Gravação dual WASAPI, chunking, Whisper, Llama e atualização do Tracker |
| `config_ia.json` | `Automacao/config_ia.json` | Chaves de API Groq, modelos, telefone e API Key do CallMeBot |
| `estado_dia.json` | `Automacao/estado_dia.json` | Controle de idempotência diária para evitar execuções duplicadas |
| `Tracker_Aulas.md` | Raiz do Google Drive (`I:\...`) | Registro histórico contínuo das aulas e planejamentos |
| `indice_capitulos.csv` | `English_File_Advanced_por_Capitulo/` | Mapeamento estruturado das unidades e páginas do livro |

---

## ⚙️ 3. Mecanismos de Execução Automática (Windows)

A automação opera de forma 100% autônoma, sem necessidade do Antigravity ou IDE abertos:

1. **Task Scheduler Diário (`Orquestrador_Aulas_Ingles_IA`)**:
   - Disparo: Diariamente às **07:00**
   - Configurações: `StartWhenAvailable = True` (executa ao acordar se o laptop estava suspenso/desligado), `WakeToRun = True`.
   - Ação: Executa `checar_agenda.py`, que consulta o iCal do Google Calendar. Se houver aula, agenda duas tarefas one-shot no Windows (`Ingles_Alerta_PreAula` às T-30min e `Ingles_Gravacao_Aula` no horário T-0).

2. **Guardião de Zoom (Watcher em Background)**:
   - Disparo: Inicialização do Windows (`Startup\Orquestrador_Aulas_Ingles.lnk`).
   - Executável: `pythonw.exe "...\checar_agenda.py" --watch` (invisível, 0% CPU).
   - Função de Redundância: Caso uma aula seja combinada/remarcada de última hora sem constar no Google Calendar, o guardião detecta a abertura do **Zoom.exe** e dispara a gravação imediatamente.

---

## 🛠️ 4. Evoluções e Correções Implementadas

1. **Eliminação de `time.sleep()` Longos**: Substituição de esperas ativas por agendamentos pontuais no Task Scheduler do Windows, tornando o fluxo imune a suspensões e hibernações do laptop.
2. **Chunking Automático para o Groq Whisper**: Áudios grandes (>20MB) são divididos automaticamente em fatias temporárias de ~10 minutos, evitando o erro HTTP 413 (*Request Entity Too Large*).
3. **Feedback Visual e Encerramento Manual**: Logs periódicos a cada 30 segundos no console (`[GRAVANDO] ⏱️ XX:XX min...`) e suporte a encerramento gracioso via `Ctrl+C` a qualquer momento.
4. **Fechamento e Notificação Pós-Aula**: Ao concluir a análise, o sistema emite alerta sonoro (`winsound`), popup nativo do Windows e fecha o terminal automaticamente após 8 segundos.

---

## 📚 5. Histórico Recente de Aulas

* **26/08/2026**: File 4 - *"The sound of silence"* (pág. 40-43) — Discussão sobre ruído e vagões silenciosos, linguagem de opinião (*as far as I'm concerned*, *live and let live*, *obnoxious*).
* **31/08/2026**: File 4B / Grammar Bank — Modal verbs of deduction (*bound to*, *deduction*, *gotten* vs *got*, *never have I seen*).
* **01/09/2026**: Vocabulary Bank (pág. 162-168) — Collocations com *get*, distinção semântica (*defeat* vs *surrender*), termos avançados (*hypertaxed*, *twin-flame*, *implausible*).
* **Próxima Aula Prevista**: Conclusão do Vocabulary Bank (pág. 169-172) & File 6A (*Help, I need somebody*, pág. 56-59) com foco nas palavras-alvo **resilient** e **catharsis**.

---

## 🚀 6. Guia para Novas Conversas

Ao iniciar uma nova sessão sobre as aulas de inglês, o assistente deve:
1. Consultar este arquivo `CONTEXTO_AUTOMACAO_INGLES.md` para recuperar todo o contexto técnico e pedagógico.
2. Verificar o final do arquivo [`Tracker_Aulas.md`](file:///H:/Meu%20Drive/Estudos/Ingl%C3%AAs/Advanced/Tracker_Aulas.md) para saber o último ponto de parada e palavras-alvo combinadas.
3. Se necessário testar ou ajustar a automação, utilizar os scripts localizados em `Automacao/`.
