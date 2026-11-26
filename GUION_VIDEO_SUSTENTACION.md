# GUION DE SUSTENTACIÓN — ACTIVIDAD DIDÁCTICA 2-M4
## Solución de un Problema de Parqueaderos con Colas M/M/1 y M/H4/1 (Centro Comercial Supercentro)

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
[0:18 - 0:42]  2. Parametrización y Estado Estable (N*): Horizonte 1000 min y N* = 220 réplicas
[0:42 - 1:15]  3. Puntos A y B: Cajero menor/mayor atención y carga real por tipo de usuario
[1:15 - 1:48]  4. Punto C: ¿Alcanzan 3 cajeros? Estrategia 4 Mixtos + UX/LPR (JSQ y M/G/c)
[1:48 - 2:20]  5. Puntos D y E: Protocolo V&V y eliminación del estado transitorio (Antes vs Después)
[2:20 - 2:30]  6. Cierre: Repositorio, pruebas unitarias (25/25), Colab y despedida
```

---

## 🎬 GUION COMPLETO PASO A PASO

> **[0:00 – 0:18] FASE 1: GANCHO Y CONTEXTO (18 segundos)**  
> *(En pantalla: Portada del informe APA 7 / Tabla de parámetros)*  
>  
> *"Cordial saludo, profesor Julián Loaiza. En representación del **Grupo 25** —Adriana Agudelo, Juan Daniel Pulgarin, Rubén Jaramillo y quien les habla, Camilo Palacios— presentamos nuestra solución al parqueadero de **Supercentro**. Sus **3 cajeros independientes** operan como colas M/M/1 por categoría, pero al mezclar perfiles forman un sistema hiperexponencial M/H4/1 (caso M/G/1); aunque el software responde al instante, el **55 %** de usuarios son lentos o muy lentos al digitar su placa."*

---

> **[0:18 – 0:42] FASE 2: MODELO Y DETERMINACIÓN DE RÉPLICAS POR ESTADO ESTABLE (24 segundos)**  
> *(En pantalla: `results/fig1_estado_estable_replicas.png`)*  
>  
> *"Modelamos jornadas de **1000 minutos** en Python con generador PCG64 (`seed = 42`, `SeedSequence`) y Números Aleatorios Comunes (**CRN**, por sus siglas en inglés). Un piloto inicial de diez réplicas (`n0 = 10`) resultó insuficiente con **38.67 %** de error relativo sobre $W$ sub q ($W_q$). Sin mirar datos futuros, la regla secuencial causal de **Law y Kelton** converge en `r = 220`, fijando **$N^* = 220$ réplicas**: $W_q$ promedia **14.73 minutos** (error **5.65 %**) y el tiempo total $W$ alcanza **18.32 minutos** (error **4.63 %**, bajo el tope del 5 %)."*

---

> **[0:42 – 1:15] FASE 3: PUNTOS A Y B — CAJEROS Y USUARIOS POR TIPO (33 segundos)**  
> *(En pantalla: `results/fig2_desempeno_cajeros_base.png` y `results/fig3_usuarios_por_tipo.png`)*  
>  
> *"En el **Punto A**, evaluando 220 jornadas con ruteo equiprobable 1/3, el **Cajero 1** registró el menor promedio muestral (**17.83 min**, $W_q = 14.24\text{ min}$), el **Cajero 2** marcó **17.97 min** y el **Cajero 3** cerró con **18.70 min** ($W_q = 15.10\text{ min}$), con servicio cercano a **3.59–3.60 min** y simetría estadística verificada ($p \ge 0.367$). En el **Punto B**, ingresan **645.88 vehículos por jornada** (**161.92** rápidos, **128.89** normales, **177.65** lentos y **177.41** muy lentos): aunque lentos y muy lentos suman **55 %** en visitas, absorben el **76.4 %** de la carga teórica de servicio."*

---

> **[1:15 – 1:48] FASE 4: PUNTO C — ESTRATEGIA DE MEJORA (33 segundos)**  
> *(En pantalla: `results/fig4_estrategias_mejora_escenarios.png`)*  
>  
> *"En el **Punto C**, tres cajeros no bastan: generan **14.73 min** de espera (**18.32 min** en sistema) y **57.0 %** global (**57.2 %** peor cajero) sobre cinco minutos. Bajo las cinco reglas cuantitativas del grupo ($W_q \le 5$, $W \le 8$, $\rho \in [45,85]\%$, $L_q < 3$, riesgo $\le 20\%$), descartamos segregar filas (`E5` castiga el carril estándar hasta **7.34 min**) y `E4` queda **redundante** por subutilización (**38.7 %**). Recomendamos **4 cajeros mixtos con lectura LPR/QR en software (`UX`, experiencia de usuario)**, reduciendo **25 %** la interacción lenta y muy lenta: $W_q$ cae a **3.05 min** ($W = 5.96\text{ min}$, el mínimo total), baja a **0.44 min** al señalizar la fila más corta (**JSQ**, *Join-the-Shortest-Queue*) y a **0.22 min** con cola única serpentina M/G/c."*

---

> **[1:48 – 2:20] FASE 5: PUNTOS D Y E — PROTOCOLO V&V Y ELIMINACIÓN DEL TRANSITORIO (32 segundos)**  
> *(En pantalla: `results/fig5_proceso_vv_diagrama.png` y `results/fig6_eliminacion_transitorio_antes_despues.png`)*  
>  
> *"En el **Punto D**, auditamos **Verificación, Calibración y Validación (V&V)**: **25 pruebas unitarias** y residuo continuo de Little ($|\frac{1}{H_{\text{eff}}}\int Q(t)dt - \lambda_{\text{eff}}W_q| \le 1.6\times 10^{-14} < 10^{-10}$); calibración con **MAE de 0.04 puntos porcentuales** ($\chi^2 = 0.470, p = 0.925$); y pruebas *t* frente a M/G/1 sin rechazar $H_0$ a 1000 minutos ($p \in [0.361, 0.949]$) y **5000 minutos** ($p \in [0.099, 0.637]$). En el **Punto E**, **MSER-5** detecta el corte base en **`k* = 176` vehículos** (~271 min), elevando $W_q$ **+9.0 %** de **14.73 a 16.05 min** (subestimación inicial de **8.2 %**) hacia **15.57 min** teóricos."*

---

> **[2:20 – 2:30] FASE 6: CIERRE Y REPRODUCIBILIDAD (10 segundos)**  
> *(En pantalla: Cuaderno Google Colab y carpeta de repositorio)*  
>  
> *"El paquete Python, las **25 pruebas**, los 17 CSV, las 7 gráficas, el informe APA 7 y nuestra bitácora ética **Usa–Modifica–Crea** (Anexo C y Sección 6 de Colab) quedan en el repositorio. ¡Gracias!"*
