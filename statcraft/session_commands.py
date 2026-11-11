"""Minitab Session Command & Batch Exec (.MTB) Interpreter for StatCraft."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, List, Tuple


def _strip_comment(line: str) -> str:
    """Strip unquoted # comments or Minitab NOTE statements."""
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped.upper() == "NOTE" or stripped.upper().startswith("NOTE "):
        return ""
    in_single = False
    in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:idx].strip()
    return stripped


def _split_unquoted_semicolons(line: str) -> List[Tuple[str, bool]]:
    """Split a line by unquoted semicolons; returns (segment_text, had_trailing_semicolon)."""
    segments: List[Tuple[str, bool]] = []
    start = 0
    in_single = False
    in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double:
            seg = line[start:idx].strip()
            if seg:
                segments.append((seg, True))
            start = idx + 1
    tail = line[start:].strip()
    if tail:
        segments.append((tail, False))
    return segments


def parse_script_blocks(script_text: str) -> List[Tuple[str, List[str]]]:
    """Parse multi-line Minitab command script with ';' continuations and '.' terminators."""
    raw_lines = [_strip_comment(ln) for ln in script_text.splitlines()]
    raw_lines = [ln for ln in raw_lines if ln]
    blocks: List[Tuple[str, List[str]]] = []
    current_main: str | None = None
    current_subs: List[str] = []

    for ln in raw_lines:
        for seg, has_semi in _split_unquoted_semicolons(ln):
            if current_main is None:
                if has_semi:
                    current_main = seg
                    current_subs = []
                elif seg.endswith("."):
                    blocks.append((seg[:-1].strip(), []))
                else:
                    blocks.append((seg, []))
            else:
                if has_semi:
                    current_subs.append(seg)
                elif seg.endswith("."):
                    sub = seg[:-1].strip()
                    if sub:
                        current_subs.append(sub)
                    blocks.append((current_main, current_subs))
                    current_main = None
                    current_subs = []
                else:
                    current_subs.append(seg)

    if current_main is not None:
        blocks.append((current_main, current_subs))
    return blocks


def _expand_do_loops(blocks: List[Tuple[str, List[str]]]) -> List[Tuple[str, List[str]]]:
    """Expand bounded DO K1 = start:end ... ENDDO blocks (up to 500 total iterations)."""
    out: List[Tuple[str, List[str]]] = []
    idx = 0
    total_iters = 0
    while idx < len(blocks):
        main, subs = blocks[idx]
        m = re.match(r"^DO\s+(K[1-9][0-9]*)\s*=\s*(-?\d+)\s*:\s*(-?\d+)$", main, re.IGNORECASE)
        if m:
            var_name = m.group(1).upper()
            start_v = int(m.group(2))
            end_v = int(m.group(3))
            body = []
            idx += 1
            while idx < len(blocks) and blocks[idx][0].upper() != "ENDDO":
                body.append(blocks[idx])
                idx += 1
            step = 1 if end_v >= start_v else -1
            for val in range(start_v, end_v + step, step):
                total_iters += 1
                if total_iters > 500:
                    raise ValueError("DO loop exceeded maximum 500 iterations.")
                pattern = re.compile(rf"\b{var_name}\b|\${var_name}\b", re.IGNORECASE)
                for b_main, b_subs in body:
                    new_main = pattern.sub(str(val), b_main)
                    new_subs = [pattern.sub(str(val), s) for s in b_subs]
                    out.append((new_main, new_subs))
            idx += 1
            continue
        out.append((main, subs))
        idx += 1
    return out


def _parse_number_tokens(text: str) -> List[float]:
    """Parse space/comma-separated numbers and start:end ranges (e.g. '1:5 10')."""
    out: List[float] = []
    for tok in re.split(r"[\s,]+", text.strip()):
        if not tok:
            continue
        if ":" in tok:
            parts = tok.split(":", 1)
            a, b = int(parts[0]), int(parts[1])
            step = 1 if b >= a else -1
            if abs(b - a) > 10000:
                raise ValueError("Range cannot exceed 10,000 steps.")
            out.extend(float(x) for x in range(a, b + step, step))
        else:
            out.append(float(tok))
    return out


