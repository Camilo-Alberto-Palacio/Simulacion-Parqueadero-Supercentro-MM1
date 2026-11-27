"""
Generador Dinámico del Informe Académico Oficial en Formato Word (.docx)
Normas APA 7.ª Edición · Redacción Reflexiva en Ingeniería (Grupo 25)
Actividad Didáctica 2-M4 — Solución de un Problema de Parqueaderos (Centro Comercial Supercentro).
Asignatura: Simulación (PREICA2602B020045) — Grupo 25.
Institución Universitaria Digital de Antioquia (IU Digital) — Facultad de Ingeniería.

Carga dinámicamente 14 de los 17 CSVs experimentales de 'results/' (parámetros base de tabla 1 desde model.py),
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


def format_es_int(val: int) -> str:
    n = int(val)
    return f"{n:,}".replace(",", "\u00a0") if abs(n) >= 10000 else str(n)


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

    for idx_line, (line_num, line_txt) in enumerate(enumerate(code_lines, start=1)):
        p = cell.paragraphs[0] if idx_line == 0 else cell.add_paragraph()
        p.paragraph_format.space_before = Pt(2 if idx_line == 0 else 0.5)
        p.paragraph_format.space_after = Pt(2 if idx_line == len(code_lines) - 1 else 0.5)
        p.paragraph_format.line_spacing = 1.02
        p.paragraph_format.keep_with_next = True

        r_num = p.add_run(f"{line_num:2d}  ")
        r_num.font.name = "Consolas"
        r_num.font.size = Pt(8.0)
        r_num.font.color.rgb = COLOR_MUTED

        r_code = p.add_run(line_txt)
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

    # Cargar dinámicamente 14 de los 17 CSVs experimentales de results/
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
    df_stat5k = pd.read_csv(os.path.join(RESULTS_DIR, "validacion_estacionaria_5000m.csv"))
    df_paired = pd.read_csv(os.path.join(RESULTS_DIR, "ic_pareados_crn_escenarios.csv"))
    df_sens = pd.read_csv(os.path.join(RESULTS_DIR, "sensibilidad_extendida_nivel_b.csv"))

    sum_idx = df_sum.set_index("escenario")
    jsq_idx = df_jsq.set_index("escenario")
    warm_idx = df_warm.set_index("escenario")
    vv_idx = df_vv.set_index("escenario")
    pil_idx = df_piloto.set_index("escenario")
    usr_idx = df_users.set_index("tipo_usuario")
    s5k_idx = df_stat5k.set_index("escenario")
    pair_idx = df_paired.set_index("contraste")

    n_det = int(df_conv["n_detectado_exacto"].iloc[0])
    n_off = int(df_conv["n_oficial_seleccionado"].iloc[0])
    er_lk_bound = float(df_conv["er_umbral_law_kelton_pct"].iloc[0])
    row_n_off = df_conv[df_conv["replica"] == n_off].iloc[0]

    # Métricas base E1 (3 Mixtos)
    wq_e1 = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_media_min"])
    wq_e1_unw = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_prom_no_ponderado_cajeros_min"])
    wq_e1_l = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_ic95_inf"])
    wq_e1_u = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_ic95_sup"])
    w_e1 = float(sum_idx.loc["E1_3_Mixtos", "sistema_w_media_min"])
    s_e1 = float(sum_idx.loc["E1_3_Mixtos", "servicio_s_media_min"])
    er_wq_e1 = float(sum_idx.loc["E1_3_Mixtos", "espera_wq_er_pct"])
    er_w_e1 = float(sum_idx.loc["E1_3_Mixtos", "sistema_w_er_pct"])
    p5_e1_glob = float(vv_idx.loc["E1_3_Mixtos", "prob_wq_mayor_5m_global_pct"])
    p5_e1_peor = float(vv_idx.loc["E1_3_Mixtos", "prob_wq_mayor_5m_peor_cajero_pct"])
    er10_e1 = float(pil_idx.loc["E1_3_Mixtos", "wq_er_piloto_pct"])
    n_prof10 = int(pil_idx.loc["E1_3_Mixtos", "n_req_wq_er10_prof"])
    n_prof75 = int(pil_idx.loc["E1_3_Mixtos", "n_req_wq_er75_prof"])
    n_prof_w5 = int(pil_idx.loc["E1_3_Mixtos", "n_req_w_er5_prof"])

    # Punto A (Cajeros base E1)
    base_caj = df_caj[df_caj["escenario"] == "E1_3_Mixtos"].copy().reset_index(drop=True)
    c_min_w = base_caj.loc[base_caj["atencion_w_prom"].idxmin()]
    c_max_w = base_caj.loc[base_caj["atencion_w_prom"].idxmax()]
    c_min_s = base_caj.loc[base_caj["servicio_s_prom"].idxmin()]
    c_max_s = base_caj.loc[base_caj["servicio_s_prom"].idxmax()]
    c_mid_w = base_caj[(base_caj["cajero"] != c_min_w["cajero"]) & (base_caj["cajero"] != c_max_w["cajero"])].iloc[0]
    p_sym_min = float(df_paired[df_paired["grupo"] == "Punto A (E1 simetría)"]["p_valor"].min())

    # Punto B (Usuarios por tipo + cargas teóricas exactas desde CSV de usuarios)
    tot_veh_jornada = float(sum_idx.loc["E1_3_Mixtos", "usuarios_promedio"])
    tot_veh_all = int(df_users["total_replicas"].sum())
    srv_loads_theo = {u: float(usr_idx.loc[u, "prop_teorica_pct"]) * float(usr_idx.loc[u, "s_teorico_min"]) for u in usr_idx.index}
    tot_srv_load_theo = sum(srv_loads_theo.values())
    srv_pct_theo = {u: (srv_loads_theo[u] / tot_srv_load_theo) * 100.0 for u in srv_loads_theo}
    srv_loads_emp = {u: float(usr_idx.loc[u, "prop_empirica_pct"]) * float(usr_idx.loc[u, "s_empirico_min"]) for u in usr_idx.index}
    tot_srv_load_emp = sum(srv_loads_emp.values())
    srv_pct_emp = {u: (srv_loads_emp[u] / tot_srv_load_emp) * 100.0 for u in srv_loads_emp}
    slow_emp_arr = float(usr_idx.loc["Lento", "prop_empirica_pct"]) + float(usr_idx.loc["Muy lento", "prop_empirica_pct"])
    slow_emp_load = srv_pct_emp["Lento"] + srv_pct_emp["Muy lento"]
    slow_theo_load = srv_pct_theo["Lento"] + srv_pct_theo["Muy lento"]
    max_dif_pp = float(df_users["dif_pp"].abs().max())

    # Punto C (Escenarios alternativos + M/G/c)
    wq_e2 = float(sum_idx.loc["E2_4_Mixtos", "espera_wq_media_min"])
    w_e2 = float(sum_idx.loc["E2_4_Mixtos", "sistema_w_media_min"])
    wq_e3 = float(sum_idx.loc["E3_5_Mixtos", "espera_wq_media_min"])
    w_e3 = float(sum_idx.loc["E3_5_Mixtos", "sistema_w_media_min"])
    wq_e3_jsq = float(jsq_idx.loc["E3_5_Mixtos", "espera_wq_media_min"])
    wq_e4 = float(sum_idx.loc["E4_6_Mixtos", "espera_wq_media_min"])
    w_e4 = float(sum_idx.loc["E4_6_Mixtos", "sistema_w_media_min"])
    rho_e4_med = float(sum_idx.loc["E4_6_Mixtos", "utilizacion_rho_media"]) * 100.0
    rho_e4_max = float(sum_idx.loc["E4_6_Mixtos", "utilizacion_max_media"]) * 100.0
    ocio_e4 = 100.0 - rho_e4_med
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

    df_mgc_blk = df_sens[df_sens["bloque"] == "Cola Única M/G/c"].set_index("escenario")
    wq_e1_mgc = float(df_mgc_blk.loc["E1_3_Mixtos", "espera_wq_media_min"])
    wq_e3_mgc = float(df_mgc_blk.loc["E3_5_Mixtos", "espera_wq_media_min"])
    wq_e7_mgc = float(df_mgc_blk.loc["E7_4_Mix_UX", "espera_wq_media_min"])
    p5_e7_mgc = float(df_mgc_blk.loc["E7_4_Mix_UX", "prob_wq_mayor_5m_peor_cajero_pct"])

    # Punto D & E
    mae_pp = float(vv_idx["calibracion_mae_pp"].iloc[0])
    chi2_st = float(vv_idx["calibracion_chi2_stat"].iloc[0])
    chi2_pv = float(vv_idx["calibracion_chi2_pval"].iloc[0])
    srv_err = float(vv_idx["calibracion_srv_max_rel_err_pct"].max())
    little_max = float(max(vv_idx["verificacion_little_max_err"].max(), vv_idx["verificacion_little_jsq_max_err"].max()))
    p_min_mg1 = float(vv_idx["p_valor_vs_mg1"].min())
    p_max_mg1 = float(vv_idx["p_valor_vs_mg1"].max())
    p_min_5k = float(vv_idx["p_valor_estacionario_5000m"].min())
    p_max_5k = float(vv_idx["p_valor_estacionario_5000m"].max())

    k_cut_e1 = int(warm_idx.loc["E1_3_Mixtos", "k_corte_vehiculos"])
    d_cut_e1 = int(warm_idx.loc["E1_3_Mixtos", "d_optimo_mser"])
    t_cut_e1 = float(warm_idx.loc["E1_3_Mixtos", "tiempo_corte_aprox_min"])
    wq_ss_e1 = float(warm_idx.loc["E1_3_Mixtos", "wq_estado_estable_min"])
    wq_mg1_e1 = float(warm_idx.loc["E1_3_Mixtos", "wq_teorica_mg1_min"])
    sesgo_e1 = float(warm_idx.loc["E1_3_Mixtos", "sesgo_subestimacion_wq_pct"])
    incr_e1 = float(warm_idx.loc["E1_3_Mixtos", "incremento_wq_pct"])
    p_mg1_e1 = float(vv_idx.loc["E1_3_Mixtos", "p_valor_vs_mg1"])
    sub_w_e27 = df_warm[df_warm["escenario"] != "E1_3_Mixtos"]
    k_other_min = int(sub_w_e27["k_corte_vehiculos"].min())
    k_other_max = int(sub_w_e27["k_corte_vehiculos"].max())
    sesgo_other_min = float(sub_w_e27["sesgo_subestimacion_wq_pct"].min())
    sesgo_other_max = float(sub_w_e27["sesgo_subestimacion_wq_pct"].max())

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
    r_hdr = hdr.add_run("MODELADO M/M/1 Y M/H4/1 — PARQUEADEROS SUPERCENTRO")
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
        "Modelado Estocástico M/M/1 y M/H4/1, Estado Estable\n"
        "y Eliminación del Período Transitorio en el Sistema de Pago\n"
        "de Parqueaderos del Centro Comercial Supercentro",
        font_size=16.5, color=COLOR_PRIMARY, bold=True,
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
        f"El problema base en Supercentro es que tres cajeros por salida no alcanzan, pues el 55 % de los usuarios (lentos y muy lentos) demora "
        f"de cuatro a seis minutos digitando la placa. Construimos un simulador discreto en Python con turnos de 1000 min, generador PCG64 mediante "
        f"SeedSequence y semilla 42. Con la regla secuencial causal de Law y Kelton sin mirar futuro, el estudio cerró en N^{{*}} = {n_off} réplicas "
        f"(W_{{q}} = {wq_e1:.2f} min, IC 95 % [{wq_e1_l:.2f}, {wq_e1_u:.2f}], ER = {er_wq_e1:.2f} %). En el esquema base pasan {tot_veh_jornada:.2f} "
        f"vehículos por jornada; el {c_min_w['cajero']} dio el menor promedio total (W = {c_min_w['atencion_w_prom']:.3f} min) y el {c_max_w['cajero']} "
        f"el mayor (W = {c_max_w['atencion_w_prom']:.3f} min), diferencia por azar muestral (p ≥ {p_sym_min:.3f}). En la comparativa bajo números "
        f"aleatorios comunes de siete diseños, con tres cajas el {p5_e1_glob:.1f} % global ({p5_e1_peor:.1f} % en el peor servidor) espera más de cinco "
        f"minutos. La propuesta elegida es E7: cuatro cajeros mixtos más lectura de placa LPR o QR que baja 25 % el tiempo de los perfiles lentos, "
        f"llevando W_{{q}} a {wq_e7:.2f} min (W = {w_e7:.2f} min), {wq_e7_jsq:.2f} min con señalización JSQ y {wq_e7_mgc:.2f} min en cola única M/G/c, "
        f"validado con Little continuo, MSER-5 y pruebas t frente a M/G/1 a 1000 min (p ∈ [{p_min_mg1:.3f}, {p_max_mg1:.3f}]) y 5000 min (p ∈ [{p_min_5k:.3f}, {p_max_5k:.3f}]).",
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
        "simulación de eventos discretos, colas M/M/1 y M/H4/1, Law y Kelton, MSER-5, verificación y validación, parqueaderos.",
        font_size=9.8, color=COLOR_BODY,
    )

    doc.add_page_break()

    # =========================================================
    # 1. INTRODUCCIÓN
    # =========================================================
    add_h1("1. Introducción")
    add_p(
        "Cada salida del centro comercial Supercentro tiene tres cajeros automáticos independientes bajo disciplina FCFS, es decir, primero en llegar y "
        "primero en salir, sin cambio de fila ni deserción. Apenas el 25 % de los conductores paga rápido, mientras que el 55 % tarda cuatro o seis minutos "
        "digitando la placa y pagando frente a la pantalla."
    )
    add_p(
        "La pregunta práctica desde la ingeniería de software es si bastan esas tres máquinas o si conviene ampliar la capacidad física y automatizar la "
        "interfaz de pago. Hay además una aclaración técnica central: si se estudia cada perfil por separado funciona como una cola exponencial M/M/1, "
        "pero al mezclar los cuatro perfiles en un mismo cajero el servicio pasa a ser una mezcla hiperexponencial M/H4/1, que pertenece al caso M/G/1."
    )
    add_p(
        "A lo largo del informe resolvemos los cinco puntos de la actividad, desde el A hasta el E. Primero determinamos el tamaño muestral N* en estado "
        "estable y revisamos qué cajero tuvo menor y mayor tiempo de atención; luego estimamos los usuarios por tipo en toda la salida y evaluamos si tres "
        "cajeros bastan para proponer una estrategia; finalmente ejecutamos la verificación, calibración y validación del simulador y eliminamos el período "
        "transitorio inicial para comparar el antes y el después."
    )

    # =========================================================
    # 2. METODOLOGÍA Y FUNDAMENTACIÓN TEÓRICA
    # =========================================================
    add_h1("2. Metodología y Fundamentación Teórica del Modelo")

    add_h2("2.1 Parametrización del Sistema y Distinción M/M/1 vs. M/H4/1 (M/G/1)")
    add_p(
        "En la Tabla 1 se muestran los cuatro perfiles de usuario con sus tiempos de servicio E[S] y tiempos entre llegadas E[IA] exponenciales (Ross, 2014). Bajo un "
        "ruteo equiprobable de 1/3 entre las tres cajas base, el tiempo medio entre llegadas por cajero queda en E[IA_{c}] = 4.650 minutos, conservando una "
        "demanda agregada fija por salida de λ_{salida} = 3 / 4.650 = 0.6452 vehículos por minuto en todos los escenarios."
    )

    tbl1_data = [
        ["Rápido", "25.0 %", "1.0 min", "3.0 min", "0.3333", "1.0000", "0.333", "Estable"],
        ["Normal", "20.0 %", "3.0 min", "3.0 min", "0.3333", "0.3333", "1.000", "Crítico (límite)"],
        ["Lento", "27.5 %", "4.0 min", "5.0 min", "0.2000", "0.2500", "0.800", "Estable"],
        ["Muy lento", "27.5 %", "6.0 min", "7.0 min", "0.1429", "0.1667", "0.857", "Estable"],
        ["Mezcla por cajero (E1)", "100.0 %", "3.600 min", "4.650 min", "0.2151", "0.2778", "0.774", "Estable (alto uso)"],
    ]
    format_apa_table(
        doc,
        "Tabla 1",
        "Parámetros exponenciales por perfil de usuario y mezcla resultante por cajero en Supercentro",
        [Inches(1.30), Inches(0.68), Inches(0.80), Inches(0.80), Inches(0.68), Inches(0.68), Inches(0.56), Inches(1.00)],
        ["Tipo de usuario", "Proporción", "Servicio E[S]", "Llegada E[IA]", "Tasa λ", "Tasa μ", "Uso ρ", "Estado teórico"],
        tbl1_data,
        "Tasas expresadas en vehículos/min. La suma de tasas individuales aisladas (1.0095 veh/min) difiere de la mezcla ponderada por cajero (0.2151 veh/min); bajo conservación total en E1, λ_{salida} = 3 / 4.650 = 0.6452 veh/min.",
        font_size=7.9,
    )

    add_p(
        "Cada perfil aislado forma una cola M/M/1 exacta (Gross et al., 2008), donde el perfil Normal tiene ρ = 1.000 y diverge sin cota, como se ve en la Tabla 2. Al mezclar "
        "los cuatro perfiles en un mismo cajero resulta un servicio hiperexponencial H4 con media E[S] = 3.600 minutos, segundo momento E[S^{2}] = 32.70 min^{2} "
        "y coeficiente C^{2}_{s} = 1.5231 mayor que uno. Con arribos de Poisson (C^{2}_{a} = 1) el sistema es exactamente M/H4/1 (caso M/G/1), por lo que "
        "la fórmula M/M/1 tradicional (12.34 minutos en E1) subestima la fila y Pollaczek–Khinchine da el valor exacto de 15.57 minutos (Kleinrock, 1975). "
        "Si las llegadas también fueran hiperexponenciales H4 con C^{2}_{a} = 1.2569, se pasa a un modelo H4/H4/1 (GI/G/1), que evaluamos en la Sección 3.7."
    )

    add_equation_box("ρ = λ_{c} / μ_{c} < 1,     P_{0} = 1 - ρ,     L_{q}(M/M/1) = ρ^{2} / (1 - ρ),     L_{q} = λ_{c} · W_{q},     L = λ_{c} · W", "(1)")
    add_equation_box("W_{q}(M/M/1) = ρ / [μ_{c}(1 - ρ)],     W_{q}(M/G/1) = [λ_{c} · E[S^{2}]] / [2(1 - ρ)],     W = W_{q} + 1/μ_{c}", "(2)")

    add_p(
        "También hay que explicar que la fórmula exponencial cerrada para P(W_{q} > 5 min) subestima las colas pesadas hiperexponenciales: en el escenario E7 "
        "predice un 18.9 % teórico exponencial frente al 21.2 % real simulado. Por eso usamos los cuantiles empíricos directos del simulador M/H4/1 para evaluar "
        "todos los umbrales de riesgo."
    )

    tbl2_data = []
    for _, rt in df_iso_theo.iterrows():
        w_txt = f"{rt['w_sistema_min']:.2f} m" if rt["estable"] else "∞"
        wq_txt = f"{rt['wq_cola_min']:.2f} m" if rt["estable"] else "∞"
        l_txt = f"{rt['l_sistema']:.2f}" if rt["estable"] else "∞"
        tbl2_data.append([
            rt["tipo_usuario"],
            f"{rt['rho']:.3f}",
            f"{rt['p0_ocio']*100:.1f} %",
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
        "Cálculo exacto mediante las ecuaciones (1) y (2) evaluando cada categoría en solitario antes de mezclarla en un servidor polivalente.",
        font_size=8.0,
    )

    add_h2("2.2 Arquitectura DES, Regla Causal Law y Kelton y Criterios del Equipo")
    add_p(
        "El simulador de eventos discretos fue programado en Python 3.13 dentro del paquete parking_queue/, sin SciPy ni librerías inferenciales externas, "
        "trabajando con turnos de 1000 minutos. Para garantizar reproducibilidad invariante al prefijo usamos SeedSequence([42, flujo, réplica]) sobre PCG64, "
        "guardando un factor unitario Z ~ Exp(1) para aplicar números aleatorios comunes (CRN) completos al comparar los siete escenarios:"
    )
    add_bullet("E1 — 3 Mixtos (Base actual): ", "tres cajeros independientes atendiendo todos los perfiles con ruteo aleatorio equiprobable 1/3.")
    add_bullet("E2, E3 y E4 — Ampliación mixta (4, 5 y 6 cajeros): ", "incremento físico de cajeros polivalentes conservando λ_{salida} = 0.6452 veh/min.")
    add_bullet("E5 (1E + 3L) y E6 (1E + 4L) — Especialización rígida: ", "1 cajero Exprés (E) exclusivo para Rápido y Normal (45 % del flujo) frente a 3 o 4 Estándar (L) exclusivos para Lento y Muy lento (55 %).")
    add_bullet("E7 — 4 Mixtos + Mejora UX/LPR: ", "cuatro cajeros mixtos sumando lectura automática de placa LPR o código QR en software (UX: experiencia de usuario), recortando 25 % la interacción de Lentos (4 → 3 min) y Muy lentos (6 → 4.5 min).")

    add_p(
        "El Grupo 25 definió cinco criterios en régimen estacionario: espera media W_{q} ≤ 5 minutos con peor cajero ≤ 5.5 minutos (óptima menor a 3 y 3.5 "
        "minutos); tiempo total W ≤ 8 minutos (óptimo menor a 5 minutos); uso del peor servidor entre 45 % y 85 %, clasificando como subutilizado por debajo "
        "de 45 %, alerta entre 85 % y 90 % y crítico por encima de 90 %; longitud de cola L_{q} menor a 3 vehículos por cajero (alerta de 3 a 5 y crítico "
        "mayor a 5); y máximo 20 % esperando más de cinco minutos en el peor servidor (óptimo menor a 10 %). Además, evaluamos señalización hacia la cola "
        "más corta JSQ, programada con deque sin clarividencia, y la referencia de cola única M/G/c."
    )

    # =========================================================
    # 3. RESULTADOS Y ANÁLISIS DEL MODELO
    # =========================================================
    add_h1("3. Resultados de Simulación y Análisis Estadístico")

    # 3.1 Estado Estable para definir réplicas N*
    add_h2("3.1 Determinación Causal de Réplicas (N*) por Law y Kelton")
    add_p(
        f"El piloto corto de n_{{0}} = 10 corridas resultó insuficiente porque dio un error relativo ER = {er10_e1:.2f} % sobre W_{{q}} en el escenario base E1; "
        f"con la fórmula clásica se habrían pedido {n_prof10} corridas para ER ≤ 10 %, {n_prof75} para ER ≤ 7.5 % y {n_prof_w5} para ER(W) ≤ 5 %. Para evitar "
        f"sesgos por mirar datos futuros usamos la regla secuencial estrictamente causal de Law y Kelton (Law, 2015), avanzando desde r = 30 hasta cumplir al "
        f"mismo tiempo ER(W_{{q}}) ≤ {er_lk_bound:.2f} % (con γ = 0.06) y una variación móvil máxima de 1.5 % en las últimas 20 réplicas."
    )

    milestones = sorted(set([10, 30, 50, 100, 150, 200, n_off, 250]))
    tbl3_data = []
    for r_m in milestones:
        rm = df_conv[df_conv["replica"] == r_m].iloc[0]
        tag = f"{int(r_m)}"
        if r_m == n_off:
            tag = f"{int(r_m)} (Oficial N*)"
        tvar = "—" if pd.isna(rm["variacion_ventana_causal_wq_pct"]) else f"{rm['variacion_ventana_causal_wq_pct']:.2f} %"
        tbl3_data.append([
            tag,
            f"{rm['wq_media_acumulada_min']:.2f} m",
            f"[{rm['wq_ic95_inf']:.2f}, {rm['wq_ic95_sup']:.2f}]",
            tvar,
            f"{rm['wq_er_pct']:.2f} %",
            f"{rm['w_media_acumulada_min']:.2f} m",
            f"{rm['w_er_pct']:.2f} %",
        ])

    format_apa_table(
        doc,
        "Tabla 3",
        "Evolución causal del promedio acumulado y error relativo bajo regla secuencial Law y Kelton (3 Mixtos)",
        [Inches(1.05), Inches(0.85), Inches(1.25), Inches(0.95), Inches(0.80), Inches(0.85), Inches(0.75)],
        ["Réplicas (r)", "W_{q} acum.", "IC 95 % t (W_{q})", "Var. causal", "ER (W_{q})", "W acum.", "ER (W)"],
        tbl3_data,
        f"Var. causal mide la desviación máxima de los últimos 20 promedios acumulados respecto a W_{{q}}(r) sin usar datos futuros. La condición dual (ER ≤ {er_lk_bound:.2f} % y Var. causal ≤ 1.5 %) se alcanza en r = {n_det}, adoptándose N* = {n_off}.",
        font_size=7.9,
    )

    add_p(
        f"El método alcanza convergencia exacta en r = {n_det}, así que adoptamos N^{{*}} = {n_off} réplicas oficiales en todo el estudio (Tabla 3 y Figura 1). "
        f"Con esas {n_off} jornadas la espera promedio queda en W_{{q}} = {row_n_off['wq_media_acumulada_min']:.2f} minutos con ER = {er_wq_e1:.2f} %, y el "
        f"tiempo total en sistema es W = {w_e1:.2f} minutos con ER = {er_w_e1:.2f} %, por debajo del 5 %."
    )

    add_apa_fig(
        "fig1_estado_estable_replicas.png",
        "Figura 1",
        "Convergencia causal de réplicas N* bajo regla secuencial de Law y Kelton y error relativo",
        f"Panel A grafica el promedio acumulado W_{{q}}(r) sin mirar información futura; Panel B verifica simultáneamente ER(W_{{q}}) ≤ {er_lk_bound:.2f} % y ER(W) ≤ 5 % en N* = {n_off}.",
        width_in=6.35,
    )

    # 3.2 Punto A
    add_h2("3.2 Punto A: Estadísticas por Cajero (Menor y Mayor Tiempo de Atención)")
    add_p(
        f"En el escenario base E1, corrido con N^{{*}} = {n_off} réplicas de 1000 minutos, el promedio simple entre los tres cajeros da W_{{q}} = {wq_e1_unw:.3f} "
        f"minutos, frente a la media del sistema ponderada por clientes de W_{{q}} = {wq_e1:.3f} minutos (Tabla 4)."
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
            f"{rc['utilizacion_rho_prom']*100:.1f} %",
        ])

    format_apa_table(
        doc,
        "Tabla 4",
        f"Desempeño estadístico por cajero en el escenario base de 3 cajeros mixtos (N* = {n_off} réplicas)",
        [Inches(0.68), Inches(0.85), Inches(0.90), Inches(0.90), Inches(0.90), Inches(0.92), Inches(0.80), Inches(0.55)],
        ["Cajero", "Veh./jornada", "Servicio S (m)", "Espera W_{q} (m)", "Total W (m)", "IC 95 % W", "Mín–Máx W", "Uso ρ"],
        tbl4_data,
        f"Cifras reportan media (±DE muestral), intervalo t al 95 % (gl = {n_off - 1}) y rango observado en {n_off} corridas. Promedio no ponderado de cajeros: W_{{q}} = {wq_e1_unw:.3f} min.",
        font_size=7.6,
    )

    add_p(
        f"Las cifras de la Tabla 4 muestran que el {c_min_w['cajero']} obtuvo el menor promedio total con W = {c_min_w['atencion_w_prom']:.3f} minutos y W_{{q}} = "
        f"{c_min_w['espera_wq_prom']:.3f} minutos. El {c_mid_w['cajero']} quedó en un punto intermedio con W = {c_mid_w['atencion_w_prom']:.3f} minutos y W_{{q}} = "
        f"{c_mid_w['espera_wq_prom']:.3f} minutos, mientras que el {c_max_w['cajero']} marcó el mayor valor con W = {c_max_w['atencion_w_prom']:.3f} minutos y "
        f"W_{{q}} = {c_max_w['espera_wq_prom']:.3f} minutos, con picos de hasta {c_max_w['atencion_w_max']:.1f} minutos. Como son tres servidores idénticos e "
        f"independientes (i.i.d.), los intervalos de confianza al 95 % se solapan y las pruebas t pareadas confirman p ≥ {p_sym_min:.3f} (Figura 2), "
        f"demostrando que esa diferencia es solamente variabilidad muestral."
    )

    add_apa_fig(
        "fig2_desempeno_cajeros_base.png",
        "Figura 2",
        "Comparativa estadística de servicio, espera y atención total por cajero en el escenario base",
        f"Panel A muestra medias con IC 95 % t solapados (simetría i.i.d., p > 0.05); Panel B exhibe diagramas de caja con media (rombo), mediana y atípicos en {n_off} corridas.",
        width_in=6.35,
    )

    # 3.3 Punto B
    add_h2("3.3 Punto B: Promedio de Usuarios por Tipo en la Totalidad de Cajeros")
    add_p(
        f"El total acumulado en las {n_off} corridas fue de {format_es_int(tot_veh_all)} vehículos, lo que equivale a {tot_veh_jornada:.2f} vehículos por "
        f"jornada frente a los 645.16 esperados bajo llegadas de Poisson. Los promedios por categoría en las tres cajas de la salida (y por cajero) son: "
        f"Rápido con {usr_idx.loc['Rápido', 'promedio_total_3_cajeros']:.2f} ± {usr_idx.loc['Rápido', 'desv_est_total']:.2f} "
        f"({usr_idx.loc['Rápido', 'promedio_por_cajero']:.2f}/caj), Normal con {usr_idx.loc['Normal', 'promedio_total_3_cajeros']:.2f} ± "
        f"{usr_idx.loc['Normal', 'desv_est_total']:.2f} ({usr_idx.loc['Normal', 'promedio_por_cajero']:.2f}/caj), Lento con "
        f"{usr_idx.loc['Lento', 'promedio_total_3_cajeros']:.2f} ± {usr_idx.loc['Lento', 'desv_est_total']:.2f} "
        f"({usr_idx.loc['Lento', 'promedio_por_cajero']:.2f}/caj) y Muy lento con {usr_idx.loc['Muy lento', 'promedio_total_3_cajeros']:.2f} ± "
        f"{usr_idx.loc['Muy lento', 'desv_est_total']:.2f} ({usr_idx.loc['Muy lento', 'promedio_por_cajero']:.2f}/caj), como se observa en la Tabla 5."
    )

    tbl5_data = []
    for _, ru in df_users.iterrows():
        tbl5_data.append([
            ru["tipo_usuario"],
            format_es_int(int(ru["total_replicas"])),
            f"{ru['promedio_total_3_cajeros']:.2f} (±{ru['desv_est_total']:.2f})",
            f"{ru['promedio_por_cajero']:.2f}",
            f"[{int(ru['min_replica'])}–{int(ru['max_replica'])}]",
            f"{ru['prop_empirica_pct']:.2f} %",
            f"{ru['prop_teorica_pct']:.1f} %",
            f"{ru['s_empirico_min']:.2f} m",
            f"{ru['w_empirico_min']:.2f} m",
        ])
    tbl5_data.append([
        "Total salida",
        format_es_int(tot_veh_all),
        f"{tot_veh_jornada:.2f}",
        f"{tot_veh_jornada/3:.2f}",
        "—",
        "100.00 %",
        "100.0 %",
        f"{s_e1:.2f} m",
        f"{w_e1:.2f} m",
    ])

    format_apa_table(
        doc,
        "Tabla 5",
        f"Promedio de usuarios por categoría en los 3 cajeros y por servidor (N* = {n_off} réplicas)",
        [Inches(0.75), Inches(0.68), Inches(1.02), Inches(0.65), Inches(0.72), Inches(0.65), Inches(0.65), Inches(0.68), Inches(0.70)],
        ["Categoría", f"Total {n_off}R", "3 Cajeros (±DE)", "Por cajero", "Mín–Máx", "Prop. Emp.", "Prop. Teór.", "Serv. S", "Total W"],
        tbl5_data,
        f"±DE expresa desviación estándar muestral entre réplicas. La diferencia máxima entre proporciones empíricas y teóricas es apenas {max_dif_pp:.2f} pp.",
        font_size=7.6,
    )

    add_p(
        f"La asimetría operativa de la Figura 3 (Panel B) muestra que los usuarios lentos y muy lentos representan el 55.0 % teórico y el {slow_emp_arr:.2f} % "
        f"empírico en llegadas, pero consumen el {slow_theo_load:.1f} % teórico ({srv_pct_theo['Lento']:.1f} % y {srv_pct_theo['Muy lento']:.1f} %) y el "
        f"{slow_emp_load:.2f} % empírico de la ocupación de las máquinas. En cambio, los usuarios rápidos suman el 25.0 % de las visitas y solo usan el "
        f"{srv_pct_theo['Rápido']:.1f} % teórico y el {srv_pct_emp['Rápido']:.2f} % empírico de la capacidad."
    )

    add_apa_fig(
        "fig3_usuarios_por_tipo.png",
        "Figura 3",
        "Distribución promedio de usuarios por tipo en los 3 cajeros y asimetría de carga en servicio",
        "Panel A muestra promedios (±DE muestral) vs. frecuencias esperadas; Panel B contrapone proporción teórica de llegadas contra proporción teórica de ocupación.",
        width_in=6.35,
    )

    # 3.4 Punto C
    add_h2("3.4 Punto C: Estrategia de Mejora y Comparativa de Escenarios")
    add_p(
        f"Tres cajeros no bastan para la salida de Supercentro. En el escenario base E1 la espera promedia {wq_e1:.2f} minutos (IC 95 % "
        f"[{wq_e1_l:.2f}, {wq_e1_u:.2f}]) y el tiempo total llega a {w_e1:.2f} minutos; el servidor más cargado promedia "
        f"{float(sum_idx.loc['E1_3_Mixtos', 'utilizacion_peor_cajero_prom'])*100:.1f} % de uso con picos intradiarios de "
        f"{float(sum_idx.loc['E1_3_Mixtos', 'utilizacion_max_media'])*100:.1f} %, y el {p5_e1_glob:.1f} % global ({p5_e1_peor:.1f} % en el peor cajero) "
        f"espera más de cinco minutos, como se observa en la Tabla 6."
    )

    tbl6_data = []
    for skey in df_sum["escenario"]:
        rs = sum_idx.loc[skey]
        rj = jsq_idx.loc[skey]
        mgc_txt = f"{float(df_mgc_blk.loc[skey, 'espera_wq_media_min']):.2f} m" if skey in df_mgc_blk.index else "—"
        tbl6_data.append([
            rs["nombre_corto"],
            f"{int(rs['num_cajeros'])}",
            f"{rs['espera_wq_media_min']:.2f} [{rs['espera_wq_ic95_inf']:.2f}–{rs['espera_wq_ic95_sup']:.2f}]",
            f"{rs['peor_cajero_wq_prom_min']:.2f} m",
            f"{rs['sistema_w_media_min']:.2f} m",
            f"{rs['wq_teorica_mg1_min']:.2f} m",
            f"{rj['espera_wq_media_min']:.2f} m",
            mgc_txt,
            f"{rs['prob_wq_mayor_5m_pct']:.1f} / {vv_idx.loc[skey, 'prob_wq_mayor_5m_peor_cajero_pct']:.1f} %",
        ])

    format_apa_table(
        doc,
        "Tabla 6",
        f"Comparativa operativa de estrategias de mejora frente al escenario base (N* = {n_off} réplicas)",
        [Inches(0.84), Inches(0.36), Inches(1.14), Inches(0.62), Inches(0.58), Inches(0.58), Inches(0.60), Inches(0.60), Inches(1.18)],
        ["Escenario", "Caj.", "W_{q} [IC 95 %]", "Peor caj.", "Total W", "M/G/1", "JSQ", "M/G/c", "P(W_{q}>5m) G/Peor"],
        tbl6_data,
        f"M/G/1 reporta Pollaczek–Khinchine teórico. JSQ usa señalización observable con deque; M/G/c mide cola única serpentina (N* = {n_off} réplicas). P(W_{{q}}>5m) separa porcentaje global y peor servidor.",
        font_size=7.2,
    )

    add_p(
        f"En la comparativa de descartes, pasar a cuatro cajeros mixtos sin cambio de software (E2) deja la espera en {wq_e2:.2f} minutos y el total en "
        f"{w_e2:.2f} minutos, todavía por encima de la meta de cinco minutos. Las opciones de segregación fija E5 ({wq_e5:.2f} minutos global, pero "
        f"{peor_e5:.2f} minutos en las filas estándar) y E6 ({peor_e6:.2f} minutos en el peor servidor frente a {wq_e3:.2f} minutos de cinco mixtos E3) "
        f"fallan por pérdida de consolidación de fila (pooling)."
    )
    add_p(
        f"Instalar seis cajeros mixtos (E4) logra una espera de {wq_e4:.2f} minutos, tiempo total de {w_e4:.2f} minutos y {p5_e4_peor:.1f} % por encima de "
        f"cinco minutos en el peor cajero, pero resulta REDUNDANTE porque trabaja con solo {rho_e4_med:.1f} % de uso promedio, {ocio_e4:.1f} % de tiempo "
        f"ocioso y {float(sum_idx.loc['E4_6_Mixtos', 'utilizacion_peor_cajero_prom'])*100:.1f} % en el servidor más cargado (por debajo de 45 %, con pico "
        f"diario de {rho_e4_max:.1f} %). Por eso la estrategia elegida es E7 (cuatro mixtos más mejora UX/LPR), que suma un solo cajero y lectura automática "
        f"de placa LPR o QR para bajar un 25 % el tiempo de los perfiles lentos y muy lentos: alcanza W_{{q}} = {wq_e7:.2f} minutos, el menor tiempo total del "
        f"estudio (W = {w_e7:.2f} minutos frente a {w_e4:.2f} en E4) y {rho_e7:.1f} % de uso. Aunque sin señalizar pasa un poco del 20 % ({p5_e7_peor:.1f} % "
        f"en el peor servidor), con señalización JSQ cae a W_{{q}} = {wq_e7_jsq:.2f} minutos ({p5_e7_jsq:.1f} % sobre cinco minutos) y en fila única M/G/c "
        f"baja a {wq_e7_mgc:.2f} minutos ({p5_e7_mgc:.1f} %, Figura 4). Como alternativa solo física queda E3 (cinco mixtos), que con JSQ logra "
        f"{wq_e3_jsq:.2f} minutos y {wq_e3_mgc:.2f} minutos en M/G/c."
    )

    add_apa_fig(
        "fig4_estrategias_mejora_escenarios.png",
        "Figura 4",
        "Evaluación comparativa de los siete escenarios frente a M/H4/1 paralelo, JSQ, cola única M/G/c y riesgo > 5 min",
        "Panel A superpone rombos de cota inferior M/G/c y triángulos de peor cajero; Panel B contrasta ocupación promedio del cajero más cargado (ρ_{caj}) contra riesgo P(W_{q} > 5 min).",
        width_in=6.35,
    )

    # 3.5 Punto D
    add_h2("3.5 Punto D: Verificación, Calibración y Validación (V&V)")
    add_p(
        f"El simulador se revisó en tres capas de verificación, calibración y validación siguiendo el enfoque de Banks et al. (2010). En la verificación "
        f"ejecutamos 25 pruebas unitarias que pasaron sin fallos, comprobamos el cruce automático del cuaderno Colab contra los archivos CSV y realizamos "
        f"una auditoría continua de la ley de Little (Little, 1961; L_{{q}} = ∫Q(t)dt / H_{{eff}} = λ_{{eff}} · W_{{q}}) en las {n_off} × 7 corridas tanto en paralelo "
        f"como en JSQ, obteniendo un residuo máximo de {little_max:.2e}, menor a 10^{{-10}}. En la calibración frente a las proporciones objetivo "
        f"(25 / 20 / 27.5 / 27.5 %) el MAE fue de {mae_pp:.2f} puntos porcentuales, la prueba de bondad de ajuste dio χ^{{2}} = {chi2_st:.3f} (gl = 3, "
        f"p = {chi2_pv:.3f} > 0.05) y el error relativo máximo de servicio fue de {srv_err:.2f} %, idéntico entre políticas bajo CRN."
    )
    add_p(
        f"En la validación estadística bilateral con α = 0.05 frente a las fórmulas exactas M/G/1 (Tabla 7 y Figura 5), en los siete escenarios no se rechaza "
        f"la igualdad con el valor teórico M/G/1 (H_{{0}}) tanto en las jornadas de 1000 minutos tras el corte MSER-5 (p ∈ [{p_min_mg1:.3f}, {p_max_mg1:.3f}]) "
        f"como en corridas dedicadas de 5000 minutos con 80 réplicas quitando los primeros 1000 minutos iniciales (p ∈ [{p_min_5k:.3f}, {p_max_5k:.3f}])."
    )

    tbl7_data = []
    for _, rv in df_vv.iterrows():
        dict_str = str(rv["dictamen_global"])
        if "ÓPTIMO" in dict_str:
            dict_short = "ÓPTIMO"
        elif "REDUNDANTE" in dict_str:
            dict_short = "REDUNDANTE"
        elif "MITIGACIÓN" in dict_str:
            dict_short = "REC. JSQ/UX"
        else:
            dict_short = "NO REC."
        tbl7_data.append([
            rv["nombre_corto"],
            "OK" if bool(rv["verificacion_little_ok"]) else "Fallo",
            f"{rv['wq_estable_min']:.2f} m",
            f"{rv['wq_teorica_mg1_min']:.2f} m",
            f"{rv['p_valor_vs_mg1']:.3f}",
            f"{rv['p_valor_estacionario_5000m']:.3f}",
            f"{rv['prob_wq_mayor_5m_peor_cajero_estable_pct']:.1f} %",
            re.sub(r"(\d)%", r"\1 %", str(rv["criterio_rho"])),
            dict_short,
        ])

    format_apa_table(
        doc,
        "Tabla 7",
        "Matriz consolidada de Verificación, Validación (1000m MSER-5 y 5000m vs. M/G/1) y dictamen operativo",
        [Inches(0.84), Inches(0.44), Inches(0.62), Inches(0.60), Inches(0.56), Inches(0.62), Inches(0.60), Inches(1.22), Inches(1.00)],
        ["Escenario", "Little", "W_{q} Est.", "M/G/1", "p (1k)", "p (5k)", "P(>5m)", "Régimen ρ_{est}", "Dictamen"],
        tbl7_data,
        f"p (1k) evalúa estado estable post-MSER-5 (N* = {n_off}); p (5k) valida en 5000 min (80 réplicas). Los cinco criterios críticos (incluidos P(>5m) del peor servidor y régimen ρ_{{est}}) se evalúan homogéneamente tras eliminar el transitorio; E4 queda REDUNDANTE (ρ̄ = {rho_e4_med:.1f} %, {ocio_e4:.1f} % ocio) y REC. JSQ/UX exige mitigación para bajar P(>5m) debajo de 20 %.",
        font_size=7.3,
    )

    add_apa_fig(
        "fig5_proceso_vv_diagrama.png",
        "Figura 5",
        "Diagrama metodológico del proceso V&V y validación estadística frente a Pollaczek–Khinchine M/G/1",
        f"Panel A detalla Verificación (25 pruebas y residuo Little |∫Q(t)dt/H - λWq| en {n_off}×7 réplicas), Calibración y Validación (1000m MSER-5 y 5000m); Panel B muestra p > 0.05 (no se rechaza H_{{0}}) en los 7 escenarios.",
        width_in=6.35,
    )

    # 3.6 Punto E
    add_h2("3.6 Punto E: Eliminación del Estado Transitorio por MSER-5 (Antes vs. Después)")
    add_p(
        "Todas las corridas arrancan vacías con L(0) = 0, lo que genera un sesgo inicial a la baja en la espera promedio (Law, 2015). Para detectar dónde "
        "termina ese transitorio aplicamos el método MSER-5 (White, 1997) en lotes de tamaño b = 5 sobre el orden de llegada k = 1…550 para hallar el punto "
        "de corte d^{*} (k^{*} = 5·d^{*} + 1), promediando después todos los vehículos restantes hasta el final del turno de 1000 minutos:"
    )

    add_code_listing(
        doc,
        [
            "z_batches = wq_cross[:eff_batches * batch_size].reshape(eff_batches, batch_size).mean(axis=1)",
            "best_d = lo_d_s",
            "best_mser = float(\"inf\")",
            "for d in range(lo_d_s, hi_d_s + 1):",
            "    tail = z_batches[d:]",
            "    m_tail = float(np.mean(tail))",
            "    mser_val = float(np.sum((tail - m_tail) ** 2) / ((eff_batches - d) ** 2))",
            "    if mser_val < best_mser:",
            "        best_mser = mser_val",
            "        best_d = d",
            "k_cut = batch_size * best_d + 1",
            "wq_ss_reps = [",
            "    float(np.mean([x[1] for x in seq[k_cut - 1:]]))",
            "    for seq in rep_seqs",
            "    if len(seq) >= k_cut",
            "]",
        ],
        "Líneas literales de eliminate_transient_and_compare en parking_queue/simulation.py (detección MSER-5 y media estacionaria hasta fin de jornada).",
    )

    tbl8_data = []
    for _, rw in df_warm.iterrows():
        tbl8_data.append([
            rw["nombre_corto"],
            f"d*={int(rw['d_optimo_mser'])} (k*={int(rw['k_corte_vehiculos'])})",
            f"{rw['tiempo_corte_aprox_min']:.1f} m",
            f"{rw['wq_con_transitorio_min']:.2f} m",
            f"{rw['wq_estado_estable_min']:.2f} m",
            f"+{rw['incremento_wq_pct']:.2f} %",
            f"{rw['sesgo_subestimacion_wq_pct']:.2f} %",
            f"{rw['w_con_transitorio_min']:.2f} → {rw['w_estado_estable_min']:.2f} m",
        ])

    format_apa_table(
        doc,
        "Tabla 8",
        f"Comparación antes y después de eliminar el período transitorio con MSER-5 en los siete escenarios (N* = {n_off})",
        [Inches(0.86), Inches(0.82), Inches(0.60), Inches(0.68), Inches(0.70), Inches(0.64), Inches(0.68), Inches(1.52)],
        ["Escenario", "Corte MSER-5", "Tiempo t*", "W_{q} Antes", "W_{q} Desp.", "Incr. (%)", "Subest. (%)", "Total W (Antes → Desp.)"],
        tbl8_data,
        "Incr. (%) = (W_{q,est} - W_{q,antes}) / W_{q,antes} × 100 %; Subest. (%) = (W_{q,est} - W_{q,antes}) / W_{q,est} × 100 % respecto al estado estable.",
        font_size=7.4,
    )

    c1w = df_warm_c1.set_index("cajero")
    c1_sub_min = float(df_warm_c1["sesgo_subestimacion_pct"].min())
    c1_sub_max = float(df_warm_c1["sesgo_subestimacion_pct"].max())
    c1_inc_min = float(df_warm_c1["incremento_wq_pct"].min())
    c1_inc_max = float(df_warm_c1["incremento_wq_pct"].max())
    add_p(
        f"En el escenario base E1 de tres mixtos, el corte queda en d^{{*}} = {d_cut_e1} (k^{{*}} = {k_cut_e1} vehículos, cerca de {t_cut_e1:.1f} minutos). Al "
        f"descartar los primeros {k_cut_e1 - 1} arribos la espera W_{{q}} sube un +{incr_e1:.2f} %, pasando de {wq_e1:.2f} a {wq_ss_e1:.2f} minutos y "
        f"convergiendo hacia el valor analítico M/G/1 de {wq_mg1_e1:.2f} minutos (p = {p_mg1_e1:.3f}), lo que deja ver una subestimación inicial del "
        f"{sesgo_e1:.2f} %. En los cajeros individuales de E1 la subestimación va de {c1_sub_min:.2f} % a {c1_sub_max:.2f} % (incremento de {c1_inc_min:.2f} % a {c1_inc_max:.2f} %): el Cajero 1 pasa de "
        f"{c1w.loc['Cajero 1', 'wq_con_transitorio_min']:.2f} a {c1w.loc['Cajero 1', 'wq_estado_estable_min']:.2f} minutos, el Cajero 2 de "
        f"{c1w.loc['Cajero 2', 'wq_con_transitorio_min']:.2f} a {c1w.loc['Cajero 2', 'wq_estado_estable_min']:.2f} minutos y el Cajero 3 de "
        f"{c1w.loc['Cajero 3', 'wq_con_transitorio_min']:.2f} a {c1w.loc['Cajero 3', 'wq_estado_estable_min']:.2f} minutos. En los demás escenarios "
        f"(E2 a E7) el corte ocurre antes, con k^{{*}} entre {k_other_min} y {k_other_max} vehículos y subestimación entre {sesgo_other_min:.2f} % y "
        f"{sesgo_other_max:.2f} %, como se ve en la Tabla 8 y la Figura 6."
    )

    add_apa_fig(
        "fig6_eliminacion_transitorio_antes_despues.png",
        "Figura 6",
        "Identificación MSER-5 del período transitorio en 3 Mixtos y comparación Antes vs. Después en los siete escenarios",
        f"Panel A delimita el arranque vacío (1–{k_cut_e1 - 1}) frente al promedio móvil centrado de Welch (w = 25); Panel B etiqueta incremento porcentual desde Antes hasta Después.",
        width_in=6.35,
    )

    # 3.7 Validación Extendida, Sensibilidad y CAPEX/OPEX
    add_h2("3.7 Validación Aislada M/M/1 (6000 min), Sensibilidad Nivel B, IC Pareados y CAPEX/OPEX")
    iso_r = df_iso_val.set_index("tipo_usuario")
    add_p(
        f"Al probar los perfiles M/M/1 aislados sobre 6000 minutos con 30 % de calentamiento descartado y 100 réplicas, los grupos Rápido "
        f"(p = {float(iso_r.loc['Rápido', 'p_valor_w']):.3f}), Lento (p = {float(iso_r.loc['Lento', 'p_valor_w']):.3f}) y Muy lento "
        f"(p = {float(iso_r.loc['Muy lento', 'p_valor_w']):.3f}) confirman el valor teórico 1/(μ - λ). En cambio, el perfil Normal (ρ = 1.00) crece desde "
        f"{float(iso_r.loc['Normal', 'w_horizonte_1000m_min']):.1f} minutos en 1000 minutos hasta {float(iso_r.loc['Normal', 'w_simulado_est_min']):.1f} "
        f"minutos en 6000 minutos, con un factor de divergencia de {float(iso_r.loc['Normal', 'ratio_crecimiento_6000_vs_1000']):.2f}× sin estabilizarse, "
        f"como se ve en la Figura 7."
    )

    add_apa_fig(
        "fig7_validacion_teoria_y_perfiles.png",
        "Figura 7",
        "Validación M/M/1 puro por perfil aislado sobre 6000 min (Panel A) y balance por cajero en escenarios clave (Panel B)",
        f"Panel A muestra crecimiento empírico {float(iso_r.loc['Normal', 'ratio_crecimiento_6000_vs_1000']):.2f}× en Normal (ρ = 1); Panel B exhibe el desbalance de cajeros Estándar en E5.",
        width_in=6.35,
    )

    add_p(
        "Para cerrar el análisis técnico, la Tabla 9 resume los contrastes pareados bajo CRN, el barrido de mejora UX de -15 % a -30 %, el impacto de "
        "llegadas hiperexponenciales H4/H4/1 y el escenario de demanda pico de +20 %, mientras que la Tabla 10 presenta la comparativa referencial de "
        "costo-beneficio CAPEX/OPEX."
    )

    ux_15_rnd = df_sens[(df_sens["bloque"] == "Sensibilidad UX/LPR") & (df_sens["escenario"] == "UX_15pct") & (df_sens["routing_mode"] == "random_mm1")].iloc[0]
    ux_15_jsq = df_sens[(df_sens["bloque"] == "Sensibilidad UX/LPR") & (df_sens["escenario"] == "UX_15pct") & (df_sens["routing_mode"] == "shortest_queue")].iloc[0]
    ux_25_rnd = df_sens[(df_sens["bloque"] == "Sensibilidad UX/LPR") & (df_sens["escenario"] == "UX_25pct") & (df_sens["routing_mode"] == "random_mm1")].iloc[0]
    ux_30_rnd = df_sens[(df_sens["bloque"] == "Sensibilidad UX/LPR") & (df_sens["escenario"] == "UX_30pct") & (df_sens["routing_mode"] == "random_mm1")].iloc[0]
    h4_e1_rnd = df_sens[(df_sens["bloque"] == "Llegadas Hiperexponenciales H4/H4/1") & (df_sens["escenario"] == "E1_3_Mixtos") & (df_sens["routing_mode"] == "random_mm1")].iloc[0]
    h4_e7_jsq = df_sens[(df_sens["bloque"] == "Llegadas Hiperexponenciales H4/H4/1") & (df_sens["escenario"] == "E7_4_Mix_UX") & (df_sens["routing_mode"] == "shortest_queue")].iloc[0]
    pk_e7_rnd = df_sens[(df_sens["bloque"] == "Demanda Pico (+20%)") & (df_sens["escenario"] == "E7_4_Mix_UX") & (df_sens["routing_mode"] == "random_mm1")].iloc[0]
    pk_e7_jsq = df_sens[(df_sens["bloque"] == "Demanda Pico (+20%)") & (df_sens["escenario"] == "E7_4_Mix_UX") & (df_sens["routing_mode"] == "shortest_queue")].iloc[0]
    pk_e4_rnd = df_sens[(df_sens["bloque"] == "Demanda Pico (+20%)") & (df_sens["escenario"] == "E4_6_Mixtos") & (df_sens["routing_mode"] == "random_mm1")].iloc[0]

    p_e7_e2 = pair_idx.loc["E7_4_Mix_UX - E2_4_Mixtos"]
    p_e7_e3 = pair_idx.loc["E7_4_Mix_UX - E3_5_Mixtos"]
    p_e7_e4 = pair_idx.loc["E7_4_Mix_UX - E4_6_Mixtos"]

    tbl9_data = [
        ["IC Pareado CRN: E7 vs. E2 (4 Mix)", f"Δ = {p_e7_e2['delta_pareado']:+.3f} m", f"[{p_e7_e2['ic95_inf']:.2f}, {p_e7_e2['ic95_sup']:.2f}]", f"p = {p_e7_e2['p_valor']:.4f} (signif.)"],
        ["IC Pareado CRN: E7 vs. E3 (5 Mix)", f"Δ = {p_e7_e3['delta_pareado']:+.3f} m", f"[{p_e7_e3['ic95_inf']:.2f}, {p_e7_e3['ic95_sup']:.2f}]", f"p = {p_e7_e3['p_valor']:.4f} (signif.)"],
        ["IC Pareado CRN: E7 vs. E4 (6 Mix)", f"Δ = {p_e7_e4['delta_pareado']:+.3f} m", f"[{p_e7_e4['ic95_inf']:.2f}, {p_e7_e4['ic95_sup']:.2f}]", f"W(E7) < W(E4) en sistema"],
        ["Barrido UX/LPR -15 % (4 Mixtos)", f"{ux_15_rnd['espera_wq_media_min']:.2f} m (JSQ {ux_15_jsq['espera_wq_media_min']:.2f})", f"W = {ux_15_rnd['sistema_w_media_min']:.2f} m", f"P(>5m) JSQ = {ux_15_jsq['prob_wq_mayor_5m_peor_cajero_pct']:.1f} %"],
        ["Barrido UX/LPR -30 % (4 Mixtos)", f"{ux_30_rnd['espera_wq_media_min']:.2f} m", f"W = {ux_30_rnd['sistema_w_media_min']:.2f} m", f"P(>5m) = {ux_30_rnd['prob_wq_mayor_5m_peor_cajero_pct']:.1f} % (≤ 20 %)"],
        ["Llegadas H4/H4/1 (Ca² = 1.257)", f"E1={h4_e1_rnd['espera_wq_media_min']:.2f} m | E7+JSQ={h4_e7_jsq['espera_wq_media_min']:.2f} m", f"E7 P(>5) JSQ={h4_e7_jsq['prob_wq_mayor_5m_peor_cajero_pct']:.1f} %", "Robusto bajo ráfagas"],
        ["Demanda Pico (+20 % λ): E7 vs. E4", f"E7={pk_e7_rnd['espera_wq_media_min']:.2f} m (JSQ {pk_e7_jsq['espera_wq_media_min']:.2f})", f"E4={pk_e4_rnd['espera_wq_media_min']:.2f} m", f"E7+JSQ P(>5)={pk_e7_jsq['prob_wq_mayor_5m_peor_cajero_pct']:.1f} %"],
    ]

    format_apa_table(
        doc,
        "Tabla 9",
        f"Síntesis de contrastes pareados CRN y análisis de sensibilidad Nivel B (N* = {n_off} réplicas)",
        [Inches(2.10), Inches(1.75), Inches(1.30), Inches(1.35)],
        ["Experimento / Contraste", "Resultado W_{q}", "IC 95 % / Métrica W", "Hallazgo clave"],
        tbl9_data,
        f"Sensibilidad paramétrica ejecutada con {n_off} réplicas CRN (base E7 -25 % UX = {ux_25_rnd['espera_wq_media_min']:.2f} m). Incluso ante +20 % de demanda o arribos H4/H4/1, E7 con JSQ mantiene W_{{q}} < 1 min.",
        font_size=7.4,
    )

    tbl10_data = [
        ["E3: 5 Mixtos (+2 quioscos)", "+2 cajeros físicos", "Alto (~USD 24k–36k)", "Medio (+mantenimiento x2)", f"Wq {wq_e3:.2f} m (JSQ {wq_e3_jsq:.2f} m)"],
        ["E4: 6 Mixtos (REDUNDANTE)", "+3 cajeros físicos", "Muy alto (~USD 36k–54k)", f"Alto ({ocio_e4:.1f} % ocio)", f"Wq {wq_e4:.2f} m (W {w_e4:.2f} m)"],
        ["E7: 4 Mix + UX/LPR (+JSQ)", "+1 quiosco + LPR/QR + pantalla", "Moderado (~USD 16k–23k)", "Bajo (1 equipo + software)", f"Wq {wq_e7:.2f} m (JSQ {wq_e7_jsq:.2f} m; W {w_e7:.2f} m)"],
    ]

    format_apa_table(
        doc,
        "Tabla 10",
        "Evaluación ilustrativa costo-beneficio CAPEX/OPEX frente a desempeño simulado por salida",
        [Inches(1.50), Inches(1.40), Inches(1.20), Inches(1.15), Inches(1.25)],
        ["Alternativa", "Alcance de inversión", "CAPEX referencial", "OPEX relativo", "Desempeño esperado"],
        tbl10_data,
        "Los rangos CAPEX/OPEX son estimaciones ilustrativas de referencia en ingeniería de quioscos comerciales LPR/QR por punto de salida (sujetos a cotización local del proveedor).",
        font_size=7.3,
    )

    # =========================================================
    # 4. CONCLUSIONES Y RECOMENDACIONES
    # =========================================================
    add_h1("4. Conclusiones y Recomendaciones")
    add_numbered_item(
        "1.",
        "Insuficiencia de los tres cajeros actuales: ",
        f"Tres cajeros por salida no alcanzan para la operación de Supercentro. La espera promedio llega a {wq_e1:.2f} minutos ({wq_ss_e1:.2f} minutos en "
        f"estado estable), el tiempo total sube a {w_e1:.2f} minutos y el {p5_e1_glob:.1f} % global ({p5_e1_peor:.1f} % en el peor servidor) espera más de "
        f"cinco minutos.",
    )
    add_numbered_item(
        "2.",
        "Estabilidad muestral N* y simetría entre cajeros (Punto A): ",
        f"Con la regla secuencial causal de Law y Kelton trabajamos con N^{{*}} = {n_off} réplicas, logrando ER(W_{{q}}) = {er_wq_e1:.2f} % y ER(W) = "
        f"{er_w_e1:.2f} %. Aunque en la muestra el {c_min_w['cajero']} marcó {c_min_w['atencion_w_prom']:.3f} minutos y el {c_max_w['cajero']} llegó a "
        f"{c_max_w['atencion_w_prom']:.3f} minutos (con servicio global cercano a {s_e1:.3f} minutos), las pruebas pareadas dan p ≥ {p_sym_min:.3f} y "
        f"confirman que los tres cajeros trabajan de forma simétrica.",
    )
    add_numbered_item(
        "3.",
        "Desbalance de carga por perfiles lentos (Punto B): ",
        f"Por la salida pasan en promedio {tot_veh_jornada:.2f} vehículos por jornada ({usr_idx.loc['Rápido', 'promedio_total_3_cajeros']:.2f} Rápido, "
        f"{usr_idx.loc['Normal', 'promedio_total_3_cajeros']:.2f} Normal, {usr_idx.loc['Lento', 'promedio_total_3_cajeros']:.2f} Lento y "
        f"{usr_idx.loc['Muy lento', 'promedio_total_3_cajeros']:.2f} Muy lento). Aunque los usuarios lentos y muy lentos suman el {slow_emp_arr:.2f} % de "
        f"las visitas, consumen el {slow_theo_load:.1f} % de la carga teórica de servicio y el {slow_emp_load:.2f} % de la carga empírica.",
    )
    add_numbered_item(
        "4.",
        "Estrategia recomendada (Punto C): ",
        f"Se descartan las filas segregadas (E5 y E6) por pérdida de consolidación y también el escenario E4 de seis mixtos por resultar REDUNDANTE con "
        f"{ocio_e4:.1f} % de tiempo ocioso. La mejor opción es E7 (cuatro cajeros mixtos con lectura automática LPR/QR), que baja la espera a {wq_e7:.2f} "
        f"minutos (W = {w_e7:.2f} minutos), cae a {wq_e7_jsq:.2f} minutos con señalización JSQ ({p5_e7_jsq:.1f} % sobre cinco minutos) o a {wq_e7_mgc:.2f} "
        f"minutos con cola única M/G/c, y, con señalización JSQ, aguanta un aumento de +20 % en demanda pico (W_{{q}} = {float(pk_e7_jsq['espera_wq_media_min']):.2f} min) con menor CAPEX y OPEX.",
    )
    add_numbered_item(
        "5.",
        "Verificación, validación y ajuste MSER-5 (Puntos D y E): ",
        f"El modelo pasó 25 pruebas unitarias, la auditoría continua de Little con residuo menor a 10^{{-10}}, la calibración χ^{{2}} con p = {chi2_pv:.3f} "
        f"y las pruebas t bilaterales frente a M/G/1 (sin rechazar H_{{0}}, α = 0.05) tanto a 1000 minutos (p ∈ [{p_min_mg1:.3f}, {p_max_mg1:.3f}]) como a 5000 minutos "
        f"(p ∈ [{p_min_5k:.3f}, {p_max_5k:.3f}]). Aplicar el corte MSER-5 en E1 tras k^{{*}} = {k_cut_e1} vehículos corrige la subestimación inicial del "
        f"{sesgo_e1:.2f} % (incremento real de +{incr_e1:.2f} %).",
    )
    add_numbered_item(
        "6.",
        "Limitaciones y mejoras futuras: ",
        "El simulador asume demanda estable durante 1000 minutos y cero abandonos en fila. Como trabajo futuro conviene modelar franjas de hora pico con "
        "llegadas no homogéneas (NHPP) e incluir pagos desde aplicación móvil fuera del quiosco.",
    )

    # =========================================================
    # REFERENCIAS (APA 7 SIN PARAFRASEAR DATOS ORIGINALES)
    # =========================================================
    add_h1("Referencias")
    referencias_apa7 = [
        [("Banks, J., Carson, J. S., II, Nelson, B. L., & Nicol, D. M. (2010). ", False), ("Discrete-event system simulation", True), (" (5th ed.). Pearson.", False)],
        [("Gross, D., Shortle, J. F., Thompson, J. M., & Harris, C. M. (2008). ", False), ("Fundamentals of queueing theory", True), (" (4th ed.). John Wiley & Sons.", False)],
        [("Kleinrock, L. (1975). ", False), ("Queueing systems: Vol. 1. Theory", True), (". John Wiley & Sons.", False)],
        [("Law, A. M. (2015). ", False), ("Simulation modeling and analysis", True), (" (5th ed.). McGraw-Hill Education.", False)],
        [("Little, J. D. C. (1961). A proof for the queuing formula: L = λ W. ", False), ("Operations Research, 9", True), ("(3), 383–387. https://doi.org/10.1287/opre.9.3.383", False)],
        [("Ross, S. M. (2014). ", False), ("Introduction to probability models", True), (" (11th ed.). Academic Press.", False)],
        [("White, K. P. (1997). An effective truncation heuristic for bias reduction in simulation output. ", False), ("Simulation, 69", True), ("(6), 323–334. https://doi.org/10.1177/003754979706900601", False)],
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
    add_h1("Anexo A: Estructura Completa del Repositorio y Reproducibilidad")
    add_p(
        "El proyecto se entrega como paquete modular en Python, suite de 25 pruebas unitarias, cuaderno Google Colab pre-ejecutado y "
        "resultados auditables exportados en results/:",
        space_after=4.0,
    )
    tree = [
        "Simulacion-Parqueadero-Supercentro-MM1/",
        "  parking_queue/",
        "    __init__.py ............. <- Exportación pública del paquete",
        "    model.py ................ <- M/M/1, M/H4/1, SeedSequence, H4 arrivals y regímenes",
        "    simulation.py ........... <- DES (Law-Kelton N*, ∫Q(t)dt, MSER-5, JSQ, M/G/c, CRN)",
        "    visualizations.py ....... <- Generador de 7 figuras científicas a 300 DPI",
        "  tests/",
        "    __init__.py",
        "    test_parking_queue.py ... <- Suite de 25 pruebas unitarias de código e invariantes",
        "  results/ .................. <- 17 tablas CSV y 7 figuras PNG (300 DPI)",
        "  main.py ................... <- Orquestador experimental completo",
        "  create_colab_notebook.py .. <- Generador, ejecutor y verificador de paridad vs. CSV",
        "  Simulacion_Parqueadero_Supercentro_Colab.ipynb <- Cuaderno Colab autocontenido",
        "  generate_doc.py ........... <- Generador dinámico APA 7 del informe Word",
        "  Palacios_Camilo_problemaParqueadero.docx       <- Informe oficial APA 7",
        "  GUION_VIDEO_SUSTENTACION.md, README.md, requirements.txt, LICENSE",
    ]
    for idx_t, line in enumerate(tree):
        pt = doc.add_paragraph()
        pt.paragraph_format.left_indent = Inches(0.18)
        pt.paragraph_format.space_before = Pt(0)
        pt.paragraph_format.space_after = Pt(5 if idx_t == len(tree) - 1 else 0.5)
        pt.paragraph_format.line_spacing = 1.03
        rl = pt.add_run(line)
        rl.font.name = "Consolas"
        rl.font.size = Pt(7.6)
        rl.font.color.rgb = COLOR_PRIMARY

    add_h1("Anexo B: Video de Sustentación")
    p_vid = doc.add_paragraph()
    p_vid.paragraph_format.left_indent = Inches(0.20)
    p_vid.paragraph_format.space_after = Pt(4)
    p_vid.paragraph_format.line_spacing = 1.1
    add_rich_runs(p_vid, "Enlace del video (2:33 min): ", font_size=9.8, color=COLOR_PRIMARY, bold=True)
    add_rich_runs(p_vid, "https://youtu.be/ix6PkWOdiRA", font_name="Consolas", font_size=8.8, color=COLOR_SECONDARY, bold=True)
    add_p(
        f"El libreto cronometrado en GUION_VIDEO_SUSTENTACION.md resume la transición M/M/1 a M/H4/1, la detección causal Law y Kelton (N^{{*}} = {n_off} "
        f"réplicas), Puntos A y B, la estrategia 4 Mixtos + UX/LPR con JSQ y cola única M/G/c (Punto C), V&V con 5000 min (Punto D) y MSER-5 tras "
        f"k^{{*}} = {k_cut_e1} arribos (Punto E)."
    )

    add_h1("Anexo C: Declaración de Uso Ético de IA y Bitácora Usa–Modifica–Crea")
    add_p(
        "En coherencia con el marco ético institucional de la asignatura, declaramos el apoyo de herramientas de inteligencia artificial generativa "
        "para codificación auxiliar en Python, depuración de pruebas, estructuración gráfica y verificación automatizada de consistencia, siempre bajo "
        "diseño, validación matemática y revisión técnica por pares del Grupo 25:"
    )
    add_bullet(
        "Usa: ",
        "partimos de las tablas oficiales de parámetros de Supercentro y la base arquitectónica DES verificada en modelos de colas.",
    )
    add_bullet(
        "Modifica: ",
        "adaptamos el horizonte a 1000 minutos y 5000 minutos estacionarios, sustituimos semillas lineales por SeedSequence([base, flujo, r]) "
        "bajo CRN completos e implementamos sin dependencias externas cuantiles t de Student, χ² e integrador continuo ∫Q(t)dt para Little.",
    )
    add_bullet(
        "Crea: ",
        "desarrollamos el detector causal sin look-ahead de Law y Kelton (N*), la detección MSER-5 con Welch centrado (Punto E), el simulador "
        "comparativo paralelo/JSQ/cola única M/G/c, el análisis de sensibilidad H4/H4/1–UX–Pico+20 %, los contrastes pareados CRN, la suite "
        "de 25 pruebas unitarias de invariantes y la verificación cruzada en create_colab_notebook.py contra los CSVs oficiales.",
    )
    add_bullet(
        "Responsabilidad y validación del equipo: ",
        "el Grupo 25 definió el modelado M/M/1 y M/H4/1, estableció los cinco criterios cuantitativos de decisión y escenarios de mejora, verificó "
        "manualmente las fórmulas analíticas y salidas CSV frente al cuaderno Colab y el informe, y validó por pares la interpretación final y su sustentación.",
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
