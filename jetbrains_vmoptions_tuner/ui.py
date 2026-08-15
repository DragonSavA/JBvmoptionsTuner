"""WinUI 3 interface implemented with PyWinRT projections."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Tuple, Union, cast, override
from uuid import uuid4

from winrt.system import Array
from winrt.windows.foundation import Uri
from winrt.windows.ui.text import TextGetOptions, TextSetOptions
from winrt.windows.ui.xaml.interop import TypeKind, TypeName
from winui3.microsoft.ui.xaml import (
    Application,
    ApplicationInitializationCallbackParams,
    ElementTheme,
    FrameworkElement,
    HorizontalAlignment,
    LaunchActivatedEventArgs,
    VerticalAlignment,
    Visibility,
    Window,
)
from winui3.microsoft.ui.xaml.controls import (
    Border,
    Button,
    ComboBox,
    Image,
    InfoBar,
    InfoBarSeverity,
    ListView,
    ListViewItem,
    Orientation,
    RichEditBox,
    StackPanel,
    TextBlock,
    TextBox,
    ToggleSwitch,
    XamlControlsResources,
)
from winui3.microsoft.ui.xaml.controls.primitives import ToggleButton
from winui3.microsoft.ui.xaml.markup import (
    IXamlMetadataProvider,
    IXamlType,
    XamlReader,
    XmlnsDefinition,
)
from winui3.microsoft.ui.xaml.media import SolidColorBrush, Stretch
from winui3.microsoft.ui.xaml.media.imaging import SvgImageSource
from winui3.microsoft.ui.xaml.xamltypeinfo import XamlControlsXamlMetaDataProvider
from winui3.microsoft.ui.windowing import OverlappedPresenter
from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import (
    InitializeOptions,
    initialize,
)

from . import autostart
from .catalog import PRODUCTS, PRODUCT_BY_KEY, Product
from .config import ConfigStore
from .native_picker import choose_vmoptions_file
from .sync import (
    TextFile,
    group_for_ide,
    missing_lines,
    now_iso,
    read_text_file,
    save_edited_text,
    synchronize_all,
    synchronize_ide,
    validate_option_lines,
)


IGNORE_COMPATIBILITY = "-Didea.ignore.plugin.compatibility=true"
ACCENT_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
GREEN = "#22C55E"
ASSET_DIR = Path(__file__).with_name("assets")


def color_tuple(value: str) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return 255, int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def brush(value: str) -> SolidColorBrush:
    result = SolidColorBrush()
    result.color = color_tuple(value)
    return result


def foreground_for(value: str) -> str:
    _, red, green, blue = color_tuple(value)
    luminance = (red * 299 + green * 587 + blue * 114) / 1000
    return "#111111" if luminance > 150 else "#FFFFFF"


def display_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "ещё не выполнялась"
    try:
        parsed = datetime.fromisoformat(value).astimezone()
    except ValueError:
        return value
    return parsed.strftime("%d.%m.%Y, %H:%M:%S")


class MainController:
    def __init__(self, window: Window, store: ConfigStore, entry_script: Path) -> None:
        self.window = window
        self.store = store
        self.entry_script = entry_script
        self.config = self.store.load()
        self._handlers: list[Callable[..., None]] = []
        self._setting_autostart = False
        self._loading_editor = False
        self._selected_ide_id: str | None = None
        self._selected_group_id: str | None = None
        self._viewer_ide_id: str | None = None
        self._current_file: TextFile | None = None
        self._loaded_editor_text = ""
        self._editor_dirty = False
        self._ide_index_ids: list[str] = []
        self._group_index_ids: list[str] = []
        self._group_ide_buttons: dict[str, ToggleButton] = {}
        self._viewer_buttons: dict[str, Button] = {}

        root = cast(FrameworkElement, window.content.as_(FrameworkElement))
        self.root = root
        self.theme_picker = self._find(root, "ThemePicker", ComboBox)
        self.accent_box = self._find(root, "AccentBox", TextBox)
        self.apply_appearance_button = self._find(root, "ApplyAppearanceButton", Button)
        self.autostart_toggle = self._find(root, "AutostartToggle", ToggleSwitch)
        self.autostart_hint = self._find(root, "AutostartHint", TextBlock)
        self.status_info = self._find(root, "StatusInfo", InfoBar)
        self.sync_all_top = self._find(root, "SyncAllTop", Button)
        self.sync_all_bottom = self._find(root, "SyncAllBottom", Button)

        self.ide_list = self._find(root, "IdeList", ListView)
        self.product_picker = self._find(root, "ProductPicker", ComboBox)
        self.ide_path_box = self._find(root, "IdePathBox", TextBox)
        self.new_ide_button = self._find(root, "NewIdeButton", Button)
        self.choose_file_button = self._find(root, "ChooseFileButton", Button)
        self.save_ide_button = self._find(root, "SaveIdeButton", Button)
        self.delete_ide_button = self._find(root, "DeleteIdeButton", Button)

        self.group_list = self._find(root, "GroupList", ListView)
        self.group_name_box = self._find(root, "GroupNameBox", TextBox)
        self.group_lines_box = self._find(root, "GroupLinesBox", TextBox)
        self.group_ide_panel = self._find(root, "GroupIdeButtons", StackPanel)
        self.group_validation = self._find(root, "GroupValidationText", TextBlock)
        self.new_group_button = self._find(root, "NewGroupButton", Button)
        self.add_compatibility_button = self._find(root, "AddCompatibilityButton", Button)
        self.save_group_button = self._find(root, "SaveGroupButton", Button)
        self.delete_group_button = self._find(root, "DeleteGroupButton", Button)

        self.viewer_ide_panel = self._find(root, "ViewerIdeButtons", StackPanel)
        self.viewer_path = self._find(root, "ViewerPathText", TextBlock)
        self.missing_panel = self._find(root, "MissingPanel", Border)
        self.missing_text = self._find(root, "MissingText", TextBlock)
        self.sync_selected_button = self._find(root, "SyncSelectedButton", Button)
        self.save_panel = self._find(root, "SavePanel", Border)
        self.save_file_button = self._find(root, "SaveFileButton", Button)
        self.discard_file_button = self._find(root, "DiscardFileButton", Button)
        self.options_editor = self._find(root, "OptionsEditor", RichEditBox)
        self.last_manual_text = self._find(root, "LastManualText", TextBlock)
        self.last_auto_text = self._find(root, "LastAutoText", TextBlock)

    @staticmethod
    def _find(root: FrameworkElement, name: str, expected_type):
        item = root.find_name(name)
        if item is None:
            raise RuntimeError(f"В XAML отсутствует элемент {name}")
        return item.as_(expected_type)

    def _bind(self, add_handler: Callable[[Callable[..., None]], object], handler: Callable) -> None:
        def safe(sender, args) -> None:
            try:
                handler(sender, args)
            except Exception as error:  # callbacks must never leak into WinRT
                self.show_status(str(error), InfoBarSeverity.ERROR, "Ошибка")

        self._handlers.append(safe)
        add_handler(safe)

    def initialize(self) -> None:
        self._populate_product_picker()
        self._bind(self.apply_appearance_button.add_click, self.on_apply_appearance)
        self._bind(self.autostart_toggle.add_toggled, self.on_autostart_toggled)
        self._bind(self.sync_all_top.add_click, self.on_sync_all)
        self._bind(self.sync_all_bottom.add_click, self.on_sync_all)
        self._bind(self.ide_list.add_selection_changed, self.on_ide_selected)
        self._bind(self.new_ide_button.add_click, self.on_new_ide)
        self._bind(self.choose_file_button.add_click, self.on_choose_file)
        self._bind(self.save_ide_button.add_click, self.on_save_ide)
        self._bind(self.delete_ide_button.add_click, self.on_delete_ide)
        self._bind(self.group_list.add_selection_changed, self.on_group_selected)
        self._bind(self.new_group_button.add_click, self.on_new_group)
        self._bind(self.group_lines_box.add_text_changed, self.on_group_lines_changed)
        self._bind(self.add_compatibility_button.add_click, self.on_add_compatibility)
        self._bind(self.save_group_button.add_click, self.on_save_group)
        self._bind(self.delete_group_button.add_click, self.on_delete_group)
        self._bind(self.sync_selected_button.add_click, self.on_sync_selected)
        self._bind(self.options_editor.add_text_changed, self.on_editor_changed)
        self._bind(self.save_file_button.add_click, self.on_save_file)
        self._bind(self.discard_file_button.add_click, self.on_discard_file)

        first_run_message = self._ensure_first_run_autostart()
        self._load_appearance()
        self._refresh_autostart()
        self.refresh_all()
        if first_run_message:
            self.show_status(first_run_message, InfoBarSeverity.WARNING, "Автозапуск")

    def _ensure_first_run_autostart(self) -> str | None:
        settings = self.config["settings"]
        if settings.get("first_run_completed"):
            return None
        try:
            autostart.enable(self.entry_script)
        except OSError as error:
            return f"Не удалось включить автозапуск: {error}"
        settings["first_run_completed"] = True
        self.store.save(self.config)
        return None

    def _populate_product_picker(self) -> None:
        self.product_picker.items.clear()
        for product in PRODUCTS:
            item = self._product_row(product, 34, include_name=True)
            self.product_picker.items.append(item)
        self.product_picker.selected_index = 0

    def _product_tile(self, product: Product, size: float = 36) -> Border:
        tile = Border()
        tile.width = size
        tile.height = size
        tile.corner_radius = (7, 7, 7, 7)
        if product.icon:
            icon_path = ASSET_DIR / product.icon
            if icon_path.is_file():
                image = Image()
                image.width = size
                image.height = size
                image.stretch = Stretch.UNIFORM
                image.source = SvgImageSource(Uri(icon_path.resolve().as_uri()))
                tile.child = image
                return tile

        # JetBrains Client has no separate official icon in the product asset
        # catalog, so it deliberately keeps the old monogram as a fallback.
        tile.background = brush(product.color)
        label = TextBlock()
        label.text = product.initials
        label.font_size = 11 if len(product.initials) < 3 else 9
        label.horizontal_alignment = HorizontalAlignment.CENTER
        label.vertical_alignment = VerticalAlignment.CENTER
        label.foreground = brush("#FFFFFF")
        tile.child = label
        return tile

    def _product_row(self, product: Product, size: float = 36, include_name: bool = True) -> StackPanel:
        row = StackPanel()
        row.orientation = Orientation.HORIZONTAL
        row.spacing = 10
        row.children.append(self._product_tile(product, size))
        if include_name:
            label = TextBlock()
            label.text = product.name
            label.vertical_alignment = VerticalAlignment.CENTER
            row.children.append(label)
        return row

    def _load_appearance(self) -> None:
        theme = self.config["settings"].get("theme", "system")
        self.theme_picker.selected_index = {"system": 0, "light": 1, "dark": 2}.get(theme, 0)
        accent = self.config["settings"].get("accent_color", "#4F7CFF")
        self.accent_box.text = accent if ACCENT_PATTERN.fullmatch(accent) else "#4F7CFF"
        self.apply_appearance(save=False)

    def apply_appearance(self, save: bool = True) -> None:
        accent = self.accent_box.text.strip()
        if not ACCENT_PATTERN.fullmatch(accent):
            raise ValueError("Акцентный цвет должен быть в формате #00FF00.")
        theme_index = self.theme_picker.selected_index
        theme = {0: "system", 1: "light", 2: "dark"}.get(theme_index, "system")
        self.root.requested_theme = {
            "system": ElementTheme.DEFAULT,
            "light": ElementTheme.LIGHT,
            "dark": ElementTheme.DARK,
        }[theme]
        accent_brush = brush(accent)
        text_brush = brush(foreground_for(accent))
        for button in (
            self.sync_all_top,
            self.sync_all_bottom,
            self.sync_selected_button,
            self.save_file_button,
            self.save_ide_button,
            self.save_group_button,
        ):
            button.background = accent_brush
            button.foreground = text_brush
        self.config["settings"]["theme"] = theme
        self.config["settings"]["accent_color"] = accent.upper()
        self._style_viewer_buttons()
        if save:
            self.store.save(self.config)

    def on_apply_appearance(self, _sender, _args) -> None:
        self.apply_appearance()
        self.show_status("Оформление применено.", InfoBarSeverity.SUCCESS)

    def _refresh_autostart(self) -> None:
        self._setting_autostart = True
        try:
            enabled = autostart.is_enabled()
            self.autostart_toggle.is_on = enabled
            self.autostart_hint.text = (
                "При входе в Windows файлы проверяются без открытия окна."
                if enabled
                else "Автоматическое восстановление при входе в Windows отключено."
            )
        finally:
            self._setting_autostart = False

    def on_autostart_toggled(self, _sender, _args) -> None:
        if self._setting_autostart:
            return
        try:
            if self.autostart_toggle.is_on:
                autostart.enable(self.entry_script)
            else:
                autostart.disable()
        except OSError:
            self._refresh_autostart()
            raise
        self._refresh_autostart()
        self.show_status(
            "Автозапуск включён." if self.autostart_toggle.is_on else "Автозапуск выключен.",
            InfoBarSeverity.SUCCESS,
        )

    def show_status(
        self, message: str, severity=InfoBarSeverity.INFORMATIONAL, title: str = ""
    ) -> None:
        self.status_info.title = title
        self.status_info.message = message
        self.status_info.severity = severity
        self.status_info.is_open = True

    def _save_config(self) -> None:
        self.store.save(self.config)
        self.refresh_timestamps()

    def refresh_all(self) -> None:
        self.refresh_ide_list()
        self.refresh_group_list()
        self.refresh_group_ide_buttons()
        self.refresh_viewer_buttons()
        self.refresh_timestamps()

    def refresh_timestamps(self) -> None:
        self.last_manual_text.text = (
            "Последняя ручная синхронизация: "
            + display_timestamp(self.config.get("last_manual_sync"))
        )
        self.last_auto_text.text = (
            "Последнее автоматическое восстановление: "
            + display_timestamp(self.config.get("last_auto_sync"))
        )

    def _ide_by_id(self, ide_id: str | None) -> dict | None:
        return next((item for item in self.config["ides"] if item.get("id") == ide_id), None)

    def _group_by_id(self, group_id: str | None) -> dict | None:
        return next((item for item in self.config["groups"] if item.get("id") == group_id), None)

    def refresh_ide_list(self) -> None:
        self.ide_list.items.clear()
        self._ide_index_ids.clear()
        selected_index = -1
        for index, ide in enumerate(self.config["ides"]):
            ide_id = str(ide.get("id"))
            product = PRODUCT_BY_KEY.get(str(ide.get("product")))
            if not product:
                continue
            row = self._product_row(product, 38, include_name=False)
            detail = StackPanel()
            detail.spacing = 2
            name = TextBlock()
            name.text = product.name
            path = TextBlock()
            path.text = str(ide.get("path", ""))
            path.opacity = 0.65
            path.font_size = 11
            detail.children.append(name)
            detail.children.append(path)
            row.children.append(detail)
            item = ListViewItem()
            item.content = row
            item.padding = (10, 8, 10, 8)
            item.margin = (0, 2, 0, 2)
            item.horizontal_content_alignment = HorizontalAlignment.STRETCH
            self.ide_list.items.append(item)
            self._ide_index_ids.append(ide_id)
            if ide_id == self._selected_ide_id:
                selected_index = index
        self.ide_list.selected_index = selected_index

    def on_new_ide(self, _sender, _args) -> None:
        self._selected_ide_id = None
        self.ide_list.selected_index = -1
        self.product_picker.selected_index = 0
        self.ide_path_box.text = ""
        self.delete_ide_button.is_enabled = False

    def on_ide_selected(self, _sender, _args) -> None:
        index = self.ide_list.selected_index
        if index < 0 or index >= len(self._ide_index_ids):
            return
        self._selected_ide_id = self._ide_index_ids[index]
        ide = self._ide_by_id(self._selected_ide_id)
        if not ide:
            return
        product_key = ide.get("product")
        self.product_picker.selected_index = next(
            (i for i, product in enumerate(PRODUCTS) if product.key == product_key), 0
        )
        self.ide_path_box.text = str(ide.get("path", ""))
        self.delete_ide_button.is_enabled = True

    def on_choose_file(self, _sender, _args) -> None:
        selected = choose_vmoptions_file()
        if selected:
            self.ide_path_box.text = selected

    def on_save_ide(self, _sender, _args) -> None:
        index = self.product_picker.selected_index
        if index < 0 or index >= len(PRODUCTS):
            raise ValueError("Выберите IDE.")
        product = PRODUCTS[index]
        path = Path(self.ide_path_box.text.strip())
        if path.suffix.lower() != ".vmoptions":
            raise ValueError("Выберите файл с расширением .vmoptions.")
        if not path.is_file():
            raise ValueError("Указанный файл не существует.")
        duplicate = next(
            (
                ide
                for ide in self.config["ides"]
                if ide.get("product") == product.key and ide.get("id") != self._selected_ide_id
            ),
            None,
        )
        if duplicate:
            raise ValueError(f"Для {product.name} связка уже создана.")
        ide = self._ide_by_id(self._selected_ide_id)
        if ide is None:
            ide = {"id": str(uuid4())}
            self.config["ides"].append(ide)
            self._selected_ide_id = ide["id"]
        ide.update({"product": product.key, "path": str(path.resolve())})
        self._save_config()
        self.refresh_all()
        self.show_status("Связка IDE сохранена.", InfoBarSeverity.SUCCESS)

    def on_delete_ide(self, _sender, _args) -> None:
        if not self._selected_ide_id:
            return
        if self._editor_dirty and self._viewer_ide_id == self._selected_ide_id:
            raise ValueError("Сначала сохраните или отмените изменения в открытом файле.")
        removed = self._selected_ide_id
        self.config["ides"] = [ide for ide in self.config["ides"] if ide.get("id") != removed]
        for group in self.config["groups"]:
            group["ide_ids"] = [ide_id for ide_id in group.get("ide_ids", []) if ide_id != removed]
        if self._viewer_ide_id == removed:
            self._viewer_ide_id = None
            self._current_file = None
        self._selected_ide_id = None
        self._save_config()
        self.refresh_all()
        self.on_new_ide(None, None)
        self.show_status("Связка IDE удалена.", InfoBarSeverity.SUCCESS)

    def refresh_group_list(self) -> None:
        self.group_list.items.clear()
        self._group_index_ids.clear()
        selected_index = -1
        for index, group in enumerate(self.config["groups"]):
            group_id = str(group.get("id"))
            panel = StackPanel()
            panel.spacing = 7
            title = TextBlock()
            title.text = str(group.get("name", "Без названия"))
            panel.children.append(title)
            icons = StackPanel()
            icons.orientation = Orientation.HORIZONTAL
            icons.spacing = 5
            for ide_id in group.get("ide_ids", []):
                ide = self._ide_by_id(str(ide_id))
                product = PRODUCT_BY_KEY.get(str(ide.get("product"))) if ide else None
                if product:
                    icons.children.append(self._product_tile(product, 27))
            panel.children.append(icons)
            item = ListViewItem()
            item.content = panel
            item.padding = (10, 8, 10, 8)
            item.margin = (0, 2, 0, 2)
            item.horizontal_content_alignment = HorizontalAlignment.STRETCH
            self.group_list.items.append(item)
            self._group_index_ids.append(group_id)
            if group_id == self._selected_group_id:
                selected_index = index
        self.group_list.selected_index = selected_index

    def refresh_group_ide_buttons(self, selected_ids: set[str] | None = None) -> None:
        if selected_ids is None:
            group = self._group_by_id(self._selected_group_id)
            selected_ids = set(group.get("ide_ids", [])) if group else set()
        self.group_ide_panel.children.clear()
        self._group_ide_buttons.clear()
        for ide in self.config["ides"]:
            ide_id = str(ide.get("id"))
            product = PRODUCT_BY_KEY.get(str(ide.get("product")))
            if not product:
                continue
            button = ToggleButton()
            button.content = self._product_row(product, 30, include_name=True)
            button.is_checked = ide_id in selected_ids
            self.group_ide_panel.children.append(button)
            self._group_ide_buttons[ide_id] = button

    def on_new_group(self, _sender, _args) -> None:
        self._selected_group_id = None
        self.group_list.selected_index = -1
        self.group_name_box.text = ""
        self.group_lines_box.text = ""
        self.refresh_group_ide_buttons(set())
        self.delete_group_button.is_enabled = False
        self._update_group_validation()

    def on_group_selected(self, _sender, _args) -> None:
        index = self.group_list.selected_index
        if index < 0 or index >= len(self._group_index_ids):
            return
        self._selected_group_id = self._group_index_ids[index]
        group: dict | None = self._group_by_id(self._selected_group_id)
        if not group:
            return
        self.group_name_box.text = str(group.get("name", ""))
        self.group_lines_box.text = "\r\n".join(group.get("lines", []))
        self.refresh_group_ide_buttons(set(group.get("ide_ids", [])))
        self.delete_group_button.is_enabled = True
        self._update_group_validation()

    def on_group_lines_changed(self, _sender, _args) -> None:
        self._update_group_validation()

    def _update_group_validation(self) -> None:
        raw_lines = [line.strip() for line in self.group_lines_box.text.splitlines() if line.strip()]
        invalid = [line for line in raw_lines if not line.startswith("-")]
        if invalid:
            self.group_validation.text = "Каждая строка должна начинаться с ‘-’."
            self.group_validation.visibility = Visibility.VISIBLE
        else:
            self.group_validation.text = ""
            self.group_validation.visibility = Visibility.COLLAPSED
        self.add_compatibility_button.is_enabled = IGNORE_COMPATIBILITY not in raw_lines

    def on_add_compatibility(self, _sender, _args) -> None:
        lines = [line.rstrip() for line in self.group_lines_box.text.splitlines()]
        if IGNORE_COMPATIBILITY in (line.strip() for line in lines):
            return
        if self.group_lines_box.text and not self.group_lines_box.text.endswith(("\r", "\n")):
            self.group_lines_box.text += "\r\n"
        self.group_lines_box.text += IGNORE_COMPATIBILITY

    def on_save_group(self, _sender, _args) -> None:
        name = self.group_name_box.text.strip()
        if not name:
            raise ValueError("Введите название набора.")
        lines, errors = validate_option_lines(self.group_lines_box.text)
        if errors:
            self.group_validation.text = "\n".join(errors)
            self.group_validation.visibility = Visibility.VISIBLE
            raise ValueError(errors[0])
        assigned = [
            ide_id for ide_id, button in self._group_ide_buttons.items() if button.is_checked
        ]
        group: dict = self._group_by_id(self._selected_group_id) or {}
        if not group:
            group = {"id": str(uuid4())}
            self.config["groups"].append(group)
            self._selected_group_id = group["id"]
        # Reassignment is deliberate: it enforces the one-IDE/one-group rule.
        for other in self.config["groups"]:
            if other is not group:
                other["ide_ids"] = [
                    ide_id for ide_id in other.get("ide_ids", []) if ide_id not in assigned
                ]
        group.update({"name": name, "lines": lines, "ide_ids": assigned})
        self._save_config()
        self.refresh_group_list()
        self.refresh_viewer_buttons()
        if self._viewer_ide_id:
            self.select_viewer_ide(self._viewer_ide_id)
        self.show_status("Набор сохранён.", InfoBarSeverity.SUCCESS)

    def on_delete_group(self, _sender, _args) -> None:
        if not self._selected_group_id:
            return
        self.config["groups"] = [
            group for group in self.config["groups"] if group.get("id") != self._selected_group_id
        ]
        self._selected_group_id = None
        self._save_config()
        self.refresh_group_list()
        self.refresh_viewer_buttons()
        self.on_new_group(None, None)
        if self._viewer_ide_id:
            self.select_viewer_ide(self._viewer_ide_id)
        self.show_status("Набор удалён.", InfoBarSeverity.SUCCESS)

    def refresh_viewer_buttons(self) -> None:
        self.viewer_ide_panel.children.clear()
        self._viewer_buttons.clear()
        for ide in self.config["ides"]:
            ide_id = str(ide.get("id"))
            product = PRODUCT_BY_KEY.get(str(ide.get("product")))
            if not product:
                continue
            button = Button()
            button.content = self._product_row(product, 36, include_name=True)

            def choose(_sender, _args, selected_id=ide_id) -> None:
                self.select_viewer_ide(selected_id)

            self._bind(button.add_click, choose)
            self.viewer_ide_panel.children.append(button)
            self._viewer_buttons[ide_id] = button
        if self._viewer_ide_id not in self._viewer_buttons:
            self._viewer_ide_id = None
        if self._viewer_ide_id is None and self.config["ides"] and not self._editor_dirty:
            self.select_viewer_ide(str(self.config["ides"][0].get("id")))
        else:
            self._style_viewer_buttons()

    def _style_viewer_buttons(self) -> None:
        accent = self.config["settings"].get("accent_color", "#4F7CFF")
        accent_brush = brush(accent if ACCENT_PATTERN.fullmatch(accent) else "#4F7CFF")
        for ide_id, button in self._viewer_buttons.items():
            button.border_brush = accent_brush
            button.border_thickness = (2, 2, 2, 2) if ide_id == self._viewer_ide_id else (0, 0, 0, 0)

    @staticmethod
    def _logical_text(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.rstrip("\n")

    def _editor_text(self) -> str:
        raw = self.options_editor.document.get_text(TextGetOptions.NONE)
        return self._logical_text(raw)

    def _set_editor_text(self, text: str) -> None:
        logical = self._logical_text(text)
        self._loading_editor = True
        try:
            self.options_editor.document.set_text(TextSetOptions.NONE, logical)
            self._loaded_editor_text = logical
            self._editor_dirty = False
            self.save_panel.visibility = Visibility.COLLAPSED
        finally:
            self._loading_editor = False

    def select_viewer_ide(self, ide_id: str) -> None:
        if self._editor_dirty and ide_id != self._viewer_ide_id:
            self.show_status(
                "Сначала сохраните или отмените изменения в открытом файле.",
                InfoBarSeverity.WARNING,
            )
            return
        ide = self._ide_by_id(ide_id)
        if not ide:
            return
        self._viewer_ide_id = ide_id
        self.viewer_path.text = str(ide.get("path", ""))
        try:
            self._current_file = read_text_file(str(ide.get("path", "")))
        except (OSError, UnicodeError) as error:
            self._current_file = None
            self._set_editor_text("")
            self.options_editor.is_read_only = True
            self.missing_panel.visibility = Visibility.COLLAPSED
            self.show_status(f"Не удалось открыть файл: {error}", InfoBarSeverity.ERROR)
            self._style_viewer_buttons()
            return
        self.options_editor.is_read_only = False
        self._set_editor_text(self._current_file.text)
        self._highlight_required_lines()
        self._update_missing_panel(self._loaded_editor_text)
        self._style_viewer_buttons()

    def _required_lines(self) -> list[str]:
        group = group_for_ide(self.config, self._viewer_ide_id or "")
        return list(group.get("lines", [])) if group else []

    def _highlight_required_lines(self) -> None:
        required = set(self._required_lines())
        if not required:
            return
        cursor = 0
        for line in self._loaded_editor_text.splitlines(keepends=True):
            content = line.rstrip("\r\n")
            if content.strip() in required:
                end = cursor + len(content)
                text_range = self.options_editor.document.get_range(cursor, end)
                text_range.character_format.foreground_color = color_tuple(GREEN)
            cursor += len(line)
        # splitlines(keepends=True) returns no line for an empty final paragraph;
        # the logical editor text deliberately excludes that paragraph.

    def _update_missing_panel(self, text: str) -> None:
        missing = missing_lines(text, self._required_lines())
        if missing:
            suffix = "строка" if len(missing) == 1 else "строки"
            self.missing_text.text = (
                f"В файле отсутствует {len(missing)} {suffix} из назначенного набора."
            )
            self.missing_panel.visibility = Visibility.VISIBLE
        else:
            self.missing_panel.visibility = Visibility.COLLAPSED

    def on_editor_changed(self, _sender, _args) -> None:
        if self._loading_editor or self._current_file is None:
            return
        current = self._editor_text()
        self._editor_dirty = current != self._loaded_editor_text
        self.save_panel.visibility = Visibility.VISIBLE if self._editor_dirty else Visibility.COLLAPSED
        self._update_missing_panel(current)

    def on_save_file(self, _sender, _args) -> None:
        if not self._viewer_ide_id or self._current_file is None:
            return
        ide = self._ide_by_id(self._viewer_ide_id)
        if not ide:
            return
        logical = self._editor_text()
        text = logical + (self._current_file.newline if logical else "")
        save_edited_text(str(ide.get("path", "")), text, self._current_file)
        self.select_viewer_ide(self._viewer_ide_id)
        self.show_status("Файл .vmoptions сохранён.", InfoBarSeverity.SUCCESS)

    def on_discard_file(self, _sender, _args) -> None:
        if self._viewer_ide_id:
            self._editor_dirty = False
            self.select_viewer_ide(self._viewer_ide_id)

    def on_sync_selected(self, _sender, _args) -> None:
        if self._editor_dirty:
            raise ValueError("Сначала сохраните или отмените ручные изменения.")
        ide = self._ide_by_id(self._viewer_ide_id)
        if not ide:
            return
        result = synchronize_ide(self.config, ide)
        self.config["last_manual_sync"] = now_iso()
        self._save_config()
        if result.error:
            raise OSError(result.error)
        self.select_viewer_ide(str(ide.get("id")))
        message = (
            f"Добавлено строк: {len(result.added_lines)}."
            if result.changed
            else "Файл уже синхронизирован."
        )
        self.show_status(message, InfoBarSeverity.SUCCESS)

    def on_sync_all(self, _sender, _args) -> None:
        if self._editor_dirty:
            raise ValueError("Сначала сохраните или отмените ручные изменения.")
        report = synchronize_all(self.config)
        self.config["last_manual_sync"] = now_iso()
        self._save_config()
        if self._viewer_ide_id:
            self.select_viewer_ide(self._viewer_ide_id)
        if report.errors:
            details = "; ".join(f"{item.path}: {item.error}" for item in report.errors)
            self.show_status(
                f"Синхронизация завершена с ошибками. {details}",
                InfoBarSeverity.ERROR,
                "Не все файлы обработаны",
            )
        elif report.changed:
            self.show_status(
                f"Синхронизировано файлов: {report.changed_count}.", InfoBarSeverity.SUCCESS
            )
        else:
            self.show_status("Все файлы уже синхронизированы.", InfoBarSeverity.SUCCESS)


class App(Application, IXamlMetadataProvider):
    startup_entry_script: Path

    def __init__(self) -> None:
        self._provider = XamlControlsXamlMetaDataProvider()
        self._entry_script = self.startup_entry_script
        self._window: Window | None = None
        self._controller: MainController | None = None

    @override
    def _on_launched(self, _args: LaunchActivatedEventArgs) -> None:
        self.resources.merged_dictionaries.append(XamlControlsResources())
        xaml = Path(__file__).with_name("main_window.xaml").read_text(encoding="utf-8")
        window = XamlReader.load(xaml).as_(Window)
        window.title = "vmoptions Tuner"
        self._window = window
        self._controller = MainController(window, ConfigStore(), self._entry_script)
        self._controller.initialize()
        window.activate()
        try:
            window.app_window.presenter.as_(OverlappedPresenter).maximize()
        except (AttributeError, OSError):
            # The normal resizable window is still usable if a custom presenter
            # is supplied by a future Windows App Runtime.
            pass

    @override
    def get_xaml_type(self, type: Union[TypeName, Tuple[str, TypeKind]]) -> IXamlType:
        return self._provider.get_xaml_type(type)

    @override
    def get_xaml_type_by_full_name(self, full_name: str) -> IXamlType:
        return self._provider.get_xaml_type_by_full_name(full_name)

    @override
    def get_xmlns_definitions(self) -> Array[XmlnsDefinition]:
        return self._provider.get_xmlns_definitions()


def run_ui(entry_script: Path) -> int:
    def init(_params: ApplicationInitializationCallbackParams) -> None:
        App.startup_entry_script = entry_script
        App()

    with initialize(options=InitializeOptions.ON_NO_MATCH_SHOW_UI):
        Application.start(init)
    return 0
