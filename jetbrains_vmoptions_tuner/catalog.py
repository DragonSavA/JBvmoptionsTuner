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
    icon: str | None = None
    legacy: bool = False


PRODUCTS: tuple[Product, ...] = (
    Product("idea", "IntelliJ IDEA", "IJ", "#FE315D", icon="idea.svg"),
    Product("pycharm", "PyCharm", "PC", "#21D789", icon="pycharm.svg"),
    Product("webstorm", "WebStorm", "WS", "#07C3F2", icon="webstorm.svg"),
    Product("phpstorm", "PhpStorm", "PS", "#B345F1", icon="phpstorm.svg"),
    Product("rubymine", "RubyMine", "RM", "#FF4057", icon="rubymine.svg"),
    Product("clion", "CLion", "CL", "#21D789", icon="clion.svg"),
    Product("goland", "GoLand", "GO", "#00CDD7", icon="goland.svg"),
    Product("rider", "Rider", "RD", "#FF7A00", icon="rider.svg"),
    Product("rustrover", "RustRover", "RR", "#F05A28", icon="rustrover.svg"),
    Product("datagrip", "DataGrip", "DG", "#22D88F", icon="datagrip.svg"),
    Product(
        "android-studio", "Android Studio", "AS", "#3DDC84", icon="android-studio.svg"
    ),
    Product("mps", "JetBrains MPS", "MPS", "#6B57FF", icon="mps.svg"),
    Product("gateway", "JetBrains Gateway", "GW", "#6B57FF", icon="gateway.svg"),
    Product("client", "JetBrains Client", "JC", "#6B57FF"),
    Product(
        "dataspell",
        "DataSpell (legacy)",
        "DS",
        "#36D7B7",
        icon="dataspell.svg",
        legacy=True,
    ),
    Product("aqua", "Aqua (legacy)", "AQ", "#25C2A0", icon="aqua.svg", legacy=True),
    Product("fleet", "Fleet (legacy)", "FL", "#7B61FF", icon="fleet.svg", legacy=True),
    Product(
        "appcode", "AppCode (legacy)", "AC", "#087CFA", icon="appcode.svg", legacy=True
    ),
)

PRODUCT_BY_KEY = {product.key: product for product in PRODUCTS}
