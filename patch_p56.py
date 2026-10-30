from pathlib import Path

# 1. recipes.py
p_rec = Path("work/statcraft/statcraft/recipes.py")
rec_txt = p_rec.read_text(encoding="utf-8")
old_rec = "if action in ('two_sample_t', 'two_sample_proportion'):"
new_rec = "if action in ('two_sample_t', 'two_sample_proportion', 'two_sample_poisson'):"
assert old_rec in rec_txt
rec_txt = rec_txt.replace(old_rec, new_rec)
p_rec.write_text(rec_txt, encoding="utf-8")
print("recipes.py patched.")

# 2. app.py
p_app = Path("work/statcraft/statcraft/app.py")
app_txt = p_app.read_text(encoding="utf-8")

poisson_method = '''    def two_sample_poisson(self, settings=None):
        from .two_sample_poisson_engine import run_two_sample_poisson, two_sample_poisson_settings
        st = two_sample_poisson_settings(**(settings or {}))
        result = run_two_sample_poisson(self.worksheet, st)
        s1_name = result.get("sample1", {}).get("name", "Sample 1")
        s2_name = result.get("sample2", {}).get("name", "Sample 2")
        title = f"Test and CI for Two-Sample Poisson Rates: {s1_name}, {s2_name}" if st.get("data_format") != 2 else "Test and CI for Two-Sample Poisson Rates"
        recipe = {
            "action": "two_sample_poisson",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["two_sample_poisson"] = True
        return self._record(title, result, recipe=recipe)

'''
marker_app = "    def one_sample_poisson(self, settings=None):"
assert marker_app in app_txt
app_txt = app_txt.replace(marker_app, poisson_method + marker_app)

format_case = '''    if isinstance(result, dict) and (result.get("two_sample_poisson") is True or ("difference" in result and "sample1" in result and "sample2" in result and "sample_rate" in (result.get("sample1") or {}))):
        from .two_sample_poisson_report import format_two_sample_poisson_report
        return format_two_sample_poisson_report(entry)
'''
marker_fmt = '    if isinstance(result, dict) and (result.get("one_sample_poisson") is True or ("samples" in result and "length_of_observation" in result)):'
assert marker_fmt in app_txt
app_txt = app_txt.replace(marker_fmt, format_case + marker_fmt)

p_app.write_text(app_txt, encoding="utf-8")
print("app.py patched.")

# 3. modern_app.py
p_modern = Path("work/statcraft/statcraft/modern_app.py")
mod_txt = p_modern.read_text(encoding="utf-8")

menu_marker = 'self.one_sample_poisson_action = self._action(basic, "1-Sample Poisson Rate…", self.one_sample_poisson_dialog, None, None, True)'
menu_add = menu_marker + '\n        self.two_sample_poisson_action = self._action(basic, "2-Sample Poisson Rate…", self.two_sample_poisson_dialog, None, None, True)'
assert menu_marker in mod_txt
mod_txt = mod_txt.replace(menu_marker, menu_add)

dialog_method = '''    def two_sample_poisson_dialog(self):
        from .two_sample_poisson_dialogs import TwoSamplePoissonDialog
        self._commit_editor()
        self._last_dialog_action = self.two_sample_poisson_dialog
        dlg = TwoSamplePoissonDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload or dlg.settings
            if p:
                entry = self._call(lambda: self.presenter.two_sample_poisson(settings=p), result=True)
                if entry:
                    self.show_result(entry)

'''
dialog_marker = '    def one_sample_poisson_dialog(self):'
assert dialog_marker in mod_txt
mod_txt = mod_txt.replace(dialog_marker, dialog_method + dialog_marker)

p_modern.write_text(mod_txt, encoding="utf-8")
print("modern_app.py patched.")
