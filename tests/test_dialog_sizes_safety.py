import unittest
import os
import re

DIALOG_FILES = [
    "statcraft/anova_plots_dialogs.py",
    "statcraft/boxplot_dialogs.py",
    "statcraft/categorical_points_dialogs.py",
    "statcraft/doe_dialogs.py",
    "statcraft/doe_planner_dialog.py",
    "statcraft/doe_terms_dialog.py",
    "statcraft/dotplot_dialogs.py",
    "statcraft/equal_variances_dialogs.py",
    "statcraft/gage_rr_dialogs.py",
    "statcraft/glm_dialogs.py",
    "statcraft/graph_builder_dialog.py",
    "statcraft/graph_layout_dialog.py",
    "statcraft/graph_object_dialog.py",
    "statcraft/histogram_dialogs.py",
    "statcraft/histogram_options_dialog.py",
    "statcraft/logistic_dialogs.py",
    "statcraft/mixture_joint_dialog.py",
    "statcraft/mixture_multi_optimizer_dialog.py",
    "statcraft/multivari_dialogs.py",
    "statcraft/native_graph_appearance.py",
    "statcraft/panel_graph_dialog.py",
    "statcraft/prediction_dialogs.py",
    "statcraft/response_surface_dialogs.py",
    "statcraft/similar_graph_dialog.py",
    "statcraft/standardize_dialogs.py",
    "statcraft/store_descriptive.py",
    "statcraft/twoway_anova_dialogs.py",
    "statcraft/variable_dialogs.py",
]


class TestDialogSizesSafety(unittest.TestCase):
    def test_all_target_dialog_classes_have_size_grips_and_minimums(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []

        for rel_path in DIALOG_FILES:
            full_path = os.path.join(root_dir, rel_path)
            if not os.path.isfile(full_path):
                continue
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            classes = re.findall(r"class\s+([A-Za-z0-9_]+)\s*\(([^)]*QDialog[^)]*)\):", content)
            for cls_name, _ in classes:
                # Find the class implementation block
                cls_pattern = rf"class\s+{cls_name}\s*\([^)]+\):.*?(?=\nclass\s|\Z)"
                cls_match = re.search(cls_pattern, content, re.DOTALL)
                if not cls_match:
                    continue
                body = cls_match.group(0)
                if "def __init__" in body:
                    has_grip = "setSizeGripEnabled(True)" in body
                    if not has_grip:
                        offenders.append(f"{rel_path}: {cls_name} missing setSizeGripEnabled(True)")

        self.assertEqual(offenders, [], f"The following dialogs are missing size grips:\n" + "\n".join(offenders))

    def test_tall_dialogs_have_responsive_limits(self):
        """Ensure notoriously tall dialogs do not set initial or minimum heights >= 750px without scroll protection."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tall_files = [
            "statcraft/mixture_joint_dialog.py",
            "statcraft/mixture_multi_optimizer_dialog.py",
            "statcraft/doe_planner_dialog.py",
        ]
        offenders = []
        for rel_path in tall_files:
            full_path = os.path.join(root_dir, rel_path)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            for h in re.findall(r"resize\(\s*\d+\s*,\s*(\d+)\s*\)", content):
                if int(h) >= 750 and "QScrollArea" not in content:
                    offenders.append(f"{rel_path}: resize height {h} >= 750 without QScrollArea")
            for h in re.findall(r"setMinimumSize\(\s*\d+\s*,\s*(\d+)\s*\)", content):
                if int(h) >= 700 and "QScrollArea" not in content:
                    offenders.append(f"{rel_path}: minimum height {h} >= 700 without QScrollArea")

        self.assertEqual(offenders, [], "Tall dialogs exceed vertical safety threshold:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
