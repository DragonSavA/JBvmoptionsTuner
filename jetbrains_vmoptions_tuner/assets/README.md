# Icon assets

## Application icon

`vmopt.svg` is an original icon for vmoptions Tuner, distributed under the project's
[MIT license](../../LICENSE). Its geometric style and multicolour palette are
inspired by IDE product icons; the central black square carries the application's
own `VMopT` lettering. It is not an official JetBrains product logo.

`vmopt.ico` is generated from that SVG for Windows desktop shortcuts, the title
bar and taskbar. It contains 16, 24, 32, 48, 64, 128 and 256 pixel representations.
To regenerate it on Windows, run `scripts/build_icon.ps1` from the repository root.

## Product icons

The other SVG files in this directory are unmodified product icons used only to
identify the corresponding IDE in the application UI.

- JetBrains product icons were downloaded from the official
  [JetBrains/logos](https://github.com/JetBrains/logos) repository at revision
  `3f21b4a2eeaf930823c8987c373feb49e4c58753`. Their use is governed by the
  repository's [logo license](https://github.com/JetBrains/logos/blob/master/LICENSE.txt)
  and the [JetBrains Brand Guidelines](https://www.jetbrains.com/company/brand/).
- `android-studio.svg` was downloaded from the official
  [Android Developers website](https://developer.android.com/studio/images/android-studio-stable.svg).

Copyright © 2026 JetBrains s.r.o. JetBrains product names and their logos are
trademarks of JetBrains s.r.o. Android Studio and its logo are trademarks of
Google LLC. All other trademarks belong to their respective owners. This
project is independent and is not affiliated with, endorsed by, or sponsored
by any trademark owner.

## Development credit and GitHub link

- `branding/dragonsava.svg` is the avatar supplied by DragonSavA. The original
  vector artwork is preserved; SVG clip paths restore transparency in the centre.
- `branding/codex.svg` is an original vector terminal emblem for the Codex
  development credit, inspired by the terminal symbol in the
  [official Codex interface](https://developers.openai.com/images/codex/icons/terminal.svg).
  It is project artwork under the MIT license.
- `branding/github.svg` uses the unchanged path geometry of the official
  [Primer Octicons GitHub mark](https://github.com/primer/octicons/blob/main/icons/mark-github-24.svg).
  Its [MIT license](branding/octicons-LICENSE.txt) is included alongside it.
- The `-white.svg` variants use white instead of black so the monochrome marks
  remain readable in the dark theme. GitHub and Codex are trademarks of their
  respective owners.

## Русский

`vmopt.svg` — оригинальная иконка vmoptions Tuner под [лицензией MIT](../../LICENSE).
В геометрическом стиле и многоцветной палитре использованы мотивы иконок IDE;
в центре — чёрный квадрат с собственной надписью `VMopT`. Это не официальный
логотип продукта JetBrains.

Из SVG создан `vmopt.ico` для ярлыка Windows, заголовка окна и панели задач.
Он содержит размеры 16, 24, 32, 48, 64, 128 и 256 пикселей. Для пересоздания
запустите `scripts/build_icon.ps1` из корня репозитория в Windows.

SVG продуктов в корне этой папки — неизменённые официальные иконки, используемые для их
идентификации. Источники, закреплённая ревизия и ссылки на условия использования
указаны в английском разделе выше. Copyright © 2026 JetBrains s.r.o.
Названия и логотипы продуктов JetBrains — товарные знаки JetBrains s.r.o.;
Android Studio и его логотип — товарные знаки Google LLC. Остальные товарные знаки
принадлежат их владельцам. Проект независимый и не связан с правообладателями,
не является их представителем и не получал их одобрения или спонсорской поддержки.

В `branding/` находится аватар DragonSavA с восстановленной прозрачностью центра,
оригинальная векторная эмблема терминала для подписи Codex и официальный знак
GitHub из Primer Octicons с приложенной лицензией MIT. Варианты `-white.svg`
используются в тёмной теме. Источники и условия использования указаны выше.
