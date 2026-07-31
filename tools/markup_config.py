#!/usr/bin/env python3
"""Small dependency-free inline markup renderer for managed website text."""
from __future__ import annotations

import html
import re
from typing import Any

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "theta": "θ", "lambda": "λ", "mu": "μ", "pi": "π", "rho": "ρ",
    "sigma": "σ", "tau": "τ", "phi": "φ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
BLACKBOARD = {
    "C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ",
    "F": "𝔽", "A": "𝔸",
}
FRAKTUR = {
    "a": "𝔞", "b": "𝔟", "c": "𝔠", "d": "𝔡", "e": "𝔢", "f": "𝔣",
    "g": "𝔤", "h": "𝔥", "i": "𝔦", "j": "𝔧", "k": "𝔨", "l": "𝔩",
    "m": "𝔪", "n": "𝔫", "o": "𝔬", "p": "𝔭", "q": "𝔮", "r": "𝔯",
    "s": "𝔰", "t": "𝔱", "u": "𝔲", "v": "𝔳", "w": "𝔴", "x": "𝔵",
    "y": "𝔶", "z": "𝔷",
}


def static_math_html(expression: Any) -> str:
    """Render a deliberately small, safe subset of inline TeX without JS."""
    text = html.escape(str(expression or ""), quote=False)
    text = text.replace(r"\left", "").replace(r"\right", "")

    def blackboard(match: re.Match[str]) -> str:
        value = html.unescape(match.group(1))
        rendered = "".join(BLACKBOARD.get(ch, ch) for ch in value)
        return f'<span class="mathbb">{html.escape(rendered, quote=False)}</span>'

    def fraktur(match: re.Match[str]) -> str:
        value = html.unescape(match.group(1))
        rendered = "".join(FRAKTUR.get(ch, ch) for ch in value)
        return f'<span class="mathfrak">{html.escape(rendered, quote=False)}</span>'

    text = re.sub(r"\\mathbb\{([^{}]+)\}", blackboard, text)
    text = re.sub(r"\\mathfrak\{([^{}]+)\}", fraktur, text)
    text = re.sub(r"\\(?:mathrm|operatorname)\{([^{}]+)\}", r"\1", text)
    for name, symbol in GREEK.items():
        text = re.sub(rf"\\{re.escape(name)}(?![A-Za-z])", symbol, text)
    text = re.sub(r"_\{([^{}]+)\}", r"<sub>\1</sub>", text)
    text = re.sub(r"\^\{([^{}]+)\}", r"<sup>\1</sup>", text)
    text = re.sub(r"_([A-Za-z0-9])", r"<sub>\1</sub>", text)
    text = re.sub(r"\^([A-Za-z0-9])", r"<sup>\1</sup>", text)
    return f'<span class="math-inline">{text}</span>'


def rich_html(value: Any) -> str:
    """Render [i], [b], and dependency-free inline math delimited by $...$."""
    text = html.escape(str(value or ""), quote=False)
    text = re.sub(r"\[i\](.+?)\[/i\]", r"<em>\1</em>", text, flags=re.I | re.S)
    text = re.sub(r"\[b\](.+?)\[/b\]", r"<strong>\1</strong>", text, flags=re.I | re.S)
    text = re.sub(r"\$([^$\n]+)\$", lambda m: static_math_html(html.unescape(m.group(1))), text)
    return text
