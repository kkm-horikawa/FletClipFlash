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


class HotkeyManager:
    """グローバルホットキーを管理するクラス"""

    def __init__(self, callback):
        self.callback = callback
        self.hotkey = "ctrl+shift+v"  # デフォルトホットキー

    def register(self):
        """ホットキーを登録"""
        try:
            keyboard.add_hotkey(self.hotkey, self.callback)
            print(f"ホットキー登録: {self.hotkey}")
        except Exception as e:
            print(f"ホットキー登録エラー: {e}")

    def unregister(self):
        """ホットキーを解除"""
        try:
            keyboard.remove_hotkey(self.hotkey)
        except Exception as e:
            print(f"ホットキー解除エラー: {e}")


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

    # クリップボード履歴管理
    clipboard_history = ClipboardHistory(max_history=100)

    # UI要素
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
        tray_manager.stop()
        page.window.destroy()

    # システムトレイ設定
    tray_manager = SystemTrayManager(
        on_show=lambda: show_window(),
        on_quit=lambda: on_quit()
    )
    tray_manager.start()

    # グローバルホットキー設定 (Ctrl+Shift+V)
    hotkey_manager = HotkeyManager(callback=toggle_window)
    hotkey_manager.register()

    # ウィンドウイベント処理
    def on_window_event(e):
        """ウィンドウイベント処理"""
        if e.data == "close":
            # ウィンドウを閉じる代わりに非表示にする
            hide_window()

    page.window.on_event = on_window_event
    page.window.prevent_close = True

    # ヘッダー
    header = ft.Row([
        ft.Text("クリップボード履歴", size=24, weight=ft.FontWeight.BOLD),
        ft.IconButton(
            icon=ft.Icons.DELETE_SWEEP,
            tooltip="履歴をクリア",
            on_click=on_clear_history,
        ),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # レイアウト
    page.add(
        ft.Column([
            header,
            search_field,
            history_list,
        ], expand=True, spacing=10)
    )

    # 初期表示
    update_history_list()


if __name__ == "__main__":
    ft.app(target=main)