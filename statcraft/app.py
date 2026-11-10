"""Original StatCraft desktop source and a GUI-independent document presenter.

Only implemented calculations appear as actions. This source neither packages an
executable nor asserts complete compatibility with another application.
"""
import json
import math
import copy
import csv
import io as text_io
import sys
from functools import wraps
from datetime import datetime
from pathlib import Path
from . import engine
from .model import Column, Matrix, Worksheet, finite_number, datetime_to_serial, serial_to_datetime, display_date
from . import io


def undoable(method):
    """Record only completed edits; preserve the worksheet object used by a project."""
    @wraps(method)
    def edit(self, *args, **kwargs):
        if getattr(self,'_edit_depth',0):
            return method(self,*args,**kwargs)
        target = self.worksheet
        before = copy.deepcopy(target)
        old_columns=list(target.columns)
        structural=method.__name__ in ('insert_columns','move_columns','delete_columns')
        from .recipe_columns import capture,remap,restore as restore_recipe
        recipe_changes=capture(self,target) if structural else []
        others=[(sheet,copy.deepcopy(sheet)) for sheet in self.native_project.worksheets if sheet is not target] if method.__name__=='calculate_all_formulas' and self.native_project else []
        history_before=list(self.history)
        dirty_before=(self._document_dirty,self._results_dirty)
        before_revision = self._revision
        self._edit_depth=1
        try:
            result = method(self, *args, **kwargs)
            from .formulas import refresh_after_edit,remap_references
            if method.__name__ in ('insert_columns','move_columns','delete_columns'):
                remap_references(target,old_columns)
            refresh_after_edit(target,before,self.auto_calculate_formulas)
            if structural:
                recipe_changes=remap(recipe_changes,old_columns,target.columns)
                if recipe_changes:self._results_dirty=True
        except Exception:
            for sheet,snapshot in [(target,before)]+others:
                sheet.__dict__.clear();sheet.__dict__.update(snapshot.__dict__)
            self.history[:]=history_before
            for change in recipe_changes: restore_recipe(change['entry'],change['before'])
            self._document_dirty,self._results_dirty=dirty_before
            raise
        finally:
            self._edit_depth=0
        if target != before or recipe_changes or any(sheet!=snapshot for sheet,snapshot in others):
            self._next_revision += 1
            self._revision = self._next_revision
            self._undo_stack.append({"target": target, "before": before, "after": copy.deepcopy(target),
                "before_revision": before_revision, "after_revision": self._revision, "action": method.__name__,
                "recipe_changes":recipe_changes,
                "column_index_map":{i:next(j for j,c in enumerate(target.columns) if c is old) for i,old in enumerate(old_columns) if any(c is old for c in target.columns)} if structural else None,
                "related":[{"target":sheet,"before":snapshot,"after":copy.deepcopy(sheet)} for sheet,snapshot in others]})
            self._undo_stack = self._undo_stack[-20:]
            self._redo_stack.clear()
        self.dirty = self._revision != self._saved_revision
        return result
    return edit


class Presenter:
    """Pure document/actions layer, testable without a desktop or Tk interpreter."""
    def __init__(self):
        self.auto_calculate_formulas=True
        self._results_dirty = False
        self.worksheet = Worksheet("Untitled", [Column("C1")])
        from .connect import ensure_worksheet_identities
        ensure_worksheet_identities(self.worksheet)
        self.project_path = None
        self.dirty = False
        self.history = []
        self.workspace = None
        self.notices = []
        self.native_project = None
        self._reset_edits()

    @property
    def worksheets(self):
        if self.native_project is not None and getattr(self.native_project, 'worksheets', None):
            return self.native_project.worksheets
        return [self.worksheet]

    @property
    def dirty(self):
        return self._document_dirty or self._results_dirty

    @dirty.setter
    def dirty(self, value):
        self._document_dirty = bool(value)

    def _reset_edits(self):
        self._undo_stack = []
        self._redo_stack = []
        self._revision = self._saved_revision = self._next_revision = 0

    @property
    def can_undo(self):
        return bool(self._undo_stack)

    @property
    def can_redo(self):
        return bool(self._redo_stack)

    def _restore_edit(self, command, key):
        if 'entry' in command:
            value=copy.deepcopy(command[key]);entry=command['entry'];field=command['field']
            if value is None:entry.pop(field,None)
            else:entry[field]=value
            self._revision=command[key+'_revision'];self._results_dirty=True
            self.dirty=self._revision!=self._saved_revision
            return
        target = command["target"]
        if command.get('column_index_map') is not None:
            from .recipe_columns import capture,remap_mapping
            known={id(change['entry']) for change in command.get('recipe_changes',[])}
            new_entries=[change for change in capture(self,target) if id(change['entry']) not in known]
            mapping=command['column_index_map']
            if key=='before':mapping={new:old for old,new in mapping.items()}
            additions=remap_mapping(new_entries,mapping)
            if key=='before':
                for change in additions:change['before'],change['after']=change['after'],change['before']
            command.setdefault('recipe_changes',[]).extend(additions)
        restored = copy.deepcopy(command[key])
        target.__dict__.clear()
        target.__dict__.update(restored.__dict__)
        for related in command.get('related',[]):
            restored_related=copy.deepcopy(related[key])
            related['target'].__dict__.clear();related['target'].__dict__.update(restored_related.__dict__)
        from .recipe_columns import restore as restore_recipe
        for change in command.get('recipe_changes',[]):
            restore_recipe(change['entry'],change[key])
        if command.get('recipe_changes'):self._results_dirty=True
        self.worksheet = target
        if self.native_project is not None:
            self.native_project.active_index = next(i for i, sheet in enumerate(self.native_project.worksheets) if sheet is target)
        self._revision = command[key + "_revision"]
        self.dirty = self._revision != self._saved_revision

    def undo(self):
        if not self._undo_stack:
            return False
        command = self._undo_stack.pop()
        self._restore_edit(command, "before")
        self._redo_stack.append(command)
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        command = self._redo_stack.pop()
        self._restore_edit(command, "after")
        self._undo_stack.append(command)
        return True

    def new(self):
        self._results_dirty = False
        self.history = []
        self.workspace = None
        self.worksheet = Worksheet("Untitled", [Column("C1")])
        self.project_path = None
        self.dirty = False
        self.notices = []
        self.native_project = None
        self._reset_edits()

    def reorder_worksheets(self, from_idx, to_idx):
        if self.native_project is None:
            return
        sheets = self.native_project.worksheets
        if not (0 <= from_idx < len(sheets) and 0 <= to_idx < len(sheets)):
            return
        item = sheets.pop(from_idx)
        sheets.insert(to_idx, item)
        self.native_project.active_index = to_idx
        self.worksheet = sheets[to_idx]
        self.dirty = True

    def select_worksheet(self, index):
        if self.native_project is None:
            if index != 0:
                raise ValueError("This document contains one worksheet.")
            return
        if type(index) is not int or not 0 <= index < len(self.native_project.worksheets):
            raise ValueError("Choose an existing project worksheet.")
        self.native_project.active_index = index
        self.worksheet = self.native_project.worksheets[index]

    def _worksheet_name(self,name):
        if not isinstance(name,str) or not name or name!=name.strip() or len(name)>128:
            raise ValueError('Use a worksheet name of 1–128 characters without leading or trailing blanks.')
        names=[s.name.casefold() for s in self.native_project.worksheets] if self.native_project else [self.worksheet.name.casefold()]
        if name.casefold() in names:raise ValueError('A worksheet with that name already exists.')
        return name

    def _owned_project(self):
        if self.native_project is not None:
            if not getattr(self.native_project,'statcraft_owned',False):
                raise ValueError('Worksheet structure changes are currently supported in projects created by StatCraft. Imported native projects retain their existing worksheets.')
            return self.native_project
        from .mpx_create import create_project
        project=create_project([self.worksheet])
        for entry in self.history:
            if entry.get('origin')=='statcraft':entry['worksheet_id']=project.worksheet_ids[0]
        self.native_project=project
        self.worksheet=project.active_worksheet
        self.project_path=None
        return project

    def add_worksheet(self,name=None):
        if name is None:
            names={s.name.casefold() for s in self.native_project.worksheets} if self.native_project else {self.worksheet.name.casefold()}
            number=1
            while ('Worksheet '+str(number)).casefold() in names:number+=1
            name='Worksheet '+str(number)
        self._worksheet_name(name)
        project=self._owned_project()
        from uuid import uuid4
        worksheet=Worksheet(name,[Column('C'+str(i),metadata={'auto_type':True}) for i in range(1,17)])
        identifier=str(uuid4());suffix=0
        while '/sheets/'+str(suffix)+'/sheet' in project.worksheet_uris:suffix+=1
        project.worksheets.append(worksheet);project.worksheet_ids.append(identifier);project.worksheet_uris.append('/sheets/'+str(suffix)+'/sheet')
        project.active_index=len(project.worksheets)-1;self.worksheet=worksheet
        self.dirty=True;self._results_dirty=True;self._reset_edits()
        return worksheet

    def rename_worksheet(self,name):
        if name==self.worksheet.name:return
        self._worksheet_name(name)
        if self.native_project is None:
            self.worksheet.name=name
            for entry in self.history:
                if entry.get('worksheet_id') is None:entry['worksheet_name']=name
            self.dirty=True
            return
        project=self._owned_project();self.worksheet.name=name
        for entry in self.history:
            if entry.get('worksheet_id')==project.worksheet_ids[project.active_index]:entry['worksheet_name']=name
        self.dirty=True;self._results_dirty=True

    def duplicate_worksheet(self,name=None):
        name=name or self.worksheet.name+' Copy';self._worksheet_name(name)
        original=copy.deepcopy(self.worksheet)
        worksheet=self.add_worksheet(name)
        worksheet.columns=original.columns;worksheet.constants=original.constants;worksheet.matrices=original.matrices;worksheet.metadata=original.metadata
        return worksheet

    def delete_worksheet(self):
        if self.native_project is None or len(self.native_project.worksheets)<2:
            raise ValueError('Keep at least one worksheet in the project.')
        project=self._owned_project();index=project.active_index
        identifier=project.worksheet_ids[index]
        del project.worksheets[index];del project.worksheet_ids[index];del project.worksheet_uris[index]
        project.active_index=min(index,len(project.worksheets)-1)
        self.worksheet=project.active_worksheet
        self.history=[e for e in self.history if e.get('worksheet_id')!=identifier]
        self.dirty=True;self._results_dirty=True;self._reset_edits()
        return True

    def load(self, path, column_types=None):
        suffix = Path(path).suffix.lower()
        native_project = None
        native_outputs = []
        if suffix == ".mpx":
            from .mpx import load_mpx
            native_project = load_mpx(path)
            worksheet = native_project.active_worksheet
            from .native_mpx_outputs import read_outputs
            from .native_mpx_models import read_native_models
            from .native_output_state import apply as apply_native_views
            native_outputs = read_outputs(native_project.metadata, native_project.retained_members)
            apply_native_views(native_outputs,native_project.native_views)
            recovered = read_native_models(native_project)
            for entry in native_outputs:
                descriptor = recovered.get(entry.get('native_command_id'))
                if descriptor is not None:entry['native_model']=copy.deepcopy(descriptor)
            project_path = str(path) if getattr(native_project,'statcraft_owned',False) else None
        elif suffix == ".statcraft":
            worksheet = io.load_project(path)
            project_path = str(path)
        elif suffix in (".csv", ".tsv", ".tab"):
            worksheet = io.load_csv(path, column_types=column_types)
            project_path = None
        elif suffix == ".mwx":
            worksheet = io.load_mwx(path)
            project_path = None
        elif suffix in (".jmp", ".jsl"):
            from .jmp_reader import load_jmp
            from .mpx_create import create_project
            worksheet = load_jmp(path)
            native_project = create_project([worksheet])
            native_project.statcraft_owned = True
            project_path = None
        else:
            raise io.UnsupportedFormatError("Open an .mpx project, .statcraft, .csv, .tsv, supported .mwx, or .jmp/.jsl file.")
        # Replace the active document only after the complete import succeeds.
        self.worksheet = worksheet
        self.native_project = native_project
        self.workspace = copy.deepcopy(native_project.workspace) if native_project else copy.deepcopy(worksheet.metadata.get("statcraft_workspace"))
        self.project_path = project_path
        self.history = []
        self._results_dirty = False
        self.dirty = False
        self._reset_edits()
        self.notices = list(worksheet.metadata.get("import", {}).get("warnings", []))
        if native_project is not None:
            self.history = []
            self.notices = list(native_project.warnings) + ["MPX project opened with all supported worksheets. Original archive contents are retained.",
                            "Supported saved native reports and graphs are displayed from their stored values. Native commands are never executed. Supported recovered model setups can be explicitly refitted with StatCraft.",
                            "MPX Save Copy supports same-size edits, typed numeric row growth on plain worksheets, and independent numeric-column append. Text/date resizing, native worksheet/model structure and type changes remain unsupported.",
                            "StatCraft results are saved in a separate session record inside MPX copies. This is independent of native output encoding; native application reopening remains unverified."]
            if native_project.history and not native_outputs:
                self._record("Project command history", {"commands": native_project.history}, persist=False)
                for index, command in enumerate(native_project.history[-80:], max(1, len(native_project.history) - 79)):
                    self._record("Native command " + str(index), {"command": command, "source": "Retained project history; not executed."}, persist=False)
            self.history = (self.history + native_outputs + copy.deepcopy(native_project.session_records))[-100:]
            if suffix in (".jmp", ".jsl"):
                self.notices = ["JMP data table auto-converted to Minitab project. Full Minitab statistical procedures, multiple worksheets, and .MPX saving are enabled."]
            elif getattr(native_project, 'statcraft_owned', False):
                self.notices = ['StatCraft-authored MPX project: worksheet data, design metadata and saved StatCraft analyses are editable. Native application compatibility remains unverified.']
        if suffix in (".csv", ".tsv", ".tab") and column_types is None:
            self.notices.append("Column types were inferred. Numeric-looking labels become numeric; use explicit text types when preparing data.")
        return self.notices

    def save(self, path=None):
        path = path or self.project_path
        if not path:
            raise ValueError("Choose a StatCraft project destination.")
        if self.native_project is not None:
            if Path(path).suffix.lower() != ".mpx":
                raise io.UnsupportedFormatError("Save this multi-worksheet project as an MPX copy; saving one worksheet would discard project contents.")
            from .mpx import save_mpx
            records = [copy.deepcopy(entry) for entry in self.history if entry.get("origin") == "statcraft"]
            self.native_project.workspace=copy.deepcopy(self.workspace)
            from .native_output_state import capture as capture_native_views
            self.native_project.native_views=capture_native_views(self.history)
            save_mpx(self.native_project, path, session_records=records)
            self.native_project.session_records = records
            self.project_path = str(path)
            self.dirty = False
            self._results_dirty = False
            self._saved_revision = self._revision
            return
        if Path(path).suffix.lower()=='.mpx':
            # Construct and publish a complete owned project before changing document mode.
            from .mpx_create import create_project,save_owned
            project=create_project([self.worksheet])
            project.workspace=copy.deepcopy(self.workspace)
            records=copy.deepcopy([entry for entry in self.history if entry.get('origin')=='statcraft'])
            for entry in records:entry['worksheet_id']=project.worksheet_ids[0]
            save_owned(project,path,records)
            entries=[entry for entry in self.history if entry.get('origin')=='statcraft']
            for entry in entries:entry['worksheet_id']=project.worksheet_ids[0]
            self.native_project=project;self.worksheet=project.active_worksheet;project.session_records=records;self.history=entries
            self._reset_edits();self.project_path=str(path);self.dirty=False;self._results_dirty=False
            return
        if Path(path).suffix.lower() != ".statcraft":
            raise ValueError("Projects use the .statcraft extension.")
        if self.workspace is not None:self.worksheet.metadata["statcraft_workspace"]=copy.deepcopy(self.workspace)
        io.save_project(self.worksheet, path)
        self.project_path = str(path)
        self.dirty = False
        self._saved_revision = self._revision

    def export_excel(self,path,all_worksheets=True):
        if type(all_worksheets) is not bool:raise ValueError('Choose current worksheet or all worksheets.')
        from .xlsx_export import write_workbook
        sheets=self.native_project.worksheets if all_worksheets and self.native_project else [self.worksheet]
        return write_workbook(path,sheets,protected_paths=[self.project_path] if self.project_path else [])

    def create_doe_plan(self,**parameters):
        from .doe_planner import build_plan,summarize
        from .data_prep import store_prepared
        sheet=build_plan(**parameters)
        # Complete validation before changing this project. Name conflicts get a new tab.
        used={s.name.casefold() for s in self.native_project.worksheets} if self.native_project else {self.worksheet.name.casefold()}
        base=sheet.name;number=2
        while sheet.name.casefold() in used:
            suffix=' ('+str(number)+')';sheet.name=base[:128-len(suffix)]+suffix;number+=1
        store_prepared(self,sheet,'worksheet')
        self.worksheet.metadata=copy.deepcopy(sheet.metadata)
        return self._record('DOE Plan: '+sheet.name,summarize(sheet))

    def export_notices(self):
        notices = ["Delimited export includes the column table only. Column types, metadata and unequal column lengths are not retained."]
        if self.worksheet.constants or self.worksheet.matrices:
            notices.append("Constants and matrices are excluded. Save a project to retain them.")
        if any(c.kind == "date" for c in self.worksheet.columns):
            notices.append("Dates are exported as serial numbers; their date type is not retained.")
        return notices

    def export(self, path):
        if Path(path).suffix.lower() not in (".csv", ".tsv", ".tab"):
            raise ValueError("Delimited exports use .csv or .tsv.")
        # Export deliberately does not clear unsaved project changes.
        return io.save_csv(self.worksheet, path)

    @staticmethod
    def parse_cell(raw, kind):
        if kind == "text":
            return raw
        s = raw.strip()
        if s in ("", "*") or s.lower() in ("na", "n/a", "nan", "none", ".", "-"):
            return None
        if kind == "date":
            try:
                value = finite_number(float(raw))
            except ValueError:
                value = datetime_to_serial(datetime.fromisoformat(raw.strip()))
            serial_to_datetime(value)
            return value
        if kind != "number":
            raise ValueError("Unsupported column type.")
        value = finite_number(float(raw))
        return engine.normalize_numeric(value)

    @undoable
    def set_cell(self, row, column, raw):
        if type(row) is not int or row < 0 or row >= io.MAX_CELLS:
            raise ValueError("Row is outside the editable range.")
        if not 0 <= column < len(self.worksheet.columns):
            raise ValueError("Select an existing column.")
        col = self.worksheet.columns[column]
        if col.metadata.get('formula') and self.auto_calculate_formulas:
            raise ValueError('C'+str(column+1)+' is calculated. Remove its formula or turn off automatic calculation before editing its cells.')
        kind = col.kind
        s = raw.strip()
        if kind != "text" and s.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity", "+infinity"):
            raise ValueError("Nonfinite cells are unsupported; use None or * for missing data.")
        is_missing = s in ("", "*") or s.lower() in ("na", "n/a", "none", ".", "-")
        if kind == 'number' and col.metadata.get('auto_type') and not is_missing:
            try:
                float(raw)
            except ValueError:
                kind = 'text'
                col.values = [str(int(v)) if (isinstance(v, float) and v.is_integer()) else (str(v) if v is not None else None) for v in col.values]
        value = self.parse_cell(raw, kind)
        if (row + 1) * len(self.worksheet.columns) > io.MAX_CELLS:
            raise ValueError("The worksheet exceeds the cell limit.")
        while len(col.values) <= row:
            col.values.append(None)
        col.kind=kind
        col.values[row] = value
        self.dirty = True

    @undoable
    def add_column(self, name, kind="number"):
        if not name.strip():
            raise ValueError("Enter a column name.")
        column = Column(name.strip(), kind, [None] * self.worksheet.row_count)
        if len(self.worksheet.columns) + 1 > io.MAX_CELLS // max(1, self.worksheet.row_count):
            raise ValueError("The worksheet exceeds the cell limit.")
        self.worksheet.columns.append(column)
        self.dirty = True

    @undoable
    def rename_column(self, index, name):
        if not name.strip():
            raise ValueError("Enter a column name.")
        self.worksheet.columns[index].name = name.strip()
        self.dirty = True

    @undoable
    def rename_columns(self, start, names):
        if type(start) is not int or start<0 or not names or start+len(names)>len(self.worksheet.columns):
            raise ValueError("Paste names into existing columns only.")
        if any(not isinstance(name,str) for name in names): raise ValueError("Column names must be text.")
        for index,name in enumerate(names,start):
            self.worksheet.columns[index].name=name.strip() or "C"+str(index+1)
        self.dirty=True

    @undoable
    def add_rows(self, count=1):
        if type(count) is not int or count < 1:
            raise ValueError("Enter a positive row count.")
        rows = self.worksheet.row_count + count
        if not self.worksheet.columns:
            raise ValueError("Add a column before adding rows.")
        if self.native_project is not None and all(c.metadata.get('unsupported_native_storage')=='untyped-empty-v0' for c in self.worksheet.columns):
            raise ValueError('Initializing empty native placeholder columns is unsupported. Add a typed column first.')
        if rows * len(self.worksheet.columns) > io.MAX_CELLS:
            raise ValueError("The worksheet exceeds the cell limit.")
        for col in self.worksheet.columns:
            if self.native_project is not None and col.metadata.get('unsupported_native_storage')=='untyped-empty-v0':
                continue  # Keep retained native placeholders uninitialized.
            col.values.extend([None] * (rows - len(col.values)))
        self.dirty = True

    @undoable
    def paste(self, row, column, text):
        """Paste a rectangular tab-separated block transactionally, preserving types."""
        if type(row) is not int or type(column) is not int or row < 0 or column < 0:
            raise ValueError("Select a valid paste destination.")
        try:
            rows = list(csv.reader(text_io.StringIO(text, newline=""), delimiter="\t", strict=True))
        except csv.Error as exc:
            raise ValueError("Invalid clipboard table: " + str(exc)) from exc
        if not rows:
            return
        width = len(rows[0])
        if not width or any(len(r) != width for r in rows):
            raise ValueError("Clipboard rows must have equal numbers of cells.")

        # Smart Header Detection: If row == 0 and top row is headers, extract them
        headers = None
        if row == 0 and len(rows) >= 2:
            header_candidates = []
            for c_idx in range(width):
                val_0 = rows[0][c_idx].strip()
                is_num_0 = False
                try:
                    if val_0 not in ("", "*", "NA", "N/A", "nan", "NaN"):
                        finite_number(float(val_0))
                        is_num_0 = True
                except ValueError:
                    is_num_0 = False

                has_num_rest = False
                for r_idx in range(1, len(rows)):
                    val_r = rows[r_idx][c_idx].strip()
                    try:
                        if val_r not in ("", "*", "NA", "N/A", "nan", "NaN"):
                            finite_number(float(val_r))
                            has_num_rest = True
                            break
                    except ValueError:
                        pass
                if not is_num_0 and has_num_rest:
                    header_candidates.append(c_idx)

            if header_candidates:
                headers = [r.strip() for r in rows[0]]
                rows = rows[1:]

        if self.auto_calculate_formulas:
            for index in range(column,min(column+width,len(self.worksheet.columns))):
                if self.worksheet.columns[index].metadata.get('formula'):
                    raise ValueError('C'+str(index+1)+' is calculated. Remove its formula or turn off automatic calculation before pasting into it.')
        count = max(len(self.worksheet.columns), column + width)
        height = max(self.worksheet.row_count, row + len(rows))
        if count * height > io.MAX_CELLS:
            raise ValueError("The pasted worksheet exceeds the cell limit.")
        columns = copy.deepcopy(self.worksheet.columns)
        while len(columns) < count:
            index = len(columns)
            raw = [r[index - column] for r in rows] if index >= column else []
            try:
                for value in raw:
                    if value.strip() not in ("", "*", "NA", "N/A", "nan", "NaN"):
                        finite_number(float(value))
                kind = "number"
            except ValueError:
                kind = "text"
            col_name = headers[index - column] if (headers and index >= column and headers[index - column]) else ("C" + str(index + 1))
            columns.append(Column(col_name, kind))
        for position in range(width):
            col = columns[column + position]
            if headers is not None and headers[position]:
                col.name = headers[position]
            if all(v is None for v in col.values):
                try:
                    for cells in rows:
                        if cells[position].strip() not in ("", "*", "NA", "N/A", "nan", "NaN"):
                            finite_number(float(cells[position]))
                    col.kind = "number"
                except ValueError:
                    col.kind = "text"
        for offset, cells in enumerate(rows):
            for position, raw in enumerate(cells):
                col = columns[column + position]
                value = self.parse_cell(raw, col.kind)
                while len(col.values) <= row + offset:
                    col.values.append(None)
                col.values[row + offset] = value
        self.worksheet.columns = columns
        self.dirty = True

    def copy_block(self, first_row, last_row, first_column, last_column):
        if min(first_row, last_row, first_column, last_column) < 0:
            raise ValueError("Invalid clipboard selection.")
        if last_column >= len(self.worksheet.columns) or first_column > last_column or first_row > last_row:
            raise ValueError("Select an existing cell block.")
        stream = text_io.StringIO(newline="")
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        for row in range(first_row, last_row + 1):
            cells = []
            for column in range(first_column, last_column + 1):
                col = self.worksheet.columns[column]
                value = col.values[row] if row < len(col.values) else None
                cells.append("" if value is None else display_date(value) if col.kind=='date' else value)
            writer.writerow(cells)
        return stream.getvalue()

    @undoable
    def set_column_type(self, index, kind):
        col = self.worksheet.columns[index]
        converted = [None if v is None else self.parse_cell(str(v), kind) for v in col.values]
        replacement = Column(col.name, kind, converted, copy.deepcopy(col.metadata))
        self.worksheet.columns[index] = replacement
        self.dirty = True

    @undoable
    def replace_stored_data(self, constants=None, matrices=None):
        """Commit a validated editor snapshot without changing C/K/M positions."""
        if self.native_project is not None and not getattr(self.native_project,'statcraft_owned',False):
            raise io.UnsupportedFormatError('Imported native constants and matrices are view-only.')
        sheet=self.worksheet
        constants=copy.deepcopy(sheet.constants if constants is None else constants)
        matrices=copy.deepcopy(sheet.matrices if matrices is None else matrices)
        candidate=Worksheet(sheet.name,list(sheet.columns),constants,matrices,copy.deepcopy(sheet.metadata))
        for entries in (constants,matrices):
            names=[]
            for entry in entries:
                if not entry.name.strip() or entry.name!=entry.name.strip():
                    raise ValueError('Enter a nonempty name without leading or trailing spaces.')
                names.append(entry.name.casefold())
                if isinstance(entry,Column) and entry.kind!='number':
                    raise ValueError('Only numeric stored constants can currently be edited.')
                if isinstance(entry,Matrix) and (entry.rows<1 or entry.columns<1):
                    raise ValueError('Matrices require at least one row and one column.')
                if any(v is not None and finite_number(v)==io.MISSING_SENTINEL for v in entry.values):
                    raise ValueError('This numeric value is reserved for missing data.')
            if len(names)!=len(set(names)):raise ValueError('Stored names must be unique within constants or matrices.')
        sheets=[candidate]+([s for s in self.native_project.worksheets if s is not sheet] if self.native_project else [])
        total=sum(sum(len(c.values) for c in s.columns+s.constants)+sum(len(m.values) for m in s.matrices) for s in sheets)
        if total>io.MAX_CELLS:raise ValueError('The project exceeds the cell limit.')
        sheet.constants=constants;sheet.matrices=matrices

    def graph_builder(self,graph_type,response_indices,x_index=None,group_indices=None,options=None):
        from .graph_builder import compute_builder
        parameters,title,result=compute_builder(self.worksheet,graph_type=graph_type,response_indices=response_indices,x_index=x_index,group_indices=group_indices,options=options)
        return self._record(title,result,recipe={'action':'graph_builder','parameters':parameters})

    def categorical_points(self,response_indices,plot_type='individual',variant='one',group_indices=None,variable_position='outer',layout='combined',display=None,interval_options=None,jitter=.12,color_levels=None):
        from .categorical_points import validate_parameters,build_points
        parameters=validate_parameters(self.worksheet,response_indices,plot_type,variant,group_indices,variable_position,layout,display,interval_options,jitter,color_levels)
        result=build_points(self.worksheet,**parameters)
        return self._record(result['title'],result,recipe={'action':'categorical_points','parameters':parameters})

    def dotplot_graphs(self,response_indices,variant='one',group_indices=None,variable_position='outer',layout='combined',stack=True,intervals=None,color_levels=None):
        from .dotplot_graphs import validate_parameters,build_dotplots
        parameters=validate_parameters(self.worksheet,response_indices,variant,group_indices,variable_position,layout,stack,intervals,color_levels)
        result=build_dotplots(self.worksheet,**parameters)
        return self._record(result['title'],result,recipe={'action':'dotplot_graphs','parameters':parameters})

    def boxplot_graphs(self,response_indices,variant='one',group_indices=None,variable_position='outer',layout='combined',display=None):
        from .boxplot_graphs import validate_parameters,build_boxplots
        parameters=validate_parameters(self.worksheet,response_indices,variant,group_indices,variable_position,layout,display)
        result=build_boxplots(self.worksheet,**parameters)
        return self._record(result['title'],result,recipe={'action':'boxplot_graphs','parameters':parameters})

    def histogram_graphs(self,response_indices,variant='simple',group_index=None,layout='overlay',settings=None):
        from .histogram_graphs import validate_parameters,build_histograms
        parameters=validate_parameters(self.worksheet,response_indices,variant,group_index,layout,settings)
        result=build_histograms(self.worksheet,**parameters)
        return self._record(result['title'],result,recipe={'action':'histogram_graphs','parameters':parameters})

    def expanded_graph(self,method,indices,group_index=None,bins=10,confidence=.95,distribution='Normal',parameters=None):
        from .expanded_graphs import compute
        parameters={} if parameters is None else parameters
        result=compute(method,self.worksheet,indices,group_index,bins,confidence,distribution,parameters)
        return self._record(result['title'],result,recipe={'action':'expanded_graph','parameters':{
            'method':method,'indices':list(indices),'group_index':group_index,'bins':bins,
            'confidence':confidence,'distribution':distribution,'parameters':parameters}})

    def ecdf_plot(self, variable_index, group_index=None, distribution='None', confidence=0.95, title=None):
        from .ecdf_plot import compute_ecdf_plot
        result = compute_ecdf_plot(
            self.worksheet,
            variable_index=variable_index,
            group_index=group_index,
            distribution=distribution,
            confidence=confidence,
            title=title,
        )
        recipe = {
            'action': 'ecdf_plot',
            'parameters': {
                'variable_index': variable_index,
                'group_index': group_index,
                'distribution': distribution,
                'confidence': confidence,
                'title': title,
            }
        }
        return self._record(result['title'], result, recipe=recipe)

    def marginal_plot(self, y_index, x_index, marginal_type='histogram', show_normal_curve=False, bins=12, title=None):
        from .marginal_plot import compute_marginal_plot
        result = compute_marginal_plot(
            self.worksheet,
            y_index=y_index,
            x_index=x_index,
            marginal_type=marginal_type,
            show_normal_curve=show_normal_curve,
            bins=bins,
            title=title,
        )
        recipe = {
            'action': 'marginal_plot',
            'parameters': {
                'y_index': y_index,
                'x_index': x_index,
                'marginal_type': marginal_type,
                'show_normal_curve': show_normal_curve,
                'bins': bins,
                'title': title,
            }
        }
        return self._record(result['title'], result, recipe=recipe)

    def probability_distribution_plot(self, distribution='Normal', parameters=None, mode='single', shade_by='probability', tail='both', prob_value=0.05, x_value=None, x_low=None, x_high=None):
        from .prob_dist_plot import compute_probability_distribution_plot
        parameters = {} if parameters is None else parameters
        result = compute_probability_distribution_plot(
            distribution=distribution,
            parameters=parameters,
            mode=mode,
            shade_by=shade_by,
            tail=tail,
            prob_value=prob_value,
            x_value=x_value,
            x_low=x_low,
            x_high=x_high,
        )
        recipe = {
            'action': 'probability_distribution_plot',
            'parameters': {
                'distribution': distribution,
                'parameters': parameters,
                'mode': mode,
                'shade_by': shade_by,
                'tail': tail,
                'prob_value': prob_value,
                'x_value': x_value,
                'x_low': x_low,
                'x_high': x_high,
            }
        }
        return self._record(result['title'], result, recipe=recipe)

    def panel_graph(self,source_recipe,by_indices,shared_x=True,shared_y=True,source_appearance=None):
        from .panel_graphs import build_panels,validate_parameters
        from .compositions import validate_appearance,apply_panel_appearance
        parameters=validate_parameters(source_recipe,by_indices,shared_x,shared_y)
        appearance=validate_appearance(source_appearance)
        result=apply_panel_appearance(build_panels(self.worksheet,**parameters),appearance)
        return self._record('Panel Graph by '+', '.join(result['by_variables']),result,recipe={'action':'panel_graph','parameters':dict(parameters,source_appearance=appearance)})

    def graph_layout(self,entries,rows=2,columns=2,title='Graph Layout'):
        from .graph_layouts import build_layout
        from uuid import uuid4
        result=build_layout(entries,rows,columns,title)
        for source,snapshot in zip(entries,result['graphs']):
            if 'entry_id' not in source:source['entry_id']=str(uuid4())
            snapshot['entry_id']=source['entry_id']
        self._results_dirty=True
        return self._record(title,result)

    def update_graph_layout(self,entry,entries,rows=2,columns=2,title='Graph Layout'):
        from .graph_layouts import build_layout
        if entry.get('result',{}).get('graph')!='graph_layout':raise ValueError('Select a graph layout to edit.')
        result=build_layout(entries,rows,columns,title)
        return self._set_graph_option(entry,'result',result)

    def validate_brushed_rows(self,entry,rows):
        from .brushing import validate_brushed_rows
        if not any(item is entry for item in self.history):raise ValueError('Select a graph in the current project before brushing.')
        if self.result_stale(entry) is not False:raise ValueError('Rerun this graph with current worksheet data before brushing its rows.')
        return validate_brushed_rows(entry,self.result_worksheet(entry),rows)

    @undoable
    def calculate(self, expression, destination):
        from . import calculator
        values = calculator.evaluate_advanced(expression, self.worksheet)
        has_text = any(isinstance(v, str) for v in values)
        target_kind = "text" if has_text else "number"
        if target_kind == "text":
            values = [None if v is None else str(v) for v in values]

        dest_clean = destination.strip()
        if dest_clean.isdigit() or (dest_clean.upper().startswith("C") and dest_clean[1:].isdigit()):
            index = int(dest_clean[1:] if dest_clean.upper().startswith("C") else dest_clean) - 1
            if not 0 <= index < len(self.worksheet.columns):
                raise ValueError("Choose an existing column number (e.g., 1 or C1) or enter a new column name.")
            self.worksheet.columns[index].kind = target_kind
            self.worksheet.columns[index].values = values
        else:
            if not dest_clean:
                raise ValueError("Enter a destination name.")
            if (len(self.worksheet.columns) + 1) * max(1, self.worksheet.row_count) > io.MAX_CELLS:
                raise ValueError("The worksheet exceeds the cell limit.")
            self.worksheet.columns.append(Column(dest_clean, target_kind, values))
        return self._record("Calculator", {"expression": expression, "destination": destination, "rows": len(values)})

    def fit_binary_logistic(self,response_index,continuous_indices,categorical_indices,event=None,trials_index=None,terms=None,options=None):
        from .logistic import fit
        result=fit(self.worksheet,response_index,continuous_indices,categorical_indices,event,trials_index,terms,options)
        result['assumptions']=result['methodnotes']
        parameters=dict(response_index=response_index,continuous_indices=list(continuous_indices),categorical_indices=list(categorical_indices),event=result['event'] if trials_index is None else None,trials_index=trials_index,terms=result['terms'],options=result['options'])
        return self._record('Binary Logistic Regression: '+result['response_name'],result,recipe={'action':'fit_binary_logistic','parameters':parameters})

    def factorial_plots(self,model_recipe,selected_indices=None,options=None):
        from .model_plots import factorial_plots as run_factorial_plots
        from .prediction import normalize_recipe
        model_recipe=normalize_recipe(model_recipe)
        result=run_factorial_plots(self.worksheet,model_recipe,selected_indices,options)
        parameters=dict(model_recipe=copy.deepcopy(result['model_recipe']),selected_indices=list(result['selected_indices']),options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'factorial_plots','parameters':parameters})

    def model_contour_plot(self,model_recipe,x_index=None,y_index=None,options=None):
        from .model_plots import model_contour_plot as run_contour_plot
        from .prediction import normalize_recipe
        model_recipe=normalize_recipe(model_recipe)
        result=run_contour_plot(self.worksheet,model_recipe,x_index,y_index,options)
        parameters=dict(model_recipe=copy.deepcopy(result['model_recipe']),x_index=result['x_index'],y_index=result['y_index'],options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'model_contour_plot','parameters':parameters})

    def model_surface_plot(self,model_recipe,x_index=None,y_index=None,options=None):
        from .model_plots import model_surface_plot as run_surface_plot
        from .prediction import normalize_recipe
        model_recipe=normalize_recipe(model_recipe)
        result=run_surface_plot(self.worksheet,model_recipe,x_index,y_index,options)
        parameters=dict(model_recipe=copy.deepcopy(result['model_recipe']),x_index=result['x_index'],y_index=result['y_index'],options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'model_surface_plot','parameters':parameters})

    def optimize_responses(self,responses,options=None):
        from .optimizer import optimize
        result=optimize(self.worksheet,responses,options)
        parameters=dict(responses=copy.deepcopy(result['responses']),options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'optimize_responses','parameters':parameters})

    def predict_model(self,model_recipe,input_mode='values',values=None,new_indices=None,options=None):
        from .prediction import predict,normalize_recipe
        model_recipe=normalize_recipe(model_recipe)
        result=predict(self.worksheet,model_recipe,input_mode,values,new_indices,options)
        result['assumptions']=result['methodnotes']
        parameters=dict(model_recipe=copy.deepcopy(model_recipe),input_mode=input_mode,values=copy.deepcopy(values),new_indices=copy.deepcopy(new_indices),options=result['options'])
        return self._record('Prediction for '+result['response_name'],result,recipe={'action':'predict_model','parameters':parameters})

    def gage_rr(self,measurement_index,part_index,operator_index,options=None):
        from .gage_rr import analyze
        result=analyze(self.worksheet,measurement_index,part_index,operator_index,options)
        parameters=dict(measurement_index=measurement_index,part_index=part_index,operator_index=operator_index,options=result['options'])
        return self._record('Gage R&R Study (Crossed): '+self.worksheet.columns[measurement_index].name,result,recipe={'action':'gage_rr','parameters':parameters})

    def subgroup_control_chart(self, chart_type='xbar_r', stacked=True, response_index=None, factor_index=None, indices=None, subgroup_size=None, options=None, **kwargs):
        from .subgroup_control import fit_from_worksheet
        result = fit_from_worksheet(
            self.worksheet,
            stacked=stacked,
            response_index=response_index,
            factor_index=factor_index,
            indices=indices,
            subgroup_size=subgroup_size,
            chart_type=chart_type,
            options=options
        )
        parameters = dict(
            chart_type=chart_type,
            stacked=stacked,
            response_index=response_index,
            factor_index=factor_index,
            indices=list(indices) if indices else None,
            subgroup_size=subgroup_size,
            options=result['options'],
        )
        chart_name = "Xbar-R Chart" if chart_type == 'xbar_r' else "Xbar-S Chart"
        title = f"{chart_name}: {result['variable_name']}"
        return self._record(title, result, recipe={'action': 'subgroup_control_chart', 'parameters': parameters})

    def oneway_anova(self, response_index=None, factor_index=None, response_indices=None, options=None, stacked=True, **kwargs):
        if not stacked or (response_indices is not None and response_index is None):
            return self.oneway_anova_unstacked(response_indices=response_indices, options=options)
        from .oneway import fit
        result = fit(self.worksheet, response_index, factor_index, options)
        parameters = dict(
            stacked=True,
            response_index=response_index,
            factor_index=factor_index,
            response_indices=None,
            options=result['options'],
        )
        self._store_oneway_columns(result)
        return self._record('One-Way ANOVA: ' + result['response_name'] + ' versus ' + result['factor_name'],
                            result,
                            recipe={'action': 'oneway_anova', 'parameters': parameters})

    def oneway_anova_unstacked(self, response_indices, options=None, **kwargs):
        from .oneway import fit_unstacked
        result = fit_unstacked(self.worksheet, list(response_indices), options)
        parameters = dict(
            stacked=False,
            response_index=None,
            factor_index=None,
            response_indices=list(response_indices),
            options=result['options'],
        )
        self._store_oneway_columns(result)
        names = ', '.join(self.worksheet.columns[i].name or f'C{i+1}' for i in response_indices)
        return self._record('One-Way ANOVA: ' + names,
                            result,
                            recipe={'action': 'oneway_anova', 'parameters': parameters})

    def twoway_anova(self, response_index, factor_a_index, factor_b_index, fit_interaction=True, display_means=True, confidence=0.95):
        from .twoway_anova_engine import compute_twoway_anova
        y_col = self.worksheet.columns[response_index]
        a_col = self.worksheet.columns[factor_a_index]
        b_col = self.worksheet.columns[factor_b_index]

        result = compute_twoway_anova(
            responses=y_col.values,
            factor_a_vals=a_col.values,
            factor_b_vals=b_col.values,
            response_name=y_col.name,
            factor_a_name=a_col.name,
            factor_b_name=b_col.name,
            fit_interaction=fit_interaction,
            display_means=display_means,
            confidence=confidence
        )
        parameters = {
            "response_index": response_index,
            "factor_a_index": factor_a_index,
            "factor_b_index": factor_b_index,
            "fit_interaction": fit_interaction,
            "display_means": display_means,
            "confidence": confidence
        }
        title = f"Two-Way ANOVA: {y_col.name} versus {a_col.name}, {b_col.name}"
        return self._record(title, result, recipe={'action': 'twoway_anova', 'parameters': parameters})

    def main_effects_plot(self, response_index: int, factor_indices: list[int]):
        from .anova_plots_engine import compute_main_effects
        y_col = self.worksheet.columns[response_index]
        factors_data = [self.worksheet.columns[i].values for i in factor_indices]
        factor_names = [self.worksheet.columns[i].name for i in factor_indices]
        result = compute_main_effects(
            responses=y_col.values,
            factors_data=factors_data,
            response_name=y_col.name,
            factor_names=factor_names
        )
        parameters = {
            "response_index": response_index,
            "factor_indices": factor_indices
        }
        title = f"Main Effects Plot for {y_col.name}"
        return self._record(title, result, recipe={'action': 'main_effects_plot', 'parameters': parameters})

    def interactions_plot(self, response_index: int, factor_a_index: int, factor_b_index: int):
        from .anova_plots_engine import compute_interactions
        y_col = self.worksheet.columns[response_index]
        a_col = self.worksheet.columns[factor_a_index]
        b_col = self.worksheet.columns[factor_b_index]
        result = compute_interactions(
            responses=y_col.values,
            factor_a_vals=a_col.values,
            factor_b_vals=b_col.values,
            response_name=y_col.name,
            factor_a_name=a_col.name,
            factor_b_name=b_col.name
        )
        parameters = {
            "response_index": response_index,
            "factor_a_index": factor_a_index,
            "factor_b_index": factor_b_index
        }
        title = f"Interaction Plot for {y_col.name} ({a_col.name} by {b_col.name})"
        return self._record(title, result, recipe={'action': 'interactions_plot', 'parameters': parameters})

    @undoable
    def store_descriptive_stats(self, var_indices: list[int], by_index: int | None = None, selected_stats: list[str] | None = None):
        from .store_descriptive import compute_store_descriptive_columns
        new_cols = compute_store_descriptive_columns(self.worksheet, var_indices, by_index, selected_stats)
        for col in new_cols:
            self.worksheet.columns.append(col)
        self.dirty = True
        return self._record("Store Descriptive Statistics", {
            "stored_columns": [c.name for c in new_cols],
            "var_indices": var_indices,
            "by_index": by_index,
            "selected_stats": selected_stats
        }, recipe={
            'action': 'store_descriptive_stats',
            'parameters': {
                'var_indices': var_indices,
                'by_index': by_index,
                'selected_stats': selected_stats
            }
        })

    def _store_oneway_columns(self, result):
        storage = (result.get('options') or {}).get('storage') or {}
        store_fits = storage.get('fits', False)
        store_resi = storage.get('residuals', False)
        if not store_fits and not store_resi:
            return
        raw_pairs = result.get('raw_pairs') or []
        fits = result.get('fits') or []
        residuals = result.get('residuals') or []
        n_rows = self.worksheet.row_count

        def _next_col_name(base_prefix):
            existing = {c.name.upper() for c in self.worksheet.columns if c.name}
            cand = base_prefix
            if cand not in existing:
                return cand
            idx = 1
            while f"{base_prefix}{idx}" in existing:
                idx += 1
            return f"{base_prefix}{idx}"

        if store_fits and fits:
            col_vals = [None] * n_rows
            for (y, x, r), f in zip(raw_pairs, fits):
                if 0 <= r < n_rows:
                    col_vals[r] = round(float(f), 6)
            col_name = _next_col_name('FITS')
            col = Column(col_name, 'number', col_vals)
            if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
                from .mpx_columns import independent_metadata
                col.metadata = independent_metadata()
            self.worksheet.columns.append(col)
            self.dirty = True

        if store_resi and residuals:
            col_vals = [None] * n_rows
            for (y, x, r), res in zip(raw_pairs, residuals):
                if 0 <= r < n_rows:
                    col_vals[r] = round(float(res), 6)
            col_name = _next_col_name('RESI')
            col = Column(col_name, 'number', col_vals)
            if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
                from .mpx_columns import independent_metadata
                col.metadata = independent_metadata()
            self.worksheet.columns.append(col)
            self.dirty = True

    def general_linear_model(self,response_index,factor_indices,covariate_indices,terms=None,options=None):
        from .glm import fit
        result=fit(self.worksheet,response_index,factor_indices,covariate_indices,terms,options)
        parameters=dict(response_index=response_index,factor_indices=list(factor_indices),covariate_indices=list(covariate_indices),terms=result['terms'],options=result['options'])
        return self._record('General Linear Model: '+result['response_name'],result,recipe={'action':'general_linear_model','parameters':parameters})

    def multiple_regression(self, response_index, predictor_indices, confidence=.95):
        from .regression import multiple_regression
        if not predictor_indices or len(set(predictor_indices)) != len(predictor_indices) or response_index in predictor_indices:
            raise ValueError("Choose distinct predictors and a separate response.")
        response = self.worksheet.columns[response_index]
        predictors = [self.worksheet.columns[i] for i in predictor_indices]
        columns = predictors + [response]
        if any(c.kind != "number" for c in columns):
            raise ValueError("Regression requires numeric response and predictor columns.")
        size = max(len(c.values) for c in columns)
        aligned = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in columns]
        result = multiple_regression(aligned[:-1], aligned[-1], confidence, [c.name for c in predictors], response_name=response.name)
        from .connect import create_connected_regression
        connected = create_connected_regression(self.worksheet, response_index, predictor_indices, result, confidence)
        entry = self._record("Multiple Regression — " + response.name,
                            {"response_name": response.name, "variables": [c.name for c in predictors], "analysis": "multiple_regression", **result},
                            recipe={"action":"multiple_regression", "parameters":{"response_index":response_index, "predictor_indices":list(predictor_indices), "confidence":confidence}})
        entry["connected_analysis"] = connected.to_dict()
        return entry

    def best_subsets(
        self,
        response_index: int,
        free_indices: list,
        forced_indices: list = None,
        models_per_subset: int = 2,
        min_free: int = 1,
        max_free: int = None,
    ):
        from .best_subsets import best_subsets_regression
        forced_indices = list(forced_indices) if forced_indices else []
        free_indices = list(free_indices)
        if not free_indices:
            raise ValueError("Choose at least one free predictor.")
        if response_index in free_indices or response_index in forced_indices:
            raise ValueError("Response variable cannot also be a predictor.")
        if set(free_indices).intersection(set(forced_indices)):
            raise ValueError("Predictors cannot be both free and forced.")

        resp_col = self.worksheet.columns[response_index]
        free_cols = [self.worksheet.columns[i] for i in free_indices]
        forced_cols = [self.worksheet.columns[i] for i in forced_indices]

        all_cols = [resp_col] + free_cols + forced_cols
        if any(c.kind != "number" for c in all_cols):
            raise ValueError("Best Subsets requires numeric response and predictor columns.")

        size = max(len(c.values) for c in all_cols)
        aligned = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in all_cols]

        resp_vals = aligned[0]
        free_vals = aligned[1 : 1 + len(free_cols)]
        forced_vals = aligned[1 + len(free_cols) :]

        res = best_subsets_regression(
            response=resp_vals,
            free_predictors=free_vals,
            free_names=[c.name for c in free_cols],
            forced_predictors=forced_vals if forced_cols else None,
            forced_names=[c.name for c in forced_cols] if forced_cols else None,
            models_per_subset=models_per_subset,
            min_free=min_free,
            max_free=max_free,
            response_name=resp_col.name,
        )

        title = f"Best Subsets Regression: {resp_col.name} versus {', '.join(c.name for c in free_cols)}"
        recipe = {
            "action": "best_subsets",
            "parameters": {
                "response_index": response_index,
                "free_indices": list(free_indices),
                "forced_indices": list(forced_indices),
                "models_per_subset": models_per_subset,
                "min_free": min_free,
                "max_free": max_free,
            },
        }
        return self._record(title, res, recipe=recipe)

    def stepwise_regression(self, settings=None):
        import copy
        from .stepwise import stepwise_regression
        if settings is None:
            raise ValueError("Stepwise Regression requires settings.")
        resp_idx = settings.get("response_index")
        pred_idxs = list(settings.get("predictor_indices", []))
        if resp_idx is None:
            raise ValueError("Please select a response variable.")
        if not pred_idxs:
            raise ValueError("Please select at least one predictor variable.")

        resp_col = self.worksheet.columns[resp_idx]
        pred_cols = [self.worksheet.columns[i] for i in pred_idxs]
        all_cols = [resp_col] + pred_cols
        if any(c.kind != "number" for c in all_cols):
            raise ValueError("Stepwise Regression requires numeric response and predictor columns.")

        size = max(len(c.values) for c in all_cols)
        aligned = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in all_cols]
        resp_vals = aligned[0]
        pred_vals = aligned[1:]

        res = stepwise_regression(
            response=resp_vals,
            predictors=pred_vals,
            predictor_names=[c.name for c in pred_cols],
            response_name=resp_col.name,
            method=settings.get("method", "stepwise"),
            alpha_to_enter=settings.get("alpha_to_enter", 0.15),
            alpha_to_remove=settings.get("alpha_to_remove", 0.15),
            forced_indices=settings.get("forced_indices"),
        )
        res["analysis"] = "stepwise_regression"
        recipe = {
            "action": "stepwise_regression",
            "parameters": dict(settings),
        }
        return self._record(res["title"], res, recipe=recipe)

    def reliability_arbitrary(self, settings=None):
        import copy
        from .reliability_arbitrary import fit_parametric_arbitrary_censoring
        if settings is None:
            raise ValueError("Arbitrary Censoring requires settings.")
        st = copy.deepcopy(settings)
        s_idx = st.get("start_index")
        e_idx = st.get("end_index")
        f_idx = st.get("frequency_index")

        if s_idx is None and e_idx is None:
            raise ValueError("Start or End time column is required.")

        s_col = self.worksheet.columns[s_idx] if s_idx is not None else None
        e_col = self.worksheet.columns[e_idx] if e_idx is not None else None
        f_col = self.worksheet.columns[f_idx] if f_idx is not None else None

        all_cols = [c for c in (s_col, e_col, f_col) if c is not None]
        size = max(len(c.values) for c in all_cols)

        s_vals = (s_col.numeric_values(True) + [None] * (size - len(s_col.values))) if s_col else [None] * size
        e_vals = (e_col.numeric_values(True) + [None] * (size - len(e_col.values))) if e_col else [None] * size
        f_vals = (f_col.numeric_values(True) + [None] * (size - len(f_col.values))) if f_col else None

        res = fit_parametric_arbitrary_censoring(
            start_times=s_vals,
            end_times=e_vals,
            frequencies=f_vals,
            distribution=st.get("distribution", "weibull"),
            confidence=st.get("confidence", 0.95),
        )
        res["analysis"] = "reliability_arbitrary"
        recipe = {
            "action": "reliability_arbitrary",
            "parameters": {
                "start_index": s_idx,
                "end_index": e_idx,
                "frequency_index": f_idx,
                "distribution": st.get("distribution", "weibull"),
                "confidence": st.get("confidence", 0.95),
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def nonparametric_growth_curve(
        self,
        time_column=None,
        system_column=None,
        event_column=None,
        cost_column=None,
        confidence=0.95,
        settings=None,
    ):
        import copy
        from .repairable_systems import fit_nonparametric_mcf
        if settings is not None:
            st = copy.deepcopy(settings)
            t_idx = st.get("time_index", st.get("time_column"))
            s_idx = st.get("system_index", st.get("system_column"))
            ev_idx = st.get("event_index", st.get("event_column"))
            c_idx = st.get("cost_index", st.get("cost_column"))
            conf = float(st.get("confidence", 0.95))
        else:
            t_idx = time_column
            s_idx = system_column
            ev_idx = event_column
            c_idx = cost_column
            conf = float(confidence)

        if t_idx is None:
            raise ValueError("Operating / event time variable is required.")
        if s_idx is None:
            raise ValueError("System ID variable is required.")

        t_col = self.worksheet.columns[t_idx]
        s_col = self.worksheet.columns[s_idx]
        ev_col = self.worksheet.columns[ev_idx] if ev_idx is not None else None
        c_col = self.worksheet.columns[c_idx] if c_idx is not None else None

        size = max(len(t_col.values), len(s_col.values))
        t_vals = t_col.numeric_values(True) + [None] * (size - len(t_col.values))
        s_vals = list(s_col.values) + [None] * (size - len(s_col.values))
        ev_vals = (ev_col.numeric_values(True) + [None] * (size - len(ev_col.values))) if ev_col else None
        c_vals = (c_col.numeric_values(True) + [None] * (size - len(c_col.values))) if c_col else None

        res = fit_nonparametric_mcf(
            system=s_vals,
            time=t_vals,
            event=ev_vals,
            cost=c_vals,
            confidence=conf,
            system_name=s_col.name,
            time_name=t_col.name,
        )
        res["analysis"] = "nonparametric_growth_curve"
        recipe = {
            "action": "nonparametric_growth_curve",
            "parameters": {
                "time_index": t_idx,
                "system_index": s_idx,
                "event_index": ev_idx,
                "cost_index": c_idx,
                "confidence": conf,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def parametric_growth_curve(
        self,
        time_column=None,
        system_column=None,
        event_column=None,
        confidence=0.95,
        settings=None,
    ):
        import copy
        from .repairable_systems import fit_parametric_growth_curve
        if settings is not None:
            st = copy.deepcopy(settings)
            t_idx = st.get("time_index", st.get("time_column"))
            s_idx = st.get("system_index", st.get("system_column"))
            ev_idx = st.get("event_index", st.get("event_column"))
            conf = float(st.get("confidence", 0.95))
        else:
            t_idx = time_column
            s_idx = system_column
            ev_idx = event_column
            conf = float(confidence)

        if t_idx is None:
            raise ValueError("Operating / event time variable is required.")
        if s_idx is None:
            raise ValueError("System ID variable is required.")

        t_col = self.worksheet.columns[t_idx]
        s_col = self.worksheet.columns[s_idx]
        ev_col = self.worksheet.columns[ev_idx] if ev_idx is not None else None

        size = max(len(t_col.values), len(s_col.values))
        t_vals = t_col.numeric_values(True) + [None] * (size - len(t_col.values))
        s_vals = list(s_col.values) + [None] * (size - len(s_col.values))
        ev_vals = (ev_col.numeric_values(True) + [None] * (size - len(ev_col.values))) if ev_col else None

        res = fit_parametric_growth_curve(
            system=s_vals,
            time=t_vals,
            event=ev_vals,
            confidence=conf,
            system_name=s_col.name,
            time_name=t_col.name,
        )
        res["analysis"] = "parametric_growth_curve"
        recipe = {
            "action": "parametric_growth_curve",
            "parameters": {
                "time_index": t_idx,
                "system_index": s_idx,
                "event_index": ev_idx,
                "confidence": conf,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def probit_analysis(
        self,
        response_column=None,
        trials_column=None,
        dose_column=None,
        distribution="probit",
        dose_transform="none",
        confidence=0.95,
        settings=None,
    ):
        import copy
        from .probit import fit_probit_analysis
        if settings is not None:
            st = copy.deepcopy(settings)
            resp_idx = st.get("response_index", st.get("response_column"))
            trials_idx = st.get("trials_index", st.get("trials_column"))
            dose_idx = st.get("dose_index", st.get("dose_column"))
            dist = st.get("distribution", "probit")
            trans = st.get("dose_transform", "none")
            conf = float(st.get("confidence", 0.95))
        else:
            resp_idx = response_column
            trials_idx = trials_column
            dose_idx = dose_column
            dist = distribution
            trans = dose_transform
            conf = float(confidence)

        if resp_idx is None:
            raise ValueError("Response (events) variable is required.")
        if dose_idx is None:
            raise ValueError("Stress / stimulus (dose) variable is required.")

        resp_col = self.worksheet.columns[resp_idx]
        dose_col = self.worksheet.columns[dose_idx]
        trials_col = self.worksheet.columns[trials_idx] if trials_idx is not None else None

        size = max(len(resp_col.values), len(dose_col.values), len(trials_col.values) if trials_col else 0)
        resp_vals = resp_col.numeric_values(True) + [None] * (size - len(resp_col.values))
        dose_vals = dose_col.numeric_values(True) + [None] * (size - len(dose_col.values))
        trials_vals = (trials_col.numeric_values(True) + [None] * (size - len(trials_col.values))) if trials_col else None

        res = fit_probit_analysis(
            events=resp_vals,
            dose=dose_vals,
            trials=trials_vals,
            distribution=dist,
            dose_transform=trans,
            confidence=conf,
            dose_name=dose_col.name,
            events_name=resp_col.name,
            trials_name=trials_col.name if trials_col else "Trials",
        )
        res["analysis"] = "probit_analysis"
        recipe = {
            "action": "probit_analysis",
            "parameters": {
                "response_index": resp_idx,
                "trials_index": trials_idx,
                "dose_index": dose_idx,
                "distribution": dist,
                "dose_transform": trans,
                "confidence": conf,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def multiple_correspondence(
        self,
        variable_columns=None,
        n_components=2,
        settings=None,
    ):
        import copy
        from .multiple_correspondence import fit_multiple_correspondence
        if settings is not None:
            st = copy.deepcopy(settings)
            v_idxs = list(st.get("variable_indices", st.get("variable_columns", [])))
            n_comp = int(st.get("n_components", 2))
        else:
            v_idxs = list(variable_columns or [])
            n_comp = int(n_components)

        if not v_idxs or len(v_idxs) < 2:
            raise ValueError("Multiple Correspondence Analysis requires at least 2 variables.")

        cols = [self.worksheet.columns[i] for i in v_idxs]
        max_size = max(len(c.values) for c in cols)
        data_vals = [list(c.values) + [None] * (max_size - len(c.values)) for c in cols]

        res = fit_multiple_correspondence(
            data_columns=data_vals,
            n_components=n_comp,
            variable_names=[c.name for c in cols],
        )
        res["analysis"] = "multiple_correspondence"
        recipe = {
            "action": "multiple_correspondence",
            "parameters": {
                "variable_indices": v_idxs,
                "n_components": n_comp,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def factor_analysis(
        self,
        variable_columns=None,
        n_factors=None,
        rotation="varimax",
        settings=None,
    ):
        import copy
        from .factor_analysis import fit_factor_analysis
        if settings is not None:
            st = copy.deepcopy(settings)
            v_idxs = list(st.get("variable_indices", st.get("variable_columns", [])))
            n_fac = st.get("n_factors")
            rot = st.get("rotation", "varimax")
        else:
            v_idxs = list(variable_columns or [])
            n_fac = n_factors
            rot = rotation

        if not v_idxs or len(v_idxs) < 2:
            raise ValueError("Factor Analysis requires at least 2 variables.")

        cols = [self.worksheet.columns[i] for i in v_idxs]
        max_size = max(len(c.values) for c in cols)
        data_vals = [c.numeric_values(True) + [None] * (max_size - len(c.values)) for c in cols]

        res = fit_factor_analysis(
            data_columns=data_vals,
            n_factors=n_fac,
            rotation=rot,
            variable_names=[c.name for c in cols],
        )
        res["analysis"] = "factor_analysis"
        recipe = {
            "action": "factor_analysis",
            "parameters": {
                "variable_indices": v_idxs,
                "n_factors": n_fac,
                "rotation": rot,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def life_regression(
        self,
        response_column=None,
        predictor_columns=None,
        censor_column=None,
        distribution="weibull",
        confidence=0.95,
        settings=None,
    ):
        import copy
        from .life_regression import fit_life_regression
        if settings is not None:
            st = copy.deepcopy(settings)
            r_idx = st.get("response_index", st.get("response_column"))
            p_idxs = list(st.get("predictor_indices", st.get("predictor_columns", [])))
            c_idx = st.get("censor_index", st.get("censor_column"))
            dist = st.get("distribution", "weibull")
            conf_val = float(st.get("confidence", 0.95))
        else:
            r_idx = response_column
            p_idxs = list(predictor_columns or [])
            c_idx = censor_column
            dist = distribution
            conf_val = float(confidence)

        if r_idx is None:
            raise ValueError("Response lifetime variable is required.")
        if not p_idxs:
            raise ValueError("At least one predictor is required.")

        r_col = self.worksheet.columns[r_idx]
        p_cols = [self.worksheet.columns[i] for i in p_idxs]
        c_col = self.worksheet.columns[c_idx] if c_idx is not None else None

        all_cols = [r_col] + p_cols + ([c_col] if c_col else [])
        size = max(len(c.values) for c in all_cols)

        r_vals = r_col.numeric_values(True) + [None] * (size - len(r_col.values))
        p_vals = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in p_cols]
        c_vals = (c_col.numeric_values(True) + [None] * (size - len(c_col.values))) if c_col else None

        res = fit_life_regression(
            response=r_vals,
            predictors=p_vals,
            censor=c_vals,
            distribution=dist,
            confidence=conf_val,
            response_name=r_col.name,
            predictor_names=[c.name for c in p_cols],
        )
        res["analysis"] = "life_regression"
        recipe = {
            "action": "life_regression",
            "parameters": {
                "response_index": r_idx,
                "predictor_indices": p_idxs,
                "censor_index": c_idx,
                "distribution": dist,
                "confidence": conf_val,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def stability_study(
        self,
        response_column=None,
        time_column=None,
        batch_column=None,
        lsl=None,
        usl=None,
        alpha_pool=0.25,
        confidence=0.95,
        settings=None,
    ):
        import copy
        from .stability_study import fit_stability_study
        if settings is not None:
            st = copy.deepcopy(settings)
            r_idx = st.get("response_index", st.get("response_column"))
            t_idx = st.get("time_index", st.get("time_column"))
            b_idx = st.get("batch_index", st.get("batch_column"))
            lsl_val = st.get("lsl")
            usl_val = st.get("usl")
            alpha_val = float(st.get("alpha_pool", 0.25))
            conf_val = float(st.get("confidence", 0.95))
        else:
            r_idx = response_column
            t_idx = time_column
            b_idx = batch_column
            lsl_val = lsl
            usl_val = usl
            alpha_val = float(alpha_pool)
            conf_val = float(confidence)

        if r_idx is None:
            raise ValueError("Response variable is required.")
        if t_idx is None:
            raise ValueError("Time variable is required.")
        if b_idx is None:
            raise ValueError("Batch variable is required.")

        r_col = self.worksheet.columns[r_idx]
        t_col = self.worksheet.columns[t_idx]
        b_col = self.worksheet.columns[b_idx]

        size = max(len(r_col.values), len(t_col.values), len(b_col.values))
        r_vals = r_col.numeric_values(True) + [None] * (size - len(r_col.values))
        t_vals = t_col.numeric_values(True) + [None] * (size - len(t_col.values))
        b_vals = list(b_col.values) + [None] * (size - len(b_col.values))

        res = fit_stability_study(
            response=r_vals,
            time=t_vals,
            batch=b_vals,
            lsl=lsl_val,
            usl=usl_val,
            alpha_pool=alpha_val,
            confidence=conf_val,
            response_name=r_col.name,
            time_name=t_col.name,
            batch_name=b_col.name,
        )
        res["analysis"] = "stability_study"
        recipe = {
            "action": "stability_study",
            "parameters": {
                "response_index": r_idx,
                "time_index": t_idx,
                "batch_index": b_idx,
                "lsl": lsl_val,
                "usl": usl_val,
                "alpha_pool": alpha_val,
                "confidence": conf_val,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def orthogonal_regression(
        self,
        response_column=None,
        predictor_column=None,
        error_variance_ratio=1.0,
        confidence=0.95,
        settings=None,
    ):
        import copy
        from .orthogonal_regression import fit_orthogonal_regression
        if settings is not None:
            st = copy.deepcopy(settings)
            resp_idx = st.get("response_index", st.get("response_column"))
            pred_idx = st.get("predictor_index", st.get("predictor_column"))
            ratio = float(st.get("error_variance_ratio", 1.0))
            conf = float(st.get("confidence", 0.95))
        else:
            resp_idx = response_column
            pred_idx = predictor_column
            ratio = float(error_variance_ratio)
            conf = float(confidence)

        if resp_idx is None:
            raise ValueError("Response variable (Y) is required.")
        if pred_idx is None:
            raise ValueError("Predictor variable (X) is required.")

        resp_col = self.worksheet.columns[resp_idx]
        pred_col = self.worksheet.columns[pred_idx]

        size = max(len(resp_col.values), len(pred_col.values))
        resp_vals = resp_col.numeric_values(True) + [None] * (size - len(resp_col.values))
        pred_vals = pred_col.numeric_values(True) + [None] * (size - len(pred_col.values))

        res = fit_orthogonal_regression(
            response=resp_vals,
            predictor=pred_vals,
            error_variance_ratio=ratio,
            response_name=resp_col.name,
            predictor_name=pred_col.name,
            confidence=conf,
        )
        res["analysis"] = "orthogonal_regression"
        recipe = {
            "action": "orthogonal_regression",
            "parameters": {
                "response_index": resp_idx,
                "predictor_index": pred_idx,
                "error_variance_ratio": ratio,
                "confidence": conf,
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def pls_regression(self, settings=None):
        import copy
        from .pls import fit_pls_regression
        if settings is None:
            raise ValueError("Partial Least Squares requires settings.")
        st = copy.deepcopy(settings)
        resp_idx = st.get("response_index")
        pred_idxs = list(st.get("predictor_indices", []))

        if resp_idx is None:
            raise ValueError("Response variable is required.")
        if not pred_idxs:
            raise ValueError("At least one predictor is required.")

        resp_col = self.worksheet.columns[resp_idx]
        pred_cols = [self.worksheet.columns[i] for i in pred_idxs]

        all_cols = [resp_col] + pred_cols
        size = max(len(c.values) for c in all_cols)

        resp_vals = resp_col.numeric_values(True) + [None] * (size - len(resp_col.values))
        pred_vals = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in pred_cols]

        res = fit_pls_regression(
            response=resp_vals,
            predictors=pred_vals,
            n_components=st.get("n_components"),
            max_components=st.get("max_components", 10),
            predictor_names=[c.name for c in pred_cols],
            response_name=resp_col.name,
        )
        res["analysis"] = "pls_regression"
        recipe = {
            "action": "pls_regression",
            "parameters": {
                "response_index": resp_idx,
                "predictor_indices": pred_idxs,
                "n_components": st.get("n_components"),
                "max_components": st.get("max_components", 10),
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def nonlinear_regression(self, settings=None):
        import copy
        from .nonlinear_regression import fit_nonlinear_regression
        if settings is None:
            raise ValueError("Nonlinear Regression requires settings.")
        st = copy.deepcopy(settings)
        resp_idx = st.get("response_index")
        pred_idxs = list(st.get("predictor_indices", []))

        if resp_idx is None:
            raise ValueError("Response variable is required.")
        if not pred_idxs:
            raise ValueError("At least one predictor is required.")

        resp_col = self.worksheet.columns[resp_idx]
        pred_cols = [self.worksheet.columns[i] for i in pred_idxs]

        all_cols = [resp_col] + pred_cols
        size = max(len(c.values) for c in all_cols)

        resp_vals = resp_col.numeric_values(True) + [None] * (size - len(resp_col.values))
        pred_vals = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in pred_cols]

        res = fit_nonlinear_regression(
            response=resp_vals,
            predictors=pred_vals,
            model=st.get("model", "asymptotic"),
            custom_formula=st.get("custom_formula"),
            parameter_names=st.get("parameter_names"),
            initial_values=st.get("initial_values"),
            predictor_names=[c.name for c in pred_cols],
            response_name=resp_col.name,
            confidence=st.get("confidence", 0.95),
        )
        res["analysis"] = "nonlinear_regression"
        recipe = {
            "action": "nonlinear_regression",
            "parameters": {
                "response_index": resp_idx,
                "predictor_indices": pred_idxs,
                "model": st.get("model", "asymptotic"),
                "custom_formula": st.get("custom_formula"),
                "parameter_names": st.get("parameter_names"),
                "initial_values": st.get("initial_values"),
                "confidence": st.get("confidence", 0.95),
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def nominal_logistic_regression(self, settings=None):
        import copy
        from .nominal_logistic import fit_nominal_logistic_regression
        if settings is None:
            raise ValueError("Nominal Logistic Regression requires settings.")
        st = copy.deepcopy(settings)
        resp_idx = st.get("response_index")
        cont_idxs = list(st.get("continuous_indices", []))
        cat_idxs = list(st.get("categorical_indices", []))

        if resp_idx is None:
            raise ValueError("Response variable is required.")
        if not cont_idxs and not cat_idxs:
            raise ValueError("At least one predictor is required.")

        resp_col = self.worksheet.columns[resp_idx]
        cont_cols = [self.worksheet.columns[i] for i in cont_idxs]
        cat_cols = [self.worksheet.columns[i] for i in cat_idxs]

        all_cols = [resp_col] + cont_cols + cat_cols
        size = max(len(c.values) for c in all_cols)

        resp_vals = list(resp_col.values) + [None] * (size - len(resp_col.values))
        cont_vals = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in cont_cols]
        cat_vals = [list(c.values) + [None] * (size - len(c.values)) for c in cat_cols]

        res = fit_nominal_logistic_regression(
            response=resp_vals,
            continuous_predictors=cont_vals if cont_cols else None,
            categorical_predictors=cat_vals if cat_cols else None,
            continuous_names=[c.name for c in cont_cols] if cont_cols else None,
            categorical_names=[c.name for c in cat_cols] if cat_cols else None,
            reference_level=st.get("reference_level"),
            response_name=resp_col.name,
            confidence=st.get("confidence", 0.95),
        )
        res["analysis"] = "nominal_logistic_regression"
        recipe = {
            "action": "nominal_logistic_regression",
            "parameters": {
                "response_index": resp_idx,
                "continuous_indices": cont_idxs,
                "categorical_indices": cat_idxs,
                "reference_level": st.get("reference_level"),
                "confidence": st.get("confidence", 0.95),
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def ordinal_logistic_regression(self, settings=None):
        import copy
        from .ordinal_logistic import fit_ordinal_logistic_regression
        if settings is None:
            raise ValueError("Ordinal Logistic Regression requires settings.")
        st = copy.deepcopy(settings)
        resp_idx = st.get("response_index")
        cont_idxs = list(st.get("continuous_indices", []))
        cat_idxs = list(st.get("categorical_indices", []))

        if resp_idx is None:
            raise ValueError("Response variable is required.")
        if not cont_idxs and not cat_idxs:
            raise ValueError("At least one predictor is required.")

        resp_col = self.worksheet.columns[resp_idx]
        cont_cols = [self.worksheet.columns[i] for i in cont_idxs]
        cat_cols = [self.worksheet.columns[i] for i in cat_idxs]

        all_cols = [resp_col] + cont_cols + cat_cols
        size = max(len(c.values) for c in all_cols)

        resp_vals = list(resp_col.values) + [None] * (size - len(resp_col.values))
        cont_vals = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in cont_cols]
        cat_vals = [list(c.values) + [None] * (size - len(c.values)) for c in cat_cols]

        res = fit_ordinal_logistic_regression(
            response=resp_vals,
            continuous_predictors=cont_vals if cont_cols else None,
            categorical_predictors=cat_vals if cat_cols else None,
            continuous_names=[c.name for c in cont_cols] if cont_cols else None,
            categorical_names=[c.name for c in cat_cols] if cat_cols else None,
            response_name=resp_col.name,
            confidence=st.get("confidence", 0.95),
        )
        res["analysis"] = "ordinal_logistic_regression"
        recipe = {
            "action": "ordinal_logistic_regression",
            "parameters": {
                "response_index": resp_idx,
                "continuous_indices": cont_idxs,
                "categorical_indices": cat_idxs,
                "confidence": st.get("confidence", 0.95),
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def gage_rr_expanded(self, settings=None):
        import copy
        from .gage_rr_expanded import analyze_gage_rr_expanded
        if settings is None:
            raise ValueError("Expanded Gage R&R requires settings.")
        st = copy.deepcopy(settings)
        meas_idx = st.get("measurement_index")
        part_idx = st.get("part_index")
        op_idx = st.get("operator_index")
        add_idxs = list(st.get("additional_factor_indices", []))

        if any(idx is None for idx in (meas_idx, part_idx, op_idx)):
            raise ValueError("Measurement, part, and operator columns are required.")

        meas_col = self.worksheet.columns[meas_idx]
        part_col = self.worksheet.columns[part_idx]
        op_col = self.worksheet.columns[op_idx]
        add_cols = [self.worksheet.columns[i] for i in add_idxs]

        all_cols = [meas_col, part_col, op_col] + add_cols
        size = max(len(c.values) for c in all_cols)

        meas_vals = meas_col.numeric_values(True) + [None] * (size - len(meas_col.values))
        part_vals = list(part_col.values) + [None] * (size - len(part_col.values))
        op_vals = list(op_col.values) + [None] * (size - len(op_col.values))
        add_vals = [list(c.values) + [None] * (size - len(c.values)) for c in add_cols]

        res = analyze_gage_rr_expanded(
            measurements=meas_vals,
            part_values=part_vals,
            operator_values=op_vals,
            additional_factors=add_vals if add_cols else None,
            part_name=part_col.name,
            operator_name=op_col.name,
            additional_factor_names=[c.name for c in add_cols] if add_cols else None,
            study_multiplier=st.get("study_multiplier", 6.0),
            tolerance=st.get("tolerance"),
            process_stdev=st.get("process_stdev"),
        )
        res["analysis"] = "gage_rr_expanded"
        recipe = {
            "action": "gage_rr_expanded",
            "parameters": {
                "measurement_index": meas_idx,
                "part_index": part_idx,
                "operator_index": op_idx,
                "additional_factor_indices": add_idxs,
                "study_multiplier": st.get("study_multiplier", 6.0),
                "tolerance": st.get("tolerance"),
                "process_stdev": st.get("process_stdev"),
            },
        }
        return self._record(res["title"], res, recipe=recipe)

    def poisson_regression(self, settings=None):
        import copy
        from .poisson_regression import fit_poisson_regression
        if settings is None:
            raise ValueError("Poisson Regression requires settings.")
        st = copy.deepcopy(settings)
        resp_idx = st.get("response_index")
        cont_idxs = list(st.get("continuous_indices", []))
        cat_idxs = list(st.get("categorical_indices", []))
        off_idx = st.get("offset_index")

        if resp_idx is None:
            raise ValueError("Response variable is required.")
        if not cont_idxs and not cat_idxs:
            raise ValueError("At least one predictor is required.")

        resp_col = self.worksheet.columns[resp_idx]
        cont_cols = [self.worksheet.columns[i] for i in cont_idxs]
        cat_cols = [self.worksheet.columns[i] for i in cat_idxs]
        off_col = self.worksheet.columns[off_idx] if off_idx is not None else None

        all_cols = [resp_col] + cont_cols + cat_cols + ([off_col] if off_col else [])
        size = max(len(c.values) for c in all_cols)

        resp_vals = resp_col.numeric_values(True) + [None] * (size - len(resp_col.values))
        cont_vals = [c.numeric_values(True) + [None] * (size - len(c.values)) for c in cont_cols]
        cat_vals = [list(c.values) + [None] * (size - len(c.values)) for c in cat_cols]
        off_vals = (off_col.numeric_values(True) + [None] * (size - len(off_col.values))) if off_col else None

        res = fit_poisson_regression(
            response=resp_vals,
            continuous_predictors=cont_vals if cont_cols else None,
            categorical_predictors=cat_vals if cat_cols else None,
            continuous_names=[c.name for c in cont_cols] if cont_cols else None,
            categorical_names=[c.name for c in cat_cols] if cat_cols else None,
            offset=off_vals,
            offset_name=off_col.name if off_col else None,
            response_name=resp_col.name,
            confidence=st.get("confidence", 0.95),
        )
        res["analysis"] = "poisson_regression"
        recipe = {
            "action": "poisson_regression",
            "parameters": {
                "response_index": resp_idx,
                "continuous_indices": cont_idxs,
                "categorical_indices": cat_idxs,
                "offset_index": off_idx,
                "confidence": st.get("confidence", 0.95),
            },
        }
        return self._record(res["title"], res, recipe=recipe)


    def recode(
        self,
        source_indices: list,
        rules: list,
        target_kind: str = "number",
        storage: str = "new_columns",
        default_action: str = "original",
        default_value=None,
    ):
        from .recode import recode_column
        from .model import Column
        source_indices = list(source_indices)
        if not source_indices:
            raise ValueError("Select at least one column to recode.")
        cols = [self.worksheet.columns[i] for i in source_indices]

        recoded_columns = []
        for col in cols:
            new_vals = recode_column(
                col.values,
                rules=rules,
                target_kind=target_kind,
                default_action=default_action,
                default_value=default_value,
            )
            if storage == "original":
                col.values = new_vals
                col.kind = target_kind
                recoded_columns.append(col.name)
            else:
                new_name = f"RECODE_{col.name}" if col.name else f"RECODE_C{self.worksheet.columns.index(col)+1}"
                new_col = Column(name=new_name, kind=target_kind, values=new_vals)
                self.worksheet.columns.append(new_col)
                recoded_columns.append(new_name)

        title = f"Recode — {', '.join(c.name for c in cols)}"
        result = {
            "analysis": "recode",
            "source_columns": [c.name for c in cols],
            "recoded_columns": recoded_columns,
            "target_kind": target_kind,
            "storage": storage,
            "rules": rules,
        }
        recipe = {
            "action": "recode",
            "parameters": {
                "source_indices": source_indices,
                "rules": rules,
                "target_kind": target_kind,
                "storage": storage,
                "default_action": default_action,
                "default_value": default_value,
            },
        }
        return self._record(title, result, recipe=recipe)

    def fitted_line_plot(self, response_index, predictor_index, model_type="linear", confidence=0.95, options=None):
        from .fitted_line_plot import fit_fitted_line_plot
        if response_index == predictor_index:
            raise ValueError("Response and predictor must be different columns.")
        response = self.worksheet.columns[response_index]
        predictor = self.worksheet.columns[predictor_index]
        if response.kind != "number" or predictor.kind != "number":
            raise ValueError("Fitted Line Plot requires numeric response and predictor columns.")
        result = fit_fitted_line_plot(
            predictor.values,
            response.values,
            model_type=model_type,
            confidence=confidence,
            x_name=predictor.name,
            y_name=response.name,
            options=options,
        )
        from .connect import create_connected_fitted_line_plot
        connected = create_connected_fitted_line_plot(self.worksheet, response_index, predictor_index, result, confidence, model_type=model_type)
        entry = self._record(
            f"Fitted Line Plot: {response.name} versus {predictor.name}",
            result,
            recipe={
                "action": "fitted_line_plot",
                "parameters": {
                    "response_index": response_index,
                    "predictor_index": predictor_index,
                    "model_type": model_type,
                    "confidence": confidence,
                    "options": options or {},
                }
            }
        )
        entry["connected_analysis"] = connected.to_dict()
        return entry

    def cause_and_effect(self, branches, effect="Effect", title="", no_empty=False, no_labels=False):
        from .cause_and_effect import build_cause_and_effect
        populated_branches = []
        for b in branches:
            b_copy = dict(b)
            if not b_copy.get("causes") and b_copy.get("column_index") is not None:
                c_idx = b_copy["column_index"]
                if 0 <= c_idx < len(self.worksheet.columns):
                    col = self.worksheet.columns[c_idx]
                    b_copy["causes"] = [v for v in col.values if v is not None and str(v).strip()]
            populated_branches.append(b_copy)

        result = build_cause_and_effect(
            populated_branches,
            effect=effect,
            title=title,
            no_empty=no_empty,
            no_labels=no_labels,
        )

        from .connect import create_connected_cause_and_effect
        connected = create_connected_cause_and_effect(self.worksheet, populated_branches, result)

        entry = self._record(
            title or f"Cause-and-Effect Diagram: {effect}",
            result,
            recipe={
                "action": "cause_and_effect",
                "parameters": {
                    "branches": branches,
                    "effect": effect,
                    "title": title,
                    "no_empty": no_empty,
                    "no_labels": no_labels,
                }
            }
        )
        entry["connected_analysis"] = connected.to_dict()
        return entry

    def anom(self, response_index, factor1_index, factor2_index=None, distribution="normal", sample_size=100, alpha=0.05, title=""):
        from .anom import (
            calculate_anom_normal_1way,
            calculate_anom_normal_2way,
            calculate_anom_binomial,
            calculate_anom_poisson,
        )
        resp_col = self.worksheet.columns[response_index]
        f1_col = self.worksheet.columns[factor1_index]
        if resp_col.kind != "number":
            raise ValueError("ANOM requires a numeric response column.")
        
        f2_col = self.worksheet.columns[factor2_index] if factor2_index is not None and 0 <= factor2_index < len(self.worksheet.columns) else None

        if distribution == "normal":
            if f2_col is not None:
                result = calculate_anom_normal_2way(
                    resp_col.values, f1_col.values, f2_col.values,
                    alpha=alpha, response_name=resp_col.name,
                    factor1_name=f1_col.name, factor2_name=f2_col.name, title=title
                )
            else:
                result = calculate_anom_normal_1way(
                    resp_col.values, f1_col.values,
                    alpha=alpha, response_name=resp_col.name,
                    factor_name=f1_col.name, title=title
                )
        elif distribution == "binomial":
            result = calculate_anom_binomial(
                resp_col.values, f1_col.values, sample_size=sample_size,
                alpha=alpha, response_name=resp_col.name,
                factor_name=f1_col.name, title=title
            )
        elif distribution == "poisson":
            result = calculate_anom_poisson(
                resp_col.values, f1_col.values, sample_size=sample_size,
                alpha=alpha, response_name=resp_col.name,
                factor_name=f1_col.name, title=title
            )
        else:
            raise ValueError(f"Unsupported distribution '{distribution}'.")

        from .connect import create_connected_anom
        connected = create_connected_anom(self.worksheet, response_index, factor1_index, result, factor2_index=factor2_index, alpha=alpha)

        entry = self._record(
            title or f"Analysis of Means: {resp_col.name} by {f1_col.name}",
            result,
            recipe={
                "action": "anom",
                "parameters": {
                    "response_index": response_index,
                    "factor1_index": factor1_index,
                    "factor2_index": factor2_index,
                    "distribution": distribution,
                    "sample_size": sample_size,
                    "alpha": alpha,
                    "title": title,
                }
            }
        )
        entry["connected_analysis"] = connected.to_dict()
        return entry

    def johnson_transformation(
        self,
        column_index: int,
        store_column_name=None,
        p_threshold: float = 0.10,
    ):
        from .johnson import calculate_johnson_transformation
        from .johnson_report import generate_johnson_report
        col = self.worksheet.columns[column_index]
        if col.kind != "number":
            raise ValueError("Johnson Transformation requires a numeric data column.")

        target_store = store_column_name or f"Johnson_{col.name}"
        result = calculate_johnson_transformation(
            col.values,
            variable_name=col.name,
            p_threshold=p_threshold,
            store_column_name=target_store,
        )
        report_text = generate_johnson_report(result)
        result["report"] = report_text

        # Store transformed data into worksheet column
        trans_vals = result.get("transformed", {}).get("full_values", [])
        existing_col = next((c for c in self.worksheet.columns if c.name == target_store), None)
        if existing_col is not None:
            existing_col.values = list(trans_vals)
            existing_col.kind = "number"
        else:
            from .model import Column
            self.worksheet.columns.append(Column(name=target_store, kind="number", values=list(trans_vals)))

        from .connect import create_connected_johnson
        connected = create_connected_johnson(self.worksheet, column_index, result, p_threshold=p_threshold)

        entry = self._record(
            f"Johnson Transformation for {col.name}",
            result,
            recipe={
                "action": "johnson_transformation",
                "parameters": {
                    "column_index": column_index,
                    "store_column_name": target_store,
                    "p_threshold": p_threshold,
                }
            }
        )
        entry["connected_analysis"] = connected.to_dict()
        return entry

    def dist_id(
        self,
        column_index: int,
        distributions=None,
        subgroup_size: int = 1,
        alpha: float = 0.05,
        box_cox_lambda=None,
        johnson_p_threshold: float = 0.10,
        show_ci: bool = True,
    ):
        from .dist_id import calculate_distribution_identification
        from .dist_id_report import generate_dist_id_report
        col = self.worksheet.columns[column_index]
        if col.kind != "number":
            raise ValueError("Individual Distribution Identification requires a numeric data column.")

        result = calculate_distribution_identification(
            col.values,
            distributions=distributions,
            subgroup_size=subgroup_size,
            alpha=alpha,
            variable_name=col.name,
            box_cox_lambda=box_cox_lambda,
            johnson_p_threshold=johnson_p_threshold,
        )
        report_text = generate_dist_id_report(result)
        result["report"] = report_text

        from .connect import create_connected_dist_id
        connected = create_connected_dist_id(self.worksheet, column_index, result, alpha=alpha)

        entry = self._record(
            f"Individual Distribution Identification for {col.name}",
            result,
            recipe={
                "action": "dist_id",
                "parameters": {
                    "column_index": column_index,
                    "distributions": list(distributions) if distributions else None,
                    "subgroup_size": subgroup_size,
                    "alpha": alpha,
                    "box_cox_lambda": box_cox_lambda,
                    "johnson_p_threshold": johnson_p_threshold,
                }
            }
        )
        entry["connected_analysis"] = connected.to_dict()
        return entry

    def individuals_moving_range(self, index):
        from .quality import individuals_moving_range
        col = self.worksheet.columns[index]
        return self._record("I-MR Chart — " + col.name,
                            {"variable": col.name, **individuals_moving_range(col.numeric_values(True))},
                            recipe={"action":"individuals_moving_range", "parameters":{"index":index}})

    def _bound_settings(self, action, settings):
        """Resolve saved source identities before an analysis reads any data."""
        if settings is None:
            return None
        from .analysis_bindings import normalize
        return normalize(action, self.worksheet, settings)

    def imr_chart(self, settings=None):
        settings = self._bound_settings("imr_chart", settings)
        from .imr_engine import run_imr_chart
        if settings is None:
            raise ValueError("I-MR Chart requires analysis settings.")
        vars_list = settings.get("variables", [])
        if not vars_list:
            raise ValueError("Select at least one variable for I-MR Chart.")
        opts = settings.get("options", {})

        last_entry = None
        for idx in vars_list:
            if idx < 0 or idx >= len(self.worksheet.columns):
                raise ValueError(f"Invalid column index: {idx}")
            col = self.worksheet.columns[idx]
            if col.kind != "number":
                raise ValueError(f"Column '{col.name}' must be numeric.")
            res = run_imr_chart(col.values, options=opts, variable_name=col.name)
            entry = self._record(
                f"I-MR Chart of {col.name}",
                {"variable": col.name, **res},
                recipe={"action": "imr_chart", "parameters": {"settings": {"variables": [idx], "options": dict(opts)}}},
            )
            last_entry = entry
        return last_entry

    def attribute_control_chart(self, settings=None):
        settings = self._bound_settings("attribute_control_chart", settings)
        from .attribute_control_engine import run_attribute_control
        if settings is None:
            raise ValueError("Attribute Control Chart requires analysis settings.")
        chart_type = settings.get("chart_type", "P").upper()
        vars_list = settings.get("variables", [])
        if not vars_list:
            raise ValueError(f"Select at least one variable for {chart_type} Chart.")
        opts = settings.get("options", {})

        is_subgroup_col = settings.get("is_subgroup_col", False)
        subgroup_col_idx = settings.get("subgroup_col_idx")
        subgroup_size_const = settings.get("subgroup_size")
        subgroup_size_name = None
        subgroup_sizes = None

        if is_subgroup_col and subgroup_col_idx is not None:
            if subgroup_col_idx < 0 or subgroup_col_idx >= len(self.worksheet.columns):
                raise ValueError(f"Invalid subgroup size column index: {subgroup_col_idx}")
            size_col = self.worksheet.columns[subgroup_col_idx]
            subgroup_sizes = size_col.numeric_values(True)
            subgroup_size_name = size_col.name
        elif subgroup_size_const is not None:
            subgroup_sizes = float(subgroup_size_const)
        elif chart_type == "C":
            subgroup_sizes = 1.0

        last_entry = None
        for idx in vars_list:
            if idx < 0 or idx >= len(self.worksheet.columns):
                raise ValueError(f"Invalid column index: {idx}")
            col = self.worksheet.columns[idx]
            if col.kind != "number":
                raise ValueError(f"Column '{col.name}' must be numeric.")
            res = run_attribute_control(
                chart_type=chart_type,
                counts=col.numeric_values(True),
                sample_sizes=subgroup_sizes,
                options=opts,
                variable_name=col.name,
                subgroup_size_name=subgroup_size_name,
            )
            entry = self._record(
                f"{chart_type} Chart of {col.name}",
                {"variable": col.name, **res},
                recipe={"action": "attribute_control_chart", "parameters": {"settings": {
                    "chart_type": chart_type,
                    "variables": [idx],
                    "subgroup_size": subgroup_size_const,
                    "subgroup_col_idx": subgroup_col_idx,
                    "is_subgroup_col": is_subgroup_col,
                    "options": dict(opts),
                }}},
            )
            last_entry = entry
        return last_entry

    def time_weighted_control_chart(self, settings=None):
        settings = self._bound_settings("time_weighted_control_chart", settings)
        import copy
        from .time_weighted_control_engine import run_ewma_control, run_moving_average_control, run_cusum_control
        if settings is None:
            raise ValueError("Time-Weighted Control Chart requires analysis settings.")
        chart_type = settings.get("chart_type", "EWMA").upper()
        cols = settings.get("columns", [])
        if not cols:
            raise ValueError(f"Select at least one variable for {chart_type} Chart.")
        arranged_mode = settings.get("arranged_mode", 0)
        subgroup_spec = settings.get("subgroup_spec", 1)
        subgroup_text = settings.get("subgroup_text")
        opts = settings.get("options", {})

        last_entry = None
        def _get_vals(name_or_idx):
            if isinstance(name_or_idx, int) and 0 <= name_or_idx < len(self.worksheet.columns):
                return self.worksheet.columns[name_or_idx].values
            for col in self.worksheet.columns:
                if col.name == name_or_idx:
                    return col.values
            return []

        if arranged_mode == 1:
            data_cols = [_get_vals(c) for c in cols]
            var_name = ", ".join(str(c) for c in cols)
            if chart_type == "EWMA":
                res = run_ewma_control(
                    data=[],
                    weight=settings.get("weight", 0.2),
                    options=opts,
                    variable_name=var_name,
                    rows_are_subgroups=True,
                    data_columns=data_cols,
                )
            elif chart_type in ("MA", "MOVING_AVERAGE"):
                res = run_moving_average_control(
                    data=[],
                    span=settings.get("span", 3),
                    options=opts,
                    variable_name=var_name,
                    rows_are_subgroups=True,
                    data_columns=data_cols,
                )
            else:
                res = run_cusum_control(
                    data=[],
                    target=settings.get("target"),
                    options=opts,
                    variable_name=var_name,
                    rows_are_subgroups=True,
                    data_columns=data_cols,
                )
            entry = self._record(
                f"{chart_type} Chart of {var_name}",
                {"variable": var_name, **res},
                recipe={"action": "time_weighted_control_chart", "parameters": {"settings": copy.deepcopy(settings)}},
            )
            return entry
        else:
            for c in cols:
                data_vals = _get_vals(c)
                if chart_type == "EWMA":
                    res = run_ewma_control(
                        data=data_vals,
                        subgroup_size=subgroup_spec,
                        weight=settings.get("weight", 0.2),
                        options=opts,
                        variable_name=c,
                        subgroup_size_name=subgroup_text if isinstance(subgroup_spec, list) else None,
                    )
                elif chart_type in ("MA", "MOVING_AVERAGE"):
                    res = run_moving_average_control(
                        data=data_vals,
                        subgroup_size=subgroup_spec,
                        span=settings.get("span", 3),
                        options=opts,
                        variable_name=c,
                        subgroup_size_name=subgroup_text if isinstance(subgroup_spec, list) else None,
                    )
                else:
                    res = run_cusum_control(
                        data=data_vals,
                        subgroup_size=subgroup_spec,
                        target=settings.get("target"),
                        options=opts,
                        variable_name=c,
                        subgroup_size_name=subgroup_text if isinstance(subgroup_spec, list) else None,
                    )
                entry = self._record(
                    f"{chart_type} Chart of {c}",
                    {"variable": c, **res},
                    recipe={"action": "time_weighted_control_chart", "parameters": {"settings": {
                        **copy.deepcopy(settings),
                        "columns": [c],
                    }}},
                )
                last_entry = entry
            return last_entry

    def rare_event_control_chart(self, settings=None):
        settings = self._bound_settings("rare_event_control_chart", settings)
        import copy
        from .rare_event_control_engine import run_g_chart, run_t_chart
        if settings is None:
            raise ValueError("Rare Event Control Chart requires analysis settings.")
        chart_type = settings.get("chart_type", "G").upper()
        cols = settings.get("columns", [])
        if not cols:
            raise ValueError(f"Select at least one variable for {chart_type} Chart.")
        form_of_data = int(settings.get("form_of_data", 1))
        opts = settings.get("options", {})

        def _get_vals(name_or_idx):
            if isinstance(name_or_idx, int) and 0 <= name_or_idx < len(self.worksheet.columns):
                return self.worksheet.columns[name_or_idx].values
            for col in self.worksheet.columns:
                if col.name == name_or_idx:
                    return col.values
            return []

        last_entry = None
        for c in cols:
            data_vals = _get_vals(c)
            if chart_type == "G":
                res = run_g_chart(
                    data=data_vals,
                    form_of_data=form_of_data,
                    method_of_count=settings.get("method_of_count", 0),
                    options=opts,
                    variable_name=str(c),
                )
            else:
                res = run_t_chart(
                    data=data_vals,
                    form_of_data=form_of_data,
                    distribution=opts.get("distribution", "Weibull"),
                    units=settings.get("units", "Days") or "Days",
                    options=opts,
                    variable_name=str(c),
                )
            entry = self._record(
                f"{chart_type} Chart of {c}",
                {"variable": str(c), **res},
                recipe={"action": "rare_event_control_chart", "parameters": {"settings": {
                    **copy.deepcopy(settings),
                    "columns": [c],
                }}},
            )
            last_entry = entry
        return last_entry

    def multivariate_control_chart(self, settings=None):
        settings = self._bound_settings("multivariate_control_chart", settings)
        import copy
        from .multivariate_control_engine import run_tsquared_control, run_genvar_control, run_mewma_control
        if settings is None:
            raise ValueError("Multivariate Control Chart requires analysis settings.")
        chart_type = settings.get("chart_type", "TSQUARED").upper()
        cols = settings.get("variables") or settings.get("columns", [])
        if len(cols) < 2:
            raise ValueError("Multivariate control charts require at least two variables.")

        def _get_col_vals(c):
            if isinstance(c, int) and 0 <= c < len(self.worksheet.columns):
                return self.worksheet.columns[c].values
            for col in self.worksheet.columns:
                if col.name == c:
                    return col.values
            return []

        col_data = [_get_col_vals(c) for c in cols]
        sg_spec = settings.get("subgroup_size", 1)
        if isinstance(sg_spec, str) and not sg_spec.isdigit():
            sg_vals = _get_col_vals(sg_spec)
            if sg_vals:
                sg_spec = sg_vals

        opts = settings.get("options", {})
        var_names = [str(c) for c in cols]

        if chart_type == "TSQUARED":
            res = run_tsquared_control(
                columns_data=col_data,
                subgroup_size=sg_spec,
                alpha=float(opts.get("alpha", 0.0027)),
                options=opts,
                variable_names=var_names,
            )
            title = f"T² Chart of {', '.join(var_names)}"
        elif chart_type == "GENVAR":
            res = run_genvar_control(
                columns_data=col_data,
                subgroup_size=sg_spec,
                options=opts,
                variable_names=var_names,
            )
            title = f"Generalized Variance Chart of {', '.join(var_names)}"
        elif chart_type == "MEWMA":
            res = run_mewma_control(
                columns_data=col_data,
                subgroup_size=sg_spec,
                weight=float(opts.get("weight", 0.1)),
                arl=float(opts.get("arl", 200.0)),
                options=opts,
                variable_names=var_names,
            )
            title = f"Multivariate EWMA Chart of {', '.join(var_names)}"
        else:
            raise ValueError(f"Unknown multivariate chart type: {chart_type}")

        entry = self._record(
            title,
            {"variables": var_names, **res},
            recipe={"action": "multivariate_control_chart", "parameters": {"settings": copy.deepcopy(settings)}},
        )
        return entry

    def pareto_chart(self, settings=None):
        settings = self._bound_settings("pareto_chart", settings)
        import copy
        from .pareto_engine import run_pareto_chart
        if settings is None:
            raise ValueError("Pareto Chart requires analysis settings.")

        def _get_col_vals(name_or_idx):
            if isinstance(name_or_idx, int) and 0 <= name_or_idx < len(self.worksheet.columns):
                return self.worksheet.columns[name_or_idx].values
            for col in self.worksheet.columns:
                if col.name == name_or_idx:
                    return col.values
            return []

        is_summ = bool(settings.get("is_summarized", False))
        defect_col = settings.get("defect_column")
        defect_vals = _get_col_vals(defect_col)

        count_vals = None
        if is_summ:
            count_col = settings.get("count_column")
            count_vals = _get_col_vals(count_col)

        by_col = settings.get("by_column")
        by_vals = _get_col_vals(by_col) if by_col is not None and by_col != "" else None

        combine_pct = settings.get("combine_percent", 95.0)
        show_cum = bool(settings.get("show_cumulative", True))

        res = run_pareto_chart(
            defect_data=defect_vals,
            count_data=count_vals,
            by_data=by_vals,
            combine_percent=combine_pct,
            show_cumulative=show_cum,
            chart_title=settings.get("title") or f"Pareto Chart of {self.worksheet.columns[defect_col].name}",
            variable_name=self.worksheet.columns[defect_col].name,
        )

        defect_name = self.worksheet.columns[defect_col].name if type(defect_col) is int else str(defect_col)
        title = f"Pareto Chart of {defect_name}"
        entry = self._record(
            title,
            {"variable": defect_name, **res},
            recipe={"action": "pareto_chart", "parameters": {"settings": copy.deepcopy(settings)}},
        )
        return entry

    def type1_gage(self, measurement_index, reference, settings=None, measurement_name=None):
        import copy
        from .type1_gage import compute_type1_gage
        if not (0 <= measurement_index < len(self.worksheet.columns)):
            raise ValueError("Measurement column index out of range.")
        col = self.worksheet.columns[measurement_index]
        if col.kind != "number":
            raise ValueError("Type 1 Gage Study requires a numeric measurement column.")
        name = measurement_name or col.name or f"C{measurement_index+1}"
        res = compute_type1_gage(col.values, reference, settings=settings)
        res["analysis"] = "type1_gage"
        res["graph"] = "type1_gage"
        title = f"Type 1 Gage Study for {name}"
        recipe = {
            "action": "type1_gage",
            "parameters": {
                "measurement_index": measurement_index,
                "measurement_name": name,
                "reference": float(reference),
                "settings": copy.deepcopy(settings or {})
            }
        }
        return self._record(title, res, recipe=recipe)

    def attribute_gage(self, ref_index, acc_index, trials=20, part_index=None, settings=None, ref_name=None, acc_name=None, part_name=None, trials_index=None):
        import copy
        from .attribute_gage import compute_attribute_gage_study
        if not (0 <= ref_index < len(self.worksheet.columns)):
            raise ValueError("Reference column index out of range.")
        if not (0 <= acc_index < len(self.worksheet.columns)):
            raise ValueError("Acceptances column index out of range.")
        ref_col = self.worksheet.columns[ref_index]
        acc_col = self.worksheet.columns[acc_index]
        if ref_col.kind != "number":
            raise ValueError("Attribute Gage Study requires a numeric reference column.")
        if acc_col.kind != "number":
            raise ValueError("Attribute Gage Study requires a numeric acceptances column.")

        trials_val = trials
        if trials_index is not None and 0 <= trials_index < len(self.worksheet.columns):
            trials_val = self.worksheet.columns[trials_index].values
        elif isinstance(trials, int) and 0 <= trials < len(self.worksheet.columns) and trials != 20:
            trials_index = trials
            trials_val = self.worksheet.columns[trials].values

        part_vals = None
        if part_index is not None and 0 <= part_index < len(self.worksheet.columns):
            part_vals = self.worksheet.columns[part_index].values

        r_name = ref_name or ref_col.name or f"C{ref_index+1}"
        a_name = acc_name or acc_col.name or f"C{acc_index+1}"
        p_name = part_name or (self.worksheet.columns[part_index].name if part_index is not None and 0 <= part_index < len(self.worksheet.columns) else None)

        res = compute_attribute_gage_study(ref_col.values, acc_col.values, trials=trials_val, part_labels=part_vals, settings=settings)
        res["analysis"] = "attribute_gage"
        res["graph"] = "attribute_gage"
        title = f"Attribute Gage Study for {r_name}"

        recipe = {
            "action": "attribute_gage",
            "parameters": {
                "ref_index": ref_index,
                "acc_index": acc_index,
                "trials": trials if trials_index is None else trials_index,
                "trials_index": trials_index,
                "part_index": part_index,
                "ref_name": r_name,
                "acc_name": a_name,
                "part_name": p_name,
                "settings": copy.deepcopy(settings or {}),
            }
        }
        return self._record(title, res, recipe=recipe)

    def symmetry_plot(self, column_index=0, settings=None, column_name=None):
        import copy
        from .symmetry_plot import compute_symmetry_plot
        if not (0 <= column_index < len(self.worksheet.columns)):
            raise ValueError(f"Invalid column index {column_index} for Symmetry Plot.")
        col = self.worksheet.columns[column_index]
        if col.kind != "number":
            raise ValueError("Symmetry Plot requires a numeric column.")
        c_name = column_name or col.name or f"C{column_index+1}"
        res = compute_symmetry_plot(col.values, settings=settings)
        res["analysis"] = "symmetry_plot"
        res["graph"] = "symmetry_plot"
        res["column_index"] = column_index
        res["column_name"] = c_name
        title = f"Symmetry Plot for {c_name}"
        recipe = {
            "action": "symmetry_plot",
            "parameters": {
                "column_index": column_index,
                "column_name": c_name,
                "settings": copy.deepcopy(settings or {}),
            }
        }
        return self._record(title, res, recipe=recipe)

    def acceptance_sampling_attributes(self, settings=None):
        import copy
        from .acceptance_sampling import compute_acceptance_sampling_attributes
        st = copy.deepcopy(settings or {})
        res = compute_acceptance_sampling_attributes(settings=st)
        res["analysis"] = "acceptance_sampling_attributes"
        res["graph"] = "acceptance_sampling_attributes"
        n = res["sample_size"]
        c = res["acceptance_number"]
        title = f"Acceptance Sampling by Attributes (n={n}, c={c})"
        recipe = {
            "action": "acceptance_sampling_attributes",
            "parameters": {
                "settings": st,
            }
        }
        return self._record(title, res, recipe=recipe)

    def acceptance_sampling_variables(self, settings=None):
        import copy
        from .acceptance_sampling_variables import solve_variables_sampling_plan
        st = copy.deepcopy(settings or {})
        res = solve_variables_sampling_plan(
            aql=st.get("aql", 0.015),
            rql=st.get("rql", 0.05),
            alpha=st.get("alpha", 0.05),
            beta=st.get("beta", 0.10),
            lsl=st.get("lsl"),
            usl=st.get("usl"),
            sigma=st.get("sigma"),
            lot_size=st.get("lot_size"),
        )
        res["analysis"] = "acceptance_sampling_variables"
        res["graph"] = "acceptance_sampling_variables"
        title = "Acceptance Sampling by Variables"
        recipe = {
            "action": "acceptance_sampling_variables",
            "parameters": {
                "settings": st,
            }
        }
        return self._record(title, res, recipe=recipe)

    def tolerance_intervals(self, settings=None):
        settings = self._bound_settings("tolerance_intervals", settings)
        import copy
        from .tolerance_intervals import compute_tolerance_interval
        if settings is None:
            raise ValueError("Tolerance intervals require settings.")
        st = copy.deepcopy(settings)
        is_summ = bool(st.get("is_summarized", False))
        if is_summ:
            res = compute_tolerance_interval(
                n=st.get("n"),
                mean=st.get("mean"),
                std=st.get("std"),
                settings=st.get("settings"),
                variable_name="Summarized Data"
            )
            var_name = "Summarized Data"
        else:
            v_indices = st.get("variable_indices", [])
            if not v_indices:
                raise ValueError("No variable columns specified for tolerance intervals.")
            idx = v_indices[0]
            col = self.worksheet.columns[idx]
            var_name = col.name or f"C{idx+1}"
            res = compute_tolerance_interval(
                raw_data=col.values,
                settings=st.get("settings"),
                variable_name=var_name
            )
        res["analysis"] = "tolerance_intervals"
        res["graph"] = "tolerance_intervals"
        title = f"Tolerance Intervals for {var_name}"
        recipe = {
            "action": "tolerance_intervals",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def trend_analysis(self, settings=None):
        settings = self._bound_settings("trend_analysis", settings)
        import copy
        from .time_series import trend_analysis
        from .model import Column
        if settings is None:
            raise ValueError("Trend Analysis requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Trend Analysis requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = trend_analysis(
            values=col.values,
            model=st.get("model", "linear"),
            forecasts=st.get("forecasts", 0),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "trend_analysis"
        res["graph"] = "trend_analysis"
        title = res["title"]

        if st.get("store_fits"):
            self.worksheet.columns.append(Column(name=f"FITS_{var_name}", kind="number", values=res["fitted"]))
        if st.get("store_residuals"):
            self.worksheet.columns.append(Column(name=f"RESI_{var_name}", kind="number", values=res["residuals"]))
        if st.get("store_forecasts") and res["forecasts"]:
            fc_vals = [f["forecast"] for f in res["forecasts"]]
            self.worksheet.columns.append(Column(name=f"FORE_{var_name}", kind="number", values=fc_vals))

        recipe = {
            "action": "trend_analysis",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def decomposition(self, settings=None):
        settings = self._bound_settings("decomposition", settings)
        import copy
        from .time_series import decomposition
        from .model import Column
        if settings is None:
            raise ValueError("Decomposition requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Decomposition requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = decomposition(
            values=col.values,
            season_length=st.get("season_length", 4),
            model=st.get("model", "multiplicative"),
            forecasts=st.get("forecasts", 0),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "decomposition"
        res["graph"] = "decomposition"
        title = res["title"]

        if st.get("store_fits"):
            self.worksheet.columns.append(Column(name=f"FITS_{var_name}", kind="number", values=res["fitted"]))
        if st.get("store_residuals"):
            self.worksheet.columns.append(Column(name=f"RESI_{var_name}", kind="number", values=res["residuals"]))
        if st.get("store_forecasts") and res["forecasts"]:
            fc_vals = [f["forecast"] for f in res["forecasts"]]
            self.worksheet.columns.append(Column(name=f"FORE_{var_name}", kind="number", values=fc_vals))

        recipe = {
            "action": "decomposition",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def moving_average(self, settings=None):
        settings = self._bound_settings("moving_average", settings)
        import copy
        from .time_series import moving_average
        from .model import Column
        if settings is None:
            raise ValueError("Moving Average requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Moving Average requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = moving_average(
            values=col.values,
            ma_length=st.get("ma_length", 3),
            center=st.get("center", False),
            forecasts=st.get("forecasts", 0),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "moving_average"
        res["graph"] = "moving_average"
        title = res["title"]

        if st.get("store_fits"):
            self.worksheet.columns.append(Column(name=f"SMOO_{var_name}", kind="number", values=res["fitted"]))
        if st.get("store_residuals"):
            self.worksheet.columns.append(Column(name=f"RESI_{var_name}", kind="number", values=res["residuals"]))
        if st.get("store_forecasts") and res["forecasts"]:
            fc_vals = [f["forecast"] for f in res["forecasts"]]
            self.worksheet.columns.append(Column(name=f"FORE_{var_name}", kind="number", values=fc_vals))

        recipe = {
            "action": "moving_average",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def single_exp_smoothing(self, settings=None):
        settings = self._bound_settings("single_exp_smoothing", settings)
        import copy
        from .time_series import single_exp_smoothing
        from .model import Column
        if settings is None:
            raise ValueError("Single Exponential Smoothing requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Single Exponential Smoothing requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = single_exp_smoothing(
            values=col.values,
            alpha=st.get("alpha"),
            forecasts=st.get("forecasts", 0),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "single_exp_smoothing"
        res["graph"] = "single_exp_smoothing"
        title = res["title"]

        if st.get("store_fits"):
            self.worksheet.columns.append(Column(name=f"SMOO_{var_name}", kind="number", values=res["fitted"]))
        if st.get("store_residuals"):
            self.worksheet.columns.append(Column(name=f"RESI_{var_name}", kind="number", values=res["residuals"]))
        if st.get("store_forecasts") and res["forecasts"]:
            fc_vals = [f["forecast"] for f in res["forecasts"]]
            self.worksheet.columns.append(Column(name=f"FORE_{var_name}", kind="number", values=fc_vals))

        recipe = {
            "action": "single_exp_smoothing",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def double_exp_smoothing(self, settings=None):
        settings = self._bound_settings("double_exp_smoothing", settings)
        import copy
        from .time_series import double_exp_smoothing
        from .model import Column
        if settings is None:
            raise ValueError("Double Exponential Smoothing requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Double Exponential Smoothing requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = double_exp_smoothing(
            values=col.values,
            alpha=st.get("alpha"),
            gamma=st.get("gamma"),
            forecasts=st.get("forecasts", 0),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "double_exp_smoothing"
        res["graph"] = "double_exp_smoothing"
        title = res["title"]

        if st.get("store_fits"):
            self.worksheet.columns.append(Column(name=f"SMOO_{var_name}", kind="number", values=res["fitted"]))
        if st.get("store_residuals"):
            self.worksheet.columns.append(Column(name=f"RESI_{var_name}", kind="number", values=res["residuals"]))
        if st.get("store_forecasts") and res["forecasts"]:
            fc_vals = [f["forecast"] for f in res["forecasts"]]
            self.worksheet.columns.append(Column(name=f"FORE_{var_name}", kind="number", values=fc_vals))

        recipe = {
            "action": "double_exp_smoothing",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def winters_method(self, settings=None):
        settings = self._bound_settings("winters_method", settings)
        import copy
        from .winters_method import winters_method
        from .model import Column
        if settings is None:
            raise ValueError("Winters' Method requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Winters' Method requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = winters_method(
            values=col.values,
            season_length=st.get("season_length", 4),
            model=st.get("model", "multiplicative"),
            alpha=st.get("alpha"),
            gamma=st.get("gamma"),
            delta=st.get("delta"),
            forecasts=st.get("forecasts", 0),
            conf_level=st.get("conf_level", 95.0),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "winters_method"
        res["graph"] = "winters_method"
        title = res["title"]

        if st.get("store_fits"):
            self.worksheet.columns.append(Column(name=f"SMOO_{var_name}", kind="number", values=res["fitted"]))
        if st.get("store_residuals"):
            self.worksheet.columns.append(Column(name=f"RESI_{var_name}", kind="number", values=res["residuals"]))
        if st.get("store_forecasts") and res["forecasts"]:
            fc_vals = [f["forecast"] for f in res["forecasts"]]
            self.worksheet.columns.append(Column(name=f"FORE_{var_name}", kind="number", values=fc_vals))

        recipe = {
            "action": "winters_method",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def arima(self, settings=None):
        settings = self._bound_settings("arima", settings)
        import copy
        from .arima import fit_arima
        from .model import Column
        if settings is None:
            raise ValueError("ARIMA requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("ARIMA requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = fit_arima(
            values=col.values,
            p=st.get("p", 1),
            d=st.get("d", 0),
            q=st.get("q", 0),
            P=st.get("P", 0),
            D=st.get("D", 0),
            Q=st.get("Q", 0),
            S=st.get("S", 1),
            include_constant=st.get("include_constant", True),
            forecasts=st.get("forecasts", 0),
            conf_level=st.get("conf_level", 95.0),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "arima"
        res["graph"] = "arima"
        title = res["title"]

        if st.get("store_fits"):
            self.worksheet.columns.append(Column(name=f"FITT_{var_name}", kind="number", values=res["fitted"]))
        if st.get("store_residuals"):
            self.worksheet.columns.append(Column(name=f"RESI_{var_name}", kind="number", values=res["residuals"]))
        if st.get("store_forecasts") and res["forecasts"]:
            fc_vals = [f["forecast"] for f in res["forecasts"]]
            self.worksheet.columns.append(Column(name=f"FORE_{var_name}", kind="number", values=fc_vals))

        recipe = {
            "action": "arima",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def autocorrelation(self, settings=None):
        settings = self._bound_settings("autocorrelation", settings)
        import copy
        from .time_series import autocorrelation
        if settings is None:
            raise ValueError("Autocorrelation requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Autocorrelation requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = autocorrelation(
            values=col.values,
            max_lags=st.get("max_lags"),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "autocorrelation"
        res["graph"] = "autocorrelation"
        title = res["title"]
        recipe = {
            "action": "autocorrelation",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def cross_correlation(self, first_index, second_index, lags=0, title=None, store_ccf=False):
        from .time_series import cross_correlation
        indices = (first_index, second_index)
        if first_index == second_index or any(type(i) is not int or not 0 <= i < len(self.worksheet.columns) for i in indices):
            raise ValueError("Choose two distinct numeric series.")
        first, second = (self.worksheet.columns[i] for i in indices)
        if first.kind != "number" or second.kind != "number":
            raise ValueError("Choose two numeric series.")
        result = cross_correlation(first.values, second.values, lags)
        if (title is not None and (not isinstance(title, str) or len(title) > 200)
                or type(store_ccf) is not bool):
            raise ValueError("Choose a title up to 200 characters and a valid storage option.")
        custom_title = (title or "").strip()
        title = custom_title or f"Cross Correlation Function for {first.name}, {second.name}"
        result.update(title=title, first_name=first.name, second_name=second.name,
                      xlabel="Lag", ylabel="Cross correlation")
        recipe = {"action": "cross_correlation",
                  "parameters": {"first_index": first_index, "second_index": second_index,
                                 "lags": lags, "title": custom_title or None, "store_ccf": store_ccf}}
        if store_ccf:
            result["stored_column"] = self._store_cross_correlations(result["lags"])
        return self._record(title, result, recipe=recipe)

    @undoable
    def _store_cross_correlations(self, lags):
        columns = self.worksheet.columns
        if max(self.worksheet.row_count, len(lags)) * (len(columns) + 1) > io.MAX_CELLS:
            raise ValueError("Storing the cross correlations would exceed the worksheet cell limit.")
        names = {column.name.casefold() for column in columns}
        name = "CCF"
        suffix = 1
        while name.casefold() in names:
            name = f"CCF{suffix}"
            suffix += 1
        column = Column(name, "number", [row["correlation"] for row in lags])
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            from .mpx_columns import independent_metadata
            column.metadata = independent_metadata()
        columns.append(column)
        self.dirty = True
        return name

    def partial_autocorrelation(self, settings=None):
        settings = self._bound_settings("partial_autocorrelation", settings)
        import copy
        from .time_series import partial_autocorrelation
        if settings is None:
            raise ValueError("Partial Autocorrelation requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Partial Autocorrelation requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        res = partial_autocorrelation(
            values=col.values,
            max_lags=st.get("max_lags"),
            variable_name=var_name,
            title=st.get("title", ""),
        )
        res["analysis"] = "partial_autocorrelation"
        res["graph"] = "partial_autocorrelation"
        title = res["title"]
        recipe = {
            "action": "partial_autocorrelation",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(title, res, recipe=recipe)

    def differences(self, settings=None):
        settings = self._bound_settings("differences", settings)
        import copy
        from .time_series import compute_differences
        from .model import Column
        if settings is None:
            raise ValueError("Differences requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Differences requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        lag = st.get("lag", 1)
        store_name = st.get("store_col") or f"DIFF_{var_name}"
        diff_vals = compute_differences(col.values, lag=lag)
        self.worksheet.columns.append(Column(name=store_name, kind="number", values=diff_vals))
        res = {
            "analysis": "differences",
            "variable_name": var_name,
            "lag": lag,
            "store_col": store_name,
            "title": f"Differences of {var_name}",
        }
        recipe = {
            "action": "differences",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def lag(self, settings=None):
        settings = self._bound_settings("lag", settings)
        import copy
        from .time_series import compute_lag
        from .model import Column
        if settings is None:
            raise ValueError("Lag requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("series_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("Lag requires a valid series column.")
        col = self.worksheet.columns[idx]
        var_name = col.name or f"C{idx+1}"
        lag_k = st.get("lag", 1)
        store_name = st.get("store_col") or f"LAG_{var_name}"
        lag_vals = compute_lag(col.values, lag=lag_k)
        self.worksheet.columns.append(Column(name=store_name, kind="number", values=lag_vals))
        res = {
            "analysis": "lag",
            "variable_name": var_name,
            "lag": lag_k,
            "store_col": store_name,
            "title": f"Lag of {var_name}",
        }
        recipe = {
            "action": "lag",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def sign_test(self, settings=None):
        settings = self._bound_settings("sign_test", settings)
        import copy
        from .nonparametrics import sign_test
        if settings is None:
            raise ValueError("Sign Test requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if not indices:
            raise ValueError("Sign Test requires at least one variable.")
        last_rec = None
        for idx in indices:
            if not (0 <= idx < len(self.worksheet.columns)):
                continue
            col = self.worksheet.columns[idx]
            var_name = col.name or f"C{idx+1}"
            res = sign_test(
                data=col.values,
                test_median=st.get("test_median", 0.0),
                alternative=st.get("alternative", "two_sided"),
                conf_level=st.get("conf_level", 0.95),
            )
            res["variable_name"] = var_name
            res["title"] = f"Sign Test for Median: {var_name}"
            recipe = {
                "action": "sign_test",
                "parameters": {
                    "settings": copy.deepcopy(settings)
                }
            }
            last_rec = self._record(res["title"], res, recipe=recipe)
        return last_rec

    def one_sample_wilcoxon(self, settings=None):
        settings = self._bound_settings("one_sample_wilcoxon", settings)
        import copy
        from .nonparametrics import one_sample_wilcoxon
        if settings is None:
            raise ValueError("1-Sample Wilcoxon requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if not indices:
            raise ValueError("1-Sample Wilcoxon requires at least one variable.")
        last_rec = None
        for idx in indices:
            if not (0 <= idx < len(self.worksheet.columns)):
                continue
            col = self.worksheet.columns[idx]
            var_name = col.name or f"C{idx+1}"
            res = one_sample_wilcoxon(
                data=col.values,
                test_median=st.get("test_median", 0.0),
                alternative=st.get("alternative", "two_sided"),
                conf_level=st.get("conf_level", 0.95),
            )
            res["variable_name"] = var_name
            res["title"] = f"Wilcoxon Signed Rank Test: {var_name}"
            recipe = {
                "action": "one_sample_wilcoxon",
                "parameters": {
                    "settings": copy.deepcopy(settings)
                }
            }
            last_rec = self._record(res["title"], res, recipe=recipe)
        return last_rec

    def mann_whitney(self, settings=None):
        settings = self._bound_settings("mann_whitney", settings)
        import copy
        from .nonparametrics import mann_whitney
        if settings is None:
            raise ValueError("Mann-Whitney requires settings.")
        st = copy.deepcopy(settings)
        i1 = st.get("first_index")
        i2 = st.get("second_index")
        if i1 is None or i2 is None or not (0 <= i1 < len(self.worksheet.columns)) or not (0 <= i2 < len(self.worksheet.columns)):
            raise ValueError("Mann-Whitney requires valid first and second sample columns.")
        col1 = self.worksheet.columns[i1]
        col2 = self.worksheet.columns[i2]
        name1 = col1.name or f"C{i1+1}"
        name2 = col2.name or f"C{i2+1}"
        res = mann_whitney(
            sample1=col1.values,
            sample2=col2.values,
            test_diff=st.get("test_diff", 0.0),
            alternative=st.get("alternative", "two_sided"),
            conf_level=st.get("conf_level", 0.95),
        )
        res["name1"] = name1
        res["name2"] = name2
        res["graph"] = "mann_whitney"
        res["title"] = f"Mann-Whitney Test and CI: {name1}, {name2}"
        recipe = {
            "action": "mann_whitney",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def kruskal_wallis(self, settings=None):
        settings = self._bound_settings("kruskal_wallis", settings)
        import copy
        from .nonparametrics import kruskal_wallis
        if settings is None:
            raise ValueError("Kruskal-Wallis requires settings.")
        st = copy.deepcopy(settings)
        ri = st.get("response_index")
        fi = st.get("factor_index")
        if ri is None or fi is None or not (0 <= ri < len(self.worksheet.columns)) or not (0 <= fi < len(self.worksheet.columns)):
            raise ValueError("Kruskal-Wallis requires valid Response and Factor columns.")
        r_col = self.worksheet.columns[ri]
        f_col = self.worksheet.columns[fi]
        r_name = r_col.name or f"C{ri+1}"
        f_name = f_col.name or f"C{fi+1}"
        res = kruskal_wallis(response=r_col.values, factor=f_col.values)
        res["response_name"] = r_name
        res["factor_name"] = f_name
        res["graph"] = "kruskal_wallis"
        res["title"] = f"Kruskal-Wallis Test: {r_name} versus {f_name}"
        recipe = {
            "action": "kruskal_wallis",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def moods_median(self, settings=None):
        settings = self._bound_settings("moods_median", settings)
        import copy
        from .nonparametrics import moods_median
        if settings is None:
            raise ValueError("Mood's Median requires settings.")
        st = copy.deepcopy(settings)
        ri = st.get("response_index")
        fi = st.get("factor_index")
        if ri is None or fi is None or not (0 <= ri < len(self.worksheet.columns)) or not (0 <= fi < len(self.worksheet.columns)):
            raise ValueError("Mood's Median requires valid Response and Factor columns.")
        r_col = self.worksheet.columns[ri]
        f_col = self.worksheet.columns[fi]
        r_name = r_col.name or f"C{ri+1}"
        f_name = f_col.name or f"C{fi+1}"
        res = moods_median(response=r_col.values, factor=f_col.values, conf_level=st.get("conf_level", 0.95))
        res["response_name"] = r_name
        res["factor_name"] = f_name
        res["graph"] = "moods_median"
        res["title"] = f"Mood's Median Test: {r_name} versus {f_name}"
        recipe = {
            "action": "moods_median",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def friedman_test(self, settings=None):
        settings = self._bound_settings("friedman_test", settings)
        import copy
        from .nonparametrics import friedman_test
        if settings is None:
            raise ValueError("Friedman Test requires settings.")
        st = copy.deepcopy(settings)
        ri = st.get("response_index")
        ti = st.get("treatment_index")
        bi = st.get("block_index")
        if ri is None or ti is None or bi is None or not (0 <= ri < len(self.worksheet.columns)) or not (0 <= ti < len(self.worksheet.columns)) or not (0 <= bi < len(self.worksheet.columns)):
            raise ValueError("Friedman Test requires valid Response, Treatment, and Block columns.")
        r_col = self.worksheet.columns[ri]
        t_col = self.worksheet.columns[ti]
        b_col = self.worksheet.columns[bi]
        r_name = r_col.name or f"C{ri+1}"
        t_name = t_col.name or f"C{ti+1}"
        b_name = b_col.name or f"C{bi+1}"
        res = friedman_test(response=r_col.values, treatment=t_col.values, block=b_col.values)
        res["response_name"] = r_name
        res["treatment_name"] = t_name
        res["block_name"] = b_name
        res["title"] = f"Friedman Test: {r_name} versus {t_name} blocked by {b_name}"
        recipe = {
            "action": "friedman_test",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def runs_test(self, settings=None):
        settings = self._bound_settings("runs_test", settings)
        import copy
        from .nonparametrics import runs_test
        if settings is None:
            raise ValueError("Runs Test requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if not indices:
            raise ValueError("Runs Test requires at least one variable.")
        last_rec = None
        for idx in indices:
            if not (0 <= idx < len(self.worksheet.columns)):
                continue
            col = self.worksheet.columns[idx]
            var_name = col.name or f"C{idx+1}"
            res = runs_test(
                data=col.values,
                baseline=st.get("baseline", "mean"),
                custom_baseline=st.get("custom_baseline"),
            )
            res["variable_name"] = var_name
            res["graph"] = "runs_test"
            res["title"] = f"Runs Test for {var_name}"
            recipe = {
                "action": "runs_test",
                "parameters": {
                    "settings": copy.deepcopy(settings)
                }
            }
            last_rec = self._record(res["title"], res, recipe=recipe)
        return last_rec

    def paired_wilcoxon(self, settings=None):
        settings = self._bound_settings("paired_wilcoxon", settings)
        import copy
        from .nonparametrics import paired_wilcoxon
        if settings is None:
            raise ValueError("Paired Wilcoxon requires settings.")
        st = copy.deepcopy(settings)
        i1 = st.get("first_index")
        i2 = st.get("second_index")
        if i1 is None or i2 is None or not (0 <= i1 < len(self.worksheet.columns)) or not (0 <= i2 < len(self.worksheet.columns)):
            raise ValueError("Paired Wilcoxon requires valid first and second sample columns.")
        col1 = self.worksheet.columns[i1]
        col2 = self.worksheet.columns[i2]
        name1 = col1.name or f"C{i1+1}"
        name2 = col2.name or f"C{i2+1}"
        res = paired_wilcoxon(
            sample1=col1.values,
            sample2=col2.values,
            test_diff=st.get("test_diff", 0.0),
            alternative=st.get("alternative", "two_sided"),
            conf_level=st.get("conf_level", 0.95),
        )
        res["name1"] = name1
        res["name2"] = name2
        res["title"] = f"Wilcoxon Signed Rank Test: Diff ({name1} - {name2})"
        recipe = {
            "action": "paired_wilcoxon",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def pca(self, settings=None):
        settings = self._bound_settings("pca", settings)
        import copy
        from .multivariate import pca
        if settings is None:
            raise ValueError("PCA requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if len(indices) < 2:
            raise ValueError("PCA requires at least 2 variables.")
        cols_data = []
        names = []
        for idx in indices:
            col = self.worksheet.columns[idx]
            cols_data.append(col.values)
            names.append(col.name or f"C{idx+1}")
        res = pca(
            data=cols_data,
            var_names=names,
            matrix_type=st.get("matrix_type", "correlation"),
            n_components=st.get("n_components"),
        )
        res["graph"] = "pca"
        res["title"] = f"Principal Component Analysis: {', '.join(names)}"
        recipe = {
            "action": "pca",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def item_analysis(self, settings=None):
        settings = self._bound_settings("item_analysis", settings)
        import copy
        from .multivariate import item_analysis
        if settings is None:
            raise ValueError("Item Analysis requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if len(indices) < 2:
            raise ValueError("Item Analysis requires at least 2 items.")
        cols_data = []
        names = []
        for idx in indices:
            col = self.worksheet.columns[idx]
            cols_data.append(col.values)
            names.append(col.name or f"C{idx+1}")
        res = item_analysis(data=cols_data, var_names=names)
        res["graph"] = "item_analysis"
        res["title"] = f"Item Analysis of {', '.join(names)}"
        recipe = {
            "action": "item_analysis",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def cluster_observations(self, settings=None):
        settings = self._bound_settings("cluster_observations", settings)
        import copy
        from .multivariate import cluster_observations
        if settings is None:
            raise ValueError("Cluster Observations requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if not indices:
            raise ValueError("Cluster Observations requires at least 1 variable.")
        cols_data = []
        names = []
        for idx in indices:
            col = self.worksheet.columns[idx]
            cols_data.append(col.values)
            names.append(col.name or f"C{idx+1}")
        res = cluster_observations(
            data=cols_data,
            var_names=names,
            linkage_method=st.get("linkage_method", "average"),
            distance_measure=st.get("distance_measure", "euclidean"),
            standardize=st.get("standardize", "none"),
            n_clusters=st.get("n_clusters", 3),
        )
        res["graph"] = "cluster_observations"
        res["title"] = "Cluster Analysis of Observations"
        recipe = {
            "action": "cluster_observations",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def cluster_kmeans(self, settings=None):
        settings = self._bound_settings("cluster_kmeans", settings)
        import copy
        from .multivariate import cluster_kmeans
        if settings is None:
            raise ValueError("Cluster K-Means requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if not indices:
            raise ValueError("Cluster K-Means requires at least 1 variable.")
        cols_data = []
        names = []
        for idx in indices:
            col = self.worksheet.columns[idx]
            cols_data.append(col.values)
            names.append(col.name or f"C{idx+1}")
        res = cluster_kmeans(
            data=cols_data,
            var_names=names,
            k_clusters=st.get("k_clusters", 3),
            max_iter=st.get("max_iter", 100),
        )
        res["graph"] = "cluster_kmeans"
        res["title"] = f"K-Means Cluster Analysis: {', '.join(names)}"
        recipe = {
            "action": "cluster_kmeans",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def cluster_variables(self, settings=None):
        settings = self._bound_settings("cluster_variables", settings)
        import copy
        from .multivariate import cluster_variables
        if settings is None:
            raise ValueError("Cluster Variables requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("variable_indices", [])
        if len(indices) < 2:
            raise ValueError("Cluster Variables requires at least 2 variables.")
        cols_data = []
        names = []
        for idx in indices:
            col = self.worksheet.columns[idx]
            cols_data.append(col.values)
            names.append(col.name or f"C{idx+1}")
        res = cluster_variables(
            data=cols_data,
            var_names=names,
            linkage_method=st.get("linkage_method", "average"),
        )
        res["graph"] = "cluster_variables"
        res["title"] = f"Cluster Analysis of Variables: {', '.join(names)}"
        recipe = {
            "action": "cluster_variables",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def discriminant_analysis(self, settings=None):
        settings = self._bound_settings("discriminant_analysis", settings)
        import copy
        from .multivariate import discriminant_analysis
        if settings is None:
            raise ValueError("Discriminant Analysis requires settings.")
        st = copy.deepcopy(settings)
        gi = st.get("group_index")
        pi = st.get("predictor_indices", [])
        if gi is None or not (0 <= gi < len(self.worksheet.columns)):
            raise ValueError("Discriminant Analysis requires a valid group column.")
        if not pi:
            raise ValueError("Discriminant Analysis requires at least 1 predictor variable.")
        g_col = self.worksheet.columns[gi]
        g_name = g_col.name or f"C{gi+1}"
        pred_data = []
        p_names = []
        for idx in pi:
            col = self.worksheet.columns[idx]
            pred_data.append(col.values)
            p_names.append(col.name or f"C{idx+1}")
        res = discriminant_analysis(
            group_col=g_col.values,
            pred_data=pred_data,
            group_name=g_name,
            pred_names=p_names,
            method=st.get("method", "linear"),
            priors=st.get("priors", "equal"),
        )
        res["graph"] = "discriminant_analysis"
        res["title"] = f"Discriminant Analysis: {g_name} versus {', '.join(p_names)}"
        recipe = {
            "action": "discriminant_analysis",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def simple_correspondence(self, settings=None):
        settings = self._bound_settings("simple_correspondence", settings)
        import copy
        from .multivariate import simple_correspondence
        if settings is None:
            raise ValueError("Simple Correspondence Analysis requires settings.")
        st = copy.deepcopy(settings)
        ci = st.get("column_indices", [])
        if len(ci) < 2:
            raise ValueError("Simple Correspondence Analysis requires at least 2 columns.")
        table = []
        col_names = []
        row_count = len(self.worksheet.columns[ci[0]].values)
        for idx in ci:
            col = self.worksheet.columns[idx]
            col_names.append(col.name or f"C{idx+1}")
        for r in range(row_count):
            row_vals = []
            for idx in ci:
                val = self.worksheet.columns[idx].values[r]
                try:
                    row_vals.append(float(val) if val is not None else 0.0)
                except (ValueError, TypeError):
                    row_vals.append(0.0)
            table.append(row_vals)
        res = simple_correspondence(table=table, col_names=col_names)
        res["graph"] = "simple_correspondence"
        res["title"] = "Simple Correspondence Analysis"
        recipe = {
            "action": "simple_correspondence",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def one_sample_equivalence(self, settings=None):
        settings = self._bound_settings("one_sample_equivalence", settings)
        import copy
        from .equivalence import one_sample_equivalence
        if settings is None:
            raise ValueError("1-Sample Equivalence Test requires settings.")
        st = copy.deepcopy(settings)
        idx = st.get("sample_index")
        if idx is None or not (0 <= idx < len(self.worksheet.columns)):
            raise ValueError("1-Sample Equivalence Test requires a valid sample column.")
        col = self.worksheet.columns[idx]
        name = col.name or f"C{idx+1}"
        res = one_sample_equivalence(
            data=col.values,
            target=st.get("target", 0.0),
            lower_margin=st.get("lower_margin", -1.0),
            upper_margin=st.get("upper_margin", 1.0),
            alpha=st.get("alpha", 0.05),
            hypothesis_type=st.get("hypothesis_type", "difference"),
        )
        res["sample_name"] = name
        res["graph"] = "one_sample_equivalence"
        res["title"] = f"Equivalence Test: {name}"
        recipe = {
            "action": "one_sample_equivalence",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def two_sample_equivalence(self, settings=None):
        settings = self._bound_settings("two_sample_equivalence", settings)
        import copy
        from .equivalence import two_sample_equivalence
        if settings is None:
            raise ValueError("2-Sample Equivalence Test requires settings.")
        st = copy.deepcopy(settings)
        i1 = st.get("first_index")
        i2 = st.get("second_index")
        if i1 is None or i2 is None or not (0 <= i1 < len(self.worksheet.columns)) or not (0 <= i2 < len(self.worksheet.columns)):
            raise ValueError("2-Sample Equivalence Test requires valid Test and Reference columns.")
        col1 = self.worksheet.columns[i1]
        col2 = self.worksheet.columns[i2]
        name1 = col1.name or f"C{i1+1}"
        name2 = col2.name or f"C{i2+1}"
        res = two_sample_equivalence(
            sample1=col1.values,
            sample2=col2.values,
            name1=name1,
            name2=name2,
            lower_margin=st.get("lower_margin", -1.0),
            upper_margin=st.get("upper_margin", 1.0),
            alpha=st.get("alpha", 0.05),
            equal_variances=st.get("equal_variances", False),
            hypothesis_type=st.get("hypothesis_type", "difference"),
        )
        res["name1"] = name1
        res["name2"] = name2
        res["graph"] = "two_sample_equivalence"
        res["title"] = f"2-Sample Equivalence Test: {name1} vs {name2}"
        recipe = {
            "action": "two_sample_equivalence",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def paired_equivalence(self, settings=None):
        settings = self._bound_settings("paired_equivalence", settings)
        import copy
        from .equivalence import paired_equivalence
        if settings is None:
            raise ValueError("Paired Equivalence Test requires settings.")
        st = copy.deepcopy(settings)
        i1 = st.get("first_index")
        i2 = st.get("second_index")
        if i1 is None or i2 is None or not (0 <= i1 < len(self.worksheet.columns)) or not (0 <= i2 < len(self.worksheet.columns)):
            raise ValueError("Paired Equivalence Test requires valid Sample 1 and Sample 2 columns.")
        col1 = self.worksheet.columns[i1]
        col2 = self.worksheet.columns[i2]
        name1 = col1.name or f"C{i1+1}"
        name2 = col2.name or f"C{i2+1}"
        res = paired_equivalence(
            sample1=col1.values,
            sample2=col2.values,
            name1=name1,
            name2=name2,
            lower_margin=st.get("lower_margin", -1.0),
            upper_margin=st.get("upper_margin", 1.0),
            alpha=st.get("alpha", 0.05),
            hypothesis_type=st.get("hypothesis_type", "difference"),
        )
        res["name1"] = name1
        res["name2"] = name2
        res["graph"] = "paired_equivalence"
        res["title"] = f"Paired Equivalence Test: {name1}, {name2}"
        recipe = {
            "action": "paired_equivalence",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def crossover_equivalence(self, settings=None):
        settings = self._bound_settings("crossover_equivalence", settings)
        import copy
        from .equivalence import crossover_equivalence
        if settings is None:
            raise ValueError("2x2 Crossover Equivalence Test requires settings.")
        st = copy.deepcopy(settings)
        ri = st.get("response_index")
        si = st.get("sequence_index")
        pi = st.get("period_index")
        sub_i = st.get("subject_index")
        ti = st.get("treatment_index")
        for idx_name, idx_val in [("response", ri), ("sequence", si), ("period", pi), ("subject", sub_i), ("treatment", ti)]:
            if idx_val is None or not (0 <= idx_val < len(self.worksheet.columns)):
                raise ValueError(f"2x2 Crossover Equivalence Test requires a valid {idx_name} column.")
        res = crossover_equivalence(
            response=self.worksheet.columns[ri].values,
            sequence=self.worksheet.columns[si].values,
            period=self.worksheet.columns[pi].values,
            subject=self.worksheet.columns[sub_i].values,
            treatment=self.worksheet.columns[ti].values,
            lower_margin=st.get("lower_margin", -1.0),
            upper_margin=st.get("upper_margin", 1.0),
            alpha=st.get("alpha", 0.05),
            hypothesis_type=st.get("hypothesis_type", "difference"),
        )
        res["graph"] = "crossover_equivalence"
        res["title"] = f"2x2 Crossover Equivalence: {self.worksheet.columns[ri].name or 'Response'}"
        recipe = {
            "action": "crossover_equivalence",
            "parameters": {
                "settings": copy.deepcopy(settings)
            }
        }
        return self._record(res["title"], res, recipe=recipe)

    def one_sample_z_power(self, settings=None):
        settings = self._bound_settings("one_sample_z_power", settings)
        import copy
        from .power import one_sample_z_power
        if settings is None:
            raise ValueError("1-Sample Z Power requires settings.")
        st = copy.deepcopy(settings)
        res = one_sample_z_power(
            differences=st.get("differences"),
            sample_sizes=st.get("sample_sizes"),
            target_powers=st.get("target_powers"),
            sigma=st.get("sigma", 1.0),
            alpha=st.get("alpha", 0.05),
            alternative=st.get("alternative", "two_sided"),
        )
        res["graph"] = "one_sample_z_power"
        res["title"] = "Power and Sample Size: 1-Sample Z"
        recipe = {"action": "one_sample_z_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def one_sample_t_power(self, settings=None):
        settings = self._bound_settings("one_sample_t_power", settings)
        import copy
        from .power import one_sample_t_power
        if settings is None:
            raise ValueError("1-Sample t Power requires settings.")
        st = copy.deepcopy(settings)
        res = one_sample_t_power(
            differences=st.get("differences"),
            sample_sizes=st.get("sample_sizes"),
            target_powers=st.get("target_powers"),
            sigma=st.get("sigma", 1.0),
            alpha=st.get("alpha", 0.05),
            alternative=st.get("alternative", "two_sided"),
        )
        res["graph"] = "one_sample_t_power"
        res["title"] = "Power and Sample Size: 1-Sample t"
        recipe = {"action": "one_sample_t_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def two_sample_t_power(self, settings=None):
        settings = self._bound_settings("two_sample_t_power", settings)
        import copy
        from .power import two_sample_t_power
        if settings is None:
            raise ValueError("2-Sample t Power requires settings.")
        st = copy.deepcopy(settings)
        res = two_sample_t_power(
            differences=st.get("differences"),
            sample_sizes=st.get("sample_sizes"),
            target_powers=st.get("target_powers"),
            sigma=st.get("sigma", 1.0),
            alpha=st.get("alpha", 0.05),
            alternative=st.get("alternative", "two_sided"),
        )
        res["graph"] = "two_sample_t_power"
        res["title"] = "Power and Sample Size: 2-Sample t"
        recipe = {"action": "two_sample_t_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def paired_t_power(self, settings=None):
        settings = self._bound_settings("paired_t_power", settings)
        import copy
        from .power import paired_t_power
        if settings is None:
            raise ValueError("Paired t Power requires settings.")
        st = copy.deepcopy(settings)
        res = paired_t_power(
            differences=st.get("differences"),
            sample_sizes=st.get("sample_sizes"),
            target_powers=st.get("target_powers"),
            stdev_diff=st.get("stdev_diff", st.get("sigma", 1.0)),
            alpha=st.get("alpha", 0.05),
            alternative=st.get("alternative", "two_sided"),
        )
        res["graph"] = "paired_t_power"
        res["title"] = "Power and Sample Size: Paired t"
        recipe = {"action": "paired_t_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def one_proportion_power(self, settings=None):
        settings = self._bound_settings("one_proportion_power", settings)
        import copy
        from .power import one_proportion_power
        if settings is None:
            raise ValueError("1 Proportion Power requires settings.")
        st = copy.deepcopy(settings)
        res = one_proportion_power(
            comparison_proportions=st.get("comparison_proportions"),
            baseline_p0=st.get("baseline_p0", 0.5),
            sample_sizes=st.get("sample_sizes"),
            target_powers=st.get("target_powers"),
            alpha=st.get("alpha", 0.05),
            alternative=st.get("alternative", "two_sided"),
        )
        res["graph"] = "one_proportion_power"
        res["title"] = "Power and Sample Size: 1 Proportion"
        recipe = {"action": "one_proportion_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def two_proportions_power(self, settings=None):
        settings = self._bound_settings("two_proportions_power", settings)
        import copy
        from .power import two_proportions_power
        if settings is None:
            raise ValueError("2 Proportions Power requires settings.")
        st = copy.deepcopy(settings)
        res = two_proportions_power(
            p1_values=st.get("p1_values"),
            p2=st.get("p2", 0.5),
            sample_sizes=st.get("sample_sizes"),
            target_powers=st.get("target_powers"),
            alpha=st.get("alpha", 0.05),
            alternative=st.get("alternative", "two_sided"),
        )
        res["graph"] = "two_proportions_power"
        res["title"] = "Power and Sample Size: 2 Proportions"
        recipe = {"action": "two_proportions_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def oneway_anova_power(self, settings=None):
        settings = self._bound_settings("oneway_anova_power", settings)
        import copy
        from .power import oneway_anova_power
        if settings is None:
            raise ValueError("One-Way ANOVA Power requires settings.")
        st = copy.deepcopy(settings)
        res = oneway_anova_power(
            levels=st.get("levels", 3),
            max_differences=st.get("max_differences"),
            sample_sizes=st.get("sample_sizes"),
            target_powers=st.get("target_powers"),
            sigma=st.get("sigma", 1.0),
            alpha=st.get("alpha", 0.05),
        )
        res["graph"] = "oneway_anova_power"
        res["title"] = "Power and Sample Size: One-Way ANOVA"
        recipe = {"action": "oneway_anova_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def factorial_power(self, settings=None):
        settings = self._bound_settings("factorial_power", settings)
        import copy
        from .power import factorial_power
        if settings is None:
            raise ValueError("Factorial Design Power requires settings.")
        st = copy.deepcopy(settings)
        res = factorial_power(
            factors=st.get("factors", 3),
            corner_points=st.get("corner_points", 8),
            replicates=st.get("replicates"),
            effects=st.get("effects"),
            target_powers=st.get("target_powers"),
            center_points=st.get("center_points", 0),
            sigma=st.get("sigma", 1.0),
            alpha=st.get("alpha", 0.05),
        )
        res["graph"] = "factorial_power"
        res["title"] = "Power and Sample Size: 2-Level Factorial"
        recipe = {"action": "factorial_power", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def _phase3_col(self, index, label="Variable", numeric=True):
        if index is None or not (0 <= int(index) < len(self.worksheet.columns)):
            raise ValueError(f"{label} requires a valid column index.")
        col = self.worksheet.columns[int(index)]
        return col.name, (col.numeric_values(True) if numeric else list(col.values))

    def _store_generated_col(self, prefix, values, kind="number"):
        existing = {c.name for c in self.worksheet.columns}
        name = prefix
        k = 2
        while name in existing:
            name = f"{prefix}_{k}"
            k += 1
        self.worksheet.columns.append(Column(name, kind, list(values)))
        self.dirty = True
        return name

    def bootstrap_1sample(self, index, statistic="Mean", n_resamples=2000, confidence=0.95, seed=42, store_replicates=False):
        from .resampling import bootstrap_1sample as _fn
        name, vals = self._phase3_col(index, "Variable", numeric=True)
        res = _fn(vals, statistic=statistic, n_resamples=int(n_resamples), confidence=float(confidence), seed=int(seed), variable_name=name)
        if store_replicates and res.get("_replicates"):
            res["stored_replicates_column"] = self._store_generated_col(f"Boot_{name}", res["_replicates"], "number")
        clean = {k: v for k, v in res.items() if not k.startswith("_")}
        recipe = {"action": "bootstrap_1sample", "parameters": {"index": index, "statistic": statistic, "n_resamples": n_resamples, "confidence": confidence, "seed": seed}}
        return self._record(f"1-Sample Bootstrap ({statistic}): {name}", clean, recipe=recipe)

    def bootstrap_2sample(self, index1, index2, statistic="Mean Difference", n_resamples=2000, confidence=0.95, seed=42, store_replicates=False):
        from .resampling import bootstrap_2sample as _fn
        n1, v1 = self._phase3_col(index1, "Sample 1", numeric=True)
        n2, v2 = self._phase3_col(index2, "Sample 2", numeric=True)
        res = _fn(v1, v2, statistic=statistic, n_resamples=int(n_resamples), confidence=float(confidence), seed=int(seed), name1=n1, name2=n2)
        if store_replicates and res.get("_replicates"):
            res["stored_replicates_column"] = self._store_generated_col("Boot_Diff", res["_replicates"], "number")
        clean = {k: v for k, v in res.items() if not k.startswith("_")}
        recipe = {"action": "bootstrap_2sample", "parameters": {"index1": index1, "index2": index2, "statistic": statistic, "n_resamples": n_resamples, "confidence": confidence, "seed": seed}}
        return self._record(f"2-Sample Bootstrap ({statistic}): {n1}, {n2}", clean, recipe=recipe)

    def randomization_1sample(self, index, hypothesized_mean=0.0, alternative="two_sided", n_resamples=2000, seed=42):
        from .resampling import randomization_1sample as _fn
        name, vals = self._phase3_col(index, "Variable", numeric=True)
        res = _fn(vals, hypothesized_mean=float(hypothesized_mean), alternative=alternative, n_resamples=int(n_resamples), seed=int(seed), variable_name=name)
        recipe = {"action": "randomization_1sample", "parameters": {"index": index, "hypothesized_mean": hypothesized_mean, "alternative": alternative, "n_resamples": n_resamples, "seed": seed}}
        return self._record(f"1-Sample Randomization Test: {name}", res, recipe=recipe)

    def randomization_2sample(self, index1, index2, alternative="two_sided", n_resamples=2000, seed=42):
        from .resampling import randomization_2sample as _fn
        n1, v1 = self._phase3_col(index1, "Sample 1", numeric=True)
        n2, v2 = self._phase3_col(index2, "Sample 2", numeric=True)
        res = _fn(v1, v2, alternative=alternative, n_resamples=int(n_resamples), seed=int(seed), name1=n1, name2=n2)
        recipe = {"action": "randomization_2sample", "parameters": {"index1": index1, "index2": index2, "alternative": alternative, "n_resamples": n_resamples, "seed": seed}}
        return self._record(f"2-Sample Randomization Test: {n1}, {n2}", res, recipe=recipe)

    def goodness_of_fit_poisson(self, index):
        from .count_models import goodness_of_fit_poisson as _fn
        name, vals = self._phase3_col(index, "Counts", numeric=True)
        res = _fn(vals, variable_name=name)
        recipe = {"action": "goodness_of_fit_poisson", "parameters": {"index": index}}
        return self._record(f"Goodness-of-Fit Test for Poisson: {name}", res, recipe=recipe)

    def negative_binomial_regression(self, response_index, predictor_indices, exposure_index=None):
        from .count_models import negative_binomial_regression as _fn
        res = _fn(self.worksheet, response_index, list(predictor_indices), exposure_index=exposure_index)
        recipe = {"action": "negative_binomial_regression", "parameters": {"response_index": response_index, "predictor_indices": list(predictor_indices), "exposure_index": exposure_index}}
        return self._record(f"Negative Binomial Regression: {res['response']}", res, recipe=recipe)

    def extended_power(self, kind, **kwargs):
        from . import power_extended as _pe
        table = {
            "one_variance": (_pe.one_variance_power, "Power and Sample Size: 1 Variance", "one_variance_power"),
            "two_variances": (_pe.two_variances_power, "Power and Sample Size: 2 Variances", "two_variances_power"),
            "one_poisson_rate": (_pe.one_poisson_rate_power, "Power and Sample Size: 1-Sample Poisson Rate", "one_poisson_rate_power"),
            "two_poisson_rates": (_pe.two_poisson_rates_power, "Power and Sample Size: 2-Sample Poisson Rates", "two_poisson_rates_power"),
            "equivalence_tost": (_pe.equivalence_tost_power, "Power and Sample Size: Equivalence (TOST)", "equivalence_tost_power"),
            "estimation": (_pe.sample_size_estimation, "Sample Size for Estimation", "sample_size_estimation"),
            "tolerance_interval": (_pe.sample_size_tolerance_interval, "Sample Size for Tolerance Intervals", "sample_size_tolerance_interval"),
        }
        if kind not in table:
            raise ValueError(f"Unsupported extended power calculation kind: {kind}")
        fn, title, graph_tag = table[kind]
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        res = fn(**clean_kwargs)
        res["graph"] = graph_tag
        res["title"] = title
        recipe = {"action": "extended_power", "parameters": {"kind": kind, **clean_kwargs}}
        return self._record(title, res, recipe=recipe)

    def balanced_anova(self, response_index, factor_indices, include_interactions=True):
        from .advanced_anova import balanced_anova as _fn
        res = _fn(self.worksheet, response_index, list(factor_indices), include_interactions=bool(include_interactions))
        recipe = {"action": "balanced_anova", "parameters": {"response_index": response_index, "factor_indices": list(factor_indices), "include_interactions": bool(include_interactions)}}
        return self._record(f"Balanced ANOVA: {res['response']}", res, recipe=recipe)

    def fully_nested_anova(self, response_index, factor_indices):
        from .advanced_anova import fully_nested_anova as _fn
        res = _fn(self.worksheet, response_index, list(factor_indices))
        recipe = {"action": "fully_nested_anova", "parameters": {"response_index": response_index, "factor_indices": list(factor_indices)}}
        return self._record(f"Fully Nested ANOVA: {res['response']}", res, recipe=recipe)

    def oneway_manova(self, response_indices, factor_index):
        from .advanced_anova import oneway_manova as _fn
        res = _fn(self.worksheet, list(response_indices), factor_index)
        recipe = {"action": "oneway_manova", "parameters": {"response_indices": list(response_indices), "factor_index": factor_index}}
        return self._record(f"One-Way MANOVA: {', '.join(res['responses'])}", res, recipe=recipe)

    def fit_mixed_reml(self, response_index, fixed_indices=(), random_indices=()):
        from .mixed_reml import fit_mixed_reml as _fn
        res = _fn(self.worksheet, response_index, fixed_indices=list(fixed_indices), random_indices=list(random_indices))
        recipe = {"action": "fit_mixed_reml", "parameters": {"response_index": response_index, "fixed_indices": list(fixed_indices), "random_indices": list(random_indices)}}
        return self._record(f"Mixed Effects Model (REML): {res['response']}", res, recipe=recipe)

    def cox_ph_regression(self, time_index, event_index, covariate_indices, event_value=1):
        from .survival_advanced import cox_ph_regression as _fn
        res = _fn(self.worksheet, time_index, event_index, list(covariate_indices), event_value=event_value)
        recipe = {"action": "cox_ph_regression", "parameters": {"time_index": time_index, "event_index": event_index, "covariate_indices": list(covariate_indices), "event_value": event_value}}
        return self._record("Cox Proportional Hazards Regression", res, recipe=recipe)

    def warranty_analysis(self, ages_index, fails_index, at_risk_total=None, forecast_horizon=12.0):
        from .survival_advanced import warranty_analysis as _fn
        _, ages = self._phase3_col(ages_index, "Age intervals", numeric=True)
        _, fails = self._phase3_col(fails_index, "Failure counts", numeric=True)
        if at_risk_total is None:
            raise ValueError("Warranty Analysis requires total units in field (at risk).")
        res = _fn(ages, fails, float(at_risk_total), forecast_horizon=float(forecast_horizon))
        recipe = {"action": "warranty_analysis", "parameters": {"ages_index": ages_index, "fails_index": fails_index, "at_risk_total": at_risk_total, "forecast_horizon": forecast_horizon}}
        return self._record("Warranty Analysis & Claims Forecast", res, recipe=recipe)

    def six_sigma_process_report(self, index, lsl=None, usl=None, subgroup_size=1, sigma_shift=1.5):
        from .six_sigma import six_sigma_process_report as _fn
        name, vals = self._phase3_col(index, "Process measurement", numeric=True)
        res = _fn(vals, lsl=lsl, usl=usl, subgroup_size=int(subgroup_size), sigma_shift=float(sigma_shift), variable_name=name)
        recipe = {"action": "six_sigma_process_report", "parameters": {"index": index, "lsl": lsl, "usl": usl, "subgroup_size": subgroup_size, "sigma_shift": sigma_shift}}
        return self._record(f"Six Sigma Process Report: {name}", res, recipe=recipe)

    def rolled_throughput_yield(self, step_yields=None, index=None, process_name="Product Process"):
        from .six_sigma import rolled_throughput_yield as _fn
        if index is not None:
            name, vals = self._phase3_col(index, "Step yields (%)", numeric=True)
            yields = [v for v in vals if v is not None]
            if process_name == "Product Process":
                process_name = name
        else:
            yields = list(step_yields or [])
        res = _fn(yields, process_name=process_name)
        recipe = {"action": "rolled_throughput_yield", "parameters": {"step_yields": yields, "index": index, "process_name": process_name}}
        return self._record(f"Six Sigma Product Report (RTY): {process_name}", res, recipe=recipe)

    def _maybe_store_ml_cols(self, res: dict, prefix: str, store_fits: bool) -> None:
        if not store_fits or not res.get("_fits"):
            return
        fit_kind = "number" if res.get("task") == "regression" else "text"
        res["stored_fit_column"] = self._store_generated_col(f"{prefix}_Fit", res["_fits"], fit_kind)
        if res.get("_residuals"):
            res_name = f"{prefix}_Res" if res.get("task") == "regression" else f"{prefix}_Prob"
            res["stored_resid_column"] = self._store_generated_col(res_name, res["_residuals"], "number")

    def random_forest(self, response_index, predictor_indices, task="auto", n_trees=80, max_depth=8, min_samples_leaf=2, max_features="auto", seed=42, store_fits=False):
        from .predictive_ml import random_forest_fit as _fn
        preds = list(predictor_indices)
        res = _fn(self.worksheet, response_index, preds, task=task, n_trees=int(n_trees), max_depth=int(max_depth), min_samples_leaf=int(min_samples_leaf), max_features=max_features, seed=int(seed))
        self._maybe_store_ml_cols(res, "RF", bool(store_fits))
        clean = {k: v for k, v in res.items() if not k.startswith("_")}
        recipe = {"action": "random_forest", "parameters": {"response_index": response_index, "predictor_indices": preds, "task": task, "n_trees": int(n_trees), "max_depth": int(max_depth), "min_samples_leaf": int(min_samples_leaf), "max_features": max_features, "seed": int(seed)}}
        return self._record(f"Random Forests ({clean['task'].title()}): {clean['response']}", clean, recipe=recipe)

    def treenet_gbm(self, response_index, predictor_indices, task="auto", n_trees=100, learning_rate=0.08, max_depth=3, subsample=0.8, loss="ls", validation_fraction=0.2, seed=42, store_fits=False):
        from .predictive_ml import treenet_fit as _fn
        preds = list(predictor_indices)
        res = _fn(self.worksheet, response_index, preds, task=task, n_trees=int(n_trees), learning_rate=float(learning_rate), max_depth=int(max_depth), subsample=float(subsample), loss=loss, validation_fraction=float(validation_fraction), seed=int(seed))
        self._maybe_store_ml_cols(res, "TreeNet", bool(store_fits))
        clean = {k: v for k, v in res.items() if not k.startswith("_")}
        recipe = {"action": "treenet_gbm", "parameters": {"response_index": response_index, "predictor_indices": preds, "task": task, "n_trees": int(n_trees), "learning_rate": float(learning_rate), "max_depth": int(max_depth), "subsample": float(subsample), "loss": loss, "validation_fraction": float(validation_fraction), "seed": int(seed)}}
        return self._record(f"TreeNet Gradient Boosting ({clean['task'].title()}): {clean['response']}", clean, recipe=recipe)

    def mars_regression(self, response_index, predictor_indices, task="auto", max_terms=16, max_degree=2, penalty=2.0, store_fits=False):
        from .predictive_ml import mars_fit as _fn
        preds = list(predictor_indices)
        res = _fn(self.worksheet, response_index, preds, task=task, max_terms=int(max_terms), max_degree=int(max_degree), penalty=float(penalty))
        self._maybe_store_ml_cols(res, "MARS", bool(store_fits))
        clean = {k: v for k, v in res.items() if not k.startswith("_")}
        recipe = {"action": "mars_regression", "parameters": {"response_index": response_index, "predictor_indices": preds, "task": task, "max_terms": int(max_terms), "max_degree": int(max_degree), "penalty": float(penalty)}}
        return self._record(f"MARS Splines ({clean['task'].title()}): {clean['response']}", clean, recipe=recipe)

    def discover_best_model(self, response_index, predictor_indices, task="auto", validation_fraction=0.25, seed=42):
        from .predictive_ml import discover_best_model as _fn
        preds = list(predictor_indices)
        res = _fn(self.worksheet, response_index, preds, task=task, validation_fraction=float(validation_fraction), seed=int(seed))
        recipe = {"action": "discover_best_model", "parameters": {"response_index": response_index, "predictor_indices": preds, "task": task, "validation_fraction": float(validation_fraction), "seed": int(seed)}}
        return self._record(f"Discover Best Model ({res['task'].title()}): {res['response']}", res, recipe=recipe)

    def monte_carlo_simulation(self, inputs, formula, lsl=None, usl=None, n_sims=10000, seed=42, store_column=False):
        from .monte_carlo import monte_carlo_simulation as _fn, parse_input_specs
        parsed = parse_input_specs(inputs) if isinstance(inputs, str) else list(inputs)
        res = _fn(parsed, formula, lsl=lsl, usl=usl, n_sims=int(n_sims), seed=int(seed))
        if store_column and res.get("_draws"):
            res["stored_column"] = self._store_generated_col("MC_Output", res["_draws"], "number")
        clean = {k: v for k, v in res.items() if not k.startswith("_")}
        recipe = {"action": "monte_carlo_simulation", "parameters": {"inputs": parsed, "formula": formula, "lsl": lsl, "usl": usl, "n_sims": int(n_sims), "seed": int(seed)}}
        return self._record(f"Monte Carlo Simulation ({clean['n_sims']:,} runs)", clean, recipe=recipe)

    def cross_tabulation(self, settings=None):
        settings = self._bound_settings("cross_tabulation", settings)
        import copy
        from .tables import cross_tabulation
        if settings is None:
            raise ValueError("Cross Tabulation requires settings.")
        st = copy.deepcopy(settings)
        r_idx = st.get("row_column")
        c_idx = st.get("col_column")
        if r_idx is None or not (0 <= r_idx < len(self.worksheet.columns)):
            raise ValueError("Cross Tabulation requires a valid row variable.")
        if c_idx is None or not (0 <= c_idx < len(self.worksheet.columns)):
            raise ValueError("Cross Tabulation requires a valid column variable.")
        r_col = self.worksheet.columns[r_idx]
        c_col = self.worksheet.columns[c_idx]
        r_name = r_col.name or f"C{r_idx+1}"
        c_name = c_col.name or f"C{c_idx+1}"

        f_data = None
        f_idx = st.get("freq_column")
        if f_idx is not None and 0 <= f_idx < len(self.worksheet.columns):
            f_data = self.worksheet.columns[f_idx].values

        res = cross_tabulation(
            row_data=r_col.values,
            col_data=c_col.values,
            row_name=r_name,
            col_name=c_name,
            freq_data=f_data,
            include_expected=st.get("include_expected", True),
            include_row_percents=st.get("include_row_percents", True),
            include_col_percents=st.get("include_col_percents", True),
            include_total_percents=st.get("include_total_percents", False),
            include_chi_square=st.get("include_chi_square", True),
        )
        res["graph"] = "cross_tabulation"
        res["title"] = f"Cross Tabulation and Chi-Square: {r_name}, {c_name}"
        recipe = {"action": "cross_tabulation", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def chi_square_goodness_of_fit(self, settings=None):
        settings = self._bound_settings("chi_square_goodness_of_fit", settings)
        import copy
        from .tables import chi_square_goodness_of_fit
        if settings is None:
            raise ValueError("Goodness-of-Fit Test requires settings.")
        st = copy.deepcopy(settings)
        obs_idx = st.get("observed_column")
        if obs_idx is None or not (0 <= obs_idx < len(self.worksheet.columns)):
            raise ValueError("Goodness-of-Fit Test requires a valid categorical variable.")
        col = self.worksheet.columns[obs_idx]
        var_name = col.name or f"C{obs_idx+1}"

        f_data = None
        f_idx = st.get("freq_column")
        if f_idx is not None and 0 <= f_idx < len(self.worksheet.columns):
            f_data = self.worksheet.columns[f_idx].values

        res = chi_square_goodness_of_fit(
            data=col.values,
            var_name=var_name,
            freq_data=f_data,
            test_proportions=st.get("test_proportions"),
        )
        res["graph"] = "chi_square_goodness_of_fit"
        res["title"] = f"Chi-Square Goodness-of-Fit Test: {var_name}"
        recipe = {"action": "chi_square_goodness_of_fit", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def chi_square_association_table(self, settings=None):
        settings = self._bound_settings("chi_square_association_table", settings)
        import copy
        from .tables import chi_square_association_table
        if settings is None:
            raise ValueError("Chi-Square Test for Association requires settings.")
        st = copy.deepcopy(settings)
        t_indices = st.get("table_columns", [])
        if not t_indices or len(t_indices) < 2:
            raise ValueError("Chi-Square Test for Association requires at least 2 table columns.")
        col_names = []
        table_cols_data = []
        for idx in t_indices:
            if not (0 <= idx < len(self.worksheet.columns)):
                raise ValueError(f"Invalid column index {idx}.")
            col = self.worksheet.columns[idx]
            col_names.append(col.name or f"C{idx+1}")
            table_cols_data.append(col.values)

        row_count = min(len(col_vals) for col_vals in table_cols_data)
        table = []
        for r in range(row_count):
            row_vals = []
            for col_vals in table_cols_data:
                v = col_vals[r]
                row_vals.append(float(v) if v is not None else 0.0)
            table.append(row_vals)

        row_names = None
        r_lbl_idx = st.get("row_labels_column")
        if r_lbl_idx is not None and 0 <= r_lbl_idx < len(self.worksheet.columns):
            lbl_col = self.worksheet.columns[r_lbl_idx]
            row_names = [str(v) if v is not None else f"Row {i+1}" for i, v in enumerate(lbl_col.values[:row_count])]

        res = chi_square_association_table(
            table=table,
            row_names=row_names,
            col_names=col_names,
        )
        res["graph"] = "chi_square_association_table"
        res["title"] = f"Chi-Square Test for Association: {', '.join(col_names)}"
        recipe = {"action": "chi_square_association_table", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def tally_variables(self, settings=None):
        settings = self._bound_settings("tally_variables", settings)
        import copy
        from .tables import tally_variables
        if settings is None:
            raise ValueError("Tally Individual Variables requires settings.")
        st = copy.deepcopy(settings)
        indices = st.get("columns", [])
        if not indices:
            raise ValueError("Tally requires at least one variable.")
        all_results = []
        var_names = []
        for idx in indices:
            if not (0 <= idx < len(self.worksheet.columns)):
                continue
            col = self.worksheet.columns[idx]
            name = col.name or f"C{idx+1}"
            var_names.append(name)
            sub_res = tally_variables(
                data=col.values,
                var_name=name,
                include_counts=st.get("include_counts", True),
                include_percents=st.get("include_percents", True),
                include_cumulative_counts=st.get("include_cumulative_counts", True),
                include_cumulative_percents=st.get("include_cumulative_percents", True),
            )
            all_results.append(sub_res)

        if not all_results:
            raise ValueError("No valid variables found for Tally.")

        res = all_results[0] if len(all_results) == 1 else {
            "analysis": "tally_variables",
            "var_name": ", ".join(var_names),
            "multiple": True,
            "results": all_results,
            "categories": all_results[0].get("categories", []),
            "counts": all_results[0].get("counts", []),
        }
        res["graph"] = "tally_variables"
        res["title"] = f"Tally for Discrete Variables: {', '.join(var_names)}"
        recipe = {"action": "tally_variables", "parameters": {"settings": copy.deepcopy(settings)}}
        return self._record(res["title"], res, recipe=recipe)

    def xbar_r_rows(self, indices):
        from .subgroup_quality import xbar_r
        if not 2 <= len(indices) <= 10 or len(set(indices)) != len(indices):
            raise ValueError("Select 2 to 10 distinct measurement columns; each row forms one subgroup.")
        columns = [self.worksheet.columns[i] for i in indices]
        if any(c.kind != "number" for c in columns):
            raise ValueError("Subgroup measurements must be numeric.")
        size = max(len(c.values) for c in columns)
        groups = [[c.values[row] if row < len(c.values) else None for c in columns] for row in range(size)]
        result = xbar_r(groups)
        return self._record("Xbar-R — " + self.worksheet.name,
            {**result, "chart":"Xbar-R", "variable":", ".join(c.name for c in columns),
             "subgroup_labels":[str(row+1) for row in range(size)]},
            recipe={"action":"xbar_r_rows", "parameters":{"indices":list(indices)}})

    def xbar_r_stacked(self, response_index, factor_index):
        from .subgroup_quality import xbar_r
        if response_index == factor_index:
            raise ValueError("Choose separate measurement and subgroup-ID columns.")
        response, factor = self.worksheet.columns[response_index], self.worksheet.columns[factor_index]
        if response.kind != "number" or factor.kind not in ("number", "text"):
            raise ValueError("Choose numeric measurements and numeric or text subgroup IDs.")
        response.validate(); factor.validate()
        groups, omitted = {}, 0
        for row in range(max(len(response.values),len(factor.values))):
            level = factor.values[row] if row < len(factor.values) else None
            if level is None or level == "":
                omitted += 1
                continue
            value = response.values[row] if row < len(response.values) else None
            groups.setdefault(level, []).append(value)
        result = xbar_r(list(groups.values()))
        if omitted:
            result["warnings"].append(str(omitted) + " rows with missing subgroup IDs were omitted.")
        return self._record("Xbar-R — " + response.name,
            {**result, "chart":"Xbar-R", "variable":response.name,
             "subgroup_labels":[str(label) for label in groups]},
            recipe={"action":"xbar_r_stacked", "parameters":{"response_index":response_index, "factor_index":factor_index}})

    def attribute_capability(self, method, count_index, sample_size=1.0, size_index=None, options=None):
        from .attribute_capability import analyze
        result = analyze(self.worksheet, method, count_index, sample_size, size_index, options)
        if result['options']['show_graphs']:
            result['graph'] = 'attribute_capability'
        return self._record(result['title'], result, recipe={
            'action': 'attribute_capability', 'parameters': {
                'method': method, 'count_index': count_index, 'sample_size': sample_size,
                'size_index': size_index, 'options': copy.deepcopy(options or {})}})

    def machine_capability(self, index=None, lsl=None, usl=None, target=None, settings=None):
        st = dict(settings or {})
        st["study_type"] = "machine"
        if "options" not in st:
            st["options"] = {}
        st["options"]["study_type"] = "machine"
        return self.normal_capability(index=index, lsl=lsl, usl=usl, target=target, settings=st)

    def reliability_distribution(self, settings=None):
        from .reliability_inputs import prepare_inputs
        from .reliability_engine import run_reliability_analysis
        if settings is None:
            raise ValueError('Reliability Distribution Analysis requires settings.')
        inputs = prepare_inputs(self.worksheet, settings)
        settings_rec = inputs['settings']
        col_idx = settings_rec['column_index']
        col = self.worksheet.columns[col_idx]
        res = run_reliability_analysis(
            time_values=inputs['time_values'], censor_values=inputs['censor_values'],
            censor_value=inputs['censor_value'], dist_name=settings_rec.get('dist_name', 'weibull'),
            confidence_level=settings_rec.get('confidence_level', 0.95))
        res.update(row_indices=inputs['row_indices'], omitted_rows=inputs['omitted_rows'], invalid_count=inputs['invalid_count'])
        return self._record(f'Distribution Analysis — {col.name}',
            {'variable': col.name, 'variable_name': col.name, **res},
            recipe={'action': 'reliability_distribution', 'parameters': {'settings': settings_rec}})

    def capability_nonparametric(self, settings=None):
        settings = self._bound_settings("capability_nonparametric", settings)
        from .capability_automated_engine import run_nonparametric_capability

        if settings is None:
            raise ValueError("Nonparametric Capability Analysis requires settings.")

        col_ref = settings.get("column_name")
        col_idx = settings.get("column_index")
        col = None
        if isinstance(col_idx, int) and 0 <= col_idx < len(self.worksheet.columns):
            col = self.worksheet.columns[col_idx]
        elif col_ref:
            for ci, c in enumerate(self.worksheet.columns):
                if c.name == col_ref:
                    col = c
                    col_idx = ci
                    break
        if col is None:
            col_idx = settings.get("variable_index", 0)
            col = self.worksheet.columns[col_idx]

        settings_rec = dict(settings)
        settings_rec["column_index"] = col_idx
        settings_rec["column_name"] = col.name

        data_vals = [float(v) for v in col.values if v is not None and v != ""]
        res = run_nonparametric_capability(
            values=data_vals,
            lsl=settings.get("lsl"),
            usl=settings.get("usl"),
            target=settings.get("target"),
            tolerance_k=settings.get("tolerance_k", 6.0),
            naming_convention=settings.get("naming_convention", "classical"),
        )

        var_name = col.name
        return self._record(
            f"Nonparametric Capability Analysis — {var_name}",
            {"variable": var_name, "variable_name": var_name, **res},
            recipe={"action": "capability_nonparametric", "parameters": {"settings": settings_rec}}
        )

    def capability_automated(self, settings=None):
        settings = self._bound_settings("capability_automated", settings)
        from .capability_automated_engine import run_automated_capability_tournament

        if settings is None:
            raise ValueError("Automated Capability Analysis requires settings.")

        col_ref = settings.get("column_name")
        col_idx = settings.get("column_index")
        col = None
        if isinstance(col_idx, int) and 0 <= col_idx < len(self.worksheet.columns):
            col = self.worksheet.columns[col_idx]
        elif col_ref:
            for ci, c in enumerate(self.worksheet.columns):
                if c.name == col_ref:
                    col = c
                    col_idx = ci
                    break
        if col is None:
            col_idx = settings.get("variable_index", 0)
            col = self.worksheet.columns[col_idx]

        settings_rec = dict(settings)
        settings_rec["column_index"] = col_idx
        settings_rec["column_name"] = col.name

        data_vals = [float(v) for v in col.values if v is not None and v != ""]
        res = run_automated_capability_tournament(
            values=data_vals,
            lsl=settings.get("lsl"),
            usl=settings.get("usl"),
            target=settings.get("target"),
            tolerance_k=settings.get("tolerance_k", 6.0),
            naming_convention=settings.get("naming_convention", "classical"),
        )

        var_name = col.name
        return self._record(
            f"Automated Capability Analysis — {var_name}",
            {"variable": var_name, "variable_name": var_name, **res},
            recipe={"action": "capability_automated", "parameters": {"settings": settings_rec}}
        )

    def _resolve_col_obj(self, ref):
        if ref is None:
            return None, None
        if type(ref) is int:
            if not 0 <= ref < len(self.worksheet.columns):
                raise ValueError('A source column no longer exists.')
            return self.worksheet.columns[ref], ref
        if not isinstance(ref, str):
            raise ValueError('Select a valid source column.')
        matches = [(column, index) for index, column in enumerate(self.worksheet.columns) if column.name == ref]
        if len(matches) > 1:
            raise ValueError('The source column name is ambiguous; select its C-number.')
        return matches[0] if matches else (None, None)

    def nested_gage_rr(self, part_col=None, operator_col=None, measurement_col=None, options=None, settings=None, **kwargs):
        from .msa_nested_engine import analyze_nested_gage_rr
        cfg = dict(kwargs)
        cfg.update(settings or {})
        p_name = cfg.get("part_col", part_col)
        o_name = cfg.get("operator_col", operator_col)
        m_name = cfg.get("measurement_col", measurement_col)
        opts = cfg.get("options", options or {})
        mult = float(opts.get("study_multiplier", cfg.get("study_multiplier", 6.0)))
        tol = opts.get("tolerance") if opts.get("tolerance") is not None else cfg.get("tolerance")
        if tol is not None:
            tol = float(tol)
        psd = opts.get("process_stdev") if opts.get("process_stdev") is not None else cfg.get("process_stdev")
        if psd is not None:
            psd = float(psd)

        for label, value in [('Study variation', mult), ('Tolerance', tol), ('Historical standard deviation', psd)]:
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(label + ' must be positive and finite.')

        p_col, p_idx = self._resolve_col_obj(cfg.get("part_index") if cfg.get("part_index") is not None else p_name)
        o_col, o_idx = self._resolve_col_obj(cfg.get("operator_index") if cfg.get("operator_index") is not None else o_name)
        m_col, m_idx = self._resolve_col_obj(cfg.get("measurement_index") if cfg.get("measurement_index") is not None else m_name)

        if not p_col or not o_col or not m_col:
            raise ValueError("Nested Gage R&R requires valid part, operator, and measurement columns.")

        if m_col.kind != 'number':
            raise ValueError('Measurement data must use a numeric column.')
        res = analyze_nested_gage_rr(
            measurements=m_col.values,
            parts=p_col.values,
            operators=o_col.values,
            study_multiplier=mult,
            tolerance=tol,
            process_stdev=psd,
        )
        res["part"] = p_col.name
        res["operator"] = o_col.name
        res["measurement"] = m_col.name
        rec_params = {
            "part_col": p_col.name,
            "operator_col": o_col.name,
            "measurement_col": m_col.name,
            "part_index": p_idx,
            "operator_index": o_idx,
            "measurement_index": m_idx,
            "options": {"study_multiplier": mult, "tolerance": tol, "process_stdev": psd},
        }
        return self._record(
            f"Gage R&R Study (Nested) — {m_col.name}",
            res,
            recipe={"action": "nested_gage_rr", "parameters": rec_params}
        )

    def gage_linearity(self, reference_col=None, measurement_col=None, part_col=None, process_variation=None, settings=None, **kwargs):
        from .msa_linearity_engine import analyze_gage_linearity_and_bias
        cfg = dict(settings or kwargs)
        r_name = cfg.get("reference_col", reference_col)
        m_name = cfg.get("measurement_col", measurement_col)
        p_name = cfg.get("part_col", part_col)
        pv = cfg.get("process_variation", process_variation)
        if pv is not None:
            pv = float(pv)

        r_col, r_idx = self._resolve_col_obj(cfg.get("reference_index") if cfg.get("reference_index") is not None else r_name)
        m_col, m_idx = self._resolve_col_obj(cfg.get("measurement_index") if cfg.get("measurement_index") is not None else m_name)
        p_col, p_idx = self._resolve_col_obj(cfg.get("part_index") if cfg.get("part_index") is not None else p_name)

        if not r_col or not m_col:
            raise ValueError("Gage Linearity and Bias requires valid reference and measurement columns.")

        if r_col.kind != 'number' or m_col.kind != 'number':
            raise ValueError('Reference values and measurements must use numeric columns.')
        if (p_name is not None or cfg.get('part_index') is not None) and p_col is None:
            raise ValueError('The selected part column was not found.')
        res = analyze_gage_linearity_and_bias(
            reference_values=r_col.values,
            measurements=m_col.values,
            parts=p_col.values if p_col else None,
            process_variation=pv,
        )
        res["reference"] = r_col.name
        res["measurement"] = m_col.name
        if p_col:
            res["part"] = p_col.name
        rec_params = {
            "reference_col": r_col.name,
            "measurement_col": m_col.name,
            "part_col": p_col.name if p_col else None,
            "reference_index": r_idx,
            "measurement_index": m_idx,
            "part_index": p_idx,
            "process_variation": pv,
        }
        return self._record(
            f"Gage Linearity and Bias Study — {m_col.name}",
            res,
            recipe={"action": "gage_linearity", "parameters": rec_params}
        )

    def attribute_agreement(self, attribute_col=None, sample_col=None, appraiser_col=None, standard_col=None, trial_col=None, settings=None, **kwargs):
        from .msa_attribute_engine import analyze_attribute_agreement
        cfg = dict(settings or kwargs)
        a_name = cfg.get("attribute_col", attribute_col)
        s_name = cfg.get("sample_col", sample_col)
        ap_name = cfg.get("appraiser_col", appraiser_col)
        std_name = cfg.get("standard_col", standard_col)
        tr_name = cfg.get("trial_col", trial_col)

        a_col, a_idx = self._resolve_col_obj(cfg.get("attribute_index") if cfg.get("attribute_index") is not None else a_name)
        s_col, s_idx = self._resolve_col_obj(cfg.get("sample_index") if cfg.get("sample_index") is not None else s_name)
        ap_col, ap_idx = self._resolve_col_obj(cfg.get("appraiser_index") if cfg.get("appraiser_index") is not None else ap_name)
        std_col, std_idx = self._resolve_col_obj(cfg.get("standard_index") if cfg.get("standard_index") is not None else std_name)
        tr_col, tr_idx = self._resolve_col_obj(cfg.get("trial_index") if cfg.get("trial_index") is not None else tr_name)

        if not a_col or not s_col or not ap_col:
            raise ValueError("Attribute Agreement Analysis requires valid attribute, sample, and appraiser columns.")

        if (std_name is not None or cfg.get('standard_index') is not None) and std_col is None:
            raise ValueError('The selected standard column was not found.')
        if (tr_name is not None or cfg.get('trial_index') is not None) and tr_col is None:
            raise ValueError('The selected trial column was not found.')
        res = analyze_attribute_agreement(
            attribute_data=a_col.values,
            samples=s_col.values,
            appraisers=ap_col.values,
            standard=std_col.values if std_col else None,
            trials=tr_col.values if tr_col else None,
        )
        res["attribute"] = a_col.name
        res["sample"] = s_col.name
        res["appraiser"] = ap_col.name
        if std_col:
            res["standard"] = std_col.name
        rec_params = {
            "attribute_col": a_col.name,
            "sample_col": s_col.name,
            "appraiser_col": ap_col.name,
            "standard_col": std_col.name if std_col else None,
            "trial_col": tr_col.name if tr_col else None,
            "attribute_index": a_idx,
            "sample_index": s_idx,
            "appraiser_index": ap_idx,
            "standard_index": std_idx,
            "trial_index": tr_idx,
        }
        return self._record(
            f"Attribute Agreement Analysis — {a_col.name}",
            res,
            recipe={"action": "attribute_agreement", "parameters": rec_params}
        )

    def multiple_capability(self, method='normal', variable_indices=None, by_indices=None,
                            subgroup_sizes=1, subgroup_indices=None, lower_specs=None,
                            upper_specs=None, targets=None, distribution='weibull', options=None):
        from .multiple_capability_engine import analyze_multiple_capability
        parameters = dict(method=method, variable_indices=list(variable_indices or []),
                          by_indices=list(by_indices or []), subgroup_sizes=copy.deepcopy(subgroup_sizes),
                          subgroup_indices=copy.deepcopy(subgroup_indices), lower_specs=copy.deepcopy(lower_specs),
                          upper_specs=copy.deepcopy(upper_specs), targets=copy.deepcopy(targets),
                          distribution=distribution, options=copy.deepcopy(options or {}))
        result = analyze_multiple_capability(self.worksheet, **parameters)
        label = 'Normal' if method == 'normal' else 'Nonnormal'
        return self._record(result['title'], result,
                            recipe={'action': 'multiple_capability', 'parameters': parameters})

    def capability_nonnormal(self, settings=None):
        settings = self._bound_settings("capability_nonnormal", settings)
        from .capability_nonnormal_engine import run_nonnormal_capability

        if settings is None:
            raise ValueError("Nonnormal Capability Analysis requires settings.")

        col_ref = settings.get("column_name")
        col_idx = settings.get("column_index")
        col = None
        if isinstance(col_idx, int) and 0 <= col_idx < len(self.worksheet.columns):
            col = self.worksheet.columns[col_idx]
        elif col_ref:
            for ci, c in enumerate(self.worksheet.columns):
                if c.name == col_ref:
                    col = c
                    col_idx = ci
                    break
        if col is None:
            col_idx = settings.get("variable_index", 0)
            col = self.worksheet.columns[col_idx]

        settings_rec = dict(settings)
        settings_rec["column_index"] = col_idx
        settings_rec["column_name"] = col.name

        data_vals = [float(v) for v in col.values if v is not None and v != ""]
        dist_choice = settings.get("dist_or_transform", "weibull")
        lsl_val = settings.get("lsl")
        usl_val = settings.get("usl")
        target_val = settings.get("target")
        naming = settings.get("naming_convention", "classical")

        res = run_nonnormal_capability(
            values=data_vals,
            dist_or_transform=dist_choice,
            lsl=lsl_val,
            usl=usl_val,
            target=target_val,
            tolerance_k=settings.get("tolerance_k", 6.0),
            box_cox_lambda=settings.get("box_cox_lambda"),
            naming_convention=naming,
            confidence_level=settings.get("confidence_level", 0.95),
        )

        var_name = col.name
        return self._record(
            f"Nonnormal Capability Analysis — {var_name}",
            {"variable": var_name, "variable_name": var_name, **res},
            recipe={"action": "capability_nonnormal", "parameters": {"settings": settings_rec}}
        )

    def acceptance_control_chart(self, settings=None):
        settings = self._bound_settings("acceptance_control_chart", settings)
        from .acceptance_chart_engine import run_acceptance_control_chart

        if settings is None:
            raise ValueError("Acceptance Control Chart requires settings.")

        single = settings.get("single_column", True)
        opts = settings.get("options", {})
        lsl_val = settings.get("lsl")
        usl_val = settings.get("usl")
        target_val = opts.get("target") or settings.get("target")
        delta_val = settings.get("delta", 0.001)
        alpha_val = settings.get("alpha", 0.05)
        hsd = settings.get("historical_stdev")

        settings_rec = dict(settings)
        if single:
            col_ref = settings.get("column_name")
            col = None
            col_idx = None
            if isinstance(col_ref, int):
                col_idx = col_ref
                col = self.worksheet.columns[col_ref]
            else:
                for ci, c in enumerate(self.worksheet.columns):
                    if c.name == col_ref:
                        col = c
                        col_idx = ci
                        break
            if col is None:
                raise ValueError(f"Column '{col_ref}' not found in worksheet.")
            settings_rec["column_index"] = col_idx

            sub_spec = settings.get("subgroup_spec", 5)
            subgroup_arg = sub_spec
            settings_rec["subgroup_col_index"] = None
            if isinstance(sub_spec, str) and not sub_spec.isdigit():
                sub_col = None
                for ci, c in enumerate(self.worksheet.columns):
                    if c.name == sub_spec:
                        sub_col = c
                        settings_rec["subgroup_col_index"] = ci
                        break
                if sub_col is not None:
                    subgroup_arg = sub_col.values

            data_vals = col.numeric_values(True)
            var_name = col.name
        else:
            cols_across = settings.get("cols_across", [])
            cols_data = []
            ca_indices = []
            for cn in cols_across:
                c_found = None
                for ci, c in enumerate(self.worksheet.columns):
                    if c.name == cn:
                        c_found = c
                        ca_indices.append(ci)
                        break
                if c_found is None:
                    raise ValueError(f"Column '{cn}' not found.")
                cols_data.append(c_found.values)
            settings_rec["cols_across_indices"] = ca_indices
            max_len = max(len(cd) for cd in cols_data) if cols_data else 0
            rows_data = []
            for r in range(max_len):
                row = [cols_data[ci][r] if r < len(cols_data[ci]) else None for ci in range(len(cols_data))]
                rows_data.append(row)
            data_vals = rows_data
            subgroup_arg = 1
            var_name = ", ".join(cols_across)

        res = run_acceptance_control_chart(
            data=data_vals,
            subgroup_spec=subgroup_arg,
            lsl=lsl_val,
            usl=usl_val,
            target=target_val,
            delta=delta_val,
            alpha=alpha_val,
            historical_stdev=hsd,
            estimate_method=opts.get("estimate_method", "pooled"),
            unbiased=opts.get("unbiased", True),
            variable_name=var_name,
            title=opts.get("title") or f"Acceptance Control Chart of {var_name}",
        )
        return self._record(
            f"Acceptance Control Chart \u2014 {var_name}",
            {"variable": var_name, **res},
            recipe={"action": "acceptance_control_chart", "parameters": {"settings": settings_rec}}
        )

    def normal_capability(self, index=None, lsl=None, usl=None, target=None, settings=None):
        settings = self._bound_settings("normal_capability", settings)
        from .capability_engine import run_normal_capability

        if settings is not None:
            single = settings.get("single_column", True)
            opts = settings.get("options", {})
            lsl_val = settings.get("lsl")
            usl_val = settings.get("usl")
            target_val = opts.get("target") or settings.get("target")
            hmean = settings.get("historical_mean")
            hsd = settings.get("historical_stdev")

            settings_rec = dict(settings)
            if single:
                col_ref = settings.get("column_name")
                col = None
                col_idx = None
                if isinstance(col_ref, int):
                    col_idx = col_ref
                    col = self.worksheet.columns[col_ref]
                else:
                    for ci, c in enumerate(self.worksheet.columns):
                        if c.name == col_ref:
                            col = c
                            col_idx = ci
                            break
                if col is None and index is not None:
                    col = self.worksheet.columns[index]
                    col_idx = index
                if col is None:
                    raise ValueError(f"Column '{col_ref}' not found in worksheet.")
                settings_rec["column_index"] = col_idx

                sub_spec = settings.get("subgroup_spec", 1)
                subgroup_arg = sub_spec
                settings_rec["subgroup_col_index"] = None
                if isinstance(sub_spec, str) and not sub_spec.isdigit():
                    sub_col = None
                    for ci, c in enumerate(self.worksheet.columns):
                        if c.name == sub_spec:
                            sub_col = c
                            settings_rec["subgroup_col_index"] = ci
                            break
                    if sub_col is not None:
                        subgroup_arg = sub_col.values

                data_vals = col.numeric_values(True)
                var_name = col.name
            else:
                cols_across = settings.get("cols_across", [])
                cols_data = []
                ca_indices = []
                for cn in cols_across:
                    c_found = None
                    for ci, c in enumerate(self.worksheet.columns):
                        if c.name == cn:
                            c_found = c
                            ca_indices.append(ci)
                            break
                    if c_found is None:
                        raise ValueError(f"Column '{cn}' not found.")
                    cols_data.append(c_found.values)
                settings_rec["cols_across_indices"] = ca_indices
                max_len = max(len(cd) for cd in cols_data) if cols_data else 0
                rows_data = []
                for r in range(max_len):
                    row = [cols_data[ci][r] if r < len(cols_data[ci]) else None for ci in range(len(cols_data))]
                    rows_data.append(row)
                data_vals = rows_data
                subgroup_arg = 1
                var_name = ", ".join(cols_across)

            analysis_mode = settings.get("analysis_mode", "normal")
            study_type = opts.get("study_type") or settings.get("study_type", "process")
            naming_convention = opts.get("naming_convention") or settings.get("naming_convention", "classical")
            is_bw = (analysis_mode == "between_within")
            is_machine = (study_type == "machine")
            is_aiag_vda = (naming_convention == "aiag_vda")

            if is_machine:
                default_title = f"Machine Capability Report for {var_name}"
                title_prefix = "Machine Capability"
            elif is_bw and is_aiag_vda:
                default_title = f"Between/Within Capability (AIAG/VDA) Report for {var_name}"
                title_prefix = "Between/Within Capability (AIAG/VDA)"
            elif is_bw:
                default_title = f"Between/Within Capability Report for {var_name}"
                title_prefix = "Between/Within Capability"
            else:
                default_title = f"Process Capability Report for {var_name}"
                title_prefix = "Normal Capability"

            res = run_normal_capability(
                data=data_vals,
                subgroup_spec=subgroup_arg,
                lsl=lsl_val,
                usl=usl_val,
                target=target_val,
                historical_mean=hmean,
                historical_stdev=hsd,
                estimate_method_gt1=opts.get("estimate_method_gt1", "pooled"),
                estimate_method_eq1=opts.get("estimate_method_eq1", "amr"),
                moving_range_len=opts.get("moving_range_len", 2),
                unbiased_within=opts.get("unbiased_within", True),
                unbiased_overall=opts.get("unbiased_overall", False),
                tolerance_k=opts.get("tolerance_k", 6.0),
                display_unit=opts.get("display_unit", "ppm"),
                stats_type=opts.get("stats_type", "capability"),
                include_ci=opts.get("include_ci", False),
                confidence_level=opts.get("confidence_level", 95.0),
                ci_type=opts.get("ci_type", "two_sided"),
                variable_name=var_name,
                title=opts.get("title") or default_title,
                analysis_mode=analysis_mode,
                naming_convention=naming_convention,
                study_type=study_type,
            )
            res["graph"] = "capability"
            res["analysis"] = "capability"
            return self._record(
                f"{title_prefix} — {var_name}",
                {"variable": var_name, **res},
                recipe={"action": "normal_capability", "parameters": {"settings": settings_rec}}
            )

        col = self.worksheet.columns[index]
        res = run_normal_capability(
            data=col.numeric_values(True),
            subgroup_spec=1,
            lsl=lsl,
            usl=usl,
            target=target,
            variable_name=col.name
        )
        res["graph"] = "capability"
        res["analysis"] = "capability"
        return self._record(
            f"Normal Capability — {col.name}",
            {"variable": col.name, **res},
            recipe={"action": "normal_capability", "parameters": {"index": index, "lsl": lsl, "usl": usl, "target": target}}
        )

    def between_within_sixpack(self, settings=None):
        settings = self._bound_settings("between_within_sixpack", settings)
        if settings is not None:
            settings["analysis_mode"] = "between_within"
        return self.normal_sixpack(settings=settings)

    def nonnormal_sixpack(self, settings=None):
        settings = self._bound_settings("nonnormal_sixpack", settings)
        from .sixpack_engine import run_nonnormal_sixpack
        if settings is None:
            raise ValueError("Nonnormal Capability Sixpack requires analysis settings.")

        settings_rec = dict(settings)
        col_ref = settings.get("column_name")
        col = None
        col_idx = None
        if isinstance(col_ref, int):
            col_idx = col_ref
            col = self.worksheet.columns[col_ref]
        else:
            for ci, c in enumerate(self.worksheet.columns):
                if c.name == col_ref:
                    col = c
                    col_idx = ci
                    break
        if col is None:
            raise ValueError(f"Column '{col_ref}' not found in worksheet.")
        settings_rec["column_index"] = col_idx

        sub_spec = settings.get("subgroup_spec", 1)
        settings_rec["subgroup_col_index"] = None
        subgroup_data = None
        if isinstance(sub_spec, str) and not sub_spec.isdigit():
            for ci, c in enumerate(self.worksheet.columns):
                if c.name == sub_spec:
                    settings_rec["subgroup_col_index"] = ci
                    subgroup_data = c.values
                    break

        col_data = col.numeric_values(True)
        var_name = col.name
        calc_settings = {
            "data_mode": "single_column",
            "column_name": var_name,
            "column_data": col_data,
            "subgroup_type": "column" if subgroup_data is not None else "size",
            "subgroup_size": int(sub_spec) if (isinstance(sub_spec, int) or (isinstance(sub_spec, str) and sub_spec.isdigit())) else 1,
            "subgroup_data": subgroup_data,
            "distribution": settings.get("distribution", "weibull"),
            "lsl": settings.get("lsl"),
            "usl": settings.get("usl"),
            "target": settings.get("target"),
            "options": settings.get("options", {}),
        }

        res = run_nonnormal_sixpack(calc_settings)
        res["graph"] = "capability_sixpack"
        res["analysis"] = "capability_sixpack_nonnormal"
        return self._record(
            f"Nonnormal Capability Sixpack — {var_name}",
            {"variable": var_name, **res},
            recipe={"action": "nonnormal_sixpack", "parameters": {"settings": settings_rec}},
        )

    def normal_sixpack(self, settings=None):
        settings = self._bound_settings("normal_sixpack", settings)
        from .sixpack_engine import run_normal_sixpack

        if settings is None:
            raise ValueError("Capability Sixpack requires analysis settings.")

        single = settings.get("single_column", True)
        settings_rec = dict(settings)

        if single:
            col_ref = settings.get("column_name")
            col = None
            col_idx = None
            if isinstance(col_ref, int):
                col_idx = col_ref
                col = self.worksheet.columns[col_ref]
            else:
                for ci, c in enumerate(self.worksheet.columns):
                    if c.name == col_ref:
                        col = c
                        col_idx = ci
                        break
            if col is None:
                raise ValueError(f"Column '{col_ref}' not found in worksheet.")
            settings_rec["column_index"] = col_idx

            sub_spec = settings.get("subgroup_spec", 1)
            settings_rec["subgroup_col_index"] = None
            subgroup_data = None
            if isinstance(sub_spec, str) and not sub_spec.isdigit():
                sub_col = None
                for ci, c in enumerate(self.worksheet.columns):
                    if c.name == sub_spec:
                        sub_col = c
                        settings_rec["subgroup_col_index"] = ci
                        break
                if sub_col is not None:
                    subgroup_data = sub_col.values

            col_data = col.numeric_values(True)
            var_name = col.name
            calc_settings = {
                "data_mode": "single_column",
                "column_name": var_name,
                "column_data": col_data,
                "subgroup_type": "column" if subgroup_data is not None else "size",
                "subgroup_size": int(sub_spec) if (isinstance(sub_spec, int) or (isinstance(sub_spec, str) and sub_spec.isdigit())) else 1,
                "subgroup_data": subgroup_data,
                "lsl": settings.get("lsl"),
                "usl": settings.get("usl"),
                "target": settings.get("options", {}).get("target") or settings.get("target"),
                "historical_mean": settings.get("historical_mean"),
                "historical_stdev": settings.get("historical_stdev"),
                "analysis_mode": settings.get("analysis_mode", settings.get("options", {}).get("analysis_mode", "normal")),
                "options": settings.get("options", {}),
            }
        else:
            cols_across = settings.get("cols_across", [])
            cols_data = []
            ca_indices = []
            for cn in cols_across:
                c_found = None
                for ci, c in enumerate(self.worksheet.columns):
                    if c.name == cn:
                        c_found = c
                        ca_indices.append(ci)
                        break
                if c_found is None:
                    raise ValueError(f"Column '{cn}' not found.")
                cols_data.append(c_found.values)
            settings_rec["cols_across_indices"] = ca_indices
            var_name = ", ".join(cols_across)
            calc_settings = {
                "data_mode": "subgroups_across",
                "column_name": var_name,
                "cols_across": cols_across,
                "cols_across_data": cols_data,
                "lsl": settings.get("lsl"),
                "usl": settings.get("usl"),
                "target": settings.get("options", {}).get("target") or settings.get("target"),
                "historical_mean": settings.get("historical_mean"),
                "historical_stdev": settings.get("historical_stdev"),
                "options": settings.get("options", {}),
            }

        res = run_normal_sixpack(calc_settings)
        res["graph"] = "capability_sixpack"
        res["analysis"] = "capability_sixpack_normal"
        return self._record(
            f"Capability Sixpack — {var_name}",
            {"variable": var_name, **res},
            recipe={"action": "between_within_sixpack" if settings.get("analysis_mode") == "between_within" else "normal_sixpack", "parameters": {"settings": settings_rec}}
        )

    def describe_columns(self, indices):
        from .analyses import describe
        if not indices:
            raise ValueError("Select at least one numeric column.")
        summaries = []
        for index in indices:
            col = self.worksheet.columns[index]
            summaries.append({"name": col.name, **describe(col.numeric_values(True))})
        return self._record("Descriptive Statistics", {"columns": summaries},
                            recipe={"action":"describe_columns", "parameters":{"indices":list(indices)}})

    def _selected_numeric(self, indices):
        if not indices or len(set(indices)) != len(indices) or any(type(i) is not int or i < 0 or i >= len(self.worksheet.columns) for i in indices):
            raise ValueError("Select distinct available numeric columns.")
        columns = [self.worksheet.columns[i] for i in indices]
        if any(c.kind != "number" for c in columns): raise ValueError("Select numeric columns.")
        return columns

    def create_response_surface(self,factors,kind='central_composite',centers=6,replicates=1,alpha_mode='rotatable',alpha=1.4142135623730951,levels_define='cube',randomize=True,seed=1,name='Response surface design',destination='worksheet',display='summary',fraction=1,blocks=1,center_cube=None,center_axial=None,block_replicates=False):
        from .response_surface import create,design_summary
        from .data_prep import store_prepared
        sheet=create(factors,kind,centers,replicates,alpha_mode,alpha,levels_define,randomize,seed,name,fraction=fraction,blocks=blocks,center_cube=center_cube,center_axial=center_axial,block_replicates=block_replicates)
        summary=design_summary(sheet,display)
        target=store_prepared(self,sheet,destination)
        target.worksheet.metadata=copy.deepcopy(sheet.metadata)
        entry=target._record('Response Surface Design',summary) if display!='none' else None
        return target,entry

    def mixture_process_contour(self,model_recipe,process_values=None,covariate_values=None,block_value=None,component_positions=None,hold_values=None,options=None):
        from .recipes import columns
        columns(model_recipe)
        if model_recipe['action']!='analyze_mixture_process':raise ValueError('Select a fitted mixture/process model.')
        from .mixture_process_model import fit
        from .mixture_condition import contour
        result=contour(fit(self.worksheet,**model_recipe['parameters']),process_values,covariate_values,block_value,component_positions,hold_values,options)
        fixed=result['conditioning']
        params=dict(model_recipe=copy.deepcopy(model_recipe),process_values=copy.deepcopy(fixed['process_values']),
            covariate_values=copy.deepcopy(fixed['covariate_values']),block_value=copy.deepcopy(fixed['block_value']),
            component_positions=list(result['component_positions']),hold_values=[{'position':item['position'],'value':item['value']} for item in result['hold_values']],options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'mixture_process_contour','parameters':params})

    def optimize_mixture_process(self,model_recipe,process_values=None,covariate_values=None,block_value=None,goal='maximize',target=None,bounds=None,options=None):
        from .recipes import columns
        columns(model_recipe)
        if model_recipe['action']!='analyze_mixture_process':raise ValueError('Select a fitted mixture/process model.')
        from .mixture_process_model import fit
        from .mixture_condition import optimize
        result=optimize(fit(self.worksheet,**model_recipe['parameters']),process_values,covariate_values,block_value,goal,target,bounds,options)
        fixed=result['conditioning']
        params=dict(model_recipe=copy.deepcopy(model_recipe),process_values=copy.deepcopy(fixed['process_values']),
            covariate_values=copy.deepcopy(fixed['covariate_values']),block_value=copy.deepcopy(fixed['block_value']),
            goal=goal,target=target,bounds=copy.deepcopy(result['component_bounds']),options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'optimize_mixture_process','parameters':params})

    def optimize_mixture_joint(self,model_recipe,goal='maximize',target=None,component_bounds=None,process_bounds=None,covariate_values=None,block_value=None,options=None):
        from .recipes import columns
        columns(model_recipe)
        if model_recipe['action']!='analyze_mixture_process':raise ValueError('Select a fitted mixture/process model.')
        from .mixture_process_model import fit
        from .mixture_joint_optimizer import optimize
        result=optimize(fit(self.worksheet,**model_recipe['parameters']),goal=goal,target=target,component_bounds=component_bounds,process_bounds=process_bounds,covariate_values=covariate_values,block_value=block_value,options=options)
        params=dict(model_recipe=copy.deepcopy(model_recipe),goal=goal,target=target,
            component_bounds=copy.deepcopy(result['component_bounds']),
            process_bounds=copy.deepcopy(result['process_bounds']),
            covariate_values=copy.deepcopy(result['covariate_values']),
            block_value=copy.deepcopy(result['block_value']),options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'optimize_mixture_joint','parameters':params})

    def analyze_mixture_process(self,response_index,component_indices,process_indices=None,block_index=None,covariate_indices=None,model='quadratic',total=1.,options=None):
        from .mixture_process_model import fit
        result=fit(self.worksheet,response_index,component_indices,process_indices,block_index,covariate_indices,model,total,options)
        snapshot=copy.deepcopy(result['options'])
        snapshot['bounds']=copy.deepcopy(result['component_bounds'])
        snapshot['process_coding']=copy.deepcopy(result['process_coding'])
        snapshot['covariate_coding']=copy.deepcopy(result['covariate_coding'])
        params=dict(response_index=response_index,component_indices=list(component_indices),process_indices=list(process_indices or []),
                    block_index=block_index,covariate_indices=list(covariate_indices or []),model=model,total=total,options=snapshot)
        return self._record(result['title'],result,recipe={'action':'analyze_mixture_process','parameters':params})

    def predict_mixture_process(self,model_recipe,component_rows,process_rows=None,covariate_rows=None,block_values=None,confidence=None):
        from .recipes import columns
        columns(model_recipe)
        if model_recipe['action']!='analyze_mixture_process':raise ValueError('Select a fitted mixture/process model.')
        from .mixture_process_model import fit,predict
        fitted=fit(self.worksheet,**model_recipe['parameters'])
        result=predict(fitted,component_rows,process_rows,covariate_rows,block_values,confidence)
        params=dict(model_recipe=copy.deepcopy(model_recipe),component_rows=copy.deepcopy(component_rows),
                    process_rows=copy.deepcopy(process_rows),covariate_rows=copy.deepcopy(covariate_rows),
                    block_values=copy.deepcopy(block_values),confidence=result['confidence'])
        return self._record('Mixture/Process Prediction: '+fitted['response_name'],result,recipe={'action':'predict_mixture_process','parameters':params})

    def analyze_mixture(self,response_index,component_indices,model='quadratic',total=1.0,options=None):
        from .mixture_analysis import fit
        result=fit(self.worksheet,response_index,component_indices,model,total,options)
        snapshot=copy.deepcopy(result['options'])
        snapshot['bounds']=copy.deepcopy(result['component_bounds'])
        params=dict(response_index=response_index,component_indices=list(component_indices),model=model,total=total,options=snapshot)
        return self._record(result['title'],result,
                            recipe={'action':'analyze_mixture','parameters':params})

    def mixture_contour(self,model_recipe,component_positions=None,hold_values=None,options=None):
        from .recipes import columns
        columns(model_recipe)
        if model_recipe['action']!='analyze_mixture':raise ValueError('Select a fitted mixture model.')
        from .mixture_analysis import fit
        from .mixture_exploration import contour
        result=contour(fit(self.worksheet,**model_recipe['parameters']),component_positions,hold_values,options)
        params=dict(model_recipe=copy.deepcopy(model_recipe),component_positions=list(result['component_positions']),
                    hold_values=[{'position':item['position'],'value':item['value']} for item in result['hold_values']],options=copy.deepcopy(result['options']))
        return self._record(result.get('title') or 'Mixture Contour Plot',result,recipe={'action':'mixture_contour','parameters':params})

    def _mixture_multi_inputs(self,responses):
        from .recipes import columns
        columns({'action':'optimize_mixture_multi','parameters':{'responses':responses,'bounds':None,'options':None}})
        from .mixture_analysis import fit
        models=[];specifications=[]
        for item in responses:
            models.append(fit(self.worksheet,**item['model_recipe']['parameters']))
            specifications.append({key:copy.deepcopy(value) for key,value in item.items() if key!='model_recipe'})
        return models,specifications

    def _mixture_multi_profiles(self,models,specifications,result):
        from .mixture_multi_optimizer import profiles
        bounds=result['component_bounds']
        balance=next((i for i in reversed(range(len(bounds))) if bounds[i]['low']<bounds[i]['high']),len(bounds)-1)
        return profiles(models,specifications,result['components'],bounds,{'balance_position':balance})

    def optimize_mixture_multi(self,responses,bounds=None,options=None):
        from .mixture_multi_optimizer import optimize
        models,specifications=self._mixture_multi_inputs(responses)
        result=optimize(models,specifications,bounds,options)
        result['profiles']=self._mixture_multi_profiles(models,specifications,result)
        params=dict(responses=copy.deepcopy(responses),bounds=copy.deepcopy(result['component_bounds']),options=copy.deepcopy(result['options']))
        return self._record(result['title'],result,recipe={'action':'optimize_mixture_multi','parameters':params})

    def evaluate_mixture_multi(self,responses,components,bounds=None,options=None):
        from .mixture_multi_optimizer import evaluate,settings
        models,specifications=self._mixture_multi_inputs(responses)
        opts=settings(options)
        result=evaluate(models,specifications,components,bounds,opts['confidence'])
        result.update(analysis='mixture_multi_evaluation',title=opts['title'].strip() or 'Mixture Response Settings',
                      method='User-selected feasible setting',options=opts)
        result['profiles']=self._mixture_multi_profiles(models,specifications,result)
        params=dict(responses=copy.deepcopy(responses),components=list(result['components']),
                    bounds=copy.deepcopy(result['component_bounds']),options=copy.deepcopy(opts))
        return self._record(result['title'],result,recipe={'action':'evaluate_mixture_multi','parameters':params})

    def optimize_mixture(self,model_recipe,goal='maximize',target=None,bounds=None,options=None):
        from .recipes import columns
        columns(model_recipe)
        if model_recipe['action']!='analyze_mixture':raise ValueError('Select a fitted mixture model.')
        from .mixture_analysis import fit
        from .mixture_exploration import optimize
        result=optimize(fit(self.worksheet,**model_recipe['parameters']),goal,target,bounds,options)
        params=dict(model_recipe=copy.deepcopy(model_recipe),goal=goal,target=target,
                    bounds=copy.deepcopy(result['component_bounds']),options=copy.deepcopy(result['options']))
        return self._record(result.get('title') or 'Mixture Response Optimizer',result,recipe={'action':'optimize_mixture','parameters':params})

    def predict_mixture(self,model_recipe,component_rows,confidence=.95):
        from .recipes import columns
        columns(model_recipe)
        if model_recipe['action']!='analyze_mixture':raise ValueError('Select a fitted mixture model.')
        from .mixture_analysis import fit,predict
        fitted=fit(self.worksheet,**model_recipe['parameters'])
        result=predict(fitted,component_rows,confidence)
        result['component_names']=list(fitted['component_names'])
        result['response_name']=fitted['response_name']
        result['total']=fitted['total']
        params=dict(model_recipe=copy.deepcopy(model_recipe),component_rows=copy.deepcopy(component_rows),confidence=confidence)
        return self._record('Mixture Prediction: '+fitted['response_name'],result,
                            recipe={'action':'predict_mixture','parameters':params})

    def analyze_dynamic_taguchi(self,response_indices,signal_values,factor_indices,options=None):
        from .dynamic_taguchi_analysis import analyze
        result=analyze(self.worksheet,response_indices,signal_values,factor_indices,options)
        params=dict(response_indices=list(response_indices),signal_values=list(result['signal_values']),
                    factor_indices=list(factor_indices),options=copy.deepcopy(result['options']))
        return self._record('Dynamic Taguchi Analysis',result,
                            recipe={'action':'analyze_dynamic_taguchi','parameters':params})

    def analyze_taguchi(self,response_indices,factor_indices,options=None):
        from .taguchi_analysis import analyze
        result=analyze(self.worksheet,response_indices,factor_indices,options)
        params=dict(response_indices=list(response_indices),factor_indices=list(factor_indices),options=copy.deepcopy(result['options']))
        return self._record('Taguchi Analysis',result,recipe={'action':'analyze_taguchi','parameters':params})

    def analyze_response_surface(self,response_index,factor_indices,coding=None,terms=None,options=None,block_index=None):
        from .response_surface import fit
        result=fit(self.worksheet,response_index,factor_indices,coding,terms,options,block_index=block_index)
        codes=result.get('surface_coding_information',result['coding_information'])
        parameters=dict(response_index=response_index,factor_indices=list(factor_indices),coding=[dict(low=c['low'],high=c['high']) for c in codes],terms=result.get('surface_terms',result['terms']),options=result['options'])
        if block_index is not None:parameters['block_index']=block_index
        entry = self._record('Response Surface Regression: '+result['response_name'],result,recipe={'action':'analyze_response_surface','parameters':parameters})
        try:
            from .connect import create_connected_response_surface
            conf = options.get('confidence', 0.95) if isinstance(options, dict) else 0.95
            conn = create_connected_response_surface(self.worksheet, response_index, factor_indices, result, conf, coding=parameters['coding'], terms=parameters['terms'], options=options)
            entry['connected_analysis'] = conn.to_dict()
        except Exception:
            pass
        return entry

    def create_factorial(self,factors,replicates=1,centers=0,randomize=True,seed=1,generators=None,blocks=1):
        from .doe import create_factorial
        if generators is None:worksheet=create_factorial(factors,replicates,centers,randomize,seed,blocks=blocks)
        else:
            from .fractional import create_fractional
            worksheet=create_fractional(factors,generators,replicates,centers,randomize,seed,blocks=blocks)
        self.new(); self.worksheet=worksheet; self.dirty=True
        result={'design':'Full two-level factorial' if generators is None else 'Regular fractional factorial','factors':len(factors),
            'runs':worksheet.row_count,'replicates':replicates,'center_points':centers*blocks,'blocks':blocks,
            'randomized':randomize,'seed':seed,'factor_coding':worksheet.metadata['doe']['factors'],
            'convention':'StdOrder identifies unrandomized design order; RunOrder identifies worksheet order. Add a response column after collecting results.'}
        if generators is not None:
            metadata=worksheet.metadata['doe']; result['resolution']=metadata['resolution']
            result['generators']=metadata['generators']
            from .fractional import alias_structure
            result['alias_structure']=[{'term':row['term'],'aliases':row['expression']} for row in alias_structure(generators,len(factors))['rows']]
        return self._record("Factorial Design",result)

    def analyze_factorial(self,response_index,factor_indices,max_order=2,confidence=.95,plot_residuals=True,show_factor_coding=True,selected_terms=None,include_blocks=None):
        if type(plot_residuals) is not bool or type(show_factor_coding) is not bool: raise ValueError("Choose valid DOE graph and result options.")
        from .doe import analyze_factorial
        result=analyze_factorial(self.worksheet,response_index,factor_indices,max_order,confidence,selected_terms,include_blocks=include_blocks)
        result['plot_residuals']=plot_residuals; result['show_factor_coding']=show_factor_coding
        result['effects']=[{'term':c['name'],'effect':c['effect'],'standard_error':c['effect_se'],'t':c['t'],'p_value':c['p_value'],
                            'ci_low':c['effect_ci_low'],'ci_high':c['effect_ci_high']} for c in result['coefficients'][1:]]
        parameters=dict(response_index=response_index,factor_indices=list(factor_indices),max_order=max_order,confidence=confidence,plot_residuals=plot_residuals,show_factor_coding=show_factor_coding)
        if include_blocks is not None: parameters['include_blocks']=include_blocks
        action='analyze_factorial'
        if selected_terms is not None:parameters['selected_terms']=selected_terms; action='analyze_factorial_terms'
        return self._record("Factorial Fit — "+self.worksheet.columns[response_index].name,result,recipe={'action':action,'parameters':parameters})

    def analyze_factorial_terms(self,**parameters):
        return self.analyze_factorial(**parameters)

    def create_definitive_screening_design(self, factors, replicates=1, extra_centers=0, randomize=True, seed=1, name="Definitive Screening Design"):
        from .dsd import create_definitive_screening_design
        worksheet = create_definitive_screening_design(factors, replicates=replicates, extra_centers=extra_centers, randomize=randomize, seed=seed, name=name)
        self.new()
        self.worksheet = worksheet
        self.dirty = True
        result = {
            "design": "Definitive Screening Design",
            "factors": len(factors),
            "runs": worksheet.row_count,
            "replicates": replicates,
            "extra_centers": extra_centers,
            "randomized": randomize,
            "seed": seed,
            "convention": "Definitive Screening Design with orthogonal main effects and foldover structure (Jones & Nachtsheim 2011).",
        }
        return self._record("Definitive Screening Design", result)

    def analyze_definitive_screening_design(self, response_index, factor_indices=None, selection='stepwise', alpha_enter=0.10, alpha_leave=0.05, confidence=95.0, show_pareto=True):
        from .dsd_analysis import analyze_definitive_screening_design
        result = analyze_definitive_screening_design(
            self.worksheet,
            response_index=response_index,
            factor_indices=factor_indices,
            selection=selection,
            alpha_enter=alpha_enter,
            alpha_leave=alpha_leave,
            confidence=confidence,
            show_pareto=show_pareto,
        )
        resp_name = self.worksheet.columns[response_index].name
        parameters = {
            "response_index": response_index,
            "factor_indices": factor_indices,
            "selection": selection,
            "alpha_enter": alpha_enter,
            "alpha_leave": alpha_leave,
            "confidence": confidence,
            "show_pareto": show_pareto,
        }
        return self._record(
            f"Definitive Screening Fit — {resp_name}",
            result,
            recipe={"action": "definitive_screening_analysis", "parameters": parameters},
        )

    def accelerated_life_testing(self, time_index, stress_index, censor_index=None, model='arrhenius', distribution='weibull', use_stress=25.0, confidence=95.0):
        from .alt_engine import fit_accelerated_life_test
        from .alt_report import format_alt_report, get_alt_structured_tables

        time_col = self.worksheet.columns[time_index]
        stress_col = self.worksheet.columns[stress_index]
        censor_col = self.worksheet.columns[censor_index] if censor_index is not None else None

        times, events, stresses = [], [], []
        n_rows = self.worksheet.row_count
        for r in range(n_rows):
            t_v = time_col.values[r]
            s_v = stress_col.values[r]
            if t_v is None or s_v is None or not isinstance(t_v, (int, float)) or not isinstance(s_v, (int, float)):
                continue
            if t_v <= 0 or not math.isfinite(t_v) or not math.isfinite(s_v):
                continue

            if censor_col is not None:
                c_v = censor_col.values[r]
                if c_v is None:
                    continue
                e_v = 1 if c_v in (1, 1.0, "1", "Failure", "Failed", "F") else 0
            else:
                e_v = 1

            times.append(float(t_v))
            events.append(e_v)
            stresses.append(float(s_v))

        result = fit_accelerated_life_test(
            times=times,
            events=events,
            stresses=stresses,
            model=model,
            distribution=distribution,
            use_stress=use_stress,
            confidence=confidence,
        )
        result["time_name"] = time_col.name
        result["stress_name"] = stress_col.name
        result["time_index"] = time_index
        result["stress_index"] = stress_index
        result["censor_index"] = censor_index
        result["tables"] = get_alt_structured_tables(result)
        result["session_text"] = format_alt_report({"result": result})

        parameters = {
            "time_index": time_index,
            "stress_index": stress_index,
            "censor_index": censor_index,
            "model": model,
            "distribution": distribution,
            "use_stress": use_stress,
            "confidence": confidence,
        }
        return self._record(
            f"Accelerated Life Testing — {time_col.name} vs {stress_col.name}",
            result,
            recipe={"action": "accelerated_life_testing", "parameters": parameters},
        )

    def evaluating_measurement_process(self, measurement_index, part_index, operator_index, alpha_interaction=0.05):
        from .emp_engine import evaluate_measurement_process
        from .emp_report import format_emp_report, get_emp_structured_tables

        m_col = self.worksheet.columns[measurement_index]
        p_col = self.worksheet.columns[part_index]
        o_col = self.worksheet.columns[operator_index]

        measurements, parts, operators = [], [], []
        n_rows = self.worksheet.row_count
        for r in range(n_rows):
            mv = m_col.values[r]
            pv = p_col.values[r]
            ov = o_col.values[r]
            if mv is None or pv is None or ov is None:
                continue
            if not isinstance(mv, (int, float)) or not math.isfinite(mv):
                continue
            measurements.append(float(mv))
            parts.append(pv)
            operators.append(ov)

        result = evaluate_measurement_process(
            measurements=measurements,
            parts=parts,
            operators=operators,
            alpha_interaction=alpha_interaction,
        )
        result["meas_name"] = m_col.name
        result["part_name"] = p_col.name
        result["op_name"] = o_col.name
        result["measurement_index"] = measurement_index
        result["part_index"] = part_index
        result["operator_index"] = operator_index
        result["alpha_interaction"] = alpha_interaction
        result["tables"] = get_emp_structured_tables(result)
        result["session_text"] = format_emp_report({"result": result})

        parameters = {
            "measurement_index": measurement_index,
            "part_index": part_index,
            "operator_index": operator_index,
            "alpha_interaction": alpha_interaction,
        }
        return self._record(
            f"Evaluating the Measurement Process — {m_col.name}",
            result,
            recipe={"action": "evaluating_measurement_process", "parameters": parameters},
        )

    def fit_y_by_x(self, y_index, x_index, platform=None, confidence=0.95):
        from .fit_y_by_x_engine import compute_fit_y_by_x
        from .fit_y_by_x_report import format_fit_y_by_x_report, get_fit_y_by_x_structured_tables

        result = compute_fit_y_by_x(
            self.worksheet,
            y_index=y_index,
            x_index=x_index,
            platform=platform,
            conf=confidence
        )
        result["analysis"] = "fit_y_by_x"
        result["tables"] = get_fit_y_by_x_structured_tables(result)
        result["session_text"] = format_fit_y_by_x_report({"result": result})

        parameters = {
            "y_index": y_index,
            "x_index": x_index,
            "platform": platform,
            "confidence": confidence
        }
        title = result.get("title", f"Fit Y by X — {self.worksheet.columns[y_index].name} by {self.worksheet.columns[x_index].name}")
        return self._record(
            title,
            result,
            recipe={"action": "fit_y_by_x", "parameters": parameters}
        )

    def jmp_distribution(self, column_indices, confidence=0.95):
        from .jmp_distribution_engine import compute_jmp_distribution
        from .jmp_distribution_report import format_jmp_distribution_report, get_jmp_distribution_structured_tables

        result = compute_jmp_distribution(
            self.worksheet,
            column_indices=column_indices,
            confidence=confidence
        )
        result["analysis"] = "jmp_distribution"
        result["tables"] = get_jmp_distribution_structured_tables(result)
        result["session_text"] = format_jmp_distribution_report({"result": result})

        parameters = {
            "column_indices": list(column_indices),
            "confidence": confidence
        }
        title = result.get("title", "Distributions")
        return self._record(
            title,
            result,
            recipe={"action": "jmp_distribution", "parameters": parameters}
        )

    def control_chart_builder(
        self,
        y_indices,
        subgroup_index=None,
        subgroup_size=1,
        phase_index=None,
        chart_type="auto",
        k_sigma=3.0,
    ):
        from .control_chart_builder_engine import calculate_control_chart_builder
        from .control_chart_builder_report import (
            format_control_chart_builder_report,
            get_control_chart_builder_tables,
        )

        y_idx = y_indices[0] if isinstance(y_indices, (list, tuple)) else y_indices
        y_col = self.worksheet.columns[y_idx]
        y_vals = y_col.values

        sub_vals = self.worksheet.columns[subgroup_index].values if subgroup_index is not None and 0 <= subgroup_index < len(self.worksheet.columns) else None
        sub_name = self.worksheet.columns[subgroup_index].name if subgroup_index is not None and 0 <= subgroup_index < len(self.worksheet.columns) else None

        ph_vals = self.worksheet.columns[phase_index].values if phase_index is not None and 0 <= phase_index < len(self.worksheet.columns) else None
        ph_name = self.worksheet.columns[phase_index].name if phase_index is not None and 0 <= phase_index < len(self.worksheet.columns) else None

        result = calculate_control_chart_builder(
            y_values=y_vals,
            subgroup_values=sub_vals,
            subgroup_size=subgroup_size,
            phase_values=ph_vals,
            y_name=y_col.name,
            subgroup_name=sub_name,
            phase_name=ph_name,
            chart_type=chart_type,
            k_sigma=k_sigma,
        )
        result["analysis"] = "control_chart_builder"
        result["tables"] = get_control_chart_builder_tables(result)
        result["session_text"] = format_control_chart_builder_report(result)

        parameters = {
            "y_indices": [y_idx],
            "subgroup_index": subgroup_index,
            "subgroup_size": subgroup_size,
            "phase_index": phase_index,
            "chart_type": chart_type,
            "k_sigma": k_sigma,
        }
        return self._record(
            result["title"],
            result,
            recipe={"action": "control_chart_builder", "parameters": parameters},
        )

    def process_screening(
        self,
        variable_indices,
        subgroup_size=1,
        subgroup_index=None,
        k_sigma=3.0,
    ):
        from .process_screening_engine import calculate_process_screening
        from .process_screening_report import (
            format_process_screening_report,
            get_process_screening_tables,
        )

        cols_data = []
        for idx in variable_indices:
            if 0 <= idx < len(self.worksheet.columns):
                c = self.worksheet.columns[idx]
                cols_data.append({"name": c.name, "index": idx, "values": c.values})

        sub_vals = self.worksheet.columns[subgroup_index].values if subgroup_index is not None and 0 <= subgroup_index < len(self.worksheet.columns) else None

        result = calculate_process_screening(
            columns_data=cols_data,
            subgroup_size=subgroup_size,
            subgroup_values=sub_vals,
            k_sigma=k_sigma,
        )
        result["analysis"] = "process_screening"
        result["tables"] = get_process_screening_tables(result)
        result["session_text"] = format_process_screening_report(result)

        parameters = {
            "variable_indices": list(variable_indices),
            "subgroup_size": subgroup_size,
            "subgroup_index": subgroup_index,
            "k_sigma": k_sigma,
        }
        return self._record(
            result["title"],
            result,
            recipe={"action": "process_screening", "parameters": parameters},
        )

    def cart_tree(self, response_index, predictor_indices, tree_type='auto', max_depth=5, min_split_size=10, min_leaf_size=5):
        from .tree_engine import fit_decision_tree
        from .tree_report import format_tree_report, get_tree_structured_tables

        r_col = self.worksheet.columns[response_index]
        p_cols = [self.worksheet.columns[i] for i in predictor_indices]

        n_rows = self.worksheet.row_count
        X_mat, y_vec = [], []

        for r in range(n_rows):
            y_val = r_col.values[r]
            if y_val is None:
                continue
            row = [c.values[r] for c in p_cols]
            X_mat.append(row)
            y_vec.append(y_val)

        feat_names = [c.name for c in p_cols]
        feat_kinds = ["numeric" if c.kind == "number" else "categorical" for c in p_cols]

        result = fit_decision_tree(
            X=X_mat,
            y=y_vec,
            feature_names=feat_names,
            feature_kinds=feat_kinds,
            tree_type=tree_type,
            max_depth=max_depth,
            min_split_size=min_split_size,
            min_leaf_size=min_leaf_size,
        )
        result["response_name"] = r_col.name
        result["response_index"] = response_index
        result["predictor_indices"] = predictor_indices
        result["tables"] = get_tree_structured_tables(result)
        result["session_text"] = format_tree_report({"result": result})

        parameters = {
            "response_index": response_index,
            "predictor_indices": predictor_indices,
            "tree_type": tree_type,
            "max_depth": max_depth,
            "min_split_size": min_split_size,
            "min_leaf_size": min_leaf_size,
        }
        return self._record(
            f"CART® {result['tree_type'].capitalize()} Tree — {r_col.name}",
            result,
            recipe={"action": "cart_tree", "parameters": parameters},
        )

    def create_optimal_design(self, factors, n_runs, model_order='interactions', randomize=True, seed=42, name='Custom D-Optimal Design'):
        from .optimal_design import create_optimal_design_worksheet
        from .optimal_report import format_optimal_design_report, get_optimal_structured_tables

        worksheet, result = create_optimal_design_worksheet(
            factors=factors,
            n_runs=n_runs,
            model_order=model_order,
            randomize=randomize,
            seed=seed,
            name=name,
        )
        self.new()
        self.worksheet = worksheet
        self.dirty = True

        result["tables"] = get_optimal_structured_tables(result)
        result["session_text"] = format_optimal_design_report({"result": result})

        return self._record(
            f"Custom D-Optimal Design — {n_runs} Runs",
            result,
        )

    def evaluate_design(self, factor_indices, model_order='interactions'):
        import numpy as np
        from .optimal_design import expand_model_matrix, evaluate_design_matrix
        from .optimal_report import format_optimal_design_report, get_optimal_structured_tables

        f_cols = [self.worksheet.columns[i] for i in factor_indices]
        n_runs = self.worksheet.row_count

        # Convert columns to coded [-1, 1] matrix
        coded_cols = []
        factors_info = []

        for col in f_cols:
            vals = col.values[:n_runs]
            if col.kind == "number":
                num_vals = [float(v) for v in vals if v is not None and not math.isnan(float(v))]
                min_v = min(num_vals) if num_vals else -1.0
                max_v = max(num_vals) if num_vals else 1.0
                rng_v = max_v - min_v if max_v > min_v else 1.0
                # Scale to [-1, 1]
                c_vec = [((float(v) - min_v) / rng_v * 2.0 - 1.0) if v is not None else 0.0 for v in vals]
                factors_info.append({"name": col.name, "kind": "continuous", "low": min_v, "high": max_v})
            else:
                unique_levs = sorted(list(set(str(v) for v in vals if v is not None)))
                lev0 = unique_levs[0] if unique_levs else "A"
                c_vec = [-1.0 if str(v) == lev0 else 1.0 for v in vals]
                factors_info.append({"name": col.name, "kind": "categorical", "levels": unique_levs[:2]})
            coded_cols.append(c_vec)

        X_coded = np.column_stack(coded_cols)
        X_model, term_names = expand_model_matrix(X_coded, model_order=model_order)

        # Replace X1, X2 with actual factor names
        pretty_terms = []
        for t in term_names:
            name_t = t
            for f_idx, col in enumerate(f_cols):
                name_t = name_t.replace(f"X{f_idx+1}", col.name)
            pretty_terms.append(name_t)

        eval_res = evaluate_design_matrix(X_model)

        result = {
            "analysis": "design_evaluation",
            "design_name": self.worksheet.name,
            "n_runs": n_runs,
            "model_order": model_order,
            "factors": factors_info,
            "factor_indices": factor_indices,
            "term_names": pretty_terms,
            "eval": eval_res,
        }
        result["tables"] = get_optimal_structured_tables(result)
        result["session_text"] = format_optimal_design_report({"result": result})

        parameters = {
            "factor_indices": factor_indices,
            "model_order": model_order,
        }
        return self._record(
            f"Design Evaluation — {self.worksheet.name}",
            result,
            recipe={"action": "evaluate_design", "parameters": parameters},
        )

    def scatter_plot(self,x_index,y_index,mode="simple",group_index=None,order="Increasing X",title="",x_label="",y_label=""):
        from .scatter import build
        parameters=dict(x_index=x_index,y_index=y_index,mode=mode,group_index=group_index,order=order,title=title,x_label=x_label,y_label=y_label)
        result=build(self.worksheet,**parameters)
        return self._record(result['plot_title'],result,recipe={"action":"scatter_plot","parameters":parameters})

    def one_variance(self, index=None, null_stdev=1., confidence=.95, settings=None):
        if settings is not None:
            from .one_variance_engine import compute_one_variance_sample
            mode = settings.get("mode", 0)
            perform_test = settings.get("perform_test", True)
            is_var = settings.get("is_variance_test", False)
            hyp_val = settings.get("hypothesized_value", 1.0)
            conf = settings.get("confidence_level", 95.0)
            alt = settings.get("alternative", "not_equal")

            samples = []
            if mode == 0:
                cols = settings.get("columns", [])
                for idx in cols:
                    col = self.worksheet.columns[idx]
                    s_res = compute_one_variance_sample(
                        sample_name=col.name,
                        values=col.values,
                        hypothesized_value=hyp_val,
                        is_variance_test=is_var,
                        perform_test=perform_test,
                        confidence_level=conf,
                        alternative=alt,
                    )
                    samples.append(s_res)
            elif mode == 1:
                s_res = compute_one_variance_sample(
                    sample_name="Sample",
                    sample_size=settings.get("sample_size"),
                    sample_stdev=settings.get("sample_stdev"),
                    hypothesized_value=hyp_val,
                    is_variance_test=is_var,
                    perform_test=perform_test,
                    confidence_level=conf,
                    alternative=alt,
                )
                samples.append(s_res)
            elif mode == 2:
                s_res = compute_one_variance_sample(
                    sample_name="Sample",
                    sample_size=settings.get("sample_size"),
                    sample_variance=settings.get("sample_variance"),
                    hypothesized_value=hyp_val,
                    is_variance_test=is_var,
                    perform_test=perform_test,
                    confidence_level=conf,
                    alternative=alt,
                )
                samples.append(s_res)

            names = ", ".join(s["name"] for s in samples) if samples else "Sample"
            title = f"Test and CI for One Variance: {names}"
            res_dict = {
                "one_variance_native": True,
                "samples": samples,
                "settings": dict(settings),
            }
            recipe = {"action": "one_variance", "parameters": {"settings": dict(settings)}}
            return self._record(title, res_dict, recipe=recipe)
        else:
            from .normality import one_variance
            column = self._selected_numeric([index])[0]
            return self._record("1 Variance — " + column.name, {"variable": column.name, **one_variance(column.numeric_values(True), null_stdev, confidence)},
                recipe={"action": "one_variance", "parameters": {"index": index, "null_stdev": null_stdev, "confidence": confidence}})

    def two_variances(self, settings=None, **kwargs):
        from .two_variances_engine import compute_two_variances
        st = dict(settings or {})
        st.update(kwargs)
        mode = st.get("mode", 1)
        conf = st.get("confidence_level", 95.0)
        hyp_ratio = st.get("hypothesized_ratio", 1.0)
        is_var_ratio = st.get("is_variance_ratio", False)
        alt = st.get("alternative", "not_equal")
        use_norm = st.get("use_normal_distribution", True)
        graphs = st.get("graphs", {})
        results_opts = st.get("results_options", {})

        if mode == 0:
            col_s = self.worksheet.columns[st["samples_col"]]
            col_id = self.worksheet.columns[st["subscripts_col"]]
            groups = {}
            for r in range(self.worksheet.row_count):
                if r < len(col_s.values) and r < len(col_id.values):
                    v = col_s.values[r]
                    gid = col_id.values[r]
                    if v is not None and gid is not None:
                        groups.setdefault(str(gid), []).append(v)
            gkeys = list(groups.keys())
            if len(gkeys) < 2:
                raise ValueError("Stacked layout requires at least two sample ID groups.")
            s1_name, s2_name = gkeys[0], gkeys[1]
            s1_vals, s2_vals = groups[s1_name], groups[s2_name]
            result = compute_two_variances(
                sample1_name=s1_name,
                sample2_name=s2_name,
                sample1_values=s1_vals,
                sample2_values=s2_vals,
                hypothesized_ratio=hyp_ratio,
                is_variance_ratio=is_var_ratio,
                confidence_level=conf,
                alternative=alt,
                use_normal_distribution=use_norm,
                graphs=graphs,
                results_options=results_opts,
            )
        elif mode == 1:
            col1 = self.worksheet.columns[st["s1_col"]]
            col2 = self.worksheet.columns[st["s2_col"]]
            result = compute_two_variances(
                sample1_name=col1.name,
                sample2_name=col2.name,
                sample1_values=col1.values,
                sample2_values=col2.values,
                hypothesized_ratio=hyp_ratio,
                is_variance_ratio=is_var_ratio,
                confidence_level=conf,
                alternative=alt,
                use_normal_distribution=use_norm,
                graphs=graphs,
                results_options=results_opts,
            )
        else:
            result = compute_two_variances(
                sample1_name="Sample 1",
                sample2_name="Sample 2",
                sample1_size=st.get("sample1_size"),
                sample1_stdev=st.get("sample1_stdev"),
                sample1_variance=st.get("sample1_variance"),
                sample2_size=st.get("sample2_size"),
                sample2_stdev=st.get("sample2_stdev"),
                sample2_variance=st.get("sample2_variance"),
                hypothesized_ratio=hyp_ratio,
                is_variance_ratio=is_var_ratio,
                confidence_level=conf,
                alternative=alt,
                use_normal_distribution=True,
                graphs=graphs,
                results_options=results_opts,
            )

        name1 = result.get("sample1", {}).get("name", "Sample 1")
        name2 = result.get("sample2", {}).get("name", "Sample 2")
        title = f"Test and CI for Two Variances: {name1}, {name2}"
        result["two_variances"] = True
        recipe = {"action": "two_variances", "parameters": {"settings": dict(st)}}
        return self._record(title, result, recipe=recipe)

    def multivari(self, response_index, factor_indices):
        from .multivari import compute_multivari
        res = compute_multivari(self.worksheet, response_index, factor_indices)
        resp_col = self.worksheet.columns[response_index]
        return self._record("Multi-Vari Chart for " + resp_col.name, res,
                            recipe={"action": "multivari", "parameters": {"response_index": response_index, "factor_indices": list(factor_indices)}})

    def outlier_test(self, variable_index, alpha=0.05, alternative='two-sided'):
        from .outlier_test import grubbs_test
        column = self._selected_numeric([variable_index])[0]
        res = grubbs_test(column.numeric_values(True), alpha=alpha, alternative=alternative)
        res['variable_name'] = column.name
        return self._record("Outlier Test: " + column.name, res,
                            recipe={"action": "outlier_test", "parameters": {"variable_index": variable_index, "alpha": alpha, "alternative": alternative}})

    @undoable
    def standardize(self, source_indices, target_indices=None, method='zscore'):
        from .standardize import standardize_column
        from .model import Column
        created_names = []
        for i, s_idx in enumerate(source_indices):
            s_col = self.worksheet.columns[s_idx]
            std_vals = standardize_column(s_col.values, method=method)
            if target_indices and i < len(target_indices) and 0 <= target_indices[i] < len(self.worksheet.columns):
                t_col = self.worksheet.columns[target_indices[i]]
                t_col.kind = 'number'
                t_col.values = std_vals
                t_col.metadata.pop("auto_type", None)
                created_names.append(t_col.name)
            else:
                new_name = f"Z_{s_col.name}" if method == 'zscore' else f"Std_{s_col.name}"
                new_col = Column(new_name, 'number', std_vals)
                self.worksheet.columns.append(new_col)
                created_names.append(new_name)
        self.dirty = True
        return self._record(f"Standardize ({method})", {"columns": created_names, "method": method})

    def graphical_summary(self, variable_index, confidence=0.95):
        from .graphical_summary import graphical_summary
        column = self._selected_numeric([variable_index])[0]
        res = graphical_summary(column.numeric_values(True), confidence=confidence)
        res['variable_name'] = column.name
        res['analysis'] = 'graphical_summary'
        return self._record("Summary Report for " + column.name, res,
                            recipe={"action": "graphical_summary", "parameters": {"variable_index": variable_index, "confidence": confidence}})

    def run_chart(self, variable_index, subgroup_size=1):
        from .run_chart import run_chart
        column = self._selected_numeric([variable_index])[0]
        res = run_chart(column.numeric_values(True), subgroup_size=subgroup_size)
        res['variable_name'] = column.name
        res['analysis'] = 'run_chart'
        return self._record("Run Chart of " + column.name, res,
                            recipe={"action": "run_chart", "parameters": {"variable_index": variable_index, "subgroup_size": subgroup_size}})

    @undoable
    def make_patterned_data(self, target_column_index, from_val, to_val, step=1.0, repeat_each=1, repeat_sequence=1):
        from .calc_data import make_patterned_numbers
        values = make_patterned_numbers(from_val, to_val, step, repeat_each, repeat_sequence)
        if target_column_index == -1 or target_column_index >= len(self.worksheet.columns):
            new_name = f"C{len(self.worksheet.columns) + 1}"
            from .model import Column
            col = Column(new_name, "number", values)
            self.worksheet.columns.append(col)
        else:
            col = self.worksheet.columns[target_column_index]
            col.kind = 'number'
            col.values = values
            col.metadata.pop("auto_type", None)
        self.dirty = True
        return self._record("Patterned Data — " + col.name, {"target_column": col.name, "rows": len(values)})

    @undoable
    def make_patterned_arbitrary(self, target_column_index, numbers, repeat_each=1, repeat_sequence=1):
        from .calc_data import make_patterned_arbitrary_numbers
        values = make_patterned_arbitrary_numbers(numbers, repeat_each, repeat_sequence)
        if target_column_index == -1 or target_column_index >= len(self.worksheet.columns):
            new_name = f"C{len(self.worksheet.columns) + 1}"
            from .model import Column
            col = Column(new_name, "number", values)
            self.worksheet.columns.append(col)
        else:
            col = self.worksheet.columns[target_column_index]
            col.kind = 'number'
            col.values = values
            col.metadata.pop("auto_type", None)
        self.dirty = True
        return self._record("Patterned Numbers — " + col.name, {"target_column": col.name, "rows": len(values)})

    @undoable
    def make_patterned_text_data(self, target_column_index, items, repeat_each=1, repeat_sequence=1):
        from .calc_data import make_patterned_text
        values = make_patterned_text(items, repeat_each, repeat_sequence)
        if target_column_index == -1 or target_column_index >= len(self.worksheet.columns):
            new_name = f"C{len(self.worksheet.columns) + 1}-T"
            from .model import Column
            col = Column(new_name, "text", values)
            self.worksheet.columns.append(col)
        else:
            col = self.worksheet.columns[target_column_index]
            col.kind = 'text'
            col.values = values
            col.metadata.pop("auto_type", None)
        self.dirty = True
        return self._record("Patterned Text — " + col.name, {"target_column": col.name, "rows": len(values)})

    @undoable
    def make_patterned_datetime_data(self, target_column_index, start_dt, end_dt=None, count=None, step=1, unit="days", repeat_each=1, repeat_sequence=1, dt_format="%Y-%m-%d"):
        from datetime import datetime
        from .calc_data import make_patterned_datetime
        from .model import Column, datetime_to_serial
        str_values = make_patterned_datetime(start_dt, end_dt, count, step, unit, repeat_each, repeat_sequence, dt_format)
        serial_values = []
        for s in str_values:
            for fmt_try in (dt_format, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(s, fmt_try)
                    serial_values.append(datetime_to_serial(dt))
                    break
                except ValueError:
                    continue
            else:
                serial_values.append(0.0)

        if target_column_index == -1 or target_column_index >= len(self.worksheet.columns):
            new_name = f"C{len(self.worksheet.columns) + 1}-D"
            col = Column(new_name, "date", serial_values)
            self.worksheet.columns.append(col)
        else:
            col = self.worksheet.columns[target_column_index]
            col.kind = 'date'
            col.values = serial_values
            col.metadata.pop("auto_type", None)
        self.dirty = True
        return self._record("Patterned Date/Time — " + col.name, {"target_column": col.name, "rows": len(serial_values)})

    @undoable
    def generate_random_data(self, target_column_index, dist='normal', n=50, param1=0.0, param2=1.0, seed=None):
        from .calc_data import (
            generate_random_normal, generate_random_uniform,
            generate_random_exponential, generate_random_poisson, generate_random_binomial
        )
        if dist == 'normal':
            values = generate_random_normal(n, mean=param1, stdev=param2, seed=seed)
        elif dist == 'uniform':
            values = generate_random_uniform(n, low=param1, high=param2, seed=seed)
        elif dist == 'exponential':
            values = generate_random_exponential(n, scale=param1, seed=seed)
        elif dist == 'poisson':
            values = generate_random_poisson(n, mean=param1, seed=seed)
        elif dist == 'binomial':
            values = generate_random_binomial(n, trials=int(param1), prob=param2, seed=seed)
        else:
            raise ValueError(f"Unsupported distribution: {dist}")
        if target_column_index == -1 or target_column_index >= len(self.worksheet.columns):
            new_name = f"C{len(self.worksheet.columns) + 1}"
            from .model import Column
            col = Column(new_name, "number", values)
            self.worksheet.columns.append(col)
        else:
            col = self.worksheet.columns[target_column_index]
            col.kind = 'number'
            col.values = values
            col.metadata.pop("auto_type", None)
        self.dirty = True
        return self._record(f"Random Data ({dist.title()}) — " + col.name, {"target_column": col.name, "rows": len(values), "distribution": dist})

    def _assign_or_append_column(self, target_column_index: int | str, values, kind: str = "number", default_name: str | None = None):
        from .model import Column
        if isinstance(target_column_index, str):
            dest = target_column_index.strip()
            if dest.isdigit() or (dest.upper().startswith("C") and dest[1:].isdigit()):
                idx = int(dest[1:] if dest.upper().startswith("C") else dest) - 1
            else:
                if not dest:
                    raise ValueError("Enter a destination column name.")
                col = Column(dest, kind, values)
                self.worksheet.columns.append(col)
                return col
        else:
            idx = target_column_index
        if idx == -1 or idx >= len(self.worksheet.columns):
            new_name = default_name or f"C{len(self.worksheet.columns) + 1}"
            col = Column(new_name, kind, values)
            self.worksheet.columns.append(col)
            return col
        col = self.worksheet.columns[idx]
        col.kind = kind
        col.values = values
        col.metadata.pop("auto_type", None)
        return col

    @undoable
    def generate_random_distribution_data(self, target_column_index, distribution: str, n: int = 50, parameters=(), seed=None):
        from .calc_data import generate_random_distribution
        values = generate_random_distribution(distribution, n, parameters, seed=seed)
        col = self._assign_or_append_column(target_column_index, values, "number")
        self.dirty = True
        return self._record(
            f"Random Data ({distribution}) — {col.name}",
            {"target_column": col.name, "rows": len(values), "distribution": distribution},
        )

    @undoable
    def sample_from_columns(self, source_indices, n: int = 10, replace: bool = False, seed=None):
        from .calc_data import sample_from_columns as _sample_cols
        if not source_indices:
            raise ValueError("Select at least one source column.")
        src_cols = [self.worksheet.columns[i] for i in source_indices]
        sampled = _sample_cols([c.values for c in src_cols], n, replace=replace, seed=seed)
        created = []
        for src_col, vals in zip(src_cols, sampled):
            new_col = self._assign_or_append_column(-1, vals, src_col.kind, default_name=f"{src_col.name}_Sample")
            created.append(new_col.name)
        self.dirty = True
        return self._record(
            "Sample from Columns",
            {"source_columns": [c.name for c in src_cols], "created_columns": created, "rows": n, "with_replacement": bool(replace)},
        )

    @undoable
    def row_statistics(self, source_indices, stat_name: str = "Mean", destination: str | int = "RowStat"):
        from .calc_data import compute_row_statistics
        cols = self._selected_numeric(source_indices)
        values = compute_row_statistics([c.values for c in cols], stat_name)
        col = self._assign_or_append_column(destination, values, "number")
        self.dirty = True
        return self._record(
            f"Row Statistics ({stat_name}) — {col.name}",
            {"statistic": stat_name, "variables": [c.name for c in cols], "destination": col.name, "rows": len(values)},
        )

    @undoable
    def column_statistics(self, col_index: int, stat_name: str = "Mean", store_constant_name: str | None = None):
        from .calc_data import compute_column_statistics
        from .model import Column
        col = self._selected_numeric([col_index])[0]
        val = compute_column_statistics(col.values, stat_name)
        stored_label = None
        if store_constant_name and store_constant_name.strip():
            cname = store_constant_name.strip()
            existing = next((c for c in self.worksheet.constants if c.name.casefold() == cname.casefold()), None)
            if existing is not None:
                existing.kind = "number"
                existing.values = [val]
            else:
                self.worksheet.constants.append(Column(cname, "number", [val]))
            stored_label = cname
            self.dirty = True
        return self._record(
            f"Column Statistics ({stat_name}) — {col.name}",
            {"variable": col.name, "statistic": stat_name, "value": val, "stored_constant": stored_label},
        )

    @undoable
    def make_indicator_variables(self, col_index: int, prefix: str = ""):
        from .data_prep import make_indicator_variables as _make_ind
        new_cols = _make_ind(self.worksheet, col_index, prefix=prefix)
        self.worksheet.columns.extend(new_cols)
        self.dirty = True
        return self._record(
            f"Make Indicator Variables — {self.worksheet.columns[col_index].name}",
            {"source": self.worksheet.columns[col_index].name, "created_columns": [c.name for c in new_cols]},
        )

    def subset_worksheet_by_condition(self, condition_expr: str, name: str = "Subset"):
        from .calculator import evaluate_advanced
        flags = evaluate_advanced(condition_expr, self.worksheet)
        matched_rows = [
            r for r, v in enumerate(flags)
            if v is not None and v not in (0, 0.0, False, "")
        ]
        if not matched_rows:
            raise ValueError("No rows matched the specified condition.")
        new_sheet = self.subset_worksheet(name=name or None, mode="include", row_indices=matched_rows)
        return self._record(
            f"Subset Worksheet — {new_sheet.name}",
            {"condition": condition_expr, "matched_rows": len(matched_rows), "worksheet": new_sheet.name},
        )

    @undoable
    def round_datetime(self, col_index: int, unit: str = "Day", destination: str = ""):
        from .data_prep import round_datetime_column
        serials = round_datetime_column(self.worksheet, col_index, unit=unit)
        dest = destination.strip() if destination and destination.strip() else col_index
        col = self._assign_or_append_column(dest, serials, "date")
        self.dirty = True
        return self._record(
            f"Round Date/Time ({unit}) — {col.name}",
            {"source": self.worksheet.columns[col_index].name, "unit": unit, "destination": col.name, "rows": len(serials)},
        )

    @undoable
    def convert_text_to_datetime(self, col_index: int, date_format: str = "", destination: str = ""):
        from .data_prep import convert_text_to_datetime_column
        serials = convert_text_to_datetime_column(self.worksheet, col_index, fmt=date_format)
        dest = destination.strip() if destination and destination.strip() else col_index
        col = self._assign_or_append_column(dest, serials, "date")
        self.dirty = True
        return self._record(
            f"Convert Text to Date/Time — {col.name}",
            {"source": self.worksheet.columns[col_index].name, "format": date_format or "Auto", "destination": col.name, "rows": len(serials)},
        )

    def covariance(self, indices, missing="Pairwise"):
        from .covariance import compute_covariance
        columns = self._selected_numeric(indices)
        result = compute_covariance([c.numeric_values(True) for c in columns], [c.name for c in columns], missing)
        return self._record("Covariance", result, recipe={"action":"covariance", "parameters":{
            "indices":list(indices), "missing":missing}})

    def stem_and_leaf(self, index):
        from .stem_leaf import compute_stem_leaf
        column = self._selected_numeric([index])[0]
        result = compute_stem_leaf(column.numeric_values(True), column.name)
        return self._record("Stem-and-Leaf — " + column.name, result, recipe={"action":"stem_and_leaf", "parameters":{
            "index":index}})

    def normality(self, index):
        from .normality import normality
        column=self._selected_numeric([index])[0]
        return self._record("Normality Test — "+column.name, {"variable":column.name, **normality(column.numeric_values(True))},
                            recipe={"action":"normality", "parameters":{"index":index}})

    def correlation(self, indices, method="Pearson", missing="Pairwise", confidence=.95):
        from .basic_stats import correlation
        columns = self._selected_numeric(indices)
        result = correlation([c.numeric_values(True) for c in columns], [c.name for c in columns], method, missing, confidence)
        return self._record(method + " Correlation", result, recipe={"action":"correlation", "parameters":{
            "indices":list(indices), "method":method, "missing":missing, "confidence":confidence}})

    def one_proportion(self, index, null_proportion=.5, confidence=.95, alternative="two-sided"):
        from .basic_stats import one_proportion
        column = self._selected_numeric([index])[0]
        result = one_proportion(column.numeric_values(True), null_proportion, confidence, alternative)
        return self._record("1 Proportion — " + column.name, {"variable":column.name, **result}, recipe={"action":"one_proportion", "parameters":{
            "index":index, "null_proportion":null_proportion, "confidence":confidence, "alternative":alternative}})

    def two_proportions(self, first_index, second_index, confidence=.95):
        from .basic_stats import two_proportions
        columns = self._selected_numeric([first_index,second_index])
        result = two_proportions(columns[0].numeric_values(True), columns[1].numeric_values(True), confidence)
        for record,column in zip(result['samples'],columns): record['variable'] = column.name
        return self._record("2 Proportions", result, recipe={"action":"two_proportions", "parameters":{
            "first_index":first_index, "second_index":second_index, "confidence":confidence}})

    def inference(self, method, indices, mu=0.0, confidence=0.95):
        from . import inference
        columns = [self.worksheet.columns[i] for i in indices]
        if any(c.kind != "number" for c in columns):
            raise ValueError("Select numeric columns.")
        values = [c.numeric_values(True) for c in columns]
        if method == "one_sample_t" and len(values) == 1:
            result = inference.one_sample_t(values[0], mu, confidence)
        elif method == "two_sample_t" and len(values) == 2:
            result = inference.two_sample_t(values[0], values[1], mu, confidence)
        elif method in ("paired_t", "linear_regression") and len(values) == 2:
            size = max(map(len, values))
            aligned = [v + [None] * (size - len(v)) for v in values]
            if method == "paired_t":
                result = inference.paired_t(aligned[0], aligned[1], mu, confidence)
            else:
                result = inference.linear_regression(aligned[0], aligned[1], confidence)
        elif method == "one_way_anova" and len(values) >= 2:
            result = inference.one_way_anova(values)
        else:
            raise ValueError("Select the required number of columns for this method.")
        return self._record(method.replace("_", " ").title(), {"variables": [c.name for c in columns], **result},
                            recipe={"action":"inference", "parameters":{"method":method, "indices":list(indices), "mu":mu, "confidence":confidence}})

    def attribute_chart(self, chart, count_index, size_index):
        from .attribute_quality import p_chart, u_chart
        if count_index == size_index:
            raise ValueError("Choose separate count and sample-size columns.")
        if chart not in ("P", "U"):
            raise ValueError("Choose a P or U chart.")
        count = self.worksheet.columns[count_index]
        size = self.worksheet.columns[size_index]
        if count.kind != "number" or size.kind != "number":
            raise ValueError("Choose numeric count and sample-size columns.")
        counts, sizes = count.numeric_values(True), size.numeric_values(True)
        length = max(len(counts), len(sizes))
        counts += [None] * (length - len(counts))
        sizes += [None] * (length - len(sizes))
        result = (p_chart if chart == "P" else u_chart)(counts, sizes)
        return self._record(chart + " Chart — " + count.name,
                            {**result, "count_variable": count.name, "size_variable": size.name},
                            recipe={"action":"attribute_chart", "parameters":{"chart":chart, "count_index":count_index, "size_index":size_index}})

    def stacked_anova(self, response_index, factor_index):
        from .grouped import stacked_anova
        if response_index == factor_index:
            raise ValueError("Choose separate response and factor columns.")
        response = self.worksheet.columns[response_index]
        factor = self.worksheet.columns[factor_index]
        if response.kind != "number" or factor.kind not in ("number", "text"):
            raise ValueError("Choose a numeric response and a numeric or text factor.")
        result = stacked_anova(response.numeric_values(True), factor.values,factor)
        return self._record("One-Way ANOVA — " + response.name + " versus " + factor.name,
                            {**result, "response_name": response.name, "factor_name": factor.name},
                            recipe={"action":"stacked_anova", "parameters":{"response_index":response_index, "factor_index":factor_index}})

    def equal_variances_columns(self, indices, method="Levene"):
        from .variance_tests import equal_variances
        if len(indices) < 2 or len(set(indices)) != len(indices):
            raise ValueError("Choose at least two distinct numeric group columns.")
        columns = [self.worksheet.columns[i] for i in indices]
        values = [c.numeric_values(True) for c in columns]
        result = equal_variances(values, method)
        return self._record("Test for Equal Variances — " + method,
            {**result, "variance_test":True, "variables":[c.name for c in columns]},
            recipe={"action":"equal_variances_columns", "parameters":{"indices":list(indices),"method":method}})

    def equal_variances_stacked(self, response_index, factor_index, method="Levene"):
        from .variance_tests import equal_variances
        from .grouped import group_pairs
        if response_index == factor_index:
            raise ValueError("Choose separate response and factor columns.")
        response, factor = self.worksheet.columns[response_index], self.worksheet.columns[factor_index]
        if response.kind != "number" or factor.kind not in ("number","text"):
            raise ValueError("Choose a numeric response and a numeric or text factor.")
        groups, levels, missing_rows, used_rows = group_pairs(response.numeric_values(True),factor.values,factor)
        result = equal_variances(groups,method)
        if missing_rows:
            result["warnings"].append(str(len(missing_rows)) + " incomplete response/factor pairs omitted.")
        return self._record("Test for Equal Variances — " + response.name + " versus " + factor.name,
            {**result, "variance_test":True, "variables":[str(level) for level in levels],
             "factor_levels":levels, "missing":len(missing_rows), "missing_rows":missing_rows, "used_rows":used_rows},
            recipe={"action":"equal_variances_stacked", "parameters":{"response_index":response_index,"factor_index":factor_index,"method":method}})

    def test_equal_variances(self, stacked=True, response_index=None, factor_indices=None, response_indices=None, options=None):
        from .equal_variances_engine import run_test_equal_variances, store_equal_variances_columns
        result = run_test_equal_variances(
            self.worksheet,
            stacked=stacked,
            response_index=response_index,
            factor_indices=factor_indices,
            response_indices=response_indices,
            options=options,
        )
        store_equal_variances_columns(self.worksheet, result, options)
        title = "Test for Equal Variances: " + result["response_name"]
        if result.get("factor_names"):
            title += " versus " + ", ".join(result["factor_names"])
        recipe = {
            "action": "test_equal_variances",
            "parameters": {
                "stacked": bool(stacked),
                "response_index": response_index,
                "factor_indices": list(factor_indices) if factor_indices is not None else None,
                "response_indices": list(response_indices) if response_indices is not None else None,
                "options": dict(result["options"]),
            },
        }
        result["test_equal_variances"] = True
        result["equal_variances"] = True
        result["graph"] = "equal_variances"
        return self._record(title, result, recipe=recipe)

    def one_sample_z(self, settings=None):
        from .one_sample_z_engine import run_one_sample_z, one_sample_z_settings
        st = one_sample_z_settings(**(settings or {}))
        result = run_one_sample_z(self.worksheet, st)
        samples = result.get("samples", [])
        sample_names = ", ".join(s["name"] for s in samples) if samples else "Sample"
        title = f"One-Sample Z: {sample_names}"
        recipe = {
            "action": "one_sample_z",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["one_sample_z"] = True
        result["graph"] = "one_sample_z"
        return self._record(title, result, recipe=recipe)

    def one_sample_proportion(self, settings=None):
        from .one_sample_proportion_engine import run_one_sample_proportion, one_sample_proportion_settings
        st = one_sample_proportion_settings(**(settings or {}))
        result = run_one_sample_proportion(self.worksheet, st)
        samples = result.get("samples", [])
        sample_names = ", ".join(s["name"] for s in samples) if samples else "Sample"
        title = f"Test and CI for One Proportion: {sample_names}" if st.get("data_format") != 2 else "Test and CI for One Proportion"
        recipe = {
            "action": "one_sample_proportion",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["one_sample_proportion"] = True
        return self._record(title, result, recipe=recipe)

    def two_sample_poisson(self, settings=None, **kwargs):
        from .two_sample_poisson_engine import run_two_sample_poisson, two_sample_poisson_settings
        cfg = dict(settings or {})
        cfg.update(kwargs)
        st = two_sample_poisson_settings(**cfg)
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

    def one_sample_poisson(self, settings=None):
        from .one_sample_poisson_engine import run_one_sample_poisson, one_sample_poisson_settings
        st = one_sample_poisson_settings(**(settings or {}))
        result = run_one_sample_poisson(self.worksheet, st)
        samples = result.get("samples", [])
        sample_names = ", ".join(s["sample_name"] for s in samples) if samples else "Sample"
        title = f"Test and CI for One-Sample Poisson Rate: {sample_names}" if st.get("data_format") == 0 else "Test and CI for One-Sample Poisson Rate"
        recipe = {
            "action": "one_sample_poisson",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["one_sample_poisson"] = True
        return self._record(title, result, recipe=recipe)

    def one_sample_t(self, settings=None):
        from .one_sample_t_engine import run_one_sample_t, one_sample_t_settings
        st = one_sample_t_settings(**(settings or {}))
        result = run_one_sample_t(self.worksheet, st)
        samples = result.get("samples", [])
        sample_names = ", ".join(s["name"] for s in samples) if samples else "Sample"
        title = f"One-Sample T-Test and CI: {sample_names}"
        recipe = {
            "action": "one_sample_t",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["one_sample_t"] = True
        result["graph"] = "one_sample_t"
        return self._record(title, result, recipe=recipe)
    def two_sample_t(self, settings=None):
        from .two_sample_t_engine import run_two_sample_t, two_sample_t_settings
        st = two_sample_t_settings(**(settings or {}))
        result = run_two_sample_t(self.worksheet, st)
        s1 = result["sample1"]["name"]
        s2 = result["sample2"]["name"]
        title = f"Two-Sample T-Test and CI: {s1}, {s2}"
        recipe = {
            "action": "two_sample_t",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["two_sample_t"] = True
        result["graph"] = "two_sample_t"
        return self._record(title, result, recipe=recipe)

    def two_sample_proportion(self, settings=None):
        from .two_sample_proportion_engine import run_two_sample_proportion, two_sample_proportion_settings
        st = two_sample_proportion_settings(**(settings or {}))
        result = run_two_sample_proportion(self.worksheet, st)
        s1 = result["sample1"]["name"]
        s2 = result["sample2"]["name"]
        title = f"Test and CI for Two Proportions: {s1}, {s2}" if st.get("data_format") != 2 else "Test and CI for Two Proportions"
        recipe = {
            "action": "two_sample_proportion",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["two_sample_proportion"] = True
        return self._record(title, result, recipe=recipe)

    def paired_t(self, settings=None):
        from .paired_t_engine import run_paired_t, paired_t_settings
        st = paired_t_settings(**(settings or {}))
        result = run_paired_t(self.worksheet, st)
        s1 = result.get("sample1_name", "Sample 1")
        s2 = result.get("sample2_name", "Sample 2")
        title = f"Paired T-Test and CI: {s1}, {s2}" if result.get("data_format") != 2 else "Paired T-Test and CI"
        recipe = {
            "action": "paired_t",
            "parameters": {
                "settings": dict(st),
            },
        }
        result["paired_t"] = True
        result["graph"] = "paired_t"
        return self._record(title, result, recipe=recipe)


    def _record(self, title, result, persist=True, recipe=None):
        from uuid import uuid4
        entry = {"time": datetime.now().isoformat(timespec="seconds"),
                 'entry_id':str(uuid4()),
                 "title": title, "result": copy.deepcopy(result),
                 "origin": "statcraft" if persist else "native",
                 "worksheet_name": self.worksheet.name,
                 "worksheet_id": self.native_project.worksheet_ids[self.native_project.active_index] if self.native_project else None}
        if recipe is not None:
            from .recipes import columns, fingerprints
            from .analysis_bindings import ACTIONS, KEY, normalize
            recipe = copy.deepcopy(recipe)
            if recipe.get('action') in ACTIONS and 'settings' in recipe.get('parameters', {}):
                # Each output can represent one variable from a multi-variable dialog.
                settings = recipe['parameters']['settings']
                settings.pop(KEY, None)
                recipe['parameters']['settings'] = normalize(recipe['action'], self.worksheet, settings)
            entry["recipe"] = copy.deepcopy(recipe)
            entry["dependencies"] = fingerprints(self.worksheet, columns(recipe))
        self.history.append(entry)
        if len(self.history) > 100:
            self.history.pop(0)
        if persist and self.native_project is not None:
            self._results_dirty = True
        return entry

    def result_worksheet(self, entry):
        if self.native_project:
            identifier = entry.get("worksheet_id")
            if identifier not in self.native_project.worksheet_ids:
                raise ValueError("The result's source worksheet is unavailable.")
            return self.native_project.worksheets[self.native_project.worksheet_ids.index(identifier)]
        if entry.get("worksheet_id") is not None or entry.get("worksheet_name") != self.worksheet.name:
            raise ValueError("The result's source worksheet is unavailable.")
        return self.worksheet

    def result_stale(self, entry, cache=None):
        """True/False for tracked inputs; None for legacy/native snapshots."""
        if entry.get('source_unavailable'):
            return True
        if "recipe" not in entry or "dependencies" not in entry:
            return None
        from .recipes import columns, fingerprints
        try:
            sheet = self.result_worksheet(entry)
            indices = columns(entry["recipe"])
            if cache is None:
                current = fingerprints(sheet, indices)
            else:
                current = []
                for index in indices:
                    key = (id(sheet), index)
                    if key not in cache:
                        cache[key] = fingerprints(sheet, [index])[0]
                    current.append(cache[key])
            return current != entry["dependencies"]
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            return True

    def rerun_result(self, entry):
        if entry.get('source_unavailable'):
            raise ValueError(str(entry['source_unavailable']))
        if entry.get("origin") != "statcraft" or "recipe" not in entry:
            raise ValueError("This snapshot has no supported rerun recipe. Run the analysis from its menu.")
        from .recipes import columns, fingerprints, run
        from .analysis_bindings import ACTIONS, KEY, normalize
        source = self.result_worksheet(entry)
        recipe = copy.deepcopy(entry["recipe"])
        if recipe.get('action') in ACTIONS and 'settings' in recipe.get('parameters', {}):
            settings = recipe['parameters']['settings']
            if KEY not in settings:
                # Older name-only records cannot safely infer identity after an edit.
                try:
                    migrated = normalize(recipe['action'], source, settings)
                    candidate = {'action': recipe['action'], 'parameters': {'settings': migrated}}
                    dependencies = fingerprints(source, columns(candidate))
                    if 'dependencies' not in entry or dependencies != entry['dependencies']:
                        raise ValueError('Saved source fingerprints no longer match.')
                    recipe = candidate
                except (ValueError, TypeError, KeyError, IndexError) as error:
                    raise ValueError('This older result has no verified source bindings. Run the analysis again and select its source columns.') from error
        columns(recipe)
        previous = self.worksheet
        previous_index = self.native_project.active_index if self.native_project else None
        history_before=list(self.history);results_dirty_before=self._results_dirty
        try:
            self.worksheet = source
            if self.native_project:
                self.native_project.active_index = next(i for i, sheet in enumerate(self.native_project.worksheets) if sheet is source)
            result=run(self, recipe)
            if 'graph_presentation' in entry:
                from .graph_presentation import validate_presentation
                result['graph_presentation']=validate_presentation(entry['graph_presentation'])
            for field in ('graph_styles','histogram_settings'):
                if field in entry:
                    if field=='graph_styles':
                        from .graph_styles import validate_styles
                        result[field]=validate_styles(entry[field])
                    else:
                        from .histogram_options import validate_histogram_settings
                        result[field]=validate_histogram_settings(entry[field])
                        from .histogram_options import build_histogram_panel
                        build_histogram_panel(result['result'].get('histogram_source'),result[field])
            return result
        except Exception:
            self.history[:]=history_before;self._results_dirty=results_dirty_before
            self.worksheet = previous
            if self.native_project:
                self.native_project.active_index = previous_index
            raise

    def describe_column(self, index):
        from .analyses import describe
        col = self.worksheet.columns[index]
        values = col.numeric_values(include_missing=True)
        return self._record("Descriptive statistics — " + col.name, describe(values),
                            recipe={"action":"describe_column", "parameters":{"index":index}})

    def weibull(self, method, shape, scale, location=0.0, value=None):
        if method == "mean":
            result = engine.weibull_mean(shape, scale, location)
        elif method == "pdf":
            result = engine.weibull_pdf(value, shape, scale, location)
        elif method == "cdf":
            result = engine.weibull_cdf(value, shape, scale, location)
        else:
            raise ValueError("Choose Weibull PDF, CDF or mean.")
        return self._record("Weibull " + method.upper(),
                            {"shape": shape, "scale": scale, "location": location,
                             "value": value if method != "mean" else "not applicable", "result": result})

    def solve(self, packed, rhs, transpose=False):
        result = engine.packed_triangular_solve(packed, rhs, transpose)
        if result.status != -1:
            raise ValueError("Singular system: diagonal entry " + str(result.status + 1) + " is zero. No solution was recorded.")
        return self._record("Packed triangular solve", {"packed_upper": list(packed), "rhs": list(rhs),
                                                       "transpose": transpose, "solution": result.solution})

    @undoable
    def cut_block(self, first_row, last_row, first_column, last_column):
        text = self.copy_block(first_row, last_row, first_column, last_column)
        for col_index in range(first_column, last_column + 1):
            col = self.worksheet.columns[col_index]
            for row in range(first_row, min(last_row + 1, len(col.values))):
                col.values[row] = "" if col.kind == "text" else None
        self.dirty = True
        return text

    @undoable
    def insert_cells(self, row, first_column, last_column, count=1):
        if type(row) is not int or row < 0 or type(count) is not int or count < 1:
            raise ValueError("Choose a valid starting row and positive cell count.")
        if min(first_column, last_column) < 0 or last_column >= len(self.worksheet.columns) or first_column > last_column:
            raise ValueError("Select existing worksheet columns.")
        if (max(self.worksheet.row_count, row) + count) * len(self.worksheet.columns) > io.MAX_CELLS:
            raise ValueError("The worksheet exceeds the cell limit.")
        for col_index in range(first_column, last_column + 1):
            col = self.worksheet.columns[col_index]
            if row < len(col.values):
                col.values[row:row] = [None] * count
        self.dirty = True

    @undoable
    def insert_rows(self, row, count=1):
        if type(row) is not int or row < 0 or type(count) is not int or count < 1:
            raise ValueError("Choose a valid row position and positive row count.")
        if (max(self.worksheet.row_count, row) + count) * max(1, len(self.worksheet.columns)) > io.MAX_CELLS:
            raise ValueError("The worksheet exceeds the cell limit.")
        for col in self.worksheet.columns:
            if self.native_project is not None and col.metadata.get("unsupported_native_storage") == "untyped-empty-v0":
                continue
            if row < len(col.values):
                col.values[row:row] = [None] * count
            elif len(col.values) > 0:
                col.values.extend([None] * count)
        self.dirty = True

    @undoable
    def insert_columns(self, index, count=1, kind="number"):
        if type(index) is not int or not 0 <= index <= len(self.worksheet.columns) or type(count) is not int or count < 1:
            raise ValueError("Choose a valid column insertion position and positive count.")
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            from .mpx_columns import preflight
            preflight(self.native_project,self.worksheet)
            if kind != 'number':
                raise ValueError('Inserted columns in imported projects currently require numeric storage.')
        if (len(self.worksheet.columns) + count) * max(1, self.worksheet.row_count) > io.MAX_CELLS:
            raise ValueError("The worksheet exceeds the cell limit.")
        new_cols = [Column("C" + str(index + i + 1), kind, metadata={"auto_type": True}) for i in range(count)]
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            from .mpx_columns import independent_metadata
            for col in new_cols: col.metadata=independent_metadata()
        self.worksheet.columns[index:index] = new_cols
        for i, col in enumerate(self.worksheet.columns):
            if col.name.startswith("C") and col.name[1:].isdigit():
                col.name = "C" + str(i + 1)
        self.dirty = True

    @undoable
    def move_columns(self, indices, destination="after_last", before_column=0):
        if not indices or any(type(i) is not int or not 0 <= i < len(self.worksheet.columns) for i in indices) or len(set(indices)) != len(indices):
            raise ValueError("Select one or more distinct columns to move.")
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            from .mpx_columns import preflight
            preflight(self.native_project,self.worksheet)
        selected_set = set(indices)
        moving = [self.worksheet.columns[i] for i in indices]
        remaining = [col for i, col in enumerate(self.worksheet.columns) if i not in selected_set]
        if destination == "before_c1":
            updated = moving + remaining
        elif destination == "after_last":
            def used(col):
                return bool(col.values or col.name != 'C'+str(next(i for i,c in enumerate(self.worksheet.columns) if c is col)+1)
                            or set(col.metadata)-{'auto_type'})
            last=max((i for i,col in enumerate(remaining) if used(col)),default=-1)+1
            updated = remaining[:last] + moving + remaining[last:]
        elif destination == "before_column":
            if type(before_column) is not int or not 0 <= before_column < len(self.worksheet.columns):
                raise ValueError("Choose a valid target column.")
            target_col = self.worksheet.columns[before_column]
            if any(target_col is col for col in moving):
                raise ValueError("Choose a target column that is not among the moved columns.")
            pos = next(i for i,col in enumerate(remaining) if col is target_col)
            updated = remaining[:pos] + moving + remaining[pos:]
        else:
            raise ValueError("Choose a valid column destination.")
        for i, col in enumerate(updated):
            if col.name.startswith("C") and col.name[1:].isdigit():
                col.name = "C" + str(i + 1)
        self.worksheet.columns = updated
        self.dirty = True

    @undoable
    def delete_rows(self, rows, indices=None):
        row_set = sorted({int(r) for r in rows})
        if not row_set or any(r < 0 or r >= self.worksheet.row_count for r in row_set):
            raise ValueError("Enter existing 1-based row numbers.")
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            raise ValueError("Deleting rows in imported native projects is not supported.")
        targets = range(len(self.worksheet.columns)) if indices is None else indices
        for col_index in targets:
            col = self.worksheet.columns[col_index]
            for r in reversed(row_set):
                if r < len(col.values):
                    del col.values[r]
        self.dirty = True

    @undoable
    def erase_variables(self, indices=(), clear_constants=False, clear_matrices=False):
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            raise ValueError("Erasing variables in imported native projects is not supported.")
        for index in indices:
            if not 0 <= index < len(self.worksheet.columns):
                raise ValueError("Choose existing columns to erase.")
            col = self.worksheet.columns[index]
            col.name = "C" + str(index + 1)
            col.kind = "number"
            col.values = []
            col.metadata = {"auto_type": True}
        if clear_constants:
            self.worksheet.constants = []
        if clear_matrices:
            self.worksheet.matrices = []
        self.dirty = True

    @undoable
    def duplicate_column(self, col_index):
        if not 0 <= col_index < len(self.worksheet.columns):
            raise ValueError("Select a valid column to duplicate.")
        col = self.worksheet.columns[col_index]
        new_name = f"{col.name} (Copy)"
        existing_names = {c.name for c in self.worksheet.columns}
        count = 1
        while new_name in existing_names:
            count += 1
            new_name = f"{col.name} (Copy {count})"
        new_col = Column(new_name, col.kind, list(col.values), metadata=copy.deepcopy(col.metadata))
        insert_pos = col_index + 1
        self.worksheet.columns.insert(insert_pos, new_col)
        self.dirty = True
        return insert_pos

    @undoable
    def sort_columns(self, target_indices, by_index, descending=False):
        if not target_indices or any(not 0 <= i < len(self.worksheet.columns) for i in target_indices):
            raise ValueError("Select at least one column to sort.")
        by_indices = [by_index] if isinstance(by_index, int) else list(by_index)
        if not by_indices or any(not 0 <= i < len(self.worksheet.columns) for i in by_indices):
            raise ValueError("Select a valid column to sort by.")
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            raise ValueError("Sorting in imported native projects is supported via Save Copy on StatCraft-owned workbooks.")
        by_cols = [self.worksheet.columns[i] for i in by_indices]
        rows = max([len(c.values) for c in by_cols] + [len(self.worksheet.columns[i].values) for i in target_indices])
        if rows == 0:
            raise ValueError("Selected columns contain no observations to sort.")

        def sort_key_for_row(r):
            key_parts = []
            has_missing = False
            for col in by_cols:
                val = col.values[r] if r < len(col.values) else None
                if val is None or (col.kind == "text" and val == ""):
                    has_missing = True
                    key_parts.append((1, ""))
                else:
                    k = str(val).casefold() if col.kind == "text" else float(val)
                    key_parts.append((0, k))
            return (1 if has_missing else 0, tuple(key_parts), r)

        present, missing = [], []
        for r in range(rows):
            k = sort_key_for_row(r)
            if k[0] == 1:
                missing.append(r)
            else:
                present.append((k, r))

        present.sort(key=lambda item: item[0], reverse=bool(descending))
        order = [r for _, r in present] + missing
        for idx in set(target_indices):
            col = self.worksheet.columns[idx]
            padded = list(col.values) + [None] * (rows - len(col.values))
            col.values = [padded[r] for r in order]
        if len(set(target_indices)) == len(self.worksheet.columns) or set(target_indices) >= {i for i, c in enumerate(self.worksheet.columns) if c.values}:
            from .connect import permute_row_identities
            permute_row_identities(self.worksheet, order)
        self.dirty = True
        by_names = ", ".join(c.name for c in by_cols)
        return self._record("Sort — by " + by_names, {
            "sorted_columns": [self.worksheet.columns[i].name for i in target_indices],
            "by_variable": by_names,
            "order": "Descending" if descending else "Ascending",
            "rows_sorted": rows,
        })

    @undoable
    def rank_column(self, source_index, destination):
        if not 0 <= source_index < len(self.worksheet.columns) or self.worksheet.columns[source_index].kind != "number":
            raise ValueError("Select a numeric column to rank.")
        col = self.worksheet.columns[source_index]
        ranks = [None] * len(col.values)
        present_idx = [i for i, v in enumerate(col.values) if v is not None]
        if not present_idx:
            raise ValueError("Selected column has no nonmissing numeric values.")
        ordered = sorted((float(col.values[i]), pos) for pos, i in enumerate(present_idx))
        computed = [0.0] * len(present_idx)
        k = 0
        while k < len(ordered):
            end = k + 1
            while end < len(ordered) and ordered[end][0] == ordered[k][0]:
                end += 1
            avg_rank = (k + 1 + end) / 2.0
            for m in range(k, end):
                computed[ordered[m][1]] = avg_rank
            k = end
        for pos, r_val in zip(present_idx, computed):
            ranks[pos] = engine.normalize_numeric(r_val)
        dest = destination.strip()
        if dest.upper().startswith("C") and dest[1:].isdigit():
            dest_idx = int(dest[1:]) - 1
        elif dest.isdigit():
            dest_idx = int(dest) - 1
        else:
            dest_idx = None
        if dest_idx is not None and 0 <= dest_idx < len(self.worksheet.columns):
            target = self.worksheet.columns[dest_idx]
            target.kind = "number"
            target.values = ranks
            target.metadata.pop("auto_type", None)
            stored_name = target.name
        else:
            if not dest:
                raise ValueError("Enter a destination column or name.")
            self.worksheet.columns.append(Column(dest, "number", ranks))
            stored_name = dest
        self.dirty = True
        return self._record("Rank — " + col.name, {"source": col.name, "destination": stored_name, "count": len(present_idx)})

    @undoable
    def assign_formula(self, index, expression):
        if not 0 <= index < len(self.worksheet.columns):
            raise ValueError("Select an existing column.")
        from .formulas import recalculate
        from .calculator import parse_expression
        parse_expression(expression)
        col = self.worksheet.columns[index]
        col.kind = "number"
        col.metadata["formula"] = expression.strip()
        col.metadata.pop("auto_type", None)
        recalculate(self.worksheet,targets={index})
        self.dirty = True
        return self._record("Assign Formula — " + col.name, {"column": "C" + str(index + 1), "name": col.name, "expression": expression.strip(), "rows": len(col.values)})

    def find_cell(self, query, start_row=0, start_col=0, match_case=False, whole_word=False, direction="down"):
        if not isinstance(query, str) or not query:
            raise ValueError("Enter text or a value to find.")
        needle = query if match_case else query.casefold()
        cols = len(self.worksheet.columns)
        rows = max(1, self.worksheet.row_count)
        if cols == 0:
            return None
        total = rows * cols
        step = -1 if direction == "up" else 1
        start = max(0, min(total - 1, start_row * cols + start_col))
        for offset in range(1, total + 1):
            pos = (start + offset * step) % total
            r, c = divmod(pos, cols)
            col = self.worksheet.columns[c]
            val = col.values[r] if r < len(col.values) else None
            text = "" if val is None else display_date(val) if col.kind == "date" else _display(val) if col.kind == "number" else str(val)
            candidate = text if match_case else text.casefold()
            if whole_word and candidate == needle or not whole_word and needle in candidate:
                return (r, c)
        return None

    def worksheet_information(self):
        rows = []
        for i, col in enumerate(self.worksheet.columns):
            nonmissing = sum(1 for v in col.values if v is not None and not (col.kind == "text" and v == ""))
            missing = max(0, len(col.values) - nonmissing)
            rows.append({
                "column": "C" + str(i + 1) + ("-T" if col.kind == "text" else "-D" if col.kind == "date" else ""),
                "name": col.name,
                "count": nonmissing,
                "missing": missing,
                "type": col.kind.upper()[0],
                "formula": col.metadata.get("formula", ""),
            })
        desc = self.worksheet.metadata.get("description", {})
        return self._record("Worksheet Information — " + self.worksheet.name, {
            "worksheet": self.worksheet.name,
            "columns_count": len(self.worksheet.columns),
            "rows_count": self.worksheet.row_count,
            "constants_count": len(self.worksheet.constants),
            "matrices_count": len(self.worksheet.matrices),
            "creator": desc.get("creator", ""),
            "comments": desc.get("comments", ""),
            "variables_table": rows,
        })

    @undoable
    def set_worksheet_description(self, creator="", date_text="", comments=""):
        self.worksheet.metadata["description"] = {
            "creator": str(creator).strip(),
            "date": str(date_text).strip(),
            "comments": str(comments).strip(),
        }
        self.dirty = True

    @undoable
    def delete_columns(self, indices):
        col_set = sorted({int(i) for i in indices})
        if not col_set or any(i < 0 or i >= len(self.worksheet.columns) for i in col_set):
            raise ValueError("Select existing columns to delete.")
        if self.native_project is not None and not getattr(self.native_project, "statcraft_owned", False):
            from .mpx_columns import preflight
            preflight(self.native_project,self.worksheet)
            for idx in reversed(col_set):
                del self.worksheet.columns[idx]
            self.dirty=True
            return
        if len(col_set) >= len(self.worksheet.columns):
            self.worksheet.columns = [Column("C" + str(i), metadata={"auto_type": True}) for i in range(1, 17)]
        else:
            for idx in reversed(col_set):
                del self.worksheet.columns[idx]
            while len(self.worksheet.columns) < 16:
                self.worksheet.columns.append(Column("C" + str(len(self.worksheet.columns) + 1), metadata={"auto_type": True}))
            for i, col in enumerate(self.worksheet.columns):
                if col.name.startswith("C") and col.name[1:].isdigit():
                    col.name = "C" + str(i + 1)
        self.dirty = True

    @undoable
    def clear_columns_data(self, indices):
        col_set = sorted({int(i) for i in indices})
        if not col_set or any(i < 0 or i >= len(self.worksheet.columns) for i in col_set):
            raise ValueError("Select existing columns to clear.")
        for idx in col_set:
            col = self.worksheet.columns[idx]
            col.values = [None] * len(col.values)
        self.dirty = True

    @undoable
    def autofill_column(self, col_index, start_row, sample_len, count):
        from .autofill_engine import autofill_sequence
        if not 0 <= col_index < len(self.worksheet.columns):
            raise ValueError("Select a valid column.")
        col = self.worksheet.columns[col_index]
        sample = col.values[start_row : start_row + sample_len]
        new_values = autofill_sequence(sample, count)
        target_start = start_row + sample_len
        target_end = target_start + count
        while len(col.values) < target_end:
            col.values.append(None)
        for i, val in enumerate(new_values):
            col.values[target_start + i] = val
        self.dirty = True

    @undoable
    def replace_cells(self, query, replacement, match_case=False, whole_word=False, replace_all=True, start_row=0, start_col=0):
        if not isinstance(query, str) or not query:
            raise ValueError("Enter text or a value to find.")
        needle = query if match_case else query.casefold()
        count = 0
        cols = len(self.worksheet.columns)
        rows = max(1, self.worksheet.row_count)
        if cols == 0:
            return 0
        total = rows * cols
        start = max(0, min(total - 1, start_row * cols + start_col))
        for offset in range(total):
            pos = (start + offset) % total
            r, c = divmod(pos, cols)
            col = self.worksheet.columns[c]
            val = col.values[r] if r < len(col.values) else None
            if val is None:
                continue
            text = display_date(val) if col.kind == "date" else _display(val) if col.kind == "number" else str(val)
            candidate = text if match_case else text.casefold()
            matched = (candidate == needle) if whole_word else (needle in candidate)
            if not matched:
                continue
            if whole_word or col.kind != "text":
                new_raw = str(replacement)
            else:
                if match_case:
                    new_raw = text.replace(query, str(replacement))
                else:
                    idx = candidate.find(needle)
                    new_raw = text[:idx] + str(replacement) + text[idx + len(query):]
            self.set_cell(r, c, new_raw)
            count += 1
            if not replace_all:
                break
        return count

    @undoable
    def set_cell_comment(self, row, col_index, comment):
        if not 0 <= col_index < len(self.worksheet.columns) or row < 0:
            raise ValueError("Select a valid cell.")
        col = self.worksheet.columns[col_index]
        comments = dict(col.metadata.get("cell_comments", {}))
        text = str(comment).strip()
        if text:
            comments[str(row)] = text
        else:
            comments.pop(str(row), None)
        if comments:
            col.metadata["cell_comments"] = comments
        else:
            col.metadata.pop("cell_comments", None)
        self.dirty = True

    @undoable
    def set_cell_highlight(self, rows, cols, color):
        for c in cols:
            if not 0 <= c < len(self.worksheet.columns):
                continue
            col = self.worksheet.columns[c]
            highlights = dict(col.metadata.get("cell_highlights", {}))
            for r in rows:
                if r < 0:
                    continue
                if color:
                    highlights[str(r)] = str(color)
                else:
                    highlights.pop(str(r), None)
            if highlights:
                col.metadata["cell_highlights"] = highlights
            else:
                col.metadata.pop("cell_highlights", None)
        self.dirty = True

    @undoable
    def clear_cell_formats(self, rows=None, cols=None):
        target_cols = range(len(self.worksheet.columns)) if cols is None else cols
        for c in target_cols:
            if not 0 <= c < len(self.worksheet.columns):
                continue
            col = self.worksheet.columns[c]
            if rows is None:
                col.metadata.pop("cell_highlights", None)
                col.metadata.pop("cell_comments", None)
            else:
                highlights = dict(col.metadata.get("cell_highlights", {}))
                comments = dict(col.metadata.get("cell_comments", {}))
                for r in rows:
                    highlights.pop(str(r), None)
                    comments.pop(str(r), None)
                if highlights:
                    col.metadata["cell_highlights"] = highlights
                else:
                    col.metadata.pop("cell_highlights", None)
                if comments:
                    col.metadata["cell_comments"] = comments
                else:
                    col.metadata.pop("cell_comments", None)
        self.dirty = True

    @undoable
    def set_column_format(self, index, mode="automatic", decimals=2):
        if not 0 <= index < len(self.worksheet.columns):
            raise ValueError("Select an existing column.")
        col = self.worksheet.columns[index]
        if mode == "automatic":
            col.metadata.pop("format", None)
        else:
            col.metadata["format"] = {"mode": str(mode), "decimals": max(0, min(12, int(decimals)))}
        self.dirty = True

    @undoable
    def set_column_description(self, index, description):
        if not 0 <= index < len(self.worksheet.columns):
            raise ValueError("Select an existing column.")
        col = self.worksheet.columns[index]
        text = str(description).strip()
        if text:
            col.metadata["description"] = text
        else:
            col.metadata.pop("description", None)
        self.dirty = True

    @undoable
    def set_column_value_order(self, index, order_mode="alphabetical", custom_values=()):
        if not 0 <= index < len(self.worksheet.columns):
            raise ValueError("Select an existing column.")
        col = self.worksheet.columns[index]
        if col.kind!='text':raise ValueError('Value Order is available for text columns only.')
        from .value_order import validate_order
        col.metadata['value_order']=validate_order(order_mode,custom_values)
        self.dirty = True

    @undoable
    def apply_conditional_formatting(self, index, rule_type, param1=None, param2=None, color="#f8d7da"):
        if not 0 <= index < len(self.worksheet.columns):
            raise ValueError("Select an existing column.")
        col = self.worksheet.columns[index]
        rules = list(col.metadata.get("conditional_rules", []))
        rules.append({"type": str(rule_type), "param1": param1, "param2": param2, "color": str(color)})
        from .conditional_formatting import validate_rules
        col.metadata["conditional_rules"] = validate_rules(rules)
        col.metadata["conditional_format_version"] = 2
        self.dirty = True

    @undoable
    def clear_conditional_formatting(self, indices=None):
        targets = range(len(self.worksheet.columns)) if indices is None else indices
        for c in targets:
            if 0 <= c < len(self.worksheet.columns):
                col = self.worksheet.columns[c]
                col.metadata.pop("conditional_rules", None)
                col.metadata.pop("conditional_format_version", None)
        self.dirty = True

    @undoable
    def remove_formulas(self, indices):
        for c in indices:
            if 0 <= c < len(self.worksheet.columns):
                self.worksheet.columns[c].metadata.pop("formula", None)
        self.dirty = True

    @undoable
    def calculate_all_formulas(self):
        from .formulas import recalculate
        sheets=self.native_project.worksheets if self.native_project else [self.worksheet]
        return sum(recalculate(sheet) for sheet in sheets)

    def set_automatic_formulas(self,enabled):
        if type(enabled) is not bool:raise ValueError('Automatic calculation must be on or off.')
        if enabled and not self.auto_calculate_formulas:self.calculate_all_formulas()
        self.auto_calculate_formulas=enabled

    def subset_worksheet(self, name=None, mode="include", row_indices=()):
        source = self.worksheet
        total_rows = source.row_count
        row_set = {int(r) for r in row_indices if 0 <= int(r) < total_rows}
        if mode == "exclude":
            keep_rows = [r for r in range(total_rows) if r not in row_set]
        else:
            keep_rows = sorted(row_set)
        new_sheet = self.add_worksheet(name)
        new_cols = []
        for col in source.columns:
            vals = [col.values[r] if r < len(col.values) else None for r in keep_rows]
            while vals and vals[-1] is None:
                vals.pop()
            new_cols.append(Column(col.name, col.kind, vals, copy.deepcopy(col.metadata)))
        new_sheet.columns = new_cols
        try:
            from .connect import ensure_worksheet_identities
            ensure_worksheet_identities(source)
            src_row_ids = source.metadata.get("row_ids", [])
            new_sheet.metadata["source_worksheet"] = getattr(source, "name", "Data")
            new_sheet.metadata["source_rows"] = [r + 1 for r in keep_rows]
            new_sheet.metadata["source_row_ids"] = [src_row_ids[r] for r in keep_rows if r < len(src_row_ids)]
            ensure_worksheet_identities(new_sheet)
        except Exception:
            pass
        self.dirty = True
        return new_sheet

    @undoable
    def create_indicator_from_brushed(self, row_numbers, col_name="Brushed_Indicator"):
        """Create a binary 0/1 indicator column marking brushed 1-based row numbers."""
        total = self.worksheet.row_count
        if total == 0:
            raise ValueError("Worksheet is empty.")
        brushed_set = {int(r) for r in (row_numbers or ()) if 1 <= int(r) <= total}
        vals = [1.0 if (idx + 1) in brushed_set else 0.0 for idx in range(total)]
        base = (col_name or "Brushed_Indicator").strip() or "Brushed_Indicator"
        existing = {c.name.casefold() for c in self.worksheet.columns}
        final_name = base
        suffix = 2
        while final_name.casefold() in existing:
            final_name = f"{base}_{suffix}"
            suffix += 1
        col = Column(final_name, "number", vals)
        self.worksheet.columns.append(col)
        self.dirty = True
        return col

    def delete_result(self, entry):
        if entry in self.history:
            self.history.remove(entry)
            self._results_dirty = True
            return True
        return False

    def rename_result(self, entry, new_title):
        clean = str(new_title).strip()
        if not clean:
            raise ValueError("Enter a non-empty title.")
        entry["title"] = clean
        if isinstance(entry.get("result"), dict) and "plot_title" in entry["result"]:
            entry["result"]["plot_title"] = clean
        self._results_dirty = True
        return entry

    def update_result_metadata(self, entry, title=None, xlabel=None, ylabel=None):
        if title is not None and str(title).strip():
            entry["title"] = str(title).strip()
            if isinstance(entry.get("result"), dict):
                entry["result"]["plot_title"] = str(title).strip()
        if isinstance(entry.get("result"), dict):
            if xlabel is not None:
                entry["result"]["xlabel"] = str(xlabel)
            if ylabel is not None:
                entry["result"]["ylabel"] = str(ylabel)
        self._results_dirty = True
        return entry

    def refit_native_model(self,entry):
        if not any(item is entry for item in self.history):raise ValueError('Select a saved native model in the current project.')
        from .native_mpx_models import resolve_model_recipe,compare_native_model
        descriptor=entry.get('native_model',{})
        recipe=resolve_model_recipe(self.native_project,descriptor)
        source=self.native_project.worksheet_ids.index(descriptor['worksheet_id'])
        previous=self.native_project.active_index
        self.select_worksheet(source)
        try:
            # Only the reconstructed typed recipe executes. Native history and
            # macro text are never interpreted.
            fresh=self.analyze_response_surface(**recipe['parameters'])
        except Exception:
            self.select_worksheet(previous)
            raise
        comparison=compare_native_model(fresh['result'],descriptor)
        fresh['native_model_source']={'command_id':descriptor['command_id'],'model_uri':descriptor['model_uri'],
            'model_id':descriptor['model_id'],'comparison':comparison}
        if not comparison['matches_saved_native']:
            fresh['result'].setdefault('warnings',[]).append('This fresh StatCraft fit differs from the stored native model. The worksheet or fit state may have changed; original native outputs were retained.')
        return fresh

    def update_native_graph_view(self,entry,index,changes):
        from .native_graph_view import validate_view,validate_views
        if entry.get('result',{}).get('analysis')!='native_saved_output':raise ValueError('Select an imported saved graph.')
        graphs=entry['result'].get('graphs',[])
        if type(index) is not int or not 0<=index<len(graphs):raise ValueError('Select an available saved graph.')
        normalized=validate_view(changes);views=copy.deepcopy(entry.get('native_graph_views',{}))
        view=views.setdefault(str(index),{});view.update(normalized)
        return self._set_graph_option(entry,'native_graph_views',validate_views(views,len(graphs)))

    def update_graph_presentation(self,entry,settings):
        from .graph_presentation import validate_presentation
        normalized=validate_presentation(settings)
        if entry.get('result',{}).get('analysis')=='native_saved_output':
            return self.update_native_graph_view(entry,entry.get('_native_graph_index',0),{'presentation':normalized})
        return self._set_graph_option(entry,'graph_presentation',normalized)

    def _set_graph_option(self,entry,field,normalized):
        native_overlay=field=='native_graph_views' and entry.get('result',{}).get('analysis')=='native_saved_output'
        if (entry.get('origin')!='statcraft' and not native_overlay) or not any(item is entry for item in self.history):
            raise ValueError('Select a saved StatCraft graph to edit.')
        if entry.get(field)!=normalized:
            before=copy.deepcopy(entry.get(field));before_revision=self._revision
            entry[field]=copy.deepcopy(normalized);self._results_dirty=True
            self._next_revision+=1;self._revision=self._next_revision
            self._undo_stack.append({'entry':entry,'field':field,'before':before,'after':copy.deepcopy(normalized),
                'before_revision':before_revision,'after_revision':self._revision,'action':'edit_graph'})
            self._undo_stack=self._undo_stack[-20:];self._redo_stack.clear()
        return entry

    def update_graph_styles(self,entry,styles):
        from .graph_styles import validate_styles
        normalized=validate_styles(styles)
        if entry.get('result',{}).get('analysis')=='native_saved_output':
            return self.update_native_graph_view(entry,entry.get('_native_graph_index',0),{'styles':normalized})
        return self._set_graph_option(entry,'graph_styles',normalized)

    def update_histogram_settings(self,entry,settings):
        from .histogram_options import validate_histogram_settings,build_histogram_panel
        normalized=validate_histogram_settings(settings)
        if entry.get('result',{}).get('graph')!='histogram':raise ValueError('Select a histogram.')
        build_histogram_panel(entry['result'].get('histogram_source'),normalized)
        return self._set_graph_option(entry,'histogram_settings',normalized)

    def execute_session_command(self, line):
        """Execute a session command or subcommand block."""
        from .session_commands import execute_script
        results = execute_script(self, line)
        return results[-1] if results else None

    def execute_session_script(self, script_text):
        """Execute a multi-line Minitab Exec / session command script (.MTB)."""
        from .session_commands import execute_script
        return execute_script(self, script_text)


def format_entry(entry):
    title = entry["title"] + "\n" + entry["time"] + "\n" + "─" * 76 + "\n\n"
    result = entry["result"]
    if isinstance(result, dict) and (result.get('analysis') == 'bootstrap_uncertainty' or 'bootstrap_report' in result):
        return title + result.get('text', '')
    if isinstance(result, dict) and (result.get('analysis') == 'ecdf_plot' or result.get('graph') == 'ecdf_plot'):
        from .ecdf_report import format_ecdf_report
        return title + format_ecdf_report(result)
    if isinstance(result, dict) and (result.get('analysis') == 'marginal_plot' or result.get('graph') == 'marginal_plot'):
        from .marginal_plot_report import format_marginal_plot_report
        return title + format_marginal_plot_report(result)
    if isinstance(result, dict) and (result.get('analysis') == 'probability_distribution' or result.get('graph') == 'probability_distribution'):
        from .prob_dist_report import format_probability_distribution_report
        return title + format_probability_distribution_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'covariance':
        from .covariance_report import format_covariance_report
        return title + format_covariance_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'stem_leaf':
        from .stem_leaf_report import format_stem_leaf_report
        return title + format_stem_leaf_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'multivari':
        from .multivari_report import format_multivari_report
        return title + format_multivari_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'outlier_test':
        from .outlier_test_report import format_outlier_report
        return title + format_outlier_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'graphical_summary':
        from .graphical_summary_report import format_graphical_summary_report
        return title + format_graphical_summary_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'cause_and_effect':
        from .cause_and_effect_report import format_cause_and_effect_report
        return title + format_cause_and_effect_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'anom':
        from .anom_report import format_anom_report
        return title + format_anom_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'fitted_line_plot':
        from .fitted_line_plot_report import format_fitted_line_plot_report
        return title + format_fitted_line_plot_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'run_chart':
        from .run_chart_report import format_run_chart_report
        return title + format_run_chart_report(result)
    if isinstance(result,dict) and result.get('analysis') == 'native_saved_output':
        return title + result.get('text', '') + ('\n\n' + '\n'.join(result['warnings']) if result.get('warnings') else '')
    if isinstance(result,dict) and result.get('analysis') == 'mixture_joint_optimization':
        from .mixture_joint_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis') in ('mixture_process_model','mixture_process_prediction'):
        from .mixture_process_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis') in ('mixture_multi_optimization','mixture_multi_evaluation'):
        from .mixture_multi_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis') in ('mixture_contour','mixture_optimization'):
        from .mixture_exploration_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis')=='mixture_prediction':
        lines=['Mixture prediction: '+result['response_name'],str(result['confidence']*100)+'% confidence / prediction intervals','Components | Fit | SE Fit | Lower CI | Upper CI | Lower PI | Upper PI']
        for row in result['rows']:lines.append(' | '.join(_display(row[key]) for key in ('components','fit','standard_error','ci_low','ci_high','prediction_low','prediction_high')))
        return title+'\n'.join(lines)+'\n'+'\n'.join(result['warnings'])
    if isinstance(result,dict) and result.get('analysis')=='mixture_model':
        from .mixture_report import format_mixture_report
        return title+format_mixture_report(result)
    if isinstance(result,dict) and result.get('analysis')=='dynamic_taguchi_analysis':
        from .dynamic_taguchi_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis')=='taguchi_analysis':
        from .taguchi_analysis_report import text_report as format_taguchi_report
        return title+format_taguchi_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'doe_plan':
        from .doe_planner import format_plan
        return title + format_plan(result)
    if isinstance(result, dict) and result.get('analysis') == 'multiple_capability':
        from .multiple_capability_report import format_multiple_capability_report
        return title + format_multiple_capability_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'attribute_capability':
        from .attribute_capability_report import generate_attribute_capability_report
        return title + generate_attribute_capability_report(result)
    if isinstance(result, dict):
        _p3_formatters = {
            'bootstrap_1sample': ('.resampling', 'format_resampling_report'),
            'bootstrap_2sample': ('.resampling', 'format_resampling_report'),
            'randomization_1sample': ('.resampling', 'format_resampling_report'),
            'randomization_2sample': ('.resampling', 'format_resampling_report'),
            'poisson_gof': ('.count_models', 'format_count_report'),
            'negative_binomial_regression': ('.count_models', 'format_count_report'),
            'one_variance_power': ('.power_extended', 'format_power_extended_report'),
            'two_variances_power': ('.power_extended', 'format_power_extended_report'),
            'one_poisson_rate_power': ('.power_extended', 'format_power_extended_report'),
            'two_poisson_rates_power': ('.power_extended', 'format_power_extended_report'),
            'equivalence_tost_power': ('.power_extended', 'format_power_extended_report'),
            'sample_size_estimation': ('.power_extended', 'format_power_extended_report'),
            'sample_size_tolerance_interval': ('.power_extended', 'format_power_extended_report'),
            'balanced_anova': ('.advanced_anova', 'format_advanced_anova_report'),
            'fully_nested_anova': ('.advanced_anova', 'format_advanced_anova_report'),
            'oneway_manova': ('.advanced_anova', 'format_advanced_anova_report'),
            'mixed_reml': ('.mixed_reml', 'format_mixed_reml_report'),
            'cox_ph_regression': ('.survival_advanced', 'format_survival_advanced_report'),
            'warranty_analysis': ('.survival_advanced', 'format_survival_advanced_report'),
            'six_sigma_process_report': ('.six_sigma', 'format_six_sigma_report'),
            'six_sigma_product_report': ('.six_sigma', 'format_six_sigma_report'),
            'random_forest': ('.predictive_ml', 'format_predictive_ml_report'),
            'treenet_gbm': ('.predictive_ml', 'format_predictive_ml_report'),
            'mars_regression': ('.predictive_ml', 'format_predictive_ml_report'),
            'discover_best_model': ('.predictive_ml', 'format_predictive_ml_report'),
            'monte_carlo_simulation': ('.monte_carlo', 'format_monte_carlo_report'),
        }
        _p3_key = result.get('analysis')
        if _p3_key in _p3_formatters:
            import importlib
            _mod_name, _fn_name = _p3_formatters[_p3_key]
            _mod = importlib.import_module(_mod_name, package=__package__)
            return title + getattr(_mod, _fn_name)(result)
    if isinstance(result,dict) and result.get('graph')=='categorical_points':
        lines=['Variable             Group               N       Mean          Median        StDev         SE Mean       Lower         Upper']
        for panel in result['panels']:
            for item in panel['items']:lines.append(item['response_name'].ljust(21)+(item['group_label'] or '(all)').ljust(20)+str(item['n']).ljust(8)+''.join(_display(item[key]).ljust(14) for key in ('mean','median','stdev','standard_error','lower','upper')))
        return title+'\n'.join(lines)+'\n\n'+result['convention']
    if isinstance(result,dict) and result.get('graph')=='dotplot_graphs':
        lines=['Series                                      Category                       N']
        for panel in result['panels']:
            for series in panel['series']:lines.append(series['label'].ljust(44)+panel['lanes'][series['lane']].ljust(31)+str(len(series['source'])))
        return title+'\n'.join(lines)+'\n\n'+result['convention']
    if isinstance(result,dict) and result.get('graph')=='boxplot_graphs':
        lines=['Variable             Group               N       Q1            Median        Q3            Mean']
        for panel in result['panels']:
            for item in panel['items']:
                lines.append(item['response_name'].ljust(21)+(item['group_label'] or '(all)').ljust(20)+str(item['n']).ljust(8)+''.join(_display(item['box'][key]).ljust(14) for key in ('q1','median','q3'))+_display(item['mean']))
        return title+'\n'.join(lines)+'\n\n'+result['convention']
    if isinstance(result,dict) and result.get('graph')=='histogram_graphs':
        lines=['Variable                 Group               N       Fit Mean      Fit StDev']
        for panel in result['panels']:
            for series in panel['series']:
                fit=series.get('fit_parameters') or {}
                lines.append(panel['xlabel'].ljust(25)+(series['label'] if panel['group_name'] else '(all)').ljust(20)+str(series['n']).ljust(8)+_display(fit.get('mean')).ljust(14)+_display(fit.get('stdev')))
        return title+'\n'.join(lines)+'\n\nGroups share equal-width bins within each response. Percent and Density normalize within each group. Normal fits use sample standard deviation.'
    if isinstance(result, dict) and (result.get("two_variances") is True or ("ratio_sd" in result and "sample1" in result and "sample2" in result)):
        from .two_variances_report import format_two_variances_report
        return title + format_two_variances_report(result)
    if isinstance(result, dict) and (result.get("one_variance_native") is True or ("samples" in result and "chi2" in (result.get("samples") or [{}])[0])):
        from .one_variance_report import format_one_variance_report
        reps = [format_one_variance_report(s) for s in result.get("samples", [])]
        return title + "\n\n".join(reps)
    if isinstance(result, dict) and (result.get("two_sample_poisson") is True or ("difference" in result and "sample1" in result and "sample2" in result and "sample_rate" in (result.get("sample1") or {}))):
        from .two_sample_poisson_report import format_two_sample_poisson_report
        return format_two_sample_poisson_report(entry)
    if isinstance(result, dict) and (result.get("one_sample_poisson") is True or ("samples" in result and "length_of_observation" in result)):
        from .one_sample_poisson_report import format_one_sample_poisson_report
        return format_one_sample_poisson_report(entry)
    if isinstance(result, dict) and (result.get("one_sample_proportion") is True or ("samples" in result and "hypothesized_proportion" in result)):
        from .one_sample_proportion_report import format_one_sample_proportion_report
        return format_one_sample_proportion_report(entry)
    if isinstance(result, dict) and (result.get("one_sample_z") is True or ("samples" in result and "sigma" in result)):
        from .one_sample_z_report import format_one_sample_z_report
        return format_one_sample_z_report(entry)
    if isinstance(result, dict) and not result.get("one_sample_z") and "sigma" not in result and (result.get("one_sample_t") is True or ("samples" in result and "perform_test" in result and "hypothesized_mean" in result)):
        from .one_sample_t_report import format_one_sample_t_report
        return format_one_sample_t_report(entry)
    if isinstance(result, dict) and (result.get("two_sample_proportion") is True or ("difference" in result and "sample1" in result and "sample2" in result and "events" in (result.get("sample1") or {}))):
        from .two_sample_proportion_report import format_two_sample_proportion_report
        return format_two_sample_proportion_report(entry)
    if isinstance(result, dict) and (result.get("paired_t") is True or ("differences" in result and "sample1_name" in result)):
        from .paired_t_report import format_paired_t_report
        return format_paired_t_report(entry)
    if isinstance(result, dict) and not result.get("paired_t") and (result.get("two_sample_t") is True or ("t_statistic" in result and "sample1" in result and "sample2" in result)):
        from .two_sample_t_report import format_two_sample_t_report
        return format_two_sample_t_report(entry)
    if isinstance(result, dict) and (result.get("test_equal_variances") is True or "individual_confidence_level" in (result.get("result") or {})):
        from .equal_variances_report import format_equal_variances_report
        return title + format_equal_variances_report(entry)
    if isinstance(result, dict) and result.get("variance_test") is True:
        lines = ["H0: all population variances are equal.", "Method: " + result["method"],
            "", "Test statistic: " + _display(result["test_statistic"]), "Degrees of freedom: " + str(result["df"]),
            "P-value: " + _display(result["p_value"]), "", "Group               N       StDev         Median"]
        for index, group in enumerate(result["group_statistics"]):
            name = result["variables"][index]
            lines.append(name.ljust(20) + _display(group["count"]).ljust(8) + _display(group["sample_stdev"]).ljust(14) + _display(group["median"]))
        lines += ["", "Missing observations: " + str(result["missing"])]
        return title + "\n".join(lines) + _report_notes(result)
    if isinstance(result, dict) and result.get("chart") == "Xbar-R":
        lines = ["Measurements: " + result.get("variable", ""),
            "Complete subgroups: " + str(result["count"]) + "    Size: " + str(result["subgroup_size"]),
            "Within sigma (Rbar / d2): " + _display(result["within_stdev"]),
            "", "Chart           Center        LCL           UCL"]
        for prefix, label in (("xbar","Xbar"),("r","Range")):
            lines.append(label.ljust(16) + "".join(_display(result[prefix + suffix]).ljust(14) for suffix in ("_center","_lcl","_ucl")))
        lines += ["", "Test 1 signal subgroups:",
            "Xbar: " + (", ".join(map(str,result["xbar_signals"])) or "None"),
            "Range: " + (", ".join(map(str,result["r_signals"])) or "None")]
        lines += ["", "Subgroup             Mean          Range"]
        labels = result.get("subgroup_labels", [])
        for row, (mean, spread) in enumerate(zip(result["means"],result["ranges"])):
            if row >= 100:
                lines.append("… additional subgroups are retained in the saved result.")
                break
            label = labels[row] if row < len(labels) else str(row+1)
            lines.append(str(label).ljust(21) + _display(mean).ljust(14) + _display(spread))
        return title + "\n".join(lines) + _report_notes(result)
    if isinstance(result, dict) and result.get("graph") in ("histogram", "scatter", "boxplot"):
        text=title + "Graph: " + result["graph"].title() + "\nVariables: " + ", ".join(result.get("variables", [])) + "\n\n" + result.get("convention", "")
        for fit in result.get('fits',[]):
            text+='\n\n'+str(fit['group'])+': Y = '+_display(fit['intercept'])+' + '+_display(fit['slope'])+' X; N = '+str(fit['count'])
        return text
    if isinstance(result,dict) and result.get('analysis')=='response_surface_design':
        from .response_surface_report import design_text
        return title+design_text(result)
    if isinstance(result,dict) and result.get('analysis')=='response_surface':
        from .response_surface_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis')=='binary_logistic':
        from .logistic_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis')=='logistic_prediction':
        from .logistic_report import prediction_text_report
        return title+prediction_text_report(result)
    if isinstance(result,dict) and result.get('analysis') in ('factorial_plots','model_contour_plot','model_surface_plot'):
        from .model_plots_report import text_report
        return title+text_report(result)
    if isinstance(result, dict) and result.get("analysis") == "pca":
        from .multivariate_report import format_pca_report
        return title + format_pca_report(result)
    if isinstance(result, dict) and result.get("analysis") == "item_analysis":
        from .multivariate_report import format_item_analysis_report
        return title + format_item_analysis_report(result)
    if isinstance(result, dict) and result.get("analysis") == "cluster_observations":
        from .multivariate_report import format_cluster_observations_report
        return title + format_cluster_observations_report(result)
    if isinstance(result, dict) and result.get("analysis") == "cluster_kmeans":
        from .multivariate_report import format_cluster_kmeans_report
        return title + format_cluster_kmeans_report(result)
    if isinstance(result, dict) and result.get("analysis") == "cluster_variables":
        from .multivariate_report import format_cluster_variables_report
        return title + format_cluster_variables_report(result)
    if isinstance(result, dict) and result.get("analysis") == "discriminant_analysis":
        from .multivariate_report import format_discriminant_analysis_report
        return title + format_discriminant_analysis_report(result)
    if isinstance(result, dict) and result.get("analysis") == "simple_correspondence":
        from .multivariate_report import format_simple_correspondence_report
        return title + format_simple_correspondence_report(result)
    if isinstance(result, dict) and result.get("analysis") == "one_sample_equivalence":
        from .equivalence_report import format_one_sample_equivalence_report
        return title + format_one_sample_equivalence_report(result)
    if isinstance(result, dict) and result.get("analysis") == "two_sample_equivalence":
        from .equivalence_report import format_two_sample_equivalence_report
        return title + format_two_sample_equivalence_report(result)
    if isinstance(result, dict) and result.get("analysis") == "paired_equivalence":
        from .equivalence_report import format_paired_equivalence_report
        return title + format_paired_equivalence_report(result)
    if isinstance(result, dict) and result.get("analysis") == "crossover_equivalence":
        from .equivalence_report import format_crossover_equivalence_report
        return title + format_crossover_equivalence_report(result)
    if isinstance(result, dict) and result.get("analysis") == "one_sample_z_power":
        from .power_report import format_one_sample_z_power_report
        return title + format_one_sample_z_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "one_sample_t_power":
        from .power_report import format_one_sample_t_power_report
        return title + format_one_sample_t_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "two_sample_t_power":
        from .power_report import format_two_sample_t_power_report
        return title + format_two_sample_t_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "paired_t_power":
        from .power_report import format_paired_t_power_report
        return title + format_paired_t_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "one_proportion_power":
        from .power_report import format_one_proportion_power_report
        return title + format_one_proportion_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "two_proportions_power":
        from .power_report import format_two_proportions_power_report
        return title + format_two_proportions_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "oneway_anova_power":
        from .power_report import format_oneway_anova_power_report
        return title + format_oneway_anova_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "factorial_power":
        from .power_report import format_factorial_power_report
        return title + format_factorial_power_report(result)
    if isinstance(result, dict) and result.get("analysis") == "cross_tabulation":
        from .tables_report import format_cross_tabulation_report
        return title + format_cross_tabulation_report(result)
    if isinstance(result, dict) and result.get("analysis") == "chi_square_goodness_of_fit":
        from .tables_report import format_chi_square_goodness_of_fit_report
        return title + format_chi_square_goodness_of_fit_report(result)
    if isinstance(result, dict) and result.get("analysis") == "chi_square_association_table":
        from .tables_report import format_chi_square_association_table_report
        return title + format_chi_square_association_table_report(result)
    if isinstance(result, dict) and result.get("analysis") == "tally_variables":
        from .tables_report import format_tally_variables_report
        return title + format_tally_variables_report(result)
    if isinstance(result,dict) and result.get('analysis')=='response_optimizer':
        from .optimizer_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis')=='model_prediction':
        from .prediction_report import text_report
        return title+text_report(result)
    if isinstance(result,dict) and result.get('analysis')=='gage_rr':
        from .gage_rr_report import text_report
        return title+text_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'subgroup_control':
        from .subgroup_control_report import text_report
        return title + text_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'oneway_anova':
        from .oneway_report import text_report
        return title + text_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'twoway_anova':
        from .twoway_anova_report import format_twoway_anova_report
        return title + format_twoway_anova_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'main_effects_plot':
        from .anova_plots_report import format_main_effects_report
        return title + format_main_effects_report(result)
    if isinstance(result, dict) and result.get('analysis') == 'interactions_plot':
        from .anova_plots_report import format_interactions_report
        return title + format_interactions_report(result)
    if isinstance(result,dict) and result.get('analysis')=='general_linear_model':
        from .glm_report import text_report
        return title+text_report(result)
    if isinstance(result, dict) and "coefficients" in result and "adjusted_r_squared" in result:
        resp_name = result.get("response_name", "Y")
        lines = []
        if result.get("regression_equation"):
            lines += ["Regression Equation", result["regression_equation"], ""]
        else:
            lines += ["Response: " + resp_name, ""]
        lines += [
            "Model Summary",
            "N       N*      S             R-sq          R-sq(adj)     R-sq(pred)",
            _display(result.get("count")).ljust(8) + _display(result.get("missing")).ljust(8) +
            _display(result.get("residual_stdev")).ljust(14) + (_display(100 * result["r_squared"]) + "%").ljust(14) +
            (_display(100 * result["adjusted_r_squared"]) + "%").ljust(14) +
            (_display(100 * result.get("predicted_r_squared", 0.0)) + "%"), "",
            "Coefficients  (" + _display(result.get("confidence", .95) * 100) + "% confidence intervals)",
            "Term                 Coef          SE Coef       T             P             Lower CI      Upper CI      VIF"]
        for row in result["coefficients"]:
            fields = [row.get(k) for k in ("estimate", "standard_error", "t", "p_value", "ci_low", "ci_high", "vif")]
            lines.append(row["name"].ljust(21) + "".join(_display(v).ljust(14) for v in fields))
        lines += ["", "Analysis of Variance", "Source           DF        Adj SS        Adj MS        F             P",
            "Regression       " + _display(result["df_regression"]).ljust(10) + _display(result["ss_regression"]).ljust(14) +
            _display(result["ms_regression"]).ljust(14) + _display(result.get("f")).ljust(14) + _display(result.get("p_value")),
            "Error            " + _display(result["df_error"]).ljust(10) + _display(result["ss_error"]).ljust(14) + _display(result["ms_error"]),
            "Total            " + _display(result["df_total"]).ljust(10) + _display(result["ss_total"])]
        if result.get("unusual_observations"):
            lines += ["", "Fits and Diagnostics for Unusual Observations",
                      "Obs      " + resp_name.ljust(14) + "Fit           Resid         Std Resid     Leverage      Symbol"]
            for obs in result["unusual_observations"]:
                lines.append(
                    _display(obs["obs"]).ljust(9) +
                    _display(obs["response"]).ljust(14) +
                    _display(obs["fit"]).ljust(14) +
                    _display(obs["resid"]).ljust(14) +
                    _display(obs["std_resid"]).ljust(14) +
                    _display(obs.get("leverage")).ljust(14) +
                    obs["symbol"]
                )
            lines += ["", "R: Large residual (|Std Resid| > 2)", "X: High leverage (Leverage > 3*p/n)"]
        if result.get('effects'):
            lines += ['', 'Estimated Effects', 'Term                 Effect        SE Effect     T             P']
            for row in result['effects']:
                lines.append(row['term'].ljust(21)+''.join(_display(row.get(key)).ljust(14) for key in ('effect','standard_error','t','p_value')))
            if result.get('show_factor_coding',True):
                lines += ['', 'Factor Coding', 'Factor               Low           Center        High']
                for row in result['factor_coding']:
                    name=(row.get('letter','')+' '+row['name']).strip()
                    lines.append(name.ljust(21)+''.join(_display(row[key]).ljust(14) for key in ('low','center','high')))
        if result.get('alias_structure'):
            lines += ['', 'Alias Structure (nominal corner fraction; letters follow factor coding)']
            lines.extend(row['aliases'] for row in result['alias_structure'])
        return title + "\n".join(lines) + _report_notes(result)
    if isinstance(result, dict) and result.get("analysis") == "attribute_control":
        from .attribute_control_report import format_attribute_control_report
        return title + format_attribute_control_report(result)
    if isinstance(result, dict) and result.get("analysis") == "time_weighted_control":
        from .time_weighted_control_report import generate_time_weighted_report
        return title + generate_time_weighted_report(result)
    if isinstance(result, dict) and result.get("analysis") == "rare_event_control":
        from .rare_event_control_report import generate_rare_event_report
        return title + generate_rare_event_report(result)
    if isinstance(result, dict) and result.get("analysis") == "multivariate_control":
        from .multivariate_control_report import generate_multivariate_report
        return title + generate_multivariate_report(result)
    if isinstance(result, dict) and result.get("analysis") == "pareto_chart":
        from .pareto_report import generate_pareto_report
        return title + generate_pareto_report(result)
    if isinstance(result, dict) and (result.get("analysis") == "type1_gage" or result.get("graph") == "type1_gage"):
        from .type1_gage_report import generate_type1_gage_report
        meas_name = entry.get("recipe", {}).get("parameters", {}).get("measurement_name", "Measurement")
        return title + generate_type1_gage_report(result, meas_name)
    if isinstance(result, dict) and (result.get("analysis") == "attribute_gage" or result.get("graph") == "attribute_gage"):
        from .attribute_gage_report import generate_attribute_gage_report
        r_name = entry.get("recipe", {}).get("parameters", {}).get("ref_name", "Reference")
        a_name = entry.get("recipe", {}).get("parameters", {}).get("acc_name", "Acceptances")
        return title + generate_attribute_gage_report(result, r_name, a_name)
    if isinstance(result, dict) and (result.get("analysis") == "symmetry_plot" or result.get("graph") == "symmetry_plot"):
        from .symmetry_plot_report import generate_symmetry_plot_report
        c_name = result.get("column_name", "Variable")
        return title + generate_symmetry_plot_report(result, variable_name=c_name)
    if isinstance(result, dict) and (result.get("analysis") == "acceptance_sampling_attributes" or result.get("graph") == "acceptance_sampling_attributes"):
        from .acceptance_sampling_report import generate_acceptance_sampling_report
        return title + generate_acceptance_sampling_report(result)
    if isinstance(result, dict) and (result.get("analysis") == "acceptance_sampling_variables" or result.get("graph") == "acceptance_sampling_variables"):
        from .acceptance_sampling_variables_report import generate_acceptance_sampling_variables_report
        return title + generate_acceptance_sampling_variables_report(result)
    if isinstance(result, dict) and (result.get("analysis") == "tolerance_intervals" or result.get("graph") == "tolerance_intervals"):
        from .tolerance_intervals_report import generate_tolerance_intervals_report
        return title + generate_tolerance_intervals_report(result)
    if isinstance(result, dict) and result.get("analysis") == "trend_analysis":
        from .time_series_report import generate_trend_analysis_report
        return title + generate_trend_analysis_report(result)
    if isinstance(result, dict) and result.get("analysis") == "decomposition":
        from .time_series_report import generate_decomposition_report
        return title + generate_decomposition_report(result)
    if isinstance(result, dict) and result.get("analysis") == "moving_average":
        from .time_series_report import generate_moving_average_report
        return title + generate_moving_average_report(result)
    if isinstance(result, dict) and result.get("analysis") == "single_exp_smoothing":
        from .time_series_report import generate_single_exp_smoothing_report
        return title + generate_single_exp_smoothing_report(result)
    if isinstance(result, dict) and result.get("analysis") == "double_exp_smoothing":
        from .time_series_report import generate_double_exp_smoothing_report
        return title + generate_double_exp_smoothing_report(result)
    if isinstance(result, dict) and result.get("analysis") == "winters_method":
        from .winters_method_report import generate_winters_method_report
        return title + generate_winters_method_report(result)
    if isinstance(result, dict) and result.get("analysis") == "arima":
        from .arima_report import generate_arima_report
        return title + generate_arima_report(result)
    if isinstance(result, dict) and result.get("analysis") == "reliability_arbitrary":
        from .reliability_arbitrary_report import generate_reliability_arbitrary_report
        return title + generate_reliability_arbitrary_report(result)
    if isinstance(result, dict) and result.get("analysis") in ("nonparametric_growth_curve", "parametric_growth_curve"):
        from .repairable_systems_report import generate_repairable_systems_report
        return title + generate_repairable_systems_report(result)
    if isinstance(result, dict) and result.get("analysis") == "probit_analysis":
        from .probit_report import generate_probit_report
        return title + generate_probit_report(result)
    if isinstance(result, dict) and result.get("analysis") == "multiple_correspondence":
        from .multiple_correspondence_report import generate_multiple_correspondence_report
        return title + generate_multiple_correspondence_report(result)
    if isinstance(result, dict) and result.get("analysis") == "factor_analysis":
        from .factor_analysis_report import generate_factor_analysis_report
        return title + generate_factor_analysis_report(result)
    if isinstance(result, dict) and result.get("analysis") == "life_regression":
        from .life_regression_report import generate_life_regression_report
        return title + generate_life_regression_report(result)
    if isinstance(result, dict) and result.get("analysis") == "stability_study":
        from .stability_study_report import generate_stability_study_report
        return title + generate_stability_study_report(result)
    if isinstance(result, dict) and result.get("analysis") == "orthogonal_regression":
        from .orthogonal_regression_report import generate_orthogonal_regression_report
        return title + generate_orthogonal_regression_report(result)
    if isinstance(result, dict) and result.get("analysis") == "pls_regression":
        from .pls_report import generate_pls_report
        return title + generate_pls_report(result)
    if isinstance(result, dict) and result.get("analysis") == "nonlinear_regression":
        from .nonlinear_regression_report import generate_nonlinear_regression_report
        return title + generate_nonlinear_regression_report(result)
    if isinstance(result, dict) and result.get("analysis") == "nominal_logistic_regression":
        from .nominal_logistic_report import generate_nominal_logistic_report
        return title + generate_nominal_logistic_report(result)
    if isinstance(result, dict) and result.get("analysis") == "ordinal_logistic_regression":
        from .ordinal_logistic_report import generate_ordinal_logistic_report
        return title + generate_ordinal_logistic_report(result)
    if isinstance(result, dict) and result.get("analysis") == "gage_rr_expanded":
        from .gage_rr_expanded_report import generate_gage_rr_expanded_report
        return title + generate_gage_rr_expanded_report(result)
    if isinstance(result, dict) and result.get("analysis") == "poisson_regression":
        from .poisson_regression_report import generate_poisson_regression_report
        return title + generate_poisson_regression_report(result)
    if isinstance(result, dict) and result.get("analysis") == "stepwise_regression":
        from .stepwise_report import generate_stepwise_report
        return title + generate_stepwise_report(result)
    if isinstance(result, dict) and result.get("analysis") == "best_subsets_regression":
        from .best_subsets_report import generate_best_subsets_report
        return title + generate_best_subsets_report(result)
    if isinstance(result, dict) and result.get("analysis") == "recode":
        lines = [
            title,
            "=" * len(title),
            "",
            f"Target Data Type: {result.get('target_kind', 'number').capitalize()}",
            f"Storage Location: {result.get('storage', 'new_columns')}",
            f"Source Columns: {', '.join(result.get('source_columns', []))}",
            f"Result Columns: {', '.join(result.get('recoded_columns', []))}",
            "",
            f"Rules Applied ({len(result.get('rules', []))} rules):",
        ]
        for r in result.get("rules", []):
            if r.get("type") == "missing":
                lines.append(f"  Missing (*) -> {r.get('recoded')}")
            else:
                lines.append(f"  {r.get('current')} -> {r.get('recoded')}")
        lines.append("")
        return "\n" + "\n".join(lines)
    if isinstance(result, dict) and result.get("analysis") == "autocorrelation":
        from .time_series_report import generate_autocorrelation_report
        return title + generate_autocorrelation_report(result)
    if isinstance(result, dict) and result.get("analysis") == "cross_correlation":
        lines = ["Positive lag pairs the first series with later values of the second series.",
                 "The approximate two-standard-deviation threshold is 2 / sqrt(pairs).", "",
                 f"{'Lag':>6} {'CCF':>12} {'Pairs':>8}"]
        lines.extend(f"{row['lag']:>6} {row['correlation']:>12.6f} {row['pairs']:>8}" for row in result['lags'])
        return title + "\n".join(lines)
    if isinstance(result, dict) and result.get("analysis") == "partial_autocorrelation":
        from .time_series_report import generate_partial_autocorrelation_report
        return title + generate_partial_autocorrelation_report(result)
    if isinstance(result, dict) and result.get("analysis") == "sign_test":
        from .nonparametrics_report import format_sign_test_report
        return title + format_sign_test_report(result, result.get("variable_name", "C1"))
    if isinstance(result, dict) and result.get("analysis") == "one_sample_wilcoxon":
        from .nonparametrics_report import format_one_sample_wilcoxon_report
        return title + format_one_sample_wilcoxon_report(result, result.get("variable_name", "C1"))
    if isinstance(result, dict) and result.get("analysis") == "mann_whitney":
        from .nonparametrics_report import format_mann_whitney_report
        return title + format_mann_whitney_report(result, result.get("name1", "C1"), result.get("name2", "C2"))
    if isinstance(result, dict) and result.get("analysis") == "kruskal_wallis":
        from .nonparametrics_report import format_kruskal_wallis_report
        return title + format_kruskal_wallis_report(result, result.get("response_name", "Response"), result.get("factor_name", "Factor"))
    if isinstance(result, dict) and result.get("analysis") == "moods_median":
        from .nonparametrics_report import format_moods_median_report
        return title + format_moods_median_report(result, result.get("response_name", "Response"), result.get("factor_name", "Factor"))
    if isinstance(result, dict) and result.get("analysis") == "friedman_test":
        from .nonparametrics_report import format_friedman_report
        return title + format_friedman_report(result, result.get("response_name", "Response"), result.get("treatment_name", "Treatment"), result.get("block_name", "Block"))
    if isinstance(result, dict) and result.get("analysis") == "runs_test":
        from .nonparametrics_report import format_runs_test_report
        return title + format_runs_test_report(result, result.get("variable_name", "C1"))
    if isinstance(result, dict) and result.get("analysis") == "paired_wilcoxon":
        from .nonparametrics_report import format_paired_wilcoxon_report
        return title + format_paired_wilcoxon_report(result, result.get("name1", "C1"), result.get("name2", "C2"))
    if isinstance(result, dict) and result.get("chart") in ("P", "U"):
        lines = ["Count: " + result.get("count_variable", ""),
                 "Sample size: " + result.get("size_variable", ""),
                 "Center = " + _display(result["center"]) + "    N = " + str(result["count"]) + "    N* = " + str(result["missing"]),
                 "", "Row          Value         LCL           Center        UCL           Signal"]
        for row, (value, lower, upper) in enumerate(zip(result["observations"], result["lcl"], result["ucl"]), 1):
            if row > 100:
                lines.append("… additional rows are included in the graph and exported result.")
                break
            lines.append(str(row).ljust(13) + "".join(_display(v).ljust(14) for v in (value, lower, result["center"] if value is not None else None, upper)) + ("1" if row in result["signals"] else ""))
        lines += ["", "Test 1 signal rows: " + (", ".join(map(str, result["signals"])) or "None")]
        return title + "\n".join(lines) + _report_notes(result)
    if isinstance(result, dict) and result.get("analysis") == "imr_control":
        from .imr_report import format_imr_report
        return title + format_imr_report(result)
    if isinstance(result, dict) and "i_center" in result:
        lines = ["Variable: " + result.get("variable", ""), "",
            "N = " + _display(result["count"]) + "    N* = " + _display(result["missing"]),
            "Within sigma (average moving range, span 2 / d2) = " + _display(result["within_stdev"]),
            "Average moving range = " + _display(result["average_moving_range"]), "",
            "Chart                 Center        LCL           UCL",
            "Individuals           " + _display(result["i_center"]).ljust(14) + _display(result["i_lcl"]).ljust(14) + _display(result["i_ucl"]),
            "Moving range          " + _display(result["mr_center"]).ljust(14) + _display(result["mr_lcl"]).ljust(14) + _display(result["mr_ucl"]),
            "", "Signal rows (1-based; points outside limits):",
            "Individuals: " + (", ".join(map(str, result["i_signals"])) or "None"),
            "Moving range: " + (", ".join(map(str, result["mr_signals"])) or "None"),
            "", "Missing gaps are not bridged when forming moving ranges."]
        return title + "\n".join(lines) + _report_notes(result)
    if isinstance(result, dict) and result.get("analysis") in ("capability_sixpack_normal", "capability_sixpack_between_within", "capability_sixpack_nonnormal"):
        from .sixpack_report import format_sixpack_report
        return title + format_sixpack_report(result)
    if isinstance(result, dict) and result.get("analysis") == "reliability_distribution":
        from .reliability_report import format_reliability_report
        return title + format_reliability_report(entry)
    if isinstance(result, dict) and result.get("analysis") == "nested_gage_rr":
        from .msa_reports import format_nested_gage_rr_report
        return title + format_nested_gage_rr_report(result)
    if isinstance(result, dict) and result.get("analysis") == "gage_linearity_and_bias":
        from .msa_reports import format_gage_linearity_report
        return title + format_gage_linearity_report(result)
    if isinstance(result, dict) and result.get("analysis") == "attribute_agreement_analysis":
        from .msa_reports import format_attribute_agreement_report
        return title + format_attribute_agreement_report(result)
    if isinstance(result, dict) and result.get("analysis") == "capability_nonparametric":
        from .capability_automated_report import format_nonparametric_capability_report
        return title + format_nonparametric_capability_report(entry)
    if isinstance(result, dict) and result.get("analysis") == "capability_automated":
        from .capability_automated_report import format_automated_capability_report
        return title + format_automated_capability_report(entry)
    if isinstance(result, dict) and result.get("analysis") == "capability_nonnormal":
        from .capability_nonnormal_report import format_nonnormal_capability_report
        return title + format_nonnormal_capability_report(entry)
    if isinstance(result, dict) and result.get("analysis") == "acceptance_control":
        from .acceptance_chart_report import format_acceptance_chart_report
        return title + format_acceptance_chart_report(result)
    if isinstance(result, dict) and "observed_perf" in result:
        from .capability_report import format_capability_report
        return title + format_capability_report(result)
    if isinstance(result, dict) and "cpk" in result and "ppk" in result:
        lines = ["Variable: " + result.get("variable", ""), "",
            "N = " + _display(result["count"]) + "    N* = " + _display(result["missing"]) + "    Mean = " + _display(result["mean"]),
            "LSL = " + _display(result.get("lsl")) + "    USL = " + _display(result.get("usl")) + "    Target = " + _display(result.get("target")),
            "", "Within sigma: average moving range, span 2 / d2 = " + _display(result["within_stdev"]),
            "Overall sigma: sample StDev = " + _display(result["overall_stdev"]),
            "", "Potential (Within) Capability",
            "Cp            CPL           CPU           Cpk",
            "".join(_display(result.get(k)).ljust(14) for k in ("cp", "cpl", "cpu", "cpk")),
            "", "Overall Capability", "Pp            PPL           PPU           Ppk           Cpm",
            "".join(_display(result.get(k)).ljust(14) for k in ("pp", "ppl", "ppu", "ppk", "cpm")),
            "", "Performance (parts per million)", "                        Below LSL     Above USL     Total"]
        for label, prefix in [("Observed", "observed"), ("Expected within", "expected_within"), ("Expected overall", "expected_overall")]:
            lines.append(label.ljust(24) + "".join(_display(result.get(prefix + "_ppm_" + tail)).ljust(14) for tail in ("below", "above", "total")))
        return title + "\n".join(lines) + "\n\n* denotes an index not defined for the provided specifications." + _report_notes(result)
    if isinstance(result,dict) and result.get('graph') in ('panel_graph','graph_layout'):
        lines=[str(len(result['graphs']))+' graphs; '+str(result['columns'])+' columns']
        lines += [str(index+1)+'. '+str(child.get('title','Graph')) for index,child in enumerate(result['graphs'])]
        return title+'\n'.join(lines)
    if isinstance(result, dict) and "columns" in result:
        from .descriptive_report import format_descriptive_stats_report
        return title + format_descriptive_stats_report(result)
    if isinstance(result, dict) and "intercept" in result and "slope" in result:
        variables = result.get("variables", ["X", "Y"])
        lines = ["Response: " + variables[1] + "    Predictor: " + variables[0],
                 "", "Regression Equation",
                 variables[1] + " = " + _display(result["intercept"]) + " + " + _display(result["slope"]) + " " + variables[0],
                 "", "Model Summary", "N       N*      S             R-sq",
                 _display(result.get("count")).ljust(8) + _display(result.get("missing")).ljust(8) +
                 _display(result.get("residual_stdev")).ljust(14) + _display(100 * result["r_squared"]) + "%",
                 "", "Coefficients  (" + _display(result.get("confidence", .95) * 100) + "% confidence intervals)",
                 "Term             Coef          SE Coef       T             P             Lower CI      Upper CI"]
        for term, prefix in [("Constant", "intercept"), (variables[0], "slope")]:
            fields = [result.get(prefix), result.get(prefix + "_se"), result.get(prefix + "_t"),
                      result.get(prefix + "_p_value"), result.get(prefix + "_ci_low"), result.get(prefix + "_ci_high")]
            lines.append(term.ljust(17) + "".join(_display(v).ljust(14) for v in fields))
        return title + "\n".join(lines) + _report_notes(result)
    if isinstance(result, dict) and "ss_between" in result and "group_statistics" in result:
        lines = ["Analysis of Variance", "Source           DF        Adj SS        Adj MS        F             P",
                 "Between groups   " + _display(result["df_between"]).ljust(10) + _display(result["ss_between"]).ljust(14) +
                 _display(result["ms_between"]).ljust(14) + _display(result["f"]).ljust(14) + _display(result["p_value"]),
                 "Within groups    " + _display(result["df_within"]).ljust(10) + _display(result["ss_within"]).ljust(14) + _display(result["ms_within"]),
                 "", "Group Summaries", "Group               N       N*      Mean          StDev"]
        variables = result.get("variables", [])
        for index, group in enumerate(result["group_statistics"]):
            name = variables[index] if index < len(variables) else str(group.get("group", index + 1))
            lines.append(name.ljust(20) + _display(group.get("count")).ljust(8) + _display(group.get("missing")).ljust(8) +
                         _display(group.get("mean")).ljust(14) + _display(group.get("sample_stdev")))
        return title + "\n".join(lines) + _report_notes(result)
    lines = []
    if not isinstance(result, dict):
        return title + _display(result)
    for key, value in result.items():
        label = key.replace("_", " ").capitalize()
        if key in ("fitted", "residuals"):
            shown = value[:20]
            lines.append(label + ": " + ", ".join(_display(v) for v in shown) +
                         (" … (" + str(len(value)) + " observations)" if len(value) > 20 else ""))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(label + ":")
            for item in value:
                lines.append("  " + "   ".join(k.replace("_", " ") + "=" + _display(v) for k, v in item.items()))
        elif isinstance(value, list):
            lines.append(label + ": " + (", ".join(_display(v) for v in value) or "None"))
        elif isinstance(value, dict):
            lines.append(label + ":")
            lines.extend("  " + k.replace("_", " ") + "  " + _display(v) for k, v in value.items())
        else:
            lines.append(label.ljust(25) + _display(value))
    return title + "\n".join(lines)


def _report_notes(result):
    lines = []
    assumptions = result.get("assumptions", [])
    warnings = result.get("warnings", [])
    if isinstance(assumptions, str): assumptions = [assumptions]
    if isinstance(warnings, str): warnings = [warnings]
    for assumption in assumptions:
        lines.append("Assumption: " + assumption)
    for warning in warnings:
        lines.append("Note: " + warning)
    return "\n\n" + "\n".join(lines) if lines else ""


def _display(value):
    if value is None:
        return "*"
    if isinstance(value, float):
        return format(value, ".7g")
    return str(value)


def histogram_data(values, bins=None):
    values = [finite_number(v) for v in values if v is not None]
    if not values:
        raise ValueError("A histogram needs nonmissing numeric observations.")
    bins = bins or max(1, min(50, math.ceil(math.sqrt(len(values)))))
    if type(bins) is not int or not 1 <= bins <= 200:
        raise ValueError("Choose 1 to 200 bins.")
    low, high = min(values), max(values)
    if low == high:
        low, high = low - 0.5, high + 0.5
    width = (high - low) / bins
    if not math.isfinite(width) or width <= 0:
        raise ValueError("Data range is outside supported plotting precision.")
    counts = [0] * bins
    for value in values:
        index = min(bins - 1, max(0, int((value - low) / width)))
        counts[index] += 1
    return [low + i * width for i in range(bins + 1)], counts


def boxplot_data(values):
    from .analyses import describe
    values = sorted(finite_number(v) for v in values if v is not None)
    if not values:
        raise ValueError("A boxplot needs nonmissing numeric observations.")
    summary = describe(values)
    q1, median, q3 = summary["q1"], summary["median"], summary["q3"]
    spread = q3 - q1
    if not math.isfinite(spread):
        raise ValueError("Data range is outside supported plotting precision.")
    inside = [v for v in values if q1 - 1.5 * spread <= v <= q3 + 1.5 * spread]
    return {"q1": q1, "median": median, "q3": q3, "low": min(inside), "high": max(inside),
            "outliers": [v for v in values if v < q1 - 1.5 * spread or v > q3 + 1.5 * spread]}


def chart_segments(values):
    """Preserve original row positions and break lines at missing observations."""
    segments, current = [], []
    for row, value in enumerate(values, 1):
        if value is None:
            if current: segments.append(current)
            current = []
        else:
            current.append((row, finite_number(value)))
    if current: segments.append(current)
    return segments


def _number_list(text):
    text = text.strip()
    if text.startswith("["):
        values = json.loads(text)
        if not isinstance(values, list):
            raise ValueError("Enter a list of numbers.")
        return [finite_number(v) for v in values]
    return [finite_number(float(v)) for v in text.replace(",", " ").split()]


class StatCraftApp:
    """Tk widgets are created only after the caller explicitly constructs the app."""
    PAGE_SIZE = 100

    def __init__(self, root, presenter=None):
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog, simpledialog
        self.tk, self.ttk = tk, ttk
        self.messagebox, self.filedialog, self.simpledialog = messagebox, filedialog, simpledialog
        self.root = root
        self.presenter = presenter or Presenter()
        self._prepare_blank_sheet()
        self.page = 0
        self.active = (0, 0)
        self.selection_anchor = self.selection_end = (0, 0)
        self.editor = None
        self.root.title("StatCraft")
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "StatCraft.ico"
        if icon.is_file():
            try: self.root.iconbitmap(str(icon))
            except tk.TclError: pass
        self.root.geometry("1120x620+0+0")
        self.root.minsize(850, 560)
        self.root.configure(background="#f3f3f3")
        self.root.option_add("*Font", "{Segoe UI} 9")
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TFrame", background="#f3f3f3")
        style.configure("TLabel", background="#f3f3f3", font=("Segoe UI",9))
        style.configure("TButton", font=("Segoe UI",9), padding=(5,2))
        style.configure("White.TFrame", background="white")
        style.configure("Pane.TLabel", background="#e9e9e9", font=("Segoe UI",9,"bold"), padding=(8,5))
        style.configure("White.TLabel", background="white", font=("Segoe UI",9), foreground="#555555")
        style.configure("Report.Treeview", font=("Segoe UI",9), rowheight=24, background="white", fieldbackground="white", borderwidth=0)
        style.configure("Report.Treeview.Heading", font=("Segoe UI",9))
        self._menus()
        toolbar = ttk.Frame(root, padding=(5,3)); toolbar.pack(fill="x")
        for label, command in [("New", self.new), ("Open…", self.open_file), ("Save", self.save_project),
                               ("Copy", self.copy_cells), ("Paste", self.paste_cells),
                               ("Statistics…", self.describe_column), ("Histogram…", lambda: self.plot("histogram"))]:
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0,3))
        ttk.Separator(root, orient="horizontal").pack(fill="x")
        self.main_panes = main = ttk.Panedwindow(root, orient="horizontal"); main.pack(fill="both", expand=True)
        self.navigator_pane = navigator = ttk.Frame(main, width=210, style="White.TFrame"); main.add(navigator, weight=0)
        ttk.Label(navigator, text="Navigator", style="Pane.TLabel").pack(fill="x")
        self.nav_name = ttk.Label(navigator, text="Worksheet", wraplength=190, style="White.TLabel", padding=(8,6)); self.nav_name.pack(fill="x")
        self.history_list = tk.Listbox(navigator, font=("Segoe UI",9), background="white", foreground="#333333", selectbackground="#d8edf5", selectforeground="#202020", relief="flat", highlightthickness=0, activestyle="none", exportselection=False, width=27)
        self.history_list.pack(fill="both", expand=True, padx=2)
        self.history_list.bind("<<ListboxSelect>>", self.show_history)
        ttk.Button(navigator, text="Rerun selected result", command=self.rerun_selected_result).pack(fill="x", padx=6, pady=6)
        self.work_panes = work = ttk.Panedwindow(main, orient="vertical"); main.add(work, weight=1)
        self.output_pane = session = ttk.Frame(work, style="White.TFrame"); work.add(session, weight=3)
        output_bar = ttk.Frame(session, padding=(8,5)); output_bar.pack(fill="x")
        self.output_title = ttk.Label(output_bar, text="Output", font=("Segoe UI",11)); self.output_title.pack(side="left")
        ttk.Button(output_bar, text="Export…", command=self.export_result).pack(side="right")
        self.tabs = ttk.Notebook(session); self.tabs.pack(fill="both", expand=True)
        notes_tab = ttk.Frame(self.tabs, padding=8, style="White.TFrame")
        report_tab = ttk.Frame(self.tabs, style="White.TFrame")
        self.tabs.add(notes_tab, text="Project information"); self.tabs.add(report_tab, text="Results")
        ttk.Label(notes_tab, text="Open an MPX project, MWX worksheet, CSV/TSV or StatCraft project. MPX opens all supported worksheets; select the active worksheet above the grid. Stored native results remain inactive. Project-specific import notes appear in Session output.", wraplength=650).pack(anchor="w")
        self.tabs.select(1)
        self.output = tk.Text(report_tab, wrap="none", font=("Consolas",9), background="white", foreground="#202020", relief="flat", padx=14, pady=10, height=11)
        output_y = ttk.Scrollbar(report_tab, orient="vertical", command=self.output.yview)
        output_x = ttk.Scrollbar(report_tab, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=output_y.set, xscrollcommand=output_x.set)
        self.output.grid(row=0, column=0, sticky="nsew"); output_y.grid(row=0, column=1, sticky="ns"); output_x.grid(row=1, column=0, sticky="ew")
        self._output_y,self._output_x = output_y,output_x
        self.report_surface = ttk.Frame(report_tab,style="White.TFrame",padding=(14,12))
        self.report_intro = ttk.Label(self.report_surface,text="",style="White.TLabel"); self.report_intro.pack(anchor="w",pady=(0,10))
        table_frame = ttk.Frame(self.report_surface,style="White.TFrame"); table_frame.pack(fill="x")
        self.report_table = ttk.Treeview(table_frame,show="headings",height=4,style="Report.Treeview")
        self.report_table.pack(fill="x")
        table_scroll = ttk.Scrollbar(table_frame,orient="horizontal",command=self.report_table.xview)
        table_scroll.pack(fill="x"); self.report_table.configure(xscrollcommand=table_scroll.set)
        self.report_note = ttk.Label(self.report_surface,text="",style="White.TLabel",wraplength=780); self.report_note.pack(anchor="w",pady=(12,0))
        report_tab.rowconfigure(0, weight=1); report_tab.columnconfigure(0, weight=1)
        self.data_pane = sheet_tab = ttk.Frame(work); work.add(sheet_tab, weight=4)
        sheet_bar = ttk.Frame(sheet_tab, padding=(5,4)); sheet_bar.pack(fill="x")
        self.sheet_selector = ttk.Combobox(sheet_bar, state="readonly", width=27)
        self.sheet_selector.pack(side="left")
        self.sheet_label = ttk.Label(sheet_bar, text=""); self.sheet_label.pack(side="left", padx=10)
        self.sheet_selector.bind("<<ComboboxSelected>>", self.change_worksheet)
        grid_frame = ttk.Frame(sheet_tab); grid_frame.pack(fill="both", expand=True)
        from .worksheet_grid import WorksheetGrid
        self.grid = WorksheetGrid(grid_frame)
        self.grid.heading("#0", text="Row"); self.grid.column("#0", width=65, stretch=False)
        vertical = ttk.Scrollbar(grid_frame, orient="vertical", command=self.grid.yview)
        horizontal = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.grid.xview)
        self.grid.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.grid.grid(row=0, column=0, sticky="nsew"); vertical.grid(row=0, column=1, sticky="ns"); horizontal.grid(row=1, column=0, sticky="ew")
        grid_frame.rowconfigure(0, weight=1); grid_frame.columnconfigure(0, weight=1)
        self.grid.bind("<Double-1>", self.edit_cell)
        self.grid.bind("<Return>", self.edit_selected)
        self.grid.bind("<Button-1>", self.select_cell)
        self.grid.bind("<Shift-Button-1>", self.select_cell)
        self.grid.bind("<Control-c>", self.copy_cells)
        self.grid.bind("<Control-v>", self.paste_cells)
        self.grid.bind("<F2>", self.edit_selected)
        self.grid.bind("<KeyPress>", self.type_cell)
        for key,dr,dc in (("Up",-1,0),("Down",1,0),("Left",0,-1),("Right",0,1)):
            self.grid.bind("<"+key+">",lambda event,r=dr,c=dc:self.navigate_cell(event,r,c))
            self.grid.bind("<Shift-"+key+">",lambda event,r=dr,c=dc:self.navigate_cell(event,r,c))
        nav = ttk.Frame(sheet_tab, padding=(5,2)); nav.pack(fill="x")
        ttk.Button(nav, text="◀", width=3, command=lambda: self.change_page(-1)).pack(side="left")
        ttk.Button(nav, text="▶", width=3, command=lambda: self.change_page(1)).pack(side="left", padx=3)
        self.page_label = ttk.Label(nav, text=""); self.page_label.pack(side="left", padx=10)
        self.status = tk.StringVar()
        footer = ttk.Frame(root, padding=(5,2)); footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status).pack(side="left")
        for label,mode in (("Data & Output","both"),("Data","data"),("Output","output")):
            ttk.Button(footer,text=label,command=lambda m=mode:self.set_view_mode(m)).pack(side="right",padx=2)
        self._set_output("No results to display.\n\nChoose an analysis from the Stat menu or a graph from the Graph menu.")
        self.refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-o>", lambda event: self.open_file())
        self.root.bind("<Control-s>", lambda event: self.save_project())
        self.root.bind("<Control-n>", lambda event: self.new())
        self.root.bind("<Control-z>", self.undo_edit)
        self.root.bind("<Control-y>", self.redo_edit)
        self.root.update_idletasks()
        self.main_panes.sashpos(0,180)
        self.work_panes.sashpos(0,250)

    def _menus(self):
        menu = self.tk.Menu(self.root)
        file_menu = self.tk.Menu(menu, tearoff=False)
        for label, fn in [("New", self.new), ("Open…", self.open_file), ("Save project", self.save_project),
                          ("Save project as…", lambda: self.save_project(True)), ("Import with column types…", lambda: self.open_file(True)), ("Export CSV/TSV…", self.export),
                          ("Export current result…", self.export_result)]:
            file_menu.add_command(label=label, command=fn)
        file_menu.add_separator(); file_menu.add_command(label="Exit", command=self.close)
        menu.add_cascade(label="File", menu=file_menu)
        edit = self.tk.Menu(menu, tearoff=False)
        self.edit_menu = edit
        edit.add_command(label="Undo worksheet edit", command=self.undo_edit, accelerator="Ctrl+Z")
        edit.add_command(label="Redo worksheet edit", command=self.redo_edit, accelerator="Ctrl+Y")
        edit.add_separator()
        edit.add_command(label="Copy cells", command=self.copy_cells, accelerator="Ctrl+C")
        edit.add_command(label="Paste cells", command=self.paste_cells, accelerator="Ctrl+V")
        edit.add_command(label="Edit active cell", command=self.edit_selected, accelerator="F2")
        menu.add_cascade(label="Edit", menu=edit)
        view = self.tk.Menu(menu, tearoff=False)
        self.navigator_visible = self.tk.BooleanVar(value=True)
        view.add_checkbutton(label="Navigator", variable=self.navigator_visible, command=self.toggle_navigator)
        view.add_separator()
        for label,mode in (("Data and Output","both"),("Data Only","data"),("Output Only","output")):
            view.add_command(label=label, command=lambda m=mode:self.set_view_mode(m))
        menu.add_cascade(label="View",menu=view)
        data = self.tk.Menu(menu, tearoff=False)
        data.add_command(label="Add column…", command=self.add_column)
        data.add_command(label="Add rows…", command=self.add_rows)
        data.add_command(label="Rename column…", command=self.rename_column)
        data.add_command(label="Change column type…", command=self.change_column_type)
        menu.add_cascade(label="Data", menu=data)
        calculations = self.tk.Menu(menu, tearoff=False)
        calculations.add_command(label="Calculator…", command=self.calculator)
        calculations.add_command(label="Probability Distributions…", command=self.probability)
        menu.add_cascade(label="Calc", menu=calculations)
        stat = self.tk.Menu(menu, tearoff=False)
        basic = self.tk.Menu(stat, tearoff=False)
        basic.add_command(label="Display Descriptive Statistics…", command=self.describe_column)
        for label, method in [("1-Sample t…", "one_sample_t"), ("2-Sample t (Welch)…", "two_sample_t"), ("Paired t…", "paired_t")]:
            basic.add_command(label=label, command=lambda m=method: self.inference_dialog(m))
        stat.add_cascade(label="Basic Statistics", menu=basic)
        anova = self.tk.Menu(stat, tearoff=False)
        anova.add_command(label="One-Way — Response and Factor…", command=self.stacked_anova_dialog)
        anova.add_command(label="One-Way — Separate Response Columns…", command=lambda: self.inference_dialog("one_way_anova"))
        anova.add_separator()
        anova.add_command(label="Test for Equal Variances — Response and Factor…", command=lambda: self.variance_dialog(True))
        anova.add_command(label="Test for Equal Variances — Separate Columns…", command=lambda: self.variance_dialog(False))
        stat.add_cascade(label="ANOVA", menu=anova)
        regression = self.tk.Menu(stat, tearoff=False)
        regression.add_command(label="Simple Regression…", command=lambda: self.inference_dialog("linear_regression"))
        regression.add_command(label="Fit Regression Model…", command=self.multiple_regression_dialog)
        stat.add_cascade(label="Regression", menu=regression)
        control = self.tk.Menu(stat, tearoff=False)
        control.add_command(label="I-MR…", command=self.imr_dialog)
        control.add_command(label="Xbar-R — Subgroups in Rows…", command=self.xbar_r_rows_dialog)
        control.add_command(label="Xbar-R — Measurement and Subgroup ID…", command=self.xbar_r_stacked_dialog)
        control.add_command(label="P…", command=lambda: self.attribute_chart_dialog("P"))
        control.add_command(label="U…", command=lambda: self.attribute_chart_dialog("U"))
        stat.add_cascade(label="Control Charts", menu=control)
        quality = self.tk.Menu(stat, tearoff=False)
        quality.add_command(label="Normal Capability…", command=self.capability_dialog)
        stat.add_cascade(label="Quality Tools", menu=quality)
        menu.add_cascade(label="Stat", menu=stat)
        graph = self.tk.Menu(menu, tearoff=False)
        for label, method in [("Histogram…", "histogram"), ("Scatterplot…", "scatter"), ("Boxplot…", "boxplot")]:
            graph.add_command(label=label, command=lambda m=method: self.plot(m))
        menu.add_cascade(label="Graph", menu=graph)
        help_menu = self.tk.Menu(menu, tearoff=False); help_menu.add_command(label="About StatCraft", command=self.about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=menu)

    def _guard(self, action):
        try:
            return action()
        except (ValueError, TypeError, IndexError, KeyError, OverflowError, OSError, ImportError) as exc:
            self.messagebox.showerror("StatCraft", str(exc), parent=self.root)
            self.status.set("Action was not completed: " + str(exc))
            return None

    def toggle_navigator(self):
        if self.navigator_visible.get():
            if str(self.navigator_pane) not in tuple(map(str,self.main_panes.panes())):
                self.main_panes.insert(0,self.navigator_pane,weight=0)
        elif str(self.navigator_pane) in tuple(map(str,self.main_panes.panes())):
            self.main_panes.forget(self.navigator_pane)

    def set_view_mode(self, mode):
        if mode not in ("both","data","output"):
            raise ValueError("Choose data, output or both panes.")
        for pane in (self.output_pane,self.data_pane):
            if str(pane) in tuple(map(str,self.work_panes.panes())): self.work_panes.forget(pane)
        if mode in ("both","output"): self.work_panes.add(self.output_pane,weight=3)
        if mode in ("both","data"): self.work_panes.add(self.data_pane,weight=4)
        if mode == "both":
            self.root.update_idletasks(); self.work_panes.sashpos(0,250)

    def _set_output(self, text):
        self.report_surface.grid_remove()
        self.output.grid(); self._output_y.grid(); self._output_x.grid()
        self.output.configure(state="normal"); self.output.delete("1.0", "end")
        self.output.insert("1.0", text); self.output.configure(state="disabled")

    def _render_entry(self,entry):
        self._set_output(format_entry(entry))
        result=entry["result"]
        if isinstance(result,dict) and isinstance(result.get("columns"),list):
            fields=[("name","Variable",120),("count","N",40),("missing","N*",40),
                ("mean","Mean",75),("standard_error","SE Mean",75),("sample_stdev","StDev",75),
                ("minimum","Minimum",75),("q1","Q1",65),("median","Median",65),("q3","Q3",65),("maximum","Maximum",75)]
            self.report_table.configure(columns=[field[0] for field in fields],height=min(12,max(2,len(result["columns"]))))
            self.report_table.delete(*self.report_table.get_children())
            for key,label,width in fields:
                self.report_table.heading(key,text=label)
                self.report_table.column(key,width=width,minwidth=40,stretch=False,anchor="w" if key=="name" else "e")
            for summary in result["columns"]:
                self.report_table.insert("","end",values=[_display(summary.get(key)) for key,label,width in fields])
            self.report_intro.configure(text="Descriptive statistics   •   " + entry.get("worksheet_name",""))
            self.report_note.configure(text="N* counts missing values. StDev and SE Mean use sample variance (n−1).")
            self.output.grid_remove(); self._output_y.grid_remove(); self._output_x.grid_remove()
            self.report_surface.grid(row=0,column=0,columnspan=2,sticky="nsew")

    def refresh(self):
        sheet = self.presenter.worksheet
        self.edit_menu.entryconfigure(0, state="normal" if self.presenter.can_undo else "disabled")
        self.edit_menu.entryconfigure(1, state="normal" if self.presenter.can_redo else "disabled")
        project = self.presenter.native_project
        self.sheet_selector.configure(values=[s.name for s in project.worksheets] if project else [sheet.name])
        self.sheet_selector.current(project.active_index if project else 0)
        self.root.title("StatCraft — " + sheet.name + (" *" if self.presenter.dirty else ""))
        ids = ["c" + str(i) for i in range(len(sheet.columns))]
        self.grid.configure(columns=ids)
        for i, col in enumerate(sheet.columns):
            address = "C" + str(i + 1)
            heading = address + ("-T" if col.kind == "text" else "-D" if col.kind == "date" else "") + "\n" + (col.name if col.name != address else "")
            self.grid.heading(ids[i], text=heading)
            self.grid.column(ids[i], width=110, minwidth=80, stretch=False)
        self.grid.delete(*self.grid.get_children())
        start = self.page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, max(start + 25, sheet.row_count + 10))
        for row in range(start, end):
            cells = [col.values[row] if row < len(col.values) else None for col in sheet.columns]
            values = ["" if row >= len(sheet.columns[i].values) else
                      ("" if sheet.columns[i].kind == "text" else "*") if v is None else _display(v)
                      for i, v in enumerate(cells)]
            self.grid.insert("", "end", iid=str(row), text=str(row + 1), values=values)
        self.sheet_label.configure(text=str(sheet.row_count) + " rows, " + str(len(sheet.columns)) + " columns")
        self.nav_name.configure(text=sheet.name)
        self.page_label.configure(text=(str(start + 1) + "–" + str(end) if end else "No rows yet") + " · " + str(len(sheet.constants)) + " constants · " + str(len(sheet.matrices)) + " matrices")
        self.status.set("Unsaved changes" if self.presenter.dirty else "Ready")
        self.grid.set_cell_selection(*self.active,self.selection_anchor,self.selection_end)
        self._refresh_history()

    def _confirm_leave(self):
        if not self._commit_editor():
            return False
        if not self.presenter.dirty:
            return True
        answer = self.messagebox.askyesnocancel("Unsaved project", "Save your project changes before continuing?", parent=self.root)
        if answer is None:
            return False
        if answer:
            return self.save_project()
        return True

    def new(self):
        if self._confirm_leave():
            self.presenter.new(); self._prepare_blank_sheet(); self.page = 0; self.refresh()

    def close(self):
        if self._confirm_leave():
            self.root.destroy()

    def open_file(self, explicit_types=False):
        if not self._confirm_leave():
            return
        path = self.filedialog.askopenfilename(parent=self.root, title="Open worksheet or project",
            filetypes=[("Projects and worksheets", "*.mpx *.statcraft *.csv *.tsv *.tab *.mwx"), ("MPX project", "*.mpx"), ("All files", "*.*")])
        if not path:
            return
        column_types = None
        if explicit_types and Path(path).suffix.lower() in (".csv", ".tsv", ".tab"):
            types = self.simpledialog.askstring("Delimited column types", "Optional types in column order (number, text, date).\nLeave blank for automatic inference. Choose text to preserve numeric-looking labels.", initialvalue="", parent=self.root)
            if types is None:
                return
            if types.strip():
                column_types = [kind.strip().lower() for kind in types.split(",")]
        def action():
            notices = self.presenter.load(path, column_types); self.page = 0; self.refresh()
            self.active = self.selection_anchor = self.selection_end = (0, 0)
            self._refresh_history()
            if notices:
                self._set_output("Import notes\n\n" + "\n\n".join(notices))
        self._guard(action)

    def save_project(self, save_as=False):
        if not self._commit_editor():
            return False
        path = None if save_as else self.presenter.project_path
        native = self.presenter.native_project is not None
        if not path:
            path = self.filedialog.asksaveasfilename(parent=self.root, title="Save MPX project copy" if native else "Save StatCraft project", defaultextension=".mpx" if native else ".statcraft", filetypes=[("MPX project", "*.mpx")] if native else [("StatCraft project", "*.statcraft")])
        if not path:
            return False
        if native and self.presenter.dirty and not self.messagebox.askokcancel("Save MPX copy", "Stored analyses and graphs will be retained without recalculation. New StatCraft results are not added to native output. Save the supported worksheet edits to this copy?", parent=self.root):
            return False
        def action():
            self.presenter.save(path); self.refresh(); self.status.set("Project saved")
            return True
        return bool(self._guard(action))

    def change_worksheet(self, event=None):
        if not self._commit_editor():
            self.refresh()
            return
        self._guard(lambda: self.presenter.select_worksheet(self.sheet_selector.current()))
        self.page = 0
        self.active = self.selection_anchor = self.selection_end = (0, 0)
        self.refresh()

    def export(self):
        if not self.messagebox.askokcancel("Delimited export limitations", "\n\n".join(self.presenter.export_notices()), parent=self.root):
            return
        path = self.filedialog.asksaveasfilename(parent=self.root, title="Export worksheet table", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("Tab-separated", "*.tsv")])
        if path:
            self._guard(lambda: self.presenter.export(path))

    def export_result(self):
        path = self.filedialog.asksaveasfilename(parent=self.root, title="Export current result", defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            self._guard(lambda: Path(path).write_text(self.output.get("1.0", "end-1c"), encoding="utf-8"))

    def add_column(self):
        name = self.simpledialog.askstring("Add column", "Column name:", parent=self.root)
        if name is None:
            return
        kind = self.simpledialog.askstring("Column type", "Type: number, text or date", initialvalue="number", parent=self.root)
        if kind is not None:
            self._guard(lambda: self.presenter.add_column(name, kind.strip().lower())); self.refresh()

    def add_rows(self):
        count = self.simpledialog.askinteger("Add rows", "How many rows?", initialvalue=1, minvalue=1, maxvalue=100000, parent=self.root)
        if count is not None:
            self._guard(lambda: self.presenter.add_rows(count)); self.refresh()

    def _choose_column(self, numeric=False):
        eligible = [(i, c) for i, c in enumerate(self.presenter.worksheet.columns) if not numeric or c.kind == "number"]
        if not eligible:
            self.messagebox.showinfo("Choose a column", "No eligible columns. Add or import a numeric column first.", parent=self.root)
            return None
        items = "\n".join(str(i + 1) + ": " + c.name for i, c in eligible)
        number = self.simpledialog.askinteger("Choose a column", items + "\n\nEnter its column number:", initialvalue=eligible[0][0] + 1, minvalue=1, maxvalue=len(self.presenter.worksheet.columns), parent=self.root)
        if number is None:
            return None
        if number - 1 not in [i for i, c in eligible]:
            self.messagebox.showerror("Choose a column", "That column is not numeric.", parent=self.root)
            return None
        return number - 1

    def rename_column(self):
        index = self._choose_column()
        if index is not None:
            name = self.simpledialog.askstring("Rename column", "New name:", initialvalue=self.presenter.worksheet.columns[index].name, parent=self.root)
            if name is not None:
                self._guard(lambda: self.presenter.rename_column(index, name)); self.refresh()

    def edit_selected(self, event=None):
        if self.presenter.worksheet.columns:
            self._inline_edit(*self.active)
        return "break"

    def edit_cell(self, event):
        row = self.grid.identify_row(event.y)
        column = self.grid.identify_column(event.x)
        if row and column and column != "#0":
            self.active = (int(row), int(column[1:]) - 1)
            self._inline_edit(*self.active)
        return "break"

    def _edit(self, row, column):
        col = self.presenter.worksheet.columns[column]
        value = col.values[row] if row < len(col.values) else None
        window = self.tk.Toplevel(self.root); window.title("Edit cell")
        window.transient(self.root); window.grab_set()
        self.ttk.Label(window, text=col.name + " · row " + str(row + 1) + " · " + col.kind, padding=12).pack(anchor="w")
        entry = self.tk.Text(window, width=55, height=5, font=("Segoe UI", 11)); entry.pack(padx=12, pady=(0, 12))
        entry.insert("1.0", "" if value is None else str(value)); entry.focus_set()
        def save():
            try:
                self.presenter.set_cell(row, column, entry.get("1.0", "end-1c"))
            except (ValueError, TypeError, OverflowError) as exc:
                self.messagebox.showerror("Invalid cell", str(exc), parent=window)
                return
            window.destroy(); self.refresh()
        buttons = self.ttk.Frame(window, padding=12); buttons.pack(fill="x")
        self.ttk.Button(buttons, text="Save cell", command=save).pack(side="right")
        self.ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="right", padx=8)
        if value is None and col.kind == "text":
            self.ttk.Label(window, text="Saving an empty text field creates a literal empty string.", padding=12).pack()

    def change_page(self, direction):
        self.page = max(0, self.page + direction); self.refresh()

    def _show_entry(self, entry):
        if not entry:
            return
        self.current_result = entry
        self.output_title.configure(text=entry["title"])
        self._render_entry(entry); self.tabs.select(1)
        self._refresh_history()

    def _refresh_history(self):
        self.root.title("StatCraft — " + self.presenter.worksheet.name + (" *" if self.presenter.dirty else ""))
        self.history_list.delete(0, "end")
        cache = {}
        self._navigator_entries = list(self.presenter.history)
        for index,item in enumerate(self._navigator_entries):
            stale = self.presenter.result_stale(item, cache)
            self.history_list.insert("end", ("[Changed] " if stale else "") + item["title"])
            if item is getattr(self,"current_result",None):
                self.history_list.selection_set(index); self.history_list.see(index)

    def undo_edit(self, event=None):
        self._cancel_editor()
        if self.presenter.undo():
            self.page = 0; self.refresh()
        return "break"

    def redo_edit(self, event=None):
        self._cancel_editor()
        if self.presenter.redo():
            self.page = 0; self.refresh()
        return "break"

    def describe_column(self):
        indices = self._choose_columns("Display Descriptive Statistics", minimum=1)
        if indices:
            self._show_entry(self._guard(lambda: self.presenter.describe_columns(indices)))

    def weibull(self, method):
        parameters = {}
        for key, default in [("shape", 2.0), ("scale", 1.0), ("location", 0.0)]:
            value = self.simpledialog.askfloat("Weibull " + method.upper(), key.capitalize() + ":", initialvalue=default, parent=self.root)
            if value is None:
                return
            parameters[key] = value
        value = None
        if method != "mean":
            value = self.simpledialog.askfloat("Weibull " + method.upper(), "Observation value:", initialvalue=1.0, parent=self.root)
            if value is None:
                return
        self._show_entry(self._guard(lambda: self.presenter.weibull(method, value=value, **parameters)))

    def solve(self):
        packed = self.simpledialog.askstring("Packed triangular solve", "Upper triangle by columns: U00, U01, U11, U02, U12, U22, …\nEnter comma-separated numbers or a JSON array:", initialvalue="2, 1, 3", parent=self.root)
        if packed is None:
            return
        rhs = self.simpledialog.askstring("Right-hand side", "Enter the RHS vector:", initialvalue="5, 6", parent=self.root)
        if rhs is None:
            return
        transpose = self.messagebox.askyesnocancel("System orientation", "Solve the transposed system Uᵀx=b?\nChoose No to solve Ux=b.", parent=self.root)
        if transpose is not None:
            self._show_entry(self._guard(lambda: self.presenter.solve(_number_list(packed), _number_list(rhs), transpose)))

    def show_history(self, event=None):
        selection = self.history_list.curselection()
        if selection:
            entry = self._navigator_entries[selection[0]]
            self._guard(lambda: self.restore_result(entry))

    def rerun_selected_result(self):
        if not self._commit_editor():
            return
        selected = self.history_list.curselection()
        if not selected:
            self.status.set("Select a result in the navigator first.")
            return
        original = self._navigator_entries[selected[0]]
        def calculate():
            entry = self.presenter.rerun_result(original)
            self.page = 0
            self.refresh()
            self.restore_result(entry)
            self.status.set("New result created from current source data; previous result retained.")
        self._guard(calculate)

    def restore_result(self, entry):
        """Display a saved snapshot; never re-execute commands or fit a model."""
        result = entry["result"]
        self.current_result = entry
        self.output_title.configure(text=entry["title"])
        stale = self.presenter.result_stale(entry)
        state = "Source data changed. Select this result and click Rerun selected result for new results." if stale else "Source data match the saved inputs." if stale is False else "Input tracking is unavailable for this snapshot."
        self._set_output("Result snapshot — worksheet: " + entry.get("worksheet_name", "") + "\n" + state + "\nDisplayed values are not recalculated automatically.\n\n" + format_entry(entry)); self.tabs.select(1)
        if isinstance(result.get("columns"),list):
            self._render_entry(entry)
            self.report_note.configure(text=state + "\nN* counts missing values. StDev and SE Mean use sample variance (n−1).")
        if result.get("chart") == "Xbar-R":
            self._draw_control_chart(result)
        elif "graph_data" in result and result.get("graph") in ("histogram", "scatter", "boxplot"):
            self._draw_graph(entry["title"], result["graph"], result["graph_data"],
                             result.get("xlabel", ""), result.get("ylabel", ""),
                             result.get("convention", ""), record=False)
        elif result.get("chart") in ("P", "U"):
            self._draw_attribute_chart(result)
        elif "i_center" in result:
            self._draw_control_chart(result)
        elif "cpk" in result and "ppk" in result:
            self._draw_capability(result)

    def _prepare_blank_sheet(self):
        sheet = self.presenter.worksheet
        if sheet.row_count == 0 and len(sheet.columns) == 1 and sheet.columns[0].name == "C1":
            sheet.columns[0].metadata["auto_type"] = True
            sheet.columns.extend(Column("C" + str(i), metadata={"auto_type": True}) for i in range(2, 9))

    def select_cell(self, event):
        row, column = self.grid.identify_row(event.y), self.grid.identify_column(event.x)
        if not row or column == "#0" or not column:
            return
        position = (int(row), int(column[1:]) - 1)
        self.active = position
        if not event.state & 1:
            self.selection_anchor = position
        self.selection_end = position
        low, high = sorted((self.selection_anchor[0], position[0]))
        self.grid.selection_set([str(i) for i in range(low, high + 1) if self.grid.exists(str(i))])
        self.grid.focus(row); self.grid.focus_set()
        self.grid.set_cell_selection(*self.active,self.selection_anchor,self.selection_end)
        self.status.set("Active C" + str(position[1] + 1) + ", row " + str(position[0] + 1) + " · Shift-click selects a rectangular block")
        return "break"

    def type_cell(self, event):
        if event.char and event.char.isprintable() and not event.state & 4:
            self._inline_edit(*self.active, initial=event.char)
            return "break"

    def navigate_cell(self,event,dr,dc):
        if not self._commit_editor(): return "break"
        sheet=self.presenter.worksheet
        if not sheet.columns: return "break"
        row=max(0,min(self.active[0]+dr,max(25,sheet.row_count)-1))
        column=max(0,min(self.active[1]+dc,len(sheet.columns)-1))
        self.active=(row,column)
        if not event.state & 1: self.selection_anchor=self.active
        self.selection_end=self.active
        self.page=row//self.PAGE_SIZE
        self.refresh()
        low,high=sorted((self.selection_anchor[0],self.selection_end[0]))
        self.grid.selection_set([str(i) for i in range(low,high+1) if self.grid.exists(str(i))])
        self.grid.see_cell(row,column); self.grid.focus_set()
        self.status.set("C"+str(column+1)+", row "+str(row+1))
        return "break"

    def _inline_edit(self, row, column, initial=None):
        if self.editor is not None and not self._commit_editor():
            return
        if not 0 <= column < len(self.presenter.worksheet.columns):
            return
        self.page = row // self.PAGE_SIZE
        if not self.grid.exists(str(row)):
            self.refresh()
        self.grid.see_cell(str(row),column); self.root.update_idletasks()
        box = self.grid.bbox(str(row), "c" + str(column))
        if not box:
            self.status.set("Scroll horizontally to the selected column.")
            return
        self.grid.set_cell_selection(row,column,self.selection_anchor,self.selection_end)
        low,high=sorted((self.selection_anchor[0],self.selection_end[0]))
        self.grid.selection_set([str(i) for i in range(low,high+1) if self.grid.exists(str(i))])
        col = self.presenter.worksheet.columns[column]
        value = col.values[row] if row < len(col.values) else None
        if isinstance(value, str) and "\n" in value:
            self._edit(row, column)
            return
        widget = self.ttk.Entry(self.grid, font=("Segoe UI", 10))
        widget.place(x=box[0], y=box[1], width=box[2], height=box[3])
        widget.insert(0, initial if initial is not None else "" if value is None else str(value))
        if initial is None:
            widget.selection_range(0, "end")
        self.editor = (widget, row, column)
        widget.focus_set()
        widget.bind("<Return>", lambda event: self._move_after_edit(1, 0))
        widget.bind("<Tab>", lambda event: self._move_after_edit(0, 1))
        widget.bind("<Shift-Tab>", lambda event: self._move_after_edit(0, -1))
        widget.bind("<Escape>", self._cancel_editor)
        widget.bind("<FocusOut>", lambda event: self._commit_editor())

    def _cancel_editor(self, event=None):
        if self.editor is not None:
            widget, row, column = self.editor
            self.editor = None; widget.destroy(); self.grid.focus_set()
        return "break"

    def _commit_editor(self):
        if self.editor is None:
            return True
        widget, row, column = self.editor
        try:
            self.presenter.set_cell(row, column, widget.get())
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set("Invalid cell: " + str(exc)); widget.focus_set()
            return False
        self.editor = None; widget.destroy(); self.active = (row, column); self.refresh()
        return True

    def _move_after_edit(self, row_delta, column_delta):
        if not self._commit_editor():
            return "break"
        row, column = self.active
        column += column_delta; row += row_delta
        if column >= len(self.presenter.worksheet.columns):
            column = 0; row += 1
        elif column < 0:
            column = len(self.presenter.worksheet.columns) - 1; row = max(0, row - 1)
        self.active = self.selection_anchor = self.selection_end = (max(0, row), column)
        self._inline_edit(*self.active)
        return "break"

    def copy_cells(self, event=None):
        first, last = self.selection_anchor, self.selection_end
        text = self._guard(lambda: self.presenter.copy_block(min(first[0], last[0]), max(first[0], last[0]),
                          min(first[1], last[1]), max(first[1], last[1])))
        if text is not None:
            self.root.clipboard_clear(); self.root.clipboard_append(text)
            self.status.set("Selected cell block copied")
        return "break"

    def paste_cells(self, event=None):
        if not self._commit_editor():
            return "break"
        try:
            text = self.root.clipboard_get()
        except self.tk.TclError:
            self.messagebox.showerror("Paste", "The clipboard does not contain text.", parent=self.root)
            return "break"
        self._guard(lambda: self.presenter.paste(*self.active, text)); self.refresh()
        return "break"

    def change_column_type(self):
        index = self._choose_column()
        if index is None:
            return
        kind = self.simpledialog.askstring("Change column type", "number, text or date. All existing cells must convert successfully.", initialvalue=self.presenter.worksheet.columns[index].kind, parent=self.root)
        if kind is not None:
            self._guard(lambda: self.presenter.set_column_type(index, kind.strip().lower())); self.refresh()

    def _choose_columns(self, title, minimum=1, maximum=None, note="", kinds=("number",)):
        eligible = [(i, c) for i, c in enumerate(self.presenter.worksheet.columns) if c.kind in kinds]
        if len(eligible) < minimum:
            self.messagebox.showinfo(title, "Add or import enough columns of the required type first.", parent=self.root)
            return None
        window = self.tk.Toplevel(self.root); window.title(title); window.transient(self.root); window.grab_set()
        window.geometry("430x390")
        self.ttk.Label(window, text="Select variables (Ctrl/Shift for multiple).\n" + note, wraplength=390, padding=12).pack(anchor="w")
        choice = self.tk.Listbox(window, selectmode="extended", exportselection=False, font=("Segoe UI", 11))
        choice.pack(fill="both", expand=True, padx=12)
        for index, col in eligible:
            choice.insert("end", "C" + str(index + 1) + "   " + col.name)
        choice.selection_set(0)
        result = []
        def accept():
            selected = [eligible[i][0] for i in choice.curselection()]
            if len(selected) < minimum or (maximum is not None and len(selected) > maximum):
                self.messagebox.showerror(title, "Select " + (str(minimum) if minimum == maximum else "at least " + str(minimum)) + " variables.", parent=window)
                return
            result.extend(selected); window.destroy()
        buttons = self.ttk.Frame(window, padding=12); buttons.pack(fill="x")
        self.ttk.Button(buttons, text="OK", command=accept).pack(side="right")
        self.ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="right", padx=8)
        self.root.wait_window(window)
        return result or None

    def inference_dialog(self, method):
        count = 1 if method == "one_sample_t" else 2
        note = "Separate group columns." if method == "one_way_anova" else "First selected column is X (predictor); second is Y (response)." if method == "linear_regression" else "Paired data stay aligned by worksheet row." if method == "paired_t" else "Select sample columns."
        columns = self._choose_columns(method.replace("_", " ").title(), count, None if method == "one_way_anova" else count, note)
        if not columns:
            return
        mu, confidence = 0.0, .95
        if method in ("one_sample_t", "two_sample_t", "paired_t"):
            mu = self.simpledialog.askfloat("Null hypothesis", "Hypothesized mean" + (" difference:" if method != "one_sample_t" else ":"), initialvalue=0.0, parent=self.root)
            if mu is None:
                return
        if method != "one_way_anova":
            confidence = self.simpledialog.askfloat("Confidence level", "Confidence level (0 to 1):", initialvalue=.95, parent=self.root)
            if confidence is None:
                return
        self._show_entry(self._guard(lambda: self.presenter.inference(method, columns, mu, confidence)))

    def variance_dialog(self, stacked):
        if stacked:
            response = self._choose_columns("Equal Variances: Response",1,1,"Choose the numeric response.")
            if not response:
                return
            factor = self._choose_columns("Equal Variances: Factor",1,1,"Choose the group column. Incomplete response/factor pairs are omitted.", kinds=("number","text"))
            if not factor:
                return
        else:
            indices = self._choose_columns("Equal Variances: Groups",2,None,"Each column is one group; missing values are omitted independently.")
            if not indices:
                return
        window = self.tk.Toplevel(self.root); window.title("Equal Variances: Method")
        window.transient(self.root); window.grab_set()
        choice = self.tk.StringVar(value="Levene")
        self.ttk.Label(window,text="Levene: median-centered Brown–Forsythe test.\nBartlett: assumes normally distributed populations.\nBonett and simultaneous comparison intervals are not implemented.",padding=14).pack(anchor="w")
        self.ttk.Combobox(window,textvariable=choice,values=("Levene","Bartlett"),state="readonly").pack(padx=14,pady=8)
        selected = []
        def accept():
            selected.append(choice.get()); window.destroy()
        self.ttk.Button(window,text="OK",command=accept).pack(side="right",padx=14,pady=14)
        self.ttk.Button(window,text="Cancel",command=window.destroy).pack(side="right",pady=14)
        self.root.wait_window(window)
        if selected:
            action = (lambda: self.presenter.equal_variances_stacked(response[0],factor[0],selected[0])) if stacked else (lambda: self.presenter.equal_variances_columns(indices,selected[0]))
            self._show_entry(self._guard(action))

    def stacked_anova_dialog(self):
        response = self._choose_columns("One-Way ANOVA: Response", 1, 1, "Choose the numeric response column.")
        if not response:
            return
        factor = self._choose_columns("One-Way ANOVA: Factor", 1, 1, "Choose the numeric or text group column. Incomplete pairs are omitted. Equal variances assumed.", kinds=("number", "text"))
        if factor:
            self._show_entry(self._guard(lambda: self.presenter.stacked_anova(response[0], factor[0])))

    def multiple_regression_dialog(self):
        response = self._choose_columns("Regression response", 1, 1, "Choose the numeric response Y.")
        if not response:
            return
        predictors = self._choose_columns("Regression predictors", 1, None, "Choose continuous predictors; exclude the response.")
        if not predictors:
            return
        confidence = self.simpledialog.askfloat("Confidence level", "Confidence level (0 to 1):", initialvalue=.95, parent=self.root)
        if confidence is not None:
            self._show_entry(self._guard(lambda: self.presenter.multiple_regression(response[0], predictors, confidence)))

    def attribute_chart_dialog(self, chart):
        counts = self._choose_columns(chart + " Chart: Counts", 1, 1,
            "Choose the count of defective units." if chart == "P" else "Choose the count of defects.")
        if not counts:
            return
        sizes = self._choose_columns(chart + " Chart: Sample Size", 1, 1,
            "Choose the number inspected per row." if chart == "P" else "Choose the exposure or units inspected per row.")
        if sizes:
            def run():
                entry = self.presenter.attribute_chart(chart, counts[0], sizes[0])
                self._show_entry(entry)
                self._draw_attribute_chart(entry["result"])
            self._guard(run)

    def _draw_attribute_chart(self, result):
        observations = result["observations"]
        if len(observations) > 10000:
            raise ValueError("Control chart drawing supports at most 10,000 worksheet rows.")
        values = [v for key in ("observations", "lcl", "ucl") for v in result[key] if v is not None] + [result["center"]]
        low, high = min(values), max(values)
        span = high - low
        if not math.isfinite(span):
            raise ValueError("Chart range exceeds supported precision.")
        if span == 0:
            span = max(.01, abs(low) * .1)
        low -= span * .08
        high += span * .08
        if not math.isfinite(high - low) or high == low:
            raise ValueError("Chart range exceeds supported precision.")
        window = self.tk.Toplevel(self.root)
        window.title(result["chart"] + " Chart of " + result.get("count_variable", "Data"))
        window.geometry("900x560")
        canvas = self.tk.Canvas(window, width=880, height=540, background="white")
        canvas.pack(fill="both", expand=True)
        canvas.create_text(440, 25, text=window.title(), font=("Segoe UI", 15, "bold"))
        def x(row): return 85 + (row - 1) / max(1, len(observations) - 1) * 620
        def y(value): return 445 - (value - low) / (high - low) * 365
        canvas.create_line(85, 80, 85, 445, 705, 445, fill="#333")
        canvas.create_text(23, 265, text="Proportion defective" if result["chart"] == "P" else "Defects per unit", angle=90)
        for i in range(5):
            value = low + (high - low) * i / 4
            canvas.create_text(78, y(value), text=_display(value), anchor="e", font=("Segoe UI", 9))
            row = 1 + round((len(observations) - 1) * i / 4)
            canvas.create_text(x(row), 462, text=str(row), font=("Segoe UI", 9))
        canvas.create_line(85, y(result["center"]), 705, y(result["center"]), fill="#488553", dash=(5, 3))
        canvas.create_text(718, y(result["center"]), text="Center = " + _display(result["center"]), anchor="w", fill="#488553")
        for key in ("lcl", "ucl"):
            for segment in chart_segments(result[key]):
                coordinates = [c for row, value in segment for c in (x(row), y(value))]
                if len(segment) > 1:
                    canvas.create_line(*coordinates, fill="#b74b4b", dash=(5, 3))
                else:
                    row, value = segment[0]
                    canvas.create_oval(x(row)-2, y(value)-2, x(row)+2, y(value)+2, outline="#b74b4b")
        signals = set(result["signals"])
        for segment in chart_segments(observations):
            coordinates = [c for row, value in segment for c in (x(row), y(value))]
            if len(segment) > 1:
                canvas.create_line(*coordinates, fill="#346b9c")
            for row, value in segment:
                color = "#c63b3b" if row in signals else "#346b9c"
                canvas.create_oval(x(row)-3, y(value)-3, x(row)+3, y(value)+3, fill=color, outline=color)
        canvas.create_text(440, 495, text="Worksheet row · Weighted center · Variable three-sigma limits · Test 1 only", font=("Segoe UI", 10))
        return window

    def xbar_r_rows_dialog(self):
        indices = self._choose_columns("Xbar-R: Subgroups in Rows", 2, 10,
            "Choose 2 to 10 measurement columns. Every row is one subgroup. Complete equal-size subgroups; Test 1 only.")
        if indices:
            def run():
                entry = self.presenter.xbar_r_rows(indices)
                self._show_entry(entry); self._draw_control_chart(entry["result"])
            self._guard(run)

    def xbar_r_stacked_dialog(self):
        response = self._choose_columns("Xbar-R: Measurements", 1, 1, "Choose the numeric measurement column.")
        if not response:
            return
        factor = self._choose_columns("Xbar-R: Subgroup IDs", 1, 1,
            "Choose numeric or text subgroup IDs. Groups follow first occurrence; complete equal sizes 2 to 10 only.", kinds=("number","text"))
        if factor:
            def run():
                entry = self.presenter.xbar_r_stacked(response[0], factor[0])
                self._show_entry(entry); self._draw_control_chart(entry["result"])
            self._guard(run)

    def imr_dialog(self):
        columns = self._choose_columns("I-MR Chart", 1, 1, "Observations in time order. Span 2, three-sigma limits, Test 1 only. Missing gaps break moving ranges.")
        if columns:
            def run():
                entry = self.presenter.individuals_moving_range(columns[0])
                self._show_entry(entry)
                self._draw_control_chart(entry['result'])
            self._guard(run)

    def capability_dialog(self):
        columns = self._choose_columns("Normal Capability", 1, 1, "Individual observations. Within sigma: average span-2 moving range / d2. Overall sigma: sample StDev.")
        if not columns:
            return
        window = self.tk.Toplevel(self.root); window.title("Normal Capability"); window.transient(self.root); window.grab_set()
        frame = self.ttk.Frame(window, padding=18); frame.pack(fill="both", expand=True)
        options = []
        for row, label in enumerate(["Lower specification", "Upper specification", "Target (optional)"]):
            self.ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            var = self.tk.StringVar(); options.append(var)
            self.ttk.Entry(frame, textvariable=var, width=25).grid(row=row, column=1, pady=6)
        self.ttk.Label(frame, text="Leave unused specifications blank. A normal distribution is assumed.\nMissing gaps are not bridged for within-sigma estimation.").grid(row=3, column=0, columnspan=2, pady=10)
        def run():
            try:
                parameters = [None if not v.get().strip() else finite_number(float(v.get())) for v in options]
                entry = self.presenter.normal_capability(columns[0], *parameters)
            except (ValueError, TypeError, OverflowError) as exc:
                self.messagebox.showerror("Normal Capability", str(exc), parent=window)
                return
            window.destroy(); self._show_entry(entry)
            self._guard(lambda: self._draw_capability(entry['result']))
        self.ttk.Button(frame, text="OK", command=run).grid(row=4, column=1, sticky="e", pady=8)
        self.ttk.Button(frame, text="Cancel", command=window.destroy).grid(row=4, column=0, sticky="w")
        self.root.wait_window(window)

    def _draw_control_chart(self, result):
        subgroup = result.get("chart") == "Xbar-R"
        if subgroup:
            result = {**result, 'observations':result['means'], 'moving_ranges':result['ranges'],
                **{'i'+suffix:result['xbar'+suffix] for suffix in ('_center','_lcl','_ucl','_signals')},
                **{'mr'+suffix:result['r'+suffix] for suffix in ('_center','_lcl','_ucl','_signals')}}
        window = self.tk.Toplevel(self.root); window.title(("Xbar-R" if subgroup else "I-MR") + " Chart of " + result.get('variable','Data'))
        window.geometry("920x710")
        canvas = self.tk.Canvas(window, width=900, height=660, background="white"); canvas.pack(fill="both", expand=True)
        graph_title = window.title()
        canvas.create_text(450, 22, text=graph_title if len(graph_title) <= 70 else graph_title[:67] + '…', font=("Segoe UI",15,"bold"))
        if len(result['observations']) > 10000:
            window.destroy(); raise ValueError('This chart renderer supports at most 10,000 worksheet positions.')
        def panel(values, prefix, top, bottom, ylabel, signals):
            clean = [v for v in values if v is not None]
            limits = [result[prefix + suffix] for suffix in ('_lcl','_center','_ucl')]
            low, high = min(clean + limits), max(clean + limits)
            span = high - low
            if not math.isfinite(span): raise ValueError('Chart range exceeds supported precision.')
            if span == 0: span = max(.5, abs(low)*.01)
            low -= span*.08; high += span*.08
            if high == low or not math.isfinite(high-low): raise ValueError('Chart range exceeds supported precision.')
            def x(row): return 80 + (row-1)/max(1,len(values)-1)*640
            def y(value): return bottom - (value-low)/(high-low)*(bottom-top)
            canvas.create_line(80,top,80,bottom,720,bottom,fill='#333')
            canvas.create_text(26,(top+bottom)/2,text=ylabel,angle=90)
            for i in range(5):
                value = low+(high-low)*i/4
                canvas.create_text(73,y(value),text=_display(value),anchor='e',font=('Segoe UI',9))
                row = 1+round((len(values)-1)*i/4)
                labels = result.get('subgroup_labels', [])
                tick = str(labels[row-1]) if subgroup and row <= len(labels) else str(row)
                canvas.create_text(x(row),bottom+15,text=tick[:16],font=('Segoe UI',9))
            for suffix, label, color in [('_lcl','LCL','#b74b4b'),('_center','Mean','#488553'),('_ucl','UCL','#b74b4b')]:
                value = result[prefix+suffix]
                canvas.create_line(80,y(value),720,y(value),fill=color,dash=(5,3))
                canvas.create_text(733,y(value),text=label+' = '+_display(value),anchor='w',fill=color,font=('Segoe UI',9))
            for segment in chart_segments(values):
                coordinates = [coordinate for row,value in segment for coordinate in (x(row),y(value))]
                if len(segment)>1: canvas.create_line(*coordinates,fill='#346b9c')
                for row,value in segment:
                    color = '#c63b3b' if row in signals else '#346b9c'
                    canvas.create_oval(x(row)-3,y(value)-3,x(row)+3,y(value)+3,fill=color,outline=color)
        try:
            panel(result['observations'],'i',60,290,'Subgroup mean' if subgroup else 'Individual value',set(result['i_signals']))
            panel(result['moving_ranges'],'mr',365,595,'Subgroup range' if subgroup else 'Moving range',set(result['mr_signals']))
            footer = 'Subgroup position · Size ' + str(result['subgroup_size']) + ' · Rbar / d2 · Test 1 only' if subgroup else 'Observation (worksheet row) · Span 2 · Test 1 only · Missing gaps are not bridged'
            canvas.create_text(400,630,text=footer,font=('Segoe UI',9))
        except Exception:
            window.destroy(); raise

    def _draw_capability(self, result):
        window = self.tk.Toplevel(self.root); window.title('Normal Capability of '+result.get('variable','Data'))
        window.geometry('920x620')
        canvas = self.tk.Canvas(window,width=900,height=600,background='white'); canvas.pack(fill='both',expand=True)
        canvas.create_text(450,25,text=window.title(),font=('Segoe UI',15,'bold'))
        from scipy.stats import norm
        values = result['observations']
        sigma, mean = result['overall_stdev'], result['mean']
        bounds = values+[mean-4*sigma,mean+4*sigma]+[result[k] for k in ('lsl','usl') if result[k] is not None]
        low,high=min(bounds),max(bounds)
        if not math.isfinite(high-low) or high==low:
            window.destroy(); raise ValueError('Capability graph range exceeds supported precision.')
        edges,counts=histogram_data(values)
        width=edges[1]-edges[0]
        xs=[low+(high-low)*i/200 for i in range(201)]
        curves=[]
        for key in ('within_stdev','overall_stdev'):
            curves.append([float(norm.pdf((value-mean)/result[key]))/result[key]*len(values)*width for value in xs])
        peak=max(max(counts),*(max(curve) for curve in curves))*1.1
        if not math.isfinite(peak) or peak<=0:
            window.destroy(); raise ValueError('Capability graph scale exceeds supported precision.')
        def x(value): return 70+(value-low)/(high-low)*590
        def y(value): return 480-value/peak*390
        canvas.create_line(70,70,70,480,660,480,fill='#333')
        canvas.create_text(20,275,text='Frequency',angle=90)
        for i in range(5):
            height=peak*i/4
            canvas.create_text(62,y(height),text=_display(height),anchor='e',font=('Segoe UI',9))
        for i,count in enumerate(counts):
            canvas.create_rectangle(x(edges[i]),y(count),x(edges[i+1]),480,fill='#bdcfdf',outline='white')
        for curve,color,label in zip(curves,['#d57936','#346b9c'],['Within','Overall']):
            coordinates=[coordinate for value,height in zip(xs,curve) for coordinate in (x(value),y(height))]
            canvas.create_line(*coordinates,fill=color,width=2)
            canvas.create_text(730,100 if label=='Within' else 125,text=label+' normal fit',fill=color,anchor='w')
        for key,label in [('lsl','LSL'),('usl','USL'),('target','Target')]:
            value=result[key]
            if value is not None and low<=value<=high:
                canvas.create_line(x(value),70,x(value),480,dash=(5,3),fill='#b34646')
                canvas.create_text(x(value),57,text=label,font=('Segoe UI',9))
        for i in range(6):
            value=low+(high-low)*i/5
            canvas.create_text(x(value),500,text=_display(value),font=('Segoe UI',9))
        canvas.create_text(365,535,text=result.get('variable','Value'))
        for i,key in enumerate(['mean','within_stdev','overall_stdev','cp','cpk','pp','ppk','cpm']):
            canvas.create_text(700,165+i*30,text=key.replace('_',' ').upper()+': '+_display(result[key]),anchor='w')
        canvas.create_text(450,575,text='Normal fits · Within sigma: average span-2 moving range / d2 · Overall: sample StDev',font=('Segoe UI',9))

    def probability(self):
        from . import probability
        window = self.tk.Toplevel(self.root); window.title("Probability Distributions"); window.transient(self.root); window.grab_set()
        frame = self.ttk.Frame(window, padding=16); frame.pack(fill="both", expand=True)
        distribution = self.tk.StringVar(value="Normal"); operation = self.tk.StringVar(value="CDF")
        self.ttk.Label(frame, text="Distribution").grid(row=0, column=0, sticky="w", pady=5)
        select = self.ttk.Combobox(frame, textvariable=distribution, values=list(probability.PARAMETERS), state="readonly", width=28)
        select.grid(row=0, column=1, pady=5)
        self.ttk.Label(frame, text="Operation").grid(row=1, column=0, sticky="w", pady=5)
        method = self.ttk.Combobox(frame, textvariable=operation, values=["PDF/PMF", "CDF", "Inverse CDF"], state="readonly", width=28)
        method.grid(row=1, column=1, pady=5)
        parameters_frame = self.ttk.Frame(frame); parameters_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=12)
        parameter_vars = []
        def update(event=None):
            for child in parameters_frame.winfo_children(): child.destroy()
            parameter_vars.clear()
            for row, (label, default) in enumerate(zip(probability.PARAMETERS[distribution.get()], probability.DEFAULTS[distribution.get()])):
                variable = self.tk.StringVar(value=str(default)); parameter_vars.append(variable)
                self.ttk.Label(parameters_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 20), pady=5)
                self.ttk.Entry(parameters_frame, textvariable=variable, width=18).grid(row=row, column=1, pady=5)
        select.bind("<<ComboboxSelected>>", update); update()
        input_label = self.ttk.Label(frame, text="Input value"); input_label.grid(row=3, column=0, sticky="w", pady=5)
        value = self.tk.StringVar(value="0"); self.ttk.Entry(frame, textvariable=value).grid(row=3, column=1, pady=5)
        def update_operation(event=None):
            inverse = operation.get() == "Inverse CDF"
            input_label.configure(text="Cumulative probability" if inverse else "Input value")
            value.set("0.5" if inverse else "0")
        method.bind("<<ComboboxSelected>>", update_operation)
        def calculate():
            try:
                result = probability.calculate(distribution.get(), operation.get(), finite_number(float(value.get())), [finite_number(float(v.get())) for v in parameter_vars])
            except (ValueError, TypeError, OverflowError) as exc:
                self.messagebox.showerror("Probability Distributions", str(exc), parent=window); return
            entry = self.presenter._record(distribution.get() + " — " + operation.get(), result)
            window.destroy(); self._show_entry(entry)
        self.ttk.Button(frame, text="Calculate", command=calculate).grid(row=4, column=1, sticky="e", pady=12)
        self.ttk.Button(frame, text="Cancel", command=window.destroy).grid(row=4, column=0, sticky="w", pady=12)

    def calculator(self):
        expression = self.simpledialog.askstring("Calculator", "Expression using C1, C2, … and ABS, SQRT, LOG, LOG10, EXP, SIN, COS, ROUND:\nExamples: C1 + C2    SQRT(C1)    C1 ^ 2", parent=self.root)
        if expression is None:
            return
        destination = self.simpledialog.askstring("Store calculated result", "Destination column number, or a name for a new numeric column:", initialvalue="Calculated", parent=self.root)
        if destination is None:
            return
        def calculate():
            entry = self.presenter.calculate(expression, destination)
            self.refresh(); self._show_entry(entry)
        self._guard(calculate)

    def plot(self, method):
        indices = self._choose_columns(method.title(), 2 if method == "scatter" else 1, 2 if method == "scatter" else 1,
                    "First column is X; second column is Y." if method == "scatter" else "Missing values are excluded.")
        if not indices:
            return
        def make():
            cols = [self.presenter.worksheet.columns[i] for i in indices]
            if method == "histogram":
                bins = self.simpledialog.askinteger("Histogram", "Equal-width bins (default uses square-root count):", initialvalue=max(1, min(50, math.ceil(math.sqrt(len(cols[0].numeric_values()))))), minvalue=1, maxvalue=200, parent=self.root)
                if bins is None: return
                edges, counts = histogram_data(cols[0].values, bins)
                self._draw_graph("Histogram of " + cols[0].name, method, (edges, counts), cols[0].name, "Frequency", "Equal-width bins; missing observations excluded.", recipe={"action":"graph", "parameters":{"method":method, "indices":list(indices), "bins":bins}})
            elif method == "scatter":
                points = self.presenter.worksheet.complete_rows(indices)
                if not points: raise ValueError("A scatterplot needs at least one complete pair.")
                self._draw_graph("Scatterplot of " + cols[1].name + " vs " + cols[0].name, method, points, cols[0].name, cols[1].name, "Complete pairs only; no fitted line.", recipe={"action":"graph", "parameters":{"method":method, "indices":list(indices), "bins":1}})
            else:
                summary = boxplot_data(cols[0].values)
                self._draw_graph("Boxplot of " + cols[0].name, method, summary, cols[0].name, "", "Quartiles: clamped (n+1)p interpolation. Standard whiskers: last value within 1.5 IQR; circles: outliers. Native boxplot equivalence unverified.", recipe={"action":"graph", "parameters":{"method":method, "indices":list(indices), "bins":1}})
        self._guard(make)

    def _draw_graph(self, title, method, data, xlabel, ylabel, note, record=True, recipe=None):
        window = self.tk.Toplevel(self.root); window.title(title); window.geometry("850x590")
        canvas = self.tk.Canvas(window, width=840, height=530, background="white", highlightthickness=0); canvas.pack(fill="both", expand=True)
        self.ttk.Label(window, text=note, padding=7, wraplength=820).pack(fill="x")
        canvas.create_text(420, 26, text=title, font=("Segoe UI", 15, "bold"))
        left, right, top, bottom = 90, 790, 65, 450
        if method == "histogram":
            edges, counts = data; xmin, xmax, ymin, ymax = edges[0], edges[-1], 0, max(counts) * 1.1
        elif method == "scatter":
            xmin, xmax = min(p[0] for p in data), max(p[0] for p in data)
            ymin, ymax = min(p[1] for p in data), max(p[1] for p in data)
        else:
            all_values = [data["low"], data["high"]] + data["outliers"]
            xmin, xmax, ymin, ymax = min(all_values), max(all_values), 0, 1
        if xmin == xmax: xmin -= .5; xmax += .5
        if ymin == ymax: ymin -= .5; ymax += .5
        xspan, yspan = xmax - xmin, ymax - ymin
        if not math.isfinite(xspan) or not math.isfinite(yspan) or xspan <= 0 or yspan <= 0:
            window.destroy(); raise ValueError("Plot range is outside supported numeric precision.")
        def x(value): return left + (value - xmin) / xspan * (right - left)
        def y(value): return bottom - (value - ymin) / yspan * (bottom - top)
        canvas.create_line(left, top, left, bottom, right, bottom, fill="#333333")
        for i in range(6):
            xv = xmin + xspan * i / 5
            canvas.create_line(x(xv), bottom, x(xv), bottom + 5)
            canvas.create_text(x(xv), bottom + 18, text=_display(xv), font=("Segoe UI", 9))
            if method != "boxplot":
                yv = ymin + yspan * i / 5
                canvas.create_line(left - 5, y(yv), left, y(yv))
                canvas.create_text(left - 10, y(yv), text=_display(yv), anchor="e", font=("Segoe UI", 9))
        canvas.create_text((left + right) / 2, bottom + 55, text=xlabel, font=("Segoe UI", 11))
        if ylabel: canvas.create_text(25, (top + bottom) / 2, text=ylabel, angle=90, font=("Segoe UI", 11))
        if method == "histogram":
            for i, count in enumerate(counts):
                canvas.create_rectangle(x(edges[i]), y(count), x(edges[i + 1]), bottom, fill="#507ea4", outline="white")
        elif method == "scatter":
            for xv, yv in data:
                canvas.create_oval(x(xv) - 3, y(yv) - 3, x(xv) + 3, y(yv) + 3, fill="#426e97", outline="")
        else:
            middle = (top + bottom) / 2
            canvas.create_line(x(data["low"]), middle, x(data["high"]), middle)
            for bound in ("low", "high"):
                canvas.create_line(x(data[bound]), middle - 18, x(data[bound]), middle + 18)
            canvas.create_rectangle(x(data["q1"]), middle - 55, x(data["q3"]), middle + 55, fill="#9bb9d0", outline="#333333")
            canvas.create_line(x(data["median"]), middle - 55, x(data["median"]), middle + 55, width=2)
            for value in data["outliers"]:
                canvas.create_oval(x(value) - 4, middle - 4, x(value) + 4, middle + 4, outline="#426e97")
        if record:
            self.presenter._record(title, {"graph": method, "graph_data": data, "xlabel": xlabel,
                "ylabel": ylabel, "convention": note, "variables": [xlabel, ylabel] if method == "scatter" else [xlabel]}, recipe=recipe)
        # The graph window remains visible; update its navigator entry without replacing output.
        self._refresh_history()

    def about(self):
        self.messagebox.showinfo("About StatCraft", "StatCraft\n\nOriginal worksheet and statistical analysis application.\nSummaries, t-tests, one-way ANOVA, simple/multiple regression, I-MR charts, normal capability, probability distributions, worksheet calculator and graphs. Worksheet edits support Undo/Redo.\n\nMPX projects: all supported worksheets, native history and retained package contents; conservative Save Copy for same-size numeric/text edits. Stored native output remains inactive. New native projects and full compatibility remain unverified. MWX import remains read-only.", parent=self.root)


def main():
    import tkinter as tk
    root = tk.Tk()
    StatCraftApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
