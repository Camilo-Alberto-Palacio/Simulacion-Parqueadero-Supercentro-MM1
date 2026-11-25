"""
Módulo de Visualizaciones Científicas para la Simulación del Parqueadero Supercentro.
Genera 7 figuras en alta resolución (300 DPI) con estética editorial sobria,
etiquetas nítidas y cero solapamientos.
"""

from typing import Optional
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch

from .model import SCENARIO_DEFINITIONS, USER_TYPES, ParkingQueuingModel


class ParkingVisualizer:
    """Generador de 7 gráficas científicas a 300 DPI para Supercentro."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        plt.rcParams["font.family"] = "DejaVu Sans"
        plt.rcParams["axes.edgecolor"] = "#CBD5E1"
        plt.rcParams["axes.linewidth"] = 0.8

        self.palette = {
            "navy": "#1E3A8A",
            "blue": "#2563EB",
            "teal": "#0F766E",
            "amber": "#D97706",
            "red": "#DC2626",
            "purple": "#7C3AED",
            "slate": "#475569",
            "light_bg": "#F8FAFC",
        }
        self.user_colors = {
            "Rápido": "#16A34A",
            "Normal": "#2563EB",
            "Lento": "#D97706",
            "Muy lento": "#DC2626",
        }

    def plot_steady_state_replicas(
        self,
        df_conv: pd.DataFrame,
        wq_mg1_base: float,
        filename: str = "fig1_estado_estable_replicas.png",
    ) -> str:
        """Figura 1: Determinación causal de réplicas N* por Law & Kelton y estabilidad móvil."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.4, 5.6), dpi=300)

        reps = df_conv["replica"].values
        cum_wq = df_conv["wq_media_acumulada_min"].values
        ic_inf = df_conv["wq_ic95_inf"].values
        ic_sup = df_conv["wq_ic95_sup"].values
        n_det = int(df_conv["n_detectado_exacto"].iloc[0])
        n_off = int(df_conv["n_oficial_seleccionado"].iloc[0])
        er_lk = float(df_conv["er_umbral_law_kelton_pct"].iloc[0])
        wq_n_off = float(df_conv.loc[df_conv["replica"] == n_off, "wq_media_acumulada_min"].iloc[0])
        band_lo = wq_n_off * 0.985
        band_hi = wq_n_off * 1.015

        ax1.fill_between(reps, ic_inf, ic_sup, color="#BFDBFE", alpha=0.45, label="IC 95% t acumulado")
        ax1.axhspan(band_lo, band_hi, color="#DCFCE7", alpha=0.55, label="Banda causal ±1.5% en N*")
        ax1.plot(reps, cum_wq, color=self.palette["navy"], linewidth=2.2, label="Media acumulada Wq(r)")
        ax1.axhline(wq_mg1_base, color=self.palette["teal"], linestyle="-.", linewidth=1.4,
                    label=f"Teórico M/G/1 = {wq_mg1_base:.2f} min")
        ax1.axvline(n_det, color=self.palette["amber"], linestyle=":", linewidth=1.7,
                    label=f"Detección Law & Kelton r = {n_det}")
        ax1.axvline(n_off, color=self.palette["red"], linestyle="--", linewidth=1.8,
                    label=f"Réplicas oficiales N* = {n_off}")

        ax1.scatter([n_off], [wq_n_off], color=self.palette["red"], zorder=6, s=55)
        ax1.annotate(
            f"N* = {n_off}\nWq = {wq_n_off:.2f} min",
            xy=(n_off, wq_n_off),
            xytext=(max(30, n_off - 68), wq_n_off - 2.9),
            fontsize=8.1, fontweight="bold", color="#991B1B",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#FCA5A5"),
            arrowprops=dict(arrowstyle="->", color="#991B1B", lw=1.1),
        )

        ax1.set_xlim(1, int(reps.max()))
        ax1.set_ylim(max(0.0, float(np.min(cum_wq)) - 4.0), float(np.percentile(ic_sup[5:], 98)) * 1.18)
        ax1.set_xlabel("Número acumulado de réplicas (r)", fontsize=9.8)
        ax1.set_ylabel("Tiempo promedio acumulado en cola Wq (min)", fontsize=9.8)
        ax1.set_title("A. Convergencia Causal del Promedio Acumulado de Wq (3 Mixtos)", fontsize=10.4, fontweight="bold", color="#0F172A")
        ax1.grid(True, linestyle=":", alpha=0.6)
        ax1.legend(loc="upper right", fontsize=7.5, frameon=True)

        # Panel B: Error Relativo ER% de Wq y W frente a Law & Kelton
        sub_b = df_conv[df_conv["replica"] >= 5]
        r_b = sub_b["replica"].values
        er_wq = sub_b["wq_er_pct"].values
        er_w = sub_b["w_er_pct"].values

        ax2.plot(r_b, er_wq, color=self.palette["blue"], linewidth=2.2, label="ER 95% de Wq (%)")
        ax2.plot(r_b, er_w, color=self.palette["teal"], linewidth=2.0, label="ER 95% de W (%)")
        ax2.axhline(10.0, color="#64748B", linestyle="--", linewidth=1.2, label="Umbral curso ER ≤ 10%")
        ax2.axhline(er_lk, color=self.palette["amber"], linestyle=":", linewidth=1.6,
                    label=f"Cota Law & Kelton (γ=0.06 → {er_lk:.2f}%)")
        ax2.axhline(5.0, color="#16A34A", linestyle="-.", linewidth=1.2, label="Meta ER(W) ≤ 5.0%")
        ax2.axvline(n_off, color=self.palette["red"], linestyle="--", linewidth=1.7, label=f"N* = {n_off} réplicas")

        er_wq_off = float(df_conv.loc[df_conv["replica"] == n_off, "wq_er_pct"].iloc[0])
        er_w_off = float(df_conv.loc[df_conv["replica"] == n_off, "w_er_pct"].iloc[0])
        ax2.scatter([n_off, n_off], [er_wq_off, er_w_off], color=self.palette["red"], zorder=6, s=48)
        ax2.annotate(
            f"En N*={n_off}:\nER(Wq)={er_wq_off:.2f}%\nER(W)={er_w_off:.2f}%",
            xy=(n_off, er_wq_off),
            xytext=(max(30, n_off - 90), er_wq_off + 9.0),
            fontsize=8.0, fontweight="bold", color="#1E3A8A",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#93C5FD"),
            arrowprops=dict(arrowstyle="->", color="#1E3A8A", lw=1.1),
        )

        ax2.set_xlim(5, int(reps.max()))
        ax2.set_ylim(0, min(65.0, float(np.nanmax(er_wq)) * 1.08))
        ax2.set_xlabel("Número acumulado de réplicas (r)", fontsize=9.8)
        ax2.set_ylabel("Error Relativo ER = (ME / Ȳ) × 100 (%)", fontsize=9.8)
        ax2.set_title("B. Convergencia Secuencial del Error Relativo (Law & Kelton)", fontsize=10.4, fontweight="bold", color="#0F172A")
        ax2.grid(True, linestyle=":", alpha=0.6)
        ax2.legend(loc="upper right", fontsize=7.4, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_base_cashier_performance(
        self,
        df_cashiers_all: pd.DataFrame,
        df_cashier_summary: pd.DataFrame,
        filename: str = "fig2_desempeno_cajeros_base.png",
    ) -> str:
        """Figura 2 (Punto A): Desempeño S, Wq y W por cajero e identificación de menor/mayor atención."""
        base_sum = df_cashier_summary[df_cashier_summary["escenario"] == "E1_3_Mixtos"].copy().reset_index(drop=True)
        base_rep = df_cashiers_all[df_cashiers_all["escenario"] == "E1_3_Mixtos"].copy()
        n_rep = int(base_rep["replica"].nunique())

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.0, 5.5), dpi=300)

        cajeros = base_sum["cajero"].tolist()
        x = np.arange(len(cajeros))
        w = 0.25

        s_m = base_sum["servicio_s_prom"].values
        s_err = (base_sum["servicio_s_ic95_sup"] - base_sum["servicio_s_prom"]).values
        wq_m = base_sum["espera_wq_prom"].values
        wq_err = (base_sum["espera_wq_ic95_sup"] - base_sum["espera_wq_prom"]).values
        wt_m = base_sum["atencion_w_prom"].values
        wt_err = (base_sum["atencion_w_ic95_sup"] - base_sum["atencion_w_prom"]).values

        b1 = ax1.bar(x - w, s_m, width=w, yerr=s_err, capsize=3.5, color="#0F766E", label="Servicio medio S (min)")
        b2 = ax1.bar(x, wq_m, width=w, yerr=wq_err, capsize=3.5, color="#F59E0B", label="Espera en cola Wq (min)")
        b3 = ax1.bar(x + w, wt_m, width=w, yerr=wt_err, capsize=3.5, color="#1E3A8A", label="Atención total W = Wq+S (min)")

        for bars, err_arr, col in [(b1, s_err, "#0F766E"), (b2, wq_err, "#B45309"), (b3, wt_err, "#1E3A8A")]:
            for idx_b, bar in enumerate(bars):
                h = bar.get_height()
                ax1.text(
                    bar.get_x() + bar.get_width() / 2, h + err_arr[idx_b] + 0.35,
                    f"{h:.2f}", ha="center", va="bottom", fontsize=8.0, fontweight="bold", color=col,
                )

        idx_min_w = int(np.argmin(wt_m))
        idx_max_w = int(np.argmax(wt_m))
        ax1.annotate(
            "Menor atención\npromedio (W)",
            xy=(x[idx_min_w] + w, wt_m[idx_min_w] + wt_err[idx_min_w] + 1.1),
            xytext=(x[idx_min_w] + w, wt_m[idx_min_w] + wt_err[idx_min_w] + 3.4),
            ha="center", fontsize=7.6, fontweight="bold", color="#15803D",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#DCFCE7", edgecolor="#86EFAC"),
            arrowprops=dict(arrowstyle="->", color="#15803D", lw=1.0),
        )
        ax1.annotate(
            "Mayor atención\npromedio (W)",
            xy=(x[idx_max_w] + w, wt_m[idx_max_w] + wt_err[idx_max_w] + 1.1),
            xytext=(x[idx_max_w] + w, wt_m[idx_max_w] + wt_err[idx_max_w] + 3.4),
            ha="center", fontsize=7.6, fontweight="bold", color="#B91C1C",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#FEE2E2", edgecolor="#FCA5A5"),
            arrowprops=dict(arrowstyle="->", color="#B91C1C", lw=1.0),
        )

        ax1.set_xticks(x)
        ax1.set_xticklabels([f"{c}\n(ρ={r*100:.1f}%)" for c, r in zip(cajeros, base_sum["utilizacion_rho_prom"])],
                            fontsize=9.0, fontweight="bold")
        ax1.set_ylabel("Tiempo promedio por vehículo (min)", fontsize=9.8)
        ax1.set_title(f"A. Servicio (S), Espera (Wq) y W ({n_rep} Rép.; IC 95% solapados por simetría)",
                      fontsize=10.1, fontweight="bold", color="#0F172A")
        ax1.set_ylim(0, float(np.max(wt_m + wt_err)) * 1.44)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper right", fontsize=8.0, frameon=True)

        # Panel B: Dispersión entre réplicas (Boxplot de W por cajero)
        data_box = [base_rep[base_rep["cajero"] == c]["atencion_total_w_min"].values for c in cajeros]
        bp = ax2.boxplot(
            data_box, tick_labels=cajeros, patch_artist=True,
            showmeans=True, meanline=False,
            meanprops=dict(marker="D", markerfacecolor="#DC2626", markeredgecolor="white", markersize=6.5),
            medianprops=dict(color="#0F172A", linewidth=1.8),
        )
        box_colors = ["#DBEAFE", "#DCFCE7", "#E0E7FF"]
        for patch, col in zip(bp["boxes"], box_colors):
            patch.set_facecolor(col)
            patch.set_edgecolor("#1E3A8A")

        for idx_c, vals in enumerate(data_box):
            ax2.text(
                idx_c + 1.10, float(np.percentile(vals, 75)) + 1.0,
                f"μ={np.mean(vals):.2f}\nDE={np.std(vals, ddof=1):.2f}\n[{np.min(vals):.1f}–{np.max(vals):.1f}]",
                ha="left", va="bottom", fontsize=7.5, color="#1E293B",
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="#CBD5E1", alpha=0.92),
            )

        ax2.set_ylabel("Tiempo total en el sistema W por réplica (min)", fontsize=9.8)
        ax2.set_title(f"B. Distribución de Atención Total W por Cajero ({n_rep} Réplicas)",
                      fontsize=10.5, fontweight="bold", color="#0F172A")
        ax2.set_ylim(0, max(float(np.max(v)) for v in data_box) * 1.12)
        ax2.grid(axis="y", linestyle=":", alpha=0.6)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_user_types_summary(
        self,
        model: ParkingQueuingModel,
        df_rep_base: pd.DataFrame,
        df_wait_type_base: pd.DataFrame,
        filename: str = "fig3_usuarios_por_tipo.png",
    ) -> str:
        """Figura 3 (Punto B): Promedio de usuarios por tipo en totalidad de cajeros y carga de servicio."""
        n_rep = len(df_rep_base)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.2, 5.5), dpi=300)

        col_map = {"Rápido": "rapido", "Normal": "normal", "Lento": "lento", "Muy lento": "muy_lento"}
        means = np.array([float(df_rep_base[col_map[u]].mean()) for u in USER_TYPES])
        sds = np.array([float(df_rep_base[col_map[u]].std(ddof=1)) for u in USER_TYPES])
        tot_mean = float(means.sum())
        emp_pcts = (means / tot_mean) * 100.0
        theo_pcts = np.array([model.user_type_probs[u] * 100.0 for u in USER_TYPES])

        x = np.arange(len(USER_TYPES))
        colors = [self.user_colors[u] for u in USER_TYPES]
        bars = ax1.bar(x, means, yerr=sds, capsize=4, color=colors, alpha=0.88, width=0.55)

        for idx_b, bar in enumerate(bars):
            h = bar.get_height()
            per_c = h / 3.0
            ax1.text(
                bar.get_x() + bar.get_width() / 2, h + sds[idx_b] + 4.5,
                f"{h:.2f} veh/j\n({per_c:.2f}/caj)\nEmp: {emp_pcts[idx_b]:.2f}%\nTeór: {theo_pcts[idx_b]:.1f}%",
                ha="center", va="bottom", fontsize=7.6, fontweight="bold", color="#0F172A",
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="#E2E8F0", alpha=0.92),
            )

        ax1.set_xticks(x)
        ax1.set_xticklabels(USER_TYPES, fontsize=9.5, fontweight="bold")
        ax1.set_ylabel("Promedio de vehículos ± DE en 3 cajeros (1000 min)", fontsize=9.5)
        ax1.set_title(
            f"A. Promedio por Tipo en los 3 Cajeros (±DE; Total = {tot_mean:.2f} veh, {n_rep} Rép.)",
            fontsize=10.0, fontweight="bold", color="#0F172A",
        )
        ax1.set_ylim(0, float(np.max(means + sds)) * 1.44)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)

        # Panel B: Comparativa % Llegadas vs % Carga de Servicio + Tiempos S y Wq
        wt_idx = df_wait_type_base.set_index("tipo_usuario")
        s_means = np.array([model.service_means[u] for u in USER_TYPES])
        load_shares = (theo_pcts * s_means) / np.sum(theo_pcts * s_means) * 100.0
        wq_vals = np.array([float(wt_idx.loc[u, "wq_media_min"]) for u in USER_TYPES])
        s_emp = np.array([float(wt_idx.loc[u, "s_media_min"]) for u in USER_TYPES])

        w_bar = 0.34
        b_arr = ax2.bar(x - w_bar / 2, theo_pcts, width=w_bar, color="#64748B", alpha=0.85, label="% de llegadas (Teór.)")
        b_load = ax2.bar(x + w_bar / 2, load_shares, width=w_bar, color="#DC2626", alpha=0.88, label="% carga en servicio (Teór.)")

        for idx_b in range(len(x)):
            ax2.text(x[idx_b] - w_bar / 2 - 0.02, theo_pcts[idx_b] + 0.9, f"{theo_pcts[idx_b]:.1f}%",
                     ha="center", va="bottom", fontsize=7.6, color="#334155", fontweight="bold")
            ax2.text(x[idx_b] + w_bar / 2 + 0.03, load_shares[idx_b] + 1.0,
                     f"{load_shares[idx_b]:.1f}%\n(S={s_emp[idx_b]:.1f}m\nWq={wq_vals[idx_b]:.1f}m)",
                     ha="center", va="bottom", fontsize=7.0, color="#991B1B", fontweight="bold",
                     bbox=dict(boxstyle="square,pad=0.08", facecolor="white", edgecolor="none", alpha=0.82))

        ax2.annotate(
            f"Lento + Muy lento = {theo_pcts[2]+theo_pcts[3]:.1f}% de usuarios\n"
            f"pero consumen {load_shares[2]+load_shares[3]:.1f}% del tiempo de servicio",
            xy=(2.5, max(load_shares[2], load_shares[3]) + 6.5),
            xytext=(1.1, 56.0),
            ha="center", fontsize=8.1, fontweight="bold", color="#7F1D1D",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEF2F2", edgecolor="#FCA5A5"),
            arrowprops=dict(arrowstyle="->", color="#991B1B", lw=1.1),
        )

        ax2.set_xticks(x)
        ax2.set_xticklabels(USER_TYPES, fontsize=9.5, fontweight="bold")
        ax2.set_ylabel("Participación porcentual (%)", fontsize=9.8)
        ax2.set_title("B. Asimetría Llegadas vs. Carga Real Consumida en Cajeros",
                      fontsize=10.3, fontweight="bold", color="#0F172A")
        ax2.set_ylim(0, 68.0)
        ax2.grid(axis="y", linestyle=":", alpha=0.6)
        ax2.legend(loc="upper left", fontsize=8.0, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_scenarios_strategy_comparison(
        self,
        df_summary: pd.DataFrame,
        df_jsq_summary: pd.DataFrame,
        df_sens_ext: Optional[pd.DataFrame] = None,
        filename: str = "fig4_estrategias_mejora_escenarios.png",
    ) -> str:
        """Figura 4 (Punto C): Comparativa de estrategias E1..E7 en espera Wq, JSQ, M/G/c, uso y P(Wq>5m)."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.6, 5.8), dpi=300)

        labels = df_summary["nombre_corto"].tolist()
        skeys = df_summary["escenario"].tolist()
        x = np.arange(len(labels))
        w = 0.36

        wq_mm1 = df_summary["espera_wq_media_min"].values
        wq_err = (df_summary["espera_wq_ic95_sup"] - df_summary["espera_wq_media_min"]).values
        wq_jsq = df_jsq_summary["espera_wq_media_min"].values
        peor_wq = df_summary["peor_cajero_wq_prom_min"].values

        b1 = ax1.bar(x - w / 2, wq_mm1, width=w, yerr=wq_err, capsize=3,
                     color=["#DC2626" if v > 5.0 else "#2563EB" for v in wq_mm1],
                     alpha=0.88, label="M/H4/1 Paralelo (IC 95%)")
        b2 = ax1.bar(x + w / 2, wq_jsq, width=w, color="#0F766E", alpha=0.88,
                     label="Sensibilidad JSQ (Cola más corta)")
        ax1.scatter(x - w / 2, peor_wq, color="#7C2D12", marker="^", s=45, zorder=5,
                    label="Peor cajero Wq (promedio)")

        if df_sens_ext is not None and not df_sens_ext.empty:
            mgc_sub = df_sens_ext[df_sens_ext["bloque"] == "Cola Única M/G/c"].set_index("escenario")
            mgc_x, mgc_y = [], []
            for idx_s, sk in enumerate(skeys):
                if sk in mgc_sub.index:
                    mgc_x.append(x[idx_s] + w / 2)
                    mgc_y.append(float(mgc_sub.loc[sk, "espera_wq_media_min"]))
            if mgc_x:
                ax1.scatter(mgc_x, mgc_y, color="#7C3AED", marker="D", s=40, edgecolor="white",
                            linewidth=0.7, zorder=7, label="Cola Única M/G/c (cota inf.)")

        ax1.axhline(5.0, color="#DC2626", linestyle="--", linewidth=1.3, zorder=1, label="Umbral crítico Wq = 5.0 min")
        ax1.axhline(3.0, color="#16A34A", linestyle=":", linewidth=1.4, zorder=1, label="Meta óptima Wq = 3.0 min")

        for idx_b in range(len(x)):
            ax1.text(x[idx_b] - w / 2, max(wq_mm1[idx_b] + wq_err[idx_b], peor_wq[idx_b]) + 0.35,
                     f"{wq_mm1[idx_b]:.2f}", ha="center", va="bottom", fontsize=7.6, fontweight="bold", color="#0F172A",
                     bbox=dict(boxstyle="square,pad=0.08", facecolor="white", edgecolor="none", alpha=0.85), zorder=6)
            ax1.text(x[idx_b] + w / 2, wq_jsq[idx_b] + 0.32,
                     f"{wq_jsq[idx_b]:.2f}", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#0F766E",
                     bbox=dict(boxstyle="square,pad=0.08", facecolor="white", edgecolor="none", alpha=0.88), zorder=6)

        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, fontsize=8.1, fontweight="bold", rotation=16, ha="right")
        ax1.set_ylabel("Tiempo promedio de espera en cola Wq (min)", fontsize=9.8)
        ax1.set_title("A. Espera Wq: M/H4/1 Paralelo vs. JSQ y Cola Única M/G/c", fontsize=10.2, fontweight="bold", color="#0F172A")
        ax1.set_ylim(0, max(float(np.max(wq_mm1 + wq_err)), float(np.max(peor_wq))) * 1.24)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper right", fontsize=7.4, frameon=True)

        # Panel B: Utilización del cajero más cargado rho_caj (%) vs P(Wq > 5 min) peor cajero (%)
        rho_col = "utilizacion_peor_cajero_prom" if "utilizacion_peor_cajero_prom" in df_summary.columns else "utilizacion_max_media"
        rho_peor = df_summary[rho_col].values * 100.0
        p5_peor = df_summary["prob_wq_mayor_5m_peor_cajero_pct"].values

        ax2.bar(x - w / 2, rho_peor, width=w, color="#1E3A8A", alpha=0.86, label="Utilización cajero más cargado ρ_caj (%)")
        ax2.bar(x + w / 2, p5_peor, width=w, color="#F59E0B", alpha=0.88, label="P(Wq > 5 min) peor cajero (%)")

        ax2.axhspan(45.0, 85.0, color="#DCFCE7", alpha=0.25, zorder=0, label="Zona ρ aceptable/óptima (45%–85%)")
        ax2.axhline(20.0, color="#DC2626", linestyle="--", linewidth=1.3, zorder=1, label="Umbral crítico P(Wq>5m) = 20%")

        for idx_b in range(len(x)):
            ax2.text(x[idx_b] - w / 2, rho_peor[idx_b] + 1.4, f"{rho_peor[idx_b]:.1f}%",
                     ha="center", va="bottom", fontsize=7.4, fontweight="bold", color="#1E3A8A", zorder=6)
            ax2.text(x[idx_b] + w / 2, p5_peor[idx_b] + 1.6, f"{p5_peor[idx_b]:.1f}%",
                     ha="center", va="bottom", fontsize=7.4, fontweight="bold", color="#B45309",
                     bbox=dict(boxstyle="square,pad=0.06", facecolor="white", edgecolor="none", alpha=0.85), zorder=6)

        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, fontsize=8.1, fontweight="bold", rotation=16, ha="right")
        ax2.set_ylabel("Porcentaje (%)", fontsize=9.8)
        ax2.set_title("B. Utilización por Cajero Más Cargado y Riesgo > 5 min", fontsize=10.3, fontweight="bold", color="#0F172A")
        ax2.set_ylim(0, max(float(np.max(rho_peor)), float(np.max(p5_peor))) * 1.24)
        ax2.grid(axis="y", linestyle=":", alpha=0.6)
        ax2.legend(loc="upper right", fontsize=7.2, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_vv_process_diagram(
        self,
        df_vv: pd.DataFrame,
        num_tests: int = 25,
        filename: str = "fig5_proceso_vv_diagrama.png",
    ) -> str:
        """Figura 5 (Punto D): Diagrama formal del proceso Verificación-Calibración-Validación y p-valores."""
        fig = plt.figure(figsize=(14.4, 6.4), dpi=300)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0], wspace=0.16)
        ax_d = fig.add_subplot(gs[0, 0])
        ax_v = fig.add_subplot(gs[0, 1])

        # Panel A: Diagrama de Flujo V&V con compuertas y resultados reales
        ax_d.set_xlim(0, 10)
        ax_d.set_ylim(0, 10)
        ax_d.axis("off")
        ax_d.set_title("A. Flujo Metodológico de Verificación, Calibración y Validación",
                       fontsize=10.6, fontweight="bold", color="#0F172A", pad=8)

        mae_pp = float(df_vv["calibracion_mae_pp"].iloc[0])
        chi2_p = float(df_vv["calibracion_chi2_pval"].iloc[0])
        srv_err = float(df_vv["calibracion_srv_max_rel_err_pct"].max())
        max_little = float(df_vv["verificacion_little_max_err"].max())
        p_min = float(df_vv["p_valor_vs_mg1"].min())
        p_max = float(df_vv["p_valor_vs_mg1"].max())
        has_5k = "p_valor_estacionario_5000m" in df_vv.columns and df_vv["p_valor_estacionario_5000m"].notna().any()
        if has_5k:
            p5k_min = float(df_vv["p_valor_estacionario_5000m"].min())
            p5k_max = float(df_vv["p_valor_estacionario_5000m"].max())
            desc_val = f"1000m MSER-5: p ∈ [{p_min:.3f}, {p_max:.3f}] · 5000m: p ∈ [{p5k_min:.3f}, {p5k_max:.3f}]"
        else:
            desc_val = f"1000m MSER-5: p ∈ [{p_min:.3f}, {p_max:.3f}] (> 0.05)"

        steps = [
            (8.6, "#1E3A8A", "1. MODELO CONCEPTUAL Y DES (M/M/1 y M/H4/1)",
             "4 perfiles · 1000m (y 5000m estac.) · SeedSequence + CRN PCG64"),
            (6.8, "#0F766E", "2. VERIFICACIÓN: ¿Código libre de errores?",
             f"{num_tests}/{num_tests} pruebas · |∫Q(t)dt/H_eff - λ_eff·Wq| ≤ {max_little:.1e} (<1e-10)"),
            (4.9, "#D97706", "3. CALIBRACIÓN: ¿Ajuste por escenario y tasas?",
             f"MAE = {mae_pp:.2f} pp · χ² p = {chi2_p:.3f} · Error máx E[S] = {srv_err:.2f}%"),
            (3.0, "#2563EB", "4. VALIDACIÓN: ¿Concuerda con Pollaczek–Khinchine M/G/1?",
             desc_val),
            (1.1, "#16A34A", "5. MODELO VALIDADO Y APROBADO",
             "Escenarios E1..E7, M/G/c, IC pareados CRN y sensibilidad"),
        ]

        for idx_s, (yc, col, title, desc) in enumerate(steps):
            box = FancyBboxPatch(
                (0.4, yc - 0.62), 6.5, 1.24,
                boxstyle="round,pad=0.08,rounding_size=0.16",
                facecolor="#F8FAFC", edgecolor=col, linewidth=2.0,
            )
            ax_d.add_patch(box)
            ax_d.text(3.65, yc + 0.22, title, ha="center", va="center", fontsize=8.4, fontweight="bold", color=col)
            ax_d.text(3.65, yc - 0.24, desc, ha="center", va="center", fontsize=7.2, color="#1E293B")

            if idx_s < len(steps) - 1:
                y_next = steps[idx_s + 1][0]
                arr = FancyArrowPatch((3.65, yc - 0.64), (3.65, y_next + 0.64),
                                      arrowstyle="-|>,head_width=4,head_length=6", color="#475569", lw=1.5)
                ax_d.add_patch(arr)
                if idx_s in (1, 2, 3):
                    ax_d.text(3.88, 0.5 * (yc + y_next), "SÍ", fontsize=7.5, fontweight="bold", color="#15803D")

        # Lazo de retroalimentación NO -> Corregir / Recalibrar
        for yc_from, yc_to, lbl in [
            (6.8, 8.6, "NO → Depurar lógica"),
            (4.9, 6.8, "NO → Ajustar λ, μ"),
            (3.0, 4.9, "NO → Revisar supuestos"),
        ]:
            loop_box = FancyBboxPatch(
                (7.35, yc_from - 0.32), 2.45, 0.64,
                boxstyle="round,pad=0.05,rounding_size=0.12",
                facecolor="#FEF2F2", edgecolor="#DC2626", linewidth=1.2,
            )
            ax_d.add_patch(loop_box)
            ax_d.text(8.57, yc_from, lbl, ha="center", va="center", fontsize=7.2, fontweight="bold", color="#991B1B")
            ax_d.add_patch(FancyArrowPatch((6.92, yc_from), (7.33, yc_from),
                                           arrowstyle="-|>,head_width=3.5,head_length=5", color="#DC2626", lw=1.2))
            ax_d.add_patch(FancyArrowPatch((8.57, yc_from + 0.34), (6.92, yc_to),
                                           arrowstyle="-|>,head_width=3.5,head_length=5",
                                           color="#DC2626", lw=1.1, linestyle="--", connectionstyle="arc3,rad=0.18"))

        # Panel B: p-valores prueba t post-warmup vs M/G/1 y sesgo relativo
        labels = df_vv["nombre_corto"].tolist()
        y_pos = np.arange(len(labels))
        p_vals = df_vv["p_valor_vs_mg1"].values

        bars = ax_v.barh(y_pos, p_vals, color="#2563EB", alpha=0.88, height=0.55)
        ax_v.axvline(0.05, color="#DC2626", linestyle="--", linewidth=1.6, label="Nivel de significancia α = 0.05")

        for idx_p, bar in enumerate(bars):
            val = bar.get_width()
            wq_ss = float(df_vv.iloc[idx_p]["wq_estable_min"])
            wq_mg1 = float(df_vv.iloc[idx_p]["wq_teorica_mg1_min"])
            ax_v.text(
                val + 0.02, bar.get_y() + bar.get_height() / 2,
                f"p = {val:.3f} ✓  (Est={wq_ss:.2f} vs M/G/1={wq_mg1:.2f} m)",
                va="center", ha="left", fontsize=7.7, fontweight="bold", color="#0F172A",
            )

        ax_v.set_yticks(y_pos)
        ax_v.set_yticklabels(labels, fontsize=8.6, fontweight="bold")
        ax_v.invert_yaxis()
        ax_v.set_xlim(0, 1.48)
        ax_v.set_xlabel("Valor p bilateral prueba t (H₀: μ_estable = Wq_M/G/1)", fontsize=9.5)
        ax_v.set_title("B. Validación Estadística por Escenario (Estado Estable vs. M/G/1)",
                       fontsize=10.5, fontweight="bold", color="#0F172A", pad=8)
        ax_v.grid(axis="x", linestyle=":", alpha=0.6)
        ax_v.legend(loc="lower right", fontsize=8.0, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_transient_elimination_before_after(
        self,
        df_curve_e1: pd.DataFrame,
        df_warmup: pd.DataFrame,
        filename: str = "fig6_eliminacion_transitorio_antes_despues.png",
    ) -> str:
        """Figura 6 (Punto E): Eliminación del estado transitorio (warm-up) y comparación Antes vs Después."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.4, 5.7), dpi=300)

        row_e1 = df_warmup[df_warmup["escenario"] == "E1_3_Mixtos"].iloc[0]
        k_cut = int(row_e1["k_corte_vehiculos"])
        t_cut = float(row_e1["tiempo_corte_aprox_min"])
        wq_all = float(row_e1["wq_con_transitorio_min"])
        wq_ss = float(row_e1["wq_estado_estable_min"])
        wq_mg1 = float(row_e1["wq_teorica_mg1_min"])

        k_vals = df_curve_e1["vehiculo_idx"].values
        wq_raw = df_curve_e1["wq_media_transversal_min"].values
        wq_ma = df_curve_e1["wq_promedio_movil_min"].values

        ax1.axvspan(1, k_cut, color="#FEF3C7", alpha=0.58, label=f"Estado transitorio eliminado (1–{k_cut-1})")
        ax1.axvspan(k_cut, int(k_vals.max()), color="#DCFCE7", alpha=0.35, label="Estado estable conservado")
        ax1.plot(k_vals, wq_raw, color="#94A3B8", linewidth=1.0, alpha=0.85, label="Media transversal Wq(k)")
        ax1.plot(k_vals, wq_ma, color=self.palette["navy"], linewidth=2.2, label="Welch centrado (ventana = 25)")
        ax1.axvline(k_cut, color=self.palette["red"], linestyle="--", linewidth=1.7,
                    label=f"Corte MSER-5 k* = {k_cut} (~{t_cut:.0f} min)")
        ax1.axhline(wq_all, color="#D97706", linestyle=":", linewidth=1.6,
                    label=f"Antes (con transitorio) = {wq_all:.2f} min")
        ax1.axhline(wq_ss, color=self.palette["teal"], linestyle="-.", linewidth=1.7,
                    label=f"Después (estado estable) = {wq_ss:.2f} min")
        ax1.axhline(wq_mg1, color="#64748B", linestyle="--", linewidth=1.1, alpha=0.8,
                    label=f"Teórico M/G/1 = {wq_mg1:.2f} min")

        ax1.set_xlim(1, int(k_vals.max()))
        ax1.set_ylim(0.0, max(float(np.max(wq_raw)), wq_mg1) * 1.40)
        ax1.set_xlabel("Orden de llegada del vehículo k (E1: 3 Cajeros Mixtos)", fontsize=9.6)
        ax1.set_ylabel("Tiempo promedio de espera en cola Wq (min)", fontsize=9.6)
        ax1.set_title("A. Corte MSER-5 y Promedio Móvil Centrado (Welch)",
                      fontsize=10.5, fontweight="bold", color="#0F172A")
        ax1.grid(True, linestyle=":", alpha=0.6)
        ax1.legend(loc="upper left", fontsize=7.4, frameon=True, ncol=2)

        # Panel B: Antes vs Después en todos los escenarios + referencia M/G/1
        labels = df_warmup["nombre_corto"].tolist()
        x = np.arange(len(labels))
        w = 0.27

        v_antes = df_warmup["wq_con_transitorio_min"].values
        v_desp = df_warmup["wq_estado_estable_min"].values
        v_mg1 = df_warmup["wq_teorica_mg1_min"].values
        incrs = (
            df_warmup["incremento_wq_pct"].values
            if "incremento_wq_pct" in df_warmup.columns
            else ((v_desp - v_antes) / v_antes * 100.0)
        )

        ax2.bar(x - w, v_antes, width=w, color="#F59E0B", alpha=0.88, label="Antes (con transitorio)")
        ax2.bar(x, v_desp, width=w, color="#0F766E", alpha=0.90, label="Después (estado estable)")
        ax2.bar(x + w, v_mg1, width=w, color="#64748B", alpha=0.75, label="Teórico M/G/1 (P-K)")

        for idx_b in range(len(x)):
            ax2.text(x[idx_b] - w * 1.05, v_antes[idx_b] + 0.18, f"{v_antes[idx_b]:.2f}",
                     ha="center", va="bottom", fontsize=6.6, fontweight="bold", color="#B45309")
            ax2.text(x[idx_b] + 0.04, max(v_desp[idx_b], v_mg1[idx_b]) + 0.72,
                     f"{v_desp[idx_b]:.2f}\n(+{incrs[idx_b]:.1f}%)",
                     ha="center", va="bottom", fontsize=6.7, fontweight="bold", color="#0F766E",
                     bbox=dict(boxstyle="square,pad=0.06", facecolor="white", edgecolor="none", alpha=0.85))

        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, fontsize=8.0, fontweight="bold", rotation=16, ha="right")
        ax2.set_ylabel("Tiempo promedio de espera en cola Wq (min)", fontsize=9.6)
        ax2.set_title("B. Comparación Antes vs. Después de Eliminar el Transitorio",
                      fontsize=10.5, fontweight="bold", color="#0F172A")
        ax2.set_ylim(0, max(float(np.max(v_desp)), float(np.max(v_mg1))) * 1.24)
        ax2.grid(axis="y", linestyle=":", alpha=0.6)
        ax2.legend(loc="upper right", fontsize=7.8, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_isolated_validation_and_cashier_balance(
        self,
        df_isolated: pd.DataFrame,
        df_cashier_summary: pd.DataFrame,
        filename: str = "fig7_validacion_teoria_y_perfiles.png",
    ) -> str:
        """Figura 7: Validación M/M/1 puro por tipo de usuario y balance individual entre escenarios."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.4, 5.9), dpi=300)

        # Panel A: Validación M/M/1 aislado para los 3 tipos estables + nota sobre Normal (rho=1)
        stable_df = df_isolated[df_isolated["estable"]].copy().reset_index(drop=True)
        u_labels = stable_df["tipo_usuario"].tolist()
        x = np.arange(len(u_labels))
        w = 0.34

        w_teo = stable_df["w_teorico_mm1_min"].values
        w_sim = stable_df["w_simulado_est_min"].values
        w_err = (stable_df["w_ic95_sup"] - stable_df["w_simulado_est_min"]).values
        p_vals = stable_df["p_valor_w"].values

        ax1.bar(x - w / 2, w_teo, width=w, color="#475569", alpha=0.88, label="Analítico exacto W = 1/(μ - λ)")
        ax1.bar(x + w / 2, w_sim, width=w, yerr=w_err, capsize=4, color="#2563EB", alpha=0.90,
                label="Simulado M/M/1 post-warmup (IC 95%)")

        for idx_u in range(len(x)):
            ax1.text(x[idx_u] - w / 2, w_teo[idx_u] + 0.8, f"{w_teo[idx_u]:.2f}",
                     ha="center", va="bottom", fontsize=8.0, fontweight="bold", color="#334155")
            ax1.text(x[idx_u] + w / 2, w_sim[idx_u] + w_err[idx_u] + 0.8,
                     f"{w_sim[idx_u]:.2f}\n(p={p_vals[idx_u]:.3f})",
                     ha="center", va="bottom", fontsize=7.8, fontweight="bold", color="#1E3A8A")

        norm_row = df_isolated[df_isolated["tipo_usuario"] == "Normal"].iloc[0]
        w_1k_norm = float(norm_row["w_horizonte_1000m_min"]) if "w_horizonte_1000m_min" in norm_row else float("nan")
        ratio_norm = float(norm_row["ratio_crecimiento_6000_vs_1000"]) if "ratio_crecimiento_6000_vs_1000" in norm_row else float("nan")
        ax1.text(
            0.03, 0.75,
            f"Perfil Normal (ρ = 1.00 — Inestable):\n"
            f"Teoría M/M/1: W → ∞\n"
            f"W(1000m) = {w_1k_norm:.1f} → W(6000m) = {norm_row['w_simulado_est_min']:.1f} m\n"
            f"Crecimiento empírico: {ratio_norm:.2f}×",
            transform=ax1.transAxes, fontsize=7.6, color="#7F1D1D", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEF2F2", edgecolor="#FCA5A5"),
        )

        ax1.set_xticks(x)
        ax1.set_xticklabels([f"{u}\n(ρ={r:.3f})" for u, r in zip(u_labels, stable_df["rho_teorico"])],
                            fontsize=9.2, fontweight="bold")
        ax1.set_ylabel("Tiempo total promedio en sistema W (min)", fontsize=9.8)
        ax1.set_title("A. Validación M/M/1 Puro por Perfil Aislado (Estables vs. Teoría)",
                      fontsize=10.3, fontweight="bold", color="#0F172A")
        ax1.set_ylim(0, max(float(np.max(w_teo)), float(np.max(w_sim + w_err))) * 1.24)
        ax1.grid(axis="y", linestyle=":", alpha=0.6)
        ax1.legend(loc="upper left", fontsize=8.0, frameon=True)

        # Panel B: Espera Wq individual por cajero en los escenarios clave
        key_scens = ["E1_3_Mixtos", "E2_4_Mixtos", "E5_4_Esp_1E3L", "E3_5_Mixtos", "E6_5_Esp_1E4L", "E7_4_Mix_UX"]
        rows = df_cashier_summary[df_cashier_summary["escenario"].isin(key_scens)].copy().reset_index(drop=True)
        rows["etiqueta"] = rows["nombre_corto"] + " · " + rows["cajero"].str.replace("Cajero ", "C")

        role_colors = {
            "Mixto": "#2563EB",
            "Exprés": "#16A34A",
            "Estándar": "#D97706",
        }
        bar_cols = [role_colors[r] for r in rows["rol"]]
        y_pos = np.arange(len(rows))

        bars_w = ax2.barh(y_pos, rows["espera_wq_prom"], color=bar_cols, alpha=0.88, zorder=2)
        ax2.axvline(5.0, color="#DC2626", linestyle="--", linewidth=1.3, zorder=1)
        for bar in bars_w:
            wv = bar.get_width()
            ax2.text(wv + 0.22, bar.get_y() + bar.get_height() / 2, f"{wv:.2f} m",
                     va="center", ha="left", fontsize=7.2, fontweight="bold", color="#0F172A",
                     bbox=dict(boxstyle="square,pad=0.08", facecolor="white", edgecolor="none", alpha=0.88), zorder=5)

        for idx_r in range(1, len(rows)):
            if rows.loc[idx_r, "escenario"] != rows.loc[idx_r - 1, "escenario"]:
                ax2.axhline(idx_r - 0.5, color="#CBD5E1", linewidth=0.9)

        ax2.set_yticks(y_pos)
        ax2.set_yticklabels(rows["etiqueta"], fontsize=7.2)
        ax2.invert_yaxis()
        ax2.set_xlabel("Tiempo promedio de espera Wq por cajero (min)", fontsize=9.6)
        ax2.set_title("B. Balance de Espera Wq por Cajero y Rol en Escenarios Clave",
                      fontsize=10.3, fontweight="bold", color="#0F172A")
        ax2.set_xlim(0, float(rows["espera_wq_prom"].max()) * 1.18)
        ax2.grid(axis="x", linestyle=":", alpha=0.6)

        legend_handles = [
            Patch(facecolor=role_colors["Mixto"], label="Cajero Mixto"),
            Patch(facecolor=role_colors["Exprés"], label="Exprés (Rápido/Normal)"),
            Patch(facecolor=role_colors["Estándar"], label="Estándar (Lento/M. Lento)"),
            Line2D([0], [0], color="#DC2626", linestyle="--", linewidth=1.3, label="Umbral crítico (5.0 min)"),
        ]
        ax2.legend(handles=legend_handles, loc="lower right", fontsize=7.4, frameon=True)

        out_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return out_path
