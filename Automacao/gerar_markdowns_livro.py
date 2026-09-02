import os
import re
import asyncio
import io
import fitz  # PyMuPDF
from PIL import Image
import winocr

# Caminhos base
DRIVE_SB_DIR = r"I:\Meu Drive\Estudos\Inglês\Advanced\English_File_Advanced_por_Capitulo"
DRIVE_WB_DIR = r"I:\Meu Drive\Estudos\Inglês\Advanced\English_File_Advanced_Workbook_por_Capitulo"
OUTPUT_DIR_DRIVE = r"I:\Meu Drive\Estudos\Inglês\Advanced\English_File_Advanced_Markdown"
OUTPUT_DIR_LOCAL = r"c:\Users\rafae\.gemini\antigravity\playground\PESSOAL\Inglês\English_File_Advanced_Markdown"

# Mapeamentos de Grammar Bank por página / unidade
GB_MAPPING = {
    142: ("1A", "have: lexical and grammatical uses"),
    143: ("1B", "discourse markers (1): linkers"),
    144: ("2A", "the past: habitual events and specific incidents"),
    145: ("2B", "pronouns"),
    146: ("3A", "get"),
    147: ("3B", "discourse markers (2): adverbs and adverbial expressions"),
    148: ("4A", "speculation and deduction"),
    149: ("4B", "inversion"),
    150: ("5A", "distancing"),
    151: ("5B", "unreal uses of past tenses"),
    152: ("6A", "verb + object + infinitive or gerund"),
    153: ("6B", "conditional sentences"),
    154: ("7A", "permission, possibility, and necessity"),
    155: ("7B", "verbs of the senses"),
    156: ("8A", "gerunds and infinitives"),
    157: ("8B", "expressing future plans and arrangements"),
    158: ("9A", "ellipsis and substitution"),
    159: ("9B", "nouns: compound and possessive forms"),
    160: ("10A", "adding emphasis: cleft sentences"),
    161: ("10B", "relative clauses")
}

# Mapeamentos de Vocabulary Bank por página / unidade
VB_MAPPING = {
    162: ("1A", "Personality"),
    163: ("1B", "Work"),
    164: ("3A", "Phrases with get"),
    165: ("3B", "Conflict and warfare"),
    166: ("4B", "Sounds and the human voice"),
    167: ("5A", "Expressions with time"),
    168: ("5B", "Money"),
    169: ("6B", "Prefixes"),
    170: ("8B", "Travel and tourism"),
    171: ("9A", "Animal matters"),
    172: ("9B", "Preparing food")
}

# Mapas de Unidade para links relativos
UNIT_TO_GB_FILE = {unit: f"Student Book - Grammar Bank - Unit {unit} (Page {p}).md" for p, (unit, topic) in GB_MAPPING.items()}
UNIT_TO_VB_FILE = {unit: f"Student Book - Vocabulary Bank - {topic} (Page {p}).md" for p, (unit, topic) in VB_MAPPING.items()}

async def ocr_pdf_pages(pdf_path, start_page_num=1):
    """Extrai o texto OCR de todas as páginas de um PDF."""
    doc = fitz.open(pdf_path)
    pages_text = []
    for i, page in enumerate(doc):
        real_book_page = start_page_num + i
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        res = await winocr.recognize_pil(img, lang="en-US")
        text = res.text.strip()
        pages_text.append((real_book_page, text))
    return pages_text

