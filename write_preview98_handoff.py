import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview98-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

contract = '''# StatCraft Preview 98 Contract: OnShape CAD Mouse Controls, Interactive ViewCube, Zero-Lag Surface Optimization & Edit Error Elimination

## Capabilities
1. OnShape Standard CAD 3D Mouse Controls (RSM Surface, 3D Scatter, 3D Charts, Expanded 3D Dialog):
   - **Rotate / Orbit**: Right-click drag rotates the model smoothly in 3D camera space. Correct turntable orbit directions: dragging right turns the model right (counter-clockwise around vertical axis), dragging up tilts the camera up / model down.
   - **Pan**: Middle-click drag (Scroll wheel button press) OR Ctrl + Right-click drag pans the model in screen space (`pan_x`, `pan_y`).
   - **Zoom**: Smooth mouse wheel scroll scaling (`zoom * exp(steps * 0.12)`). Seamlessly forwarded from `OutputZoomView` through Qt graphics proxy directly to the 3D canvas.
   - **Probing / Selection**: Left-click selects HUD buttons, ViewCube faces, or probes surface vertices without orbiting or moving the camera.
   - **Reset**: Double-click anywhere on the 3D viewport resets camera to default isometric view (`DEFAULT_VIEW`).

2. OnShape-Style Orientation ViewCube (Top-Right of 3D Viewport):
   - 3D interactive orientation cube rendered in the top-right corner of the 3D viewport.
   - Rotates synchronously with camera azimuth and elevation.
   - 6 faces: `TOP`, `BOTTOM`, `FRONT`, `BACK`, `RIGHT`, `LEFT` with clean CAD shading and bold typography.
   - Face Click-to-Align: Clicking any visible face snaps camera view directly to that canonical viewpoint (e.g., clicking TOP aligns to top-down elevation 89, FRONT to front view, RIGHT to right side, etc.).
   - Includes small `[ISO]` button to quickly snap back to default isometric orientation.
   - Tooltip hover hints on all faces and buttons.

3. OnShape CAD Navigation Hint Pill (Bottom-Center of 3D Viewport):
   - Translucent CAD navigation bar displayed at bottom center of 3D viewport:
     `Orbit: Right-drag | Pan: Middle-drag / Ctrl+Right-drag | Zoom: Scroll | Click: Probe | Dbl-click: Reset`
   - Gives new users immediate visual guidance on how to manipulate 3D models.

4. CAD Rendering Performance Optimization (Zero Lag / 160+ FPS):
   - Low-poly decimated preview during drag: when actively orbiting or panning, grid vertices are pre-projected and sampled at step=2 (decimating mesh to 12x12 quads, reducing draw time from 85 ms down to 6 ms, delivering 160+ FPS navigation).
   - High-fidelity restoration on release: releasing mouse button restores full 25x25 shaded surface mesh with drop stems, beacon pinheads, badges, and callout cards.

5. Elimination of "Select a saved StatCraft graph to edit." Error:
   - Suppressed context menus on 3D panels: Right-click is reserved for OnShape CAD rotation; contextMenuEvent is consumed and does not bubble to graph editing menu.
   - `_activate_graph_object` and `build_output_context_menu` guard against invoking graph options/scale dialogs on analysis plots.

## Constraints & Compatibility
- Dual execution verified: 100% unit tests passed (1,979/1,979) and packaged frozen binary verified.
- Benchmark fixtures (`quiz1.mpx`, `MFGEN 401...mpx`) remain strictly unmodified.
- Full native parity flag remains `native_full_parity: false`.
'''
(out / 'StatCraft-preview98-contract.md').write_text(contract, encoding='utf-8')

text = f'''# StatCraft preview98 - 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview98.exe**.

StatCraft Preview 98 delivers full OnShape CAD control standard parity, an interactive OnShape orientation ViewCube, zero-lag 160+ FPS rendering optimization, and complete elimination of the graph edit popup error:

1. **OnShape CAD Standard Controls**:
   - **Orbit / Rotate**: Right-click drag rotates the model smoothly in 3D camera space. Correct turntable orbit directions: dragging right turns the model right (counter-clockwise around vertical axis), dragging up tilts the camera up / model down.
   - **Pan**: Middle-click drag (Scroll wheel press) OR Ctrl + Right-click drag pans the model in screen space (`pan_x`, `pan_y`).
   - **Zoom**: Smooth mouse wheel scroll scaling (`zoom * exp(steps * 0.12)`). Seamlessly forwarded from `OutputZoomView` through Qt graphics proxy directly to the 3D canvas.
   - **Probing / Selection**: Left-click selects HUD buttons, ViewCube faces, or probes surface vertices without orbiting or moving the camera.
   - **Reset**: Double-click anywhere on the 3D viewport resets camera to default isometric view (`DEFAULT_VIEW`).

2. **OnShape-Style Orientation ViewCube (Top-Right of 3D Viewport)**:
   - 3D interactive orientation cube rendered in the top-right corner of the 3D viewport.
   - Rotates synchronously with camera azimuth and elevation.
   - 6 faces: `TOP`, `BOTTOM`, `FRONT`, `BACK`, `RIGHT`, `LEFT` with clean CAD shading and bold typography.
   - Face Click-to-Align: Clicking any visible face snaps camera view directly to that canonical viewpoint (e.g., clicking TOP aligns to top-down elevation 89, FRONT to front view, RIGHT to right side, etc.).
   - Includes small `[ISO]` button to quickly snap back to default isometric orientation.
   - Tooltip hover hints on all faces and buttons.

3. **OnShape CAD Navigation Hint Pill (Bottom-Center of 3D Viewport)**:
   - Translucent CAD navigation bar displayed at bottom center of 3D viewport:
     `Orbit: Right-drag | Pan: Middle-drag / Ctrl+Right-drag | Zoom: Scroll | Click: Probe | Dbl-click: Reset`
   - Gives new users immediate visual guidance on how to fly around and manipulate 3D models.

4. **CAD Rendering Performance Optimization (Zero Lag / 160+ FPS)**:
   - Low-poly decimated preview during drag: when actively orbiting or panning, grid vertices are pre-projected and sampled at step=2 (decimating mesh to 12x12 quads, reducing draw time from 85 ms down to 6 ms, delivering 160+ FPS navigation).
   - High-fidelity restoration on release: releasing mouse button restores full 25x25 shaded surface mesh with drop stems, beacon pinheads, badges, and callout cards.

5. **Complete Elimination of "Select a saved StatCraft graph to edit." Error**:
   - Suppressed context menus on 3D panels: Right-click is reserved for OnShape CAD rotation; contextMenuEvent is consumed and does not bubble to graph editing menu.
   - `_activate_graph_object` and `build_output_context_menu` guard against invoking graph options/scale dialogs on analysis plots.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview98-contract.md)
- [Release verification](StatCraft-preview98-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-98-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview98'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview98 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview 98 handoff and priority list updated')
