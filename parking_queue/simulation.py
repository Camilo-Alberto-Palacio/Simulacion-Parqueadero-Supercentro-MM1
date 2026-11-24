"""
Motor de Simulación de Eventos Discretos (DES) para el Sistema de Pago de Parqueaderos
del Centro Comercial Supercentro (Cajeros Independientes M/M/1 y Extensión M/G/1).

Implementa:
- Simulación fiel sobre horizonte de 1000 minutos por réplica con Números Aleatorios
  Comunes (CRN) y generador reproducible PCG64.
- Modos de enrutamiento: 'random_mm1' (descomposición equiprobable M/M/1),
  'shortest_queue' (JSQ observable no clarividente con deque) y 'least_work'.
- Detección automática del número total de réplicas N* mediante convergencia al
  estado estable del promedio acumulado y cota de Error Relativo ER%.
- Cálculo piloto (n0=10) con algoritmo de 8 pasos y cuantiles exactos t de Student.
- Eliminación del período transitorio (warm-up) con promedio móvil (antes vs. después).
- Protocolo integral de Verificación, Calibración y Validación (V&V) sin dependencias externas.
"""

from collections import deque
import math
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .model import (
    ROLE_ALLOWED_TYPES,
    SCENARIO_DEFINITIONS,
    SERVICE_MEANS,
    SIM_MINUTES,
    USER_TYPES,
    ArrivalVehicle,
    ParkingQueuingModel,
    classify_utilization_regime,
)


def _betacf(a: float, b: float, x: float) -> float:
    """Fracción continua de Lentz para la función beta incompleta regularizada."""
    max_iter = 200
    eps = 3e-14
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Función beta incompleta regularizada I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_crit_two_sided(df: int, confidence: float = 0.95) -> float:
    """Cuantil bilateral t_{alpha/2, df} exacto mediante inversión de I_x."""
    if df < 1:
        raise ValueError(f"Los grados de libertad (df) deben ser >= 1, recibido: {df}")
    if not (0.0 < confidence < 1.0):
        raise ValueError(f"El nivel de confianza debe estar en (0, 1), recibido: {confidence}")

    target = 1.0 - confidence
    lo, hi = 0.0, 20.0
    while _betainc(0.5 * df, 0.5, df / (df + hi * hi)) > target:
        hi *= 2.0

    for _ in range(90):
        mid = 0.5 * (lo + hi)
        p_two_tail = _betainc(0.5 * df, 0.5, df / (df + mid * mid))
        if p_two_tail > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def two_sided_t_pvalue(t_stat: float, df: int) -> float:
    """Calcula el valor p bilateral exacto de la prueba t de Student con df grados de libertad."""
    if df < 1:
        raise ValueError(f"df debe ser >= 1, recibido: {df}")
    return float(_betainc(0.5 * df, 0.5, df / (df + t_stat * t_stat)))


def chi2_sf_df3(x: float) -> float:
    """
    Función de supervivencia P(Chi2_3 >= x) exacta para 3 grados de libertad
    (4 categorías - 1 = 3), expresada analíticamente sin dependencias externas.
    """
    if x <= 0.0:
        return 1.0
    return float(math.erfc(math.sqrt(0.5 * x)) + math.sqrt(2.0 * x / math.pi) * math.exp(-0.5 * x))


