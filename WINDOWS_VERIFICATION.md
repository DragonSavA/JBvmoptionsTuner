# Windows verification / Проверка в Windows

## English

Run these checks on Windows 11 before a release. Use temporary copies of
`.vmoptions` files. The Python tests cover the core, configuration migration and
Windows shortcut creation; the PowerShell tests cover interpreter discovery.

### Setup and launch

1. Download/extract the complete project into a writable folder and run `start.bat`.
   Verify that Python 3.13+ is detected, `.venv` is created, dependencies are installed,
   and the window opens. Run it again to check reuse of the environment.
2. On a clean Windows test machine, repeat with no Python, with only Python 3.12,
   and with Python 3.13+ installed outside `PATH`. Verify automatic installation
   or discovery, including Python Install Manager runtimes.
3. Repeat without a compatible Windows App Runtime: setup should install the
   release required by PyWinRT. Check installer errors leave a visible explanation.
4. Test a project path containing spaces, Cyrillic and `&`. Test a broken or old
   `.venv`: it should be preserved as `.venv.backup-…` and replaced.
5. Verify that the window is resizable, opens maximized, and displays the VMopT
   icon in its header, title bar and taskbar, plus version `1.0.0-RC1`.

### Desktop and sign-in settings

1. On first use, both switches should be on. Inspect the desktop shortcut: its
   target is the project’s `start.bat`, its working directory is the project folder,
   and its icon is `assets/vmopt.ico`. Test a redirected / OneDrive desktop too.
2. Switch **Иконка на рабочем столе** off. The link should disappear. Reopen using
   both `start.bat` and `python path\to\main.py`; the link must stay absent.
3. Turn the switch on and verify the recreated link launches the app. Delete the
   link manually while the setting is enabled and relaunch: it should be repaired.
4. Inspect `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`:
   `JetBrainsVmoptionsTuner` must contain `pythonw.exe`, `main.py` and `--background`.
   Toggle autostart off/on and verify removal/recreation independently of the link.
5. Move a test copy of the project. Launch its batch file and toggle autostart
   off/on. Both launch paths should now refer to the new location.

### Editing, synchronization and appearance

1. Add two IDEs using temporary `.vmoptions` copies; edit, remove and re-add a binding.
2. Create an option set for both IDEs. Add the compatibility option using the button.
   Assign one IDE to another set and verify it leaves the original set.
3. Check rejection of lines without `-`, duplicate removal, and settings restoration
   after reopening. Legacy configurations should gain the enabled desktop setting.
4. Verify full-file editing, green highlighting, missing-option and unsaved-edit
   notices. Save/discard changes, synchronize one/all files, and check that a second
   synchronization leaves file bytes unchanged. Check CRLF and UTF-8 BOM preservation.
5. Remove a required line and run `python main.py --background`. It should be
   restored without a window. `last_auto_sync` changes only if files change.
   Repeat at Windows sign-in, including an older registration using a system Python.
6. Check system/light/dark themes, persistence of `#00FF00`, and rejection of
   `00FF00`, `#GGFF00` and shortened hex colours.

### Automated checks

After setup, run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_launcher.ps1 -PythonExecutable "$PWD\.venv\Scripts\python.exe"
.\.venv\Scripts\python.exe tests\ui_smoke.py
.\start.bat -PrepareOnly
```

The opt-in UI smoke test briefly opens and closes a real WinUI window, checks SVG
loading and both desktop-toggle transitions, and uses temporary configuration and
shortcut files. It leaves the user’s autostart registration untouched.
`-PrepareOnly` performs the normal prerequisite checks and applies the saved
shortcut preference without opening the UI.

## Русский

Перед выпуском выполните проверки в Windows 11 на временных копиях `.vmoptions`.
Python-тесты покрывают ядро, миграцию конфигурации и создание ярлыков Windows;
PowerShell-тесты проверяют поиск интерпретатора.

### Установка и запуск

1. Скачайте и полностью распакуйте проект в доступную на запись папку, запустите
   `start.bat`. Проверьте обнаружение Python 3.13+, создание `.venv`, установку
   зависимостей и открытие окна. Повторный запуск должен использовать готовую среду.
2. На чистой тестовой Windows повторите сценарий без Python, только с Python 3.12
   и с Python 3.13+ вне `PATH`. Проверьте установку или обнаружение, в том числе
   сред, установленных через Python Install Manager.
3. Повторите без совместимого Windows App Runtime: должна установиться версия,
   требуемая PyWinRT. При ошибке установщика должно оставаться понятное сообщение.
4. Проверьте путь с пробелами, кириллицей и `&`. Повреждённая или старая `.venv`
   должна сохраняться в `.venv.backup-…` перед созданием новой.
5. Окно должно менять размер, открываться развёрнутым и показывать VMopT в шапке,
   заголовке и панели задач, а также версию `1.0.0-RC1`.

### Ярлык и автозапуск

1. При первом использовании оба тумблера должны быть включены. У ярлыка на рабочем
   столе проверьте цель `start.bat`, рабочую папку проекта и иконку `assets/vmopt.ico`.
   Проверьте также перенаправленный рабочий стол / OneDrive.
2. Выключите **Иконка на рабочем столе**: ярлык должен исчезнуть. Снова запустите
   приложение через `start.bat` и `python путь\к\main.py`: ярлык не должен появляться.
3. Включите тумблер и проверьте запуск через созданный ярлык. Удалите ярлык вручную
   при включённой настройке: следующий запуск должен его восстановить.
4. В `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` значение
   `JetBrainsVmoptionsTuner` должно содержать `pythonw.exe`, `main.py`, `--background`.
   Выключение/включение автозапуска удаляет/создаёт его независимо от ярлыка.
5. Перенесите тестовую копию проекта, запустите её `.bat` и выключите/включите
   автозапуск. Оба способа запуска должны ссылаться на новую папку.

### Редактирование, синхронизация и оформление

1. Добавьте две IDE с временными `.vmoptions`, отредактируйте, удалите и снова
   добавьте связку.
2. Создайте набор для обеих IDE и добавьте compatibility-параметр кнопкой.
   Переназначьте одну IDE другому набору: она должна исчезнуть из первого.
3. Проверьте отказ для строки без `-`, удаление дубликатов и восстановление настроек
   при повторном запуске. Старая конфигурация должна получить включённую настройку ярлыка.
4. Проверьте полный редактор, зелёную подсветку, предупреждения о недостающих строках
   и ручных правках. Сохраните/отмените изменения, синхронизируйте один/все файлы:
   повторная синхронизация не должна менять байты. Проверьте CRLF и UTF-8 BOM.
5. Удалите обязательную строку и выполните `python main.py --background`: она должна
   восстановиться без окна. `last_auto_sync` меняется только при изменении файлов.
   Повторите при входе в Windows, включая старую регистрацию с системным Python.
6. Проверьте системную/светлую/тёмную темы, сохранение `#00FF00` и отказ для
   `00FF00`, `#GGFF00` и короткого hex.

### Автоматические проверки

После установки выполните из корня проекта:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_launcher.ps1 -PythonExecutable "$PWD\.venv\Scripts\python.exe"
.\.venv\Scripts\python.exe tests\ui_smoke.py
.\start.bat -PrepareOnly
```

Отдельный тест интерфейса ненадолго открывает и закрывает настоящее окно WinUI,
проверяет загрузку SVG и оба переключения тумблера ярлыка. Конфигурация и ярлыки
создаются во временной папке; пользовательская регистрация автозапуска не меняется.
`-PrepareOnly` выполняет обычные проверки зависимостей и применяет сохранённое
состояние ярлыка, не открывая интерфейс.
