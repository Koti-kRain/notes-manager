import os
import json
import sqlite3
import flet as ft
from datetime import datetime

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    from config import SUPABASE_URL, SUPABASE_KEY
except ImportError:
    SUPABASE_URL = ""
    SUPABASE_KEY = ""


class StorageMode:
    SQLITE = "SQLite"
    FILES = "Files"
    CLOUD = "Облако (Supabase)"


class NotesApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.mode = StorageMode.SQLITE
        self.supabase = None

        if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_KEY:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            except Exception:
                self.supabase = None

        self.notes_list = ft.ListView(expand=True, padding=10, spacing=10)
        self.search_field = ft.TextField(
            label="Поиск",
            on_change=self.on_search,
            icon=ft.Icons.SEARCH,
        )

        dropdown_options = [
            ft.DropdownOption(key=StorageMode.SQLITE, text=StorageMode.SQLITE),
            ft.DropdownOption(key=StorageMode.FILES, text=StorageMode.FILES),
        ]
        if self.supabase is not None:
            dropdown_options.append(
                ft.DropdownOption(key=StorageMode.CLOUD, text=StorageMode.CLOUD)
            )

        self.mode_selector = ft.Dropdown(
            options=dropdown_options,
            value=StorageMode.SQLITE,
            width=220,
            on_select=self.on_mode_change,
        )

        self.status_text = ft.Text("Режим: SQLite", size=12, color=ft.Colors.GREY_600)

        self.title_field = ft.TextField(label="Заголовок")
        self.date_field = ft.TextField(label="Дата (ГГГГ-ММ-ДД)")
        self.time_field = ft.TextField(label="Время (ЧЧ:ММ)")
        self.content_field = ft.TextField(
            label="Содержание",
            multiline=True,
            min_lines=4,
            max_lines=10,
        )
        self.edit_id = None
        self.current_dialog = None

        self.setup_ui()
        self.load_notes()

    def setup_ui(self):
        self.page.title = "Notes Manager"
        self.page.add(
            ft.Column(
                [
                    ft.Row(
                        [self.mode_selector, self.status_text],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self.search_field,
                    self.notes_list,
                    ft.Button(
                        "Создать заметку",
                        icon=ft.Icons.ADD,
                        on_click=self.open_create_form,
                    ),
                ],
                expand=True,
            )
        )

    # --- SQLite ---
    def get_sqlite_conn(self):
        conn = sqlite3.connect("notes.db")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, date TEXT, time TEXT, content TEXT
            )"""
        )
        return conn

    def save_to_sqlite(self, note):
        conn = self.get_sqlite_conn()
        if self.edit_id:
            conn.execute(
                "UPDATE notes SET title=?, date=?, time=?, content=? WHERE id=?",
                (note["title"], note["date"], note["time"], note["content"], self.edit_id),
            )
        else:
            conn.execute(
                "INSERT INTO notes (title, date, time, content) VALUES (?, ?, ?, ?)",
                (note["title"], note["date"], note["time"], note["content"]),
            )
        conn.commit()
        conn.close()

    def delete_from_sqlite(self, note_id):
        conn = self.get_sqlite_conn()
        conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        conn.commit()
        conn.close()

    def load_from_sqlite(self):
        conn = self.get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, title, date, time, content FROM notes")
        rows = cur.fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "date": r[2], "time": r[3], "content": r[4]}
            for r in rows
        ]

    # --- Файлы ---
    def ensure_files_dir(self):
        if not os.path.exists("notes_data"):
            os.makedirs("notes_data")

    def load_index(self):
        self.ensure_files_dir()
        path = os.path.join("notes_data", "index.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"next_id": 1, "notes": []}

    def save_index(self, index):
        self.ensure_files_dir()
        path = os.path.join("notes_data", "index.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def save_note_file(self, note, note_id):
        self.ensure_files_dir()
        path = os.path.join("notes_data", f"note_{note_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(note, f, ensure_ascii=False, indent=2)

    def load_notes_files(self):
        index = self.load_index()
        result = []
        for n in index.get("notes", []):
            note_id = n["id"]
            file_path = os.path.join("notes_data", f"note_{note_id}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    note = json.load(f)
                note["id"] = note_id
                result.append(note)
        return result

    def add_note_to_index(self, note_id, title, date, time):
        index = self.load_index()
        index["notes"].append({"id": note_id, "title": title, "date": date, "time": time})
        index["next_id"] = index["next_id"] + 1
        self.save_index(index)

    def update_note_in_index(self, note_id, title, date, time):
        index = self.load_index()
        for n in index["notes"]:
            if n["id"] == note_id:
                n["title"] = title
                n["date"] = date
                n["time"] = time
                break
        self.save_index(index)

    def remove_note_from_index(self, note_id):
        index = self.load_index()
        index["notes"] = [n for n in index["notes"] if n["id"] != note_id]
        self.save_index(index)
        file_path = os.path.join("notes_data", f"note_{note_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)

    def save_to_files(self, note):
        index = self.load_index()
        note_id = index["next_id"]
        self.save_note_file(note, note_id)
        self.add_note_to_index(note_id, note["title"], note["date"], note["time"])

    def update_to_files(self, note_id, note):
        self.save_note_file(note, note_id)
        self.update_note_in_index(note_id, note["title"], note["date"], note["time"])

    def delete_from_files(self, note_id):
        self.remove_note_from_index(note_id)

    # --- Supabase ---
    def save_to_supabase(self, note):
        if self.edit_id:
            self.supabase.table("notes").update({
                "title": note["title"],
                "date": note["date"],
                "time": note["time"],
                "content": note["content"],
            }).eq("id", self.edit_id).execute()
        else:
            import time
            note_id = int(time.time() * 1000)
            self.supabase.table("notes").insert({
                "id": note_id,
                "title": note["title"],
                "date": note["date"],
                "time": note["time"],
                "content": note["content"],
            }).execute()
            self.edit_id = note_id

    def delete_from_supabase(self, note_id):
        self.supabase.table("notes").delete().eq("id", note_id).execute()

    def load_from_supabase(self):
        response = self.supabase.table("notes").select("*").execute()
        return [
            {
                "id": r["id"],
                "title": r.get("title", ""),
                "date": r.get("date", ""),
                "time": r.get("time", ""),
                "content": r.get("content", ""),
            }
            for r in response.data
        ]

    # --- UI ---
    def make_note_card(self, note):
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(note["title"], size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"{note['date']} {note['time']}",
                            size=14,
                            color=ft.Colors.GREY_400,
                        ),
                        ft.Divider(),
                        ft.Text(note["content"], size=14),
                        ft.Row(
                            [
                                ft.TextButton(
                                    "Изменить",
                                    icon=ft.Icons.EDIT,
                                    on_click=lambda e, n=note: self.open_edit_form(n),
                                ),
                                ft.TextButton(
                                    "Удалить",
                                    icon=ft.Icons.DELETE,
                                    on_click=lambda e, n=note: self.delete_note(n),
                                ),
                            ],
                        ),
                    ]
                ),
                padding=15,
            ),
            elevation=4,
            margin=5,
        )

    def load_notes(self):
        self.notes_list.controls.clear()
        try:
            if self.mode == StorageMode.SQLITE:
                notes = self.load_from_sqlite()
            elif self.mode == StorageMode.FILES:
                notes = self.load_notes_files()
            else:
                notes = self.load_from_supabase()
            for note in notes:
                self.notes_list.controls.append(self.make_note_card(note))
        except Exception as e:
            self.show_error(f"Ошибка загрузки: {e}")
        self.page.update()

    def on_search(self, e):
        query = e.control.value.lower()
        self.notes_list.controls.clear()
        try:
            if self.mode == StorageMode.SQLITE:
                all_notes = self.load_from_sqlite()
            elif self.mode == StorageMode.FILES:
                all_notes = self.load_notes_files()
            else:
                all_notes = self.load_from_supabase()
            for note in all_notes:
                text = f"{note['title']} {note['date']} {note['time']} {note['content']}".lower()
                if query in text:
                    self.notes_list.controls.append(self.make_note_card(note))
        except Exception as err:
            self.show_error(f"Ошибка поиска: {err}")
        self.page.update()

    def open_create_form(self, e):
        self.edit_id = None
        self.title_field.value = ""
        self.date_field.value = datetime.now().strftime("%Y-%m-%d")
        self.time_field.value = datetime.now().strftime("%H:%M")
        self.content_field.value = ""
        self.show_form_dialog()

    def open_edit_form(self, note):
        self.edit_id = note["id"]
        self.title_field.value = note["title"]
        self.date_field.value = note["date"]
        self.time_field.value = note["time"]
        self.content_field.value = note["content"]
        self.show_form_dialog()

    def show_form_dialog(self):
        dialog = ft.AlertDialog(
            title=ft.Text("Заметка"),
            content=ft.Column(
                [
                    self.title_field,
                    self.date_field,
                    self.time_field,
                    self.content_field,
                ],
                spacing=10,
                tight=True,
            ),
            actions=[
                ft.TextButton("Отмена", on_click=self.cancel_form),
                ft.Button("Сохранить", on_click=self.save_form),
            ],
        )
        self.current_dialog = dialog
        self.page.show_dialog(dialog)

    def cancel_form(self, e):
        if self.current_dialog:
            self.page.pop_dialog()
            self.current_dialog = None

    def save_form(self, e):
        note = {
            "title": self.title_field.value or "",
            "date": self.date_field.value or "",
            "time": self.time_field.value or "",
            "content": self.content_field.value or "",
        }
        if not note["title"].strip():
            self.show_error("Заголовок обязателен!")
            return
        try:
            if self.mode == StorageMode.SQLITE:
                self.save_to_sqlite(note)
            elif self.mode == StorageMode.FILES:
                if self.edit_id is None:
                    self.save_to_files(note)
                else:
                    self.update_to_files(self.edit_id, note)
            else:
                self.save_to_supabase(note)
            if self.current_dialog:
                self.page.pop_dialog()
                self.current_dialog = None
            self.load_notes()
            self.show_snack("Сохранено!")
        except Exception as err:
            self.show_error(f"Ошибка сохранения: {err}")

    def delete_note(self, note):
        def do_delete(e):
            try:
                if self.mode == StorageMode.SQLITE:
                    self.delete_from_sqlite(note["id"])
                elif self.mode == StorageMode.FILES:
                    self.delete_from_files(note["id"])
                else:
                    self.delete_from_supabase(note["id"])
                self.page.pop_dialog()
                self.load_notes()
                self.show_snack("Удалено!")
            except Exception as err:
                self.page.pop_dialog()
                self.show_error(f"Ошибка удаления: {err}")

        confirm_dialog = ft.AlertDialog(
            title=ft.Text("Удалить заметку?"),
            content=ft.Text(f"Удалить «{note['title']}»?"),
            actions=[
                ft.TextButton("Нет", on_click=lambda ev: self.page.pop_dialog()),
                ft.Button("Да", on_click=do_delete),
            ],
        )
        self.page.show_dialog(confirm_dialog)

    def on_mode_change(self, e):
        self.mode = e.control.value
        self.status_text.value = f"Режим: {self.mode}"
        self.load_notes()

    def show_error(self, msg):
        self.page.show_dialog(ft.SnackBar(ft.Text(msg, color=ft.Colors.RED_400)))

    def show_snack(self, msg):
        self.page.show_dialog(ft.SnackBar(ft.Text(msg)))


def main(page: ft.Page):
    NotesApp(page)

ft.run(main)