def execute_command_block(presenter, main_cmd: str, subcommands: List[str] | Tuple[str, ...] = ()) -> Any:
    """Execute one Minitab command statement (with optional subcommands)."""
    from .variable_dialogs import resolve_variables
    from .calculator import evaluate_advanced
    from .model import Column

    raw = main_cmd.strip()
    if not raw:
        raise ValueError("Enter a session command (for example: DESCRIBE C1, LET C3 = C1 + C2, INFO).")
    if raw.endswith(".") or raw.endswith(";"):
        raw = raw[:-1].strip()

    parts = raw.split(None, 1)
    verb = parts[0].upper()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if verb in ("DESCRIBE", "DESC"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        return presenter.describe_columns(indices)

    if verb in ("INFO", "INFORMATION"):
        return presenter.worksheet_information()

    if verb in ("CORRELATION", "CORR"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        return presenter.correlation(indices)

    if verb in ("NORMALITY", "NORM"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(indices) != 1:
            raise ValueError("NORMALITY takes one numeric column (e.g., NORMALITY C1).")
        return presenter.normality(indices[0])

    if verb == "LET":
        if "=" not in rest:
            raise ValueError("Syntax: LET C1 = expression or LET K1 = expression")
        lhs, expr = [s.strip() for s in rest.split("=", 1)]
        lhs_up = lhs.upper()
        if lhs_up.startswith("K") and lhs_up[1:].isdigit():
            k_idx = int(lhs_up[1:]) - 1
            vals = evaluate_advanced(expr, presenter.worksheet)
            scalar = vals[0] if vals else None
            if scalar is not None and not isinstance(scalar, (int, float)):
                raise ValueError("Stored constant value must be numeric.")
            while len(presenter.worksheet.constants) <= k_idx:
                next_num = len(presenter.worksheet.constants) + 1
                presenter.worksheet.constants.append(Column(f"K{next_num}", "number", [None]))
            presenter.worksheet.constants[k_idx].kind = "number"
            presenter.worksheet.constants[k_idx].values = [None if scalar is None else float(scalar)]
            presenter.dirty = True
            return presenter._record("Let Constant", {"constant": lhs_up, "expression": expr, "value": scalar})
        if lhs_up.startswith("C") and lhs_up[1:].isdigit():
            c_idx = int(lhs_up[1:]) - 1
            if 0 <= c_idx < len(presenter.worksheet.columns):
                try:
                    return presenter.assign_formula(c_idx, expr)
                except ValueError:
                    pass
        return presenter.calculate(expr, lhs)

    if verb == "NAME":
        tokens = rest.split(None, 1)
        if len(tokens) != 2:
            raise ValueError("Syntax: NAME C1 'ColumnName'")
        indices = resolve_variables(tokens[0], presenter.worksheet, ("number", "text", "date"))
        clean_name = tokens[1].strip().strip("'\"")
        presenter.rename_column(indices[0], clean_name)
        return presenter._record("Name Column", {"column": "C" + str(indices[0] + 1), "name": clean_name})

    if verb == "ERASE":
        indices = resolve_variables(rest, presenter.worksheet, ("number", "text", "date"))
        presenter.erase_variables(indices=indices)
        return presenter._record("Erase Variables", {"columns": ["C" + str(i + 1) for i in indices]})

    if verb == "SET":
        m = re.match(r"^(C[1-9][0-9]*)\s*(.*)$", rest, re.IGNORECASE)
        if not m:
            raise ValueError("Syntax: SET C1 1 2 3 or SET C1; 1:10.")
        col_tok, inline_vals = m.group(1).upper(), m.group(2).strip()
        col_idx = int(col_tok[1:]) - 1
        val_text = " ".join([inline_vals] + list(subcommands)).strip()
        nums = _parse_number_tokens(val_text)
        return presenter.set_column_values(col_idx, nums, "number")

    if verb in ("HISTOGRAM", "HIST"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(indices) != 1:
            raise ValueError("HISTOGRAM takes one numeric column (e.g., HISTOGRAM C1).")
        from .recipes import run
        return run(presenter, {"action": "graph", "parameters": {"method": "histogram", "indices": indices, "bins": 10}})

    if verb in ("BOXPLOT", "BOX"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(indices) != 1:
            raise ValueError("BOXPLOT takes one numeric column (e.g., BOXPLOT C1).")
        from .recipes import run
        return run(presenter, {"action": "graph", "parameters": {"method": "boxplot", "indices": indices, "bins": 1}})

    if verb == "PLOT":
        cleaned = rest.replace("*", " ")
        indices = resolve_variables(cleaned, presenter.worksheet, ("number",))
        if len(indices) != 2:
            raise ValueError("Syntax: PLOT C2 * C1 (Y then X)")
        return presenter.scatter_plot(indices[1], indices[0])

    if verb in ("REGRESS", "REGR"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(indices) < 2:
            raise ValueError("Syntax: REGRESS C_response C_predictor1 [C_predictor2 ...]")
        return presenter.multiple_regression(indices[0], indices[1:])

    if verb in ("ONEWAY", "AOVONEWAY", "ANOVA"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(indices) == 2:
            return presenter.oneway_anova(response_index=indices[0], factor_index=indices[1])
        elif len(indices) > 2:
            return presenter.oneway_anova_unstacked(indices)
        raise ValueError("Syntax: ONEWAY C_response C_factor or ONEWAY C1 C2 C3...")

    if verb in ("TTEST", "TINTERVAL"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if not indices:
            raise ValueError("Syntax: TTEST C1 [C2 ...]")
        return presenter.one_sample_t({"sample_cols": indices})

    if verb in ("TWOSAMPLE", "TWOSAMPLE-T"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(indices) != 2:
            raise ValueError("Syntax: TWOSAMPLE C1 C2")
        return presenter.two_sample_t({"data_format": 1, "sample1_col": indices[0], "sample2_col": indices[1]})

    if verb in ("XBARCHART", "XBAR-R"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(indices) == 2:
            return presenter.xbar_r_stacked(response_index=indices[0], factor_index=indices[1])
        elif len(indices) > 2:
            return presenter.xbar_r_rows(indices)
        raise ValueError("Syntax: XBARCHART C_response C_subgroup or XBARCHART C1 C2 ...")

    if verb in ("IMR", "ICHART"):
        indices = resolve_variables(rest, presenter.worksheet, ("number",))
        if not indices:
            raise ValueError("Syntax: IMR C1")
        return presenter.imr_chart({"variables": indices, "options": {}})

    if verb in ("CAPABILITY", "CAPA"):
        indices = resolve_variables(rest.split()[0] if rest else "", presenter.worksheet, ("number",))
        if not indices:
            raise ValueError("Syntax: CAPABILITY C1; LSPEC lsl; USPEC usl.")
        lspec = uspec = target = None
        for sub in subcommands:
            sp = sub.split(None, 1)
            if not sp:
                continue
            sverb = sp[0].upper()
            sval = float(sp[1].strip()) if len(sp) > 1 else None
            if sverb in ("LSPEC", "LSL"):
                lspec = sval
            elif sverb in ("USPEC", "USL"):
                uspec = sval
            elif sverb == "TARGET":
                target = sval
        return presenter.normal_capability(indices[0], lspec, uspec, target)

    if verb == "TALLY":
        indices = resolve_variables(rest, presenter.worksheet, ("number", "text", "date"))
        return presenter.tally_variables({"columns": indices})

    if verb == "INDICATOR":
        indices = resolve_variables(rest, presenter.worksheet, ("number", "text", "date"))
        if len(indices) != 1:
            raise ValueError("Syntax: INDICATOR C1")
        return presenter.make_indicator_variables(indices[0])

    if verb == "SUBSET":
        cond = rest
        name = "Subset"
        for sub in subcommands:
            sp = sub.split(None, 1)
            if not sp:
                continue
            if sp[0].upper() in ("WHERE", "CONDITION") and len(sp) > 1:
                cond = sp[1].strip()
            elif sp[0].upper() == "NAME" and len(sp) > 1:
                name = sp[1].strip().strip("'\"")
        if not cond:
            raise ValueError("Syntax: SUBSET; WHERE C1 > 10.")
        return presenter.subset_worksheet_by_condition(cond, name=name)

    if verb == "RANDOM":
        tokens = rest.split()
        if len(tokens) < 2:
            raise ValueError("Syntax: RANDOM N C1 [; NORMAL mu sigma.]")
        n_rows = int(tokens[0])
        col_tok = tokens[1].upper()
        target_idx = int(col_tok[1:]) - 1 if col_tok.startswith("C") and col_tok[1:].isdigit() else -1
        dist_name = "Normal"
        dist_params: Tuple[float, ...] = (0.0, 1.0)
        for sub in subcommands:
            sp = sub.split()
            if not sp:
                continue
            dkey = sp[0].upper()
            pvals = [float(x) for x in sp[1:]]
            alias_map = {
                "NORMAL": ("Normal", (0.0, 1.0)),
                "UNIFORM": ("Uniform", (0.0, 1.0)),
                "EXPONENTIAL": ("Exponential", (1.0,)),
                "POISSON": ("Poisson", (5.0,)),
                "BINOMIAL": ("Binomial", (10.0, 0.5)),
                "WEIBULL": ("Weibull", (2.0, 1.0)),
                "GAMMA": ("Gamma", (2.0, 1.0)),
                "LOGNORMAL": ("Lognormal", (0.0, 1.0)),
                "BETA": ("Beta", (2.0, 2.0)),
                "INTEGER": ("Integer", (1.0, 10.0)),
            }
            if dkey in alias_map:
                dist_name, defaults = alias_map[dkey]
                dist_params = tuple(pvals) if pvals else defaults
        return presenter.generate_random_distribution_data(target_idx, dist_name, n_rows, dist_params)

    if verb == "SORT":
        indices = resolve_variables(rest, presenter.worksheet, ("number", "text", "date"))
        if len(indices) < 1:
            raise ValueError("Syntax: SORT C1 [by C2]")
        return presenter.sort_columns(indices[:-1] or indices, indices[-1])

    if verb == "RANK":
        tokens = rest.split()
        if len(tokens) != 2:
            raise ValueError("Syntax: RANK C1 C2")
        indices = resolve_variables(tokens[0], presenter.worksheet, ("number",))
        return presenter.rank_column(indices[0], tokens[1])

    if verb == "CCF":
        fields = rest.split(maxsplit=1)
        lag_count = int(fields[0]) if len(fields) == 2 and fields[0].isdigit() else 0
        variables = fields[1] if lag_count or len(fields) == 2 and fields[0] == "0" else rest
        indices = resolve_variables(variables, presenter.worksheet, ("number",))
        if len(indices) != 2:
            raise ValueError("Use CCF [lags] C1 C2.")
        return presenter.cross_correlation(*indices, lags=lag_count)

    if verb in ("RSCR", "RSCRIPT", "R"):
        from .r_bridge import execute_r_code
        code = rest.strip()
        if (code.startswith('"') and code.endswith('"')) or (code.startswith("'") and code.endswith("'")):
            target_path = code[1:-1]
        else:
            target_path = code
        if os.path.isfile(target_path):
            code = Path(target_path).read_text(encoding="utf-8")
        res = execute_r_code(code, worksheet=presenter.worksheet)
        session_out = f"R Output:\n{res.get('stdout', '')}"
        if res.get("stderr"):
            session_out += f"\nR Diagnostics:\n{res['stderr']}"
        return presenter._record("R Script Output", {
            "analysis": "r_script",
            "session_text": session_out,
            "stdout": res.get("stdout", ""),
            "stderr": res.get("stderr", ""),
            "plot_path": res.get("plot_path"),
        })

    def _split_eq(expr_str: str) -> Tuple[List[int], List[int]]:
        if "=" in expr_str:
            lhs_s, rhs_s = expr_str.split("=", 1)
            return (
                resolve_variables(lhs_s, presenter.worksheet, ("number", "text")),
                resolve_variables(rhs_s, presenter.worksheet, ("number", "text")),
            )
        cols_all = resolve_variables(expr_str, presenter.worksheet, ("number", "text"))
        if len(cols_all) < 2:
            raise ValueError("Provide response and predictor columns (e.g., CMD C1 = C2 C3).")
        return [cols_all[0]], cols_all[1:]

    if verb == "BOOTSTRAP":
        cols = resolve_variables(rest, presenter.worksheet, ("number",))
        opts = {k.upper(): v for k, v in (sub.split(None, 1) for sub in subcommands if sub.strip() and " " in sub.strip())}
        n_res = int(opts.get("RESAMPLES", 1000))
        stat = opts.get("STATISTIC", "Mean" if len(cols) == 1 else "Mean Difference")
        if len(cols) == 1:
            return presenter.bootstrap_1sample(cols[0], statistic=stat, n_resamples=n_res)
        if len(cols) == 2:
            return presenter.bootstrap_2sample(cols[0], cols[1], statistic=stat, n_resamples=n_res)
        raise ValueError("Syntax: BOOTSTRAP C1 [C2]")

    if verb == "RANDTEST":
        cols = resolve_variables(rest, presenter.worksheet, ("number",))
        if len(cols) == 1:
            return presenter.randomization_1sample(cols[0], n_resamples=1000)
        if len(cols) == 2:
            return presenter.randomization_2sample(cols[0], cols[1], n_resamples=1000)
        raise ValueError("Syntax: RANDTEST C1 [C2]")

    if verb == "PGOF":
        cols = resolve_variables(rest, presenter.worksheet, ("number",))
        return presenter.goodness_of_fit_poisson(cols[0])

    if verb == "NBREG":
        lhs, rhs = _split_eq(rest)
        return presenter.negative_binomial_regression(lhs[0], rhs)

    if verb == "BANOVA":
        lhs, rhs = _split_eq(rest)
        return presenter.balanced_anova(lhs[0], rhs)

    if verb == "NESTED":
        lhs, rhs = _split_eq(rest)
        return presenter.fully_nested_anova(lhs[0], rhs)

    if verb == "MANOVA":
        lhs, rhs = _split_eq(rest)
        return presenter.oneway_manova(lhs, rhs[0])

    if verb in ("REML", "MIXED"):
        lhs, rhs = _split_eq(rest)
        rnd_cols = []
        for sub in subcommands:
            if sub.strip().upper().startswith("RANDOM "):
                rnd_cols.extend(resolve_variables(sub.strip()[7:], presenter.worksheet, ("number", "text")))
        fixed_cols = [c for c in rhs if c not in rnd_cols]
        if not rnd_cols:
            rnd_cols = [rhs[-1]]
            fixed_cols = rhs[:-1]
        return presenter.fit_mixed_reml(lhs[0], fixed_indices=fixed_cols, random_indices=rnd_cols)

    if verb == "COXPH":
        lhs, rhs = _split_eq(rest)
        if len(lhs) != 2:
            raise ValueError("Syntax: COXPH Time Event = Covariates")
        return presenter.cox_ph_regression(lhs[0], lhs[1], rhs)

    if verb == "SIXSIGMA":
        cols = resolve_variables(rest, presenter.worksheet, ("number",))
        lsl, usl, sub_sz = None, None, 1
        for sub in subcommands:
            toks = sub.strip().split()
            if len(toks) >= 2 and toks[0].upper() == "LSL":
                lsl = float(toks[1])
            elif len(toks) >= 2 and toks[0].upper() == "USL":
                usl = float(toks[1])
            elif len(toks) >= 2 and toks[0].upper() == "SUBGROUP":
                sub_sz = int(float(toks[1]))
        return presenter.six_sigma_process_report(cols[0], lsl=lsl, usl=usl, subgroup_size=sub_sz)

    if verb == "RANDOMFOREST":
        lhs, rhs = _split_eq(rest)
        return presenter.random_forest(lhs[0], rhs)

    if verb == "TREENET":
        lhs, rhs = _split_eq(rest)
        return presenter.treenet_gbm(lhs[0], rhs)

    if verb == "MARS":
        lhs, rhs = _split_eq(rest)
        return presenter.mars_regression(lhs[0], rhs)

    if verb == "BESTMODEL":
        lhs, rhs = _split_eq(rest)
        return presenter.discover_best_model(lhs[0], rhs)

    if verb == "MONTECARLO":
        inputs_s = rest or "X1: Normal(10, 0.5)"
        formula_s = "X1"
        lsl, usl, n_sims = None, None, 5000
        for sub in subcommands:
            s_up = sub.strip().upper()
            if s_up.startswith("FORMULA "):
                formula_s = sub.strip()[8:].strip().strip('"').strip("'")
            elif s_up.startswith("INPUTS "):
                inputs_s = sub.strip()[7:].strip().strip('"').strip("'")
            elif s_up.startswith("LSL "):
                lsl = float(sub.strip().split()[1])
            elif s_up.startswith("USL "):
                usl = float(sub.strip().split()[1])
            elif s_up.startswith("SIMS "):
                n_sims = int(float(sub.strip().split()[1]))
        return presenter.monte_carlo_simulation(inputs_s, formula_s, lsl=lsl, usl=usl, n_sims=n_sims)

    raise ValueError(f"Unsupported session command '{verb}'.")


def execute_script(presenter, script_text: str) -> List[Any]:
    """Parse and run a multi-statement Minitab Exec / session command script."""
    blocks = _expand_do_loops(parse_script_blocks(script_text))
    if not blocks:
        raise ValueError("Script contains no executable session commands.")
    results = []
    for main_cmd, subcommands in blocks:
        results.append(execute_command_block(presenter, main_cmd, subcommands))
    return results
