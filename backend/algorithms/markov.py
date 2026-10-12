"""Cadena de Markov de categorías (W3): clasificación, distribución estacionaria,
caminata lazy y 2-SAT aleatorizado (Papadimitriou)."""
from __future__ import annotations

import math
import random

import numpy as np
import pandas as pd


def classify_states(P: pd.DataFrame) -> dict:
    """W3 T1: clases comunicantes, estados absorbentes (sumideros), irreducibilidad, periodo."""
    A = (P.to_numpy() > 0)
    n = len(A)
    reach = A | np.eye(n, dtype=bool)
    for _ in range(n):  # cierre transitivo por multiplicación booleana
        reach = reach | (reach.astype(int) @ reach.astype(int) > 0)
    comm = reach & reach.T
    classes, seen = [], set()
    for i in range(n):
        if i in seen:
            continue
        members = [j for j in range(n) if comm[i, j]]
        seen.update(members)
        closed = not any(A[a, b] for a in members for b in range(n) if b not in members)
        classes.append({"states": [P.index[j] for j in members], "closed": bool(closed)})
    absorbing = [P.index[i] for i in range(n) if math.isclose(P.iloc[i, i], 1.0)]
    # periodo del estado 0 = mcd de los k con (A^k)[0,0] > 0
    g, Ak = 0, np.eye(n, dtype=int)
    for k in range(1, 3 * n + 1):
        Ak = (Ak @ A.astype(int) > 0).astype(int)
        if Ak[0, 0]:
            g = math.gcd(g, k)
    return {"num_classes": len(classes), "classes": classes, "absorbing_states": absorbing,
            "has_absorbing_sink": bool(absorbing), "irreducible": len(classes) == 1,
            "period": int(g) if g else 0, "aperiodic": g == 1}


def stationary_distribution(P: pd.DataFrame, tol: float = 1e-13, max_iter: int = 100000
                            ) -> tuple[pd.Series, int, float]:
    """π tal que πP = π, por iteración de potencia. Devuelve (π, iteraciones, residual)."""
    M = P.to_numpy(float)
    pi = np.full(len(M), 1 / len(M))
    it = 0
    for it in range(1, max_iter + 1):
        new = pi @ M
        done = np.abs(new - pi).sum() < tol
        pi = new
        if done:
            break
    return pd.Series(pi, index=P.index, name="pi"), it, float(np.abs(pi @ M - pi).sum())


def lazy_walk(P: pd.DataFrame, pi: pd.Series, steps: int = 50000, seed: int = 42) -> dict:
    """W3 T4: caminata con self-loop 1/2 (L = (I+P)/2); compara frecuencia empírica con π."""
    M = P.to_numpy(float)
    L = 0.5 * M + 0.5 * np.eye(len(M))
    cum = np.cumsum(L, axis=1)
    cum[:, -1] = 1.0
    rng, state, visits = random.Random(seed), 0, np.zeros(len(M), dtype=int)
    for _ in range(steps):
        state = int(np.searchsorted(cum[state], rng.random(), side="left"))
        visits[state] += 1
    emp = visits / steps
    diff = np.abs(emp - pi.to_numpy())
    return {"steps": steps, "seed": seed, "max_abs_error": float(diff.max()),
            "total_variation": float(diff.sum() / 2),
            "categories": [{"category": c, "pi": float(pi[c]), "empirical": float(e)}
                           for c, e in zip(P.index, emp)]}


def papadimitriou_2sat(clauses: list[tuple[int, int]], n: int, seed: int = 42,
                       max_restarts: int = 50) -> dict:
    """2-SAT aleatorizado: asignación aleatoria; mientras haya cláusulas insatisfechas, se elige
    una al azar y se invierte una de sus variables. 2n² pasos por reinicio."""
    rng = random.Random(seed)

    def sat(lit, a):
        return a[abs(lit)] if lit > 0 else not a[abs(lit)]

    steps = 0
    for attempt in range(1, max_restarts + 1):
        a = {i: rng.random() < 0.5 for i in range(1, n + 1)}
        for _ in range(2 * n * n):
            bad = [c for c in clauses if not (sat(c[0], a) or sat(c[1], a))]
            if not bad:
                return {"satisfiable_found": True, "attempts": attempt, "flips": steps, "assignment": a}
            lit = rng.choice(rng.choice(bad))
            a[abs(lit)] = not a[abs(lit)]
            steps += 1
    return {"satisfiable_found": False, "attempts": max_restarts, "flips": steps, "assignment": a}


def moderation_policy(pi: pd.Series, flagged_frac: pd.Series, top: int = 4,
                      seed: int = 42) -> dict:
    """W3 T5: 5 restricciones de política sobre n = 2·top ≥ 8 variables.

    Para cada una de las `top` categorías de mayor riesgo (π_c · flagged_frac_c) hay dos variables:
    R_c = «agregar revisores» y T_c = «limitar subidas». Restricciones:
      (R_c ∨ T_c)  para las 4 categorías de riesgo  → si π y flagged_frac son altos, se actúa;
      (¬R_a ∨ ¬R_b) para las 2 de mayor riesgo     → presupuesto: no reforzar ambas con revisores.
    """
    risk = (pi * flagged_frac).sort_values(ascending=False)
    cats = list(risk.index[:top])
    names, clauses, texts = {}, [], []
    for k, c in enumerate(cats):
        names[2 * k + 1], names[2 * k + 2] = f"R_{c}", f"T_{c}"
        clauses.append((2 * k + 1, 2 * k + 2))
        texts.append(f"R_{c} OR T_{c}")
    clauses.append((-1, -3))
    texts.append(f"NOT R_{cats[0]} OR NOT R_{cats[1]}")
    result = papadimitriou_2sat(clauses, 2 * top, seed)
    a = result["assignment"]
    checks = []
    for text, (x, y) in zip(texts, clauses):
        ok = (a[abs(x)] if x > 0 else not a[abs(x)]) or (a[abs(y)] if y > 0 else not a[abs(y)])
        checks.append({"clause": text, "satisfied": bool(ok)})
    return {"variables": 2 * top, "constraints": len(clauses), "risk_categories": cats,
            "risk_score": {c: float(risk[c]) for c in cats},
            "found": result["satisfiable_found"], "attempts": result["attempts"],
            "flips": result["flips"],
            "assignment": {names[i]: bool(v) for i, v in a.items()}, "checks": checks}
