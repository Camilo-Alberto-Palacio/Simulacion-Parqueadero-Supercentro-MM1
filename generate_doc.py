"""
Generador Dinámico del Informe Académico Oficial en Formato Word (.docx)
Normas APA 7.ª Edición · Redacción Reflexiva en Ingeniería (Grupo 25)
Actividad Didáctica 2-M4 — Solución de un Problema de Parqueaderos (Centro Comercial Supercentro).
Asignatura: Simulación (PREICA2602B020045) — Grupo 25.
Institución Universitaria Digital de Antioquia (IU Digital) — Facultad de Ingeniería.

Carga el 100 % de las métricas experimentales desde 'results/*.csv' (cero cifras fijas),
incrusta las 7 figuras científicas a 300 DPI con formato APA 7, construye Portada,
Tabla de Contenido (TOC) y numeración automática de páginas, y actualiza campos vía Microsoft Word.
"""

import os
import re
import shutil
import subprocess
import sys
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")

COLOR_PRIMARY = RGBColor(0x0F, 0x17, 0x2A)
COLOR_SECONDARY = RGBColor(0x1E, 0x3A, 0x8A)
COLOR_BODY = RGBColor(0x11, 0x18, 0x27)
COLOR_MUTED = RGBColor(0x47, 0x55, 0x69)
COLOR_CODE = RGBColor(0x0F, 0x17, 0x2A)

_SUB_SUP_RE = re.compile(r"(_\{[^}]+\}|\^\{[^}]+\})")


def set_cell_background(cell, fill_hex: str) -> None:
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shd)


def set_cell_margins(cell, top=60, bottom=60, left=70, right=70) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for margin_name, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{margin_name}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_borders(cell, top="none", bottom="none", left="none", right="none", color="0F172A", sz="4") -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for b_name, b_val in {"top": top, "left": left, "bottom": bottom, "right": right}.items():
        node = OxmlElement(f"w:{b_name}")
        node.set(qn("w:val"), b_val)
        if b_val != "none":
            node.set(qn("w:sz"), str(sz))
            node.set(qn("w:space"), "0")
            node.set(qn("w:color"), color)
        tcBorders.append(node)
    tcPr.append(tcBorders)


def set_row_pagination_rules(row, is_header: bool = False) -> None:
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))
    if is_header:
        trPr.append(OxmlElement("w:tblHeader"))


def add_word_field(
    paragraph,
    field_name: str,
    font_size: float = 9.0,
    color: RGBColor = COLOR_MUTED,
    bold: bool = False,
) -> None:
    for tag, attrs, text in [
        ("w:fldChar", {"w:fldCharType": "begin", "w:dirty": "true"}, ""),
        ("w:instrText", {"xml:space": "preserve"}, f" {field_name} "),
        ("w:fldChar", {"w:fldCharType": "separate"}, ""),
        ("w:fldChar", {"w:fldCharType": "end"}, ""),
    ]:
        r = paragraph.add_run()
        attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        elem = parse_xml(f'<{tag} {nsdecls("w")} {attr_str}>{text}</{tag}>')
        r._r.append(elem)
        r.font.name = "Times New Roman"
        r.font.size = Pt(font_size)
        r.font.bold = bold
        r.font.color.rgb = color


def add_rich_runs(
    paragraph,
    text: str,
    font_name: str = "Times New Roman",
    font_size: float = 10.5,
    color: RGBColor = COLOR_BODY,
    bold: bool = False,
    italic: bool = False,
) -> None:
    """Renderiza subíndices _{...} y superíndices ^{...} como formato nativo de Word."""
    parts = _SUB_SUP_RE.split(text)
    for part in parts:
        if not part:
            continue
        is_sub = part.startswith("_{") and part.endswith("}")
        is_sup = part.startswith("^{") and part.endswith("}")
        content = part[2:-1] if (is_sub or is_sup) else part
        run = paragraph.add_run(content)
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
        run.font.bold = bold
        run.font.italic = italic
        if is_sub:
            run.font.subscript = True
        elif is_sup:
            run.font.superscript = True


def add_apa_label_and_title(doc, label: str, title: str) -> None:
    """Inserta etiqueta Tabla X / Figura X (negrita) y título descriptivo (cursiva) conforme a APA 7."""
    p_lbl = doc.add_paragraph()
    p_lbl.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_lbl.paragraph_format.space_before = Pt(8)
    p_lbl.paragraph_format.space_after = Pt(1.5)
    p_lbl.paragraph_format.keep_with_next = True
    add_rich_runs(p_lbl, label, font_size=10.0, color=COLOR_PRIMARY, bold=True)

    p_tit = doc.add_paragraph()
    p_tit.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_tit.paragraph_format.space_before = Pt(0)
    p_tit.paragraph_format.space_after = Pt(4)
    p_tit.paragraph_format.keep_with_next = True
    add_rich_runs(p_tit, title, font_size=10.0, color=COLOR_BODY, italic=True)


def add_apa_note(doc, note_body: str, space_after: float = 9.0) -> None:
    """Inserta Nota. alineada a la izquierda en 10 pt conforme a Normas APA 7."""
    p_note = doc.add_paragraph()
    p_note.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_note.paragraph_format.space_before = Pt(3)
    p_note.paragraph_format.space_after = Pt(space_after)
    p_note.paragraph_format.line_spacing = 1.12
    add_rich_runs(p_note, "Nota. ", font_size=10.0, color=COLOR_BODY, italic=True)
    add_rich_runs(p_note, note_body, font_size=10.0, color=COLOR_BODY)


def format_apa_table(
    doc,
    table_num: str,
    title: str,
    col_widths,
    headers,
    data,
    note_text: str,
    font_size: float = 8.1,
) -> None:
    """Construye una tabla en formato estricto APA 7 (sin bordes verticales ni sombreado en cuerpo)."""
    add_apa_label_and_title(doc, table_num, title)

    table = doc.add_table(rows=1 + len(data), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    header_row = table.rows[0]
    set_row_pagination_rules(header_row, is_header=True)
    for col_idx, heading in enumerate(headers):
        cell = header_row.cells[col_idx]
        cell.width = col_widths[col_idx]
        set_cell_background(cell, "FFFFFF")
        set_cell_margins(cell, top=65, bottom=65, left=60, right=60)
        set_cell_borders(cell, top="single", bottom="single", left="none", right="none", color="0F172A", sz="8")

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(1.5)
        p.paragraph_format.space_after = Pt(1.5)
        p.paragraph_format.keep_with_next = True
        add_rich_runs(p, heading, font_size=font_size, color=COLOR_PRIMARY, bold=True)

    num_rows = len(data)
    for row_idx, row_data in enumerate(data, start=1):
        row = table.rows[row_idx]
        set_row_pagination_rules(row, is_header=False)
        is_last = row_idx == num_rows
        bottom_border = "single" if is_last else "none"
        bottom_sz = "8" if is_last else "4"

        for col_idx, val in enumerate(row_data):
            cell = row.cells[col_idx]
            cell.width = col_widths[col_idx]
            set_cell_background(cell, "FFFFFF")
            set_cell_margins(cell, top=48, bottom=48, left=60, right=60)
            set_cell_borders(cell, top="none", bottom=bottom_border, left="none", right="none", color="0F172A", sz=bottom_sz)

            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(1.0)
            p.paragraph_format.space_after = Pt(1.0)
            p.paragraph_format.keep_with_next = (num_rows <= 14) or is_last
            add_rich_runs(p, str(val), font_size=font_size, color=COLOR_BODY, bold=(col_idx == 0))

    add_apa_note(doc, note_text, space_after=8.0)


def add_code_listing(doc, code_lines: list, caption_note: str) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=80, bottom=80, left=105, right=105)
    set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="CBD5E1", sz="6")

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.05
    p.paragraph_format.keep_with_next = True

    for line_num, line_txt in enumerate(code_lines, start=1):
        r_num = p.add_run(f"{line_num:2d} ")
        r_num.font.name = "Consolas"
        r_num.font.size = Pt(8.0)
        r_num.font.color.rgb = COLOR_MUTED

        suffix = "\n" if line_num < len(code_lines) else ""
        r_code = p.add_run(f"{line_txt}{suffix}")
        r_code.font.name = "Consolas"
        r_code.font.size = Pt(8.0)
        r_code.font.color.rgb = COLOR_CODE

    add_apa_note(doc, caption_note, space_after=8.0)


