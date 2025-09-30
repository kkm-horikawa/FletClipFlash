import flet as ft
import pyperclip
import threading
import time
from datetime import datetime
from typing import List, Optional
import json
import os
import keyboard
import pystray
from PIL import Image, ImageDraw


class FavoriteItem:
    """お気に入りアイテム"""

    def __init__(self, text: str, hotkey: str = "", label: str = ""):
        self.text = text
        self.hotkey = hotkey
        self.label = label or text[:20]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "hotkey": self.hotkey,
            "label": self.label
        }

    @staticmethod
    def from_dict(data: dict) -> 'FavoriteItem':
        return FavoriteItem(
            text=data.get("text", ""),
            hotkey=data.get("hotkey", ""),
            label=data.get("label", "")
        )


class Settings:
    """設定を管理するクラス"""

    def __init__(self):
        self.config_file = "config.json"
        self.hotkey = "ctrl+shift+v"
        self.max_history = 100
        self.favorites: List[FavoriteItem] = []
        self.load_settings()

    def load_settings(self):
        """設定をファイルから読み込み"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.hotkey = config.get("hotkey", "ctrl+shift+v")
                    self.max_history = config.get("max_history", 100)
                    favorites_data = config.get("favorites", [])
                    self.favorites = [FavoriteItem.from_dict(item) for item in favorites_data]
        except Exception as e:
            print(f"設定読み込みエラー: {e}")

    def save_settings(self):
        """設定をファイルに保存"""
        try:
            config = {
                "hotkey": self.hotkey,
                "max_history": self.max_history,
                "favorites": [item.to_dict() for item in self.favorites]
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"設定保存エラー: {e}")


class ClipboardHistory:
    """クリップボード履歴を管理するクラス"""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.history: List[dict] = []
        self.load_history()

    def add(self, text: str) -> bool:
        """履歴に追加（重複チェック付き）"""
        if not text or not text.strip():
            return False

        # 直前と同じ内容なら追加しない
        if self.history and self.history[0]["text"] == text:
            return False

        entry = {
            "text": text,
            "timestamp": datetime.now().isoformat()
        }

        self.history.insert(0, entry)

        # 最大件数を超えたら古いものを削除
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]

        self.save_history()
        return True

    def get_all(self) -> List[dict]:
        """全履歴を取得"""
        return self.history

    def search(self, query: str) -> List[dict]:
        """履歴を検索"""
        if not query:
            return self.history

        query_lower = query.lower()
        return [entry for entry in self.history if query_lower in entry["text"].lower()]

    def clear(self):
        """履歴をクリア"""
        self.history = []
        self.save_history()

    def save_history(self):
        """履歴をファイルに保存"""
        try:
            with open("clipboard_history.json", "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"履歴保存エラー: {e}")

    def load_history(self):
        """履歴をファイルから読み込み"""
        try:
            if os.path.exists("clipboard_history.json"):
                with open("clipboard_history.json", "r", encoding="utf-8") as f:
                    self.history = json.load(f)
        except Exception as e:
            print(f"履歴読み込みエラー: {e}")
            self.history = []


class ClipboardMonitor:
    """クリップボードを監視するクラス"""

    def __init__(self, history: ClipboardHistory, callback):
        self.history = history
        self.callback = callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_clipboard = ""

    def start(self):
        """監視を開始"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """監視を停止"""
        self.running = False

    def _monitor_loop(self):
        """クリップボード監視ループ"""
        while self.running:
            try:
                current = pyperclip.paste()
                if current != self.last_clipboard:
                    self.last_clipboard = current
                    if self.history.add(current):
                        # UIの更新をメインスレッドに通知
                        self.callback()
            except Exception as e:
                print(f"クリップボード監視エラー: {e}")

            time.sleep(0.5)  # 0.5秒ごとにチェック


class FavoriteHotkeyManager:
    """お気に入りアイテム用のホットキー管理"""

    def __init__(self):
        self.registered_hotkeys: dict = {}  # {hotkey: callback}

    def register_favorite(self, hotkey: str, callback):
        """お気に入り用ホットキーを登録"""
        if hotkey in self.registered_hotkeys:
            self.unregister_favorite(hotkey)

        try:
            keyboard.add_hotkey(hotkey, callback)
            self.registered_hotkeys[hotkey] = callback
            print(f"お気に入りホットキー登録: {hotkey}")
        except Exception as e:
            print(f"お気に入りホットキー登録エラー ({hotkey}): {e}")

    def unregister_favorite(self, hotkey: str):
        """お気に入り用ホットキーを解除"""
        if hotkey not in self.registered_hotkeys:
            return

        try:
            keyboard.remove_hotkey(hotkey)
            del self.registered_hotkeys[hotkey]
        except Exception as e:
            print(f"お気に入りホットキー解除エラー ({hotkey}): {e}")

    def unregister_all(self):
        """すべてのお気に入りホットキーを解除"""
        for hotkey in list(self.registered_hotkeys.keys()):
            self.unregister_favorite(hotkey)


class HotkeyManager:
    """グローバルホットキーを管理するクラス"""

    def __init__(self, callback, hotkey: str = "ctrl+shift+v"):
        self.callback = callback
        self.hotkey = hotkey
        self.registered = False

    def register(self):
        """ホットキーを登録"""
        try:
            keyboard.add_hotkey(self.hotkey, self.callback)
            self.registered = True
            print(f"ホットキー登録: {self.hotkey}")
        except Exception as e:
            print(f"ホットキー登録エラー: {e}")

    def unregister(self):
        """ホットキーを解除"""
        if not self.registered:
            return
        try:
            keyboard.remove_hotkey(self.hotkey)
            self.registered = False
        except Exception as e:
            print(f"ホットキー解除エラー: {e}")

    def change_hotkey(self, new_hotkey: str):
        """ホットキーを変更"""
        self.unregister()
        self.hotkey = new_hotkey
        self.register()


class SystemTrayManager:
    """システムトレイを管理するクラス"""

    def __init__(self, on_show, on_quit):
        self.on_show = on_show
        self.on_quit = on_quit
        self.icon: Optional[pystray.Icon] = None

    def create_icon(self) -> pystray.Icon:
        """トレイアイコンを作成"""
        # シンプルなアイコン画像を生成
        image = Image.new('RGB', (64, 64), color='blue')
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill='white')

        menu = pystray.Menu(
            pystray.MenuItem("表示", self.on_show),
            pystray.MenuItem("終了", self.on_quit),
        )

        icon = pystray.Icon("FletClipFlash", image, "FletClipFlash", menu)
        return icon

    def start(self):
        """トレイアイコンを表示"""
        if self.icon is None:
            self.icon = self.create_icon()
            threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self):
        """トレイアイコンを停止"""
        if self.icon:
            self.icon.stop()


def main(page: ft.Page):
    """Fletアプリケーションのメイン関数"""

    # ページ設定
    page.title = "FletClipFlash"
    page.window.width = 600
    page.window.height = 800
    page.window.resizable = True
    page.window.skip_task_bar = False
    page.padding = 20

    # 設定管理
    settings = Settings()

    # クリップボード履歴管理
    clipboard_history = ClipboardHistory(max_history=settings.max_history)

    # お気に入りホットキー管理
    favorite_hotkey_manager = FavoriteHotkeyManager()

    # UI要素
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        expand=True,
    )

    search_field = ft.TextField(
        label="検索",
        hint_text="履歴を検索...",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
    )

    history_list = ft.ListView(
        spacing=5,
        padding=10,
        expand=True,
    )

    def update_history_list(entries: List[dict] = None):
        """履歴リストを更新"""
        if entries is None:
            entries = clipboard_history.get_all()

        history_list.controls.clear()

        for entry in entries:
            text = entry["text"]
            timestamp = datetime.fromisoformat(entry["timestamp"])
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            # 表示用テキスト（長い場合は省略）
            display_text = text if len(text) <= 100 else text[:100] + "..."

            def on_click(e, text=text):
                """クリック時にクリップボードにコピー"""
                pyperclip.copy(text)
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("クリップボードにコピーしました"),
                    duration=1000,
                )
                page.snack_bar.open = True
                page.update()

            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(display_text, size=14, weight=ft.FontWeight.W_400),
                        ft.Text(time_str, size=10, color=ft.Colors.GREY_500),
                    ], spacing=5),
                    padding=15,
                    on_click=on_click,
                ),
            )

            history_list.controls.append(card)

        page.update()

    def on_search_change(e):
        """検索フィールド変更時"""
        query = search_field.value
        results = clipboard_history.search(query)
        update_history_list(results)

    def on_clear_history(e):
        """履歴クリアボタン"""
        clipboard_history.clear()
        update_history_list()

    def on_clipboard_change():
        """クリップボード変更時のコールバック"""
        # 検索中でなければ履歴を更新
        if not search_field.value:
            update_history_list()

    search_field.on_change = on_search_change

    # クリップボード監視開始
    monitor = ClipboardMonitor(clipboard_history, on_clipboard_change)
    monitor.start()

    # ウィンドウの表示/非表示を管理
    def show_window():
        """ウィンドウを表示"""
        page.window.visible = True
        page.window.to_front()
        page.update()

    def hide_window():
        """ウィンドウを非表示"""
        page.window.visible = False
        page.update()

    def toggle_window():
        """ウィンドウの表示/非表示を切り替え"""
        if page.window.visible:
            hide_window()
        else:
            show_window()

    def on_quit():
        """アプリケーションを終了"""
        monitor.stop()
        hotkey_manager.unregister()
        favorite_hotkey_manager.unregister_all()
        tray_manager.stop()
        page.window.destroy()

    # システムトレイ設定
    tray_manager = SystemTrayManager(
        on_show=lambda: show_window(),
        on_quit=lambda: on_quit()
    )
    tray_manager.start()

    # グローバルホットキー設定
    hotkey_manager = HotkeyManager(callback=toggle_window, hotkey=settings.hotkey)
    hotkey_manager.register()

    # ウィンドウイベント処理
    def on_window_event(e):
        """ウィンドウイベント処理"""
        if e.data == "close":
            # ウィンドウを閉じる代わりに非表示にする
            hide_window()

    page.window.on_event = on_window_event
    page.window.prevent_close = True

    # お気に入りリスト
    favorites_list = ft.ListView(
        spacing=5,
        padding=10,
        expand=True,
    )

    def copy_to_clipboard_with_paste(text: str):
        """クリップボードにコピーして自動貼り付け"""
        pyperclip.copy(text)
        # Ctrl+Vをシミュレート
        time.sleep(0.1)
        keyboard.press_and_release('ctrl+v')

    def update_favorites_list():
        """お気に入りリストを更新"""
        favorites_list.controls.clear()

        for idx, fav in enumerate(settings.favorites):
            def on_fav_click(e, text=fav.text):
                """お気に入りクリック時"""
                copy_to_clipboard_with_paste(text)
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("コピー＆ペーストしました"),
                    duration=1000,
                )
                page.snack_bar.open = True
                hide_window()
                page.update()

            def on_delete_fav(e, index=idx):
                """お気に入り削除"""
                if 0 <= index < len(settings.favorites):
                    deleted_fav = settings.favorites[index]
                    # ホットキー解除
                    if deleted_fav.hotkey:
                        favorite_hotkey_manager.unregister_favorite(deleted_fav.hotkey)
                    # リストから削除
                    settings.favorites.pop(index)
                    settings.save_settings()
                    update_favorites_list()

            def on_edit_fav(e, index=idx):
                """お気に入り編集"""
                edit_favorite_dialog(index)

            card = ft.Card(
                content=ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(fav.label, size=14, weight=ft.FontWeight.W_500),
                            ft.Text(
                                fav.text[:50] + ("..." if len(fav.text) > 50 else ""),
                                size=12,
                                color=ft.Colors.GREY_600
                            ),
                            ft.Text(
                                f"ショートカット: {fav.hotkey}" if fav.hotkey else "ショートカット: 未設定",
                                size=10,
                                color=ft.Colors.BLUE_400 if fav.hotkey else ft.Colors.GREY_400
                            ),
                        ], expand=True, spacing=3),
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                icon_size=20,
                                tooltip="編集",
                                on_click=on_edit_fav,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                icon_size=20,
                                tooltip="削除",
                                on_click=on_delete_fav,
                            ),
                        ], spacing=0),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=12,
                    on_click=on_fav_click,
                ),
            )

            favorites_list.controls.append(card)

        page.update()

    def register_all_favorite_hotkeys():
        """すべてのお気に入りホットキーを登録"""
        for fav in settings.favorites:
            if fav.hotkey:
                def make_callback(text):
                    return lambda: copy_to_clipboard_with_paste(text)
                favorite_hotkey_manager.register_favorite(fav.hotkey, make_callback(fav.text))

    def edit_favorite_dialog(index: Optional[int] = None):
        """お気に入り編集ダイアログ"""
        is_new = index is None
        fav = None if is_new else settings.favorites[index]

        label_field = ft.TextField(
            label="ラベル",
            value=fav.label if fav else "",
            hint_text="例: メールアドレス、パスワード",
        )

        text_field = ft.TextField(
            label="テキスト",
            value=fav.text if fav else "",
            multiline=True,
            min_lines=3,
            max_lines=5,
        )

        # ホットキー入力用の状態管理
        recording = {"active": False, "keys": set()}

        hotkey_display = ft.TextField(
            label="ショートカットキー（任意）",
            value=fav.hotkey if fav else "",
            hint_text="「記録」ボタンを押してください",
            read_only=True,
            border_color=ft.Colors.BLUE_200,
            expand=True,
        )

        record_button = ft.ElevatedButton(
            "記録",
            icon=ft.Icons.KEYBOARD,
            on_click=None,  # 後で設定
            width=100,
        )

        def start_recording(e):
            """ホットキー記録開始"""
            if recording["active"]:
                return

            recording["active"] = True
            recording["keys"] = set()
            hotkey_display.value = "キーを押してください..."
            hotkey_display.border_color = ft.Colors.RED_400
            record_button.text = "停止"
            page.update()

            # キーボードイベントをキャプチャ
            def on_key_event(event):
                if not recording["active"]:
                    keyboard.unhook(on_key_event)
                    return False

                # 修飾キーと通常キーを記録
                key_name = event.name.lower()

                # 修飾キーのマッピング
                modifier_map = {
                    "ctrl": "ctrl",
                    "control": "ctrl",
                    "shift": "shift",
                    "alt": "alt",
                    "alt gr": "alt",
                    "left windows": "win",
                    "right windows": "win",
                    "windows": "win",
                }

                if key_name in modifier_map:
                    recording["keys"].add(modifier_map[key_name])
                    # 現在の組み合わせを表示
                    if recording["keys"]:
                        hotkey_display.value = "+".join(sorted(recording["keys"]))
                        page.update()
                elif len(key_name) == 1 or key_name in ["space", "tab", "esc", "backspace"] or key_name.startswith("f") and key_name[1:].isdigit():
                    # 通常のキーが押された場合、記録終了
                    if key_name == "esc":
                        # ESCでキャンセル
                        stop_recording(None)
                    else:
                        recording["keys"].add(key_name)
                        stop_recording()
                    return False

                return False  # イベントを通過させる

            # キーボードフックを登録
            keyboard.on_press(on_key_event)

        def stop_recording(final_key=None):
            """ホットキー記録停止"""
            if not recording["active"]:
                return

            recording["active"] = False

            try:
                keyboard.unhook_all()
            except:
                pass

            if final_key is None:
                # キャンセルされた
                hotkey_display.value = fav.hotkey if fav else ""
            elif recording["keys"]:
                # 修飾キーの順序を統一
                modifiers = []
                key = None

                for k in recording["keys"]:
                    if k in ["ctrl", "shift", "alt", "win"]:
                        modifiers.append(k)
                    else:
                        key = k

                # ctrl, shift, alt, winの順に並べる
                order = ["ctrl", "shift", "alt", "win"]
                sorted_modifiers = [m for m in order if m in modifiers]

                if key:
                    sorted_modifiers.append(key)

                if sorted_modifiers:
                    hotkey_str = "+".join(sorted_modifiers)
                    hotkey_display.value = hotkey_str
                else:
                    hotkey_display.value = fav.hotkey if fav else ""
            else:
                hotkey_display.value = fav.hotkey if fav else ""

            hotkey_display.border_color = ft.Colors.BLUE_200
            record_button.text = "記録"
            page.update()

        record_button.on_click = start_recording

        def save_favorite(e):
            """お気に入りを保存"""
            label = label_field.value.strip()
            text = text_field.value.strip()
            hotkey = hotkey_display.value.strip()

            if not text:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("テキストを入力してください"),
                    duration=2000,
                )
                page.snack_bar.open = True
                page.update()
                return

            # 既存のホットキーを解除
            if not is_new and fav.hotkey:
                favorite_hotkey_manager.unregister_favorite(fav.hotkey)

            new_fav = FavoriteItem(text=text, hotkey=hotkey, label=label or text[:20])

            if is_new:
                settings.favorites.append(new_fav)
            else:
                settings.favorites[index] = new_fav

            settings.save_settings()

            # 新しいホットキーを登録
            if hotkey:
                def make_callback(t):
                    return lambda: copy_to_clipboard_with_paste(t)
                favorite_hotkey_manager.register_favorite(hotkey, make_callback(text))

            update_favorites_list()
            fav_dialog.open = False
            page.update()

        def close_fav_dialog(e):
            # 記録中なら停止
            if recording["active"]:
                stop_recording(None)
            fav_dialog.open = False
            page.update()

        fav_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("お気に入りを編集" if not is_new else "お気に入りを追加"),
            content=ft.Container(
                width=500,
                content=ft.Column([
                    label_field,
                    text_field,
                    ft.Row([
                        hotkey_display,
                        record_button,
                    ], spacing=10),
                    ft.Text(
                        "※「記録」ボタンを押して、キーを組み合わせて入力\n  ESCキーでキャンセル",
                        size=10,
                        color=ft.Colors.GREY_500,
                    ),
                ], spacing=10, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[
                ft.TextButton("キャンセル", on_click=close_fav_dialog),
                ft.ElevatedButton("保存", on_click=save_favorite),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(fav_dialog)
        fav_dialog.open = True
        page.update()

    def add_favorite_from_history(text: str):
        """履歴からお気に入りに追加"""
        edit_favorite_dialog()
        # ダイアログが開いた後、テキストフィールドに値を設定
        # (この実装は簡略化のため省略。必要に応じて実装可能)

    # 設定ダイアログ
    hotkey_input = ft.TextField(
        label="ショートカットキー",
        value=settings.hotkey,
        hint_text="例: ctrl+shift+v, ctrl+alt+c",
    )

    def save_hotkey_settings(e):
        """ホットキー設定を保存"""
        new_hotkey = hotkey_input.value.strip()
        if new_hotkey and new_hotkey != settings.hotkey:
            try:
                # 新しいホットキーを適用
                hotkey_manager.change_hotkey(new_hotkey)
                settings.hotkey = new_hotkey
                settings.save_settings()

                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"ショートカットキーを {new_hotkey} に変更しました"),
                    duration=2000,
                )
                page.snack_bar.open = True
                settings_dialog.open = False
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"エラー: {ex}"),
                    duration=3000,
                )
                page.snack_bar.open = True
                page.update()

    def close_settings(e):
        """設定ダイアログを閉じる"""
        settings_dialog.open = False
        page.update()

    settings_dialog = ft.AlertDialog(
        title=ft.Text("設定"),
        content=ft.Column([
            hotkey_input,
            ft.Text(
                "※ショートカットキーの書式:\n"
                "  - 修飾キー: ctrl, shift, alt, win\n"
                "  - 組み合わせ: + で繋ぐ\n"
                "  - 例: ctrl+shift+v, ctrl+alt+h",
                size=12,
                color=ft.Colors.GREY_600,
            ),
        ], tight=True, spacing=10),
        actions=[
            ft.TextButton("キャンセル", on_click=close_settings),
            ft.ElevatedButton("保存", on_click=save_hotkey_settings),
        ],
    )

    def open_settings(e):
        """設定ダイアログを開く"""
        hotkey_input.value = settings.hotkey
        page.overlay.append(settings_dialog)
        settings_dialog.open = True
        page.update()

    # ヘッダー
    header = ft.Row([
        ft.Text("FletClipFlash", size=24, weight=ft.FontWeight.BOLD),
        ft.Row([
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                tooltip="設定",
                on_click=open_settings,
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_SWEEP,
                tooltip="履歴をクリア",
                on_click=on_clear_history,
            ),
        ]),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # タブ切り替え
    def on_tab_change(e):
        """タブ変更時"""
        if tabs.selected_index == 1:  # お気に入りタブ
            update_favorites_list()
        page.update()

    tabs.on_change = on_tab_change

    # タブコンテンツ
    history_tab = ft.Tab(
        text="履歴",
        icon=ft.Icons.HISTORY,
        content=ft.Container(
            content=ft.Column([
                search_field,
                history_list,
            ], expand=True, spacing=10),
            padding=ft.padding.only(top=10),
        ),
    )

    favorites_header = ft.Row([
        ft.Text("お気に入り", size=18, weight=ft.FontWeight.BOLD),
        ft.IconButton(
            icon=ft.Icons.ADD,
            tooltip="お気に入りを追加",
            on_click=lambda e: edit_favorite_dialog(),
        ),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    favorites_tab = ft.Tab(
        text="お気に入り",
        icon=ft.Icons.STAR,
        content=ft.Container(
            content=ft.Column([
                favorites_header,
                favorites_list,
            ], expand=True, spacing=10),
            padding=ft.padding.only(top=10),
        ),
    )

    tabs.tabs = [history_tab, favorites_tab]

    # レイアウト
    page.add(
        ft.Column([
            header,
            tabs,
        ], expand=True, spacing=10)
    )

    # 初期表示
    update_history_list()
    register_all_favorite_hotkeys()


if __name__ == "__main__":
    ft.app(target=main)