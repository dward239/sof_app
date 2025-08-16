from __future__ import annotations
import re

_ELEMENT = (
    "Ac|Ag|Al|Am|Ar|As|At|Au|B|Ba|Be|Bh|Bi|Bk|Br|C|Ca|Cd|Ce|Cf|Cl|Cm|Cn|Co|Cr|Cs|Cu|Db|Ds|Dy|Er|Es|Eu|F|Fe|Fl|Fm|Fr|Ga|Gd|Ge|H|He|Hf|Hg|Ho|Hs|I|In|Ir|K|Kr|La|Li|Lr|Lu|Lv|Md|Mg|Mn|Mo|Mt|N|Na|Nb|Nd|Ne|Ni|No|Np|O|Oganesson|Os|P|Pa|Pb|Pd|Pm|Po|Pr|Pt|Pu|Ra|Rb|Re|Rf|Rg|Rh|Rn|Ru|S|Sb|Sc|Se|Sg|Si|Sm|Sn|Sr|Ta|Tb|Tc|Te|Th|Ti|Tl|Tm|Ts|U|V|W|Xe|Y|Yb|Zn|Zr"
)

_PATTERNS = [
    re.compile(r"^(?P<a>\d+)(?P<elem>[A-Za-z]{1,2})(?P<m>m?)$"),
    re.compile(r"^(?P<elem>[A-Za-z]{1,2})[- ]?(?P<a>\d+)(?P<m>m?)$"),
]

import re

# Canonical form: "Sym-MASS[misomer]" e.g., "Tc-99m", "Cs-137"
# Accept inputs in either order and mixed case:
#   "137Cs", "Cs137", "Cs-137", "99mTc", "Tc99m", "TC-99M", etc.
_ISO_RE = r"(?:m\d*)?"  # m, m1, m2, ...

def _fix_symbol(sym: str) -> str:
    sym = sym.strip()
    if not sym:
        return sym
    return sym[0].upper() + sym[1:].lower()

def to_canonical(name: str) -> str:
    if not name:
        return name
    s = str(name).strip().replace(" ", "")
    # 1) MASS[isomer] + Symbol  (e.g., "99mTc")
    m = re.fullmatch(rf"(?P<mass>\d+)(?P<iso>{_ISO_RE})(?P<sym>[A-Za-z]{{1,3}})", s, flags=re.IGNORECASE)
    if m:
        sym = _fix_symbol(m.group("sym"))
        mass = m.group("mass")
        iso = (m.group("iso") or "").lower()
        return f"{sym}-{mass}{iso}"

    # 2) Symbol + MASS[isomer] with optional hyphen (e.g., "Tc99m", "Tc-99m")
    m = re.fullmatch(rf"(?P<sym>[A-Za-z]{{1,3}})-?(?P<mass>\d+)(?P<iso>{_ISO_RE})", s, flags=re.IGNORECASE)
    if m:
        sym = _fix_symbol(m.group("sym"))
        mass = m.group("mass")
        iso = (m.group("iso") or "").lower()
        return f"{sym}-{mass}{iso}"

    # 3) Already canonical (defensive; proper case & hyphen)
    m = re.fullmatch(rf"(?P<sym>[A-Za-z]{{1,3}})-(?P<mass>\d+)(?P<iso>{_ISO_RE})?", s, flags=re.IGNORECASE)
    if m:
        sym = _fix_symbol(m.group("sym"))
        mass = m.group("mass")
        iso = (m.group("iso") or "").lower()
        return f"{sym}-{mass}{iso}"

    # Fallback: return as-is (lets alias file handle odd cases)
    return s

