from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
activity = (ROOT / "app/src/main/java/moe/honoka/npps4wrapper/ConfigEditorActivity.kt").read_text(encoding="utf-8")
styles = (ROOT / "app/src/main/res/values/styles.xml").read_text(encoding="utf-8")

required_activity = [
    "R.style.Widget_NPPS4Wrapper_ScrollableEditor",
    "EditText(\n                context,",
    "isVerticalScrollBarEnabled = true",
    "isHorizontalScrollBarEnabled = true",
    "isScrollbarFadingEnabled = false",
]
required_styles = [
    'name="Widget.NPPS4Wrapper.ScrollableEditor"',
    '<item name="android:scrollbars">horizontal|vertical</item>',
    "@drawable/npps4_scrollbar_thumb_vertical",
    "@drawable/npps4_scrollbar_thumb_horizontal",
    "@drawable/npps4_scrollbar_track_vertical",
    "@drawable/npps4_scrollbar_track_horizontal",
]

missing = [x for x in required_activity if x not in activity]
missing += [x for x in required_styles if x not in styles]
for name in [
    "npps4_scrollbar_thumb_vertical.xml",
    "npps4_scrollbar_thumb_horizontal.xml",
    "npps4_scrollbar_track_vertical.xml",
    "npps4_scrollbar_track_horizontal.xml",
]:
    if not (ROOT / "app/src/main/res/drawable" / name).is_file():
        missing.append(name)

if missing:
    raise SystemExit("scrollbar fix validation failed; missing: " + ", ".join(missing))
print("scrollbar fix validation: PASS")
