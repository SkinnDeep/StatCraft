import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview97-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

contract = '''# StatCraft Preview 97 Contract: CAD-Style 3D Surface & 2D Contour Navigation and Extrema Identification

## Capabilities
1. CAD-Style 3D Surface Navigation (RSM, Model Surface, 3D Scatter & Surface):
   - Orbit/Tilt/Rotate: Left-click drag adjusts azimuth and elevation angles smoothly.
   - Pan: Right-click drag, Middle-click drag, or Shift + Left-click drag translates coordinates (`pan_x`, `pan_y`).
   - Zoom: Mouse wheel scroll scales view smoothly (`zoom * exp(steps * 0.12)`).
   - Reset: Double-clicking viewport or clicking HUD reset button returns camera to `DEFAULT_VIEW`.
   - Cursor feedback: OpenHandCursor on viewport hover, ClosedHandCursor during orbit drag, SizeAllCursor during pan drag.

2. Visual Identification of Peaks (Maximum) and Troughs (Minimum) in 3D:
   - 3D Beacon pins & drop stems at global maximum (Peak) and global minimum (Trough).
   - Glowing pinheads & floating badge pills (`▲ MAX: <val>`, `▼ MIN: <val>`).
   - Press / Click interaction: Clicking on peak or minimum pins/badges displays an interactive CAD inspection callout card with exact response fit $\\hat{Y}$, factor coordinates $(X_1, X_2)$, and hold factors.
   - Clicking anywhere on the 3D surface probes the nearest surface vertex and displays inspection coordinates.
   - Interactive HUD pill bar in top-left corner: `[▲ Peak Max]`, `[▼ Trough Min]`, `[⟲ Reset CAD]`.

3. Visual Peak / Minimum Identification & Probing in 2D Contours:
   - Concentric target reticles and crosshairs with badge pills (`▲ MAX: <val>`, `▼ MIN: <val>`).
   - Interactive HUD buttons: `[▲ Max: <val>]`, `[▼ Min: <val>]`.
   - Press / Click interaction: Clicking on peak/minimum reticles or HUD buttons pins an interactive CAD inspection callout card.
   - Continuous Bilinear Interpolation Probing: Clicking anywhere inside the 2D contour plot bilinearly interpolates the response fit on the grid, drawing a target reticle and displaying exact $(\\hat{Y}, X_1, X_2)$ coordinates.

## Constraints & Compatibility
- Dual execution verified: 100% unit tests passed (1,975/1,975) and packaged frozen binary verified.
- Benchmark fixtures (`quiz1.mpx`, `MFGEN 401...mpx`) remain strictly unmodified.
- Full native parity flag remains `native_full_parity: false`.
'''
(out / 'StatCraft-preview97-contract.md').write_text(contract, encoding='utf-8')

text = f'''# StatCraft preview97 - 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview97.exe**.

StatCraft Preview 97 delivers CAD-style interactive 3D navigation and visual Peak/Minimum identification across RSM model plots (3D surface, 2D contour, and expanded 3D charts):

1. **CAD-Style Interactive 3D Navigation**:
   - **Tilt / Orbit / Rotate**: Left-click drag adjusts camera azimuth and elevation in real-time.
   - **Pan**: Right-click drag, Middle-click drag, or Shift + Left-click drag pans the model in screen space (`pan_x`, `pan_y`).
   - **Zoom**: Smooth mouse wheel zoom scaling centered on the model viewport.
   - **Reset**: Double-click anywhere on the 3D viewport or click the HUD reset button `[⟲ Reset CAD]` to reset camera.
   - **Cursor Semantics**: Responsive cursor switching between OpenHand, ClosedHand, and SizeAll.

2. **Visual Identification of Peaks & Minimums in 3D**:
   - **3D Beacon Pins & Drop Stems**: Vertical dashed stems dropped from bounding box floor up to global maximum (Peak) and minimum (Trough) vertices.
   - **Glowing Pinheads & Badges**: Glowing beacons with floating badge pills (`▲ MAX: <val>`, `▼ MIN: <val>`).
   - **Click-to-Inspect**: Clicking Peak/Min pins or badges pins an interactive CAD Inspection Callout Card with fitted response $\\hat{{Y}}$, factor coordinates $(X_1, X_2)$, and hold settings.
   - **Surface Vertex Probing**: Clicking anywhere on the 3D surface probes the nearest vertex and displays inspection callout card.
   - **Interactive Top HUD Bar**: Quick-access HUD buttons `[▲ Peak Max]`, `[▼ Trough Min]`, and `[⟲ Reset CAD]`.

3. **Visual Identification & Bilinear Probing in 2D Contours**:
   - **Concentric Reticles & Crosshairs**: Visual peak (coral red) and minimum (cyan/blue) target reticles and badge pills on the 2D contour map.
   - **Contour HUD Buttons**: `[▲ Max: <val>]` and `[▼ Min: <val>]` for one-click extremum inspection.
   - **Bilinear Surface Interpolation**: Clicking anywhere inside the contour plot computes exact interpolated response fit $\\hat{{Y}}$ via 2D bilinear interpolation, rendering a reticle marker and inspection callout card.

4. **Expanded 3D Charts Parity**:
   - Full CAD Pan support (`pan_x`, `pan_y`), smooth wheel zoom, and double-click reset added to `ExpandedChartWidget`.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview97-contract.md)
- [Release verification](StatCraft-preview97-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-97-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview97'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview97 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview 97 handoff and priority list updated')
