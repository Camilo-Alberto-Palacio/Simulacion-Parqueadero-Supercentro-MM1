"""
Modelo Teórico M/M/1, Parametrización Axiomática y Generador de Llegadas
para el Sistema de Pago de Parqueaderos del Centro Comercial Supercentro.

Cumple exactamente con las especificaciones de la Actividad Didáctica 2-M4:
- Punto de salida con 3 cajeros base independientes M/M/1, filas independientes,
  sin cambio de fila ni deserción.
- Horizonte por réplica: 1000 minutos (según guía de laboratorio del curso).
- Perfiles de usuario (Exponenciales de servicio y llegada):
  * Rápido    (25.0 %): E[S] = 1.0 min, E[IA] = 3.0 min
  * Normal    (20.0 %): E[S] = 3.0 min, E[IA] = 3.0 min
  * Lento     (27.5 %): E[S] = 4.0 min, E[IA] = 5.0 min
  * Muy lento (27.5 %): E[S] = 6.0 min, E[IA] = 7.0 min
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import numpy as np


BASE_CASHIERS: int = 3
SIM_MINUTES: float = 1000.0

USER_TYPES: List[str] = ["Rápido", "Normal", "Lento", "Muy lento"]

# El 25 % son rápidos, 20 % normales y el resto (55 %) se divide equitativamente entre lento y muy lento.
USER_TYPE_PROBS: Dict[str, float] = {
    "Rápido": 0.25,
    "Normal": 0.20,
    "Lento": 0.275,
    "Muy lento": 0.275,
}

# Exponencial de uso del servicio por tipo de usuario (media en minutos)
SERVICE_MEANS: Dict[str, float] = {
    "Rápido": 1.0,
    "Normal": 3.0,
    "Lento": 4.0,
    "Muy lento": 6.0,
}

# Media de llegada exponencial por cajero para cada tipo de usuario (minutos)
ARRIVAL_MEANS: Dict[str, float] = {
    "Rápido": 3.0,
    "Normal": 3.0,
    "Lento": 5.0,
    "Muy lento": 7.0,
}

ROLE_ALLOWED_TYPES: Dict[str, Set[str]] = {
    "Mixto": {"Rápido", "Normal", "Lento", "Muy lento"},
    "Exprés": {"Rápido", "Normal"},
    "Estándar": {"Lento", "Muy lento"},
}

SCENARIO_DEFINITIONS: Dict[str, Dict[str, object]] = {
    "E1_3_Mixtos": {
        "nombre": "Escenario 1: 3 Cajeros Mixtos (Base actual)",
        "nombre_corto": "3 Mixtos",
        "num_cajeros": 3,
        "ux_factor_slow": 1.0,
        "cajeros": [
            ("Cajero 1", "Mixto"),
            ("Cajero 2", "Mixto"),
            ("Cajero 3", "Mixto"),
        ],
        "descripcion": "Configuración actual en cada salida: 3 cajeros independientes para todos los usuarios.",
    },
    "E2_4_Mixtos": {
        "nombre": "Escenario 2: 4 Cajeros Mixtos (+1 cajero)",
        "nombre_corto": "4 Mixtos",
        "num_cajeros": 4,
        "ux_factor_slow": 1.0,
        "cajeros": [
            ("Cajero 1", "Mixto"),
            ("Cajero 2", "Mixto"),
            ("Cajero 3", "Mixto"),
            ("Cajero 4", "Mixto"),
        ],
        "descripcion": "Ampliación a 4 cajeros polivalentes por salida preservando demanda total.",
    },
    "E3_5_Mixtos": {
        "nombre": "Escenario 3: 5 Cajeros Mixtos (+2 cajeros)",
        "nombre_corto": "5 Mixtos",
        "num_cajeros": 5,
        "ux_factor_slow": 1.0,
        "cajeros": [
            ("Cajero 1", "Mixto"),
            ("Cajero 2", "Mixto"),
            ("Cajero 3", "Mixto"),
            ("Cajero 4", "Mixto"),
            ("Cajero 5", "Mixto"),
        ],
        "descripcion": "Ampliación a 5 cajeros polivalentes por salida para cumplir holgadamente metas de espera.",
    },
    "E4_6_Mixtos": {
        "nombre": "Escenario 4: 6 Cajeros Mixtos (+3 cajeros)",
        "nombre_corto": "6 Mixtos",
        "num_cajeros": 6,
        "ux_factor_slow": 1.0,
        "cajeros": [
            ("Cajero 1", "Mixto"),
            ("Cajero 2", "Mixto"),
            ("Cajero 3", "Mixto"),
            ("Cajero 4", "Mixto"),
            ("Cajero 5", "Mixto"),
            ("Cajero 6", "Mixto"),
        ],
        "descripcion": "Escenario de máxima holgura (6 cajeros) para evaluar rendimientos decrecientes y subutilización.",
    },
    "E5_4_Esp_1E3L": {
        "nombre": "Escenario 5: 4 Especializados (1 Exprés + 3 Estándar)",
        "nombre_corto": "4 Esp (1E+3L)",
        "num_cajeros": 4,
        "ux_factor_slow": 1.0,
        "cajeros": [
            ("Cajero 1 (Exprés)", "Exprés"),
            ("Cajero 2 (Estándar)", "Estándar"),
            ("Cajero 3 (Estándar)", "Estándar"),
            ("Cajero 4 (Estándar)", "Estándar"),
        ],
        "descripcion": "1 cajero exclusivo para Rápido/Normal (45%) y 3 cajeros para Lento/Muy lento (55%).",
    },
    "E6_5_Esp_1E4L": {
        "nombre": "Escenario 6: 5 Especializados (1 Exprés + 4 Estándar)",
        "nombre_corto": "5 Esp (1E+4L)",
        "num_cajeros": 5,
        "ux_factor_slow": 1.0,
        "cajeros": [
            ("Cajero 1 (Exprés)", "Exprés"),
            ("Cajero 2 (Estándar)", "Estándar"),
            ("Cajero 3 (Estándar)", "Estándar"),
            ("Cajero 4 (Estándar)", "Estándar"),
            ("Cajero 5 (Estándar)", "Estándar"),
        ],
        "descripcion": "1 cajero Exprés (Rápido/Normal) y 4 cajeros Estándar (Lento/Muy lento).",
    },
    "E7_4_Mix_UX": {
        "nombre": "Escenario 7: 4 Cajeros Mixtos + Mejora UX/LPR (-25% tiempo lentos)",
        "nombre_corto": "4 Mix + UX/LPR",
        "num_cajeros": 4,
        "ux_factor_slow": 0.75,
        "cajeros": [
            ("Cajero 1", "Mixto"),
            ("Cajero 2", "Mixto"),
            ("Cajero 3", "Mixto"),
            ("Cajero 4", "Mixto"),
        ],
        "descripcion": (
            "4 cajeros mixtos con actualización de interfaz (lectura automática de placa LPR/QR) "
            "que reduce en 25 % la interacción de usuarios Lentos (4→3 min) y Muy lentos (6→4.5 min)."
        ),
    },
}


@dataclass(frozen=True)
class ArrivalVehicle:
    """Representa un conductor/vehículo que arriba al punto de pago del parqueadero."""

    vehicle_id: int
    arrival_time: float
    interarrival_time: float
    user_type: str
    unit_service_exp: float
    base_service_time: float


@dataclass(frozen=True)
class MM1AnalyticalMetrics:
    """Métricas analíticas exactas de estado estable M/M/1 y referencia Pollaczek-Khinchine M/G/1."""

    role: str
    lam: float
    mu: float
    rho: float
    p0: float
    mean_service: float
    mean_s2: float
    l_system: float
    lq_queue: float
    w_system: float
    wq_queue: float
    wq_mg1: float
    stable: bool
    prob_wq_gt_5min: float = 0.0


def classify_utilization_regime(rho: float) -> str:
    """Clasifica el factor de utilización rho según los criterios de decisión del proyecto."""
    if rho < 0.45:
        return "Subutilizado (<45%)"
    if rho < 0.60:
        return "Moderado (45%-60%)"
    if rho <= 0.85:
        return "Óptimo-Alto (60%-85%)"
    if rho <= 0.90:
        return "Alerta (85%-90%)"
    if rho < 1.00:
        return "Crítico (>90%)"
    return "Inestable (>=100%)"


class ParkingQueuingModel:
    """
    Motor analítico y generador estocástico para el sistema de pago de parqueaderos
    de Supercentro. Valida axiomas de probabilidad y calcula métricas M/M/1 y M/G/1.
    """

    def __init__(
        self,
        user_type_probs: Optional[Dict[str, float]] = None,
        service_means: Optional[Dict[str, float]] = None,
        arrival_means: Optional[Dict[str, float]] = None,
        base_cashiers: int = BASE_CASHIERS,
        horizon_minutes: float = SIM_MINUTES,
    ):
        self.user_type_probs = dict(user_type_probs or USER_TYPE_PROBS)
        self.service_means = dict(service_means or SERVICE_MEANS)
        self.arrival_means = dict(arrival_means or ARRIVAL_MEANS)
        self.base_cashiers = int(base_cashiers)
        self.horizon_minutes = float(horizon_minutes)
        self._validate_parameters()

    def _validate_parameters(self) -> None:
        """Verifica validez matemática de probabilidades, medias exponenciales y horizonte."""
        if self.base_cashiers <= 0:
            raise ValueError("El número base de cajeros debe ser mayor que cero.")
        if self.horizon_minutes <= 0:
            raise ValueError("El horizonte de simulación debe ser positivo.")
        if set(self.user_type_probs.keys()) != set(USER_TYPES):
            raise ValueError("Las llaves de probabilidades deben coincidir con USER_TYPES.")
        if any(v < 0.0 for v in self.user_type_probs.values()):
            raise ValueError("No se permiten probabilidades negativas.")
        if not np.isclose(sum(self.user_type_probs.values()), 1.0, atol=1e-9):
            raise ValueError(
                f"Las probabilidades de usuario deben sumar 1.0 (actual: {sum(self.user_type_probs.values())})."
            )
        for u in USER_TYPES:
            if self.service_means[u] <= 0.0 or self.arrival_means[u] <= 0.0:
                raise ValueError(f"Medias exponenciales inválidas para el tipo {u}.")

    def expected_interarrival_per_base_cashier(self) -> float:
        """Tiempo medio entre llegadas por cajero en el diseño base E[IA_c] (min)."""
        return sum(self.user_type_probs[u] * self.arrival_means[u] for u in USER_TYPES)

    def base_cashier_arrival_rate(self) -> float:
        """Tasa de llegada por cajero en el escenario base de 3 cajeros (vehículos/min)."""
        return 1.0 / self.expected_interarrival_per_base_cashier()

    def exit_arrival_rate(self) -> float:
        """Demanda total agregada del punto de salida (vehículos/min), conservada entre escenarios."""
        return self.base_cashiers * self.base_cashier_arrival_rate()

    def expected_service_moments(
        self,
        role: str = "Mixto",
        ux_factor_slow: float = 1.0,
    ) -> Tuple[float, float]:
        """Calcula E[S] y E[S^2] para la mezcla exponencial asignada al rol dado."""
        if role not in ROLE_ALLOWED_TYPES:
            raise ValueError(f"Rol de cajero desconocido: {role}")
        if ux_factor_slow <= 0.0:
            raise ValueError("ux_factor_slow debe ser positivo.")

        allowed = ROLE_ALLOWED_TYPES[role]
        p_sub = sum(self.user_type_probs[u] for u in allowed)
        e1 = 0.0
        e2 = 0.0
        for u in USER_TYPES:
            if u not in allowed:
                continue
            w_u = self.user_type_probs[u] / p_sub
            s_u = self.service_means[u] * (ux_factor_slow if u in ("Lento", "Muy lento") else 1.0)
            e1 += w_u * s_u
            # Para X ~ Exp(media = m), E[X^2] = 2 * m^2
            e2 += w_u * 2.0 * (s_u ** 2)
        return float(e1), float(e2)

    def analyze_user_type_isolated_mm1(self) -> List[Dict[str, object]]:
        """
        Analiza cada perfil de usuario como un sistema M/M/1 puro aislado
        con sus propios parámetros de llegada y servicio de la tabla oficial.
        """
        rows: List[Dict[str, object]] = []
        for u in USER_TYPES:
            mean_ia = self.arrival_means[u]
            mean_s = self.service_means[u]
            lam = 1.0 / mean_ia
            mu = 1.0 / mean_s
            rho = lam / mu
            stable = rho < 1.0
            if stable:
                p0 = 1.0 - rho
                l_sys = rho / (1.0 - rho)
                lq = (rho ** 2) / (1.0 - rho)
                w_sys = 1.0 / (mu - lam)
                wq = rho / (mu * (1.0 - rho))
                estado = "Estable (ρ < 1)"
            else:
                p0 = 0.0
                l_sys = float("inf")
                lq = float("inf")
                w_sys = float("inf")
                wq = float("inf")
                estado = "Crítico / Inestable (ρ ≥ 1)"

            rows.append({
                "tipo_usuario": u,
                "probabilidad": self.user_type_probs[u],
                "media_servicio_min": mean_s,
                "media_llegada_min": mean_ia,
                "lambda_cli_min": lam,
                "mu_cli_min": mu,
                "rho": rho,
                "p0_ocio": p0,
                "l_sistema": l_sys,
                "lq_cola": lq,
                "w_sistema_min": w_sys,
                "wq_cola_min": wq,
                "estable": stable,
                "estado_teorico": estado,
            })
        return rows

    def compute_single_cashier_mm1(
        self,
        role: str,
        num_cashiers_with_role: int,
        ux_factor_slow: float = 1.0,
    ) -> MM1AnalyticalMetrics:
        """Calcula métricas analíticas M/M/1 y M/G/1 exactas para un cajero independiente."""
        if num_cashiers_with_role <= 0:
            raise ValueError("El número de cajeros con el rol debe ser mayor que cero.")

        allowed = ROLE_ALLOWED_TYPES[role]
        p_sub = sum(self.user_type_probs[u] for u in allowed)
        lam = (self.exit_arrival_rate() * p_sub) / num_cashiers_with_role
        mean_s, mean_s2 = self.expected_service_moments(role=role, ux_factor_slow=ux_factor_slow)
        mu = 1.0 / mean_s
        rho = lam / mu
        stable = rho < 1.0

        if stable:
            p0 = 1.0 - rho
            l_sys = rho / (1.0 - rho)
            lq = (rho ** 2) / (1.0 - rho)
            w_sys = 1.0 / (mu - lam)
            wq = rho / (mu * (1.0 - rho))
            wq_mg1 = (lam * mean_s2) / (2.0 * (1.0 - rho))
            prob_wq_gt_5min = float(rho * np.exp(-(mu - lam) * 5.0))
        else:
            p0 = 0.0
            l_sys = float("inf")
            lq = float("inf")
            w_sys = float("inf")
            wq = float("inf")
            wq_mg1 = float("inf")
            prob_wq_gt_5min = 1.0

        return MM1AnalyticalMetrics(
            role=role,
            lam=lam,
            mu=mu,
            rho=rho,
            p0=p0,
            mean_service=mean_s,
            mean_s2=mean_s2,
            l_system=l_sys,
            lq_queue=lq,
            w_system=w_sys,
            wq_queue=wq,
            wq_mg1=wq_mg1,
            stable=stable,
            prob_wq_gt_5min=prob_wq_gt_5min,
        )

    def analyze_scenario_theoretically(self, scenario_key: str) -> Dict[str, object]:
        """Calcula métricas analíticas ponderadas para un escenario completo."""
        cfg = SCENARIO_DEFINITIONS[scenario_key]
        cajeros = cfg["cajeros"]
        ux_factor = float(cfg.get("ux_factor_slow", 1.0))

        counts_by_role: Dict[str, int] = {}
        for _, role in cajeros:
            counts_by_role[role] = counts_by_role.get(role, 0) + 1

        cashier_metrics = []
        for name, role in cajeros:
            m = self.compute_single_cashier_mm1(role, counts_by_role[role], ux_factor_slow=ux_factor)
            cashier_metrics.append((name, m))

        total_lam = sum(m.lam for _, m in cashier_metrics)
        weighted_wq_mm1 = sum((m.lam / total_lam) * m.wq_queue for _, m in cashier_metrics)
        weighted_wq_mg1 = sum((m.lam / total_lam) * m.wq_mg1 for _, m in cashier_metrics)
        weighted_w_mm1 = sum((m.lam / total_lam) * m.w_system for _, m in cashier_metrics)
        weighted_w_mg1 = sum((m.lam / total_lam) * (m.wq_mg1 + m.mean_service) for _, m in cashier_metrics)
        weighted_s = sum((m.lam / total_lam) * m.mean_service for _, m in cashier_metrics)
        weighted_prob_gt_5 = sum((m.lam / total_lam) * m.prob_wq_gt_5min for _, m in cashier_metrics)
        total_lq_mm1 = sum(m.lq_queue for _, m in cashier_metrics)
        total_l_mm1 = sum(m.l_system for _, m in cashier_metrics)
        mean_rho = float(np.mean([m.rho for _, m in cashier_metrics]))
        max_rho = float(np.max([m.rho for _, m in cashier_metrics]))
        max_wq_mm1 = float(np.max([m.wq_queue for _, m in cashier_metrics]))
        max_wq_mg1 = float(np.max([m.wq_mg1 for _, m in cashier_metrics]))

        return {
            "scenario_key": scenario_key,
            "nombre": cfg["nombre"],
            "nombre_corto": cfg["nombre_corto"],
            "num_cajeros": cfg["num_cajeros"],
            "ux_factor_slow": ux_factor,
            "total_lambda": total_lam,
            "expected_arrivals_horizon": total_lam * self.horizon_minutes,
            "weighted_s": weighted_s,
            "weighted_wq_mm1": weighted_wq_mm1,
            "weighted_wq_mg1": weighted_wq_mg1,
            "weighted_w_mm1": weighted_w_mm1,
            "weighted_w_mg1": weighted_w_mg1,
            "weighted_prob_wq_gt_5min": weighted_prob_gt_5,
            "total_lq_mm1": total_lq_mm1,
            "total_l_mm1": total_l_mm1,
            "mean_rho": mean_rho,
            "max_rho": max_rho,
            "regime_max_rho": classify_utilization_regime(max_rho),
            "max_wq_mm1": max_wq_mm1,
            "max_wq_mg1": max_wq_mg1,
            "cashiers": cashier_metrics,
        }

    def generate_exit_arrivals(self, seed: int) -> List[ArrivalVehicle]:
        """
        Genera la secuencia estocástica de vehículos que llegan al punto de salida
        durante `horizon_minutes` (1000 min) como un proceso de Poisson exacto con tasa
        `exit_arrival_rate`, utilizando PCG64 para reproducibilidad determinista.
        """
        rng = np.random.default_rng(seed)
        lam_exit = self.exit_arrival_rate()
        mean_ia_exit = 1.0 / lam_exit
        probs = [self.user_type_probs[u] for u in USER_TYPES]

        vehicles: List[ArrivalVehicle] = []
        current_time = 0.0
        vid = 1

        while True:
            ia_time = float(rng.exponential(scale=mean_ia_exit))
            current_time += ia_time
            if current_time > self.horizon_minutes:
                break

            u_type = str(rng.choice(USER_TYPES, p=probs))
            z_unit = float(rng.exponential(scale=1.0))
            srv_base = z_unit * self.service_means[u_type]

            vehicles.append(
                ArrivalVehicle(
                    vehicle_id=vid,
                    arrival_time=current_time,
                    interarrival_time=ia_time,
                    user_type=u_type,
                    unit_service_exp=z_unit,
                    base_service_time=srv_base,
                )
            )
            vid += 1

        return vehicles
