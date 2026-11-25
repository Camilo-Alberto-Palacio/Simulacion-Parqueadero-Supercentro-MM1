"""
Suite de Pruebas Unitarias y Verificación Matemática del Simulador de Parqueaderos Supercentro.
Valida axiomas probabilísticos, momentos exactos M/M/1 y M/G/1, Ley de Little,
reproducibilidad PCG64, estado estable N*, enrutamiento JSQ no clarividente,
eliminación del período transitorio y coherencia dinámica de la matriz V&V.
"""

import unittest
import numpy as np

from parking_queue import (
    BASE_CASHIERS,
    SCENARIO_DEFINITIONS,
    SIM_MINUTES,
    USER_TYPES,
    ArrivalVehicle,
    ParkingQueuingModel,
    ParkingSimulationEngine,
    chi2_sf_df3,
    t_crit_two_sided,
    two_sided_t_pvalue,
)


class TestParkingQueuingModel(unittest.TestCase):
    """Pruebas rigurosas de modelado, DES y validación estadística."""

    def setUp(self) -> None:
        self.model = ParkingQueuingModel()
        self.engine = ParkingSimulationEngine(self.model)

    def test_probability_axioms_and_validation(self) -> None:
        """Verifica suma unitaria, no-negatividad y rechazo de entradas inválidas."""
        self.assertAlmostEqual(sum(self.model.user_type_probs.values()), 1.0, places=10)
        self.assertEqual(set(self.model.user_type_probs.keys()), set(USER_TYPES))
        with self.assertRaises(ValueError):
            ParkingQueuingModel(user_type_probs={"Rápido": 0.2, "Normal": 0.2, "Lento": 0.2, "Muy lento": 0.2})

    def test_exact_analytical_moments(self) -> None:
        """Comprueba E[IA_c], lambda_salida, E[S] y E[S^2] de la mezcla."""
        # 0.25*3 + 0.20*3 + 0.275*5 + 0.275*7 = 4.65
        e_ia = self.model.expected_interarrival_per_base_cashier()
        self.assertAlmostEqual(e_ia, 4.65, places=10)
        self.assertAlmostEqual(self.model.exit_arrival_rate(), BASE_CASHIERS / 4.65, places=10)

        # E[S] = 0.25*1 + 0.20*3 + 0.275*4 + 0.275*6 = 3.60
        es, es2 = self.model.expected_service_moments("Mixto")
        self.assertAlmostEqual(es, 3.60, places=10)
        # E[S^2] = 2 * (0.25*1 + 0.20*9 + 0.275*16 + 0.275*36) = 32.70
        self.assertAlmostEqual(es2, 32.70, places=10)

    def test_isolated_user_type_stability_flags(self) -> None:
        """Verifica rho = 1.0 en perfil Normal y estabilidad en los demás."""
        iso = {r["tipo_usuario"]: r for r in self.model.analyze_user_type_isolated_mm1()}
        self.assertTrue(iso["Rápido"]["estable"])
        self.assertAlmostEqual(float(iso["Rápido"]["rho"]), 1.0 / 3.0, places=8)
        self.assertFalse(iso["Normal"]["estable"])
        self.assertAlmostEqual(float(iso["Normal"]["rho"]), 1.0, places=8)
        self.assertTrue(iso["Lento"]["estable"])
        self.assertAlmostEqual(float(iso["Lento"]["rho"]), 0.8, places=8)
        self.assertTrue(iso["Muy lento"]["estable"])
        self.assertAlmostEqual(float(iso["Muy lento"]["rho"]), 6.0 / 7.0, places=8)

    def test_all_scenarios_stable_and_analytical_littles_law(self) -> None:
        """Verifica rho < 1 y cumplimiento exacto de L = lambda*W en los 7 escenarios."""
        for skey in SCENARIO_DEFINITIONS:
            theo = self.model.analyze_scenario_theoretically(skey)
            self.assertAlmostEqual(float(theo["total_lambda"]), self.model.exit_arrival_rate(), places=8)
            for _, cm in theo["cashiers"]:
                self.assertTrue(cm.stable)
                self.assertLess(cm.rho, 1.0)
                self.assertAlmostEqual(cm.l_system, cm.lam * cm.w_system, places=8)
                self.assertAlmostEqual(cm.lq_queue, cm.lam * cm.wq_queue, places=8)
                self.assertAlmostEqual(cm.w_system, cm.wq_queue + cm.mean_service, places=8)

    def test_empirical_littles_law_on_sample_path(self) -> None:
        """Verifica L_q = lambda_eff * W_q y L = lambda_eff * W en trayectoria simulada."""
        arrivals = self.model.generate_exit_arrivals(seed=42)
        for s_idx, skey in enumerate(SCENARIO_DEFINITIONS):
            res = self.engine.simulate_single_replica(skey, arrivals, routing_seed=4200 + s_idx)
            for cname, cres in res["cashiers"].items():
                if cres["total_customers"] > 0:
                    lam_eff = cres["total_customers"] / cres["horizon_effective"]
                    self.assertAlmostEqual(
                        cres["lq_empirical"], lam_eff * cres["mean_wait_wq"], places=10,
                        msg=f"Falla Little Lq en {skey}/{cname}",
                    )
                    self.assertAlmostEqual(
                        cres["l_empirical"], lam_eff * cres["mean_system_w"], places=10,
                        msg=f"Falla Little L en {skey}/{cname}",
                    )

    def test_deterministic_reproducibility(self) -> None:
        """Dos ejecuciones con la misma semilla producen cifras idénticas."""
        r1 = self.engine.run_multi_replica_experiment(num_replicas=10, base_seed=42)
        r2 = self.engine.run_multi_replica_experiment(num_replicas=10, base_seed=42)
        np.testing.assert_allclose(
            r1["df_summary"]["espera_wq_media_min"].values,
            r2["df_summary"]["espera_wq_media_min"].values,
            atol=1e-12,
        )

    def test_horizon_respects_1000_minutes(self) -> None:
        """Todas las llegadas generadas pertenecen al intervalo (0, 1000]."""
        arrivals = self.model.generate_exit_arrivals(seed=99)
        self.assertGreater(len(arrivals), 400)
        self.assertTrue(all(0.0 < v.arrival_time <= SIM_MINUTES for v in arrivals))

    def test_student_t_and_chi2_special_functions(self) -> None:
        """Verifica cuantiles exactos t de Student, p-valor bilateral y Chi2 df=3."""
        self.assertAlmostEqual(t_crit_two_sided(1, 0.95), 12.70620474, places=5)
        self.assertAlmostEqual(t_crit_two_sided(9, 0.95), 2.26215716, places=5)
        self.assertAlmostEqual(t_crit_two_sided(119, 0.95), 1.98009988, places=5)
        self.assertAlmostEqual(two_sided_t_pvalue(0.0, 50), 1.0, places=10)
        self.assertAlmostEqual(two_sided_t_pvalue(2.26215716, 9), 0.05, places=5)
        # Para chi2(3), P(X >= 7.814728) = 0.05
        self.assertAlmostEqual(chi2_sf_df3(0.0), 1.0, places=10)
        self.assertAlmostEqual(chi2_sf_df3(7.814728), 0.05, places=5)

    def test_steady_state_replicas_determination(self) -> None:
        """Verifica que la regla causal Law & Kelton converge y cumple ER(Wq) <= cota."""
        n_off, df_conv = self.engine.determine_steady_state_replicas(max_replicas=250, base_seed=42)
        self.assertGreaterEqual(n_off, 30)
        self.assertLessEqual(n_off, 250)
        row = df_conv[df_conv["replica"] == n_off].iloc[0]
        self.assertTrue(bool(row["convergio_estado_estable"]))
        self.assertLessEqual(float(row["wq_er_pct"]), float(row["er_umbral_law_kelton_pct"]))
        self.assertLessEqual(float(row["variacion_ventana_causal_wq_pct"]), 1.5)

    def test_non_clairvoyant_jsq_reduces_wait_below_mm1(self) -> None:
        """JSQ observable reduce Wq respecto a M/M/1 pero nunca supera al clarividente least_work."""
        mc_rand = self.engine.run_multi_replica_experiment(num_replicas=25, base_seed=42, routing_mode="random_mm1")
        mc_jsq = self.engine.run_multi_replica_experiment(num_replicas=25, base_seed=42, routing_mode="shortest_queue")
        mc_lwl = self.engine.run_multi_replica_experiment(num_replicas=25, base_seed=42, routing_mode="least_work")

        wq_r = float(mc_rand["df_summary"].set_index("escenario").loc["E1_3_Mixtos", "espera_wq_media_min"])
        wq_j = float(mc_jsq["df_summary"].set_index("escenario").loc["E1_3_Mixtos", "espera_wq_media_min"])
        wq_l = float(mc_lwl["df_summary"].set_index("escenario").loc["E1_3_Mixtos", "espera_wq_media_min"])
        self.assertLess(wq_j, wq_r)
        self.assertLessEqual(wq_l, wq_j)

        with self.assertRaises(ValueError):
            self.engine.simulate_single_replica(
                "E1_3_Mixtos",
                [ArrivalVehicle(1, 1.0, 1.0, "Rápido", 1.0, 1.0)],
                routing_seed=1,
                routing_mode="bad_mode",
            )

    def test_scenario_monotonicity_capacity_and_ux(self) -> None:
        """Más cajeros y la mejora UX reducen consistentemente Wq frente a la base."""
        mc = self.engine.run_multi_replica_experiment(num_replicas=40, base_seed=42)
        s = mc["df_summary"].set_index("escenario")
        self.assertLess(float(s.loc["E2_4_Mixtos", "espera_wq_media_min"]), float(s.loc["E1_3_Mixtos", "espera_wq_media_min"]))
        self.assertLess(float(s.loc["E3_5_Mixtos", "espera_wq_media_min"]), float(s.loc["E2_4_Mixtos", "espera_wq_media_min"]))
        self.assertLess(float(s.loc["E4_6_Mixtos", "espera_wq_media_min"]), float(s.loc["E3_5_Mixtos", "espera_wq_media_min"]))
        self.assertLess(float(s.loc["E7_4_Mix_UX", "espera_wq_media_min"]), float(s.loc["E2_4_Mixtos", "espera_wq_media_min"]))

    def test_user_type_totals_sum_exact_and_proportions_calibrated(self) -> None:
        """Verifica suma exacta por tipo y calibración cercana a 25/20/27.5/27.5 %."""
        mc = self.engine.run_multi_replica_experiment(num_replicas=40, base_seed=42)
        rep = mc["df_replicas"]
        sub = rep[rep["escenario"] == "E1_3_Mixtos"]
        tot = sub["rapido"] + sub["normal"] + sub["lento"] + sub["muy_lento"]
        np.testing.assert_array_equal(tot.values, sub["total_usuarios"].values)
        self.assertAlmostEqual(float(sub["rapido"].sum() / sub["total_usuarios"].sum()), 0.25, delta=0.02)

    def test_pilot_sample_size_and_relative_error_drop(self) -> None:
        """Verifica algoritmo de 8 pasos y reducción de ER% al ampliar réplicas."""
        exp10 = self.engine.run_multi_replica_experiment(num_replicas=10, base_seed=42)
        df_req = self.engine.compute_required_replicas(exp10["df_replicas"]).set_index("escenario")
        exp80 = self.engine.run_multi_replica_experiment(num_replicas=80, base_seed=42)
        s80 = exp80["df_summary"].set_index("escenario")
        for skey in SCENARIO_DEFINITIONS:
            self.assertLess(float(s80.loc[skey, "espera_wq_er_pct"]), float(df_req.loc[skey, "wq_er_piloto_pct"]))

    def test_transient_elimination_increases_or_matches_steady_wait(self) -> None:
        """Al iniciar vacío L(0)=0, MSER-5 elimina el sesgo inicial sin truncar la jornada."""
        df_warm, df_curve, df_caj_w = self.engine.eliminate_transient_and_compare(num_replicas=50, base_seed=42)
        self.assertEqual(len(df_warm), len(SCENARIO_DEFINITIONS))
        self.assertEqual(len(df_curve), 550)
        self.assertEqual(len(df_caj_w), 3)
        for _, row in df_warm.iterrows():
            self.assertGreaterEqual(int(row["k_corte_vehiculos"]), 21)
            self.assertGreaterEqual(float(row["wq_estado_estable_min"]), float(row["wq_con_transitorio_min"]))

    def test_isolated_mm1_validation_passes_for_stable_types(self) -> None:
        """Valida p > 0.05 contra teoría M/M/1 pura para Rápido, Lento y Muy lento a 6000 min."""
        df_iso = self.engine.validate_isolated_mm1_by_user_type(
            num_replicas=100, base_seed=42, horizon_minutes=6000.0, warmup_frac=0.30
        )
        stable = df_iso[df_iso["estable"]]
        self.assertEqual(len(stable), 3)
        self.assertTrue((stable["p_valor_w"] > 0.05).all())

    def test_vv_matrix_consistency_and_dynamic_dictamen(self) -> None:
        """Verifica consistencia entre resumen oficial y matriz V&V (Little, Chi2, criterios)."""
        exp = self.engine.run_multi_replica_experiment(num_replicas=50, base_seed=42)
        exp_jsq = self.engine.run_multi_replica_experiment(num_replicas=50, base_seed=42, routing_mode="shortest_queue")
        df_warm, _, _ = self.engine.eliminate_transient_and_compare(num_replicas=50, base_seed=42)
        df_vv = self.engine.compute_vv_and_critical_matrix(exp, df_warm, res_jsq=exp_jsq).set_index("escenario")
        df_sum = exp["df_summary"].set_index("escenario")
        df_caj = exp["df_cashier_summary"]

        self.assertTrue(bool(df_vv["verificacion_little_ok"].all()))
        self.assertTrue((df_vv["verificacion_little_jsq_max_err"] < 1e-10).all())
        self.assertGreater(float(df_vv["calibracion_chi2_pval"].iloc[0]), 0.01)
        self.assertIn("Crítico", str(df_vv.loc["E1_3_Mixtos", "criterio_wq"]))
        self.assertIn("NO RECOMENDADO", str(df_vv.loc["E1_3_Mixtos", "dictamen_global"]))

        df_warm_idx = df_warm.set_index("escenario")
        for skey in df_vv.index:
            self.assertAlmostEqual(
                float(df_vv.loc[skey, "peor_cajero_wq_estable_min"]),
                float(df_warm_idx.loc[skey, "peor_cajero_wq_estado_estable_min"]),
                places=8,
            )
            self.assertAlmostEqual(
                float(df_vv.loc[skey, "prob_wq_mayor_5m_peor_cajero_estable_pct"]),
                float(df_warm_idx.loc[skey, "prob_wq_mayor_5m_peor_cajero_estado_estable_pct"]),
                places=8,
            )
        self.assertEqual(str(df_sum.loc["E4_6_Mixtos", "regimen_estabilidad"]), "Subutilizado (<45%)")
        self.assertIn("REDUNDANTE", str(df_vv.loc["E4_6_Mixtos", "dictamen_global"]))

    def test_parameter_validation_rejects_missing_service_or_arrival_keys(self) -> None:
        """_validate_parameters rechaza llaves faltantes en service_means o arrival_means (N5)."""
        with self.assertRaises(ValueError):
            ParkingQueuingModel(service_means={"Rápido": 1.0, "Normal": 3.0})
        with self.assertRaises(ValueError):
            ParkingQueuingModel(arrival_means={"Rápido": 3.0, "Normal": 3.0, "Lento": 5.0})

    def test_effective_service_time_uses_instance_service_means(self) -> None:
        """_effective_service_time escala base_service_time del modelo sin acoplarse a globales (M4)."""
        custom_srv = {"Rápido": 2.0, "Normal": 6.0, "Lento": 8.0, "Muy lento": 12.0}
        m_custom = ParkingQueuingModel(service_means=custom_srv)
        arr = m_custom.generate_exit_arrivals(seed=42)
        lento_v = next(v for v in arr if v.user_type == "Lento")
        eff = ParkingSimulationEngine._effective_service_time(lento_v, ux_factor_slow=0.75)
        self.assertAlmostEqual(eff, lento_v.unit_service_exp * 8.0 * 0.75, places=10)

    def test_time_integral_littles_law_independent_across_modes(self) -> None:
        """Verifica L_q por integración temporal de Q(t) en random_mm1, JSQ y single_queue_mgc (M3, M5)."""
        arr = self.model.generate_exit_arrivals(seed=42)
        for mode in ("random_mm1", "shortest_queue", "single_queue_mgc"):
            res = self.engine.simulate_single_replica("E2_4_Mixtos", arr, routing_seed=99, routing_mode=mode)
            self.assertLess(float(res["max_little_err"]), 1e-10, msg=f"Little fallo en modo {mode}")

    def test_causal_steady_state_replicas_zero_lookahead(self) -> None:
        """La regla Law & Kelton da el mismo n_det aunque se corte el horizonte en n_det (B4)."""
        _, df_full = self.engine.determine_steady_state_replicas(max_replicas=250, base_seed=42)
        n_det_full = int(df_full["n_detectado_exacto"].iloc[0])
        _, df_trunc = self.engine.determine_steady_state_replicas(max_replicas=n_det_full, base_seed=42)
        self.assertEqual(int(df_trunc["n_detectado_exacto"].iloc[0]), n_det_full)

    def test_single_queue_mgc_and_hyperexponential_arrivals_sensitivity(self) -> None:
        """Cola única M/G/c mejora sobre JSQ y llegadas H4 (Ca2=1.257) aumentan Wq frente a Poisson (B2, M5)."""
        _, _, ca2 = self.model.expected_interarrival_moments_h4()
        self.assertGreater(ca2, 1.2)
        r_rand = self.engine.run_multi_replica_experiment(30, base_seed=42, routing_mode="random_mm1")
        r_jsq = self.engine.run_multi_replica_experiment(30, base_seed=42, routing_mode="shortest_queue")
        r_mgc = self.engine.run_multi_replica_experiment(30, base_seed=42, routing_mode="single_queue_mgc")
        wq_rand = float(r_rand["df_summary"].set_index("escenario").loc["E2_4_Mixtos", "espera_wq_media_min"])
        wq_jsq = float(r_jsq["df_summary"].set_index("escenario").loc["E2_4_Mixtos", "espera_wq_media_min"])
        wq_mgc = float(r_mgc["df_summary"].set_index("escenario").loc["E2_4_Mixtos", "espera_wq_media_min"])
        self.assertLessEqual(wq_mgc, wq_jsq + 0.05)
        self.assertLess(wq_jsq, wq_rand)

        scen_e1 = {"E1_3_Mixtos": SCENARIO_DEFINITIONS["E1_3_Mixtos"]}
        r_p = self.engine.run_multi_replica_experiment(
            40, base_seed=42, scenarios=scen_e1, routing_mode="single_queue_mgc", arrival_process="poisson"
        )
        r_h = self.engine.run_multi_replica_experiment(
            40, base_seed=42, scenarios=scen_e1, routing_mode="single_queue_mgc", arrival_process="hyperexponential"
        )
        self.assertGreater(
            float(r_h["df_summary"]["espera_wq_media_min"].iloc[0]),
            float(r_p["df_summary"]["espera_wq_media_min"].iloc[0]),
        )

    def test_paired_crn_comparisons_and_e7_specific_calibration(self) -> None:
        """IC pareados CRN detectan E7 < E2 y simetría entre cajeros E1; E7 calibra su propio servicio (M6)."""
        exp = self.engine.run_multi_replica_experiment(60, base_seed=42)
        df_p = self.engine.compute_paired_crn_comparisons(exp).set_index("contraste")
        self.assertLess(float(df_p.loc["E7_4_Mix_UX - E2_4_Mixtos", "delta_pareado"]), 0.0)
        self.assertTrue(bool(df_p.loc["E7_4_Mix_UX - E2_4_Mixtos", "significativo_95"]))

        for pair_lbl in ("Cajero 1 - Cajero 2", "Cajero 1 - Cajero 3", "Cajero 3 - Cajero 2"):
            self.assertGreater(float(df_p.loc[pair_lbl, "p_valor"]), 0.05)
            self.assertFalse(bool(df_p.loc[pair_lbl, "significativo_95"]))

        exp_ind = self.engine.run_multi_replica_experiment(40, base_seed=42, independent_arrivals_per_scenario=True)
        df_warm_ind, _, _ = self.engine.eliminate_transient_and_compare(num_replicas=40, base_seed=42)
        df_vv_ind = self.engine.compute_vv_and_critical_matrix(exp_ind, df_warm_ind).set_index("escenario")
        self.assertLess(float(df_vv_ind.loc["E7_4_Mix_UX", "calibracion_srv_max_rel_err_pct"]), 5.0)
        self.assertNotAlmostEqual(
            float(df_vv_ind.loc["E7_4_Mix_UX", "calibracion_srv_max_rel_err_pct"]),
            float(df_vv_ind.loc["E1_3_Mixtos", "calibracion_srv_max_rel_err_pct"]),
            places=6,
        )

    def test_isolated_normal_empirical_divergence_verified(self) -> None:
        """El perfil crítico Normal (rho=1) crece empíricamente al menos 1.5x entre 1000m y 6000m (M3)."""
        df_iso = self.engine.validate_isolated_mm1_by_user_type(
            num_replicas=60, base_seed=42, horizon_minutes=6000.0, warmup_frac=0.30
        ).set_index("tipo_usuario")
        ratio = float(df_iso.loc["Normal", "ratio_crecimiento_6000_vs_1000"])
        self.assertGreaterEqual(ratio, 1.5)
        self.assertIn("Divergencia empírica verificada", str(df_iso.loc["Normal", "resultado_validacion"]))

    def test_e4_redundant_subutilized_and_steady_state_vv_homogeneous(self) -> None:
        """E4 (6 Mixtos) debe clasificarse Subutilizado/REDUNDANTE y V&V debe evaluar régimen post-MSER-5 homogéneo."""
        exp = self.engine.run_multi_replica_experiment(60, base_seed=42)
        df_warm, _, _ = self.engine.eliminate_transient_and_compare(num_replicas=60, base_seed=42)
        df_vv = self.engine.compute_vv_and_critical_matrix(exp, df_warm).set_index("escenario")
        df_sum = exp["df_summary"].set_index("escenario")
        df_warm_idx = df_warm.set_index("escenario")

        self.assertEqual(str(df_sum.loc["E4_6_Mixtos", "regimen_estabilidad"]), "Subutilizado (<45%)")
        self.assertEqual(str(df_vv.loc["E4_6_Mixtos", "criterio_rho"]), "Subutilizado (<45%)")
        self.assertIn("REDUNDANTE", str(df_vv.loc["E4_6_Mixtos", "dictamen_global"]))
        self.assertNotIn("ÓPTIMO", str(df_vv.loc["E4_6_Mixtos", "dictamen_global"]))

        for skey in df_vv.index:
            self.assertAlmostEqual(
                float(df_vv.loc[skey, "rho_peor_cajero_estable_pct"]),
                float(df_warm_idx.loc[skey, "rho_peor_cajero_estado_estable_pct"]),
                places=8,
            )

    def test_h4_crn_coupled_monotonicity_5000m_and_input_guards(self) -> None:
        """Verifica CRN acoplado en H4/H4/1, validación estacionaria larga y rechazo de entradas vacías o NaN."""
        a_p = self.model.generate_exit_arrivals(seed=42, arrival_process="poisson")
        a_h = self.model.generate_exit_arrivals(seed=42, arrival_process="hyperexponential")
        n_common = min(len(a_p), len(a_h))
        self.assertGreater(n_common, 100)
        for i in range(n_common):
            self.assertEqual(a_p[i].user_type, a_h[i].user_type)
            self.assertAlmostEqual(a_p[i].unit_service_exp, a_h[i].unit_service_exp, places=12)

        scen_e1 = {"E1_3_Mixtos": SCENARIO_DEFINITIONS["E1_3_Mixtos"]}
        scen_e7 = {"E7_4_Mix_UX": SCENARIO_DEFINITIONS["E7_4_Mix_UX"]}
        r_p7 = self.engine.run_multi_replica_experiment(80, base_seed=42, scenarios=scen_e7, arrival_process="poisson")
        r_h7 = self.engine.run_multi_replica_experiment(80, base_seed=42, scenarios=scen_e7, arrival_process="hyperexponential")
        self.assertGreater(
            float(r_h7["df_summary"]["espera_wq_media_min"].iloc[0]),
            float(r_p7["df_summary"]["espera_wq_media_min"].iloc[0]),
        )
        r_p1m = self.engine.run_multi_replica_experiment(
            80, base_seed=42, scenarios=scen_e1, routing_mode="single_queue_mgc", arrival_process="poisson"
        )
        r_h1m = self.engine.run_multi_replica_experiment(
            80, base_seed=42, scenarios=scen_e1, routing_mode="single_queue_mgc", arrival_process="hyperexponential"
        )
        self.assertGreater(
            float(r_h1m["df_summary"]["espera_wq_media_min"].iloc[0]),
            float(r_p1m["df_summary"]["espera_wq_media_min"].iloc[0]),
        )

        sub_scen = {
            "E1_3_Mixtos": SCENARIO_DEFINITIONS["E1_3_Mixtos"],
            "E7_4_Mix_UX": SCENARIO_DEFINITIONS["E7_4_Mix_UX"],
        }
        df_s5k = self.engine.validate_stationary_mg1_long_horizon(
            num_replicas=20, horizon_minutes=3000.0, warmup_frac=0.20, base_seed=42, scenarios=sub_scen
        )
        self.assertTrue(bool(df_s5k["validado_alpha_05"].all()))

        with self.assertRaises(ValueError):
            ParkingQueuingModel(user_type_probs={})
        with self.assertRaises(ValueError):
            ParkingQueuingModel(service_means={"Rápido": float("nan"), "Normal": 3.0, "Lento": 4.0, "Muy lento": 6.0})
        bad_scen = {"E_BAD": {"nombre": "Bad", "nombre_corto": "Bad", "num_cajeros": 1, "ux_factor_slow": 0.0, "cajeros": [("C1", "Mixto")]}}
        with self.assertRaises(ValueError):
            self.engine.simulate_single_replica("E_BAD", a_p[:5], routing_seed=1, scenarios=bad_scen)


if __name__ == "__main__":
    unittest.main()
