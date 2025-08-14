from __future__ import annotations
import re

_ELEMENT = (
    "Ac|Ag|Al|Am|Ar|As|At|Au|B|Ba|Be|Bh|Bi|Bk|Br|C|Ca|Cd|Ce|Cf|Cl|Cm|Cn|Co|Cr|Cs|Cu|Db|Ds|Dy|Er|Es|Eu|F|Fe|Fl|Fm|Fr|Ga|Gd|Ge|H|He|Hf|Hg|Ho|Hs|I|In|Ir|K|Kr|La|Li|Lr|Lu|Lv|Md|Mg|Mn|Mo|Mt|N|Na|Nb|Nd|Ne|Ni|No|Np|O|Oganesson|Os|P|Pa|Pb|Pd|Pm|Po|Pr|Pt|Pu|Ra|Rb|Re|Rf|Rg|Rh|Rn|Ru|S|Sb|Sc|Se|Sg|Si|Sm|Sn|Sr|Ta|Tb|Tc|Te|Th|Ti|Tl|Tm|Ts|U|V|W|Xe|Y|Yb|Zn|Zr"
)

_PATTERNS = [
    re.compile(r"^(?P<a>\d+)(?P<elem>[A-Za-z]{1,2})(?P<m>m?)$"),
    re.compile(r"^(?P<elem>[A-Za-z]{1,2})[- ]?(?P<a>\d+)(?P<m>m?)$"),
]

def to_canonical(nuclide: str) -> str:
    s = nuclide.strip().replace(" ", "")
    s = s.replace("_", "-")
    s = s.replace("--", "-")
    s = s.replace("(m)", "m").replace("M", "m")
    for p in _PATTERNS:
        m = p.match(s)
        if m:
            elem = m.group("elem").capitalize()
            a = m.group("a")
            mflag = m.group("m")
            if len(elem) == 1:
                elem = elem.upper()
            elif len(elem) == 2:
                elem = elem[0].upper() + elem[1].lower()
            suffix = "m" if mflag else ""
            return f"{elem}-{a}{suffix}"
    return s
