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
        """Verifica que la técnica del estado estable converge y arroja ER(Wq) < 10%."""
        n_off, df_conv = self.engine.determine_steady_state_replicas(max_replicas=150, base_seed=42)
        self.assertGreaterEqual(n_off, 30)
        self.assertLessEqual(n_off, 150)
        row = df_conv[df_conv["replica"] == n_off].iloc[0]
        self.assertLess(float(row["wq_er_pct"]), 10.0)
        self.assertLessEqual(float(row["desviacion_asintotica_wq_pct"]), 2.5)

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
        """Al iniciar vacío L(0)=0, eliminar el transitorio remueve la subestimación inicial."""
        df_warm, df_curve, df_caj_w = self.engine.eliminate_transient_and_compare(num_replicas=40, base_seed=42)
        self.assertEqual(len(df_warm), len(SCENARIO_DEFINITIONS))
        self.assertEqual(len(df_curve), 500)
        self.assertEqual(len(df_caj_w), 3)
        for _, row in df_warm.iterrows():
            self.assertGreaterEqual(int(row["k_corte_vehiculos"]), 60)
            self.assertGreaterEqual(float(row["wq_estado_estable_min"]), float(row["wq_con_transitorio_min"]))

    def test_isolated_mm1_validation_passes_for_stable_types(self) -> None:
        """Valida p > 0.05 contra teoría M/M/1 pura para Rápido, Lento y Muy lento."""
        df_iso = self.engine.validate_isolated_mm1_by_user_type(num_replicas=60, base_seed=42, horizon_minutes=3000.0)
        stable = df_iso[df_iso["estable"]]
        self.assertEqual(len(stable), 3)
        self.assertTrue((stable["p_valor_w"] > 0.05).all())

    def test_vv_matrix_consistency_and_dynamic_dictamen(self) -> None:
        """Verifica consistencia entre resumen oficial y matriz V&V (Little, Chi2, criterios)."""
        exp = self.engine.run_multi_replica_experiment(num_replicas=50, base_seed=42)
        df_warm, _, _ = self.engine.eliminate_transient_and_compare(num_replicas=50, base_seed=42)
        df_vv = self.engine.compute_vv_and_critical_matrix(exp, df_warm).set_index("escenario")
        df_sum = exp["df_summary"].set_index("escenario")
        df_caj = exp["df_cashier_summary"]

        self.assertTrue(bool(df_vv["verificacion_little_ok"].all()))
        self.assertGreater(float(df_vv["calibracion_chi2_pval"].iloc[0]), 0.01)
        self.assertIn("Crítico", str(df_vv.loc["E1_3_Mixtos", "criterio_wq"]))
        self.assertIn("NO RECOMENDADO", str(df_vv.loc["E1_3_Mixtos", "dictamen_global"]))

        for skey in df_vv.index:
            self.assertEqual(str(df_sum.loc[skey, "regimen_estabilidad"]), str(df_vv.loc[skey, "criterio_rho"]))
            c_max_p5 = float(df_caj[df_caj["escenario"] == skey]["prob_wq_mayor_5m_prom"].max())
            self.assertAlmostEqual(float(df_vv.loc[skey, "prob_wq_mayor_5m_peor_cajero_pct"]), c_max_p5, places=8)


if __name__ == "__main__":
    unittest.main()
