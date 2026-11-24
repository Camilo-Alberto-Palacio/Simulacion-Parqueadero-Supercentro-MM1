# GUION DE SUSTENTACIÓN — ACTIVIDAD DIDÁCTICA 2-M4
## Solución de un Problema de Parqueaderos con Colas M/M/1 (Centro Comercial Supercentro)

* **Institución:** Institución Universitaria Digital de Antioquia (IU Digital) — Facultad de Ingeniería
* **Asignatura:** Simulación (`PREICA2602B020045`) — Grupo 25
* **Docente Catedrático:** Dr. Julián Andrés Loaiza López
* **Modalidad:** 1 Solo Portavoz (en representación del Grupo 25)
* **Integrantes del Equipo:** Adriana Andrea Agudelo Agudelo, Camilo Alberto Palacios Turriago, Juan Daniel Pulgarin García y Ruben Dario Jaramillo Cervantes
* **Duración Objetivo:** **2 minutos y 30 segundos (Máximo permitido: 3:00 minutos)**
* **Formato:** Video horizontal (16:9), 1080p, pantalla compartida con las figuras de `results/` o el cuaderno Google Colab + cámara en esquina

---

### ESTRUCTURA DEL PITCH (2:30 MINUTOS)

```text
[0:00 - 0:18]  1. Gancho y Problema: Los 3 cajeros de Supercentro y la paradoja del 55% lento
[0:18 - 0:42]  2. Parametrización y Estado Estable (N*): Horizonte 1000 min y N* = 120 réplicas
[0:42 - 1:15]  3. Puntos A y B: Cajero menor/mayor atención y carga real por tipo de usuario
[1:15 - 1:48]  4. Punto C: ¿Alcanzan 3 cajeros? Estrategia 4 Mixtos + UX/LPR con JSQ
[1:48 - 2:20]  5. Puntos D y E: Protocolo V&V y eliminación del estado transitorio (Antes vs Después)
[2:20 - 2:30]  6. Cierre: Repositorio, pruebas unitarias (16/16), Colab y despedida
```

---

## 🎬 GUION COMPLETO PASO A PASO

> **[0:00 – 0:18] FASE 1: GANCHO Y CONTEXTO (18 segundos)**  
> *(En pantalla: Portada del informe APA 7 / Tabla de parámetros)*  
>  
> *"Cordial saludo, profesor Julián Loaiza. En representación del **Grupo 25** —Adriana Agudelo, Juan Daniel Pulgarin, Rubén Jaramillo y quien les habla, Camilo Palacios— presentamos nuestra solución al problema de parqueaderos del **Centro Comercial Supercentro**. Cada salida cuenta con **3 cajeros automáticos M/M/1 independientes**, pero aunque el software responde al instante, el **55 %** de los conductores son lentos o muy lentos al digitar su placa."*

---

> **[0:18 – 0:42] FASE 2: MODELO Y DETERMINACIÓN DE RÉPLICAS POR ESTADO ESTABLE (24 segundos)**  
> *(En pantalla: `results/fig1_estado_estable_replicas.png`)*  
>  
> *"Modelamos jornadas de **1000 minutos** en Python con semilla reproducible PCG64 (`seed = 42`) y Números Aleatorios Comunes. Para definir cuántas corridas hacían falta, descartamos un piloto corto de 10 réplicas que arrojaba un error relativo de **44.01 %**, y aplicamos la técnica del promedio acumulado sobre $W_q$: la serie ingresó de forma sostenida en la banda asintótica de $\pm 2\%$ en `r = 112`, por lo que fijamos **$N^* = 120$ réplicas**, reduciendo el error relativo de espera a **7.10 %** y el de permanencia total a **5.72 %**."*

---

> **[0:42 – 1:15] FASE 3: PUNTOS A Y B — CAJEROS Y USUARIOS POR TIPO (33 segundos)**  
> *(En pantalla: `results/fig2_desempeno_cajeros_base.png` y `results/fig3_usuarios_por_tipo.png`)*  
>  
> *"En el **Punto A**, evaluando los 3 cajeros base durante 120 corridas, el **Cajero 2** registró el menor tiempo promedio de atención total (**16.84 min**, $W_q = 13.23\text{ min}$), el **Cajero 3** fue intermedio (**17.22 min**) y el **Cajero 1** acumuló el mayor promedio (**17.29 min**, $W_q = 13.68\text{ min}$), mientras el servicio puro empató alrededor de **3.60 min**. En el **Punto B**, ingresan **640.33 vehículos por jornada** (**162.00** rápidos, **126.98** normales, **177.12** lentos y **174.22** muy lentos). Aquí descubrimos la causa de la congestión: aunque los usuarios lentos y muy lentos son el **55 %** en cantidad, consumen el **76.4 %** del tiempo total de ocupación."*

---

> **[1:15 – 1:48] FASE 4: PUNTO C — ESTRATEGIA DE MEJORA (33 segundos)**  
> *(En pantalla: `results/fig4_estrategias_mejora_escenarios.png`)*  
>  
> *"¿Bastan 3 cajeros? **Rotundamente no:** generan **13.68 min** de espera en fila, **17.29 min** en el sistema y **56.5 %** de usuarios esperando más de 5 minutos. Tras evaluar siete escenarios con criterios cuantitativos del grupo, descartamos segregar filas porque castiga la cola estándar hasta **7.23 min**. Nuestra estrategia recomendada desde ingeniería de software es **ampliar a 4 cajeros mixtos e integrar lectura automática de placa LPR o QR**, reduciendo **25 %** la interacción de usuarios lentos: así la espera cae a **2.93 min** y el tiempo total a **5.85 min** —superando incluso a 6 cajeros físicos sin desperdiciar capacidad—, y baja hasta **0.43 min** al señalar la cola más corta (JSQ)."*

---

> **[1:48 – 2:20] FASE 5: PUNTOS D Y E — PROTOCOLO V&V Y ELIMINACIÓN DEL TRANSITORIO (32 segundos)**  
> *(En pantalla: `results/fig5_proceso_vv_diagrama.png` y `results/fig6_eliminacion_transitorio_antes_despues.png`)*  
>  
> *"En el **Punto D**, auditamos las tres capas V&V: verificación con **16 pruebas unitarias** y Ley de Little exacta (`< 10⁻¹⁵`); calibración de perfiles con MAE de **0.23 puntos porcentuales** ($\chi^2 = 6.977, p = 0.073$); y validación con pruebas *t* frente a Pollaczek–Khinchine M/G/1 obteniendo $p \in [0.188, 0.820]$ ($> 0.05$) en los siete escenarios. Finalmente, en el **Punto E**, diseñamos un filtro de promedio móvil que detecta el fin del arranque vacío en **`k* = 239` vehículos** (~371 min) en el escenario base: al suprimir el período transitorio, la espera sube de **13.68 a 14.74 min** (convergiendo hacia los **15.57 min** teóricos), evitando una subestimación del **7.17 %**."*

---

> **[2:20 – 2:30] FASE 6: CIERRE Y REPRODUCIBILIDAD (10 segundos)**  
> *(En pantalla: Cuaderno Google Colab y carpeta de repositorio)*  
>  
> *"El paquete modular en Python, el cuaderno autocontenido en Google Colab, el informe en normas APA 7, nuestra bitácora ética Usa–Modifica–Crea y las 7 gráficas reproducibles quedan disponibles en nuestro repositorio. ¡Muchas gracias!"*