class ParkingSimulationEngine:
    """Motor de simulación discreta multi-escenario para Supercentro."""

    def __init__(self, model: Optional[ParkingQueuingModel] = None):
        self.model = model or ParkingQueuingModel()

    @staticmethod
    def _effective_service_time(vehicle: ArrivalVehicle, ux_factor_slow: float) -> float:
        """Retorna el tiempo de servicio efectivo aplicando el factor UX si corresponde."""
        if ux_factor_slow == 1.0 or vehicle.user_type not in ("Lento", "Muy lento"):
            return vehicle.base_service_time
        return vehicle.unit_service_exp * (SERVICE_MEANS[vehicle.user_type] * ux_factor_slow)

    @staticmethod
    def _aggregate_by_type(
        records: List[Tuple[str, float, float, float]],
    ) -> Dict[str, Dict[str, float]]:
        """Agrupa registros (tipo_usuario, wq, s, w) por perfil de usuario."""
        grouped: Dict[str, List[Tuple[float, float, float]]] = {u: [] for u in USER_TYPES}
        for utype, wq, s, w in records:
            if utype in grouped:
                grouped[utype].append((wq, s, w))

        summary: Dict[str, Dict[str, float]] = {}
        for u in USER_TYPES:
            vals = grouped[u]
            if not vals:
                summary[u] = {
                    "count": 0,
                    "mean_wait_wq": float("nan"),
                    "mean_service_s": float("nan"),
                    "mean_system_w": float("nan"),
                }
            else:
                arr = np.asarray(vals, dtype=float)
                summary[u] = {
                    "count": len(vals),
                    "mean_wait_wq": float(np.mean(arr[:, 0])),
                    "mean_service_s": float(np.mean(arr[:, 1])),
                    "mean_system_w": float(np.mean(arr[:, 2])),
                }
        return summary

    @staticmethod
    def _simulate_cashier_fcfs(
        assigned_items: List[Tuple[ArrivalVehicle, float]],
        horizon_minutes: float = SIM_MINUTES,
        include_records: bool = False,
    ) -> Dict[str, object]:
        """
        Simula un cajero individual bajo disciplina FCFS (cola independiente M/M/1)
        y calcula métricas exactas respetando la Ley de Little sobre la trayectoria.
        """
        n = len(assigned_items)
        if n == 0:
            res: Dict[str, object] = {
                "total_customers": 0,
                "completed_in_horizon": 0,
                "overtime_customers": 0,
                "mean_wait_wq": 0.0,
                "std_wait_wq": 0.0,
                "p95_wait_wq": 0.0,
                "max_wait_wq": 0.0,
                "prob_wq_gt_5min": 0.0,
                "mean_service_s": 0.0,
                "std_service_s": 0.0,
                "min_service_s": 0.0,
                "max_service_s": 0.0,
                "mean_system_w": 0.0,
                "std_system_w": 0.0,
                "utilization_rho": 0.0,
                "idle_pct": 100.0,
                "lq_empirical": 0.0,
                "l_empirical": 0.0,
                "horizon_effective": horizon_minutes,
                "counts_by_type": {u: 0 for u in USER_TYPES},
            }
            if include_records:
                res["_records"] = []
            return res

        wait_times = np.empty(n, dtype=float)
        service_times = np.empty(n, dtype=float)
        system_times = np.empty(n, dtype=float)
        counts_by_type = {u: 0 for u in USER_TYPES}
        records: List[Tuple[str, float, float, float]] = []

        free_time = 0.0
        completed_in_horizon = 0

        for idx, (veh, srv_time) in enumerate(assigned_items):
            start_time = veh.arrival_time if veh.arrival_time >= free_time else free_time
            wait = start_time - veh.arrival_time
            end_time = start_time + srv_time
            free_time = end_time

            sys_time = wait + srv_time
            wait_times[idx] = wait
            service_times[idx] = srv_time
            system_times[idx] = sys_time

            if include_records:
                records.append((veh.user_type, wait, srv_time, sys_time))

            counts_by_type[veh.user_type] += 1
            if end_time <= horizon_minutes:
                completed_in_horizon += 1

        horizon_eff = max(horizon_minutes, free_time)
        total_busy = float(np.sum(service_times))
        total_wait = float(np.sum(wait_times))
        total_sys = float(np.sum(system_times))

        res = {
            "total_customers": n,
            "completed_in_horizon": completed_in_horizon,
            "overtime_customers": n - completed_in_horizon,
            "mean_wait_wq": float(np.mean(wait_times)),
            "std_wait_wq": float(np.std(wait_times, ddof=1)) if n > 1 else 0.0,
            "p95_wait_wq": float(np.percentile(wait_times, 95)),
            "max_wait_wq": float(np.max(wait_times)),
            "prob_wq_gt_5min": float(np.mean(wait_times > 5.0) * 100.0),
            "mean_service_s": float(np.mean(service_times)),
            "std_service_s": float(np.std(service_times, ddof=1)) if n > 1 else 0.0,
            "min_service_s": float(np.min(service_times)),
            "max_service_s": float(np.max(service_times)),
            "mean_system_w": float(np.mean(system_times)),
            "std_system_w": float(np.std(system_times, ddof=1)) if n > 1 else 0.0,
            "utilization_rho": total_busy / horizon_eff,
            "idle_pct": max(0.0, (1.0 - total_busy / horizon_eff) * 100.0),
            "lq_empirical": total_wait / horizon_eff,
            "l_empirical": total_sys / horizon_eff,
            "horizon_effective": horizon_eff,
            "counts_by_type": counts_by_type,
        }
        if include_records:
            res["_records"] = records
        return res

    def simulate_single_replica(
        self,
        scenario_key: str,
        arrivals: List[ArrivalVehicle],
        routing_seed: int,
        routing_mode: str = "random_mm1",
    ) -> Dict[str, object]:
        """
        Simula una réplica completa (1000 min) para el escenario especificado.

        routing_mode:
          - 'random_mm1': Asignación equiprobable (1/k) entre cajeros elegibles
            manteniendo colas independientes M/M/1.
          - 'shortest_queue': Join-the-Shortest-Queue (JSQ observable no clarividente)
            basado en longitud de fila presente en cola o servicio.
          - 'least_work': Cota inferior clarividente por menor tiempo de liberación.
        """
        cfg = SCENARIO_DEFINITIONS[scenario_key]
        cajeros_cfg: List[Tuple[str, str]] = cfg["cajeros"]  # type: ignore[assignment]
        ux_factor = float(cfg.get("ux_factor_slow", 1.0))
        num_cajeros = len(cajeros_cfg)

        queues_by_cashier: List[List[Tuple[ArrivalVehicle, float]]] = [[] for _ in range(num_cajeros)]
        departure_queues: List[deque[float]] = [deque() for _ in range(num_cajeros)]
        free_times = [0.0 for _ in range(num_cajeros)]

        eligible_by_type: Dict[str, List[int]] = {
            utype: [
                i for i, (_, role) in enumerate(cajeros_cfg)
                if utype in ROLE_ALLOWED_TYPES[role]
            ]
            for utype in USER_TYPES
        }

        rng = np.random.default_rng(routing_seed)
        waits_by_arrival_order: List[Tuple[float, float, float, str, float, str]] = []

        for veh in arrivals:
            eligible = eligible_by_type[veh.user_type]
            if len(eligible) == 1:
                chosen = eligible[0]
            elif routing_mode == "random_mm1":
                chosen = eligible[int(rng.integers(0, len(eligible)))]
            elif routing_mode == "shortest_queue":
                for idx in eligible:
                    dq = departure_queues[idx]
                    while dq and dq[0] <= veh.arrival_time:
                        dq.popleft()
                min_q = min(len(departure_queues[idx]) for idx in eligible)
                tied = [idx for idx in eligible if len(departure_queues[idx]) == min_q]
                chosen = tied[0] if len(tied) == 1 else tied[int(rng.integers(0, len(tied)))]
            elif routing_mode == "least_work":
                chosen = min(eligible, key=lambda idx: (free_times[idx], idx))
            else:
                raise ValueError(f"Modo de enrutamiento desconocido: {routing_mode}")

            srv_time = self._effective_service_time(veh, ux_factor)
            queues_by_cashier[chosen].append((veh, srv_time))

            start_t = max(veh.arrival_time, free_times[chosen])
            wait_t = start_t - veh.arrival_time
            end_t = start_t + srv_time
            free_times[chosen] = end_t
            departure_queues[chosen].append(end_t)

            cname = cajeros_cfg[chosen][0]
            waits_by_arrival_order.append(
                (veh.arrival_time, wait_t, wait_t + srv_time, cname, srv_time, veh.user_type)
            )

        cashier_results: Dict[str, Dict[str, object]] = {}
        all_records: List[Tuple[str, float, float, float]] = []

        for idx, (cname, role) in enumerate(cajeros_cfg):
            assigned = queues_by_cashier[idx]
            res = self._simulate_cashier_fcfs(
                assigned,
                self.model.horizon_minutes,
                include_records=True,
            )
            recs = res.pop("_records")
            all_records.extend(recs)  # type: ignore[arg-type]
            res["cashier_name"] = cname
            res["role"] = role
            cashier_results[cname] = res

        all_waits = [r[1] for r in all_records]
        all_services = [r[2] for r in all_records]
        all_systems = [r[3] for r in all_records]

        metrics_by_type = self._aggregate_by_type(all_records)
        total_customers = len(arrivals)
        completed_in_horizon = sum(int(r["completed_in_horizon"]) for r in cashier_results.values())
        counts_by_type = {
            u: sum(int(r["counts_by_type"][u]) for r in cashier_results.values())  # type: ignore[index]
            for u in USER_TYPES
        }

        min_srv_cashier = min(cashier_results.values(), key=lambda r: float(r["mean_service_s"]))
        max_srv_cashier = max(cashier_results.values(), key=lambda r: float(r["mean_service_s"]))
        min_sys_cashier = min(cashier_results.values(), key=lambda r: float(r["mean_system_w"]))
        max_sys_cashier = max(cashier_results.values(), key=lambda r: float(r["mean_system_w"]))
        max_wait_cashier = max(cashier_results.values(), key=lambda r: float(r["mean_wait_wq"]))

        return {
            "scenario_key": scenario_key,
            "total_customers": total_customers,
            "completed_in_horizon": completed_in_horizon,
            "overtime_customers": total_customers - completed_in_horizon,
            "counts_by_type": counts_by_type,
            "mean_wait_wq": float(np.mean(all_waits)) if all_waits else 0.0,
            "p95_wait_wq": float(np.percentile(all_waits, 95)) if all_waits else 0.0,
            "max_wait_wq": float(np.max(all_waits)) if all_waits else 0.0,
            "prob_wq_gt_5min": float(np.mean(np.asarray(all_waits) > 5.0) * 100.0) if all_waits else 0.0,
            "waits_by_arrival_order": waits_by_arrival_order,
            "mean_service_s": float(np.mean(all_services)) if all_services else 0.0,
            "mean_system_w": float(np.mean(all_systems)) if all_systems else 0.0,
            "mean_rho": float(np.mean([float(r["utilization_rho"]) for r in cashier_results.values()])),
            "max_rho": float(np.max([float(r["utilization_rho"]) for r in cashier_results.values()])),
            "total_lq": float(sum(float(r["lq_empirical"]) for r in cashier_results.values())),
            "mean_lq_per_cashier": float(np.mean([float(r["lq_empirical"]) for r in cashier_results.values()])),
            "total_l": float(sum(float(r["l_empirical"]) for r in cashier_results.values())),
            "max_cashier_wq": float(max_wait_cashier["mean_wait_wq"]),
            "bottleneck_cashier": str(max_wait_cashier["cashier_name"]),
            "min_service_cashier": str(min_srv_cashier["cashier_name"]),
            "max_service_cashier": str(max_srv_cashier["cashier_name"]),
            "min_system_cashier": str(min_sys_cashier["cashier_name"]),
            "max_system_cashier": str(max_sys_cashier["cashier_name"]),
            "metrics_by_type": metrics_by_type,
            "cashiers": cashier_results,
        }

    @staticmethod
    def _ci95(values: List[float], confidence: float = 0.95) -> Tuple[float, float, float, float]:
        """Retorna (media, desv_est, ic_inf, ic_sup) usando t de Student exacta."""
        clean = [float(v) for v in values if v is not None and not np.isnan(v)]
        arr = np.asarray(clean, dtype=float)
        n = len(arr)
        if n == 0:
            return 0.0, 0.0, 0.0, 0.0
        mean = float(np.mean(arr))
        if n == 1:
            return mean, 0.0, mean, mean
        std = float(np.std(arr, ddof=1))
        t_val = t_crit_two_sided(n - 1, confidence=confidence)
        half = t_val * std / math.sqrt(n)
        return mean, std, mean - half, mean + half

    @staticmethod
    def _required_n_for_precision(
        std: float,
        tol: float,
        pilot_n: int,
        confidence: float = 0.95,
    ) -> Tuple[int, int]:
        """Calcula tamaño de muestra iterativo n = ceil((t_{alpha/2, df} * s / tol)^2)."""
        if std <= 0.0 or tol <= 0.0:
            return 1, 1
        t0 = t_crit_two_sided(max(1, pilot_n - 1), confidence=confidence)
        n_pilot_est = max(2, math.ceil((t0 * std / tol) ** 2))
        n = n_pilot_est
        for _ in range(50):
            t_cur = t_crit_two_sided(max(1, n - 1), confidence=confidence)
            n_next = max(2, math.ceil((t_cur * std / tol) ** 2))
            if n_next == n:
                break
            n = n_next
        return n_pilot_est, n

    def determine_steady_state_replicas(
        self,
        max_replicas: int = 150,
        base_seed: int = 42,
        stability_tol_pct: float = 2.0,
        er_target_pct: float = 7.5,
        sustained_window: int = 20,
        min_replicas: int = 30,
    ) -> Tuple[int, pd.DataFrame]:
        """
        Determina el número total de corridas o réplicas N* identificando el estado estable
        del promedio acumulado sobre Wq y verificando el criterio de precisión ER% en E1_3_Mixtos.
        """
        wq_vals: List[float] = []
        w_vals: List[float] = []
        s_vals: List[float] = []

        for r in range(1, max_replicas + 1):
            arrivals = self.model.generate_exit_arrivals(seed=base_seed + r)
            sim_res = self.simulate_single_replica(
                scenario_key="E1_3_Mixtos",
                arrivals=arrivals,
                routing_seed=base_seed * 100 + r,
                routing_mode="random_mm1",
            )
            wq_vals.append(float(sim_res["mean_wait_wq"]))
            w_vals.append(float(sim_res["mean_system_w"]))
            s_vals.append(float(sim_res["mean_service_s"]))

        wq_final = float(np.mean(wq_vals))
        w_final = float(np.mean(w_vals))
        rows: List[Dict[str, object]] = []

        for r in range(1, max_replicas + 1):
            sub_wq = wq_vals[:r]
            sub_w = w_vals[:r]
            sub_s = s_vals[:r]
            wq_m, wq_sd, wq_l, wq_u = self._ci95(sub_wq)
            w_m, w_sd, w_l, w_u = self._ci95(sub_w)
            s_m = float(np.mean(sub_s))

            wq_me = 0.5 * (wq_u - wq_l)
            w_me = 0.5 * (w_u - w_l)
            wq_er = (wq_me / wq_m * 100.0) if (r >= 2 and wq_m > 0.0) else float("nan")
            w_er = (w_me / w_m * 100.0) if (r >= 2 and w_m > 0.0) else float("nan")
            dev_pct = abs(wq_m - wq_final) / wq_final * 100.0 if wq_final > 0.0 else 0.0
            dev_w_pct = abs(w_m - w_final) / w_final * 100.0 if w_final > 0.0 else 0.0

            rows.append({
                "replica": r,
                "wq_replica_min": wq_vals[r - 1],
                "wq_media_acumulada_min": wq_m,
                "wq_sd_acumulada_min": wq_sd,
                "wq_ic95_inf": wq_l,
                "wq_ic95_sup": wq_u,
                "wq_er_pct": wq_er,
                "desviacion_asintotica_wq_pct": dev_pct,
                "w_replica_min": w_vals[r - 1],
                "w_media_acumulada_min": w_m,
                "w_er_pct": w_er,
                "desviacion_asintotica_w_pct": dev_w_pct,
                "s_media_acumulada_min": s_m,
            })

        df_conv = pd.DataFrame(rows)
        n_detected = max_replicas
        for r in range(max(min_replicas, sustained_window), max_replicas + 1):
            tail_window = df_conv.iloc[r - sustained_window:r]
            tail_rest = df_conv.iloc[r - 1:]
            cond_band = bool((tail_window["desviacion_asintotica_wq_pct"] <= stability_tol_pct).all())
            cond_future = bool((tail_rest["desviacion_asintotica_wq_pct"] <= stability_tol_pct).all())
            cond_er = bool(df_conv.loc[r - 1, "wq_er_pct"] <= er_target_pct)
            if cond_band and cond_future and cond_er:
                n_detected = r
                break

        # Redondear a múltiplo de 10 superior respetando max_replicas (ej. 120 réplicas)
        n_official = min(max_replicas, int(math.ceil(n_detected / 10.0) * 10))
        df_conv["n_detectado_exacto"] = n_detected
        df_conv["n_oficial_seleccionado"] = n_official
        df_conv["en_estado_estable_replicas"] = df_conv["replica"] >= n_detected
        return n_official, df_conv

    def compute_required_replicas(
        self,
        df_replicas: pd.DataFrame,
        confidence: float = 0.95,
        wq_abs_tol_min: float = 1.0,
        w_rel_tol: float = 0.05,
    ) -> pd.DataFrame:
        """
        Aplica el algoritmo de 8 pasos de la Semana 7 sobre una muestra piloto
        (ej. n0=10) para estimar el tamaño muestral requerido por precisión ER%.
        """
        if df_replicas.empty:
            return pd.DataFrame()

        rows: List[Dict[str, object]] = []
        for skey, cfg in SCENARIO_DEFINITIONS.items():
            sub = df_replicas[df_replicas["escenario"] == skey]
            if sub.empty:
                continue
            n0 = len(sub)
            wq_m, wq_sd, wq_l, wq_u = self._ci95(sub["espera_cola_wq_min"].tolist(), confidence)
            w_m, w_sd, w_l, w_u = self._ci95(sub["atencion_total_w_min"].tolist(), confidence)

            w_tol_min = max(1e-6, w_rel_tol * w_m)
            n_wq_0, n_wq_it = self._required_n_for_precision(wq_sd, wq_abs_tol_min, n0, confidence)
            n_w_0, n_w_it = self._required_n_for_precision(w_sd, w_tol_min, n0, confidence)

            wq_se = wq_sd / math.sqrt(n0)
            wq_me = 0.5 * (wq_u - wq_l)
            wq_er_pct = (wq_me / wq_m * 100.0) if wq_m > 0.0 else 0.0
            n_wq_er10 = max(2, math.ceil(n0 * ((wq_er_pct / 10.0) ** 2))) if wq_er_pct > 0 else 2
            n_wq_er75 = max(2, math.ceil(n0 * ((wq_er_pct / 7.5) ** 2))) if wq_er_pct > 0 else 2

            w_se = w_sd / math.sqrt(n0)
            w_me = 0.5 * (w_u - w_l)
            w_er_pct = (w_me / w_m * 100.0) if w_m > 0.0 else 0.0
            n_w_er5 = max(2, math.ceil(n0 * ((w_er_pct / 5.0) ** 2))) if w_er_pct > 0 else 2

            rows.append({
                "escenario": skey,
                "nombre_corto": cfg["nombre_corto"],
                "replicas_piloto_n0": n0,
                "t_crit_piloto_95": t_crit_two_sided(max(1, n0 - 1), confidence=confidence),
                "wq_media_min": wq_m,
                "wq_sd_min": wq_sd,
                "wq_se_min": wq_se,
                "wq_semiamp_ic95_min": wq_me,
                "wq_er_piloto_pct": wq_er_pct,
                "n_req_wq_er10_prof": n_wq_er10,
                "n_req_wq_er75_prof": n_wq_er75,
                "n_req_wq_iterativo": n_wq_it,
                "w_media_min": w_m,
                "w_sd_min": w_sd,
                "w_se_min": w_se,
                "w_semiamp_ic95_min": w_me,
                "w_er_piloto_pct": w_er_pct,
                "n_req_w_er5_prof": n_w_er5,
                "n_req_w_iterativo": n_w_it,
            })
        return pd.DataFrame(rows)

    def _summarize_wait_by_type(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Resume tiempos Wq, S y W e IC95% por escenario y tipo de usuario."""
        if raw_df.empty:
            return pd.DataFrame()
        rows: List[Dict[str, object]] = []
        for (skey, n_corto, utype), sub in raw_df.groupby(
            ["escenario", "nombre_corto", "tipo_usuario"], sort=False
        ):
            wq_m, wq_sd, wq_l, wq_u = self._ci95(sub["wq_min"].tolist())
            s_m, s_sd, _, _ = self._ci95(sub["s_min"].tolist())
            w_m, w_sd, w_l, w_u = self._ci95(sub["w_min"].tolist())
            u_m, u_sd, _, _ = self._ci95(sub["usuarios"].tolist())
            rows.append({
                "escenario": skey,
                "nombre_corto": n_corto,
                "tipo_usuario": utype,
                "usuarios_prom": u_m,
                "usuarios_sd": u_sd,
                "wq_media_min": wq_m,
                "wq_sd_min": wq_sd,
                "wq_ic95_inf": wq_l,
                "wq_ic95_sup": wq_u,
                "s_media_min": s_m,
                "s_sd_min": s_sd,
                "w_media_min": w_m,
                "w_sd_min": w_sd,
                "w_ic95_inf": w_l,
                "w_ic95_sup": w_u,
            })
        return pd.DataFrame(rows)

    def run_multi_replica_experiment(
        self,
        num_replicas: int,
        base_seed: int = 42,
        routing_mode: str = "random_mm1",
        independent_arrivals_per_scenario: bool = False,
    ) -> Dict[str, object]:
        """
        Ejecuta `num_replicas` corridas completas de 1000 min para los 7 escenarios
        utilizando Números Aleatorios Comunes (CRN) cuando `independent_arrivals_per_scenario=False`.
        """
        scenario_keys = list(SCENARIO_DEFINITIONS.keys())
        replica_rows: List[Dict[str, object]] = []
        cashier_rows: List[Dict[str, object]] = []
        wait_type_rows: List[Dict[str, object]] = []

        shared_arrivals: Dict[int, List[ArrivalVehicle]] = {}
        if not independent_arrivals_per_scenario:
            for r in range(1, num_replicas + 1):
                shared_arrivals[r] = self.model.generate_exit_arrivals(seed=base_seed + r)

        for s_idx, skey in enumerate(scenario_keys):
            cfg = SCENARIO_DEFINITIONS[skey]
            for r in range(1, num_replicas + 1):
                arrivals = (
                    self.model.generate_exit_arrivals(seed=base_seed + s_idx * 1000 + r)
                    if independent_arrivals_per_scenario
                    else shared_arrivals[r]
                )
                r_seed = base_seed * 100 + s_idx * 1000 + r
                sim_res = self.simulate_single_replica(
                    scenario_key=skey,
                    arrivals=arrivals,
                    routing_seed=r_seed,
                    routing_mode=routing_mode,
                )

                replica_rows.append({
                    "escenario": skey,
                    "nombre_escenario": cfg["nombre"],
                    "nombre_corto": cfg["nombre_corto"],
                    "num_cajeros": cfg["num_cajeros"],
                    "replica": r,
                    "total_usuarios": sim_res["total_customers"],
                    "atendidos_en_horizonte": sim_res["completed_in_horizon"],
                    "usuarios_fuera_horizonte": sim_res["overtime_customers"],
                    "rapido": sim_res["counts_by_type"]["Rápido"],
                    "normal": sim_res["counts_by_type"]["Normal"],
                    "lento": sim_res["counts_by_type"]["Lento"],
                    "muy_lento": sim_res["counts_by_type"]["Muy lento"],
                    "espera_cola_wq_min": sim_res["mean_wait_wq"],
                    "espera_p95_min": sim_res["p95_wait_wq"],
                    "espera_max_min": sim_res["max_wait_wq"],
                    "prob_espera_mayor_5m_pct": sim_res["prob_wq_gt_5min"],
                    "servicio_medio_s_min": sim_res["mean_service_s"],
                    "atencion_total_w_min": sim_res["mean_system_w"],
                    "utilizacion_media_rho": sim_res["mean_rho"],
                    "utilizacion_max_rho": sim_res["max_rho"],
                    "cola_media_lq_total": sim_res["total_lq"],
                    "cola_media_lq_cajero": sim_res["mean_lq_per_cashier"],
                    "sistema_medio_l": sim_res["total_l"],
                    "peor_wq_cajero_replica_min": sim_res["max_cashier_wq"],
                    "cajero_cuello_botella": sim_res["bottleneck_cashier"],
                    "cajero_menor_servicio": sim_res["min_service_cashier"],
                    "cajero_mayor_servicio": sim_res["max_service_cashier"],
                    "cajero_menor_atencion_total": sim_res["min_system_cashier"],
                    "cajero_mayor_atencion_total": sim_res["max_system_cashier"],
                })

                for utype, mvals in sim_res["metrics_by_type"].items():  # type: ignore[union-attr]
                    wait_type_rows.append({
                        "escenario": skey,
                        "nombre_corto": cfg["nombre_corto"],
                        "replica": r,
                        "tipo_usuario": utype,
                        "usuarios": mvals["count"],
                        "wq_min": mvals["mean_wait_wq"],
                        "s_min": mvals["mean_service_s"],
                        "w_min": mvals["mean_system_w"],
                    })

                for cname, cres in sim_res["cashiers"].items():  # type: ignore[union-attr]
                    cashier_rows.append({
                        "escenario": skey,
                        "nombre_corto": cfg["nombre_corto"],
                        "replica": r,
                        "cajero": cname,
                        "rol": cres["role"],
                        "usuarios_atendidos": cres["total_customers"],
                        "atendidos_en_horizonte": cres["completed_in_horizon"],
                        "rapido": cres["counts_by_type"]["Rápido"],
                        "normal": cres["counts_by_type"]["Normal"],
                        "lento": cres["counts_by_type"]["Lento"],
                        "muy_lento": cres["counts_by_type"]["Muy lento"],
                        "servicio_medio_s_min": cres["mean_service_s"],
                        "espera_cola_wq_min": cres["mean_wait_wq"],
                        "atencion_total_w_min": cres["mean_system_w"],
                        "espera_max_min": cres["max_wait_wq"],
                        "prob_espera_mayor_5m_pct": cres["prob_wq_gt_5min"],
                        "utilizacion_rho": cres["utilization_rho"],
                        "ocio_pct": cres["idle_pct"],
                        "cola_media_lq": cres["lq_empirical"],
                    })

        df_replicas = pd.DataFrame(replica_rows)
        df_cashiers = pd.DataFrame(cashier_rows)
        df_wait_by_type = self._summarize_wait_by_type(pd.DataFrame(wait_type_rows))

        # Resumen detallado por cajero (incluye media, DE, mín, máx e IC95% t para Punto A)
        cashier_summary_rows: List[Dict[str, object]] = []
        for (skey, n_corto, cname, role), csub in df_cashiers.groupby(
            ["escenario", "nombre_corto", "cajero", "rol"], sort=False
        ):
            s_m, s_sd, s_l, s_u = self._ci95(csub["servicio_medio_s_min"].tolist())
            wq_m, wq_sd, wq_l, wq_u = self._ci95(csub["espera_cola_wq_min"].tolist())
            w_m, w_sd, w_l, w_u = self._ci95(csub["atencion_total_w_min"].tolist())
            u_m, u_sd, _, _ = self._ci95(csub["usuarios_atendidos"].tolist())

            cashier_summary_rows.append({
                "escenario": skey,
                "nombre_corto": n_corto,
                "cajero": cname,
                "rol": role,
                "usuarios_prom": u_m,
                "usuarios_sd": u_sd,
                "usuarios_min": int(csub["usuarios_atendidos"].min()),
                "usuarios_max": int(csub["usuarios_atendidos"].max()),
                "rapido_prom": float(csub["rapido"].mean()),
                "normal_prom": float(csub["normal"].mean()),
                "lento_prom": float(csub["lento"].mean()),
                "muy_lento_prom": float(csub["muy_lento"].mean()),
                "servicio_s_prom": s_m,
                "servicio_s_sd": s_sd,
                "servicio_s_min": float(csub["servicio_medio_s_min"].min()),
                "servicio_s_max": float(csub["servicio_medio_s_min"].max()),
                "servicio_s_ic95_inf": s_l,
                "servicio_s_ic95_sup": s_u,
                "espera_wq_prom": wq_m,
                "espera_wq_sd": wq_sd,
                "espera_wq_min": float(csub["espera_cola_wq_min"].min()),
                "espera_wq_max": float(csub["espera_cola_wq_min"].max()),
                "espera_wq_ic95_inf": wq_l,
                "espera_wq_ic95_sup": wq_u,
                "atencion_w_prom": w_m,
                "atencion_w_sd": w_sd,
                "atencion_w_min": float(csub["atencion_total_w_min"].min()),
                "atencion_w_max": float(csub["atencion_total_w_min"].max()),
                "atencion_w_ic95_inf": w_l,
                "atencion_w_ic95_sup": w_u,
                "prob_wq_mayor_5m_prom": float(csub["prob_espera_mayor_5m_pct"].mean()),
                "utilizacion_rho_prom": float(csub["utilizacion_rho"].mean()),
                "ocio_pct_prom": float(csub["ocio_pct"].mean()),
                "lq_prom": float(csub["cola_media_lq"].mean()),
            })
        df_cashier_summary = pd.DataFrame(cashier_summary_rows)

        # Resumen consolidado por escenario
        summary_rows: List[Dict[str, object]] = []
        for skey in scenario_keys:
            sub = df_replicas[df_replicas["escenario"] == skey]
            c_sub = df_cashier_summary[df_cashier_summary["escenario"] == skey]
            theo = self.model.analyze_scenario_theoretically(skey)

            wq_m, wq_sd, wq_l, wq_u = self._ci95(sub["espera_cola_wq_min"].tolist())
            w_m, w_sd, w_l, w_u = self._ci95(sub["atencion_total_w_min"].tolist())
            s_m, s_sd, _, _ = self._ci95(sub["servicio_medio_s_min"].tolist())
            rho_m, rho_sd, _, _ = self._ci95(sub["utilizacion_media_rho"].tolist())
            usr_m, usr_sd, _, _ = self._ci95(sub["total_usuarios"].tolist())

            peor_cajero_wq_prom = float(c_sub["espera_wq_prom"].max())
            peor_cajero_p5_prom = float(c_sub["prob_wq_mayor_5m_prom"].max())
            rho_max_media = float(sub["utilizacion_max_rho"].mean())

            summary_rows.append({
                "escenario": skey,
                "nombre_escenario": theo["nombre"],
                "nombre_corto": theo["nombre_corto"],
                "num_cajeros": theo["num_cajeros"],
                "ux_factor_slow": theo["ux_factor_slow"],
                "replicas": num_replicas,
                "usuarios_promedio": usr_m,
                "usuarios_sd": usr_sd,
                "espera_wq_media_min": wq_m,
                "espera_wq_sd_min": wq_sd,
                "espera_wq_se_min": wq_sd / math.sqrt(num_replicas) if num_replicas > 0 else 0.0,
                "espera_wq_ic95_inf": wq_l,
                "espera_wq_ic95_sup": wq_u,
                "espera_wq_er_pct": ((0.5 * (wq_u - wq_l)) / wq_m * 100.0) if wq_m > 0.0 else 0.0,
                "peor_cajero_wq_prom_min": peor_cajero_wq_prom,
                "peor_wq_por_replica_media_min": float(sub["peor_wq_cajero_replica_min"].mean()),
                "prob_wq_mayor_5m_pct": float(sub["prob_espera_mayor_5m_pct"].mean()),
                "prob_wq_mayor_5m_peor_cajero_pct": peor_cajero_p5_prom,
                "prob_wq_mayor_5m_teorica_pct": float(theo["weighted_prob_wq_gt_5min"]) * 100.0,
                "servicio_s_media_min": s_m,
                "servicio_s_sd_min": s_sd,
                "sistema_w_media_min": w_m,
                "sistema_w_sd_min": w_sd,
                "sistema_w_se_min": w_sd / math.sqrt(num_replicas) if num_replicas > 0 else 0.0,
                "sistema_w_ic95_inf": w_l,
                "sistema_w_ic95_sup": w_u,
                "sistema_w_er_pct": ((0.5 * (w_u - w_l)) / w_m * 100.0) if w_m > 0.0 else 0.0,
                "utilizacion_rho_media": rho_m,
                "utilizacion_rho_sd": rho_sd,
                "utilizacion_max_media": rho_max_media,
                "regimen_estabilidad": classify_utilization_regime(rho_max_media),
                "regimen_estabilidad_teorico": theo["regime_max_rho"],
                "lq_total_simulada": float(sub["cola_media_lq_total"].mean()),
                "lq_cajero_simulada": float(sub["cola_media_lq_cajero"].mean()),
                "l_total_simulada": float(sub["sistema_medio_l"].mean()),
                "wq_teorica_mm1_min": theo["weighted_wq_mm1"],
                "wq_teorica_mg1_min": theo["weighted_wq_mg1"],
                "w_teorica_mm1_min": theo["weighted_w_mm1"],
                "w_teorica_mg1_min": theo["weighted_w_mg1"],
                "rho_teorica_media": theo["mean_rho"],
                "rho_teorica_max": theo["max_rho"],
            })

        df_summary = pd.DataFrame(summary_rows)
        return {
            "num_replicas": num_replicas,
            "routing_mode": routing_mode,
            "df_replicas": df_replicas,
            "df_cashiers": df_cashiers,
            "df_wait_by_type": df_wait_by_type,
            "df_summary": df_summary,
            "df_cashier_summary": df_cashier_summary,
        }

    def eliminate_transient_and_compare(
        self,
        num_replicas: int,
        base_seed: int = 42,
        window: int = 25,
        k_horizon: int = 500,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Punto E: Identifica el período transitorio (warm-up desde arranque vacío L(0)=0)
        mediante promedios móviles transversales sobre `num_replicas`, elimina los primeros
        k* - 1 clientes y compara las estadísticas antes vs. después (por escenario y por cajero en E1).
        """
        shared_arrivals = {
            r: self.model.generate_exit_arrivals(seed=base_seed + r)
            for r in range(1, num_replicas + 1)
        }
        summary_rows: List[Dict[str, object]] = []
        curve_e1_rows: List[Dict[str, object]] = []
        cashier_e1_rows: List[Dict[str, object]] = []

        for s_idx, (skey, cfg) in enumerate(SCENARIO_DEFINITIONS.items()):
            theo = self.model.analyze_scenario_theoretically(skey)
            mat_arr = np.full((num_replicas, k_horizon), np.nan, dtype=float)
            mat_wq = np.full((num_replicas, k_horizon), np.nan, dtype=float)
            mat_w = np.full((num_replicas, k_horizon), np.nan, dtype=float)
            rep_seqs: List[List[Tuple[float, float, float, str, float, str]]] = []

            for r in range(1, num_replicas + 1):
                arrivals = shared_arrivals[r]
                r_seed = base_seed * 100 + s_idx * 1000 + r
                sim_res = self.simulate_single_replica(
                    scenario_key=skey,
                    arrivals=arrivals,
                    routing_seed=r_seed,
                    routing_mode="random_mm1",
                )
                seq = sim_res["waits_by_arrival_order"]  # type: ignore[assignment]
                rep_seqs.append(seq)
                lim = min(k_horizon, len(seq))
                for idx in range(lim):
                    mat_arr[r - 1, idx] = seq[idx][0]
                    mat_wq[r - 1, idx] = seq[idx][1]
                    mat_w[r - 1, idx] = seq[idx][2]

            wq_cross = np.nanmean(mat_wq, axis=0)
            arr_cross = np.nanmean(mat_arr, axis=0)

            mov_avgs = [
                float(np.mean(wq_cross[i:i + window]))
                for i in range(len(wq_cross) - window + 1)
            ]

            # Rango candidato adaptado a la utilización del escenario para detectar estabilización
            min_cand = 120 if float(theo["max_rho"]) >= 0.70 else 60
            max_cand = 240 if float(theo["max_rho"]) >= 0.70 else 150
            cand_indices: List[int] = []
            cand_vars: List[float] = []
            for i in range(max(0, min_cand - window), min(len(mov_avgs) - window + 1, max_cand - window + 1)):
                k_cand = i + window
                if min_cand <= k_cand <= max_cand:
                    cand_indices.append(k_cand)
                    cand_vars.append(float(np.var(mov_avgs[i:i + window])))

            k_cut = cand_indices[int(np.argmin(cand_vars))] if cand_vars else min_cand
            t_cut_min = float(arr_cross[k_cut - 1])

            wq_all_reps = [float(np.mean([x[1] for x in seq])) for seq in rep_seqs if seq]
            w_all_reps = [float(np.mean([x[2] for x in seq])) for seq in rep_seqs if seq]
            wq_ss_reps = [
                float(np.mean([x[1] for x in seq[k_cut - 1:]]))
                for seq in rep_seqs
                if len(seq) >= k_cut
            ]
            w_ss_reps = [
                float(np.mean([x[2] for x in seq[k_cut - 1:]]))
                for seq in rep_seqs
                if len(seq) >= k_cut
            ]

            wq_all_m = float(np.mean(wq_all_reps))
            wq_ss_m, wq_ss_sd, wq_ss_l, wq_ss_u = self._ci95(wq_ss_reps)
            n_ss_reps = len(wq_ss_reps)
            wq_ss_se = wq_ss_sd / math.sqrt(n_ss_reps) if n_ss_reps > 0 else 0.0
            w_all_m = float(np.mean(w_all_reps))
            w_ss_m = float(np.mean(w_ss_reps))
            sesgo_pct = ((wq_ss_m - wq_all_m) / wq_ss_m * 100.0) if wq_ss_m > 0 else 0.0
            sesgo_w_pct = ((w_ss_m - w_all_m) / w_ss_m * 100.0) if w_ss_m > 0 else 0.0

            summary_rows.append({
                "escenario": skey,
                "nombre_corto": cfg["nombre_corto"],
                "k_corte_vehiculos": k_cut,
                "tiempo_corte_aprox_min": t_cut_min,
                "wq_con_transitorio_min": wq_all_m,
                "wq_estado_estable_min": wq_ss_m,
                "wq_estado_estable_sd_min": wq_ss_sd,
                "wq_estado_estable_se_min": wq_ss_se,
                "wq_estado_estable_ic95_inf": wq_ss_l,
                "wq_estado_estable_ic95_sup": wq_ss_u,
                "n_replicas_estado_estable": n_ss_reps,
                "wq_teorica_mg1_min": theo["weighted_wq_mg1"],
                "w_con_transitorio_min": w_all_m,
                "w_estado_estable_min": w_ss_m,
                "w_teorica_mg1_min": theo["weighted_w_mg1"],
                "sesgo_subestimacion_wq_pct": sesgo_pct,
                "sesgo_subestimacion_w_pct": sesgo_w_pct,
            })

            if skey == "E1_3_Mixtos":
                for idx in range(k_horizon):
                    ma_val = (
                        float(np.mean(wq_cross[max(0, idx - window + 1):idx + 1]))
                        if idx >= window - 1
                        else float(np.mean(wq_cross[:idx + 1]))
                    )
                    curve_e1_rows.append({
                        "vehiculo_idx": idx + 1,
                        "tiempo_medio_llegada_min": float(arr_cross[idx]),
                        "wq_media_transversal_min": float(wq_cross[idx]),
                        "wq_promedio_movil_min": ma_val,
                        "en_estado_estable": (idx + 1) >= k_cut,
                    })

                cashier_names = [cname for cname, _ in cfg["cajeros"]]  # type: ignore[misc]
                for cname in cashier_names:
                    c_wq_all, c_wq_ss, c_w_all, c_w_ss = [], [], [], []
                    for seq in rep_seqs:
                        all_c = [x for x in seq if x[3] == cname]
                        ss_c = [x for x in seq[k_cut - 1:] if x[3] == cname]
                        if all_c:
                            c_wq_all.append(float(np.mean([x[1] for x in all_c])))
                            c_w_all.append(float(np.mean([x[2] for x in all_c])))
                        if ss_c:
                            c_wq_ss.append(float(np.mean([x[1] for x in ss_c])))
                            c_w_ss.append(float(np.mean([x[2] for x in ss_c])))
                    m_wq_all = float(np.mean(c_wq_all))
                    m_wq_ss = float(np.mean(c_wq_ss))
                    cashier_e1_rows.append({
                        "cajero": cname,
                        "k_corte_global": k_cut,
                        "wq_con_transitorio_min": m_wq_all,
                        "wq_estado_estable_min": m_wq_ss,
                        "w_con_transitorio_min": float(np.mean(c_w_all)),
                        "w_estado_estable_min": float(np.mean(c_w_ss)),
                        "diferencia_wq_min": m_wq_ss - m_wq_all,
                        "sesgo_subestimacion_pct": ((m_wq_ss - m_wq_all) / m_wq_ss * 100.0) if m_wq_ss > 0 else 0.0,
                    })

        return pd.DataFrame(summary_rows), pd.DataFrame(curve_e1_rows), pd.DataFrame(cashier_e1_rows)

    def validate_isolated_mm1_by_user_type(
        self,
        num_replicas: int = 100,
        base_seed: int = 42,
        horizon_minutes: float = 3000.0,
    ) -> pd.DataFrame:
        """
        Valida el simulador M/M/1 puro de forma aislada para cada perfil de usuario
        contrastando las métricas post-warmup contra las fórmulas exactas M/M/1.
        """
        rows: List[Dict[str, object]] = []
        theo_rows = {r["tipo_usuario"]: r for r in self.model.analyze_user_type_isolated_mm1()}

        for u_idx, utype in enumerate(USER_TYPES):
            mean_ia = self.model.arrival_means[utype]
            mean_s = self.model.service_means[utype]
            tr = theo_rows[utype]

            w_ss_reps: List[float] = []
            wq_ss_reps: List[float] = []
            s_reps: List[float] = []
            for r in range(1, num_replicas + 1):
                rng = np.random.default_rng(base_seed * 10 + u_idx * 500 + r)
                t = 0.0
                free_t = 0.0
                w_list: List[float] = []
                wq_list: List[float] = []
                s_list: List[float] = []
                while True:
                    t += float(rng.exponential(scale=mean_ia))
                    if t > horizon_minutes:
                        break
                    s = float(rng.exponential(scale=mean_s))
                    st = t if t >= free_t else free_t
                    wq = st - t
                    free_t = st + s
                    wq_list.append(wq)
                    w_list.append(wq + s)
                    s_list.append(s)

                cut = max(1, len(w_list) // 4)
                wq_ss_reps.append(float(np.mean(wq_list[cut:])))
                w_ss_reps.append(float(np.mean(w_list[cut:])))
                s_reps.append(float(np.mean(s_list)))

            w_m, w_sd, w_l, w_u = self._ci95(w_ss_reps)
            wq_m, wq_sd, _, _ = self._ci95(wq_ss_reps)
            s_m = float(np.mean(s_reps))

            if bool(tr["estable"]):
                w_teo = float(tr["w_sistema_min"])
                wq_teo = float(tr["wq_cola_min"])
                se_w = w_sd / math.sqrt(len(w_ss_reps))
                t_stat = (w_m - w_teo) / se_w if se_w > 0 else 0.0
                p_val = two_sided_t_pvalue(t_stat, len(w_ss_reps) - 1)
                veredicto = "Validado (p > 0.05)" if p_val > 0.05 else "Revisar"
            else:
                w_teo = float("inf")
                wq_teo = float("inf")
                t_stat = float("nan")
                p_val = float("nan")
                veredicto = "Diverge según teoría (ρ = 1.0)"

            rows.append({
                "tipo_usuario": utype,
                "rho_teorico": tr["rho"],
                "estable": tr["estable"],
                "s_teorico_min": mean_s,
                "s_simulado_min": s_m,
                "wq_teorico_mm1_min": wq_teo,
                "wq_simulado_est_min": wq_m,
                "w_teorico_mm1_min": w_teo,
                "w_simulado_est_min": w_m,
                "w_ic95_inf": w_l,
                "w_ic95_sup": w_u,
                "t_stat_w": t_stat,
                "p_valor_w": p_val,
                "resultado_validacion": veredicto,
            })
        return pd.DataFrame(rows)

    def compute_vv_and_critical_matrix(
        self,
        res_official: Dict[str, object],
        df_warmup: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Punto D y criterios de decisión (Punto C): Consolida Verificación (Ley de Little),
        Calibración (MAE y bondad de ajuste Chi2), Validación (prueba t post-warmup vs M/G/1)
        y evaluación dinámica frente a los umbrales aceptables y críticos del proyecto.
        """
        df_sum = res_official["df_summary"].set_index("escenario")
        df_rep = res_official["df_replicas"]
        df_caj = res_official["df_cashier_summary"]
        df_warm_idx = df_warmup.set_index("escenario")

        # 1. Verificación exacta de Ley de Little sobre trayectoria completa en cada escenario
        arrivals_ref = self.model.generate_exit_arrivals(seed=42)
        little_err_map: Dict[str, float] = {}
        little_ok_map: Dict[str, bool] = {}
        for s_idx, skey in enumerate(SCENARIO_DEFINITIONS):
            sim_ref = self.simulate_single_replica(skey, arrivals_ref, routing_seed=4200 + s_idx * 1000 + 1)
            max_err = max(
                abs(float(c["lq_empirical"]) - (float(c["total_customers"]) / float(c["horizon_effective"])) * float(c["mean_wait_wq"]))
                for c in sim_ref["cashiers"].values()  # type: ignore[union-attr]
                if int(c["total_customers"]) > 0
            )
            little_err_map[skey] = max_err
            little_ok_map[skey] = max_err < 1e-10

        # 2. Calibración sobre E1_3_Mixtos (proporciones 25/20/27.5/27.5 y bondad de ajuste Chi2)
        sub_e1 = df_rep[df_rep["escenario"] == "E1_3_Mixtos"]
        tot_usr_all = float(sub_e1["total_usuarios"].sum())
        col_map = {"Rápido": "rapido", "Normal": "normal", "Lento": "lento", "Muy lento": "muy_lento"}
        obs_counts = {u: float(sub_e1[col_map[u]].sum()) for u in USER_TYPES}
        exp_counts = {u: tot_usr_all * self.model.user_type_probs[u] for u in USER_TYPES}

        calib_mae_pp = float(
            np.mean([
                abs((obs_counts[u] / tot_usr_all) - self.model.user_type_probs[u]) * 100.0
                for u in USER_TYPES
            ])
        )
        chi2_stat = sum(
            ((obs_counts[u] - exp_counts[u]) ** 2) / exp_counts[u]
            for u in USER_TYPES
        )
        chi2_pval = chi2_sf_df3(chi2_stat)

        df_wt = res_official["df_wait_by_type"]
        wt_e1 = df_wt[df_wt["escenario"] == "E1_3_Mixtos"].set_index("tipo_usuario")
        srv_rel_err_pct = float(
            np.max([
                abs(float(wt_e1.loc[u, "s_media_min"]) - self.model.service_means[u]) / self.model.service_means[u] * 100.0
                for u in USER_TYPES
            ])
        )

        # 3. Evaluación V&V y criterios críticos dinámicos por escenario
        rows: List[Dict[str, object]] = []
        for skey, cfg in SCENARIO_DEFINITIONS.items():
            r_sum = df_sum.loc[skey]
            w_row = df_warm_idx.loc[skey]
            c_sub = df_caj[df_caj["escenario"] == skey]

            wq_sim = float(r_sum["espera_wq_media_min"])
            wq_ss = float(w_row["wq_estado_estable_min"])
            wq_mg1 = float(r_sum["wq_teorica_mg1_min"])
            wq_ss_se = float(w_row["wq_estado_estable_se_min"])
            n_ss = int(w_row["n_replicas_estado_estable"])

            w_sim = float(r_sum["sistema_w_media_min"])
            peor_wq = float(r_sum["peor_cajero_wq_prom_min"])
            rho_med = float(r_sum["utilizacion_rho_media"]) * 100.0
            rho_max = float(r_sum["utilizacion_max_media"]) * 100.0
            lq_cajero = float(r_sum["lq_cajero_simulada"])
            prob_gt5_global = float(r_sum["prob_wq_mayor_5m_pct"])
            prob_gt5_peor = float(c_sub["prob_wq_mayor_5m_prom"].max())

            # Prueba t bilateral frente a referencia analítica M/G/1 usando el error estándar estacionario
            t_stat = (wq_ss - wq_mg1) / wq_ss_se if wq_ss_se > 0 else 0.0
            p_val = two_sided_t_pvalue(t_stat, max(1, n_ss - 1))

            if wq_sim <= 3.0 and peor_wq <= 3.5:
                crit_wq = "Óptimo (<3m)"
            elif wq_sim <= 5.0 and peor_wq <= 5.5:
                crit_wq = "Aceptable (<=5m)"
            else:
                crit_wq = "Crítico (>5m)"

            if w_sim < 5.0:
                crit_w = "Óptimo (<5m)"
            elif w_sim <= 8.0:
                crit_w = "Aceptable (<=8m)"
            else:
                crit_w = "Crítico (>8m)"

            crit_rho = classify_utilization_regime(rho_max / 100.0)

            if lq_cajero < 3.0:
                crit_lq = "Aceptable (<3 cli)"
            elif lq_cajero <= 5.0:
                crit_lq = "Alerta (3-5 cli)"
            else:
                crit_lq = "Crítico (>5 cli)"

            if prob_gt5_peor < 10.0:
                crit_prob5 = "Óptimo (<10%)"
            elif prob_gt5_peor <= 20.0:
                crit_prob5 = "Aceptable (<=20%)"
            else:
                crit_prob5 = "Crítico (>20%)"

            if (
                "Crítico" in crit_wq
                or "Crítico" in crit_w
                or "Crítico" in crit_lq
                or "Crítico" in crit_rho
            ):
                dictamen = "NO RECOMENDADO: excede umbrales críticos de espera o saturación"
            elif "Subutilizado" in crit_rho:
                dictamen = "REDUNDANTE: cumple metas de espera pero con subutilización elevada y sobrecosto de equipos"
            elif "Crítico" in crit_prob5:
                dictamen = (
                    "RECOMENDADO CON MITIGACIÓN JSQ/UX: cumple Wq<=5m, W<=8m y Lq<3, "
                    "con P(Wq>5m) sobre 20% bajo llegada aleatoria"
                )
            else:
                dictamen = "ÓPTIMO: cumple integralmente las metas de espera, riesgo P(Wq>5m) y utilización"

            rows.append({
                "escenario": skey,
                "nombre_corto": cfg["nombre_corto"],
                "num_cajeros": cfg["num_cajeros"],
                "verificacion_little_max_err": little_err_map[skey],
                "verificacion_little_ok": little_ok_map[skey],
                "calibracion_mae_pp": calib_mae_pp,
                "calibracion_chi2_stat": chi2_stat,
                "calibracion_chi2_pval": chi2_pval,
                "calibracion_srv_max_rel_err_pct": srv_rel_err_pct,
                "wq_sim_min": wq_sim,
                "wq_estable_min": wq_ss,
                "wq_teorica_mg1_min": wq_mg1,
                "t_stat_vs_mg1": t_stat,
                "p_valor_vs_mg1": p_val,
                "wq_er_pct": float(r_sum["espera_wq_er_pct"]),
                "w_sim_min": w_sim,
                "w_er_pct": float(r_sum["sistema_w_er_pct"]),
                "peor_cajero_wq_prom_min": peor_wq,
                "lq_cajero": lq_cajero,
                "rho_media_pct": rho_med,
                "rho_max_pct": rho_max,
                "prob_wq_mayor_5m_global_pct": prob_gt5_global,
                "prob_wq_mayor_5m_peor_cajero_pct": prob_gt5_peor,
                "criterio_wq": crit_wq,
                "criterio_w": crit_w,
                "criterio_rho": crit_rho,
                "criterio_lq": crit_lq,
                "criterio_prob_wq_5m": crit_prob5,
                "dictamen_global": dictamen,
            })

        return pd.DataFrame(rows)
