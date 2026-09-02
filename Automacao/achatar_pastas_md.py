import os
import shutil
import re

# Caminhos no Google Drive e Local
DRIVE_BASE = r"I:\Meu Drive\Estudos\Inglês\Advanced"
LOCAL_BASE = r"c:\Users\rafae\.gemini\antigravity\playground\PESSOAL\Inglês"

# Pastas de destino achatadas (Flat - sem subpastas)
DRIVE_SB_FLAT = os.path.join(DRIVE_BASE, "English_File_Student_Book_MD")
DRIVE_WB_FLAT = os.path.join(DRIVE_BASE, "English_File_Workbook_MD")
DRIVE_ALL_FLAT = os.path.join(DRIVE_BASE, "English_File_TODOS_MD")

LOCAL_SB_FLAT = os.path.join(LOCAL_BASE, "English_File_Student_Book_MD")
LOCAL_WB_FLAT = os.path.join(LOCAL_BASE, "English_File_Workbook_MD")
LOCAL_ALL_FLAT = os.path.join(LOCAL_BASE, "English_File_TODOS_MD")

for p in [DRIVE_SB_FLAT, DRIVE_WB_FLAT, DRIVE_ALL_FLAT, LOCAL_SB_FLAT, LOCAL_WB_FLAT, LOCAL_ALL_FLAT]:
    os.makedirs(p, exist_ok=True)

# 1. Copia e ajusta links do Student Book
sb_source = os.path.join(LOCAL_BASE, "English_File_Advanced_Markdown")
for root, dirs, files in os.walk(sb_source):
    for file in files:
        if file.endswith(".md"):
            src_file = os.path.join(root, file)
            with open(src_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Ajusta links relativos para apontar diretamente para o arquivo na mesma pasta
            content = content.replace("../11 - Reference and Bank Sections/", "./")
            content = content.replace("11%20-%20Reference%20and%20Bank%20Sections/", "")
            content = re.sub(r"\.\./\.\./English_File_Advanced_Workbook_Markdown/[^/]+/", "../English_File_Workbook_MD/", content)

            # Salva nas pastas flat
            for dest_dir in [DRIVE_SB_FLAT, LOCAL_SB_FLAT, DRIVE_ALL_FLAT, LOCAL_ALL_FLAT]:
                with open(os.path.join(dest_dir, file), "w", encoding="utf-8") as f:
                    f.write(content)

# 2. Copia e ajusta links do Workbook
wb_source = os.path.join(LOCAL_BASE, "English_File_Advanced_Workbook_Markdown")
for root, dirs, files in os.walk(wb_source):
    for file in files:
        if file.endswith(".md"):
            src_file = os.path.join(root, file)
            with open(src_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Ajusta links relativos para apontar para Student Book
            content = re.sub(r"\.\./\.\./English_File_Advanced_Markdown/[^/]+/", "../English_File_Student_Book_MD/", content)

            # Salva nas pastas flat
            for dest_dir in [DRIVE_WB_FLAT, LOCAL_WB_FLAT, DRIVE_ALL_FLAT, LOCAL_ALL_FLAT]:
                with open(os.path.join(dest_dir, file), "w", encoding="utf-8") as f:
                    f.write(content)

print(f"Student Book Flat: {len(os.listdir(LOCAL_SB_FLAT))} arquivos")
print(f"Workbook Flat: {len(os.listdir(LOCAL_WB_FLAT))} arquivos")
print(f"Todos MD Flat: {len(os.listdir(LOCAL_ALL_FLAT))} arquivos")
print("=== Achatamento concluído com sucesso! ===")
