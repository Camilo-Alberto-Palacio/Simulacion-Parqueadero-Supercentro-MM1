"""
Script Principal de Ejecución: Simulación Discreta de Colas M/M/1 y M/G/1
Sistema de Pago de Parqueaderos — Centro Comercial Supercentro.
Actividad Didáctica 2-M4 | Módulo 4 | IU Digital de Antioquia — Grupo 25.

Ejecución:
    python main.py
"""

import os
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from parking_queue import (
    SCENARIO_DEFINITIONS,
    SIM_MINUTES,
    USER_TYPES,
    ParkingQueuingModel,
    ParkingSimulationEngine,
    ParkingVisualizer,
)


def print_banner() -> None:
    print("=" * 88)
    print("  SIMULACIÓN DE COLAS M/M/1 Y M/G/1 — PARQUEADEROS CENTRO COMERCIAL SUPERCENTRO  ")
    print("  Actividad Didáctica 2-M4 | Módulo 4 | IU Digital de Antioquia — Grupo 25")
    print("=" * 88)


def main() -> None:
    print_banner()
    os.makedirs("results", exist_ok=True)

    model = ParkingQueuingModel()
    engine = ParkingSimulationEngine(model=model)
    viz = ParkingVisualizer(output_dir="results")

    # 1. Análisis Analítico M/M/1 y Pollaczek-Khinchine M/G/1
    print("\n[1/6] Calculando Propiedades Analíticas M/M/1 y M/G/1...")
    df_iso_theo = pd.DataFrame(model.analyze_user_type_isolated_mm1())
    df_iso_theo.to_csv("results/teoria_mm1_por_tipo_usuario.csv", index=False, encoding="utf-8-sig")

    theo_rows = []
    for skey in SCENARIO_DEFINITIONS:
        theo = model.analyze_scenario_theoretically(skey)
        for cname, cm in theo["cashiers"]:
            theo_rows.append({
                "escenario": skey,
                "nombre_corto": theo["nombre_corto"],
                "cajero": cname,
                "rol": cm.role,
                "lambda_cli_min": cm.lam,
                "mu_cli_min": cm.mu,
                "rho": cm.rho,
                "p0_ocio": cm.p0,
                "es_min": cm.mean_service,
                "es2_min2": cm.mean_s2,
                "l_sistema": cm.l_system,
                "lq_cola": cm.lq_queue,
                "w_sistema_min": cm.w_system,
                "wq_cola_mm1_min": cm.wq_queue,
                "wq_cola_mg1_min": cm.wq_mg1,
                "prob_wq_gt_5m_mm1_pct": cm.prob_wq_gt_5min * 100.0,
                "estable": cm.stable,
            })

    df_theo = pd.DataFrame(theo_rows)
    df_theo.to_csv("results/parametros_teoricos_mm1.csv", index=False, encoding="utf-8-sig")

    lam_exit = model.exit_arrival_rate()
    es_mix, es2_mix = model.expected_service_moments("Mixto")
    print(
        f"  • Demanda salida (3 cajeros base): λ_salida = {lam_exit:.4f} veh/min "
        f"(~{lam_exit * SIM_MINUTES:.1f} veh/{SIM_MINUTES:.0f} min)"
    )
    print(
        f"  • Mezcla global: E[IA_c] = {model.expected_interarrival_per_base_cashier():.3f} min | "
        f"E[S] = {es_mix:.3f} min | E[S^2] = {es2_mix:.2f} min² | ρ_base = {model.base_cashier_arrival_rate()*es_mix*100:.2f}%"
    )

    # 2. Determinación del número oficial de réplicas N* por estado estable sobre la media
    print("\n[2/6] Determinando Número Oficial de Réplicas N* (Estado Estable y ER%)...")
    n_official, df_conv = engine.determine_steady_state_replicas(
        max_replicas=150,
        base_seed=42,
        stability_tol_pct=2.0,
        er_target_pct=7.5,
        sustained_window=20,
        min_replicas=30,
    )
    df_conv.to_csv("results/convergencia_estado_estable_replicas.csv", index=False, encoding="utf-8-sig")

    # Piloto inicial n0 = 10 para documentar algoritmo de 8 pasos de ER%
    res_piloto10 = engine.run_multi_replica_experiment(num_replicas=10, base_seed=42, routing_mode="random_mm1")
    df_sample_n = engine.compute_required_replicas(res_piloto10["df_replicas"])
    df_sample_n.to_csv("results/tamano_muestra_piloto10_er.csv", index=False, encoding="utf-8-sig")

    n_det = int(df_conv["n_detectado_exacto"].iloc[0])
    row_noff = df_conv[df_conv["replica"] == n_official].iloc[0]
    print(
        f"  • Estabilización ±2% y ER<=7.5% detectada en r = {n_det} -> N* oficial seleccionado = {n_official} réplicas"
    )
    print(
        f"  • En N* = {n_official}: Wq = {row_noff['wq_media_acumulada_min']:.2f} min "
        f"(ER = {row_noff['wq_er_pct']:.2f}%) | W = {row_noff['w_media_acumulada_min']:.2f} min "
        f"(ER = {row_noff['w_er_pct']:.2f}%)"
    )

    # 3. Corridas Oficiales N* para los 7 escenarios (M/M/1 independiente + sensibilidad JSQ)
    print(f"\n[3/6] Ejecutando Experimento Oficial ({n_official} Réplicas × 7 Escenarios) y Sensibilidad JSQ...")
    res_off = engine.run_multi_replica_experiment(
        num_replicas=n_official,
        base_seed=42,
        routing_mode="random_mm1",
        independent_arrivals_per_scenario=False,
    )
    res_jsq = engine.run_multi_replica_experiment(
        num_replicas=n_official,
        base_seed=42,
        routing_mode="shortest_queue",
        independent_arrivals_per_scenario=False,
    )

    df_sum = res_off["df_summary"]
    df_rep = res_off["df_replicas"]
    df_caj = res_off["df_cashier_summary"]
    df_wt = res_off["df_wait_by_type"]
    df_jsq_sum = res_jsq["df_summary"]

    df_sum.to_csv("results/resumen_oficial_escenarios.csv", index=False, encoding="utf-8-sig")
    df_rep.to_csv("results/detalle_oficial_replicas.csv", index=False, encoding="utf-8-sig")
    df_caj.to_csv("results/cajeros_oficial_resumen.csv", index=False, encoding="utf-8-sig")
    df_jsq_sum.to_csv("results/sensibilidad_jsq_escenarios.csv", index=False, encoding="utf-8-sig")

    # Tabla consolidada Punto B: Promedio de usuarios por tipo en totalidad de cajeros (E1_3_Mixtos)
    base_rep = df_rep[df_rep["escenario"] == "E1_3_Mixtos"].sort_values("replica")
    wt_base = df_wt[df_wt["escenario"] == "E1_3_Mixtos"].set_index("tipo_usuario")
    col_map = {"Rápido": "rapido", "Normal": "normal", "Lento": "lento", "Muy lento": "muy_lento"}
    tot_mean_veh = float(base_rep["total_usuarios"].mean())

    user_rows = []
    for utype in USER_TYPES:
        col = col_map[utype]
        m_u, sd_u, l_u, u_u = engine._ci95(base_rep[col].tolist())
        prop_emp = (m_u / tot_mean_veh) * 100.0 if tot_mean_veh > 0 else 0.0
        prop_teo = model.user_type_probs[utype] * 100.0
        s_theo = model.service_means[utype]
        user_rows.append({
            "tipo_usuario": utype,
            "total_replicas": int(base_rep[col].sum()),
            "promedio_total_3_cajeros": m_u,
            "desv_est_total": sd_u,
            "ic95_inf_total": l_u,
            "ic95_sup_total": u_u,
            "min_replica": int(base_rep[col].min()),
            "max_replica": int(base_rep[col].max()),
            "promedio_por_cajero": m_u / 3.0,
            "prop_empirica_pct": prop_emp,
            "prop_teorica_pct": prop_teo,
            "dif_pp": prop_emp - prop_teo,
            "s_teorico_min": s_theo,
            "s_empirico_min": float(wt_base.loc[utype, "s_media_min"]),
            "wq_empirico_min": float(wt_base.loc[utype, "wq_media_min"]),
            "w_empirico_min": float(wt_base.loc[utype, "w_media_min"]),
        })
    df_users_summary = pd.DataFrame(user_rows)
    df_users_summary.to_csv("results/usuarios_por_tipo_resumen.csv", index=False, encoding="utf-8-sig")

    # Reporte en consola Punto A y Punto B
    base_caj = df_caj[df_caj["escenario"] == "E1_3_Mixtos"].copy()
    c_min_w = base_caj.loc[base_caj["atencion_w_prom"].idxmin()]
    c_max_w = base_caj.loc[base_caj["atencion_w_prom"].idxmax()]
    c_min_s = base_caj.loc[base_caj["servicio_s_prom"].idxmin()]
    c_max_s = base_caj.loc[base_caj["servicio_s_prom"].idxmax()]

    print(f"\n  [Punto A] Desempeño por Cajero en E1 (3 Mixtos, N* = {n_official} réplicas):")
    for _, r in base_caj.iterrows():
        print(
            f"      - {r['cajero']:9s} | Veh={r['usuarios_prom']:6.2f} | "
            f"S={r['servicio_s_prom']:.3f} m | Wq={r['espera_wq_prom']:.3f} m | "
            f"W={r['atencion_w_prom']:.3f} m [IC95: {r['atencion_w_ic95_inf']:.2f}–{r['atencion_w_ic95_sup']:.2f}] | "
            f"ρ={r['utilizacion_rho_prom']*100:.1f}%"
        )
    print(f"      -> Menor atención total (W): {c_min_w['cajero']} ({c_min_w['atencion_w_prom']:.3f} min) | Menor S: {c_min_s['cajero']} ({c_min_s['servicio_s_prom']:.3f} min)")
    print(f"      -> Mayor atención total (W): {c_max_w['cajero']} ({c_max_w['atencion_w_prom']:.3f} min) | Mayor S: {c_max_s['cajero']} ({c_max_s['servicio_s_prom']:.3f} min)")

    print(f"\n  [Punto B] Promedio de Usuarios por Tipo en los 3 Cajeros (Total={tot_mean_veh:.2f} veh/jornada):")
    for _, ur in df_users_summary.iterrows():
        print(
            f"      - {ur['tipo_usuario']:10s}: {ur['promedio_total_3_cajeros']:6.2f} (±{ur['desv_est_total']:.2f}) | "
            f"{ur['promedio_por_cajero']:5.2f}/caj | Emp={ur['prop_empirica_pct']:5.2f}% vs Teór={ur['prop_teorica_pct']:5.1f}% | "
            f"W={ur['w_empirico_min']:5.2f} m"
        )

    # 4. Punto E (Eliminación del Estado Transitorio) y Punto D (Validación y Matriz V&V)
    print("\n[4/6] Ejecutando Eliminación del Estado Transitorio (Warm-up) y Protocolo V&V...")
    df_warm, df_curve_e1, df_warm_caj = engine.eliminate_transient_and_compare(
        num_replicas=n_official,
        base_seed=42,
        window=25,
        k_horizon=500,
    )
    df_vv = engine.compute_vv_and_critical_matrix(res_off, df_warm)
    df_iso_val = engine.validate_isolated_mm1_by_user_type(num_replicas=100, base_seed=42, horizon_minutes=3000.0)

    df_warm.to_csv("results/eliminacion_transitorio_antes_despues.csv", index=False, encoding="utf-8-sig")
    df_curve_e1.to_csv("results/curva_warmup_e1_3mixtos.csv", index=False, encoding="utf-8-sig")
    df_warm_caj.to_csv("results/warmup_cajeros_e1_antes_despues.csv", index=False, encoding="utf-8-sig")
    df_vv.to_csv("results/matriz_vv_y_criterios_criticos.csv", index=False, encoding="utf-8-sig")
    df_iso_val.to_csv("results/validacion_mm1_tipos_aislados.csv", index=False, encoding="utf-8-sig")

    print("\n  [Puntos C y D] Resumen Comparativo de Estrategias y Validación V&V:")
    for _, rv in df_vv.iterrows():
        print(
            f"      - {rv['nombre_corto']:14s} | Wq={rv['wq_sim_min']:5.2f}m | W={rv['w_sim_min']:5.2f}m | "
            f"ρ_max={rv['rho_max_pct']:4.1f}% | P(>5m)={rv['prob_wq_mayor_5m_peor_cajero_pct']:4.1f}% | "
            f"p_MG1={rv['p_valor_vs_mg1']:.3f} | {rv['dictamen_global']}"
        )

    print("\n  [Punto E] Eliminación del Transitorio (Antes vs. Después):")
    for _, rw in df_warm.iterrows():
        print(
            f"      - {rw['nombre_corto']:14s} | k*={int(rw['k_corte_vehiculos']):3d} (~{rw['tiempo_corte_aprox_min']:5.1f}m) | "
            f"Antes={rw['wq_con_transitorio_min']:5.2f}m -> Después={rw['wq_estado_estable_min']:5.2f}m "
            f"(M/G/1={rw['wq_teorica_mg1_min']:5.2f}m, subest={rw['sesgo_subestimacion_wq_pct']:4.1f}%)"
        )

    # 5. Generación de 7 Figuras Científicas a 300 DPI
    print("\n[5/6] Generando 7 Figuras Científicas en Alta Resolución (300 DPI)...")
    wq_mg1_base = float(df_sum.loc[df_sum["escenario"] == "E1_3_Mixtos", "wq_teorica_mg1_min"].iloc[0])
    figs = [
        viz.plot_steady_state_replicas(df_conv, wq_mg1_base),
        viz.plot_base_cashier_performance(res_off["df_cashiers"], df_caj),
        viz.plot_user_types_summary(model, base_rep, wt_base.reset_index()),
        viz.plot_scenarios_strategy_comparison(df_sum, df_jsq_sum),
        viz.plot_vv_process_diagram(df_vv),
        viz.plot_transient_elimination_before_after(df_curve_e1, df_warm),
        viz.plot_isolated_validation_and_cashier_balance(df_iso_val, df_caj),
    ]
    for f in figs:
        print(f"      [+] Figura guardada: {f}")

    # 6. Cierre
    print("\n[6/6] Pipeline experimental completado exitosamente.")
    print("  • Todos los 14 CSVs y las 7 figuras quedaron exportados en 'results/'.")
    print("=" * 88)


if __name__ == "__main__":
    main()