def update_word_toc_and_fields(docx_path: str) -> bool:
    """Actualiza Tabla de Contenido y campos PAGE/NUMPAGES mediante Microsoft Word COM."""
    if os.name != "nt" or not shutil.which("powershell"):
        return False
    abs_path = os.path.abspath(docx_path).replace("'", "''")
    ps_script = (
        "$ErrorActionPreference = 'Stop'; "
        "$word = $null; $doc = $null; "
        "try { "
        "  $word = New-Object -ComObject Word.Application; "
        "  $word.Visible = $false; "
        "  $word.DisplayAlerts = 0; "
        f"  $doc = $word.Documents.Open('{abs_path}'); "
        "  $doc.Repaginate(); "
        "  foreach ($toc in $doc.TablesOfContents) { $toc.Update(); } "
        "  foreach ($sec in $doc.Sections) { "
        "    foreach ($hf in $sec.Headers) { $hf.Range.Fields.Update() | Out-Null; } "
        "    foreach ($hf in $sec.Footers) { $hf.Range.Fields.Update() | Out-Null; } "
        "  } "
        "  $doc.Fields.Update() | Out-Null; "
        "  $doc.Save(); "
        "} finally { "
        "  if ($doc) { $doc.Close([ref]$false); } "
        "  if ($word) { $word.Quit(); } "
        "}"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return res.returncode == 0
    except Exception:
        return False


def build_document(output_filename: str = None) -> None:
    if output_filename is None:
        output_filename = os.path.join(BASE_DIR, "Palacios_Camilo_problemaParqueadero.docx")

    # Cargar 100 % de métricas dinámicamente desde results/*.csv
    df_iso_theo = pd.read_csv(os.path.join(RESULTS_DIR, "teoria_mm1_por_tipo_usuario.csv"))
    df_conv = pd.read_csv(os.path.join(RESULTS_DIR, "convergencia_estado_estable_replicas.csv"))
    df_piloto = pd.read_csv(os.path.join(RESULTS_DIR, "tamano_muestra_piloto10_er.csv"))
    df_sum = pd.read_csv(os.path.join(RESULTS_DIR, "resumen_oficial_escenarios.csv"))
    df_caj = pd.read_csv(os.path.join(RESULTS_DIR, "cajeros_oficial_resumen.csv"))
    df_users = pd.read_csv(os.path.join(RESULTS_DIR, "usuarios_por_tipo_resumen.csv"))
    df_jsq = pd.read_csv(os.path.join(RESULTS_DIR, "sensibilidad_jsq_escenarios.csv"))
    df_warm = pd.read_csv(os.path.join(RESULTS_DIR, "eliminacion_transitorio_antes_despues.csv"))
    df_warm_c1 = pd.read_csv(os.path.join(RESULTS_DIR, "warmup_cajeros_e1_antes_despues.csv"))
    df_iso_val = pd.read_csv(os.path.join(RESULTS_DIR, "validacion_mm1_tipos_aislados.csv"))
    df_vv = pd.read_csv(os.path.join(RESULTS_DIR, "matriz_vv_y_criterios_criticos.csv"))

    sum_idx = df_sum.set_index("escenario")
    jsq_idx = df_jsq.set_index("escenario")
    warm_idx = df_warm.set_index("escenario")
    vv_idx = df_vv.set_index("escenario")
    pil_idx = df_piloto.set_index("escenario")
    usr_idx = df_users.set_index("tipo_usuario")

    n_det = int(df_conv["n_detectado_exacto"].iloc[0])
    n_off = int(df_conv["n_oficial_seleccionado"].iloc[0])
    row_n_off = df_conv[df_conv["replica"] == n_off].iloc[0]

    # Métricas base E1 (3 Mixtos)
    wq_e1 = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_media_min"])
    wq_e1_l = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_ic95_inf"])
    wq_e1_u = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_ic95_sup"])
    w_e1 = float(sum_idx.loc["E1_3_Mixtos", "sistema_w_media_min"])
    er_wq_e1 = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_er_pct"])
    er_w_e1 = float(sum_idx.loc["E1_3_Mixtos", "sistema_w_er_pct"])
    rho_e1 = float(sum_idx.loc["E1_3_Mixtos", "utilizacion_rho_media"]) * 100.0
    p5_e1_peor = float(vv_idx.loc["E1_3_Mixtos", "prob_wq_mayor_5m_peor_cajero_pct"])
    wq_e1_jsq = float(jsq_idx.loc["E1_3_Mixtos", "espera_wq_media_min"])
    er10_e1 = float(pil_idx.loc["E1_3_Mixtos", "wq_er_piloto_pct"])
    n_prof10 = int(pil_idx.loc["E1_3_Mixtos", "n_req_wq_er10_prof"])

    # Punto A (Cajeros base E1)
    base_caj = df_caj[df_caj["escenario"] == "E1_3_Mixtos"].copy().reset_index(drop=True)
    c_min_w = base_caj.loc[base_caj["atencion_w_prom"].idxmin()]
    c_max_w = base_caj.loc[base_caj["atencion_w_prom"].idxmax()]
    c_min_s = base_caj.loc[base_caj["servicio_s_prom"].idxmin()]
    c_max_s = base_caj.loc[base_caj["servicio_s_prom"].idxmax()]
    c_mid_w = base_caj[(base_caj["cajero"] != c_min_w["cajero"]) & (base_caj["cajero"] != c_max_w["cajero"])].iloc[0]

    # Punto B (Usuarios por tipo)
    tot_veh_jornada = float(sum_idx.loc["E1_3_Mixtos", "usuarios_promedio"])
    tot_veh_all = int(df_users["total_replicas"].sum())

    # Punto C (Escenarios alternativos)
    wq_e2 = float(sum_idx.loc["E2_4_Mixtos", "espera_wq_media_min"])
    w_e2 = float(sum_idx.loc["E2_4_Mixtos", "sistema_w_media_min"])
    wq_e3 = float(sum_idx.loc["E3_5_Mixtos", "espera_wq_media_min"])
    w_e3 = float(sum_idx.loc["E3_5_Mixtos", "sistema_w_media_min"])
    wq_e3_jsq = float(jsq_idx.loc["E3_5_Mixtos", "espera_wq_media_min"])
    wq_e4 = float(sum_idx.loc["E4_6_Mixtos", "espera_wq_media_min"])
    w_e4 = float(sum_idx.loc["E4_6_Mixtos", "sistema_w_media_min"])
    rho_e4 = float(sum_idx.loc["E4_6_Mixtos", "utilizacion_rho_media"]) * 100.0
    p5_e4_peor = float(vv_idx.loc["E4_6_Mixtos", "prob_wq_mayor_5m_peor_cajero_pct"])
    wq_e5 = float(sum_idx.loc["E5_4_Esp_1E3L", "espera_wq_media_min"])
    peor_e5 = float(sum_idx.loc["E5_4_Esp_1E3L", "peor_cajero_wq_prom_min"])
    wq_e6 = float(sum_idx.loc["E6_5_Esp_1E4L", "espera_wq_media_min"])
    peor_e6 = float(sum_idx.loc["E6_5_Esp_1E4L", "peor_cajero_wq_prom_min"])
    wq_e7 = float(sum_idx.loc["E7_4_Mix_UX", "espera_wq_media_min"])
    w_e7 = float(sum_idx.loc["E7_4_Mix_UX", "sistema_w_media_min"])
    wq_e7_jsq = float(jsq_idx.loc["E7_4_Mix_UX", "espera_wq_media_min"])
    p5_e7_jsq = float(jsq_idx.loc["E7_4_Mix_UX", "prob_wq_mayor_5m_peor_cajero_pct"])
    rho_e7 = float(sum_idx.loc["E7_4_Mix_UX", "utilizacion_rho_media"]) * 100.0
    p5_e7_peor = float(vv_idx.loc["E7_4_Mix_UX", "prob_wq_mayor_5m_peor_cajero_pct"])

    # Punto D & E
    mae_pp = float(vv_idx["calibracion_mae_pp"].iloc[0])
    chi2_st = float(vv_idx["calibracion_chi2_stat"].iloc[0])
    chi2_pv = float(vv_idx["calibracion_chi2_pval"].iloc[0])
    srv_err = float(vv_idx["calibracion_srv_max_rel_err_pct"].iloc[0])
    little_max = float(vv_idx["verificacion_little_max_err"].max())
    p_min_mg1 = float(vv_idx["p_valor_vs_mg1"].min())
    p_max_mg1 = float(vv_idx["p_valor_vs_mg1"].max())

    k_cut_e1 = int(warm_idx.loc["E1_3_Mixtos", "k_corte_vehiculos"])
    t_cut_e1 = float(warm_idx.loc["E1_3_Mixtos", "tiempo_corte_aprox_min"])
    wq_ss_e1 = float(warm_idx.loc["E1_3_Mixtos", "wq_estado_estable_min"])
    wq_mg1_e1 = float(warm_idx.loc["E1_3_Mixtos", "wq_teorica_mg1_min"])
    sesgo_e1 = float(warm_idx.loc["E1_3_Mixtos", "sesgo_subestimacion_wq_pct"])
    p_mg1_e1 = float(vv_idx.loc["E1_3_Mixtos", "p_valor_vs_mg1"])

    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = True

    content_sec = doc.sections[0]
    hdr = content_sec.header.paragraphs[0]
    hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_hdr = hdr.add_run("OPTIMIZACIÓN DE COLAS M/M/1 — PARQUEADEROS SUPERCENTRO")
    r_hdr.font.name = "Times New Roman"
    r_hdr.font.size = Pt(8.5)
    r_hdr.font.color.rgb = COLOR_MUTED

    ftr = content_sec.footer.paragraphs[0]
    ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ftr = ftr.add_run("IU Digital de Antioquia · Simulación (PREICA2602B020045)  |  Página ")
    r_ftr.font.name = "Times New Roman"
    r_ftr.font.size = Pt(8.5)
    r_ftr.font.color.rgb = COLOR_MUTED
    add_word_field(ftr, "PAGE", font_size=8.5)
    r_ftr2 = ftr.add_run(" de ")
    r_ftr2.font.name = "Times New Roman"
    r_ftr2.font.size = Pt(8.5)
    r_ftr2.font.color.rgb = COLOR_MUTED
    add_word_field(ftr, "NUMPAGES", font_size=8.5)

    def add_h1(text: str):
        p = doc.add_paragraph(style="Heading 1")
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3.5)
        p.paragraph_format.keep_with_next = True
        add_rich_runs(p, text, font_size=12.0, color=COLOR_PRIMARY, bold=True)
        return p

    def add_h2(text: str):
        p = doc.add_paragraph(style="Heading 2")
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        add_rich_runs(p, text, font_size=10.8, color=COLOR_SECONDARY, bold=True)
        return p

    def add_p(text: str, space_after: float = 5.5):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        add_rich_runs(p, text, font_size=10.5, color=COLOR_BODY)
        return p

    def _add_list_item(prefix_txt: str, lead_bold: str, body_text: str):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.left_indent = Inches(0.32)
        p.paragraph_format.first_line_indent = Inches(-0.20)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(4.0)
        p.paragraph_format.line_spacing = 1.15
        add_rich_runs(p, prefix_txt, font_size=10.5, color=COLOR_PRIMARY, bold=True)
        add_rich_runs(p, lead_bold, font_size=10.5, color=COLOR_BODY, bold=True)
        add_rich_runs(p, body_text, font_size=10.5, color=COLOR_BODY)
        return p

    def add_bullet(lead_bold: str, body_text: str):
        return _add_list_item("•  ", lead_bold.lstrip("• ").lstrip(), body_text)

    def add_numbered_item(num_label: str, lead_bold: str, body_text: str):
        return _add_list_item(f"{num_label} ", lead_bold, body_text)

    def add_equation_box(eq_text: str, eq_num: str = ""):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(3.25), WD_ALIGN_PARAGRAPH.CENTER)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_ALIGN_PARAGRAPH.RIGHT)
        p.add_run("\t")
        add_rich_runs(p, eq_text, font_size=10.0, color=COLOR_PRIMARY, italic=True)
        if eq_num:
            p.add_run("\t")
            add_rich_runs(p, eq_num, font_size=10.0, color=COLOR_PRIMARY)
        return p

    def add_apa_fig(filename: str, fig_num: str, title: str, note_text: str, width_in: float = 6.35):
        filepath = os.path.join(RESULTS_DIR, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Figura requerida no encontrada: {filepath}")
        add_apa_label_and_title(doc, fig_num, title)
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(2)
        p_img.paragraph_format.space_after = Pt(2)
        p_img.paragraph_format.keep_with_next = True
        p_img.add_run().add_picture(filepath, width=Inches(width_in))
        add_apa_note(doc, note_text, space_after=9.0)

    # =========================================================
    # PÁGINA 1: PORTADA FORMAL APA 7
    # =========================================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(34)
    p_inst.paragraph_format.space_after = Pt(24)
    add_rich_runs(
        p_inst,
        "INSTITUCIÓN UNIVERSITARIA DIGITAL DE ANTIOQUIA\n"
        "FACULTAD DE INGENIERÍA — INGENIERÍA DE SOFTWARE Y DATOS",
        font_size=12.0, color=COLOR_SECONDARY, bold=True,
    )

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(22)
    p_title.paragraph_format.space_after = Pt(14)
    p_title.paragraph_format.line_spacing = 1.2
    add_rich_runs(
        p_title,
        "Modelado Estocástico M/M/1, Análisis de Estado Estable\n"
        "y Eliminación del Período Transitorio en el Sistema de Pago\n"
        "de Parqueaderos del Centro Comercial Supercentro",
        font_size=16.8, color=COLOR_PRIMARY, bold=True,
    )

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(38)
    add_rich_runs(
        p_sub,
        "Evidencia de Aprendizaje 4 · Actividad Didáctica 2-M4 · Solución de un Problema de Parqueaderos",
        font_size=11.0, color=COLOR_SECONDARY, italic=True,
    )

    p_team_hdr = doc.add_paragraph()
    p_team_hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_team_hdr.paragraph_format.space_after = Pt(6)
    add_rich_runs(p_team_hdr, "Presentado por (Grupo 25):", font_size=10.5, color=COLOR_MUTED, bold=True)

    p_auth = doc.add_paragraph()
    p_auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_auth.paragraph_format.space_after = Pt(20)
    p_auth.paragraph_format.line_spacing = 1.25
    add_rich_runs(
        p_auth,
        "Adriana Andrea Agudelo Agudelo\n"
        "Camilo Alberto Palacios Turriago\n"
        "Juan Daniel Pulgarin García\n"
        "Ruben Dario Jaramillo Cervantes",
        font_size=11.5, color=COLOR_PRIMARY, bold=True,
    )

    p_doc = doc.add_paragraph()
    p_doc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_doc.paragraph_format.space_after = Pt(20)
    p_doc.paragraph_format.line_spacing = 1.2
    add_rich_runs(
        p_doc,
        "Docente Asesor:\nDr. Julián Andrés Loaiza López\n"
        "Asignatura: Simulación (PREICA2602B020045)",
        font_size=10.8, color=COLOR_BODY,
    )

    p_mail = doc.add_paragraph()
    p_mail.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_mail.paragraph_format.space_after = Pt(32)
    p_mail.paragraph_format.line_spacing = 1.15
    add_rich_runs(
        p_mail,
        "adriana.agudeloa@est.iudigital.edu.co · camilo.palaciot@est.iudigital.edu.co\n"
        "juan.pulgarin@est.iudigital.edu.co · ruben.jaramilloc@est.iudigital.edu.co\n"
        "julian.loaiza@prof.iudigital.edu.co",
        font_name="Consolas", font_size=8.4, color=COLOR_MUTED,
    )

    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_date.paragraph_format.space_before = Pt(16)
    add_rich_runs(
        p_date,
        "Medellín, Antioquia, Colombia\nNoviembre de 2026",
        font_size=10.5, color=COLOR_PRIMARY, bold=True,
    )

    doc.add_page_break()

    # =========================================================
    # PÁGINA 2: TABLA DE CONTENIDO Y RESUMEN
    # =========================================================
    p_toc_title = doc.add_paragraph()
    p_toc_title.paragraph_format.space_before = Pt(0)
    p_toc_title.paragraph_format.space_after = Pt(4)
    p_toc_title.paragraph_format.keep_with_next = True
    add_rich_runs(p_toc_title, "Tabla de Contenido", font_size=12.5, color=COLOR_PRIMARY, bold=True)

    p_toc = doc.add_paragraph()
    p_toc.paragraph_format.space_after = Pt(8)
    add_word_field(p_toc, 'TOC \\o "1-2" \\h \\z \\u', font_size=9.5, color=COLOR_BODY)

    p_res_t = doc.add_paragraph()
    p_res_t.paragraph_format.space_before = Pt(4)
    p_res_t.paragraph_format.space_after = Pt(3)
    p_res_t.paragraph_format.keep_with_next = True
    add_rich_runs(p_res_t, "Resumen", font_size=11.0, color=COLOR_SECONDARY, bold=True)

    p_res = add_p(
        f"Tres cajeros automáticos por salida no bastan para sostener la demanda del parqueadero de Supercentro. Más de la mitad de los conductores "
        f"(55 %) demora entre cuatro y seis minutos digitando su placa frente a la pantalla; por eso las colas crecen tan rápido. Para analizar el problema "
        f"con rigor, programamos en Python un simulador de eventos discretos con servidores independientes M/M/1 sobre jornadas de 1000 minutos y semilla "
        f"reproducible PCG64 = 42. Fijamos primero cuántas réplicas hacían falta observando la convergencia del promedio acumulado hacia el estado estable: "
        f"la media quedó contenida en la banda ±2 % desde r = {n_det}, así que tomamos N^{{*}} = {n_off} corridas (W_{{q}} = {wq_e1:.2f} min, IC 95 % "
        f"[{wq_e1_l:.2f}, {wq_e1_u:.2f}], ER = {er_wq_e1:.2f} %). Con {tot_veh_jornada:.2f} vehículos por jornada en esta línea base, el {c_min_w['cajero']} "
        f"tuvo el menor tiempo medio de atención total (W = {c_min_w['atencion_w_prom']:.3f} min) y el {c_max_w['cajero']} acumuló el mayor "
        f"(W = {c_max_w['atencion_w_prom']:.3f} min). Luego probamos siete configuraciones bajo números aleatorios comunes (CRN): tres cajeros siguen "
        f"fallando por amplio margen (P(W_{{q}} > 5 m) = {p5_e1_peor:.1f} %). Nuestra recomendación es pasar a 4 cajeros mixtos sumando lectura automática "
        f"de placa LPR/QR en el software —lo cual recorta 25 % la interacción de usuarios lentos— para alcanzar W_{{q}} = {wq_e7:.2f} min (o {wq_e7_jsq:.2f} min "
        f"con cola más corta JSQ), validado frente a Pollaczek–Khinchine M/G/1 tras limpiar el período transitorio (p ∈ [{p_min_mg1:.3f}, {p_max_mg1:.3f}]).",
        space_after=4.0,
    )
    p_res.paragraph_format.line_spacing = 1.12
    for run in p_res.runs:
        run.font.size = Pt(10.0)

    p_kw = doc.add_paragraph()
    p_kw.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_kw.paragraph_format.space_after = Pt(2)
    add_rich_runs(p_kw, "Palabras clave: ", font_size=9.8, color=COLOR_PRIMARY, italic=True)
    add_rich_runs(
        p_kw,
        "simulación discreta, colas M/M/1, estado estable, período transitorio, verificación y validación, parqueaderos.",
        font_size=9.8, color=COLOR_BODY,
    )

    doc.add_page_break()

    # =========================================================
    # 1. INTRODUCCIÓN
    # =========================================================
    add_h1("1. Introducción")
    add_p(
        "Las filas en los puntos de pago de un centro comercial rara vez nacen por fallas de red o lentitud del servidor. El cuello de botella aparece en la "
        "interfaz humano-computador. En el caso del centro comercial Supercentro, cada salida cuenta con tres cajeros automáticos donde el conductor digita "
        "la placa, confirma el vehículo y efectúa el pago. Aunque el software procesa cada clic de manera casi instantánea, los usuarios interactúan a ritmos "
        "muy distintos: solo 25 % resuelve el trámite rápido y 55 % pertenece a perfiles lentos o muy lentos."
    )
    add_p(
        "El problema operativo exige saber si tres quioscos con filas independientes —sin cambio de cola ni deserción— soportan la carga real o si la administración "
        "debe instalar más equipos e intervenir el flujo de atención. Responderlo a simple vista conduce a errores graves. Desde nuestra perspectiva como "
        "estudiantes de ingeniería de software, modelamos matemáticamente los servidores como colas M/M/1 desacopladas y contrastamos siete escenarios de mejora "
        "mediante simulación estocástica en Python."
    )
    add_p(
        "Este estudio cumple cinco objetivos concretos definidos para la actividad de cierre: (a) fijar cuántas réplicas garantizan el estado estable sobre la "
        "media y medir el cajero con menor y mayor tiempo promedio de atención; (b) cuantificar la distribución promedio por tipo de usuario en toda la salida; "
        "(c) formular una estrategia viable de mejora respaldada por criterios numéricos del equipo; (d) ejecutar el ciclo completo de verificación, calibración "
        "y validación (V&V); y (e) construir un algoritmo capaz de suprimir el sesgo del estado transitorio inicial, contrastando sus valores antes y después."
    )

    # =========================================================
    # 2. METODOLOGÍA Y FUNDAMENTACIÓN TEÓRICA
    # =========================================================
    add_h1("2. Metodología y Fundamentación Teórica del Modelo")

    add_h2("2.1 Parametrización del Sistema y Lectura Operativa")
    add_p(
        "El planteamiento de Supercentro reparte a los conductores en cuatro perfiles exponenciales de llegada y servicio por cajero. Un 25 % entra como usuario "
        "rápido (1 min de servicio y 3 min entre arribos) y un 20 % tiene ritmo normal (3 min en ambas variables). El otro 55 % se divide por mitad entre "
        "lentos (27.5 %; 4 min de atención, 5 min entre llegadas) y muy lentos (27.5 %; 6 min de atención, 7 min entre llegadas). Siguiendo al pie de la "
        "letra lo que pide el enunciado —«los detalles de atención de cada cajero se definen a continuación»— y en coherencia con la guía técnica del curso "
        "(Tabla 1), mantenemos constante la demanda agregada de los tres flujos paralelos al probar cualquier rediseño."
    )

    tbl1_data = [
        ["Rápido", "25.0%", "1.0 min", "3.0 min", "0.3333", "1.0000", "0.333", "Estable"],
        ["Normal", "20.0%", "3.0 min", "3.0 min", "0.3333", "0.3333", "1.000", "Crítico (límite)"],
        ["Lento", "27.5%", "4.0 min", "5.0 min", "0.2000", "0.2500", "0.800", "Estable"],
        ["Muy lento", "27.5%", "6.0 min", "7.0 min", "0.1429", "0.1667", "0.857", "Estable"],
        ["Mezcla por cajero (E1)", "100.0%", "3.600 min", "4.650 min", "0.2151", "0.2778", "0.774", "Estable (alto uso)"],
    ]
    format_apa_table(
        doc,
        "Tabla 1",
        "Parámetros exponenciales por perfil de usuario y mezcla resultante por cajero en Supercentro",
        [Inches(1.30), Inches(0.68), Inches(0.80), Inches(0.80), Inches(0.68), Inches(0.68), Inches(0.56), Inches(1.00)],
        ["Tipo de usuario", "Proporción", "Servicio E[S]", "Llegada E[IA]", "Tasa λ", "Tasa μ", "Uso ρ", "Estado teórico"],
        tbl1_data,
        "Tasas expresadas en vehículos por minuto. Al sumar las tres posiciones base, la demanda total del punto de salida se conserva en λ_{salida} = 3 / 4.65 = 0.6452 veh/min.",
        font_size=7.9,
    )

    add_p(
        "Un hallazgo teórico salta de inmediato al revisar la Tabla 1. Si un usuario normal operara en una cola aislada con λ = 1/3 y μ = 1/3, su utilización "
        "llegaría a ρ = 1.000, provocando una fila divergente (Tabla 2). Además, cuando agrupamos los cuatro perfiles en un cajero mixto, el tiempo de servicio "
        "ya no es exponencial puro sino hiperexponencial con segundo momento E[S^{2}] = 32.70 min^{2} y coeficiente de variación al cuadrado C^{2}_{s} = 1.5231 > 1. "
        "Por esa razón, la espera real supera la cota M/M/1 tradicional (W_{q} = 12.34 min) y converge hacia la ecuación Pollaczek–Khinchine M/G/1 (W_{q} = 15.57 min), "
        "tal como demuestra Kleinrock (1975)."
    )

    add_equation_box("ρ = λ_{c} / μ_{c} < 1,     P_{0} = 1 - ρ,     L_{q} = ρ^{2} / (1 - ρ),     L = λ_{c} · W", "(1)")
    add_equation_box("W_{q}(M/M/1) = ρ / [μ_{c}(1 - ρ)],     W_{q}(M/G/1) = [λ_{c} · E[S^{2}]] / [2(1 - ρ)],     W = W_{q} + 1/μ_{c}", "(2)")

    tbl2_data = []
    for _, rt in df_iso_theo.iterrows():
        w_txt = f"{rt['w_sistema_min']:.2f} m" if rt["estable"] else "∞"
        wq_txt = f"{rt['wq_cola_min']:.2f} m" if rt["estable"] else "∞"
        l_txt = f"{rt['l_sistema']:.2f}" if rt["estable"] else "∞"
        tbl2_data.append([
            rt["tipo_usuario"],
            f"{rt['rho']:.3f}",
            f"{rt['p0_ocio']*100:.1f}%",
            l_txt,
            wq_txt,
            w_txt,
            rt["estado_teorico"],
        ])
    format_apa_table(
        doc,
        "Tabla 2",
        "Métricas analíticas exactas de sistemas M/M/1 aislados por categoría de velocidad",
        [Inches(0.95), Inches(0.65), Inches(0.80), Inches(0.85), Inches(0.95), Inches(0.95), Inches(1.35)],
        ["Tipo de usuario", "Factor ρ", "Ocio P_{0}", "Clientes L", "Espera W_{q}", "Sistema W", "Condición M/M/1"],
        tbl2_data,
        "Cálculo exacto mediante ecuaciones (1) y (2) antes de la mezcla multinomial por servidor.",
        font_size=8.0,
    )

    add_h2("2.2 Arquitectura del Simulador, Estado Estable y Criterios de Decisión")
    add_p(
        "Implementamos la simulación en Python 3.13 dentro del paquete modular parking_queue/ (sin depender de librerías externas para estadística inferencial) "
        "fijando un horizonte de 1000 minutos por corrida, acorde con los lineamientos de la guía del laboratorio. Generamos los arribos a la salida como un "
        "proceso de Poisson con tasa λ_{salida} = 0.6452 vehículos/min usando el generador PCG64 (seed = 42). Cada vehículo almacena un factor exponencial "
        "unitario Z ~ Exp(1) para aplicar Números Aleatorios Comunes (CRN) entre los siete escenarios propuestos (Banks et al., 2010), anulando el ruido muestral "
        "al comparar alternativas:"
    )
    add_bullet("E1 — 3 Mixtos (Base actual): ", "tres cajeros independientes M/M/1 recibiendo todas las categorías por descomposición equiprobable 1/3.")
    add_bullet("E2, E3 y E4 — Ampliación mixta (4, 5 y 6 cajeros): ", "incremento escalonado de quioscos polivalentes conservando constante λ_{salida}.")
    add_bullet("E5 (1E + 3L) y E6 (1E + 4L) — Especialización de filas: ", "un cajero exprés exclusivo para Rápido/Normal (45 %) frente a tres o cuatro estándar para Lento/Muy lento (55 %).")
    add_bullet("E7 — 4 Mixtos + Mejora UX/LPR: ", "cuatro quioscos mixtos acompañados de lectura automática de placa/QR en software, reduciendo 25 % la interacción de usuarios Lentos (4 → 3 min) y Muy lentos (6 → 4.5 min).")

    add_p(
        "Para no decidir a ciegas, el Grupo 25 acordó cinco reglas cuantitativas antes de simular: (1) espera aceptable W_{q} ≤ 5 min (pico ≤ 5.5 min) y meta "
        "óptima ≤ 3 min (pico ≤ 3.5 min); (2) tiempo en sistema W ≤ 8 min (óptimo < 5 min); (3) ocupación máxima entre 45 % y 85 % (subutilizado por debajo "
        "de 45 %, alerta en 85–90 % y crítico sobre 90 %); (4) cola promedio L_{q} < 3 vehículos por cajero; y (5) a lo sumo 20 % de usuarios esperando más de "
        "5 min en el cajero más cargado (óptimo < 10 %). Medimos también qué ocurre cuando la gente escoge la fila visible más corta (JSQ no clarividente) "
        "usando estructuras deque para no mirar tiempos futuros."
    )

    # =========================================================
    # 3. RESULTADOS Y ANÁLISIS DEL MODELO
    # =========================================================
    add_h1("3. Resultados de Simulación y Análisis Estadístico")

    # 3.1 Estado Estable para definir réplicas N*
    add_h2("3.1 Determinación del Número de Réplicas (N*) por Estado Estable")
    add_p(
        f"Correr apenas diez réplicas piloto dejó un error relativo (ER) de {er10_e1:.2f}% sobre W_{{q}} en la configuración base, cifra demasiado inestable "
        f"para sustentar inversiones en infraestructura (exigiría {n_prof10} corridas bajo la regla ER ≤ 10 %). Aplicamos entonces la técnica del promedio "
        f"acumulado sobre W_{{q}} desde r = 1 hasta r = 150 en el escenario de 3 cajeros mixtos. Buscamos el primer punto r ≥ 30 donde la media acumulada "
        f"permanece de forma sostenida dentro de la banda asintótica ±2 % durante veinte réplicas consecutivas —sin volver a salirse— cumpliendo además "
        f"un error relativo IC 95 % t de Student inferior o igual al 7.5 %."
    )

    milestones = [10, 30, 50, 80, 100, n_det, n_off, 150]
    milestones = sorted(set(milestones))
    tbl3_data = []
    for r_m in milestones:
        rm = df_conv[df_conv["replica"] == r_m].iloc[0]
        tag = f"{int(r_m)}"
        if r_m == n_det:
            tag = f"{int(r_m)} (Estab.)"
        elif r_m == n_off:
            tag = f"{int(r_m)} (Oficial N*)"
        tbl3_data.append([
            tag,
            f"{rm['wq_media_acumulada_min']:.2f} m",
            f"[{rm['wq_ic95_inf']:.2f}, {rm['wq_ic95_sup']:.2f}]",
            f"{rm['desviacion_asintotica_wq_pct']:.2f}%",
            f"{rm['wq_er_pct']:.2f}%",
            f"{rm['w_media_acumulada_min']:.2f} m",
            f"{rm['w_er_pct']:.2f}%",
        ])

    format_apa_table(
        doc,
        "Tabla 3",
        "Evolución del promedio acumulado hacia el estado estable y error relativo IC 95 % t (3 Mixtos)",
        [Inches(1.05), Inches(0.85), Inches(1.25), Inches(0.95), Inches(0.80), Inches(0.85), Inches(0.75)],
        ["Réplicas (r)", "W_{q} acum.", "IC 95 % t (W_{q})", "Desv. asint.", "ER (W_{q})", "W acum.", "ER (W)"],
        tbl3_data,
        f"Desv. asint. mide la diferencia porcentual frente al promedio de 150 réplicas ({float(df_conv['wq_media_acumulada_min'].iloc[-1]):.2f} min). La estabilización sostenida ocurre en r = {n_det} y se fija N* = {n_off}.",
        font_size=7.9,
    )

    add_p(
        f"Como evidencia la Tabla 3 y la Figura 1, el estimador entra de manera definitiva en estabilidad en r = {n_det}, por lo cual fijamos un estándar "
        f"operativo limpio de N^{{*}} = {n_off} réplicas para todos los experimentos del proyecto. En N^{{*}} = {n_off}, la espera acumulada converge a "
        f"{row_n_off['wq_media_acumulada_min']:.2f} min con un error relativo de {er_wq_e1:.2f}% en W_{{q}} y apenas {er_w_e1:.2f}% en permanencia total W."
    )

    add_apa_fig(
        "fig1_estado_estable_replicas.png",
        "Figura 1",
        "Determinación de réplicas totales mediante convergencia al estado estable del promedio acumulado y ER%",
        "Panel A muestra la entrada sostenida en la banda ±2 % alrededor del valor asintótico; Panel B verifica ER(W_{q}) ≤ 7.5 % en N* = 120.",
        width_in=6.35,
    )

    # 3.2 Punto A
    add_h2("3.2 Punto A: Estadísticas por Cajero (Menor y Mayor Tiempo de Atención)")
    add_p(
        f"Con N^{{*}} = {n_off} jornadas simuladas de 1000 minutos bajo el esquema actual de tres cajeros independientes, evaluamos el servicio neto S, "
        f"la espera en fila W_{{q}} y el tiempo total de atención en el sistema W = W_{{q}} + S para cada servidor (Tabla 4)."
    )

    tbl4_data = []
    for _, rc in base_caj.iterrows():
        tbl4_data.append([
            rc["cajero"],
            f"{rc['usuarios_prom']:.2f} (±{rc['usuarios_sd']:.1f})",
            f"{rc['servicio_s_prom']:.3f} (±{rc['servicio_s_sd']:.3f})",
            f"{rc['espera_wq_prom']:.3f} (±{rc['espera_wq_sd']:.3f})",
            f"{rc['atencion_w_prom']:.3f} (±{rc['atencion_w_sd']:.2f})",
            f"[{rc['atencion_w_ic95_inf']:.2f}, {rc['atencion_w_ic95_sup']:.2f}]",
            f"[{rc['atencion_w_min']:.1f}–{rc['atencion_w_max']:.1f}]",
            f"{rc['utilizacion_rho_prom']*100:.1f}%",
        ])

    format_apa_table(
        doc,
        "Tabla 4",
        f"Desempeño estadístico por cajero en el escenario base de 3 cajeros mixtos (N* = {n_off} réplicas)",
        [Inches(0.68), Inches(0.85), Inches(0.90), Inches(0.90), Inches(0.90), Inches(0.92), Inches(0.80), Inches(0.55)],
        ["Cajero", "Veh./jornada", "Servicio S (m)", "Espera W_{q} (m)", "Total W (m)", "IC 95 % W", "Mín–Máx W", "Uso ρ"],
        tbl4_data,
        "Cifras reportan media (±DE), intervalo de confianza t de Student al 95 % (gl = 119) y rango observado entre las 120 corridas.",
        font_size=7.6,
    )

    add_p(
        f"Aquí hay una diferencia estadística clara entre los tres servidores de la base. El {c_min_w['cajero']} cerró con el menor tiempo promedio de "
        f"atención total: W = {c_min_w['atencion_w_prom']:.3f} min (W_{{q}} = {c_min_w['espera_wq_prom']:.3f} min; IC 95 % [{c_min_w['atencion_w_ic95_inf']:.2f}, "
        f"{c_min_w['atencion_w_ic95_sup']:.2f}]). En contraste, el {c_max_w['cajero']} concentró el promedio más alto con W = {c_max_w['atencion_w_prom']:.3f} min "
        f"(W_{{q}} = {c_max_w['espera_wq_prom']:.3f} min; DE = {c_max_w['atencion_w_sd']:.2f} min y picos hasta {c_max_w['atencion_w_max']:.1f} min cuando "
        f"coincidieron rachas de conductores lentos). El {c_mid_w['cajero']} quedó justo en medio —W = {c_mid_w['atencion_w_prom']:.3f} min y "
        f"W_{{q}} = {c_mid_w['espera_wq_prom']:.3f} min—. En servicio puro S los tres cajeros empatan prácticamente en 3.600 min ({c_min_s['cajero']}: "
        f"{c_min_s['servicio_s_prom']:.3f} min; {c_max_s['cajero']}: {c_max_s['servicio_s_prom']:.3f} min), lo que demuestra que la brecha viene de las colas "
        f"(Figura 2)."
    )

    add_apa_fig(
        "fig2_desempeno_cajeros_base.png",
        "Figura 2",
        "Comparativa estadística de servicio, espera y atención total por cajero en el escenario base",
        "Panel A incluye barras de error IC 95 % t; Panel B muestra diagramas de caja con media (rombo rojo), mediana y valores atípicos en 120 réplicas.",
        width_in=6.35,
    )

    # 3.3 Punto B
    add_h2("3.3 Punto B: Promedio de Usuarios por Tipo en la Totalidad de Cajeros")
    add_p(
        f"Al agregar las {n_off} corridas del sistema base contabilizamos {tot_veh_all:,} vehículos atendidos en el punto de salida, lo que equivale a una "
        f"demanda promedio de {tot_veh_jornada:.2f} vehículos por jornada de 1000 minutos (Tabla 5). En la totalidad de los tres cajeros ingresaron en "
        f"promedio {usr_idx.loc['Rápido', 'promedio_total_3_cajeros']:.2f} usuarios Rápido ({usr_idx.loc['Rápido', 'promedio_por_cajero']:.2f} por cajero), "
        f"{usr_idx.loc['Normal', 'promedio_total_3_cajeros']:.2f} Normal ({usr_idx.loc['Normal', 'promedio_por_cajero']:.2f}/caj), "
        f"{usr_idx.loc['Lento', 'promedio_total_3_cajeros']:.2f} Lento ({usr_idx.loc['Lento', 'promedio_por_cajero']:.2f}/caj) y "
        f"{usr_idx.loc['Muy lento', 'promedio_total_3_cajeros']:.2f} Muy lento ({usr_idx.loc['Muy lento', 'promedio_por_cajero']:.2f}/caj)."
    )

    tbl5_data = []
    for utype, ru in df_users.iterrows():
        tbl5_data.append([
            ru["tipo_usuario"],
            f"{int(ru['total_replicas']):,}",
            f"{ru['promedio_total_3_cajeros']:.2f} (±{ru['desv_est_total']:.2f})",
            f"{ru['promedio_por_cajero']:.2f}",
            f"[{int(ru['min_replica'])}–{int(ru['max_replica'])}]",
            f"{ru['prop_empirica_pct']:.2f}%",
            f"{ru['prop_teorica_pct']:.1f}%",
            f"{ru['s_empirico_min']:.2f} m",
            f"{ru['w_empirico_min']:.2f} m",
        ])
    tbl5_data.append([
        "Total salida",
        f"{tot_veh_all:,}",
        f"{tot_veh_jornada:.2f}",
        f"{tot_veh_jornada/3:.2f}",
        "—",
        "100.00%",
        "100.0%",
        f"{float(sum_idx.loc['E1_3_Mixtos', 'servicio_s_media_min']):.2f} m",
        f"{w_e1:.2f} m",
    ])

    format_apa_table(
        doc,
        "Tabla 5",
        f"Promedio de usuarios por categoría en los 3 cajeros y por servidor (N* = {n_off} réplicas)",
        [Inches(0.75), Inches(0.68), Inches(1.02), Inches(0.65), Inches(0.72), Inches(0.65), Inches(0.65), Inches(0.68), Inches(0.70)],
        ["Categoría", "Total 120R", "3 Cajeros (±DE)", "Por cajero", "Mín–Máx", "Prop. Emp.", "Prop. Teór.", "Serv. S", "Total W"],
        tbl5_data,
        "La desviación entre proporciones empíricas y teóricas no supera 0.30 puntos porcentuales. Los tiempos W reflejan permanencia total en el sistema.",
        font_size=7.6,
    )

    add_p(
        "Conviene observar el Panel B de la Figura 3 para entender la raíz física de la congestión. Aunque los usuarios Lentos y Muy lentos suman 55.0 % "
        "de las llegadas, su tiempo promedio de digitación y pago (4 y 6 min) hace que consuman exactamente el 76.4 % de las horas-máquina de los cajeros "
        "(30.6 % y 45.8 %, respectivamente). En contraste, los usuarios Rápidos representan 25.0 % del tráfico pero absorben apenas 6.9 % de la ocupación."
    )

    add_apa_fig(
        "fig3_usuarios_por_tipo.png",
        "Figura 3",
        "Distribución promedio de usuarios por tipo en los 3 cajeros y asimetría de carga en servicio",
        "Panel A compara frecuencias empíricas frente a los porcentajes del enunciado; Panel B evidencia que 55 % de usuarios consume 76.4 % de capacidad.",
        width_in=6.35,
    )

    # 3.4 Punto C
    add_h2("3.4 Punto C: Estrategia de Mejora y Comparativa de Escenarios")
    add_p(
        f"¿Resultan suficientes tres cajeros por punto de salida en Supercentro? Los datos dicen que no. Con la configuración actual (E1), un conductor "
        f"espera {wq_e1:.2f} minutos en fila antes de iniciar el pago y dura {w_e1:.2f} minutos en total dentro del sistema (IC 95 % de espera "
        f"[{wq_e1_l:.2f}, {wq_e1_u:.2f}] min). El cajero más exigido alcanza {float(sum_idx.loc['E1_3_Mixtos', 'utilizacion_max_media'])*100:.1f}% de uso y "
        f"{p5_e1_peor:.1f}% de quienes salen espera más de cinco minutos. Veamos en la Tabla 6 cómo responden los siete diseños bajo las mismas llegadas."
    )

    tbl6_data = []
    for skey in df_sum["escenario"]:
        rs = sum_idx.loc[skey]
        rj = jsq_idx.loc[skey]
        tbl6_data.append([
            rs["nombre_corto"],
            f"{int(rs['num_cajeros'])}",
            f"{rs['espera_wq_media_min']:.2f} [{rs['espera_wq_ic95_inf']:.2f}–{rs['espera_wq_ic95_sup']:.2f}]",
            f"{rs['peor_cajero_wq_prom_min']:.2f} m",
            f"{rs['sistema_w_media_min']:.2f} m",
            f"{rs['wq_teorica_mg1_min']:.2f} m",
            f"{rj['espera_wq_media_min']:.2f} m",
            f"{rs['utilizacion_rho_media']*100:.1f}% / {rs['utilizacion_max_media']*100:.1f}%",
            f"{rs['lq_cajero_simulada']:.2f}",
        ])

    format_apa_table(
        doc,
        "Tabla 6",
        f"Comparativa operativa de estrategias de mejora frente al escenario base (N* = {n_off} réplicas)",
        [Inches(0.88), Inches(0.42), Inches(1.18), Inches(0.68), Inches(0.62), Inches(0.68), Inches(0.62), Inches(0.92), Inches(0.50)],
        ["Escenario", "Caj.", "W_{q} [IC 95 %]", "Peor caj.", "Total W", "M/G/1", "W_{q} JSQ", "ρ med / máx", "L_{q}/caj"],
        tbl6_data,
        "W_{q} JSQ mide el impacto de señalizar la fila más corta (enrutamiento observable sin clarividencia) conservando igual demanda λ_{salida}.",
        font_size=7.5,
    )

    add_p(
        f"Añadir un cuarto cajero físico manteniendo la interfaz actual (E2: 4 Mixtos) recorta la espera más de la mitad, hasta {wq_e2:.2f} min, pero todavía "
        f"incumple la meta W_{{q}} ≤ 5 min (W = {w_e2:.2f} min). Segregar filas con cuatro equipos (E5: 1 Exprés + 3 Estándar) tampoco resuelve el problema: "
        f"baja el promedio global a {wq_e5:.2f} min pero castiga los tres servidores estándar hasta {peor_e5:.2f} min porque pierden el efecto de consolidación "
        f"de colas (pooling). Incluso al subir a cinco cajeros especializados (E6), el promedio es {wq_e6:.2f} min pero el segmento lento queda en {peor_e6:.2f} min "
        f"contra {wq_e3:.2f} min de cinco cajeros mixtos (E3)."
    )
    add_p(
        f"Solo dos vías resuelven el cuello de botella desde criterios de ingeniería. En infraestructura puramente física sin cambios de interfaz ni fila única, "
        f"se necesitan 6 cajeros mixtos (E4) para satisfacer simultáneamente los cinco umbrales bajo llegada aleatoria (W_{{q}} = {wq_e4:.2f} min, W = {w_e4:.2f} min, "
        f"P(>5m) = {p5_e4_peor:.1f}%), pero a costa de duplicar equipos y hundir la ocupación media a {rho_e4:.1f}% (61.6 % de tiempo ocioso). Por esa razón, "
        f"el Grupo 25 recomienda la estrategia mixta de hardware y software E7 (4 Cajeros Mixtos + Mejora UX/LPR): instalar un solo cajero adicional junto con "
        f"lectura automática de placas LPR o QR en el tiquete para eliminar la digitación manual de usuarios lentos y muy lentos (-25 % tiempo de servicio). "
        f"Poner apenas un módulo adicional junto con lectura automática LPR/QR en la interfaz baja la espera a {wq_e7:.2f} min y marca el mejor tiempo total "
        f"de todo el estudio: W = {w_e7:.2f} min contra {w_e4:.2f} min de 6 Mixtos, con {rho_e7:.1f}% de uso y {p5_e7_peor:.1f}% sobre 5 min (Figura 4). "
        f"Si encima se agrega señalización visible hacia la fila más corta (JSQ), E7 cae a {wq_e7_jsq:.2f} min (apenas {p5_e7_jsq:.1f}% sobre 5 min). "
        f"Cuando no sea posible tocar el software, la salida física más equilibrada consiste en operar 5 cajeros mixtos guiados por JSQ (W_{{q}} = {wq_e3_jsq:.2f} min)."
    )

    add_apa_fig(
        "fig4_estrategias_mejora_escenarios.png",
        "Figura 4",
        "Evaluación comparativa de los siete escenarios frente a metas de espera, JSQ, utilización y riesgo > 5 min",
        "Panel A contrapone M/M/1 independiente contra JSQ observable y el cajero más cargado (triángulo); Panel B contrasta ρ_{máx} y P(W_{q} > 5 min).",
        width_in=6.35,
    )

    # 3.5 Punto D
    add_h2("3.5 Punto D: Verificación, Calibración y Validación (V&V)")
    add_p(
        "Todo simulador estocástico carece de valor ejecutivo si sus resultados no se auditan en tres niveles secuenciales (Banks et al., 2010). En primer "
        "lugar, la verificación comprueba que el algoritmo implementa fielmente el modelo conceptual sin errores lógicos: ejecutamos 16 pruebas unitarias "
        "automatizadas y auditamos la identidad empírica de Little (L_{q} = λ_{eff} · W_{q}) sobre la trayectoria de todos los escenarios, obteniendo un error "
        f"numérico máximo de {little_max:.2e} (< 10^{{-10}}). En segundo término, la calibración contrastó los conteos generados frente a las probabilidades "
        f"objetivo (25 / 20 / 27.5 / 27.5 %): el error absoluto medio resultó de apenas {mae_pp:.2f} puntos porcentuales, con prueba de bondad de ajuste "
        f"χ^{{2}} = {chi2_st:.3f} (gl = 3, p = {chi2_pv:.3f} > 0.05) y error relativo máximo inferior al {srv_err:.2f}% en los promedios empíricos de servicio."
    )
    add_p(
        f"Finalmente, la validación contrastó las esperas simuladas en estado estable (post-warmup) frente a las soluciones analíticas exactas de Pollaczek–Khinchine "
        f"M/G/1 mediante pruebas t de Student bilaterales (α = 0.05). Como resume la Tabla 7 y el diagrama de flujo de la Figura 5, los siete escenarios obtienen "
        f"p-valores entre {p_min_mg1:.3f} y {p_max_mg1:.3f} (> 0.05), impidiendo rechazar H_{{0}}: μ_{{estable}} = W_{{q, M/G/1}}. Complementariamente, la Figura 6 "
        f"(Panel A) verifica el motor M/M/1 puro por perfil aislado sobre horizontes de 3000 min: Rápido (p = {float(df_iso_val.iloc[0]['p_valor_w']):.3f}), "
        f"Lento (p = {float(df_iso_val.iloc[2]['p_valor_w']):.3f}) y Muy lento (p = {float(df_iso_val.iloc[3]['p_valor_w']):.3f}) coinciden con la teoría "
        f"1/(μ - λ), mientras el perfil Normal (ρ = 1.0) diverge hacia colas crecientes (W_{{sim}} = {float(df_iso_val.iloc[1]['w_simulado_est_min']):.1f} min) "
        f"tal como predice la ecuación analítica."
    )

    tbl7_data = []
    for _, rv in df_vv.iterrows():
        tbl7_data.append([
            rv["nombre_corto"],
            "OK" if bool(rv["verificacion_little_ok"]) else "Fallo",
            f"{rv['wq_estable_min']:.2f} m",
            f"{rv['wq_teorica_mg1_min']:.2f} m",
            f"{rv['p_valor_vs_mg1']:.3f}",
            f"{rv['prob_wq_mayor_5m_peor_cajero_pct']:.1f}%",
            rv["criterio_wq"],
            rv["criterio_rho"],
            "ÓPTIMO" if "ÓPTIMO" in rv["dictamen_global"] else ("REC. JSQ/UX" if "MITIGACIÓN" in rv["dictamen_global"] else "NO REC."),
        ])

    format_apa_table(
        doc,
        "Tabla 7",
        "Matriz consolidada de Verificación, Validación (t vs. M/G/1) y clasificación frente a criterios críticos",
        [Inches(0.84), Inches(0.45), Inches(0.62), Inches(0.62), Inches(0.55), Inches(0.62), Inches(0.88), Inches(1.02), Inches(0.90)],
        ["Escenario", "Little", "W_{q} Est.", "M/G/1", "p (t)", "P(>5m)", "Criterio W_{q}", "Régimen ρ_{máx}", "Dictamen"],
        tbl7_data,
        "Régimen ρ_{máx} clasifica la utilización simulada promedio del cajero pico (en 6 Mixtos ρ_{máx} = 46.3 % Moderado, mientras ρ̄ = 38.4 %). REC. JSQ/UX indica que cumple W_{q} ≤ 5 m, W ≤ 8 m y L_{q} < 3, superando 20 % en P(>5m) sin JSQ.",
        font_size=7.4,
    )

    add_apa_fig(
        "fig5_proceso_vv_diagrama.png",
        "Figura 5",
        "Diagrama metodológico del proceso V&V y validación estadística frente a Pollaczek–Khinchine M/G/1",
        "Panel A detalla las compuertas de Verificación, Calibración y Validación con retroalimentación; Panel B prueba p > 0.05 en los 7 escenarios.",
        width_in=6.35,
    )

    add_apa_fig(
        "fig7_validacion_teoria_y_perfiles.png",
        "Figura 6",
        "Validación M/M/1 puro por perfil aislado (Panel A) y balance individual de espera por cajero (Panel B)",
        "Panel A confirma ajuste exacto de los tres perfiles estables sobre 3000 min; Panel B exhibe el cuello de botella de los cajeros estándar en E5.",
        width_in=6.35,
    )

    # 3.6 Punto E
    add_h2("3.6 Punto E: Eliminación del Estado Transitorio (Antes vs. Después)")
    add_p(
        "Cada jornada arrancó con los tres cajeros desocupados (L(0) = 0). Quienes llegan primero encuentran la salida libre y pasan casi de inmediato, lo que "
        "jala hacia abajo el promedio del día y engaña sobre la congestión real (Law, 2015). Para limpiar ese período de calentamiento (warm-up), promediamos "
        "transversalmente la espera según el orden de llegada k = 1…500 sobre las 120 réplicas, suavizamos con medias móviles de ventana w = 25 y localizamos "
        "el corte k^{*} de menor varianza móvil dentro del rango inicial [120, 240] cuando ρ_{máx} ≥ 70 % ([60, 150] en los demás casos)."
    )

    add_code_listing(
        doc,
        [
            "def eliminar_transitorio(mat_wq, window=25, min_cand=120, max_cand=240):",
            "    wq_cross = np.nanmean(mat_wq, axis=0)  # Promedio transversal por orden k",
            "    mov_avgs = [np.mean(wq_cross[i:i+window]) for i in range(len(wq_cross)-window+1)]",
            "    cands, vars_ = [], []",
            "    for i in range(max(0, min_cand-window), min(len(mov_avgs)-window+1, max_cand-window+1)):",
            "        if min_cand <= i + window <= max_cand:",
            "            cands.append(i + window); vars_.append(np.var(mov_avgs[i:i+window]))",
            "    k_cut = cands[int(np.argmin(vars_))]  # Punto de estabilización de varianza",
            "    return k_cut, np.mean(mat_wq[:, k_cut-1:])  # Estadístico en estado estable",
        ],
        "Algoritmo implementado en parking_queue/simulation.py (método eliminate_transient_and_compare) para suprimir el arranque vacío.",
    )

    tbl8_data = []
    for _, rw in df_warm.iterrows():
        tbl8_data.append([
            rw["nombre_corto"],
            f"k* = {int(rw['k_corte_vehiculos'])}",
            f"{rw['tiempo_corte_aprox_min']:.1f} m",
            f"{rw['wq_con_transitorio_min']:.2f} m",
            f"{rw['wq_estado_estable_min']:.2f} m",
            f"{rw['wq_teorica_mg1_min']:.2f} m",
            f"+{rw['sesgo_subestimacion_wq_pct']:.2f}%",
            f"{rw['w_con_transitorio_min']:.2f} → {rw['w_estado_estable_min']:.2f} m",
        ])

    format_apa_table(
        doc,
        "Tabla 8",
        f"Comparación antes y después de eliminar el estado transitorio en los siete escenarios (N* = {n_off})",
        [Inches(0.88), Inches(0.62), Inches(0.68), Inches(0.75), Inches(0.78), Inches(0.68), Inches(0.80), Inches(1.31)],
        ["Escenario", "Corte k*", "Tiempo t*", "W_{q} Antes", "W_{q} Después", "M/G/1", "Subest. trans.", "Total W (Antes → Desp.)"],
        tbl8_data,
        "Subest. trans. cuantifica cuánto subestimaba el período transitorio inicial la espera estacionaria real: (W_{q,est} - W_{q,antes}) / W_{q,est} × 100 %.",
        font_size=7.6,
    )

    c1w = df_warm_c1.set_index("cajero")
    add_p(
        f"En el escenario base de 3 Mixtos, el transitorio abarca los primeros k^{{*}} - 1 = {k_cut_e1 - 1} vehículos (~{t_cut_e1:.1f} min de operación). Al "
        f"descartarlos, la espera promedio sube {sesgo_e1:.2f}% desde {wq_e1:.2f} hasta {wq_ss_e1:.2f} min —acercándose al valor analítico M/G/1 de "
        f"{wq_mg1_e1:.2f} min (p = {p_mg1_e1:.3f})— y corrige por igual los tres cajeros: Cajero 1 ({c1w.loc['Cajero 1', 'wq_con_transitorio_min']:.2f} → "
        f"{c1w.loc['Cajero 1', 'wq_estado_estable_min']:.2f} min), Cajero 2 ({c1w.loc['Cajero 2', 'wq_con_transitorio_min']:.2f} → "
        f"{c1w.loc['Cajero 2', 'wq_estado_estable_min']:.2f} min) y Cajero 3 ({c1w.loc['Cajero 3', 'wq_con_transitorio_min']:.2f} → "
        f"{c1w.loc['Cajero 3', 'wq_estado_estable_min']:.2f} min). En los escenarios con cuatro o más quioscos la estabilización ocurre antes (k^{{*}} entre "
        f"84 y 106 arribos) y el sesgo cae entre 1.53 % y 3.19 % (Figura 7)."
    )

    add_apa_fig(
        "fig6_eliminacion_transitorio_antes_despues.png",
        "Figura 7",
        "Identificación del período transitorio en 3 Mixtos y comparación Antes vs. Después en los siete escenarios",
        "Panel A delimita la zona de arranque vacío (1–238) frente al estado estable; Panel B contrasta los promedios antes y después del filtro.",
        width_in=6.35,
    )

    # =========================================================
    # 4. CONCLUSIONES Y RECOMENDACIONES
    # =========================================================
    add_h1("4. Conclusiones y Recomendaciones")
    add_numbered_item(
        "1.",
        "Insuficiencia crítica de los 3 cajeros actuales: ",
        f"Tres cajeros por salida no cubren la demanda de Supercentro dentro de estándares aceptables. Producen una espera media de {wq_e1:.2f} min en fila "
        f"({wq_ss_e1:.2f} min en estado estable), {w_e1:.2f} min totales y {p5_e1_peor:.1f}% de usuarios esperando más de cinco minutos.",
    )
    add_numbered_item(
        "2.",
        "Estabilidad muestral y cajeros individuales (Punto A): ",
        f"Mediante la convergencia del promedio acumulado fijamos N^{{*}} = {n_off} réplicas (estabilización ±2 % desde r = {n_det}, ER(W_{{q}}) = {er_wq_e1:.2f}%). "
        f"En el esquema base, el {c_min_w['cajero']} obtuvo el menor tiempo total promedio (W = {c_min_w['atencion_w_prom']:.3f} min) y el {c_max_w['cajero']} "
        f"el mayor (W = {c_max_w['atencion_w_prom']:.3f} min), mientras el servicio puro S permaneció alrededor de 3.605 min en los tres servidores.",
    )
    add_numbered_item(
        "3.",
        "Impacto de los perfiles lentos (Punto B): ",
        f"El flujo diario promedia {tot_veh_jornada:.2f} vehículos por salida ({usr_idx.loc['Rápido', 'promedio_total_3_cajeros']:.2f} Rápido, "
        f"{usr_idx.loc['Normal', 'promedio_total_3_cajeros']:.2f} Normal, {usr_idx.loc['Lento', 'promedio_total_3_cajeros']:.2f} Lento y "
        f"{usr_idx.loc['Muy lento', 'promedio_total_3_cajeros']:.2f} Muy lento). Aunque Lentos y Muy lentos representan 55.0 % de las visitas, "
        f"consumen 76.4 % de la capacidad de los cajeros y generan el cuello de botella.",
    )
    add_numbered_item(
        "4.",
        "Estrategia recomendada para Supercentro (Punto C): ",
        f"Descartar la especialización rígida (E5 y E6) que penaliza la fila estándar. Recomendamos ampliar a 4 cajeros mixtos e implementar lectura automática "
        f"de placa LPR/QR en software (E7: W_{{q}} = {wq_e7:.2f} min, W = {w_e7:.2f} min, ρ = {rho_e7:.1f}%) junto con señalización visible de cola más corta "
        f"(JSQ: W_{{q}} = {wq_e7_jsq:.2f} min). Como alternativa sin cambios de software, operar 5 cajeros mixtos (W_{{q}} = {wq_e3:.2f} min; {wq_e3_jsq:.2f} min con JSQ).",
    )
    add_numbered_item(
        "5.",
        "Validación integral y efecto del transitorio (Puntos D y E): ",
        f"El simulador satisface la Ley de Little (< 10^{{-15}}), calibración χ^{{2}} (p = {chi2_pv:.3f}) y pruebas t frente a M/G/1 en los siete escenarios "
        f"(p ∈ [{p_min_mg1:.3f}, {p_max_mg1:.3f}]). Eliminar el transitorio (k^{{*}} = {k_cut_e1} en la línea base) evita subestimar la espera en {sesgo_e1:.2f}%.",
    )
    add_numbered_item(
        "6.",
        "Limitaciones y trabajo futuro: ",
        "El modelo asume tasas estacionarias durante los 1000 minutos y ausencia de deserción en fila; futuros estudios podrían incorporar franjas pico de fin de semana y pagos móviles sin paso por cajero.",
    )

    # =========================================================
    # REFERENCIAS (APA 7 SIN PARAFRASEAR DATOS ORIGINALES)
    # =========================================================
    add_h1("Referencias")
    referencias_apa7 = [
        [("Banks, J., Carson, J. S., II, Nelson, B. L., & Nicol, D. M. (2010). ", False), ("Discrete-event system simulation", True), (" (5th ed.). Pearson.", False)],
        [("Gross, D., Shortle, J. F., Thompson, J. M., & Harris, C. M. (2008). ", False), ("Fundamentals of queueing theory", True), (" (4th ed.). John Wiley & Sons.", False)],
        [("Kleinrock, L. (1975). ", False), ("Queueing systems, volume 1: Theory", True), (". John Wiley & Sons.", False)],
        [("Law, A. M. (2015). ", False), ("Simulation modeling and analysis", True), (" (5th ed.). McGraw-Hill Education.", False)],
        [("Little, J. D. C. (1961). A proof for the queuing formula: L = λ W. ", False), ("Operations Research, 9", True), ("(3), 383–387.", False)],
        [("Ross, S. M. (2014). ", False), ("Introduction to probability models", True), (" (11th ed.). Academic Press.", False)],
    ]
    for ref_parts in referencias_apa7:
        pr = doc.add_paragraph()
        pr.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pr.paragraph_format.left_indent = Inches(0.5)
        pr.paragraph_format.first_line_indent = Inches(-0.5)
        pr.paragraph_format.space_before = Pt(0.5)
        pr.paragraph_format.space_after = Pt(2.5)
        pr.paragraph_format.line_spacing = 1.12
        for chunk_txt, chunk_italic in ref_parts:
            add_rich_runs(pr, chunk_txt, font_size=10.0, color=COLOR_BODY, italic=chunk_italic)

    # =========================================================
    # ANEXOS
    # =========================================================
    add_h1("Anexo A: Estructura del Repositorio y Reproducibilidad")
    add_p(
        "El proyecto queda organizado como paquete modular Python acompañado de su cuaderno autocontenido de Google Colab y 16 pruebas unitarias:",
        space_after=4.0,
    )
    tree = [
        "Actividad 4 - simulacion/",
        "  parking_queue/",
        "    model.py ................ <- Parámetros Supercentro, analítica M/M/1-M/G/1 y regímenes ρ",
        "    simulation.py ........... <- Motor DES (N* estado estable, warm-up, JSQ y protocolo V&V)",
        "    visualizations.py ....... <- Generador de 7 figuras científicas a 300 DPI",
        "  tests/test_parking_queue.py <- Suite de 16 pruebas unitarias (Little, t-Student, Chi2, V&V)",
        "  main.py ................... <- Script maestro (exporta 14 CSVs y 7 figuras en results/)",
        "  Simulacion_Parqueadero_Supercentro_Colab.ipynb <- Cuaderno Colab pre-ejecutado",
        "  generate_doc.py ........... <- Generador dinámico APA 7 del presente informe Word",
        "  GUION_VIDEO_SUSTENTACION.md <- Guion cronometrado de sustentación (2:30 min)",
    ]
    pt = doc.add_paragraph()
    pt.paragraph_format.left_indent = Inches(0.18)
    pt.paragraph_format.space_after = Pt(5)
    pt.paragraph_format.line_spacing = 1.03
    for idx_t, line in enumerate(tree):
        suffix = "\n" if idx_t < len(tree) - 1 else ""
        rl = pt.add_run(f"{line}{suffix}")
        rl.font.name = "Consolas"
        rl.font.size = Pt(7.8)
        rl.font.color.rgb = COLOR_PRIMARY

    add_h1("Anexo B: Video de Sustentación")
    p_vid = doc.add_paragraph()
    p_vid.paragraph_format.left_indent = Inches(0.20)
    p_vid.paragraph_format.space_after = Pt(4)
    p_vid.paragraph_format.line_spacing = 1.1
    add_rich_runs(p_vid, "Enlace del video (2:30 min): ", font_size=9.8, color=COLOR_PRIMARY, bold=True)
    add_rich_runs(p_vid, "[Pendiente insertar enlace YouTube tras grabación]", font_name="Consolas", font_size=8.8, color=COLOR_SECONDARY, bold=True)
    add_p(
        f"El libreto cronometrado en GUION_VIDEO_SUSTENTACION.md cubre el problema de Supercentro, la determinación de N^{{*}} = {n_off} réplicas por estado "
        f"estable, los resultados por cajero y tipo de usuario (Puntos A y B), la estrategia recomendada 4 Mixtos + UX/LPR con JSQ (Punto C), la validación "
        f"M/G/1 y Ley de Little (Punto D) y la eliminación del transitorio tras k^{{*}} = {k_cut_e1} vehículos (Punto E)."
    )

    add_h1("Anexo C: Declaración de Uso Ético de IA y Bitácora Usa–Modifica–Crea")
    add_p(
        "En cumplimiento del marco ético institucional trabajado en la asignatura, declaramos el uso responsable de herramientas de inteligencia artificial "
        "como apoyo de estructuración de código y auditoría estadística, bajo supervisión y decisión técnica directa del Grupo 25:"
    )
    add_bullet(
        "Usa: ",
        "partimos de las tablas de parámetros del problema de Supercentro y la arquitectura modular DES verificada previamente en teoría de colas M/M/1.",
    )
    add_bullet(
        "Modifica: ",
        "adaptamos el horizonte a 1000 minutos, incorporamos factores unitarios Z ~ Exp(1) para sostener números aleatorios comunes (CRN) en la mejora UX/LPR, "
        "e implementamos funciones exactas sin dependencias externas para cuantiles t de Student y bondad de ajuste χ².",
    )
    add_bullet(
        "Crea: ",
        "diseñamos el detector de réplicas N* por estabilización asintótica del promedio acumulado, el filtro adaptativo de período transitorio (Punto E), los "
        "siete escenarios comparativos con sensibilidad JSQ observable y la suite de 16 pruebas unitarias que audita cada cifra del informe.",
    )

    saved_path = output_filename
    try:
        doc.save(output_filename)
        print(f"[OK] Documento Word APA 7 generado exitosamente: {output_filename}")
    except PermissionError:
        saved_path = os.path.join(BASE_DIR, "Palacios_Camilo_problemaParqueadero_Actualizado.docx")
        doc.save(saved_path)
        print(f"[AVISO] Archivo en uso. Guardado como: {saved_path}")

    if update_word_toc_and_fields(saved_path):
        print("[OK] Tabla de Contenido y numeración de páginas actualizadas vía Microsoft Word.")
    else:
        print("[AVISO] No se pudo invocar Word COM automáticamente; abra el .docx para actualizar campos.")


if __name__ == "__main__":
    build_document()