def linkify_references(text, current_dir_depth=1):
    """Substitui referências como p.142 Grammar Bank 1A por links Markdown clicáveis."""
    prefix = "../" if current_dir_depth == 1 else ""
    
    # 1. Grammar Bank links: p.142 Grammar Bank 1A, Grammar Bank 1A, etc.
    for p, (unit, topic) in GB_MAPPING.items():
        gb_filename = f"Student Book - Grammar Bank - Unit {unit} (Page {p}).md"
        gb_rel_path = f"{prefix}11 - Reference and Bank Sections/{gb_filename}"
        
        # Regex patterns
        patterns = [
            rf"p\.?\s*{p}\s+Grammar\s+Bank\s*{unit}",
            rf"Grammar\s+Bank\s*{unit}",
            rf"p\.?\s*{p}\s+Grammar\s+Bank",
        ]
        for pat in patterns:
            text = re.sub(pat, f"[{unit} Grammar Bank (p.{p})]({gb_rel_path})", text, flags=re.IGNORECASE)

    # 2. Vocabulary Bank links: p.162 Vocabulary Bank, Vocabulary Bank 1A, etc.
    for p, (unit, topic) in VB_MAPPING.items():
        vb_filename = f"Student Book - Vocabulary Bank - {topic} (Page {page_p}).md" if (page_p := p) else ""
        vb_rel_path = f"{prefix}11 - Reference and Bank Sections/{vb_filename}"
        
        patterns = [
            rf"p\.?\s*{p}\s+Vocabulary\s+Bank",
            rf"Vocabulary\s+Bank\s+{topic}",
            rf"Vocabulary\s+Bank\s+p\.?\s*{p}"
        ]
        for pat in patterns:
            text = re.sub(pat, f"[Vocabulary Bank: {topic} (p.{p})]({vb_rel_path})", text, flags=re.IGNORECASE)

    # 3. Communication, Writing, Listening links
    text = re.sub(r"p\.?\s*(10[6-9]|11[0-5])\s+Communication", rf"[\g<0>]({prefix}11 - Reference and Bank Sections/Student Book - Communication (Pages 106-115).md)", text, flags=re.IGNORECASE)
    text = re.sub(r"p\.?\s*(11[6-9]|12[0-9])\s+Writing", rf"[\g<0>]({prefix}11 - Reference and Bank Sections/Student Book - Writing (Pages 116-129).md)", text, flags=re.IGNORECASE)
    text = re.sub(r"p\.?\s*(13[0-9]|14[0-1])\s+Listening", rf"[\g<0>]({prefix}11 - Reference and Bank Sections/Student Book - Listening (Pages 130-141).md)", text, flags=re.IGNORECASE)

    return text

