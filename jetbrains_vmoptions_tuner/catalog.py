"""Static catalog used by the IDE selector.

The catalog intentionally contains the current JetBrains IDE line plus a few
JetBrains-platform applications commonly managed by Toolbox.  Legacy entries
are kept because an installed IDE can outlive its commercial support period.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Product:
    key: str
    name: str
    initials: str
    color: str
    legacy: bool = False


PRODUCTS: tuple[Product, ...] = (
    Product("idea", "IntelliJ IDEA", "IJ", "#FE315D"),
    Product("pycharm", "PyCharm", "PC", "#21D789"),
    Product("webstorm", "WebStorm", "WS", "#07C3F2"),
    Product("phpstorm", "PhpStorm", "PS", "#B345F1"),
    Product("rubymine", "RubyMine", "RM", "#FF4057"),
    Product("clion", "CLion", "CL", "#21D789"),
    Product("goland", "GoLand", "GO", "#00CDD7"),
    Product("rider", "Rider", "RD", "#FF7A00"),
    Product("rustrover", "RustRover", "RR", "#F05A28"),
    Product("datagrip", "DataGrip", "DG", "#22D88F"),
    Product("android-studio", "Android Studio", "AS", "#3DDC84"),
    Product("mps", "JetBrains MPS", "MPS", "#6B57FF"),
    Product("gateway", "JetBrains Gateway", "GW", "#6B57FF"),
    Product("client", "JetBrains Client", "JC", "#6B57FF"),
    Product("dataspell", "DataSpell (legacy)", "DS", "#36D7B7", True),
    Product("aqua", "Aqua (legacy)", "AQ", "#25C2A0", True),
    Product("fleet", "Fleet (legacy)", "FL", "#7B61FF", True),
    Product("appcode", "AppCode (legacy)", "AC", "#087CFA", True),
)

PRODUCT_BY_KEY = {product.key: product for product in PRODUCTS}