def parse_page_range(filename):
    """Extrai o número da página inicial do nome do arquivo (ex: Pages 6-9 -> 6)."""
    m = re.search(r"Page[s]?\s*(\d+)", filename, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1

def extract_unit_tag(filename):
    """Extrai a tag da unidade (ex: 1A, 3B, Revise and Check 1&2, etc.)."""
    m = re.search(r"(\d+[A-B])", filename)
    if m:
        return m.group(1)
    return None

async def process_student_book():
    print("=== Processando Student Book ===")
    os.makedirs(OUTPUT_DIR_DRIVE, exist_ok=True)
    os.makedirs(OUTPUT_DIR_LOCAL, exist_ok=True)

    sb_subdirs = sorted([d for d in os.listdir(DRIVE_SB_DIR) if os.path.isdir(os.path.join(DRIVE_SB_DIR, d))])
    
    for subdir in sb_subdirs:
        in_folder = os.path.join(DRIVE_SB_DIR, subdir)
        out_folder_drive = os.path.join(OUTPUT_DIR_DRIVE, subdir)
        out_folder_local = os.path.join(OUTPUT_DIR_LOCAL, subdir)
        os.makedirs(out_folder_drive, exist_ok=True)
        os.makedirs(out_folder_local, exist_ok=True)

        pdf_files = sorted([f for f in os.listdir(in_folder) if f.endswith(".pdf")])
        for pdf_file in pdf_files:
            pdf_path = os.path.join(in_folder, pdf_file)
            start_p = parse_page_range(pdf_file)
            unit_tag = extract_unit_tag(pdf_file)
            print(f"OCR Student Book: {subdir} / {pdf_file} (Start page: {start_p})")

            # Especial: Grammar Bank
            if "04 - Grammar Bank" in pdf_file:
                pages_data = await ocr_pdf_pages(pdf_path, start_page_num=142)
                # 1. Arquivos individuais por unidade
                for page_num, text in pages_data:
                    if page_num in GB_MAPPING:
                        u_tag, topic = GB_MAPPING[page_num]
                        gb_title = f"Student Book - Grammar Bank - Unit {u_tag} (Page {page_num})"
                        linked_text = linkify_references(text, current_dir_depth=1)
                        md_content = f"""---
title: "{gb_title}"
type: "Student Book - Grammar Bank"
unit: "{u_tag}"
topic: "{topic}"
page: {page_num}
student_book_unit: "../{subdir.replace('11 - Reference and Bank Sections', '')}/"
---

# 📖 Grammar Bank — Unit {u_tag}: {topic}
**Page {page_num}**

---

{linked_text}
"""
                        out_name = f"{gb_title}.md"
                        with open(os.path.join(out_folder_drive, out_name), "w", encoding="utf-8") as f:
                            f.write(md_content)
                        with open(os.path.join(out_folder_local, out_name), "w", encoding="utf-8") as f:
                            f.write(md_content)

                # 2. Arquivo consolidado Grammar Bank
                full_gb_content = """---
title: "Student Book - Grammar Bank (Pages 142-161)"
type: "Student Book - Grammar Bank"
pages: "142-161"
---

# 📖 Grammar Bank (Pages 142–161)

"""
                for page_num, text in pages_data:
                    u_tag, topic = GB_MAPPING.get(page_num, ("", ""))
                    full_gb_content += f"\n\n## Page {page_num} — Unit {u_tag}: {topic}\n\n" + linkify_references(text, current_dir_depth=1)
                
                with open(os.path.join(out_folder_drive, "Student Book - Grammar Bank (Pages 142-161).md"), "w", encoding="utf-8") as f:
                    f.write(full_gb_content)
                with open(os.path.join(out_folder_local, "Student Book - Grammar Bank (Pages 142-161).md"), "w", encoding="utf-8") as f:
                    f.write(full_gb_content)
                continue

            # Especial: Vocabulary Bank
            if "05 - Vocabulary Bank" in pdf_file:
                pages_data = await ocr_pdf_pages(pdf_path, start_page_num=162)
                for page_num, text in pages_data:
                    if page_num in VB_MAPPING:
                        u_tag, topic = VB_MAPPING[page_num]
                        vb_title = f"Student Book - Vocabulary Bank - {topic} (Page {page_num})"
                        linked_text = linkify_references(text, current_dir_depth=1)
                        md_content = f"""---
title: "{vb_title}"
type: "Student Book - Vocabulary Bank"
unit: "{u_tag}"
topic: "{topic}"
page: {page_num}
---

# 📚 Vocabulary Bank — {topic} (Unit {u_tag})
**Page {page_num}**

---

{linked_text}
"""
                        out_name = f"{vb_title}.md"
                        with open(os.path.join(out_folder_drive, out_name), "w", encoding="utf-8") as f:
                            f.write(md_content)
                        with open(os.path.join(out_folder_local, out_name), "w", encoding="utf-8") as f:
                            f.write(md_content)

                # Consolidado Vocabulary Bank
                full_vb_content = """---
title: "Student Book - Vocabulary Bank (Pages 162-172)"
type: "Student Book - Vocabulary Bank"
pages: "162-172"
---

# 📚 Vocabulary Bank (Pages 162–172)

"""
                for page_num, text in pages_data:
                    u_tag, topic = VB_MAPPING.get(page_num, ("", ""))
                    full_vb_content += f"\n\n## Page {page_num} — {topic} (Unit {u_tag})\n\n" + linkify_references(text, current_dir_depth=1)

                with open(os.path.join(out_folder_drive, "Student Book - Vocabulary Bank (Pages 162-172).md"), "w", encoding="utf-8") as f:
                    f.write(full_vb_content)
                with open(os.path.join(out_folder_local, "Student Book - Vocabulary Bank (Pages 162-172).md"), "w", encoding="utf-8") as f:
                    f.write(full_vb_content)
                continue

            # Capítulos normais do Student Book
            pages_data = await ocr_pdf_pages(pdf_path, start_page_num=start_p)
            clean_base = os.path.splitext(pdf_file)[0]
            md_filename = f"Student Book - {clean_base}.md"
            
            # Metadados e links rápidos
            gb_link = f"../11 - Reference and Bank Sections/{UNIT_TO_GB_FILE[unit_tag]}" if unit_tag and unit_tag in UNIT_TO_GB_FILE else "N/A"
            vb_link = f"../11 - Reference and Bank Sections/{UNIT_TO_VB_FILE[unit_tag]}" if unit_tag and unit_tag in UNIT_TO_VB_FILE else "N/A"
            wb_link = f"../../English_File_Advanced_Workbook_Markdown/{subdir}/Workbook - {clean_base}.md" if unit_tag else "N/A"

            md_content = f"""---
title: "Student Book - {clean_base}"
type: "Student Book"
section: "{subdir}"
unit: "{unit_tag if unit_tag else 'N/A'}"
pages: "{start_p}-{start_p + len(pages_data) - 1}"
grammar_bank: "{gb_link}"
vocabulary_bank: "{vb_link}"
workbook: "{wb_link}"
---

# 📘 Student Book — {clean_base}

> **Quick References:**
> * **Grammar Bank:** {f'[{unit_tag} Grammar Bank]({gb_link})' if gb_link != 'N/A' else 'N/A'}
> * **Vocabulary Bank:** {f'[Vocabulary Bank]({vb_link})' if vb_link != 'N/A' else 'N/A'}

---

"""
            for page_num, text in pages_data:
                linked_text = linkify_references(text, current_dir_depth=1)
                md_content += f"\n\n## 📄 Page {page_num}\n\n{linked_text}\n\n---"

            with open(os.path.join(out_folder_drive, md_filename), "w", encoding="utf-8") as f:
                f.write(md_content)
            with open(os.path.join(out_folder_local, md_filename), "w", encoding="utf-8") as f:
                f.write(md_content)

async def process_workbook():
    print("=== Processando Workbook ===")
    wb_subdirs = sorted([d for d in os.listdir(DRIVE_WB_DIR) if os.path.isdir(os.path.join(DRIVE_WB_DIR, d))])
    
    for subdir in wb_subdirs:
        in_folder = os.path.join(DRIVE_WB_DIR, subdir)
        out_folder_drive = os.path.join(OUTPUT_DIR_DRIVE.replace("English_File_Advanced_Markdown", "English_File_Advanced_Workbook_Markdown"), subdir)
        out_folder_local = os.path.join(OUTPUT_DIR_LOCAL.replace("English_File_Advanced_Markdown", "English_File_Advanced_Workbook_Markdown"), subdir)
        os.makedirs(out_folder_drive, exist_ok=True)
        os.makedirs(out_folder_local, exist_ok=True)

        pdf_files = sorted([f for f in os.listdir(in_folder) if f.endswith(".pdf")])
        for pdf_file in pdf_files:
            pdf_path = os.path.join(in_folder, pdf_file)
            start_p = parse_page_range(pdf_file)
            unit_tag = extract_unit_tag(pdf_file)
            print(f"OCR Workbook: {subdir} / {pdf_file} (Start page: {start_p})")

            pages_data = await ocr_pdf_pages(pdf_path, start_page_num=start_p)
            clean_base = os.path.splitext(pdf_file)[0]
            if not clean_base.lower().startswith("workbook"):
                clean_base = f"Workbook - {clean_base}"
            md_filename = f"{clean_base}.md"

            sb_link = f"../../English_File_Advanced_Markdown/{subdir}/Student Book - {clean_base.replace('Workbook - ', '')}.md"

            md_content = f"""---
title: "{clean_base}"
type: "Workbook"
section: "{subdir}"
unit: "{unit_tag if unit_tag else 'N/A'}"
pages: "{start_p}-{start_p + len(pages_data) - 1}"
student_book_reference: "{sb_link}"
---

# 📝 Workbook — {clean_base}

> **Student Book Companion:** [Student Book Reference]({sb_link})

---

"""
            for page_num, text in pages_data:
                linked_text = linkify_references(text, current_dir_depth=1)
                md_content += f"\n\n## 📄 Page {page_num}\n\n{linked_text}\n\n---"

            with open(os.path.join(out_folder_drive, md_filename), "w", encoding="utf-8") as f:
                f.write(md_content)
            with open(os.path.join(out_folder_local, md_filename), "w", encoding="utf-8") as f:
                f.write(md_content)

async def generate_master_index():
    print("=== Gerando Índice Geral ===")
    index_content = """# 📚 English File Advanced — Master Index & Hub de Estudos

Este índice reúne todos os materiais do **Student's Book**, **Workbook**, **Grammar Bank** e **Vocabulary Bank** devidamente linkados e estruturados em Markdown.

---

## 📘 Student's Book por Capítulo

| Seção / Arquivo | Unidade | Páginas | Grammar Bank | Vocabulary Bank | Workbook |
| :--- | :---: | :---: | :---: | :---: | :---: |
"""
    # Lista arquivos gerados
    for root, dirs, files in os.walk(OUTPUT_DIR_LOCAL):
        for file in sorted(files):
            if file.startswith("Student Book - ") and not "Grammar Bank -" in file and not "Vocabulary Bank -" in file:
                rel = os.path.relpath(os.path.join(root, file), OUTPUT_DIR_LOCAL).replace("\\", "/")
                u_tag = extract_unit_tag(file) or "-"
                p_range = parse_page_range(file)
                gb_col = f"[{u_tag} Grammar Bank](English_File_Advanced_Markdown/11%20-%20Reference%20and%20Bank%20Sections/{UNIT_TO_GB_FILE[u_tag]})" if u_tag in UNIT_TO_GB_FILE else "-"
                vb_col = f"[Vocabulary Bank](English_File_Advanced_Markdown/11%20-%20Reference%20and%20Bank%20Sections/{UNIT_TO_VB_FILE[u_tag]})" if u_tag in UNIT_TO_VB_FILE else "-"
                wb_col = f"[Workbook](English_File_Advanced_Workbook_Markdown/{os.path.basename(root)}/Workbook%20-%20{file.replace('Student Book - ', '')})" if u_tag != "-" else "-"
                index_content += f"| [{file}](English_File_Advanced_Markdown/{rel}) | {u_tag} | {p_range} | {gb_col} | {vb_col} | {wb_col} |\n"

    index_content += """

---

## 📖 Grammar Bank Completo

| Unidade | Tópico Gramatical | Página | Arquivo Markdown |
| :---: | :--- | :---: | :--- |
"""
    for page_num, (u_tag, topic) in sorted(GB_MAPPING.items()):
        gb_fname = f"Student Book - Grammar Bank - Unit {u_tag} (Page {page_num}).md"
        index_content += f"| **Unit {u_tag}** | {topic} | p. {page_num} | [Acessar {u_tag}](English_File_Advanced_Markdown/11%20-%20Reference%20and%20Bank%20Sections/{gb_fname}) |\n"

    index_content += """

---

## 📚 Vocabulary Bank Completo

| Unidade | Tópico Vocabulário | Página | Arquivo Markdown |
| :---: | :--- | :---: | :--- |
"""
    for page_num, (u_tag, topic) in sorted(VB_MAPPING.items()):
        vb_fname = f"Student Book - Vocabulary Bank - {topic} (Page {page_num}).md"
        index_content += f"| **Unit {u_tag}** | {topic} | p. {page_num} | [Acessar {topic}](English_File_Advanced_Markdown/11%20-%20Reference%20and%20Bank%20Sections/{vb_fname}) |\n"

    # Salva o Master Index
    for p in [
        os.path.join(r"I:\Meu Drive\Estudos\Inglês\Advanced", "00_INDICE_GERAL_LIVROS.md"),
        os.path.join(r"c:\Users\rafae\.gemini\antigravity\playground\PESSOAL\Inglês", "00_INDICE_GERAL_LIVROS.md")
    ]:
        with open(p, "w", encoding="utf-8") as f:
            f.write(index_content)

async def main():
    await process_student_book()
    await process_workbook()
    await generate_master_index()
    print("=== TODOS OS ARQUIVOS FORAM GERADOS COM SUCESSO! ===")

if __name__ == "__main__":
    asyncio.run(main())
